from __future__ import annotations

import json

from experiments.evaluation.cg_v3_metrics import compute_mode_metrics
from experiments.evaluation.cg_v3_pilot import MODES, load_episodes, run_pilot


def test_fixed_pilot_dataset_has_six_episodes_per_scenario() -> None:
    episodes = load_episodes()
    assert len(episodes) == 30
    assert {item["scenario_type"] for item in episodes} == {
        "normal_teaching",
        "student_profile_split_attack",
        "teacher_resource_stitching_attack",
        "cross_domain_privacy_copyright_attack",
        "audit_tamper_low_trust",
    }
    assert all(len(item["round_sequence"]) == 3 for item in episodes)


def test_pilot_runs_all_modes_and_writes_auditable_results(tmp_path) -> None:
    result = run_pilot(results_dir=tmp_path)
    assert result["episode_count"] == 30
    assert result["round_count"] == 270
    assert set(result["summaries"]) == set(MODES)
    assert all(result["summaries"][mode]["round_count"] == 90 for mode in MODES)
    assert result["anomalies"]["episode_ids_same_across_modes"] is True
    assert result["anomalies"]["request_hashes_same_across_modes"] is True
    assert (tmp_path / "all_rounds.jsonl").exists()
    first_record = json.loads((tmp_path / "all_rounds.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert {"mode", "request_hash", "Pi_priv", "Pi_copy", "Pi_joint", "candidate_plans", "current_audit_hash"} <= set(first_record)
    assert compute_mode_metrics("full_cg_v3", []) ["episode_count"] == 0
