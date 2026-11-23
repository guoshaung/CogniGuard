"""A fixed seed rebuilds the same request stream."""

from __future__ import annotations

import pytest

from cogniguard.governance.targets import ProtectedTarget, TargetRegistry

from experiments.capd_eval_20261123.workload import generate_requests


def _registry() -> TargetRegistry:
    witness = frozenset({("course", "a"), ("course", "b"), ("course", "c")})
    other = frozenset({("course", "d"), ("course", "e"), ("course", "f")})
    return TargetRegistry(
        (
            ProtectedTarget("alpha", "owner", "org", (witness,)),
            ProtectedTarget("beta", "owner", "org", (other,)),
        )
    )


def test_same_seed_rebuilds_the_same_stream() -> None:
    first = generate_requests(
        _registry(), student_count=8, coalition_sizes=(3, 2), seed=20261123, normal_requests=2
    )
    second = generate_requests(
        _registry(), student_count=8, coalition_sizes=(3, 2), seed=20261123, normal_requests=2
    )
    assert first == second
    assert len(first) > 0


def test_different_seed_changes_the_stream() -> None:
    first = generate_requests(
        _registry(), student_count=8, coalition_sizes=(3, 2), seed=1, normal_requests=2
    )
    second = generate_requests(
        _registry(), student_count=8, coalition_sizes=(3, 2), seed=2, normal_requests=2
    )
    assert first != second


def test_coalition_splits_one_witness_and_normals_stay_unaffiliated() -> None:
    witness = frozenset({("course", "a"), ("course", "b"), ("course", "c")})
    registry = TargetRegistry((ProtectedTarget("only", "owner", "org", (witness,)),))
    requests = generate_requests(
        registry, student_count=6, coalition_sizes=(3,), seed=11, normal_requests=2
    )
    coalition = [item for item in requests if item.role == "coalition"]
    normal = [item for item in requests if item.role == "normal"]
    assert {item.group_id for item in coalition} == {"group-0"}
    by_member = {
        recipient: [item.unit for item in coalition if item.recipient_id == recipient]
        for recipient in ("student-00", "student-01", "student-02")
    }
    assert by_member == {
        "student-00": [("course", "a")],
        "student-01": [("course", "b")],
        "student-02": [("course", "c")],
    }
    assert {item.unit for item in coalition} == witness
    assert len(coalition) == len(witness)
    assert len(normal) == 6
    assert {item.recipient_id for item in normal} == {"student-03", "student-04", "student-05"}
    assert {item.group_id for item in normal} == {None}
    assert all(item.role == "normal" for item in normal)
    names = {candidate.name for item in requests for candidate in item.candidates}
    assert names == {"full", "summary", "refuse"}


def test_smaller_group_gives_some_members_more_than_one_unit() -> None:
    witness = frozenset({("course", "a"), ("course", "b"), ("course", "c")})
    registry = TargetRegistry((ProtectedTarget("only", "owner", "org", (witness,)),))
    requests = generate_requests(
        registry, student_count=3, coalition_sizes=(2,), seed=5, normal_requests=1
    )
    coalition = [item for item in requests if item.role == "coalition"]
    by_member = {
        recipient: sorted(item.unit for item in coalition if item.recipient_id == recipient)
        for recipient in ("student-00", "student-01")
    }
    assert by_member == {
        "student-00": [("course", "a"), ("course", "c")],
        "student-01": [("course", "b")],
    }
    assert {item.unit for item in coalition} == witness


def test_oversized_group_leaves_spare_members_without_a_request() -> None:
    witness = frozenset({("course", "a"), ("course", "b"), ("course", "c")})
    registry = TargetRegistry((ProtectedTarget("only", "owner", "org", (witness,)),))
    requests = generate_requests(
        registry, student_count=4, coalition_sizes=(4,), seed=3, normal_requests=1
    )
    coalition = [item for item in requests if item.role == "coalition"]
    assert {item.recipient_id for item in coalition} == {"student-00", "student-01", "student-02"}
    assert {item.unit for item in coalition} == witness


def test_rejects_invalid_population() -> None:
    registry = _registry()
    with pytest.raises(ValueError):
        generate_requests(registry, student_count=0, coalition_sizes=(), seed=1)
    with pytest.raises(ValueError):
        generate_requests(registry, student_count=2, coalition_sizes=(), seed=1, normal_requests=0)
    with pytest.raises(ValueError):
        generate_requests(registry, student_count=2, coalition_sizes=(0,), seed=1)
    with pytest.raises(ValueError):
        generate_requests(registry, student_count=2, coalition_sizes=(3,), seed=1)
    with pytest.raises(ValueError):
        generate_requests(TargetRegistry(()), student_count=1, coalition_sizes=(), seed=1)
