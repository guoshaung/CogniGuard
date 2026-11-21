"""Characterization of actual CGController and consent entry points; synthetic data."""
from cogniguard.agents.protected_orchestrator import CGController
from cogniguard.applications.education.profile_consent import ProfileConsentPolicy, revoke_profile_consent
from cogniguard.runtime.protection_context import ProtectionContext, protection_scope
from cogniguard.runtime.sessions import SessionStore


class DiagnosisReceiver:
    agent_id = "profile_diagnosis_agent"
    def __init__(self):
        self.seen = []
    def validate_input(self, payload):
        assert isinstance(payload, dict)
    def generate(self, payload):
        self.seen.append(payload)
        return {"diagnosis_result": {"knowledge_point": "fractions"}}


def test_revoked_consent_is_not_automatically_connected_to_controller(tmp_path):
    store = SessionStore(tmp_path / "session.sqlite")
    session = store.get_or_create(None)
    with session.transaction() as state:
        state["education_subject"] = "synthetic-student"
    policy = ProfileConsentPolicy("v1", "teacher", "learning", {"preference":"ask"})
    revoke_profile_consent(session, policy, "preference", verified_student_id="synthetic-student")
    state = session.load_state()
    assert state["profile_consent"]["revision"] == 1
    receiver = DiagnosisReceiver()
    controller = CGController(student_id="synthetic-student", session_id="synthetic-session")
    with protection_scope(ProtectionContext(session, "synthetic-req", "test", state)):
        controller.dispatch("MM-FOPD", receiver, "diagnosis_request",
                            {"context_card":{"knowledge_point":"fractions"}},
                            "minimum_context", "round")
    # Characterization, not acceptance: no field dependency was supplied to the
    # controller, so this demonstrates that it does not enforce this consent.
    assert len(receiver.seen) == 1
    assert controller.verify_audit_chain()
