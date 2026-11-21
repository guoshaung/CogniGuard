"""Explicit student consent is scoped and applied before the teaching pipeline."""
from types import SimpleNamespace

import pytest

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
from cogniguard.protection.text_provenance import TextProvenanceService
from cogniguard.runtime.gateway import ProtectionGateway
from cogniguard.runtime.sessions import RequestConflict, SessionStore


@pytest.fixture
def setup(tmp_path, monkeypatch):
    gateway = ProtectionGateway(
        store=SessionStore(tmp_path / "sessions.sqlite"),
        provenance=TextProvenanceService(b"test-only-consent-key" * 4, required=True),
    )
    monkeypatch.setattr("cogniguard.runtime.gateway.get_gateway", lambda: gateway)
    seen = []

    class Pipeline:
        def run(self, profile, question, *, access):
            seen.append([record.type for record in profile.profile_records])
            return SimpleNamespace(to_dict=lambda: {"answer": "先理解这个问题。"})

    profile = StudentProfile("student-1", {}, [
        ProfileRecord("m", "mastery", "math", 0.4, 1, 0.1),
        ProfileRecord("p", "preference", "math", "SYNTHETIC_PRIVATE_PREFERENCE", 1, 0.1),
    ])
    policy = ProfileConsentPolicy("v1", "teacher-a", "personalized_tutoring",
                                  {"mastery": "automatic", "preference": "ask"})
    return gateway, Pipeline(), profile, policy, seen


def call(pipeline, profile, policy, *, token=None, request_id=None):
    return run_protected_education(
        pipeline, profile, {"question": "如何理解方程？", "student_id": profile.student_id},
        access=AccessScope(profile.student_id), session_token=token, request_id=request_id,
        consent_policy=policy,
    )


def test_pending_approval_revoke_and_cached_replay(setup):
    gateway, pipeline, profile, policy, seen = setup
    first = call(pipeline, profile, policy, request_id="first")
    token = first["session_token"]
    pending = first["profile_consent_requests"]
    assert seen[-1] == ["mastery"]
    assert len(pending) == 1 and pending[0]["field"] == "preference"
    assert "SYNTHETIC_PRIVATE_PREFERENCE" not in str(first)
    session = gateway.store.get_or_create(token)
    with pytest.raises(PermissionError):
        resolve_profile_consent(session, pending[0]["request_id"], verified_student_id="other", approve=True)
    resolve_profile_consent(session, pending[0]["request_id"], verified_student_id="student-1", approve=True)
    with pytest.raises(RequestConflict):
        call(pipeline, profile, policy, token=token, request_id="first")
    second = call(pipeline, profile, policy, token=token, request_id="second")
    assert seen[-1] == ["mastery", "preference"]
    assert second["profile_consent_requests"] == []
    revoke_profile_consent(session, policy, "preference", verified_student_id="student-1")
    with pytest.raises(RequestConflict):
        call(pipeline, profile, policy, token=token, request_id="second")
    call(pipeline, profile, policy, token=token, request_id="third")
    assert seen[-1] == ["mastery"]


def test_consent_is_scoped_to_agent_and_purpose(setup):
    gateway, pipeline, profile, policy, seen = setup
    first = call(pipeline, profile, policy)
    session = gateway.store.get_or_create(first["session_token"])
    resolve_profile_consent(session, first["profile_consent_requests"][0]["request_id"],
                            verified_student_id="student-1", approve=True)
    other = ProfileConsentPolicy("v1", "teacher-b", "personalized_tutoring",
                                 {"mastery": "automatic", "preference": "ask"})
    result = call(pipeline, profile, other, token=first["session_token"])
    assert seen[-1] == ["mastery"]
    assert result["profile_consent_requests"][0]["agent"] == "teacher-b"


def test_actual_graph_receives_only_approved_profile_records(setup):
    gateway, _, _, policy, _ = setup
    captured = []

    def generator(data):
        captured.append(data.context_card)
        return "先理解问题。"

    pipeline = ProtectionPipeline({"fopd": {"use_enhanced_fopd": False}}, [], generator=generator)
    profile = StudentProfile("student-1", {}, [
        ProfileRecord("m", "mastery", "一元一次方程", 0.4, 1, 0.1),
        ProfileRecord("p", "preference", "一元一次方程", "visual", 1, 0.1),
    ])
    question = {"request_id": "q", "student_id": "student-1", "question": "解方程",
                "expected_knowledge": "一元一次方程", "need_resource": False}
    first = run_protected_education(pipeline, profile, question, access=AccessScope("student-1"),
                                    consent_policy=policy, request_id="graph-first")
    assert "visual_support" not in captured[-1]
    session = gateway.store.get_or_create(first["session_token"])
    resolve_profile_consent(session, first["profile_consent_requests"][0]["request_id"],
                            verified_student_id="student-1", approve=True)
    run_protected_education(pipeline, profile, question, access=AccessScope("student-1"),
                            consent_policy=policy, session_token=first["session_token"],
                            request_id="graph-second")
    assert "visual_support" in captured[-1]


def test_revoke_invalidates_pending_decision(setup):
    gateway, pipeline, profile, policy, seen = setup
    first = call(pipeline, profile, policy)
    session = gateway.store.get_or_create(first["session_token"])
    request_id = first["profile_consent_requests"][0]["request_id"]
    revoke_profile_consent(session, policy, "preference", verified_student_id="student-1")
    with pytest.raises(ValueError):
        resolve_profile_consent(session, request_id, verified_student_id="student-1", approve=True)
    result = call(pipeline, profile, policy, token=first["session_token"])
    assert seen[-1] == ["mastery"]
    assert result["profile_consent_requests"] == []


def test_pending_value_is_not_released_through_a_generated_answer(setup):
    _, _, profile, policy, _ = setup

    class GuessedOutput:
        def run(self, profile, question, *, access):
            return SimpleNamespace(to_dict=lambda: {"answer": "SYNTHETIC_PRIVATE_PREFERENCE"})

    result = call(GuessedOutput(), profile, policy)
    assert "SYNTHETIC_PRIVATE_PREFERENCE" not in str(result)
    assert not result["output_validation"]["allowed"]
