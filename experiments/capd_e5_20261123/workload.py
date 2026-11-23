"""Seeded request stream, same shape as E2. The same seed rebuilds the same requests."""

from __future__ import annotations

import random
from dataclasses import dataclass

from cogniguard.runtime.release_gate import Candidate, UnitRelease

from experiments.capd_e5_20261123.data import Secret, UnitRef


@dataclass(frozen=True)
class Group:
    group_id: str
    members: tuple[str, ...]
    target_id: str
    witness: frozenset[UnitRef]


@dataclass(frozen=True)
class Request:
    recipient_id: str
    role: str
    group_id: str | None
    unit: UnitRef
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class Stream:
    requests: tuple[Request, ...]
    groups: tuple[Group, ...]


def generate(
    secrets: tuple[Secret, ...],
    *,
    student_count: int,
    coalition_sizes: tuple[int, ...],
    seed: int,
    normal_requests: int,
    complete_ratio: float,
) -> Stream:
    """Coalition groups split one witness round-robin. Of the other students, the
    leading fraction c each request one whole witness; the rest draw r units."""
    if sum(coalition_sizes) > student_count:
        raise ValueError("coalition groups exceed student_count")
    units = tuple(sorted(unit for secret in secrets for unit in secret.units))
    students = tuple(f"student-{index:02d}" for index in range(student_count))
    rng = random.Random(seed)
    pending: list[Request] = []
    groups: list[Group] = []
    cursor = 0
    for index, size in enumerate(coalition_sizes):
        members = students[cursor : cursor + size]
        cursor += size
        secret = secrets[rng.randrange(len(secrets))]
        witness = secret.witness_sets[rng.randrange(len(secret.witness_sets))]
        group = Group(f"group-{index}", members, secret.target_id, witness)
        groups.append(group)
        for position, unit in enumerate(sorted(witness)):
            member = members[position % len(members)]
            pending.append(_request(member, "coalition", group.group_id, unit))
    remaining = students[cursor:]
    complete_count = int(round(len(remaining) * complete_ratio))
    for recipient in remaining[:complete_count]:
        secret = secrets[rng.randrange(len(secrets))]
        witness = secret.witness_sets[rng.randrange(len(secret.witness_sets))]
        pending.extend(_request(recipient, "complete", None, unit) for unit in sorted(witness))
    for recipient in remaining[complete_count:]:
        for _ in range(normal_requests):
            pending.append(_request(recipient, "normal", None, units[rng.randrange(len(units))]))
    rng.shuffle(pending)
    return Stream(tuple(pending), tuple(groups))


def _request(recipient: str, role: str, group_id: str | None, unit: UnitRef) -> Request:
    resource_id, unit_id = unit
    full = Candidate("full", (UnitRelease(resource_id, unit_id, unit_id, 1.0),), 1.0)
    summary = Candidate("summary", (), 0.4)
    refuse = Candidate("refuse", (), 0.0)
    return Request(recipient, role, group_id, unit, (full, summary, refuse))
