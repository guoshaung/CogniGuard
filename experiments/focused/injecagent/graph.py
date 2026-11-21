"""Pinned InjecAgent case graph with explicit first/second-stage routing."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context


class InjecState(TypedDict, total=False):
    stage: str
    needs_second_stage: bool
    cache_miss: bool
    completed: bool


@dataclass
class InjecFrame:
    job: dict[str, Any]
    model: Any
    assets: tuple
    item: dict[str, Any] = field(default_factory=dict)
    row: dict[str, Any] = field(default_factory=dict)
    system: str = ""
    user: str = ""
    response: str | None = None
    provenance: dict[str, Any] | None = None


@dataclass
class InjecContext:
    frame: InjecFrame


def prepare(state: InjecState, runtime: Runtime[InjecContext]):
    f = runtime.context.frame
    f.item = deepcopy(f.job["item"])
    f.row = {key: value for key, value in f.job.items() if key != "item"}
    f.row.update(status="pending", user_tool=f.item["User Tool"],
                 attacker_tools=f.item["Attacker Tools"],
                 attack_type=f.item["Attack Type"], official_item=deepcopy(f.item),
                 calls=[], real_tools_executed=0)
    return {"stage": "prepare"}


def render_first(state: InjecState, runtime: Runtime[InjecContext]):
    f = runtime.context.frame
    from .runner import render_input
    prompts, _, tools, _, _ = f.assets
    f.system, f.user = render_input(f.item, prompts[f.job["prompt"]], tools)
    return {"stage": "render_first"}


def call_first(state: InjecState, runtime: Runtime[InjecContext]):
    f = runtime.context.frame
    call = f.model.call_text(f.system, f.user)
    f.row["calls"].append(call)
    f.row["_latest_call"] = call
    return {"stage": "call_first"}


def evaluate_first(state: InjecState, runtime: Runtime[InjecContext]):
    f = runtime.context.frame
    from .runner import evaluate
    parser = f.assets[1]
    call = f.row.pop("_latest_call")
    f.row["stage1"] = evaluate(parser, call["output"], f.item)
    if call["finish_reason"] == "length":
        f.row["stage1"] = {"eval": "invalid", "invalid_reason": "output_truncated"}
    f.row["status"] = "ok"
    needed = (f.job["kind"] == "ds" and f.job["setting"] != "clean_control"
              and f.row["stage1"]["eval"] == "succ")
    return {"stage": "evaluate_first", "needs_second_stage": needed}


def resolve_response(state: InjecState, runtime: Runtime[InjecContext]):
    f = runtime.context.frame
    from .runner import cached_response
    parsed = f.row["stage1"]
    f.item["Attacker Tool Parameters"] = parsed["Attacker Tool Parameters"]
    f.item["Attacker Tool Thought"] = parsed["Attacker Tool Thought"]
    cache = f.assets[4]
    f.response, f.provenance = cached_response(
        cache, f.item["Attacker Tools"][0], f.item["Attacker Tool Parameters"]
    )
    return {"stage": "resolve_response", "cache_miss": f.response is None}


def simulate_response(state: InjecState, runtime: Runtime[InjecContext]):
    f = runtime.context.frame
    from .runner import load_module
    from experiments.focused.redteam.model import ModelError
    tools = f.assets[2]
    generation = load_module("injecagent_pinned_generation", "src/prompts/generation_prompts.py")
    simulation_prompt = generation.DS_ATTACKER_TOOL_RESPONSE_GEN_MESSAGE.format(
        example=generation.EXAMPLE,
        attacker_tool=json.dumps(tools[f.item["Attacker Tools"][0]], indent=True),
        tool_parameters=f.item["Attacker Tool Parameters"],
    )
    call = f.model.call_text(generation.SYSTEM_MESSAGE, simulation_prompt)
    f.row["simulation_call"] = call
    blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)```", call["output"])
    if not blocks:
        raise ModelError("模拟器没有返回官方要求的代码块；第二阶段未完成")
    f.response = blocks[0].strip()
    f.provenance = {"source": "mimo_generated_with_official_prompt"}
    return {"stage": "simulate_response"}


def render_second(state: InjecState, runtime: Runtime[InjecContext]):
    f = runtime.context.frame
    from .runner import render_input
    prompts, _, tools, _, _ = f.assets
    f.item["Attacker Tool Response"] = f.response
    f.row["simulation"] = {**f.provenance, "response": f.response}
    f.system, f.user = render_input(f.item, prompts[f.job["prompt"]], tools, step2=True)
    return {"stage": "render_second"}


def call_second(state: InjecState, runtime: Runtime[InjecContext]):
    f = runtime.context.frame
    call = f.model.call_text(f.system, f.user)
    f.row["calls"].append(call)
    f.row["_latest_call"] = call
    return {"stage": "call_second"}


def evaluate_second(state: InjecState, runtime: Runtime[InjecContext]):
    f = runtime.context.frame
    from .runner import evaluate
    call = f.row.pop("_latest_call")
    f.row["stage2"] = evaluate(f.assets[1], call["output"], f.item, step2=True)
    if call["finish_reason"] == "length":
        f.row["stage2"] = {"eval": "invalid", "invalid_reason": "output_truncated"}
    return {"stage": "evaluate_second"}


def finish(state: InjecState, runtime: Runtime[InjecContext]):
    return {"stage": "finish", "completed": True}


def build_injecagent_graph():
    builder = StateGraph(InjecState, context_schema=InjecContext)
    nodes = (("prepare", prepare), ("render_first", render_first),
             ("call_first", call_first), ("evaluate_first", evaluate_first),
             ("resolve_response", resolve_response), ("simulate_response", simulate_response),
             ("render_second", render_second), ("call_second", call_second),
             ("evaluate_second", evaluate_second), ("finish", finish))
    for name, fn in nodes:
        builder.add_node(name, fn)
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "render_first")
    builder.add_edge("render_first", "call_first")
    builder.add_edge("call_first", "evaluate_first")
    builder.add_conditional_edges("evaluate_first", lambda s: "second" if s["needs_second_stage"] else "done",
                                  {"second": "resolve_response", "done": "finish"})
    builder.add_conditional_edges("resolve_response", lambda s: "simulate" if s["cache_miss"] else "render",
                                  {"simulate": "simulate_response", "render": "render_second"})
    builder.add_edge("simulate_response", "render_second")
    builder.add_edge("render_second", "call_second")
    builder.add_edge("call_second", "evaluate_second")
    builder.add_edge("evaluate_second", "finish")
    builder.add_edge("finish", END)
    return builder.compile(checkpointer=False, name="CogniGuardInjecAgent")


INJECAGENT_GRAPH = build_injecagent_graph()


def run_injecagent_graph(job, model, assets):
    frame = InjecFrame(job, model, assets)
    try:
        with tracing_context(enabled=False):
            state = INJECAGENT_GRAPH.invoke({}, context=InjecContext(frame))
        if not state.get("completed"):
            raise RuntimeError("InjecAgent graph did not complete")
    except Exception as exc:
        from experiments.focused.redteam.model import ModelError
        frame.row.pop("_latest_call", None)
        frame.row.update(status="error", error=str(exc) if isinstance(exc, ModelError) else type(exc).__name__)
    return frame.row
