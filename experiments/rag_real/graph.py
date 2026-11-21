"""Batch graphs for locked public-corpus retrieval and control probes.

Neural model execution remains inside an isolated worker; the graph controls
protocol freeze, per-dataset/case progression and final artifact commitment.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context


class BatchState(TypedDict, total=False):
    stage: str
    item_index: int
    item_count: int
    completed: bool


@dataclass
class BatchFrame:
    generator: Any
    result: Any = None


@dataclass
class BatchContext:
    frame: BatchFrame


def prepare(state: BatchState, runtime: Runtime[BatchContext]):
    label, count = next(runtime.context.frame.generator)
    if label != "prepare" or not isinstance(count, int) or count < 0:
        raise RuntimeError("Invalid retrieval graph preparation")
    return {"stage": "prepare", "item_index": 0, "item_count": count}


def process_item(state: BatchState, runtime: Runtime[BatchContext]):
    if next(runtime.context.frame.generator) != "item":
        raise RuntimeError("Retrieval item phase changed")
    return {"stage": "process_item", "item_index": state["item_index"] + 1}


def finalize(state: BatchState, runtime: Runtime[BatchContext]):
    frame = runtime.context.frame
    try:
        next(frame.generator)
    except StopIteration as stopped:
        frame.result = stopped.value
    else:
        raise RuntimeError("Retrieval generator produced an extra phase")
    return {"stage": "finalize", "completed": True}


def build_batch_graph(name: str):
    builder = StateGraph(BatchState, context_schema=BatchContext)
    builder.add_node("prepare", prepare)
    builder.add_node("process_item", process_item)
    builder.add_node("finalize", finalize)
    builder.add_edge(START, "prepare")
    builder.add_conditional_edges("prepare", lambda s: "item" if s["item_count"] else "done",
                                  {"item": "process_item", "done": "finalize"})
    builder.add_conditional_edges("process_item",
                                  lambda s: "again" if s["item_index"] < s["item_count"] else "done",
                                  {"again": "process_item", "done": "finalize"})
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=False, name=name)


RETRIEVAL_GRAPH = build_batch_graph("CogniGuardRealRetrieval")
CONTROL_GRAPH = build_batch_graph("CogniGuardRealCorpusControl")


def invoke_batch(graph, generator, *, recursion_limit=100):
    frame = BatchFrame(generator)
    with tracing_context(enabled=False):
        state = graph.invoke({}, context=BatchContext(frame),
                             config={"recursion_limit": recursion_limit})
    if not state.get("completed"):
        raise RuntimeError("Real-corpus graph did not complete")
    return frame.result
