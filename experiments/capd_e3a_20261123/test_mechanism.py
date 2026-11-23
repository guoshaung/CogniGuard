"""Mechanism checks from the pre-registration. These are not section 5 runs."""

from __future__ import annotations

from cogniguard.governance.targets import ProtectedTarget, TargetRegistry

from experiments.capd_e3a_20261123.arms import CapdRel
from experiments.capd_eval_20261123.arms import Capd, NoDefense
from experiments.capd_eval_20261123.metrics import Decision, crr
from experiments.capd_eval_20261123.workload import Request, _request, generate_requests


def _record(arm, requests: tuple[Request, ...]) -> tuple[Decision, ...]:
    recorded = []
    for request in requests:
        selected = arm.select(request.recipient_id, request.candidates)
        recorded.append(
            Decision(
                request.recipient_id,
                request.role,
                request.group_id,
                selected,
                0.0,
            )
        )
    return tuple(recorded)


def _identity(selected) -> tuple:
    units = tuple((unit.resource_id, unit.unit_id) for unit in selected.units)
    return (selected.name, units)


def test_max_m_matches_capd_any() -> None:
    witness = frozenset({("course", "a"), ("course", "b")})
    other = frozenset({("course", "c"), ("course", "d"), ("course", "e")})
    targets = (
        ProtectedTarget("alpha", "owner", "org", (witness,)),
        ProtectedTarget("beta", "owner", "org", (other,)),
    )
    registry = TargetRegistry(targets)
    requests = generate_requests(
        targets,
        student_count=12,
        coalition_sizes=(2, 2, 3, 3),
        seed=1,
        normal_requests=2,
        complete_ratio=0.2,
    )
    true_groups = {f"student-{index:02d}": f"g{index // 4}" for index in range(12)}
    scrambled = {
        student: f"g{(int(student[-2:]) + 1) % 3}"
        for student in true_groups
    }
    group_count = len(set(true_groups.values()))
    blocked = False
    for groups in (true_groups, scrambled):
        for k in (2, 3, 4):
            for m in (group_count, group_count + 2):
                capd_any = Capd(registry, k, price_lambda=0.0, price_decay=1.0)
                capd_rel = CapdRel(
                    registry,
                    k,
                    m,
                    groups,
                    price_lambda=0.0,
                    price_decay=1.0,
                )
                any_choices = []
                rel_choices = []
                for request in requests:
                    any_selected = capd_any.select(
                        request.recipient_id, request.candidates
                    )
                    rel_selected = capd_rel.select(
                        request.recipient_id, request.candidates
                    )
                    any_choices.append(_identity(any_selected))
                    rel_choices.append(_identity(rel_selected))
                assert any_choices == rel_choices
                blocked = blocked or any(name != "full" for name, _units in any_choices)
    assert blocked


def test_h1_crr_is_zero_inside_the_boundary() -> None:
    pair = frozenset({("course", "a"), ("course", "b")})
    triple = frozenset({("course", "c"), ("course", "d"), ("course", "e")})
    # e = 0, span 1 <= m 1, two people <= k 2.
    same_group = (
        ProtectedTarget("pair", "owner", "org", (pair,)),
    )
    same_registry = TargetRegistry(same_group)
    same_requests = (
        _request("student-00", "coalition", "coalition-0", ("course", "a")),
        _request("student-01", "coalition", "coalition-0", ("course", "b")),
    )
    same_groups = {"student-00": "g0", "student-01": "g0"}
    assert crr(same_registry, _record(NoDefense(), same_requests)) == 1.0
    assert crr(
        same_registry,
        _record(CapdRel(same_registry, 2, 1, same_groups), same_requests),
    ) == 0.0

    # e = 0, span 2 <= m 2, three people <= k 4.
    cross_group = (
        ProtectedTarget("triple", "owner", "org", (triple,)),
    )
    cross_registry = TargetRegistry(cross_group)
    cross_requests = (
        _request("student-00", "coalition", "coalition-0", ("course", "c")),
        _request("student-01", "coalition", "coalition-0", ("course", "d")),
        _request("student-02", "coalition", "coalition-0", ("course", "e")),
    )
    cross_groups = {"student-00": "g0", "student-01": "g0", "student-02": "g1"}
    assert crr(cross_registry, _record(NoDefense(), cross_requests)) == 1.0
    assert crr(
        cross_registry,
        _record(CapdRel(cross_registry, 4, 2, cross_groups), cross_requests),
    ) == 0.0


def test_span_above_m_is_not_defended() -> None:
    witness = frozenset({("course", "a"), ("course", "b")})
    targets = (ProtectedTarget("pair", "owner", "org", (witness,)),)
    registry = TargetRegistry(targets)
    requests = (
        _request("student-00", "coalition", "coalition-0", ("course", "a")),
        _request("student-01", "coalition", "coalition-0", ("course", "b")),
    )
    groups = {"student-00": "g0", "student-01": "g1"}
    assert crr(registry, _record(Capd(registry, 4, price_lambda=0.0), requests)) == 0.0
    assert crr(registry, _record(CapdRel(registry, 4, 1, groups), requests)) == 1.0


def test_registration_error_leaks_include_a_mismatched_member() -> None:
    """A leak inside the defended boundary has a mislabeled member."""
    targets = (
        ProtectedTarget("pair", "owner", "org", (frozenset({("course", "a"), ("course", "b")}),)),
        ProtectedTarget("other", "owner", "org", (frozenset({("course", "c"), ("course", "d")}),)),
    )
    registry = TargetRegistry(targets)
    requests = (
        _request("student-00", "coalition", "coalition-0", ("course", "a")),
        _request("student-01", "coalition", "coalition-0", ("course", "b")),
        _request("student-02", "coalition", "coalition-1", ("course", "c")),
        _request("student-03", "coalition", "coalition-1", ("course", "d")),
    )
    true_groups = {
        "student-00": "g0",
        "student-01": "g0",
        "student-02": "g1",
        "student-03": "g1",
    }
    # Both coalitions span one true group. Only student-01 is mislabeled.
    registered = dict(true_groups)
    registered["student-01"] = "g1"
    decisions = _record(CapdRel(registry, 2, 1, registered), requests)
    successes = []
    for group_id in ("coalition-0", "coalition-1"):
        subset = tuple(item for item in decisions if item.group_id == group_id)
        if crr(registry, subset) == 1.0:
            successes.append(group_id)
    assert successes == ["coalition-0"]
    for group_id in successes:
        members = {
            request.recipient_id
            for request in requests
            if request.group_id == group_id
        }
        assert any(registered[member] != true_groups[member] for member in members)
