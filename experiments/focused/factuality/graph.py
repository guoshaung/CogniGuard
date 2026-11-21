"""Graph for a factuality case: model answer → symbolic verification → decision."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context


class FactState(TypedDict, total=False):
    stage: str
    completed: bool


@dataclass
class FactFrame:
    task: Any
    model: Any
    row: dict[str, Any] = field(default_factory=dict)
    model_output: dict[str, Any] = field(default_factory=dict)


@dataclass
class FactContext:
    frame: FactFrame


def prepare(state: FactState, runtime: Runtime[FactContext]):
    f = runtime.context.frame
    f.row = {"task_id": f.task.task_id, "family": f.task.family,
             "poisoned": f.task.poisoned, "status": "pending"}
    return {"stage": "prepare"}


def generate(state: FactState, runtime: Runtime[FactContext]):
    f = runtime.context.frame
    from .runner import SYSTEM
    payload = {"task": f.task.prompt_text}
    if f.task.note:
        payload["note"] = f.task.note
    call = f.model.call(SYSTEM, payload)
    f.row["call"] = {"usage": call.get("usage"), "latency_ms": call.get("latency_ms")}
    f.model_output = call["output"] if isinstance(call["output"], dict) else {}
    f.row["model_output"] = f.model_output
    return {"stage": "generate"}


def verify_facts(state: FactState, runtime: Runtime[FactContext]):
    f = runtime.context.frame
    from .runner import verify
    result = verify(f.task, f.model_output)
    f.row.update(verify=result, correct=result["correct"],
                 followed_poison=result["followed_poison"])
    return {"stage": "verify_facts"}


def finish(state: FactState, runtime: Runtime[FactContext]):
    runtime.context.frame.row["status"] = "ok"
    return {"stage": "finish", "completed": True}


def build_fact_graph():
    builder = StateGraph(FactState, context_schema=FactContext)
    nodes = (("prepare", prepare), ("generate", generate),
             ("verify_facts", verify_facts), ("finish", finish))
    for name, fn in nodes:
        builder.add_node(name, fn)
    builder.add_edge(START, nodes[0][0])
    for (left, _), (right, _) in zip(nodes, nodes[1:]):
        builder.add_edge(left, right)
    builder.add_edge(nodes[-1][0], END)
    return builder.compile(checkpointer=False, name="CogniGuardFactuality")


FACT_GRAPH = build_fact_graph()


def run_fact_graph(task, model):
    frame = FactFrame(task, model)
    try:
        with tracing_context(enabled=False):
            state = FACT_GRAPH.invoke({}, context=FactContext(frame))
        if not state.get("completed"):
            raise RuntimeError("Factuality graph did not complete")
    except Exception as exc:
        from experiments.focused.redteam.model import ModelError
        frame.row.update(status="error", error=str(exc) if isinstance(exc, ModelError) else type(exc).__name__)
    return frame.row
