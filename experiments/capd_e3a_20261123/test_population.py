"""Group assignment, registration error, and the three placements."""

from __future__ import annotations

from experiments.capd_e3a_20261123.population import (
    COALITION_SIZES,
    assign_true_groups,
    generate_stream,
    place_coalitions,
    registered_groups,
)
from experiments.capd_eval_20261123.registries import synthetic_targets


def test_students_split_into_six_groups_of_ten() -> None:
    true_groups = assign_true_groups()
    assert len(true_groups) == 60
    counts: dict[str, int] = {}
    for group in true_groups.values():
        counts[group] = counts.get(group, 0) + 1
    assert counts == {f"g{index}": 10 for index in range(6)}


def test_error_rate_relabels_the_seeded_fraction_and_leaves_truth() -> None:
    true_groups = assign_true_groups()
    expected = {0.0: 0, 0.1: 6, 0.3: 18}
    for error_rate, count in expected.items():
        first = registered_groups(true_groups, error_rate, seed=4)
        second = registered_groups(true_groups, error_rate, seed=4)
        assert first == second
        moved = [
            student
            for student, group in first.items()
            if group != true_groups[student]
        ]
        assert len(moved) == count
        assert set(first) == set(true_groups)


def test_placements_follow_the_scenario_on_true_groups() -> None:
    true_groups = assign_true_groups()
    for scenario in ("S-in", "S-x2", "S-xg"):
        placed = place_coalitions(scenario, true_groups)
        assert [len(members) for members in placed] == list(COALITION_SIZES)
        flat = [member for members in placed for member in members]
        assert len(flat) == len(set(flat))
        for members in placed:
            spanned = {true_groups[member] for member in members}
            if scenario == "S-in":
                assert len(spanned) == 1
            elif scenario == "S-x2":
                assert len(spanned) == 2
            else:
                assert len(spanned) == len(members)


def test_same_seed_rebuilds_the_stream_for_one_scenario() -> None:
    targets = synthetic_targets()
    true_groups = assign_true_groups()
    first = generate_stream(
        targets,
        true_groups=true_groups,
        scenario="S-x2",
        seed=3,
        complete_ratio=0.2,
    )
    second = generate_stream(
        targets,
        true_groups=true_groups,
        scenario="S-x2",
        seed=3,
        complete_ratio=0.2,
    )
    assert first == second
    assert any(request.role == "coalition" for request in first)
    assert any(request.role == "normal" for request in first)
