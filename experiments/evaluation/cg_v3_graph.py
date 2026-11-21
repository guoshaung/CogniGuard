"""Stage graph for CG V3: authorize, budget, compose, execute, commit, audit."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context


PHASES = ("authorize", "project_budgets", "select_plan", "execute",
          "commit", "audit_feedback")


class CGState(TypedDict, total=False):
    stage: str
    completed: bool


@dataclass
class CGFrame:
    generator: Any
    result: Any = None


@dataclass
class CGContext:
    frame: CGFrame


def advance(name):
    def node(state: CGState, runtime: Runtime[CGContext]):
        observed = next(runtime.context.frame.generator)
        if observed != name:
            raise RuntimeError(f"CG phase order changed: expected {name}, got {observed}")
        return {"stage": name}
    node.__name__ = name
    return node


def finalize(state: CGState, runtime: Runtime[CGContext]):
    frame = runtime.context.frame
    try:
        next(frame.generator)
    except StopIteration as stopped:
        frame.result = stopped.value
    else:
        raise RuntimeError("CG generator produced an extra phase")
    if frame.result is None:
        raise RuntimeError("CG graph did not produce an output")
    return {"stage": "finalize", "completed": True}


def build_cg_graph():
    builder = StateGraph(CGState, context_schema=CGContext)
    for name in PHASES:
        builder.add_node(name, advance(name))
    builder.add_node("finalize", finalize)
    builder.add_edge(START, PHASES[0])
    for left, right in zip(PHASES, PHASES[1:]):
        builder.add_edge(left, right)
    builder.add_edge(PHASES[-1], "finalize")
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=False, name="CogniGuardCGV3")


CG_GRAPH = build_cg_graph()


def run_cg_graph(owner, request, actual_student_context=None,
                 actual_teacher_resource=None, attack_indicators=None):
    frame = CGFrame(owner._run_steps(
        request, actual_student_context=actual_student_context,
        actual_teacher_resource=actual_teacher_resource,
        attack_indicators=attack_indicators,
    ))
    with tracing_context(enabled=False):
        state = CG_GRAPH.invoke({}, context=CGContext(frame))
    if not state.get("completed"):
        raise RuntimeError("CG graph did not complete")
    return frame.result
