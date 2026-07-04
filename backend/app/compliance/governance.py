from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


DATA_CATEGORY_VALUES = {
    "education_record",
    "direct_identifier",
    "indirect_identifier",
    "biometric_or_voice",
    "learning_behavior",
    "assessment_result",
    "derived_profile",
    "audit_metadata",
}

RAW_LOCAL_ONLY_FIELDS = {
    "raw_screenshot",
    "wrong_answer_screenshot",
    "voice_recording",
    "audio_recording",
    "handwriting_trace",
    "raw_handwriting_trace",
    "raw_multimodal_data",
    "raw_student_data",
}

DIRECT_IDENTIFIER_FIELDS = {
    "student_name",
    "real_name",
    "full_name",
    "email",
    "phone",
    "address",
    "id_card",
    "student_real_identity",
    "student_legal_name",
}

INDIRECT_IDENTIFIER_FIELDS = {
    "student_hash",
    "student_id",
    "student_alias",
    "school",
    "school_id",
    "class_id",
}

ASSESSMENT_FIELDS = {
    "assessment_result",
    "mastery_score",
    "confidence_score",
    "learning_evidence",
    "profile_update_evidence",
}

AUDIT_FIELDS = {
    "audit_hash",
    "previous_hash",
    "watermark_id",
    "answer_id",
    "resource_id",
    "chunk_id",
    "timestamp",
    "audit_digest",
    "seed_commitment",
}


def build_compliance_state(
    *,
    jurisdiction: str = "US",
    education_stage: str = "K-12",
    student_age: int | float = 14,
    school_managed_account: bool = True,
    parental_consent: str = "not_required",
    school_authorization: str = "granted",
    third_party_model_use_allowed: bool = True,
    data_retention_policy_id: str = "course_limited_hash_audit_v1",
) -> dict[str, Any]:
    is_under_13 = float(student_age) < 13
    ferpa_applicable = jurisdiction == "US" and education_stage in {"K-12", "higher_ed"}
    coppa_applicable = jurisdiction == "US" and is_under_13
    if coppa_applicable and parental_consent == "not_required":
        parental_consent = "pending"
    if not ferpa_applicable and school_authorization == "granted":
        school_authorization = "not_required"
    return {
        "jurisdiction": jurisdiction,
        "education_stage": education_stage,
        "student_age": student_age,
        "is_under_13": is_under_13,
        "school_managed_account": school_managed_account,
        "ferpa_applicable": ferpa_applicable,
        "coppa_applicable": coppa_applicable,
        "parental_consent": parental_consent,
        "school_authorization": school_authorization,
        "third_party_model_use_allowed": third_party_model_use_allowed,
        "data_retention_policy_id": data_retention_policy_id,
    }


