from __future__ import annotations

from pathlib import Path

from experiments.evaluation.cg_v3_harness import CGV3Harness
from experiments.formal_v2.run_formal import (
    C2_METHODS,
    FOPD_METHODS,
    CG_METHODS,
    _c2_row,
    _fopd_row,
    _load_cases,
    _cg_row,
)


ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = ROOT / "experiments/datasets/cogniguard_math_suite/mixed_math_suite/splits/test"


class HiddenLabelGuard:
    def __getitem__(self, key: str):
        raise AssertionError(f"method attempted to access hidden evaluator field: {key}")

    def get(self, key: str, default=None):
        raise AssertionError(f"method attempted to access hidden evaluator field: {key}")


def test_method_adapters_cannot_access_hidden_labels() -> None:
    case = _load_cases(TEST_ROOT)[0]
    case["hidden"] = HiddenLabelGuard()
    for method in FOPD_METHODS:
        _fopd_row(case, method, 20260826)
    for method in C2_METHODS:
        _c2_row(case, method, 20260826)
    for method in CG_METHODS:
        _cg_row(case, method, 20260826)


def test_static_baseline_does_not_enable_dynamic_state_feedback() -> None:
    output = CGV3Harness(mode="static_cg", strict_execution_contract=True).run({
        "q_t": "math",
        "student_id": "s1",
        "session_id": "session",
        "round_id": "round",
        "resource_id": "r1",
        "chunk_ids": ["c1"],
        "C_u_t": {"knowledge_point": "math", "student_id": "s1"},
        "Pi_priv": {"allowed_fields": ["knowledge_point"], "forbidden_fields": ["student_id"]},
        "CR_t": {"resource_id": "r1", "chunk_id": "c1", "exposure_score": 0.8, "summary": "math"},
        "Pi_copy": {"allow_original": False, "max_exposure_score": 0.3},
        "provenance_evidence": {"confidence": 1.0},
        "capability_context": {"purpose": "legitimate_educational_interest"},
    })
    snapshot = output.Pi_joint["mechanism_snapshot"]
    assert snapshot["history_enabled"] is False
    assert snapshot["trust_enabled"] is False
    assert snapshot["dynamic_action_scoring_enabled"] is False
