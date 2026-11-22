"""Authorization cases for the immutable access registry. Time is passed as now."""

from __future__ import annotations

import pytest

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.principals import AssetOwnership, Membership


def _registry() -> AccessRegistry:
    ownerships = [
        AssetOwnership("r1", "t1", "school", 1),
        AssetOwnership("r1b", "t1", "school", 1),
        AssetOwnership("r2", "t2", "school", 1),
        AssetOwnership("r-cross", "t1", "other", 1),
        AssetOwnership("r-exp", "t1", "school", 1),
    ]
    memberships = [
        Membership("t1", "school", "teacher"),
        Membership("t2", "school", "teacher"),
        Membership("s1", "school", "student"),
        Membership("s2", "school", "student"),
        Membership("s3", "school", "student"),
        Membership("s-other", "other", "student"),
    ]
    grants = [
        AccessGrant("s1", "r1", "study", 1),
        AccessGrant("s2", "r1", "study", 1),
        AccessGrant("s3", "r1", "study", 1),
        AccessGrant("s3", "r2", "study", 1),
        AccessGrant("s-other", "r1", "study", 1),
        AccessGrant("s1", "r-exp", "study", 1, expires_at=100.0),
    ]
    return AccessRegistry(ownerships, memberships, grants)


def test_one_teacher_resource_is_granted_to_several_students() -> None:
    registry = _registry()

    assert registry.is_authorized("t1", "r1", "study", now=0.0) is True
    assert registry.is_authorized("s1", "r1", "study", now=0.0) is True
    assert registry.is_authorized("s2", "r1", "study", now=0.0) is True
    assert registry.is_authorized("s3", "r1b", "study", now=0.0) is False


def test_two_teachers_resources_do_not_cross() -> None:
    registry = _registry()

    assert registry.is_authorized("t1", "r2", "study", now=0.0) is False
    assert registry.is_authorized("t2", "r1", "study", now=0.0) is False
    assert registry.is_authorized("s1", "r2", "study", now=0.0) is False


def test_one_student_can_hold_partial_grants_from_two_teachers() -> None:
    registry = _registry()

    assert registry.is_authorized("s3", "r1", "study", now=0.0) is True
    assert registry.is_authorized("s3", "r2", "study", now=0.0) is True
    assert registry.is_authorized("s3", "r1b", "study", now=0.0) is False


def test_cross_org_access_is_denied_even_with_a_grant() -> None:
    registry = _registry()

    assert registry.org_of("s-other") == "other"
    assert registry.owner_of("r1").org_id == "school"
    assert registry.is_authorized("s-other", "r1", "study", now=0.0) is False
    assert registry.is_authorized("t1", "r-cross", "study", now=0.0) is False


def test_expired_grant_is_denied() -> None:
    registry = _registry()

    assert registry.is_authorized("s1", "r-exp", "study", now=99.0) is True
    assert registry.is_authorized("s1", "r-exp", "study", now=100.0) is False


def test_policy_version_change_leaves_the_original_registry_unchanged() -> None:
    registry = _registry()
    revised = registry.with_policy_version("r1", 2)

    assert revised.is_authorized("s1", "r1", "study", now=0.0) is False
    assert revised.owner_of("r1").policy_version == 2
    assert registry.is_authorized("s1", "r1", "study", now=0.0) is True
    assert registry.owner_of("r1").policy_version == 1
    assert registry.is_authorized("t1", "r1", "grade", now=0.0) is True


def test_unregistered_resource_is_denied() -> None:
    registry = _registry()

    assert registry.owner_of("missing") is None
    assert registry.is_authorized("s1", "missing", "study", now=0.0) is False
    assert registry.is_authorized("nobody", "r1", "study", now=0.0) is False


def test_purpose_mismatch_is_denied() -> None:
    registry = _registry()

    assert registry.is_authorized("s1", "r1", "grade", now=0.0) is False


def test_duplicate_resource_registration_is_rejected() -> None:
    with pytest.raises(ValueError):
        AccessRegistry(
            [
                AssetOwnership("r1", "t1", "school", 1),
                AssetOwnership("r1", "t2", "school", 1),
            ],
            [Membership("t1", "school", "teacher")],
            [],
        )


def _two_org_registry(memberships: list[Membership]) -> AccessRegistry:
    return AccessRegistry(
        [
            AssetOwnership("r-school", "t-school", "school", 1),
            AssetOwnership("r-lab", "t-lab", "lab", 1),
        ],
        memberships,
        [
            AccessGrant("s", "r-school", "study", 1),
            AccessGrant("s", "r-lab", "study", 1),
        ],
    )


def test_student_in_two_orgs_can_use_each_granted_resource() -> None:
    first = [
        Membership("s", "school", "student"),
        Membership("s", "lab", "student"),
        Membership("t-school", "school", "teacher"),
        Membership("t-lab", "lab", "teacher"),
    ]
    swapped = [
        Membership("s", "lab", "student"),
        Membership("s", "school", "student"),
        Membership("t-lab", "lab", "teacher"),
        Membership("t-school", "school", "teacher"),
    ]
    ahead = _two_org_registry(first)
    behind = _two_org_registry(swapped)

    assert ahead.orgs_of("s") == frozenset({"school", "lab"})
    for registry in (ahead, behind):
        assert registry.is_authorized("s", "r-school", "study", now=0.0) is True
        assert registry.is_authorized("s", "r-lab", "study", now=0.0) is True
