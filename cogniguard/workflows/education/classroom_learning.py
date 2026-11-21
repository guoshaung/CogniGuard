"""Fine-grained LangGraph stages for one classroom learning turn.

The existing domain calculations are advanced phase-by-phase through a
call-local generator. No student content enters graph state/checkpoints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from cogniguard.observability.graphs import invoke_observed_graph, observed_node
from cogniguard.observability.telemetry import SafeTelemetry

PHASES = (
    "select_student",
    "teaching_draft",
    "watermark_media",
    "audit_bindings",
    "learning_assessment",
    "next_step",
    "state_commit",
)


class LearningState(TypedDict, total=False):
    stage: str
    completed: bool


@dataclass
class LearningFrame:
    generator: Any
    result: dict[str, Any] | None = None
    recorder: SafeTelemetry = field(default_factory=SafeTelemetry)


@dataclass
class LearningContext:
    frame: LearningFrame


def phase(name: str):
    def advance(state: LearningState, runtime: Runtime[LearningContext]):
        observed = next(runtime.context.frame.generator)
        if observed != name:
            raise RuntimeError(f"Learning phase order changed: expected {name}, got {observed}")
        return {"stage": name}

    advance.__name__ = name
    return advance


def assemble_result(state: LearningState, runtime: Runtime[LearningContext]):
    frame = runtime.context.frame
    try:
        next(frame.generator)
    except StopIteration as stopped:
        frame.result = stopped.value
    else:
        raise RuntimeError("Learning generator produced an unexpected extra phase")
    if not isinstance(frame.result, dict):
        raise RuntimeError("Learning turn did not return a result")
    return {"stage": "assemble_result", "completed": True}


def build_learning_graph():
    builder = StateGraph(LearningState, context_schema=LearningContext)
    for name in PHASES:
        builder.add_node(name, observed_node("classroom_learning", name, phase(name)))
    builder.add_node(
        "assemble_result", observed_node("classroom_learning", "assemble_result", assemble_result)
    )
    builder.add_edge(START, PHASES[0])
    for left, right in zip(PHASES, PHASES[1:]):
        builder.add_edge(left, right)
    builder.add_edge(PHASES[-1], "assemble_result")
    builder.add_edge("assemble_result", END)
    return builder.compile(checkpointer=False, name="CogniGuardClassroomLearning")


LEARNING_GRAPH = build_learning_graph()


def run_learning_graph(
    state: dict, demo_case: Any, round_number: int, student_message: str, monitor=None
):
    from cogniguard.applications.education.classroom import _learning_turn_steps

    frame = LearningFrame(_learning_turn_steps(state, demo_case, round_number, student_message))
    result = invoke_observed_graph(
        LEARNING_GRAPH, {}, context=LearningContext(frame), frame=frame, monitor=monitor
    )
    if not result.get("completed") or frame.result is None:
        raise RuntimeError("Learning graph did not complete")
    return frame.result
