"""Coalition reconstruction agrees with an exhaustive enumeration on small instances."""

from __future__ import annotations

import random
from itertools import combinations

import pytest

from cogniguard.governance.reconstruction import check_release, residual_distance
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry


def _unit(name: str) -> tuple[str, str]:
    return ("doc", name)


def _target(target_id: str, *groups: set[str]) -> ProtectedTarget:
    witnesses = tuple(frozenset(_unit(name) for name in group) for group in groups)
    return ProtectedTarget(target_id, "owner", "org", witnesses)


def _knowledge(**held: set[str]) -> dict[str, frozenset]:
    return {name: frozenset(_unit(unit) for unit in units) for name, units in held.items()}


def test_coalition_size_below_one_is_rejected() -> None:
    registry = TargetRegistry([_target("goal", {"a", "b"})])
    knowledge = _knowledge(r={"a"})
    release = frozenset({_unit("b")})

    for limit in (0, -1):
        with pytest.raises(ValueError, match="at least 1"):
            check_release(registry, "r", release, knowledge, limit)
        with pytest.raises(ValueError, match="at least 1"):
            residual_distance(registry, "r", release, knowledge, limit)


def test_recipient_who_already_holds_the_rest_is_alone_enough() -> None:
    registry = TargetRegistry([_target("goal", {"a", "b"})])
    knowledge = _knowledge(r={"a"}, s=set())
    release = frozenset({_unit("b")})

    verdict = check_release(registry, "r", release, knowledge, k=1)

    assert verdict.safe is False
    assert verdict.violations[0].coalition == ("r",)
    assert verdict.violations[0].witness == frozenset({_unit("a"), _unit("b")})
    assert residual_distance(registry, "r", release, knowledge, k=1) == {"goal": 0}


def test_classmate_completes_the_witness_only_when_the_coalition_may_include_them() -> None:
    registry = TargetRegistry([_target("goal", {"a", "b"})])
    knowledge = _knowledge(r=set(), s={"a"})
    release = frozenset({_unit("b")})

    blocked = check_release(registry, "r", release, knowledge, k=2)
    alone = check_release(registry, "r", release, knowledge, k=1)

    assert blocked.safe is False
    assert blocked.violations[0].coalition == ("r", "s")
    assert alone.safe is True
    assert alone.violations == ()
    assert residual_distance(registry, "r", release, knowledge, k=2) == {"goal": 0}
    assert residual_distance(registry, "r", release, knowledge, k=1) == {"goal": 1}


def test_three_students_need_the_full_coalition() -> None:
    registry = TargetRegistry([_target("goal", {"a", "b", "c"})])
    knowledge = _knowledge(r=set(), s={"a"}, t={"b"})
    release = frozenset({_unit("c")})

    wide = check_release(registry, "r", release, knowledge, k=3)
    narrow = check_release(registry, "r", release, knowledge, k=2)

    assert wide.safe is False
    assert wide.violations[0].coalition == ("r", "s", "t")
    assert narrow.safe is True
    assert residual_distance(registry, "r", release, knowledge, k=3) == {"goal": 0}
    assert residual_distance(registry, "r", release, knowledge, k=2) == {"goal": 1}


def test_duplicate_holders_of_one_unit_count_once() -> None:
    registry = TargetRegistry([_target("goal", {"a", "b"})])
    knowledge = _knowledge(r=set(), s1={"a"}, s2={"a"})
    release = frozenset({_unit("b")})

    verdict = check_release(registry, "r", release, knowledge, k=2)

    assert verdict.safe is False
    assert verdict.violations[0].coalition == ("r", "s1")
    assert len(verdict.violations[0].coalition) == 2
    assert check_release(registry, "r", release, knowledge, k=1).safe is True


def test_either_witness_set_is_enough_to_violate() -> None:
    registry = TargetRegistry([_target("goal", {"a"}, {"b", "c"})])
    knowledge = _knowledge(r=set(), s=set())
    release = frozenset({_unit("a")})

    verdict = check_release(registry, "r", release, knowledge, k=1)

    assert verdict.safe is False
    assert verdict.violations[0].witness == frozenset({_unit("a")})
    assert residual_distance(registry, "r", release, knowledge, k=1) == {"goal": 0}


def test_targets_outside_the_release_are_ignored() -> None:
    registry = TargetRegistry(
        [_target("released", {"a"}), _target("untouched", {"z"})]
    )
    knowledge = _knowledge(r=set())
    release = frozenset({_unit("a")})

    verdict = check_release(registry, "r", release, knowledge, k=1)

    assert [item.target_id for item in verdict.violations] == ["released"]
    assert residual_distance(registry, "r", release, knowledge, k=1) == {"released": 0}


