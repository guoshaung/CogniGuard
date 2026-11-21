"""Episode/round LangGraph orchestration for the CG V3 engineering pilot.

The CGV3Harness already executes an inner protection graph. This graph owns
the outer episode and cross-round feedback sequence so budget, trust and audit
hash continuity are no longer driven by an independent Python loop.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context


class PilotState(TypedDict, total=False):
    episode_index: int
    round_index: int
    completed: bool


@dataclass
class PilotFrame:
    mode: str
    episodes: list[dict[str, Any]]
    harness_factory: Callable[..., Any]
    execute_round_fn: Callable[..., tuple[dict[str, Any], dict[str, Any], str, list[str]]]
    strict_execution_contract: bool = False
    records: list[dict[str, Any]] = field(default_factory=list)
    harness: Any = None
    previous_state: dict[str, Any] = field(default_factory=dict)
    previous_hash: str = "GENESIS"
    previous_actions: list[str] = field(default_factory=list)
    round_records: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PilotContext:
    frame: PilotFrame


def start_episode(state: PilotState, runtime: Runtime[PilotContext]):
    f = runtime.context.frame
    episode = f.episodes[state["episode_index"]]
    f.harness = f.harness_factory(
        mode=f.mode, privacy_max=float(episode["privacy_budget"]),
        copyright_max=float(episode["copyright_budget"]),
        strict_execution_contract=f.strict_execution_contract)
    f.previous_state = dict(episode.get("initial_state", {}))
    f.previous_hash = "GENESIS"
    f.previous_actions = []
    f.round_records = []
    return {"round_index": 0}


def execute_round(state: PilotState, runtime: Runtime[PilotContext]):
    f = runtime.context.frame
    episode = f.episodes[state["episode_index"]]
    round_spec = episode["round_sequence"][state["round_index"]]
    row, f.previous_state, f.previous_hash, f.previous_actions = f.execute_round_fn(
        f.mode, episode, round_spec, f.harness, f.previous_state,
        f.previous_hash, f.previous_actions)
    f.round_records.append(row)
    return {}


def advance_round(state: PilotState, runtime: Runtime[PilotContext]):
    return {"round_index": state["round_index"] + 1}


def route_round(state: PilotState, runtime: Runtime[PilotContext]):
    f = runtime.context.frame
    episode = f.episodes[state["episode_index"]]
    return "execute_round" if state["round_index"] < len(episode["round_sequence"]) else "finish_episode"


def finish_episode(state: PilotState, runtime: Runtime[PilotContext]):
    f = runtime.context.frame
    episode = f.episodes[state["episode_index"]]
    f.records.append({
        "mode": f.mode, "episode_id": episode["episode_id"],
        "scenario_type": episode["scenario_type"],
        "student_id": episode["student_id"],
        "session_id": episode["session_id"],
        "resource_id": episode["resource_id"],
        "success_oracle": episode.get("success_oracle", {}),
        "privacy_budget": episode["privacy_budget"],
        "copyright_budget": episode["copyright_budget"],
        "rounds": f.round_records,
        "latency_ms": round(sum(item["latency_ms"] for item in f.round_records), 6),
    })
    return {}


def advance_episode(state: PilotState, runtime: Runtime[PilotContext]):
    index = state["episode_index"] + 1
    return {"episode_index": index,
            "round_index": 0,
            "completed": index == len(runtime.context.frame.episodes)}


def route_episode(state: PilotState, runtime: Runtime[PilotContext]):
    return "start_episode" if state["episode_index"] < len(runtime.context.frame.episodes) else END


def build_pilot_graph():
    builder = StateGraph(PilotState, context_schema=PilotContext)
    for name, fn in (
        ("start_episode", start_episode),
        ("execute_round", execute_round),
        ("advance_round", advance_round),
        ("finish_episode", finish_episode),
        ("advance_episode", advance_episode),
    ):
        builder.add_node(name, fn)
    builder.add_conditional_edges(START, route_episode)
    builder.add_conditional_edges("start_episode", route_round)
    builder.add_edge("execute_round", "advance_round")
    builder.add_conditional_edges("advance_round", route_round)
    builder.add_edge("finish_episode", "advance_episode")
    builder.add_conditional_edges("advance_episode", route_episode)
    return builder.compile(checkpointer=False, name="CogniGuardV3PilotEpisodes")


PILOT_GRAPH = build_pilot_graph()


def run_pilot_graph(frame: PilotFrame) -> list[dict[str, Any]]:
    count_rounds = sum(len(ep["round_sequence"]) for ep in frame.episodes)
    with tracing_context(enabled=False):
        state = PILOT_GRAPH.invoke(
            {"episode_index": 0, "round_index": 0,
             "completed": not bool(frame.episodes)},
            context=PilotContext(frame),
            config={"recursion_limit": max(50, 4 * count_rounds + 5 * len(frame.episodes) + 10)},
        )
    if not state.get("completed") or len(frame.records) != len(frame.episodes):
        raise RuntimeError("CG V3 pilot graph did not complete all episodes")
    return frame.records
