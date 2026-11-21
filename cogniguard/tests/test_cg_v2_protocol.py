from __future__ import annotations

import pytest

from cogniguard.agents.agent_orchestrator import CGController
from cogniguard.agents.base_agent import AgentValidationError
from cogniguard.agents.profile_diagnosis_agent import ProfileDiagnosisAgent
from cogniguard.protection.cg.protocol import (
    BudgetManager,
    CapabilityRegistry,
    MessageEnvelope,
    PolicyRouter,
    RiskScorer,
    CGDecision,
    degrade_payload,
    sanitize_payload,
)


class FakeAgent:
    agent_id = "profile_diagnosis_agent"

    def validate_input(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            raise AssertionError("payload must be dict")

    def generate(self, payload: dict) -> dict:
        return {"diagnosis_result": {"knowledge_point": "fractions"}}


def test_authorized_adapter_hook_only_runs_after_cg_domain_checks():
    class ProbeAdapter:
        def __init__(self):
            self.calls = []

        def check_message(self, message):
            raise AssertionError("CG must select the trusted post-authorization hook")

        def check_authorized_message(self, message):
            assert message["policy_decision"]["action"] not in {"deny", "defer"}
            assert "compliance_policy" in message
            assert "budget_state" in message
            self.calls.append(message["message_id"])
            return {"allowed": True, "decision": "allow"}

    adapter = ProbeAdapter()
    controller = CGController(guardrail_adapter=adapter)
    controller.dispatch(
        sender="MM-FOPD", receiver=FakeAgent(), message_type="diagnosis_request",
        payload={"context_card": {"knowledge_point": "fractions"}},
        privacy_level="minimum_context", round_id="trusted_round",
    )
    assert len(adapter.calls) == 2
    with pytest.raises(AgentValidationError):
        controller.dispatch(
            sender="unapproved_agent", receiver=FakeAgent(), message_type="diagnosis_request",
            payload={"context_card": {"knowledge_point": "fractions"}},
            privacy_level="minimum_context", round_id="denied_round",
        )
    assert len(adapter.calls) == 2


def test_message_envelope_adds_protocol_identity_and_provenance() -> None:
    message = CGController().build_message(
        sender="MM-FOPD",
        receiver="profile_diagnosis_agent",
        message_type="diagnosis_request",
        payload={"context_card": {"knowledge_point": "fractions"}},
        privacy_level="minimum_context",
        round_id="round_1",
        parent_message_ids=["msg_parent"],
    )
    envelope = MessageEnvelope(**{
        key: value
        for key, value in message.items()
        if key in MessageEnvelope.__dataclass_fields__
    })
    assert envelope.schema_version == "cg/2.0"
    assert envelope.message_id.startswith("msg_")
    assert envelope.trace_id.startswith("trace_")
    assert envelope.parent_message_ids == ["msg_parent"]
    assert "capabilities_required" in message


def test_capability_registry_blocks_wrong_receiver() -> None:
    registry = CapabilityRegistry()
    allowed, _, capabilities = registry.route_allowed(
        "MM-FOPD", "profile_diagnosis_agent", "diagnosis_request"
    )
    assert allowed is True
    assert "diagnosis.request" in capabilities

    allowed, reason, _ = registry.route_allowed(
        "MM-FOPD", "pedagogical_teaching_agent", "diagnosis_request"
    )
    assert allowed is False
    assert "least-privilege handler" in reason


def test_field_risk_reflects_field_receiver_and_purpose() -> None:
    scorer = RiskScorer()
    low, _ = scorer.score(
        {"knowledge_point": "fractions"},
        "profile_diagnosis_agent",
        "legitimate_educational_interest",
    )
    high, breakdown = scorer.score(
        {"student_id": "stu_1", "address": "Beijing"},
        "external_llm",
        "unspecified",
    )
    assert high > low
    assert breakdown["receiver_risk"] == 0.8
    assert breakdown["purpose_factor"] == 1.0


def test_budget_manager_tracks_round_session_and_student() -> None:
    manager = BudgetManager(round_limit=0.2, session_limit=0.3, student_limit=0.4)
    manager.consume("r1", "s1", "stu1", 0.1)
    manager.consume("r2", "s1", "stu1", 0.1)
    allowed, state = manager.check("r3", "s1", "stu1", 0.15)
    assert allowed is False
    assert state["exceeded_scopes"] == ["session"]


def test_policy_router_returns_deny_sanitize_and_degrade() -> None:
    router = PolicyRouter(risk_scorer=RiskScorer(deny_threshold=0.8, degrade_threshold=0.6))

    def message(receiver: str, payload: dict) -> dict:
        return {
            "sender": "MM-FOPD",
            "receiver": receiver,
            "message_type": "diagnosis_request",
            "round_id": "r",
            "purpose": "legitimate_educational_interest",
            "payload": payload,
        }

    decision, policy = router.evaluate(
        message("profile_diagnosis_agent", {"raw_screenshot": "x"}),
        session_id="s",
        student_id="u",
        forbidden_fields={"copyright_text"},
    )
    assert decision is CGDecision.DENY
    assert policy["policy_id"] == "cg.v2.raw_or_identifier_payload"

    decision, policy = router.evaluate(
        message("profile_diagnosis_agent", {"copyright_text": "original"}),
        session_id="s",
        student_id="u",
        forbidden_fields={"copyright_text"},
    )
    assert decision is CGDecision.SANITIZE
    assert sanitize_payload({"copyright_text": "x", "safe": 1}, {"copyright_text"}) == {"safe": 1}
    assert degrade_payload({"secret": "x", "knowledge_point": "fractions"}) == {
        "knowledge_point": "fractions",
        "cg_degraded": True,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"studentId": "stu-1", "fullLearningHistory": "private"},
        {"tool": {"args": {"rawStudentData": "private"}}},
    ],
)
def test_protocol_blocks_camel_case_raw_fields(payload: dict) -> None:
    controller = CGController(session_id="camel", student_id="camel")
    message = controller.build_message(
        sender="MM-FOPD",
        receiver="profile_diagnosis_agent",
        message_type="diagnosis_request",
        payload=payload,
        privacy_level="minimum_context",
        round_id="camel-case-attack",
    )

    with pytest.raises(AgentValidationError, match="raw_or_identifier_payload"):
        controller._authorize_message(message)


