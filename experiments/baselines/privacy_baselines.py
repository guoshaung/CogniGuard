from __future__ import annotations

import hashlib
import random
import re
from typing import Any

from backend.app.compliance import build_compliance_state, build_data_categories, evaluate_compliance_policy
from protection.common.schemas import StudentProfile, Task
from protection.student_profile.src.fopd.context_card import build_context_card
from protection.student_profile.src.fopd.profile_selector import ProfileSelector, ScoredProfileRecord


DIRECT_IDENTIFIER_KEYS = {
    "student_name",
    "real_name",
    "full_name",
    "email",
    "phone",
    "address",
    "id_card",
}

INDIRECT_IDENTIFIER_KEYS = {
    "school",
    "school_id",
    "class_id",
    "family_note",
    "student_id",
}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s-]{7,}\d)")


def build_privacy_baseline_rows(
    *,
    profile: StudentProfile,
    task: Task,
    config: dict[str, Any],
    metric_row_builder: Any,
) -> list[dict[str, Any]]:
    return [
        _pii_redaction_row(profile, task, metric_row_builder),
        _presidio_style_masking_row(profile, task, metric_row_builder),
        _rbac_only_row(profile, task, metric_row_builder),
        _abac_purpose_only_row(profile, task, metric_row_builder),
        _dp_noisy_topk_row(profile, task, config, metric_row_builder),
        _local_only_no_third_party_row(profile, task, metric_row_builder),
    ]


def _all_selected(profile: StudentProfile) -> list[ScoredProfileRecord]:
    return [
        ScoredProfileRecord(record=record, score=1.0, components={"baseline": 1.0})
        for record in profile.profile_records
    ]


def _full_profile_card(profile: StudentProfile, *, include_direct_identifiers: bool = True) -> str:
    lines: list[str] = []
    if include_direct_identifiers:
        lines.extend(
            [
                f"student_id: {profile.student_id}",
                f"student_name: student-{profile.student_id}",
                f"email: {profile.student_id}@school.example",
            ]
        )
    for key, value in profile.local_only_fields.items():
        lines.append(f"{key}: {value}")
    for record in profile.profile_records:
        lines.append(f"{record.type}/{record.knowledge}: {record.value}")
    return "\n".join(lines)


def _redact_direct_identifiers(text: str) -> tuple[str, int]:
    redacted = EMAIL_RE.sub("[EMAIL]", text)
    redacted = PHONE_RE.sub("[PHONE]", redacted)
    count = int(redacted != text)
    for key in DIRECT_IDENTIFIER_KEYS:
        redacted, replaced = re.subn(
            rf"({re.escape(key)}\s*:\s*)[^\n]+",
            rf"\1[DIRECT_IDENTIFIER]",
            redacted,
            flags=re.IGNORECASE,
        )
        count += replaced
    return redacted, count


def _mask_education_identifiers(profile: StudentProfile, text: str) -> tuple[str, int]:
    masked = text
    count = 0
    for key, value in profile.local_only_fields.items():
        value_text = str(value)
        if value_text and value_text in masked:
            masked = masked.replace(value_text, f"[{key.upper()}_MASKED]")
            count += 1
    masked, direct_count = _redact_direct_identifiers(masked)
    count += direct_count
    for key in INDIRECT_IDENTIFIER_KEYS:
        masked, replaced = re.subn(
            rf"({re.escape(key)}\s*:\s*)[^\n]+",
            rf"\1[INDIRECT_IDENTIFIER_MASKED]",
            masked,
            flags=re.IGNORECASE,
        )
        count += replaced
    return masked, count


def _privacy_flags(
    profile: StudentProfile,
    card: str,
    *,
    raw_profile_sent: bool,
    unauthorized_access_blocked: bool = False,
    third_party_raw_profile_sent: bool = False,
) -> dict[str, Any]:
    local_values = [str(value) for value in profile.local_only_fields.values() if str(value)]
    direct_flag = int(
        bool(EMAIL_RE.search(card))
        or f"student-{profile.student_id}" in card
        or f"{profile.student_id}@school.example" in card
    )
    indirect_flag = int(any(value in card for value in local_values) or f"student_id: {profile.student_id}" in card)
    return {
        "PIILeakFlag": direct_flag,
        "IndirectLeakFlag": indirect_flag,
        "RawProfileSentFlag": int(raw_profile_sent),
        "UnauthorizedAccessBlocked": int(unauthorized_access_blocked),
        "ThirdPartyRawProfileRate": int(third_party_raw_profile_sent),
    }


def _pii_redaction_row(profile: StudentProfile, task: Task, metric_row_builder: Any) -> dict[str, Any]:
    card, redaction_count = _redact_direct_identifiers(_full_profile_card(profile))
    return metric_row_builder(
        "PII-Redaction",
        profile,
        task,
        card,
        _all_selected(profile),
        BaselineFamily="external_privacy",
        RedactionCount=redaction_count,
        ComplianceBlockedCount=0,
        ComplianceDecision="not_applied",
        **_privacy_flags(profile, card, raw_profile_sent=True, third_party_raw_profile_sent=True),
    )


