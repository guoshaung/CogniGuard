from __future__ import annotations

import pytest

from backend.app.agents.agent_orchestrator import TPCSController
from backend.app.agents.base_agent import AgentValidationError
from backend.app.agents.profile_diagnosis_agent import ProfileDiagnosisAgent
from backend.app.compliance import (
    append_compliance_audit_event,
    apply_compliance_deletion,
    build_compliance_state,
    build_data_categories,
    evaluate_compliance_policy,
    sanitize_context_card,
    verify_compliance_audit_chain,
)


def test_under_13_pending_consent_blocks_raw_profile_llm_payload() -> None:
    state = build_compliance_state(student_age=12, parental_consent="pending")
    payload = {
        "raw_screenshot": "base64-image",
        "voice_recording": "audio-bytes",
        "knowledge_point": "fractions",
    }
    categories = build_data_categories(payload, payload_kind="student_profile")

    policy = evaluate_compliance_policy(
        {
            "action": "third_party_call",
            "actor_role": "system",
            "data_scope": "raw_multimodal_profile",
            "purpose": "legitimate_educational_interest",
        },
        state,
        categories,
    )

    assert policy["decision"] in {"require_parental_consent", "deny"}
    assert policy["third_party_model_policy"] == "denied"
    assert "raw_screenshot" in policy["blocked_fields"]

    tpcs = TPCSController(compliance_state=state)
    with pytest.raises(AgentValidationError, match="compliance policy"):
        tpcs.dispatch(
            sender="MM-FOPD",
            receiver=ProfileDiagnosisAgent(),
            message_type="diagnosis_request",
            payload={
                "context_card": {"knowledge_point": "fractions"},
                "profile_encoding": {"raw_screenshot": "base64-image"},
            },
            privacy_level="minimum_context",
            round_id="coppa_pending",
        )


def test_ferpa_teacher_cannot_access_raw_multimodal_profile() -> None:
    state = build_compliance_state(student_age=15, school_authorization="granted")
    categories = build_data_categories(
        {
            "raw_screenshot": "image",
            "voice_recording": "voice",
            "handwriting_trace": "trace",
        },
        payload_kind="student_profile",
    )

    policy = evaluate_compliance_policy(
        {
            "action": "profile_access",
            "actor_role": "teacher",
            "data_scope": "raw_multimodal_profile",
            "purpose": "legitimate_educational_interest",
        },
        state,
        categories,
    )

    assert policy["decision"] == "local_only"
    assert {"raw_screenshot", "voice_recording", "handwriting_trace"} <= set(policy["blocked_fields"])


def test_minimum_context_card_removes_direct_identifiers() -> None:
    context_card = {
        "student_name": "Ada Student",
        "knowledge_point": "linear equations",
        "current_error_type": "sign error",
    }
    categories = build_data_categories(context_card, payload_kind="context_card")

    policy = evaluate_compliance_policy(
        {
            "action": "context_card_send",
            "actor_role": "system",
            "data_scope": "context_card",
            "purpose": "legitimate_educational_interest",
        },
        build_compliance_state(),
        categories,
    )
    sanitized = sanitize_context_card(context_card, categories)

    assert policy["decision"] == "minimize"
    assert "student_name" in policy["blocked_fields"]
    assert "student_name" not in sanitized
    assert sanitized["knowledge_point"] == "linear equations"


def test_third_party_disabled_allows_only_sanitized_context_card() -> None:
    state = build_compliance_state(third_party_model_use_allowed=False)
    context_categories = build_data_categories(
        {"knowledge_point": "quadratic vertex form", "current_error_type": "sign_confusion"},
        payload_kind="context_card",
    )

    context_policy = evaluate_compliance_policy(
        {
            "action": "third_party_call",
            "actor_role": "system",
            "data_scope": "context_card",
            "purpose": "legitimate_educational_interest",
        },
        state,
        context_categories,
    )
    raw_policy = evaluate_compliance_policy(
        {
            "action": "third_party_call",
            "actor_role": "system",
            "data_scope": "raw_multimodal_profile",
            "purpose": "legitimate_educational_interest",
        },
        state,
        build_data_categories({"raw_screenshot": "image"}, payload_kind="student_profile"),
    )

    assert context_policy["decision"] == "minimize"
    assert context_policy["third_party_model_policy"] == "context_card_only"
    assert "knowledge_point" in context_policy["allowed_fields"]
    assert raw_policy["decision"] == "deny"


def test_deletion_request_removes_raw_fields_or_marks_hash_only() -> None:
    payload = {
        "raw_screenshot": "image",
        "knowledge_point": "fractions",
        "audit_hash": "raw-audit-value",
    }
    categories = build_data_categories(payload, payload_kind="student_profile")

    policy = evaluate_compliance_policy(
        {
            "action": "deletion_request",
            "actor_role": "parent",
            "data_scope": "raw_multimodal_profile",
            "purpose": "legitimate_educational_interest",
        },
        build_compliance_state(),
        categories,
    )
    deleted = apply_compliance_deletion(payload, categories)

    assert policy["retention_action"] == "hash_only"
    assert "raw_screenshot" not in deleted
    assert deleted["audit_hash"]["storage_policy"] == "audit_hash_only"
    assert deleted["audit_hash"]["hash"]


def test_compliance_audit_log_forms_hash_chain() -> None:
    log: list[dict] = []
    first = append_compliance_audit_event(
        log,
        event_type="consent_update",
        actor_role="parent",
        data_category="direct_identifier",
        decision="granted",
        legal_context="COPPA",
    )
    second = append_compliance_audit_event(
        log,
        event_type="third_party_call",
        actor_role="system",
        data_category="derived_profile",
        decision="minimize",
        legal_context="FERPA",
    )

    assert second["previous_hash"] == first["audit_hash"]
    assert verify_compliance_audit_chain(log) is True
