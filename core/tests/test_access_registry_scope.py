"""AccessScope keeps the old allow-list and consults AccessRegistry when one is set."""

from copy import deepcopy

import pytest

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.principals import AssetOwnership, Membership
from core.access import AccessScope
from core.pipeline import ProtectionPipeline, load_inputs
from core.tests.test_focused import INPUTS
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


def _two_teachers():
    """Same construction as core/tests/test_access.py: load the offline corpus, then clone one released resource."""
    config, profiles, questions, resources = load_inputs(*INPUTS)
    question = next(item for item in questions if item["need_resource"])
    profile = deepcopy(profiles[question["student_id"]])
    baseline = ProtectionPipeline(config, resources).run(
        profile, question, access=AccessScope(profile.student_id)
    )
    teacher_a = deepcopy(baseline.controlled.resource)
    teacher_a.resource_id = "teacher_a_resource"
    teacher_a.chunk_id = "teacher_a_chunk"
    teacher_a.owner_principal_id = "teacher-a"
    teacher_a.org_id = "school"
    teacher_b = deepcopy(teacher_a)
    teacher_b.resource_id = "teacher_b_resource"
    teacher_b.chunk_id = "teacher_b_chunk"
    teacher_b.owner_principal_id = "teacher-b"
    return config, profile, question, resources, teacher_a, teacher_b


def _school_registry(student_id: str, teacher_a_id: str, teacher_b_id: str) -> AccessRegistry:
    return AccessRegistry(
        [
            AssetOwnership(teacher_a_id, "teacher-a", "school", 1),
            AssetOwnership(teacher_b_id, "teacher-b", "school", 1),
        ],
        [
            Membership(student_id, "school", "student"),
            Membership(student_id, "lab", "student"),
            Membership("teacher-a", "school", "teacher"),
            Membership("teacher-b", "school", "teacher"),
        ],
        [AccessGrant(student_id, teacher_a_id, "tutoring", 1)],
    )


def _retrieval_ids(result) -> list[str]:
    if result.controlled is None:
        return []
    return [item["resource_id"] for item in result.controlled.source_trace["retrieval_trace"]]


def _release_id(result) -> str | None:
    controlled = result.controlled
    if controlled is None or controlled.resource is None or controlled.mode == "refuse":
        return None
    return controlled.resource.resource_id


def test_same_org_retrieval_releases_only_the_granted_teacher() -> None:
    config, profile, question, _resources, teacher_a, teacher_b = _two_teachers()
    registry = _school_registry(profile.student_id, teacher_a.resource_id, teacher_b.resource_id)
    pipeline = ProtectionPipeline(config, [teacher_b, teacher_a])
    result = pipeline.run(
        profile,
        question,
        access=AccessScope(profile.student_id, registry=registry, acting_org_id="school"),
    )

    assert _retrieval_ids(result) == [teacher_a.resource_id]
    assert _release_id(result) == teacher_a.resource_id
    assert teacher_b.resource_id not in _retrieval_ids(result)
    assert pipeline.budget.get(teacher_b.chunk_id) == 0
    assert pipeline.budget.get(teacher_a.chunk_id) > 0


def test_other_org_request_retrieves_neither_teacher() -> None:
    config, profile, question, _resources, teacher_a, teacher_b = _two_teachers()
    registry = _school_registry(profile.student_id, teacher_a.resource_id, teacher_b.resource_id)
    pipeline = ProtectionPipeline(config, [teacher_b, teacher_a])
    result = pipeline.run(
        profile,
        question,
        access=AccessScope(profile.student_id, registry=registry, acting_org_id="lab"),
    )

    assert result.controlled is None
    assert _retrieval_ids(result) == []
    assert _release_id(result) is None
    assert pipeline.last_state["candidate_count"] == 0
    assert pipeline.budget.get(teacher_a.chunk_id) == 0
    assert pipeline.budget.get(teacher_b.chunk_id) == 0


def test_old_authorization_misses_resource_after_policy_version_change() -> None:
    config, profile, question, _resources, teacher_a, teacher_b = _two_teachers()
    registry = _school_registry(profile.student_id, teacher_a.resource_id, teacher_b.resource_id)
    revised = registry.with_policy_version(teacher_a.resource_id, 2)
    pipeline = ProtectionPipeline(config, [teacher_b, teacher_a])
    result = pipeline.run(
        profile,
        question,
        access=AccessScope(profile.student_id, registry=revised, acting_org_id="school"),
    )

    assert registry.is_authorized(
        profile.student_id, teacher_a.resource_id, "tutoring", "school", now=0.0
    ) is True
    assert revised.is_authorized(
        profile.student_id, teacher_a.resource_id, "tutoring", "school", now=0.0
    ) is False
    assert result.controlled is None
    assert _retrieval_ids(result) == []
    assert pipeline.budget.get(teacher_a.chunk_id) == 0
    assert pipeline.budget.get(teacher_b.chunk_id) == 0


def test_without_registry_retrieval_matches_the_previous_result() -> None:
    config, profile, question, resources, teacher_a, teacher_b = _two_teachers()
    open_result = ProtectionPipeline(config, resources).run(
        profile, question, access=AccessScope(profile.student_id)
    )
    listed_all = ProtectionPipeline(config, resources).run(
        profile,
        question,
        access=AccessScope(
            profile.student_id,
            resource_ids=frozenset(resource.resource_id for resource in resources),
        ),
    )

    assert _retrieval_ids(open_result) == _retrieval_ids(listed_all)
    assert _release_id(open_result) == _release_id(listed_all)
    assert open_result.controlled.text == listed_all.controlled.text
    assert open_result.answer == listed_all.answer

    pipeline = ProtectionPipeline(config, [teacher_b, teacher_a])
    narrowed = pipeline.run(
        profile,
        question,
        access=AccessScope(profile.student_id, resource_ids=frozenset({teacher_a.resource_id})),
    )
    assert _retrieval_ids(narrowed) == [teacher_a.resource_id]
    assert _release_id(narrowed) == teacher_a.resource_id
    assert pipeline.budget.get(teacher_b.chunk_id) == 0