def _presidio_style_masking_row(profile: StudentProfile, task: Task, metric_row_builder: Any) -> dict[str, Any]:
    card, redaction_count = _mask_education_identifiers(profile, _full_profile_card(profile))
    return metric_row_builder(
        "PresidioStyle-PII-Masking",
        profile,
        task,
        card,
        _all_selected(profile),
        BaselineFamily="external_privacy",
        RedactionCount=redaction_count,
        ComplianceBlockedCount=0,
        ComplianceDecision="not_applied",
        **_privacy_flags(profile, card, raw_profile_sent=True, third_party_raw_profile_sent=True),
    )


def _rbac_only_row(profile: StudentProfile, task: Task, metric_row_builder: Any) -> dict[str, Any]:
    actor_role = "teacher"
    allowed = actor_role in {"teacher", "admin"}
    card = _full_profile_card(profile) if allowed else ""
    selected = _all_selected(profile) if allowed else []
    return metric_row_builder(
        "RBAC-only",
        profile,
        task,
        card,
        selected,
        BaselineFamily="external_privacy",
        RedactionCount=0,
        ComplianceBlockedCount=0,
        ComplianceDecision="allow" if allowed else "deny",
        **_privacy_flags(
            profile,
            card,
            raw_profile_sent=allowed,
            unauthorized_access_blocked=not allowed,
            third_party_raw_profile_sent=allowed,
        ),
    )


def _abac_purpose_only_row(profile: StudentProfile, task: Task, metric_row_builder: Any) -> dict[str, Any]:
    card = _full_profile_card(profile)
    state = build_compliance_state(
        jurisdiction="US",
        education_stage="K-12",
        student_age=14,
        school_managed_account=True,
        parental_consent="not_required",
        school_authorization="granted",
        third_party_model_use_allowed=True,
    )
    payload = {
        "student_id": profile.student_id,
        **profile.local_only_fields,
        "profile_records": [record.text() for record in profile.profile_records],
    }
    categories = build_data_categories(payload, payload_kind="student_profile")
    policy = evaluate_compliance_policy(
        {
            "action": "profile_access",
            "actor_role": "teacher",
            "data_scope": "raw_profile",
            "purpose": "teaching",
        },
        state,
        categories,
    )
    masked_card, redaction_count = _mask_education_identifiers(profile, card)
    visible_card = masked_card if policy["decision"] in {"allow", "local_only", "minimize"} else ""
    return metric_row_builder(
        "ABAC-PurposeOnly",
        profile,
        task,
        visible_card,
        _all_selected(profile),
        BaselineFamily="external_privacy",
        RedactionCount=redaction_count,
        ComplianceBlockedCount=len(policy["blocked_fields"]),
        ComplianceDecision=policy["decision"],
        BlockedFields=policy["blocked_fields"],
        AllowedFields=policy["allowed_fields"],
        **_privacy_flags(profile, visible_card, raw_profile_sent=True, third_party_raw_profile_sent=True),
    )


def _dp_noisy_topk_row(
    profile: StudentProfile,
    task: Task,
    config: dict[str, Any],
    metric_row_builder: Any,
) -> dict[str, Any]:
    selector = ProfileSelector(config)
    scored = selector.score_records(profile, task)
    seed = int(hashlib.sha256(f"{profile.student_id}:{task.request_id}".encode("utf-8")).hexdigest()[:12], 16)
    rng = random.Random(seed)
    noisy: list[ScoredProfileRecord] = []
    for item in scored:
        noise = rng.uniform(-0.08, 0.08)
        noisy.append(
            ScoredProfileRecord(
                record=item.record,
                score=item.score + noise,
                components={**item.components, "dp_noise": noise, "baseline": 1.0},
            )
        )
    selected = [
        item
        for item in sorted(noisy, key=lambda entry: entry.score, reverse=True)
        if item.record.sensitivity <= selector.sensitivity_threshold
    ][: selector.top_k]
    card, redaction_log = build_context_card(profile, task, selected)
    return metric_row_builder(
        "DP-NoisyTopK",
        profile,
        task,
        card,
        selected,
        BaselineFamily="external_privacy",
        RedactionCount=len(redaction_log),
        ComplianceBlockedCount=0,
        ComplianceDecision="not_applied",
        **_privacy_flags(profile, card, raw_profile_sent=False, third_party_raw_profile_sent=False),
    )


def _local_only_no_third_party_row(profile: StudentProfile, task: Task, metric_row_builder: Any) -> dict[str, Any]:
    card = "\n".join(
        [
            f"knowledge: {task.knowledge}",
            f"difficulty: {task.difficulty}",
            "student_profile_policy: local_only_not_sent_to_third_party",
        ]
    )
    return metric_row_builder(
        "LocalOnly-NoThirdParty",
        profile,
        task,
        card,
        [],
        BaselineFamily="external_privacy",
        RedactionCount=0,
        ComplianceBlockedCount=len(profile.profile_records) + len(profile.local_only_fields),
        ComplianceDecision="local_only",
        ThirdPartyModelPolicy="denied",
        **_privacy_flags(profile, card, raw_profile_sent=False, third_party_raw_profile_sent=False),
    )