def test_reported_coalition_covers_the_witness_within_the_size_limit() -> None:
    registry = TargetRegistry([_target("goal", {"a", "b", "c"})])
    knowledge = _knowledge(r={"a"}, s={"b"}, t={"c"})
    release = frozenset({_unit("b")})

    verdict = check_release(registry, "r", release, knowledge, k=2)

    assert verdict.safe is False
    for violation in verdict.violations:
        assert violation.reason == ""
        assert "r" in violation.coalition
        assert len(violation.coalition) <= 2
        covered = set(release)
        for member in violation.coalition:
            covered |= knowledge[member]
        assert violation.witness <= covered


def test_oversized_free_set_is_a_conservative_violation() -> None:
    registry = TargetRegistry([_target("goal", {"a", "b", "c", "d"})])
    knowledge = _knowledge(r=set())
    release = frozenset({_unit("a")})

    verdict = check_release(registry, "r", release, knowledge, k=1, max_free_units=2)

    assert verdict.safe is False
    assert verdict.violations[0].reason == "too_large"
    assert verdict.violations[0].coalition == ("r",)


def test_residual_distance_above_the_free_unit_cap_is_zero() -> None:
    registry = TargetRegistry([_target("goal", {"a", "b", "c", "d"})])
    knowledge = _knowledge(r=set())
    release = frozenset({_unit("a")})

    assert residual_distance(registry, "r", release, knowledge, k=1) == {"goal": 3}
    assert residual_distance(
        registry, "r", release, knowledge, k=1, max_free_units=2
    ) == {"goal": 0}


def test_brute_force_matches_on_three_hundred_small_instances() -> None:
    rng = random.Random(0)
    safe_count = 0
    unsafe_count = 0
    for index in range(300):
        unit_count = rng.randint(1, 8)
        units = [("res", f"u{number}") for number in range(unit_count)]
        people = [f"p{number}" for number in range(rng.randint(1, 6))]
        recipient = people[0]
        limit = rng.randint(1, 4)
        targets = []
        for number in range(rng.randint(1, 3)):
            witnesses = []
            for _ in range(rng.randint(1, 2)):
                witnesses.append(frozenset(rng.sample(units, rng.randint(1, min(4, unit_count)))))
            targets.append(ProtectedTarget(f"t{number}", "owner", "org", tuple(witnesses)))
        registry = TargetRegistry(targets)
        knowledge = {
            person: frozenset(rng.sample(units, rng.randint(0, unit_count))) for person in people
        }
        release = frozenset(rng.sample(units, rng.randint(1, unit_count)))

        verdict = check_release(registry, recipient, release, knowledge, limit)
        distances = residual_distance(registry, recipient, release, knowledge, limit)
        expected_safe, expected_distances = _brute_force(
            registry, recipient, release, knowledge, limit
        )

        assert verdict.safe is expected_safe, index
        assert distances == expected_distances, index
        for violation in verdict.violations:
            assert violation.reason == ""
            assert recipient in violation.coalition
            assert len(violation.coalition) <= limit
            covered = set(release)
            for member in violation.coalition:
                covered |= knowledge.get(member, frozenset())
            assert violation.witness <= covered
        if verdict.safe:
            safe_count += 1
        else:
            unsafe_count += 1

    assert safe_count + unsafe_count == 300
    assert safe_count > 0
    assert unsafe_count > 0


def _affected(registry, release: frozenset):
    found = {}
    for unit in release:
        for target in registry.targets_for_unit(unit):
            found.setdefault(target.target_id, target)
    return [found[target_id] for target_id in sorted(found)]


def _brute_force(registry, recipient, release, knowledge, k):
    others = sorted(name for name in knowledge if name != recipient)
    distances = {}
    safe = True
    for target in _affected(registry, release):
        best = None
        for witness in target.witness_sets:
            gap = len(witness)
            for extra in range(k):
                for combo in combinations(others, extra):
                    covered = set(knowledge.get(recipient, frozenset())) | set(release)
                    for name in combo:
                        covered |= knowledge[name]
                    gap = min(gap, len(set(witness) - covered))
            best = gap if best is None else min(best, gap)
        distances[target.target_id] = 0 if best is None else best
        if distances[target.target_id] == 0:
            safe = False
    return safe, distances
