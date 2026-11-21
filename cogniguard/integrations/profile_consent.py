"""Compatibility exports for the education application's profile consent."""

from cogniguard.applications.education.profile_consent import (
    ProfileConsentPolicy,
    filter_profile,
    resolve_profile_consent,
    revoke_profile_consent,
)
from cogniguard.applications.education.profile_consent import (
    _key as _key,
)
from cogniguard.applications.education.profile_consent import (
    _state as _state,
)

__all__ = [
    "ProfileConsentPolicy",
    "filter_profile",
    "resolve_profile_consent",
    "revoke_profile_consent",
]
