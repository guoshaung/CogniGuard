"""Four tutoring agents. Each one builds a request and does not open an asset store."""

from cogniguard.agents.roles.assessment import LearningAssessmentAgent
from cogniguard.agents.roles.base import BaseAgent
from cogniguard.agents.roles.diagnosis import ProfileDiagnosisAgent
from cogniguard.agents.roles.learner import StudentLearningAgent
from cogniguard.agents.roles.materials import CopyrightAwareResourceAgent
from cogniguard.agents.roles.teaching import PedagogicalTeachingAgent

__all__ = [
    "BaseAgent",
    "CopyrightAwareResourceAgent",
    "LearningAssessmentAgent",
    "PedagogicalTeachingAgent",
    "ProfileDiagnosisAgent",
    "StudentLearningAgent",
]
