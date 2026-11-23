"""True groups, registered groups, and the three collusion placements.

The request stream uses one random stream. Registration errors use another
stream started from the same seed. The requests therefore stay paired across
error rates: e changes only the groups the defense can see.
"""

from __future__ import annotations

import random

from experiments.capd_eval_20261123.workload import (
    Request,
    _coalition_requests,
    _complete_requests,
    _request,
    _units,
)

STUDENT_COUNT = 60
GROUP_COUNT = 6
COALITION_SIZES = (2, 2, 3, 3, 4, 4)
SCENARIOS = ("S-in", "S-x2", "S-xg")
ERROR_RATES = (0.0, 0.1, 0.3)


def assign_true_groups(
    student_count: int = STUDENT_COUNT,
    group_count: int = GROUP_COUNT,
) -> dict[str, str]:
    """Split students into equal true groups. Group labels are g0, g1, ..."""
    if student_count < 1 or group_count < 1:
        raise ValueError("student_count and group_count must be at least 1")
    if student_count % group_count != 0:
        raise ValueError("students do not divide into equal groups")
    size = student_count // group_count
    return {
        f"student-{index:02d}": f"g{index // size}"
        for index in range(student_count)
    }


def registered_groups(
    true_groups: dict[str, str],
    error_rate: float,
    seed: int,
) -> dict[str, str]:
    """Copy the true groups, then move a seeded fraction e onto another group."""
    if error_rate < 0 or error_rate > 1:
        raise ValueError("error_rate must be between 0 and 1")
    registered = dict(true_groups)
    student_count = len(registered)
    move_count = int(round(student_count * error_rate))
    if move_count == 0:
        return registered
    labels = sorted(set(registered.values()))
    if len(labels) < 2:
        raise ValueError("relabeling a student needs another group")
    rng = random.Random(seed)
    chosen = rng.sample(sorted(registered), move_count)
    for student in chosen:
        options = [label for label in labels if label != true_groups[student]]
        registered[student] = options[rng.randrange(len(options))]
    return registered


def place_coalitions(
    scenario: str,
    true_groups: dict[str, str],
    sizes: tuple[int, ...] = COALITION_SIZES,
) -> tuple[tuple[str, ...], ...]:
    """Place one coalition per size. Membership follows the true groups."""
    if scenario not in SCENARIOS:
        raise ValueError(scenario)
    if any(size < 1 for size in sizes):
        raise ValueError("coalition groups must be non-empty")
    labels = tuple(sorted(set(true_groups.values())))
    pools = {label: [] for label in labels}
    for student, group in true_groups.items():
        pools[group].append(student)
    for label in labels:
        pools[label].sort()
    if scenario == "S-in":
        placed = [
            tuple(_take(pools, labels[index], size))
            for index, size in enumerate(sizes)
        ]
    elif scenario == "S-x2":
        placed = []
        for index, size in enumerate(sizes):
            first = labels[(2 * index) % len(labels)]
            second = labels[(2 * index + 1) % len(labels)]
            left = (size + 1) // 2
            placed.append(
                tuple(
                    _take(pools, first, left)
                    + _take(pools, second, size - left)
                )
            )
    else:
        placed = []
        for index, size in enumerate(sizes):
            members: list[str] = []
            for offset in range(size):
                label = labels[(index + offset) % len(labels)]
                members.extend(_take(pools, label, 1))
            placed.append(tuple(members))
    return tuple(placed)


def generate_stream(
    targets,
    *,
    true_groups: dict[str, str],
    scenario: str,
    seed: int,
    complete_ratio: float,
    normal_requests: int = 4,
    coalition_sizes: tuple[int, ...] = COALITION_SIZES,
) -> tuple[Request, ...]:
    """One shuffled stream. Coalition units are dealt round-robin, as in E2."""
    if normal_requests < 1:
        raise ValueError("normal_requests must be at least 1")
    if complete_ratio < 0 or complete_ratio > 1:
        raise ValueError("complete_ratio must be between 0 and 1")
    catalog = tuple(sorted(targets, key=lambda target: target.target_id))
    units = _units(catalog)
    if not units:
        raise ValueError("registry has no units")
    placed = place_coalitions(scenario, true_groups, coalition_sizes)
    used = {member for members in placed for member in members}
    if len(used) != sum(len(members) for members in placed):
        raise ValueError("a student was placed in two coalitions")
    rng = random.Random(seed)
    pending: list[Request] = []
    for index, members in enumerate(placed):
        pending.extend(
            _coalition_requests(catalog, members, f"coalition-{index}", rng)
        )
    remaining = [student for student in sorted(true_groups) if student not in used]
    complete_count = int(round(len(remaining) * complete_ratio))
    for recipient in remaining[:complete_count]:
        pending.extend(_complete_requests(catalog, recipient, rng))
    for recipient in remaining[complete_count:]:
        for _ in range(normal_requests):
            unit = units[rng.randrange(len(units))]
            pending.append(_request(recipient, "normal", None, unit))
    rng.shuffle(pending)
    return tuple(pending)


def _take(pools: dict[str, list[str]], group: str, count: int) -> list[str]:
    if group not in pools:
        raise ValueError(group)
    if count > len(pools[group]):
        raise ValueError(f"{group} does not have {count} students left")
    taken = pools[group][:count]
    del pools[group][:count]
    return taken
