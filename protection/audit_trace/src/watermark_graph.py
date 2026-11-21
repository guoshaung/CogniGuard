"""LangGraph stage controller for HSW-ST rewrite, detection, audit and attack."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context


class WatermarkState(TypedDict, total=False):
    stage: str
    sample_index: int
    sample_count: int
    completed: bool


@dataclass
class WatermarkFrame:
    generator: Any
    result: Any = None


@dataclass
class WatermarkContext:
    frame: WatermarkFrame


def advance(label: str):
    def node(state: WatermarkState, runtime: Runtime[WatermarkContext]):
        observed = next(runtime.context.frame.generator)
        if isinstance(observed, tuple):
            stage, count = observed
        else:
            stage, count = observed, None
        if stage != label:
            raise RuntimeError(f"HSW-ST phase order changed: expected {label}, got {stage}")
        update = {"stage": label}
        if label == "prepare":
            update.update(sample_index=0, sample_count=count)
        return update
    node.__name__ = label
    return node


def next_sample(state: WatermarkState, runtime: Runtime[WatermarkContext]):
    return {"stage": "next_sample", "sample_index": state["sample_index"] + 1}


def persist(state: WatermarkState, runtime: Runtime[WatermarkContext]):
    frame = runtime.context.frame
    try:
        next(frame.generator)
    except StopIteration as stopped:
        frame.result = stopped.value
    else:
        raise RuntimeError("HSW-ST generator produced unexpected extra phase")
    return {"stage": "persist", "completed": True}


def build_watermark_graph():
    builder = StateGraph(WatermarkState, context_schema=WatermarkContext)
    for name in ("prepare", "rewrite", "detect", "audit", "attack", "clean_eval"):
        builder.add_node(name, advance(name))
    builder.add_node("next_sample", next_sample)
    builder.add_node("persist", persist)
    builder.add_edge(START, "prepare")
    builder.add_conditional_edges("prepare", lambda s: "sample" if s["sample_count"] else "clean",
                                  {"sample": "rewrite", "clean": "clean_eval"})
    builder.add_edge("rewrite", "detect")
    builder.add_edge("detect", "audit")
    builder.add_edge("audit", "attack")
    builder.add_edge("attack", "next_sample")
    builder.add_conditional_edges("next_sample",
                                  lambda s: "again" if s["sample_index"] < s["sample_count"] else "clean",
                                  {"again": "rewrite", "clean": "clean_eval"})
    builder.add_edge("clean_eval", "persist")
    builder.add_edge("persist", END)
    return builder.compile(checkpointer=False, name="CogniGuardHSWST")


WATERMARK_GRAPH = build_watermark_graph()


def run_watermark_graph(cfg: dict, mode: str):
    from .main import _watermark_steps
    frame = WatermarkFrame(_watermark_steps(cfg, mode))
    with tracing_context(enabled=False):
        state = WATERMARK_GRAPH.invoke({}, context=WatermarkContext(frame),
                                       config={"recursion_limit": 10000})
    if not state.get("completed"):
        raise RuntimeError("Watermark graph did not complete")
    return frame.result
