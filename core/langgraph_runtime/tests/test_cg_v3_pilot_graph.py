from experiments.evaluation.cg_v3_pilot_graph import (
    PILOT_GRAPH, PilotFrame, run_pilot_graph,
)


def test_pilot_graph_carries_round_hash_and_state_across_episode_boundary():
    seen = []
    episodes = [
        {"episode_id": "ep-one", "scenario_type": "normal_teaching",
         "student_id": "s", "session_id": "session", "resource_id": "r",
         "privacy_budget": 1.0, "copyright_budget": 1.0,
         "initial_state": {"trust_score": 1.0},
         "round_sequence": [{"round_id": "r1"}, {"round_id": "r2"}]},
        {"episode_id": "ep-two", "scenario_type": "normal_teaching",
         "student_id": "s", "session_id": "session", "resource_id": "r",
         "privacy_budget": 1.0, "copyright_budget": 1.0,
         "initial_state": {"trust_score": 1.0},
         "round_sequence": [{"round_id": "r1"}]},
    ]

    def execute(mode, episode, round_spec, harness, previous_state,
                previous_hash, previous_actions):
        seen.append((episode["episode_id"], round_spec["round_id"], previous_hash))
        current_hash = f"{episode['episode_id']}:{round_spec['round_id']}"
        return {"latency_ms": 1.0}, previous_state, current_hash, ["allow"]

    records = run_pilot_graph(PilotFrame(
        mode="full_cg_v3", episodes=episodes,
        harness_factory=lambda **kwargs: object(),
        execute_round_fn=execute,
    ))
    assert seen == [
        ("ep-one", "r1", "GENESIS"),
        ("ep-one", "r2", "ep-one:r1"),
        ("ep-two", "r1", "GENESIS"),
    ]
    assert len(records) == 2
    assert records[0]["latency_ms"] == 2.0
    assert {"start_episode", "execute_round", "finish_episode",
            "advance_episode"} <= set(PILOT_GRAPH.get_graph().nodes)
