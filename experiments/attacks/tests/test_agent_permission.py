from __future__ import annotations

import pytest

from backend.app.agents.agent_orchestrator import TPCSController
from backend.app.agents.base_agent import AgentValidationError
from backend.app.agents.profile_diagnosis_agent import ProfileDiagnosisAgent


def test_teaching_agent_cannot_request_full_profile_from_profile_agent() -> None:
    tpcs = TPCSController()
    profile_agent = ProfileDiagnosisAgent()

    with pytest.raises(AgentValidationError, match="route denied"):
        tpcs.dispatch(
            sender="pedagogical_teaching_agent",
            receiver=profile_agent,
            message_type="full_profile_request",
            payload={
                "context_card": {
                    "knowledge_point": "quadratic vertex form",
                    "learner_state_summary": "partial understanding",
                }
            },
            privacy_level="forbidden_profile_access",
            round_id="attack_agent_permission",
        )


def test_forbidden_full_student_profile_payload_is_blocked_even_on_allowed_route() -> None:
    tpcs = TPCSController()
    profile_agent = ProfileDiagnosisAgent()

    with pytest.raises(AgentValidationError, match="forbidden payload"):
        tpcs.dispatch(
            sender="MM-FOPD",
            receiver=profile_agent,
            message_type="diagnosis_request",
            payload={
                "context_card": {"knowledge_point": "linear equation solving"},
                "full_student_profile": {"all_history": "should never pass"},
            },
            privacy_level="minimum_context",
            round_id="attack_forbidden_payload",
        )
