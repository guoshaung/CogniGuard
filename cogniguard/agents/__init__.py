"""Protected tutoring agent layer."""

from cogniguard.agents.protected_orchestrator import AgentOrchestrator, CGController
from cogniguard.agents.roles.materials import CopyrightAwareResourceAgent
from cogniguard.agents.roles.assessment import LearningAssessmentAgent
from cogniguard.providers.mimo import (
    MiMoChatClient,
    build_default_llm_client,
    build_student_llm_client,
)
from cogniguard.agents.roles.teaching import PedagogicalTeachingAgent
from cogniguard.agents.roles.diagnosis import ProfileDiagnosisAgent
from cogniguard.agents.roles.learner import StudentLearningAgent

__all__ = [
    "AgentOrchestrator",
    "CopyrightAwareResourceAgent",
    "LearningAssessmentAgent",
    "MiMoChatClient",
    "PedagogicalTeachingAgent",
    "ProfileDiagnosisAgent",
    "StudentLearningAgent",
    "CGController",
    "build_default_llm_client",
    "build_student_llm_client",
]
