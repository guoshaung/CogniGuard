"""Per-turn LangGraph entrypoint for the classroom session.

Session payloads stay in the call-local context. The existing learning and
attack functions remain domain steps until their internal stages are split.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from cogniguard.observability.graphs import invoke_observed_graph, observed_node
from cogniguard.observability.telemetry import SafeTelemetry


class ClassroomState(TypedDict, total=False):
    stage: str
    attack: bool
    completed: bool


@dataclass
class ClassroomFrame:
    data_root: str | Path
    case_index: int
    turn_kind: str
    round_number: int
    student_message: str
    attack_type: str | None
    attack_prompt: str
    session_state: dict[str, Any] | None
    target_mastery: float
    episode_id: str | None
    cg_ablation: dict[str, Any] | None
    dialogue_mode: str | None
    demo_case: Any = None
    state: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    recorder: SafeTelemetry = field(default_factory=SafeTelemetry)


@dataclass
class ClassroomContext:
    frame: ClassroomFrame


def load_case(state: ClassroomState, runtime: Runtime[ClassroomContext]):
    f = runtime.context.frame
    from cogniguard.applications.education.cases import load_demo_case

    f.demo_case = load_demo_case(
        data_root=f.data_root, case_index=f.case_index, episode_id=f.episode_id
    )
    return {"stage": "load_case", "attack": f.turn_kind == "attack"}


def initialize(state: ClassroomState, runtime: Runtime[ClassroomContext]):
    f = runtime.context.frame
    from cogniguard.applications.education.classroom import (
        _initial_state,
        _normalize_cg_ablation,
        _normalize_dialogue_mode,
    )

    target = max(0.6, min(0.98, float(f.target_mastery)))
    mode = _normalize_dialogue_mode(f.dialogue_mode, f.session_state)
    f.state = _initial_state(f.demo_case, f.case_index, f.session_state, target, mode)
    f.state["goal"]["target_mastery"] = target
    f.state["cg_ablation"] = _normalize_cg_ablation(f.cg_ablation)
    f.state["dialogue_mode"] = mode
    f.state.setdefault("communication_logs", [])
    return {"stage": "initialize"}


def attack_turn(state: ClassroomState, runtime: Runtime[ClassroomContext]):
    f = runtime.context.frame
    from cogniguard.applications.education.classroom import _run_attack_turn

    f.result = _run_attack_turn(f.state, f.attack_type, f.attack_prompt.strip())
    return {"stage": "attack_turn"}


def learning_turn(state: ClassroomState, runtime: Runtime[ClassroomContext]):
    f = runtime.context.frame
    from cogniguard.applications.education.classroom import _run_learning_turn

    f.result = _run_learning_turn(
        f.state, f.demo_case, max(1, int(f.round_number)), f.student_message.strip()
    )
    return {"stage": "learning_turn"}


def finish(state: ClassroomState, runtime: Runtime[ClassroomContext]):
    return {"stage": "finish", "completed": True}


def build_classroom_graph():
    builder = StateGraph(ClassroomState, context_schema=ClassroomContext)
    for name, fn in (
        ("load_case", load_case),
        ("initialize", initialize),
        ("attack_turn", attack_turn),
        ("learning_turn", learning_turn),
        ("finish", finish),
    ):
        builder.add_node(name, observed_node("classroom", name, fn))
    builder.add_edge(START, "load_case")
    builder.add_edge("load_case", "initialize")
    builder.add_conditional_edges(
        "initialize",
        lambda s: "attack" if s["attack"] else "learning",
        {"attack": "attack_turn", "learning": "learning_turn"},
    )
    builder.add_edge("attack_turn", "finish")
    builder.add_edge("learning_turn", "finish")
    builder.add_edge("finish", END)
    return builder.compile(checkpointer=False, name="CogniGuardClassroom")


CLASSROOM_GRAPH = build_classroom_graph()


def run_classroom_graph(*, monitor=None, **kwargs):
    frame = ClassroomFrame(**kwargs)
    state = invoke_observed_graph(
        CLASSROOM_GRAPH, {}, context=ClassroomContext(frame), frame=frame, monitor=monitor
    )
    if not state.get("completed") or frame.result is None:
        raise RuntimeError("Classroom graph did not complete")
    return frame.result
