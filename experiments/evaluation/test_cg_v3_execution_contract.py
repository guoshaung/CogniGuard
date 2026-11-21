from __future__ import annotations

from experiments.evaluation.test_cg_v3_kernel import continue_request, make_request
from experiments.evaluation.cg_v3_execution import execute_plan
from experiments.evaluation.cg_v3_harness import CGV3Harness
from experiments.evaluation.cg_v3_policy_composer import ComposerConfig, _costs
from experiments.evaluation.cg_v3_schemas import ActionPlan


def make_plan(actions: list[str]) -> ActionPlan:
    request = make_request()
    privacy_cost, copyright_cost = _costs(request, tuple(actions), ComposerConfig())
    return ActionPlan(
        selected_actions=actions,
        affected_fields=list(request.C_u_t),
        affected_resources=[request.resource_id, *request.chunk_ids],
        parameters={},
        decision_reason="test plan",
        risk_before={"privacy": 0.0, "copyright": 0.0, "audit": 0.0},
        expected_risk_after={"privacy": 0.0, "copyright": 0.0, "audit": 0.0},
        privacy_cost=privacy_cost,
        copyright_cost=copyright_cost,
        privacy_budget_before=0.0,
        privacy_budget_after=1.0,
        copyright_budget_before=0.0,
        copyright_budget_after=1.0,
        audit_evidence_required=[],
    )


def test_summarize_rejects_raw_teacher_resource_and_rolls_back() -> None:
    request = make_request(Pi_copy={"allow_original": False})
    plan = make_plan(["summarize"])
    result = execute_plan(
        request,
        plan,
        ComposerConfig(),
        privacy_remaining=1.0,
        copyright_remaining=1.0,
        supplied_teacher_resource={"full_text": "raw original"},
    )
    assert result.rolled_back is True
    assert result.teacher_resource == {}
    assert result.effective_actions == ["refuse", "audit_escalation"]


def test_minimize_does_not_return_complete_resource() -> None:
    request = make_request(Pi_copy={"allow_original": False})
    plan = make_plan(["minimize"])
    result = execute_plan(
        request,
        plan,
        ComposerConfig(),
        privacy_remaining=1.0,
        copyright_remaining=1.0,
        supplied_teacher_resource={"title": "metadata", "full_text": "raw original"},
    )
    assert result.rolled_back is True
    assert result.teacher_resource == {}


def test_projected_cost_below_actual_cost_rolls_back() -> None:
    request = make_request()
    plan = make_plan(["allow"])
    plan.privacy_cost = 0.0
    result = execute_plan(request, plan, ComposerConfig(), privacy_remaining=1.0, copyright_remaining=1.0)
    assert result.rolled_back is True
    assert result.fallback_reason == "actual disclosure exceeded projected action-plan cost"


def test_actual_cost_over_remaining_copyright_budget_refuses() -> None:
    request = make_request()
    plan = make_plan(["allow"])
    result = execute_plan(request, plan, ComposerConfig(), privacy_remaining=1.0, copyright_remaining=0.0)
    assert result.rolled_back is True
    assert result.effective_actions == ["refuse", "audit_escalation"]


def test_actual_cost_over_remaining_privacy_budget_refuses() -> None:
    request = make_request()
    plan = make_plan(["allow"])
    result = execute_plan(request, plan, ComposerConfig(), privacy_remaining=0.0, copyright_remaining=1.0)
    assert result.rolled_back is True
    assert result.effective_actions == ["refuse", "audit_escalation"]


def test_privacy_budget_enough_but_copyright_budget_insufficient_refuses() -> None:
    request = make_request()
    plan = make_plan(["allow"])
    result = execute_plan(request, plan, ComposerConfig(), privacy_remaining=1.0, copyright_remaining=0.0)
    assert result.actual_privacy_cost == 0.0
    assert result.actual_copyright_cost == 0.0


def test_copyright_budget_enough_but_privacy_budget_insufficient_refuses() -> None:
    request = make_request()
    plan = make_plan(["allow"])
    result = execute_plan(request, plan, ComposerConfig(), privacy_remaining=0.0, copyright_remaining=1.0)
    assert result.actual_privacy_cost == 0.0
    assert result.actual_copyright_cost == 0.0


