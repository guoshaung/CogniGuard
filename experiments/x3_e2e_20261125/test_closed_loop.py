"""Closed-loop checks for the shadow adapter and the real release gate."""

from __future__ import annotations

from experiments.x3_e2e_20261125.evaluate import evaluate
from experiments.x3_e2e_20261125.gate_probe import education_probe, software_probe
from experiments.x3_e2e_20261125.scenarios import FIVE, build_scenarios


def test_five_flips_accept_a_credential_and_reject_a_bare_watermark() -> None:
    report = evaluate(build_scenarios())
    assert [row["scenario_id"] for row in report["interface_regression"]] == list(FIVE)
    for row in report["interface_regression"]:
        assert row["watermark_only_allowed"] is False
        assert row["watermark_confirmed_propagation"] is False
        assert row["watermark_charged_budget"] is False
        assert row["credential_allowed"] is True
        assert row["credential_confirmed_propagation"] is False
        assert row["changes_production_path"] is False


def test_ordinary_watermark_matches_the_registry_baseline() -> None:
    report = evaluate(build_scenarios())
    for row in report["scenarios"]:
        assert row["arms"]["B4"]["allowed"] == row["arms"]["B0"]["allowed"]
        assert row["arms"]["B1"]["allowed"] == row["arms"]["B0"]["allowed"]
        assert row["arms"]["B4"]["confirmed_propagation"] is False
        assert row["arms"]["B4"]["charged_budget"] is False
        assert row["arms"]["Oracle"]["allowed"] is row["oracle_allow"]


def test_log_recovers_the_unrecorded_share_and_the_mark_does_not() -> None:
    report = evaluate(build_scenarios())
    row = next(item for item in report["scenarios"] if item["scenario_id"] == "unrecorded-share")
    assert row["oracle_allow"] is False
    assert row["arms"]["B0"]["allowed"] is True
    assert row["arms"]["B4"]["allowed"] is True
    assert row["arms"]["B2"]["allowed"] is True
    assert row["arms"]["B3"]["allowed"] is False
    assert row["arms"]["B3"]["reason"] == "reconstruction"
    assert row["arms"]["Ours"]["allowed"] is False
    assert row["arms"]["B3"]["confirmed_propagation"] is True
    assert row["arms"]["B4"]["confirmed_propagation"] is False


def test_residual_mark_and_detector_error_are_both_kept() -> None:
    report = evaluate(build_scenarios())
    residual = next(
        item for item in report["scenarios"] if item["scenario_id"] == "residual-mark-knowledge-gone"
    )
    mistake = next(item for item in report["scenarios"] if item["scenario_id"] == "detector-false-empty")
    assert residual["oracle_allow"] is False
    assert residual["arms"]["B2"]["allowed"] is True
    assert residual["arms"]["Ours"]["allowed"] is False
    assert residual["arms"]["Ours"]["reason"] == "mismatch"
    assert mistake["oracle_allow"] is True
    assert mistake["arms"]["B2"]["allowed"] is True
    assert mistake["arms"]["Ours"]["allowed"] is False


def test_revoked_sibling_and_rounds_do_not_move_the_decision() -> None:
    report = evaluate(build_scenarios())
    sibling = next(
        item for item in report["scenarios"] if item["scenario_id"] == "sibling-revoked-live-grant"
    )
    assert sibling["arms"]["B2"]["allowed"] is True
    assert sibling["arms"]["B2"]["source_status"] == "independent_grant"
    assert report["round_decisions_stable"] is True
    copied = next(
        item for item in report["scenarios"] if item["scenario_id"] == "copied-mark-wrong-grantee"
    )
    assert copied["arms"]["B4"]["allowed"] is False
    assert copied["arms"]["Ours"]["allowed"] is False


def test_education_and_software_gates() -> None:
    edu = education_probe()
    soft = software_probe()
    assert edu["teaching_one_unit_allowed"] is True
    assert edu["teaching_one_unit_committed"] is True
    assert edu["teaching_completing_unit_reason"] == "reconstruction"
    assert edu["stranger_reason"] == "unauthorized"
    assert edu["attribute_one_signal_allowed"] is True
    assert edu["attribute_completing_reason"] == "reconstruction"
    assert edu["attribute_kind"] == "student_attribute"
    assert soft["runbook_reserved"] is True
    assert soft["commit_after_policy_bump"] is False
    assert soft["key_after_bump_reason"] == "unauthorized"
    assert soft["readme_still_allowed"] is True
