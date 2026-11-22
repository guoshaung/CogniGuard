"""AccessScope keeps the old allow-list and consults AccessRegistry when one is set."""

import pytest

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.principals import AssetOwnership, Membership
from core.access import AccessScope
from protection.common.schemas import StudentProfile, Task


def _registry() -> AccessRegistry:
    return AccessRegistry(
        [
            AssetOwnership("r-ok", "t1", "school", 1),
            AssetOwnership("r-no", "t1", "school", 1),
            AssetOwnership("r-other", "t2", "other", 1),
        ],
        [
            Membership("s", "school", "student"),
            Membership("t1", "school", "teacher"),
            Membership("t2", "other", "teacher"),
        ],
        [
            AccessGrant("s", "r-ok", "tutoring", 1),
            AccessGrant("s", "r-other", "tutoring", 1),
        ],
    )


def _profile_and_task(need_resource: bool) -> tuple[StudentProfile, Task]:
    return StudentProfile("s"), Task("q", "s", "question", "knowledge", "easy", need_resource)


def test_without_registry_scope_matches_the_previous_allow_list() -> None:
    profile, task = _profile_and_task(True)
    open_scope = AccessScope("s")
    listed = AccessScope("s", resource_ids=["r-ok"])

    assert open_scope.registry is None
    assert open_scope.acting_org_id is None
    assert open_scope.purpose == "tutoring"
    assert open_scope.permits("r-ok", now=0.0) is True
    assert open_scope.permits("r-no", now=0.0) is True
    assert listed.permits("r-ok", now=0.0) is True
    assert listed.permits("r-no", now=0.0) is False
    assert AccessScope("s", resource_ids=[]).permits("r-ok", now=0.0) is False

    open_scope.authorize(profile, task)
    listed.authorize(profile, task)
    AccessScope("s", allow_resources=False).authorize(profile, Task("q", "s", "question", "knowledge", "easy", False))

    with pytest.raises(ValueError):
        open_scope.authorize(profile, Task("q", "other", "question", "knowledge", "easy", False))
    with pytest.raises(PermissionError):
        AccessScope("other").authorize(profile, task)
    with pytest.raises(PermissionError):
        AccessScope("s", allow_resources=False).authorize(profile, task)
    with pytest.raises(PermissionError):
        AccessScope("s", resource_ids=[]).authorize(profile, task)


def test_registry_without_acting_org_is_rejected() -> None:
    profile, task = _profile_and_task(False)
    scope = AccessScope("s", registry=_registry())

    with pytest.raises(PermissionError):
        scope.authorize(profile, task)
    assert scope.permits("r-ok", now=0.0) is False


def test_registry_permits_only_a_granted_resource_in_the_acting_org() -> None:
    profile, task = _profile_and_task(True)
    scope = AccessScope("s", registry=_registry(), acting_org_id="school")

    scope.authorize(profile, task)
    assert scope.permits("r-ok", now=0.0) is True
    assert scope.permits("r-no", now=0.0) is False
    assert scope.permits("r-other", now=0.0) is False


def test_resource_ids_and_registry_must_both_permit() -> None:
    registry = _registry()
    scope = AccessScope(
        "s",
        resource_ids=["r-ok", "r-no"],
        registry=registry,
        acting_org_id="school",
    )
    granted_but_unlisted = AccessScope(
        "s",
        resource_ids=["r-no"],
        registry=registry,
        acting_org_id="school",
    )

    assert scope.permits("r-ok", now=0.0) is True
    assert scope.permits("r-no", now=0.0) is False
    assert scope.permits("r-other", now=0.0) is False
    assert granted_but_unlisted.permits("r-ok", now=0.0) is False
    assert granted_but_unlisted.permits("r-no", now=0.0) is False
