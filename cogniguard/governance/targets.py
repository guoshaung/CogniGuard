"""Protected reconstruction targets. A unit ref is a (resource_id, unit_id) pair."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


UnitRef = tuple[str, str]


def _unit_set(witness: Iterable[tuple[str, str]]) -> frozenset[UnitRef]:
    return frozenset((str(resource_id), str(unit_id)) for resource_id, unit_id in witness)


def _minimal_witness_sets(
    witness_sets: Iterable[Iterable[tuple[str, str]]],
) -> tuple[frozenset[UnitRef], ...]:
    sets = [_unit_set(witness) for witness in witness_sets]
    if not sets:
        raise ValueError("a protected target needs at least one witness set")
    if any(not item for item in sets):
        raise ValueError("witness sets must be non-empty")
    unique: list[frozenset[UnitRef]] = []
    for item in sets:
        if item not in unique:
            unique.append(item)
    # A set that contains another witness is redundant: the smaller set already recovers the target.
    minimal = [item for item in unique if not any(other < item for other in unique)]
    minimal.sort(key=lambda item: (len(item), tuple(sorted(item))))
    return tuple(minimal)


@dataclass(frozen=True)
class ProtectedTarget:
    target_id: str
    owner_principal_id: str
    org_id: str
    witness_sets: tuple[frozenset[UnitRef], ...]
    value: float = 1.0
    kind: Literal["teaching_asset", "student_attribute"] = "teaching_asset"
    domain_size: int | None = None
    value_commitment: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "witness_sets", _minimal_witness_sets(self.witness_sets))
        if self.domain_size is not None and self.domain_size < 2:
            raise ValueError("domain_size must be at least 2")


class TargetRegistry:
    """Index of protected targets. Duplicate target ids are rejected."""

    def __init__(self, targets: Iterable[ProtectedTarget]) -> None:
        items = tuple(targets)
        by_id: dict[str, ProtectedTarget] = {}
        for target in items:
            if target.target_id in by_id:
                raise ValueError(target.target_id)
            by_id[target.target_id] = target
        by_unit: dict[UnitRef, list[ProtectedTarget]] = {}
        for target in items:
            seen: set[UnitRef] = set()
            for witness in target.witness_sets:
                for unit in witness:
                    if unit in seen:
                        continue
                    seen.add(unit)
                    by_unit.setdefault(unit, []).append(target)
        self._by_id = by_id
        self._by_unit = {unit: tuple(found) for unit, found in by_unit.items()}

    def targets_for_unit(self, unit_ref: UnitRef) -> tuple[ProtectedTarget, ...]:
        return self._by_unit.get((unit_ref[0], unit_ref[1]), ())

    def get(self, target_id: str) -> ProtectedTarget:
        return self._by_id[target_id]


def commit_value(value: str, salt: str) -> str:
    """Hash a secret without storing it. The digest is sha256(salt + value)."""
    return hashlib.sha256(f"{salt}{value}".encode("utf-8")).hexdigest()


def verify_commitment(value: str, salt: str, commitment: str) -> bool:
    return commit_value(value, salt) == commitment


def load_asset_pack_targets(
    path, *, owner_principal_id: str, org_id: str
) -> tuple[ProtectedTarget, ...]:
    """Read protected_targets from an asset pack. Unit text is not retained."""
    source = Path(path) / "pedagogical_assets_v1.jsonl"
    loaded: list[ProtectedTarget] = []
    with source.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            package_id = str(record["package_id"])
            for item in record.get("protected_targets", ()):
                units = ((package_id, str(unit_id)) for unit_id in item["unit_ids"])
                loaded.append(
                    ProtectedTarget(
                        target_id=f"{package_id}/{item['target_id']}",
                        owner_principal_id=owner_principal_id,
                        org_id=org_id,
                        witness_sets=(frozenset(units),),
                        kind="teaching_asset",
                    )
                )
    return tuple(loaded)
