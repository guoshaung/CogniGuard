"""LangGraph sequencing for historical baseline and ablation suites.

Compute functions keep their existing signatures and output contracts. The
suite graph owns the ordered, side-effectful invocation of each experiment
step, with only step indices in state; no automatic retry/checkpointing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context


class SuiteState(TypedDict, total=False):
    index: int
    completed: bool


@dataclass
class SuiteFrame:
    steps: Sequence[tuple[str, Callable[[], Any]]]
    results: dict[str, Any] = field(default_factory=dict)


@dataclass
class SuiteContext:
    frame: SuiteFrame


def execute_step(state: SuiteState, runtime: Runtime[SuiteContext]):
    frame = runtime.context.frame
    name, fn = frame.steps[state["index"]]
    frame.results[name] = fn()
    return {}


def advance(state: SuiteState, runtime: Runtime[SuiteContext]):
    index = state["index"] + 1
    return {"index": index, "completed": index == len(runtime.context.frame.steps)}


def route(state: SuiteState, runtime: Runtime[SuiteContext]):
    return END if state["index"] >= len(runtime.context.frame.steps) else "execute_step"


def build_suite_graph():
    builder = StateGraph(SuiteState, context_schema=SuiteContext)
    builder.add_node("execute_step", execute_step)
    builder.add_node("advance", advance)
    builder.add_conditional_edges(START, route)
    builder.add_edge("execute_step", "advance")
    builder.add_conditional_edges("advance", route)
    return builder.compile(checkpointer=False, name="CogniGuardResearchSuite")


SUITE_GRAPH = build_suite_graph()


def run_sequential_suite(steps: Sequence[tuple[str, Callable[[], Any]]]) -> dict[str, Any]:
    names = [name for name, _ in steps]
    if len(names) != len(set(names)):
        raise ValueError("Suite step names must be unique")
    frame = SuiteFrame(steps)
    with tracing_context(enabled=False):
        state = SUITE_GRAPH.invoke(
            {"index": 0, "completed": not bool(steps)},
            context=SuiteContext(frame),
            config={"recursion_limit": max(50, 3 * len(steps) + 10)},
        )
    if not state.get("completed") or len(frame.results) != len(steps):
        raise RuntimeError("Research suite graph stopped before every step completed")
    return frame.results
