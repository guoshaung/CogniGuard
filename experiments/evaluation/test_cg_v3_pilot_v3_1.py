from __future__ import annotations

from experiments.evaluation.cg_v3_pilot import MODES, _run_mode, check_anomalies, load_episodes


def test_v31_strict_modes_run_frozen_dataset() -> None:
    episodes = load_episodes()
    results = {mode: _run_mode(mode, episodes, strict_execution_contract=True) for mode in MODES}
    assert all(len(results[mode]) == 30 for mode in MODES)
    assert all(sum(len(item["rounds"]) for item in results[mode]) == 90 for mode in MODES)
    anomalies = check_anomalies(results)
    assert anomalies["plan_actual_inconsistency_events"] == []
    assert anomalies["budget_insufficient_allow_events"] == []
    assert anomalies["dual_budget_isolated"] is True


def test_v31_strict_full_blocks_copyright_reconstruction() -> None:
    episodes = [item for item in load_episodes() if item["scenario_type"] == "teacher_resource_stitching_attack"]
    results = _run_mode("full_cg_v3", episodes, strict_execution_contract=True)
    assert all(
        not {
            chunk
            for round_record in episode["rounds"]
            for chunk in round_record["actual_allowed_chunks"]
        }
        for episode in results
    )
