from __future__ import annotations

import json

import pytest

from experiments.evaluation.cg_v3_budget import DualBudgetLedger
from experiments.evaluation.cg_v3_harness import CGV3Harness
from experiments.evaluation.cg_v3_replay import replay_jsonl
from experiments.evaluation.cg_v3_schemas import CGInput


def make_request(**overrides: object) -> CGInput:
    values = {
        "q_t": "explain linear equations",
        "student_id": "student-1",
        "session_id": "session-1",
        "round_id": "round-1",
        "resource_id": "resource-1",
        "chunk_ids": ["chunk-1"],
        "C_u_t": {"knowledge_point": "linear equations", "mastery_summary": "partial"},
        "Pi_priv": {"allowed_fields": ["knowledge_point", "mastery_summary"]},
        "CR_t": {"title": "Linear equations", "exposure_score": 0.1},
        "Pi_copy": {"allow_original": True},
        "provenance_evidence": {"confidence": 1.0},
        "capability_context": {},
        "previous_state": {},
        "previous_audit_hash": "GENESIS",
    }
    values.update(overrides)
    return CGInput.from_mapping(values)


def continue_request(previous: CGInput, output: object, **overrides: object) -> CGInput:
    result = output.to_dict()
    values = previous.to_dict()
    values.update({
        "round_id": "round-2",
        "previous_state": result["updated_state"],
        "previous_audit_hash": result["audit_hash"],
    })
    values.update(overrides)
    return CGInput.from_mapping(values)


def test_dual_budget_isolated_by_domain() -> None:
    harness = CGV3Harness(privacy_max=2.0, copyright_max=2.0)
    output = harness.run(
        make_request(),
        actual_student_context={"knowledge_point": "linear equations"},
        actual_teacher_resource={"allowed_chunks": []},
    )
    snapshot = harness.ledger.snapshot("student-1", "session-1", "round-1", "resource-1", ["chunk-1"])
    assert output.action_plan.privacy_cost > 0
    assert output.action_plan.copyright_cost == 0
    assert snapshot["privacy"]["E_priv"] > 0
    assert snapshot["copyright"]["E_copy"] == 0


def test_dual_budget_accumulates_across_rounds() -> None:
    harness = CGV3Harness(privacy_max=0.15, copyright_max=2.0)
    first_request = make_request(C_u_t={"knowledge_point": "linear equations"})
    first = harness.run(first_request, actual_student_context={"knowledge_point": "linear equations"}, actual_teacher_resource={"allowed_chunks": []})
    second = harness.run(
        continue_request(first_request, first, C_u_t={"knowledge_point": "linear equations"}),
        actual_student_context={"knowledge_point": "linear equations"},
        actual_teacher_resource={"allowed_chunks": []},
    )
    assert first.updated_state.E_priv < second.updated_state.E_priv
    assert second.action_plan.privacy_budget_after < first.action_plan.privacy_budget_after
    assert any(item.get("feasible") is False for item in second.candidate_plans)


def test_cross_domain_conflict_uses_composed_action() -> None:
    harness = CGV3Harness(privacy_max=2.0, copyright_max=2.0)
    output = harness.run(make_request(Pi_copy={"allow_original": False}, CR_t={"title": "licensed", "exposure_score": 0.7}))
    assert "allow" not in output.action_plan.selected_actions
    assert {"controlled_excerpt", "watermark", "summarize", "degrade"}.intersection(output.action_plan.selected_actions)


def test_privacy_restriction_is_not_ignored() -> None:
    harness = CGV3Harness(privacy_max=2.0, copyright_max=2.0)
    output = harness.run(make_request(Pi_priv={"allowed_fields": ["knowledge_point"]}))
    assert "mastery_summary" not in output.allowed_student_context
    assert "allow" not in output.action_plan.selected_actions


def test_state_changes_candidate_scores_and_action() -> None:
    harness = CGV3Harness(privacy_max=2.0, copyright_max=2.0)
    request = make_request()
    first = harness.run(request)
    second_request = continue_request(
        request,
        first,
        provenance_evidence={"confidence": 0.2},
        previous_state={**first.updated_state.to_dict(), "trust_score": 0.2, "semantic_repetition": 5},
    )
    second = harness.run(second_request)
    assert first.candidate_plans != second.candidate_plans or first.action_plan.selected_actions != second.action_plan.selected_actions


def test_tampered_audit_hash_changes_next_action() -> None:
    harness = CGV3Harness(privacy_max=2.0, copyright_max=2.0)
    first_request = make_request()
    first = harness.run(first_request)
    tampered = harness.run(continue_request(first_request, first, previous_audit_hash="tampered-hash"))
    assert tampered.updated_state.audit_risk > first.updated_state.audit_risk
    assert {"audit_escalation", "refuse", "block"}.intersection(tampered.action_plan.selected_actions)
    assert tampered.audit_record["audit_valid"] is False


@pytest.mark.parametrize("mode", ["static_cg", "budget_only", "full_cg_v3"])
def test_all_controller_modes_run(mode: str) -> None:
    output = CGV3Harness(mode=mode).run(make_request())
    assert output.execution_result in {"allow", "degrade", "refuse", "block"}
    assert output.audit_hash


def test_capability_receiver_and_purpose_are_blocked() -> None:
    wrong_receiver = CGV3Harness().run(make_request(capability_context={"receiver": "pedagogical_teaching_agent"}))
    forged_purpose = CGV3Harness().run(make_request(capability_context={"purpose": "forged_admin_purpose"}))
    assert wrong_receiver.execution_result == "block"
    assert forged_purpose.execution_result == "block"


def test_candidate_but_unexecuted_data_is_not_consumed() -> None:
    harness = CGV3Harness()
    output = harness.run(make_request(), actual_student_context={}, actual_teacher_resource={})
    assert output.action_plan.privacy_cost == 0
    assert output.action_plan.copyright_cost == 0
    snapshot = harness.ledger.snapshot("student-1", "session-1", "round-1", "resource-1", ["chunk-1"])
    assert snapshot["privacy"]["E_priv"] == 0
    assert snapshot["copyright"]["E_copy"] == 0


def test_replay_is_deterministic_and_writes_jsonl(tmp_path) -> None:
    input_path = tmp_path / "episodes.jsonl"
    output_path = tmp_path / "results.jsonl"
    input_path.write_text(json.dumps(make_request().to_dict(), ensure_ascii=False) + "\n", encoding="utf-8")
    first = replay_jsonl(input_path, output_path)
    first_content = output_path.read_text(encoding="utf-8")
    second = replay_jsonl(input_path, output_path)
    assert first["episodes"] == second["episodes"] == 1
    assert first_content == output_path.read_text(encoding="utf-8")
    parsed = json.loads(first_content)
    assert parsed["controller_mode"] == "full_cg_v3"
    assert parsed["input_hash"]


def test_ledger_reset_scopes() -> None:
    ledger = DualBudgetLedger(privacy_max=2.0, copyright_max=2.0)
    ledger.commit_privacy("student-1", "session-1", "round-1", 0.2)
    ledger.commit_copyright("resource-1", ["chunk-1"], "session-1", 0.3)
    ledger.reset_resource("resource-1")
    ledger.reset_student("student-1")
    snapshot = ledger.snapshot("student-1", "session-1", "round-1", "resource-1", ["chunk-1"])
    assert snapshot["privacy"]["E_priv"] == 0
    assert snapshot["copyright"]["E_copy"] == 0
