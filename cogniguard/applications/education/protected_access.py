"""Trusted education execution through the shared protection gateway."""

import hashlib
import json

from cogniguard.applications.education.profile_consent import ProfileConsentPolicy, filter_profile
from cogniguard.runtime.protection_context import (
    active_protection,
    register_profile_context,
    transport_credentials,
)
from core.access import AccessScope
from core.pipeline import ProtectionPipeline
from protection.common.schemas import StudentProfile


def run_protected_education(
    pipeline: ProtectionPipeline,
    profile: StudentProfile,
    question: dict,
    *,
    access: AccessScope,
    session_token: str | None = None,
    request_id: str | None = None,
    consent_policy: ProfileConsentPolicy | None = None,
) -> dict:
    """Execute trusted education inputs with session and final delivery checks.

    The caller constructs the pipeline, profile and access scope on the server.
    A session token is an anonymous credential, not proof of user identity.
    """
    from cogniguard.runtime.gateway import get_gateway

    def execute(frame):
        subject = frame.state.setdefault("education_subject", profile.student_id)
        if subject != profile.student_id:
            raise PermissionError("Education sessions belong to one authorized subject")
        if consent_policy is None:
            return pipeline.run(profile, question, access=access).to_dict()
        view, requests = filter_profile(profile, consent_policy, frame.state)
        register_profile_context(profile=profile, selected_records=view.profile_records)
        result = pipeline.run(view, question, access=access).to_dict()
        result["profile_consent_requests"] = requests
        return result

    gateway = get_gateway()
    payload = {
        "message": question.get("question", ""),
        "question": question,
        "subject": profile.student_id,
    }
    if consent_policy is None:
        return gateway.run(
            "education", payload, execute, session_token=session_token, request_id=request_id
        )
    if not isinstance(consent_policy, ProfileConsentPolicy):
        raise TypeError("consent_policy must be a trusted ProfileConsentPolicy")
    if active_protection() is not None:
        raise RuntimeError("Consent-enabled education must start at its own gateway boundary")
    transport_token, _ = transport_credentials()
    session = gateway.store.get_or_create(
        session_token if session_token is not None else transport_token
    )
    # The lock covers revision read, replay lookup and delivery as one operation.
    with session.lock():
        state = session.load_state()
        version = state.get("profile_consent", {}).get("revision", 0)
        signature = json.dumps(
            [consent_policy.version, consent_policy.agent, consent_policy.purpose,
             sorted(consent_policy.fields.items())],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        payload["_trusted_consent_revision"] = version
        payload["_trusted_consent_policy"] = hashlib.sha256(signature.encode()).hexdigest()
        return gateway.run(
            "education", payload, execute, session_token=session.token, request_id=request_id
        )
