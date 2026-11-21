"""Opt-in synthetic-only consent demonstration; not an identity provider."""
from __future__ import annotations

from cogniguard.integrations.education import (
    AccessScope,
    ProfileConsentPolicy,
    ProfileRecord,
    ProtectionPipeline,
    StudentProfile,
    resolve_profile_consent,
    revoke_profile_consent,
    run_protected_education,
)
from cogniguard.runtime.protection_context import transport_credentials
from cogniguard.runtime.sessions import InvalidSessionToken

_SUBJECT = "synthetic-consent-demo-student"
_POLICY = ProfileConsentPolicy(
    "synthetic-demo-v1", "teaching-agent", "personalized_tutoring",
    {"mastery": "automatic", "preference": "ask"},
)


def _profile():
    return StudentProfile(_SUBJECT, {}, [
        ProfileRecord("demo-mastery", "mastery", "一元一次方程", 0.4, 1, 0.1),
        ProfileRecord("demo-preference", "preference", "一元一次方程", "visual", 1, 0.1),
    ])


def turn(message):
    if not isinstance(message, str) or not message.strip() or len(message) > 500:
        raise ValueError("请输入不超过 500 字的教学问题")
    pipeline = ProtectionPipeline({"fopd": {"use_enhanced_fopd": False}}, [])
    return run_protected_education(
        pipeline, _profile(),
        {"student_id": _SUBJECT, "question": message, "expected_knowledge": "一元一次方程",
         "need_resource": False},
        access=AccessScope(_SUBJECT), consent_policy=_POLICY,
    )


def decision(payload):
    from cogniguard.runtime.gateway import get_gateway

    token, _ = transport_credentials()
    if not token:
        raise InvalidSessionToken("A demonstration session is required")
    session = get_gateway().store.get_or_create(token)
    action = payload.get("action")
    if action == "revoke":
        revoke_profile_consent(session, _POLICY, "preference", verified_student_id=_SUBJECT)
    elif action in {"approve", "deny"}:
        request_id = payload.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("Missing consent request ID")
        resolve_profile_consent(session, request_id, verified_student_id=_SUBJECT,
                                approve=action == "approve")
    else:
        raise ValueError("Invalid demonstration decision")
    return {"success": True, "simulation": True, "decision": action}
