"""Actual education session lock and consent revision race, synthetic data."""
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from cogniguard.integrations.education import (
    AccessScope, ProfileConsentPolicy, ProfileRecord, StudentProfile,
    resolve_profile_consent, revoke_profile_consent, run_protected_education,
)
from cogniguard.protection.text_provenance import TextProvenanceService
from cogniguard.runtime.gateway import ProtectionGateway
from cogniguard.runtime.sessions import RequestConflict, SessionStore


def test_revoke_serializes_after_inflight_and_prevents_old_replay(tmp_path, monkeypatch):
    gateway = ProtectionGateway(store=SessionStore(tmp_path / "session.sqlite"),
        provenance=TextProvenanceService(b"synthetic-test-key" * 4, required=True))
    monkeypatch.setattr("cogniguard.runtime.gateway.get_gateway", lambda: gateway)
    entered, proceed, revoke_started, revoke_done = (threading.Event() for _ in range(4))
    profile = StudentProfile("synthetic-student", {}, [
        ProfileRecord("p", "preference", "fractions", "visual", 1, 0.1),
    ])
    policy = ProfileConsentPolicy("v1", "teacher", "learning", {"preference":"ask"})
    observed = []
    class Pipeline:
        def run(self, profile, question, *, access):
            observed.append([r.type for r in profile.profile_records])
            if question.get("hold"):
                entered.set()
                if not proceed.wait(5):
                    raise TimeoutError("test coordination timeout")
            return SimpleNamespace(to_dict=lambda: {"answer":"synthetic teaching answer"})
    pipeline = Pipeline()
    def call(token=None, request_id=None, hold=False):
        return run_protected_education(pipeline, profile, {"question":"Explain fractions", "hold":hold},
            access=AccessScope("synthetic-student"), consent_policy=policy,
            session_token=token, request_id=request_id)
    first = call(request_id="request-initial")
    session = gateway.store.get_or_create(first["session_token"])
    resolve_profile_consent(session, first["profile_consent_requests"][0]["request_id"],
                            verified_student_id="synthetic-student", approve=True)
    def revoke():
        revoke_started.set()
        revoke_profile_consent(session, policy, "preference", verified_student_id="synthetic-student")
        revoke_done.set()
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending = executor.submit(call, first["session_token"], "request-inflight", True)
        assert entered.wait(5)
        revoker = executor.submit(revoke)
        assert revoke_started.wait(5)
        assert not revoke_done.wait(0.1)
        proceed.set()
        assert pending.result(timeout=5)["output_validation"]["allowed"]
        revoker.result(timeout=5)
    with pytest.raises(RequestConflict):
        call(first["session_token"], "request-inflight", True)
    call(first["session_token"], "request-after")
    assert observed[-2:] == [["preference"], []]
