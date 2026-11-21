"""Education reference workflow and schemas.

This integration requires the ``runtime`` extra. The default generator uses offline
rules; governance and watermark hooks must be supplied by trusted application code.
Create one ProtectionPipeline per authorized student session to preserve budgets.
Use run_protected_education for mandatory server sessions and final delivery checks.
"""

from cogniguard.applications.education.protected_access import run_protected_education
from cogniguard.integrations.profile_consent import (
    ProfileConsentPolicy,
    resolve_profile_consent,
    revoke_profile_consent,
)
from core.access import AccessScope
from core.domain import ProtectionResult
from core.pipeline import ProtectionPipeline
from core.teaching import TeachingInput
from protection.common.schemas import (
    ProfileRecord,
    ResourcePolicy,
    StudentProfile,
    TeacherResource,
)

__all__ = [
    "AccessScope",
    "ProfileRecord",
    "ProtectionPipeline",
    "ProtectionResult",
    "ResourcePolicy",
    "StudentProfile",
    "TeacherResource",
    "TeachingInput",
    "run_protected_education",
    "ProfileConsentPolicy",
    "resolve_profile_consent",
    "revoke_profile_consent",
]
