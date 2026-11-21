from __future__ import annotations

from experiments.evaluation import cg_v3_harness
from experiments.evaluation.cg_v3_harness import CGV3Harness
from experiments.evaluation.cg_v3_pilot import _run_mode, load_episodes
from experiments.evaluation.test_cg_v3_kernel import make_request


def test_no_cg_does_not_call_composer(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("No-CG must not call the dynamic composer")

    monkeypatch.setattr(cg_v3_harness, "compose_candidates", fail)
    output = CGV3Harness(mode="no_cg", strict_execution_contract=True).run(make_request())
    assert output.action_plan.selected_actions == ["allow"]
    assert output.Pi_joint["mechanism_snapshot"]["joint_composer_enabled"] is False


def test_no_cg_budget_is_observed_but_does_not_block() -> None:
    output = CGV3Harness(
        mode="no_cg", privacy_max=0.0, copyright_max=0.0, strict_execution_contract=True
    ).run(make_request())
    assert output.execution_result == "allow"
    assert output.audit_record["budget_violation"] is True
    assert output.audit_record["committed_privacy_cost"] == output.audit_record["privacy_cost"]
    assert output.audit_record["committed_copyright_cost"] == output.audit_record["copyright_cost"]


def test_no_cg_snapshot_has_no_safety_mechanisms() -> None:
    snapshot = CGV3Harness(mode="no_cg").run(make_request()).Pi_joint["mechanism_snapshot"]
    assert all(not value for key, value in snapshot.items() if key != "execution_contract_enabled")
    assert snapshot["execution_contract_enabled"] is True


def test_independent_policy_uses_separate_domain_branches() -> None:
    output = CGV3Harness(mode="independent_policy", strict_execution_contract=True).run(
        make_request(
            Pi_priv={"allowed_fields": ["knowledge_point"]},
            Pi_copy={"allow_original": False},
            CR_t={"title": "licensed", "summary": "safe", "exposure_score": 0.9},
        )
    )
    assert output.Pi_joint["pi_joint"] is None
    assert output.Pi_joint["composer_generated_constraints"] is None
    assert output.action_plan.parameters["privacy_branch"] == ["minimize"]
    assert output.action_plan.parameters["copyright_branch"] == ["controlled_excerpt", "watermark"]
    assert "mastery_summary" not in output.allowed_student_context
    assert output.allowed_teacher_resource["return_mode"] == "controlled_excerpt"


def test_independent_policy_does_not_call_full_composer(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("Independent-Policy must not call the dynamic composer")

    monkeypatch.setattr(cg_v3_harness, "compose_candidates", fail)
    output = CGV3Harness(mode="independent_policy", strict_execution_contract=True).run(make_request())
    assert output.Pi_joint["mechanism_snapshot"]["joint_composer_enabled"] is False
    assert all(item["source"] != "compose_candidates" for item in output.candidate_plans)


def test_independent_policy_fixed_merge_handles_cross_domain_conflict() -> None:
    output = CGV3Harness(mode="independent_policy", strict_execution_contract=True).run(
        make_request(
            Pi_priv={"allowed_fields": ["knowledge_point"]},
            Pi_copy={"allow_original": False},
            CR_t={"title": "licensed", "exposure_score": 0.9},
        )
    )
    assert output.action_plan.parameters["merge_rule"] == "union domain transforms; refuse dominates"
    assert "allow" not in output.action_plan.selected_actions
    assert "mastery_summary" not in output.allowed_student_context
    assert output.allowed_teacher_resource.get("return_mode") != "original"


def test_independent_policy_budget_shortage_refuses_without_joint_scoring() -> None:
    output = CGV3Harness(
        mode="independent_policy", privacy_max=0.0, copyright_max=0.0, strict_execution_contract=True
    ).run(make_request())
    assert "allow" not in output.action_plan.selected_actions
    assert output.Pi_joint["pi_joint"] is None


def test_static_uses_old_engine_and_common_contract() -> None:
    output = CGV3Harness(mode="static_cg", strict_execution_contract=True).run(make_request())
    assert any(item["source"] == "CGPolicyEngine" for item in output.candidate_plans)
    assert output.Pi_joint["dynamic_composer_used"] is False
    assert output.Pi_joint["mechanism_snapshot"]["execution_contract_enabled"] is True


def test_budget_only_disables_state_and_audit_feedback_snapshot() -> None:
    output = CGV3Harness(mode="budget_only", strict_execution_contract=True).run(make_request())
    snapshot = output.Pi_joint["mechanism_snapshot"]
    assert snapshot["privacy_budget_enabled"] is True
    assert snapshot["copyright_budget_enabled"] is True
    assert not snapshot["history_enabled"]
    assert not snapshot["trust_enabled"]
    assert not snapshot["audit_feedback_enabled"]
    assert not snapshot["dynamic_action_scoring_enabled"]


def test_full_snapshot_proves_dynamic_composer_and_feedback_are_enabled() -> None:
    output = CGV3Harness(mode="full_cg_v3", strict_execution_contract=True).run(make_request())
    snapshot = output.Pi_joint["mechanism_snapshot"]
    assert all(snapshot.values())
    assert output.Pi_joint["dynamic_composer_used"] is True
    assert len(output.candidate_plans) > 1


def test_all_modes_commit_actual_cost_and_keep_plan_execution_aligned() -> None:
    for mode in ("no_cg", "independent_policy", "static_cg", "budget_only", "full_cg_v3"):
        output = CGV3Harness(mode=mode, strict_execution_contract=True).run(make_request())
        assert output.audit_record["output_violation"] is False
        assert output.audit_record["rolled_back"] is False
        assert output.audit_record["committed_privacy_cost"] == output.audit_record["privacy_cost"]
        assert output.audit_record["committed_copyright_cost"] == output.audit_record["copyright_cost"]


def test_five_modes_use_the_same_frozen_episode_request_hashes() -> None:
    episodes = load_episodes()
    hashes = []
    for mode in ("no_cg", "independent_policy", "static_cg", "budget_only", "full_cg_v3"):
        result = _run_mode(mode, episodes[:1], strict_execution_contract=True)
        hashes.append([item["request_hash"] for item in result[0]["rounds"]])
    assert all(item == hashes[0] for item in hashes[1:])

