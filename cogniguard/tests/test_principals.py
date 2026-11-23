"""Creation and organization checks for principal types."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cogniguard.governance.principals import AssetOwnership, Membership, Organization, same_org
from protection.common.schemas import TeacherResource


def test_types_can_be_created_and_are_frozen() -> None:
    organization = Organization(org_id="org-1", name="North School")
    membership = Membership(principal_id="p-1", org_id="org-1", role="teacher")
    ownership = AssetOwnership(resource_id="asset-1", owner_principal_id="p-1", org_id="org-1")

    assert organization.org_id == "org-1"
    assert membership.role == "teacher"
    assert ownership.policy_version == 1

    with pytest.raises(FrozenInstanceError):
        organization.name = "Other"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        membership.role = "student"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        ownership.policy_version = 2  # type: ignore[misc]


def test_same_org_matches_only_the_same_organization() -> None:
    teacher = Membership(principal_id="p-1", org_id="org-1", role="teacher")
    student = Membership(principal_id="p-2", org_id="org-1", role="student")
    admin = Membership(principal_id="p-3", org_id="org-2", role="admin")

    assert same_org(teacher, student) is True
    assert same_org(teacher, admin) is False


def test_teacher_resource_old_format_leaves_owner_and_org_empty() -> None:
    resource = TeacherResource.from_dict(
        {
            "resource_id": "r1",
            "chunk_id": "c1",
            "content": "lesson",
            "knowledge": "algebra",
            "difficulty": "easy",
            "cognitive_level": "remember",
            "resource_type": "note",
            "copyright_level": 0.2,
        }
    )

    assert resource.owner_principal_id is None
    assert resource.org_id is None


def test_teacher_resource_new_format_reads_owner_and_org() -> None:
    resource = TeacherResource.from_dict(
        {
            "resource_id": "r1",
            "chunk_id": "c1",
            "content": "lesson",
            "knowledge": "algebra",
            "difficulty": "easy",
            "cognitive_level": "remember",
            "resource_type": "note",
            "copyright_level": 0.2,
            "owner_principal_id": "p-1",
            "org_id": "org-1",
        }
    )

    assert resource.owner_principal_id == "p-1"
    assert resource.org_id == "org-1"