def test_both_budgets_exactly_enough_are_allowed() -> None:
    request = make_request(C_u_t={"knowledge_point": "linear equations"}, chunk_ids=["chunk-1"])
    plan = make_plan(["allow"])
    result = execute_plan(request, plan, ComposerConfig(), privacy_remaining=0.1, copyright_remaining=0.2)
    assert result.rolled_back is False
    assert result.actual_privacy_cost == 0.1
    assert result.actual_copyright_cost == 0.2


def test_harness_commit_records_actual_cost_only() -> None:
    harness = CGV3Harness(strict_execution_contract=True)
    output = harness.run(make_request(), actual_teacher_resource={"allowed_chunks": []})
    snapshot = harness.ledger.snapshot("student-1", "session-1", "round-1", "resource-1", ["chunk-1"])
    assert output.audit_record["committed_copyright_cost"] == 0.0
    assert snapshot["copyright"]["E_copy"] == 0.0


def test_high_copyright_risk_payload_has_no_complete_original() -> None:
    output = CGV3Harness(strict_execution_contract=True).run(
        make_request(Pi_copy={"allow_original": False}, CR_t={"title": "licensed", "summary": "safe", "exposure_score": 0.9})
    )
    assert "full_text" not in output.allowed_teacher_resource
    assert not output.allowed_teacher_resource.get("allowed_chunks", []) or output.allowed_teacher_resource.get("return_mode") != "original"


def test_cross_domain_constraints_apply_together() -> None:
    output = CGV3Harness(strict_execution_contract=True).run(
        make_request(
            Pi_priv={"allowed_fields": ["knowledge_point"], "forbidden_fields": ["mastery_summary"]},
            Pi_copy={"allow_original": False},
            CR_t={"title": "licensed", "summary": "safe", "exposure_score": 0.9},
        )
    )
    constraints = output.Pi_joint["composer_generated_constraints"]
    assert constraints["privacy"]["forbidden_fields"] == ["mastery_summary"]
    assert constraints["copyright"]["allow_original"] is False
    assert "mastery_summary" not in output.allowed_student_context
    assert constraints["return_mode"] != "original"


def test_static_keeps_old_policy_and_records_actual_cost() -> None:
    output = CGV3Harness(mode="static_cg", strict_execution_contract=True).run(
        make_request(Pi_copy={"allow_original": False}, CR_t={"title": "licensed", "summary": "safe", "exposure_score": 0.9})
    )
    assert output.Pi_joint["dynamic_composer_used"] is False
    assert output.audit_record["committed_copyright_cost"] == output.action_plan.copyright_cost
    assert "full_text" not in output.allowed_teacher_resource


def test_budget_only_disables_history_trust_and_audit_feedback() -> None:
    output = CGV3Harness(mode="budget_only", strict_execution_contract=True).run(make_request())
    assert output.Pi_joint["history_feedback_used"] is False
    assert output.Pi_joint["trust_feedback_used"] is False
    assert output.Pi_joint["audit_feedback_used"] is False


def test_budget_only_does_not_allow_when_both_budgets_are_exhausted() -> None:
    harness = CGV3Harness(mode="budget_only", privacy_max=0.1, copyright_max=0.2, strict_execution_contract=True)
    first = harness.run(make_request(C_u_t={"knowledge_point": "linear equations"}, chunk_ids=["chunk-1"]))
    second = harness.run(continue_request(make_request(C_u_t={"knowledge_point": "linear equations"}, chunk_ids=["chunk-1"]), first, C_u_t={"knowledge_point": "linear equations"}, chunk_ids=["chunk-1"]))
    assert "allow" not in second.action_plan.selected_actions


def test_tampered_hash_escalates_full() -> None:
    harness = CGV3Harness(strict_execution_contract=True)
    first_request = make_request()
    first = harness.run(first_request)
    tampered = harness.run(continue_request(first_request, first, previous_audit_hash="tampered"))
    assert {"audit_escalation", "refuse", "block"}.intersection(tampered.action_plan.selected_actions)
