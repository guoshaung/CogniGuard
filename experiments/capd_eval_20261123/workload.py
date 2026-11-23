"""Seeded request stream. The same seed rebuilds the same requests."""

from __future__ import annotations

import random
from dataclasses import dataclass

from cogniguard.governance.targets import TargetRegistry
from cogniguard.runtime.release_gate import Candidate, UnitRelease


@dataclass(frozen=True)
class Request:
    recipient_id: str
    role: str
    group_id: str | None
    unit: tuple[str, str]
    candidates: tuple[Candidate, ...]


def generate_requests(
    registry: TargetRegistry,
    *,
    student_count: int,
    coalition_sizes: tuple[int, ...],
    seed: int,
    normal_requests: int = 2,
) -> tuple[Request, ...]:
    """Normal students sample units. Each coalition group splits one witness.

    `coalition_sizes` is the size of each colluding group, in student order.
    Remaining students are the normal population.
    """
    if student_count < 1:
        raise ValueError("student_count must be at least 1")
    if normal_requests < 1:
        raise ValueError("normal_requests must be at least 1")
    if any(size < 1 for size in coalition_sizes):
        raise ValueError("coalition groups must be non-empty")
    if sum(coalition_sizes) > student_count:
        raise ValueError("coalition groups exceed student_count")
    units = _units(registry)
    if not units:
        raise ValueError("registry has no units")

    students = tuple(f"student-{index:02d}" for index in range(student_count))
    rng = random.Random(seed)
    pending: list[Request] = []
    cursor = 0
    for group_index, size in enumerate(coalition_sizes):
        members = students[cursor : cursor + size]
        cursor += size
        pending.extend(_coalition_requests(registry, members, f"group-{group_index}", rng))
    for recipient in students[cursor:]:
        for _ in range(normal_requests):
            unit = units[rng.randrange(len(units))]
            pending.append(_request(recipient, "normal", None, unit))
    rng.shuffle(pending)
    return tuple(pending)


def _coalition_requests(registry, members, group_id: str, rng: random.Random) -> list[Request]:
    targets = [registry._by_id[key] for key in sorted(registry._by_id)]
    target = targets[rng.randrange(len(targets))]
    witnesses = list(target.witness_sets)
    witness = witnesses[rng.randrange(len(witnesses))]
    assigned: dict[str, list[tuple[str, str]]] = {member: [] for member in members}
    for index, unit in enumerate(sorted(witness)):
        assigned[members[index % len(members)]].append(unit)
    requests: list[Request] = []
    for member in members:
        for unit in assigned[member]:
            requests.append(_request(member, "coalition", group_id, unit))
    return requests


def _request(recipient: str, role: str, group_id: str | None, unit: tuple[str, str]) -> Request:
    resource_id, unit_id = unit
    full = Candidate(
        "full",
        (UnitRelease(resource_id, unit_id, f"{resource_id}:{unit_id}", 1.0),),
        1.0,
    )
    summary = Candidate("summary", (), 0.4)
    refuse = Candidate("refuse", (), 0.0)
    return Request(recipient, role, group_id, unit, (full, summary, refuse))


def _units(registry: TargetRegistry) -> tuple[tuple[str, str], ...]:
    found: set[tuple[str, str]] = set()
    for target in registry._by_id.values():
        for witness in target.witness_sets:
            found.update(witness)
    return tuple(sorted(found))