def test_controller_uses_envelope_and_verifiable_audit_chain() -> None:
    controller = CGController(session_id="s", student_id="u")
    request, output, response = controller.dispatch(
        sender="MM-FOPD",
        receiver=FakeAgent(),
        message_type="diagnosis_request",
        payload={"context_card": {"knowledge_point": "fractions"}},
        privacy_level="minimum_context",
        round_id="round_audit",
    )
    assert request["schema_version"] == "cg/2.0"
    assert response["parent_message_ids"] == [request["message_id"]]
    assert output["diagnosis_result"]["knowledge_point"] == "fractions"
    assert controller.verify_audit_chain() is True
    assert all(event["previous_hash"] for event in controller.audit_events)
    assert controller.audit_events[-1]["event_hash"] == controller.audit_chain_head


def test_profile_update_gate_defers_low_confidence_to_teacher() -> None:
    controller = CGController(session_id="s", student_id="u")
    result = controller.approve_profile_update_evidence(
        {
            "requires_cg_approval": True,
            "confidence": 0.3,
            "proposed_fields": ["mastery_level"],
        },
        round_id="round_update",
    )
    assert result["action"] == "defer"
    assert result["teacher_review_required"] is True
    assert result["direct_profile_update_performed"] is False
    assert controller.teacher_review_queue


def test_session_budget_can_force_governance_failure() -> None:
    controller = CGController(
        session_id="near_limit",
        student_id="u",
        session_privacy_budget=0.01,
    )
    with pytest.raises(AgentValidationError, match="budget"):
        controller.dispatch(
            sender="MM-FOPD",
            receiver=ProfileDiagnosisAgent(),
            message_type="diagnosis_request",
            payload={
                "context_card": {"knowledge_point": "fractions"},
                "profile_encoding": {"labels": {"knowledge_point": "fractions"}},
            },
            privacy_level="minimum_context",
            round_id="budget_round",
        )


def test_audit_chain_detects_tampering() -> None:
    controller = CGController()
    controller.dispatch(
        sender="MM-FOPD",
        receiver=FakeAgent(),
        message_type="diagnosis_request",
        payload={"context_card": {"knowledge_point": "fractions"}},
        privacy_level="minimum_context",
        round_id="round_tamper",
    )
    assert controller.verify_audit_chain() is True
    controller.audit_events[0]["reason"] = "tampered"
    assert controller.verify_audit_chain() is False