def build_data_categories(
    payload: dict[str, Any] | None,
    *,
    payload_kind: str = "context_card",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field_name, value in _flatten_fields(payload or {}):
        rows.append(classify_data_field(field_name, value, payload_kind=payload_kind))
    return rows


def classify_data_field(
    field_name: str,
    value: Any = None,
    *,
    payload_kind: str = "context_card",
) -> dict[str, Any]:
    normalized = _normalize_field_name(field_name)
    category = "derived_profile"
    sensitivity = "medium"
    ferpa_record = payload_kind in {"student_profile", "context_card", "profile_encoding"}
    coppa_personal_info = False
    storage_policy = "course_limited"
    allowed_to_llm = True

    if normalized in DIRECT_IDENTIFIER_FIELDS:
        category = "direct_identifier"
        sensitivity = "restricted"
        ferpa_record = True
        coppa_personal_info = True
        storage_policy = "local_only"
        allowed_to_llm = False
    elif normalized in RAW_LOCAL_ONLY_FIELDS:
        category = "biometric_or_voice" if "voice" in normalized or "audio" in normalized or "handwriting" in normalized else "education_record"
        sensitivity = "restricted"
        ferpa_record = True
        coppa_personal_info = True
        storage_policy = "local_only"
        allowed_to_llm = False
    elif normalized in INDIRECT_IDENTIFIER_FIELDS:
        category = "indirect_identifier"
        sensitivity = "high" if normalized in {"school", "school_id", "student_id"} else "medium"
        ferpa_record = True
        coppa_personal_info = normalized not in {"student_hash"}
        storage_policy = "course_limited"
        allowed_to_llm = normalized in {"student_hash", "student_alias"}
    elif normalized in ASSESSMENT_FIELDS:
        category = "assessment_result"
        sensitivity = "high"
        ferpa_record = True
        coppa_personal_info = False
        storage_policy = "course_limited"
        allowed_to_llm = True
    elif normalized in AUDIT_FIELDS or payload_kind == "audit":
        category = "audit_metadata"
        sensitivity = "low"
        ferpa_record = False
        coppa_personal_info = False
        storage_policy = "audit_hash_only"
        allowed_to_llm = False
    elif "behavior" in normalized or "pause" in normalized or "history" in normalized:
        category = "learning_behavior"
        sensitivity = "high"
        ferpa_record = True
        coppa_personal_info = False
        storage_policy = "course_limited"
        allowed_to_llm = payload_kind == "context_card"
    elif "knowledge" in normalized or "strategy" in normalized or "error" in normalized:
        category = "derived_profile"
        sensitivity = "medium"
        ferpa_record = True
        storage_policy = "course_limited"
        allowed_to_llm = True

    return {
        "field_name": field_name,
        "category": category,
        "sensitivity": sensitivity,
        "ferpa_record": ferpa_record,
        "coppa_personal_info": coppa_personal_info,
        "storage_policy": storage_policy,
        "allowed_to_llm": allowed_to_llm,
    }


def evaluate_compliance_policy(
    request: dict[str, Any],
    compliance_state: dict[str, Any],
    data_categories: list[dict[str, Any]],
) -> dict[str, Any]:
    action = str(request.get("action") or "profile_access")
    actor_role = str(request.get("actor_role") or "system")
    data_scope = str(request.get("data_scope") or "context_card")
    purpose = str(request.get("purpose") or "legitimate_educational_interest")

    blocked_fields: list[str] = []
    allowed_fields: list[str] = []

    for item in data_categories:
        field_name = str(item.get("field_name"))
        if _field_blocked_by_storage(item):
            blocked_fields.append(field_name)
        elif action == "third_party_call" and not item.get("allowed_to_llm", False):
            blocked_fields.append(field_name)
        elif data_scope == "context_card" and item.get("category") == "direct_identifier":
            blocked_fields.append(field_name)
        else:
            allowed_fields.append(field_name)

    legal_context = _legal_context(compliance_state)
    decision = "allow"
    reason = "Compliance policy permits the minimized request."
    retention_action = "none"
    third_party_model_policy = "allowed"

    if compliance_state.get("coppa_applicable") and compliance_state.get("parental_consent") != "granted":
        coppa_blocked = [
            str(item.get("field_name"))
            for item in data_categories
            if item.get("coppa_personal_info") or item.get("storage_policy") == "local_only"
        ]
        blocked_fields = _dedupe([*blocked_fields, *coppa_blocked])
        allowed_fields = [field for field in allowed_fields if field not in blocked_fields]
        if blocked_fields:
            decision = "require_parental_consent"
            reason = "COPPA applies and parental consent is not granted; child personal information cannot be collected or sent."
            third_party_model_policy = "denied"

    if compliance_state.get("ferpa_applicable"):
        authorized = compliance_state.get("school_authorization") in {"granted", "not_required"}
        legitimate = purpose in {"legitimate_educational_interest", "teaching", "audit"}
        if not authorized or not legitimate:
            ferpa_blocked = [
                str(item.get("field_name"))
                for item in data_categories
                if item.get("ferpa_record")
            ]
            blocked_fields = _dedupe([*blocked_fields, *ferpa_blocked])
            allowed_fields = [field for field in allowed_fields if field not in blocked_fields]
            decision = "deny"
            reason = "FERPA applies; education records require authorization and a legitimate educational purpose."
            third_party_model_policy = "denied"

    if actor_role == "teacher" and data_scope in {"raw_profile", "raw_multimodal_profile"}:
        raw_blocked = [
            str(item.get("field_name"))
            for item in data_categories
            if item.get("storage_policy") == "local_only"
            or item.get("category") in {"biometric_or_voice", "direct_identifier"}
        ]
        blocked_fields = _dedupe([*blocked_fields, *raw_blocked])
        allowed_fields = [field for field in allowed_fields if field not in blocked_fields]
        decision = "local_only" if decision == "allow" else decision
        reason = "Raw multimodal profile data remains local-only and is not accessible to teachers."

    if data_scope == "context_card":
        direct_ids = [
            str(item.get("field_name"))
            for item in data_categories
            if item.get("category") == "direct_identifier"
        ]
        if direct_ids:
            blocked_fields = _dedupe([*blocked_fields, *direct_ids])
            allowed_fields = [field for field in allowed_fields if field not in blocked_fields]
            if decision == "allow":
                decision = "minimize"
                reason = "Minimum context card may be sent only after direct identifiers are removed."

    if action == "third_party_call":
        if data_scope in {"raw_profile", "raw_multimodal_profile"}:
            blocked_fields = _dedupe([*blocked_fields, *[str(item.get("field_name")) for item in data_categories]])
            allowed_fields = []
            decision = "deny"
            reason = "Third-party LLM calls cannot receive raw student profiles."
            third_party_model_policy = "denied"
        elif not compliance_state.get("third_party_model_use_allowed", True):
            raw_or_identifier = [
                str(item.get("field_name"))
                for item in data_categories
                if item.get("category") in {"direct_identifier", "biometric_or_voice"}
                or item.get("storage_policy") == "local_only"
            ]
            blocked_fields = _dedupe([*blocked_fields, *raw_or_identifier])
            allowed_fields = [field for field in allowed_fields if field not in blocked_fields]
            third_party_model_policy = "context_card_only"
            decision = "minimize" if allowed_fields else "deny"
            reason = "Third-party model use is disabled for raw data; only a sanitized context card is allowed."
        else:
            third_party_model_policy = "context_card_only" if data_scope == "context_card" else "denied"

    if action == "deletion_request":
        retention_action = "hash_only"
        decision = "local_only" if decision == "allow" else decision
        reason = "Deletion request requires raw fields to be deleted or reduced to hash commitments."
    elif data_scope == "audit_chain" or any(item.get("storage_policy") == "audit_hash_only" for item in data_categories):
        retention_action = "hash_only"
    elif any(item.get("storage_policy") == "session_only" for item in data_categories):
        retention_action = "delete_after_session"

    return {
        "decision": decision,
        "reason": reason,
        "blocked_fields": sorted(_dedupe(blocked_fields)),
        "allowed_fields": sorted(_dedupe(allowed_fields)),
        "retention_action": retention_action,
        "third_party_model_policy": third_party_model_policy,
        "legal_context": legal_context,
    }


def sanitize_context_card(
    context_card: dict[str, Any],
    data_categories: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    categories = data_categories or build_data_categories(context_card, payload_kind="context_card")
    blocked = {
        str(item.get("field_name")).split(".")[0]
        for item in categories
        if item.get("category") == "direct_identifier"
        or item.get("storage_policy") == "local_only"
    }
    return {key: value for key, value in context_card.items() if key not in blocked}


def apply_compliance_deletion(
    payload: dict[str, Any],
    data_categories: list[dict[str, Any]],
) -> dict[str, Any]:
    result = dict(payload)
    for item in data_categories:
        field = str(item.get("field_name")).split(".")[0]
        if field not in result:
            continue
        storage_policy = item.get("storage_policy")
        if storage_policy in {"local_only", "session_only"}:
            result.pop(field, None)
        elif storage_policy == "audit_hash_only":
            result[field] = {
                "storage_policy": "audit_hash_only",
                "hash": hashlib.sha256(str(result[field]).encode("utf-8")).hexdigest(),
            }
    return result


def append_compliance_audit_event(
    log: list[dict[str, Any]],
    *,
    event_type: str,
    actor_role: str,
    data_category: str,
    decision: str,
    legal_context: str,
    timestamp: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous_hash = log[-1]["audit_hash"] if log else "GENESIS"
    event = {
        "event_id": f"cmp_{len(log) + 1:04d}",
        "event_type": event_type,
        "actor_role": actor_role,
        "data_category": data_category,
        "decision": decision,
        "legal_context": legal_context,
        "timestamp": timestamp or _utc_now(),
        "previous_hash": previous_hash,
    }
    if details:
        event["details"] = details
    event["audit_hash"] = _event_hash(event)
    log.append(event)
    return event


def verify_compliance_audit_chain(log: list[dict[str, Any]]) -> bool:
    previous_hash = "GENESIS"
    for event in log:
        if event.get("previous_hash") != previous_hash:
            return False
        if event.get("audit_hash") != _event_hash(event):
            return False
        previous_hash = str(event.get("audit_hash"))
    return True


def _field_blocked_by_storage(item: dict[str, Any]) -> bool:
    return item.get("storage_policy") == "local_only" or item.get("sensitivity") == "restricted"


def _flatten_fields(payload: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    for key, value in payload.items():
        field = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            rows.extend(_flatten_fields(value, field))
        else:
            rows.append((field, value))
    return rows


def _normalize_field_name(field_name: str) -> str:
    return str(field_name).split(".")[-1].strip().lower()


def _legal_context(compliance_state: dict[str, Any]) -> str:
    contexts = []
    if compliance_state.get("ferpa_applicable"):
        contexts.append("FERPA")
    if compliance_state.get("coppa_applicable"):
        contexts.append("COPPA")
    return "+".join(contexts) if contexts else "internal_policy"


def _event_hash(event: dict[str, Any]) -> str:
    canonical = {
        key: value
        for key, value in event.items()
        if key != "audit_hash"
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
