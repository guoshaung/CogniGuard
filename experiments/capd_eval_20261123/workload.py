"""Seeded request stream. The same seed rebuilds the same requests."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from cogniguard.governance.targets import ProtectedTarget
from cogniguard.runtime.release_gate import Candidate, UnitRelease


@dataclass(frozen=True)
class Request:
    recipient_id: str
    role: str
    group_id: str | None
    unit: tuple[str, str]
    candidates: tuple[Candidate, ...]


def generate_requests(
    targets: Iterable[ProtectedTarget],
    *,
    student_count: int,
    coalition_sizes: tuple[int, ...],
    seed: int,
    normal_requests: int = 4,
    complete_ratio: float = 0.0,
) -> tuple[Request, ...]:
    """Build one shuffled stream.

    Coalition groups split one witness. Of the remaining students, the
    leading fraction `complete_ratio` (c) each request one whole witness.
    Every other remaining student is an ordinary learner and draws
    `normal_requests` (r) units. The default r is 4.
    """
    if student_count < 1:
        raise ValueError("student_count must be at least 1")
    if normal_requests < 1:
        raise ValueError("normal_requests must be at least 1")
    if complete_ratio < 0 or complete_ratio > 1:
        raise ValueError("complete_ratio must be between 0 and 1")
    if any(size < 1 for size in coalition_sizes):
        raise ValueError("coalition groups must be non-empty")
    if sum(coalition_sizes) > student_count:
        raise ValueError("coalition groups exceed student_count")
    catalog = tuple(sorted(targets, key=lambda target: target.target_id))
    units = _units(catalog)
    if not units:
        raise ValueError("registry has no units")

    students = tuple(f"student-{index:02d}" for index in range(student_count))
    rng = random.Random(seed)
    pending: list[Request] = []
    cursor = 0
    for group_index, size in enumerate(coalition_sizes):
        members = students[cursor : cursor + size]
        cursor += size
        pending.extend(_coalition_requests(catalog, members, f"group-{group_index}", rng))
    remaining = students[cursor:]
    complete_count = int(round(len(remaining) * complete_ratio))
    for recipient in remaining[:complete_count]:
        pending.extend(_complete_requests(catalog, recipient, rng))
    for recipient in remaining[complete_count:]:
        for _ in range(normal_requests):
            unit = units[rng.randrange(len(units))]
            pending.append(_request(recipient, "normal", None, unit))
    rng.shuffle(pending)
    return tuple(pending)


def _coalition_requests(catalog, members, group_id: str, rng: random.Random) -> list[Request]:
    target = catalog[rng.randrange(len(catalog))]
    witness = target.witness_sets[rng.randrange(len(target.witness_sets))]
    assigned: dict[str, list[tuple[str, str]]] = {member: [] for member in members}
    for index, unit in enumerate(sorted(witness)):
        assigned[members[index % len(members)]].append(unit)
    requests: list[Request] = []
    for member in members:
        for unit in assigned[member]:
            requests.append(_request(member, "coalition", group_id, unit))
    return requests


def _complete_requests(catalog, recipient: str, rng: random.Random) -> list[Request]:
    target = catalog[rng.randrange(len(catalog))]
    witness = target.witness_sets[rng.randrange(len(target.witness_sets))]
    return [_request(recipient, "complete", None, unit) for unit in sorted(witness)]


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


def _units(catalog: tuple[ProtectedTarget, ...]) -> tuple[tuple[str, str], ...]:
    found: set[tuple[str, str]] = set()
    for target in catalog:
        for witness in target.witness_sets:
            found.update(witness)
    return tuple(sorted(found))
