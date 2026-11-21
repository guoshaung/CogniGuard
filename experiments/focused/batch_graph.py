"""Parallel focused-experiment dispatch without putting case payloads in graph state.

Individual attack/teaching scenarios already have their own detailed graphs.
This graph owns the outer fan-out. Case objects and model clients remain in a
per-invocation context; only integer indices and completion counts are state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, Generic, Sequence, TypeVar, TypedDict, Annotated
import operator

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Send
from langsmith import tracing_context


Item = TypeVar("Item")
Result = TypeVar("Result")


class BatchState(TypedDict, total=False):
    index: int
    completed: Annotated[int, operator.add]


@dataclass
class BatchFrame(Generic[Item, Result]):
    items: Sequence[Item]
    worker: Callable[[Item], Result]
    on_result: Callable[[Result, int], None] | None = None
    results: list[Result] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)


@dataclass
class BatchContext:
    frame: BatchFrame[Any, Any]


def _fanout(state: BatchState, runtime: Runtime[BatchContext]):
    count = len(runtime.context.frame.items)
    return [Send("run_item", {"index": i}) for i in range(count)] if count else END


def _run_item(state: BatchState, runtime: Runtime[BatchContext]):
    frame = runtime.context.frame
    result = frame.worker(frame.items[state["index"]])
    with frame.lock:
        frame.results.append(result)
        if frame.on_result is not None:
            frame.on_result(result, len(frame.results))
    return {"completed": 1}


def build_batch_graph():
    builder = StateGraph(BatchState, context_schema=BatchContext)
    builder.add_node("run_item", _run_item)
    builder.add_conditional_edges(START, _fanout)
    builder.add_edge("run_item", END)
    return builder.compile(checkpointer=False, name="CogniGuardFocusedBatch")


BATCH_GRAPH = build_batch_graph()


def run_graph_batch(
    items: Sequence[Item], worker: Callable[[Item], Result], workers: int,
    on_result: Callable[[Result, int], None] | None = None,
) -> list[Result]:
    if not 1 <= workers <= 64:
        raise ValueError("workers must be between 1 and 64")
    frame = BatchFrame(items, worker, on_result)
    # Raw cases and outputs must not be exported through nested graph traces.
    with tracing_context(enabled=False):
        outcome = BATCH_GRAPH.invoke(
            {"completed": 0}, context=BatchContext(frame),
            config={"max_concurrency": workers},
        )
    if outcome.get("completed", 0) != len(items):
        raise RuntimeError("Focused batch did not complete every scheduled item")
    return frame.results
