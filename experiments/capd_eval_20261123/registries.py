"""R-syn and R-edu target tables for the pre-registered evaluation."""

from __future__ import annotations

import os
import random

from cogniguard.governance.targets import ProtectedTarget, TargetRegistry, load_asset_pack_targets

SYNTHETIC_SEED = 2026
TARGET_COUNT = 20
DOUBLE_WITNESS_TARGETS = 6
# 26 witness sets cannot split into equal thirds. 9, 9, and 8 is the closest.
WITNESS_SIZE_COUNTS = ((2, 9), (3, 9), (4, 8))
# Copying 13 private units onto other targets leaves 13 shared units out of 64.
SHARED_UNIT_COPIES = 13
RESOURCE_ID = "syn"


def synthetic_targets(seed: int = SYNTHETIC_SEED) -> tuple[ProtectedTarget, ...]:
    """Build R-syn. The default seed is the pre-registered seed."""
    rng = random.Random(seed)
    double = set(rng.sample(range(TARGET_COUNT), DOUBLE_WITNESS_TARGETS))
    sizes: list[int] = []
    for size, count in WITNESS_SIZE_COUNTS:
        sizes.extend([size] * count)
    rng.shuffle(sizes)

    groups: list[list[set[tuple[str, str]]]] = []
    cursor = 0
    next_unit = 0
    for index in range(TARGET_COUNT):
        witnesses: list[set[tuple[str, str]]] = []
        for _ in range(2 if index in double else 1):
            witness: set[tuple[str, str]] = set()
            for _ in range(sizes[cursor]):
                witness.add((RESOURCE_ID, f"u{next_unit:04d}"))
                next_unit += 1
            cursor += 1
            witnesses.append(witness)
        groups.append(witnesses)
    _copy_units_across_targets(rng, groups, SHARED_UNIT_COPIES)

    targets = tuple(
        ProtectedTarget(
            f"syn-{index:02d}",
            "owner",
            "org",
            tuple(frozenset(witness) for witness in witnesses),
        )
        for index, witnesses in enumerate(groups)
    )
    if sum(len(target.witness_sets) == 2 for target in targets) != DOUBLE_WITNESS_TARGETS:
        raise RuntimeError("synthetic witnesses collapsed")
    return targets


def education_targets() -> tuple[ProtectedTarget, ...]:
    """Load R-edu. The pack path is COGNIGUARD_ASSET_PACK. Only ids are read."""
    path = os.environ.get("COGNIGUARD_ASSET_PACK", "").strip()
    if not path:
        raise RuntimeError("COGNIGUARD_ASSET_PACK is required to load R-edu")
    return load_asset_pack_targets(path, owner_principal_id="owner", org_id="org")


def registry_from(targets) -> TargetRegistry:
    return TargetRegistry(targets)


def _copy_units_across_targets(rng: random.Random, groups, copies: int) -> None:
    for _ in range(copies):
        occurrences = _occurrences(groups)
        private = sorted(unit for unit, places in occurrences.items() if len(places) == 1)
        source = private[rng.randrange(len(private))]
        source_target = occurrences[source][0][0]
        options: list[tuple[int, int, tuple[str, str]]] = []
        for target_index, witnesses in enumerate(groups):
            if target_index == source_target:
                continue
            owned = set().union(*witnesses)
            if source in owned:
                continue
            for witness_index, witness in enumerate(witnesses):
                for removed in witness:
                    if len(occurrences[removed]) != 1:
                        continue
                    updated = set(witness)
                    updated.remove(removed)
                    updated.add(source)
                    if _overlaps_sibling(witnesses, witness_index, updated):
                        continue
                    options.append((target_index, witness_index, removed))
        options.sort()
        target_index, witness_index, removed = options[rng.randrange(len(options))]
        groups[target_index][witness_index].remove(removed)
        groups[target_index][witness_index].add(source)


def _occurrences(groups) -> dict[tuple[str, str], list[tuple[int, int]]]:
    found: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for target_index, witnesses in enumerate(groups):
        for witness_index, witness in enumerate(witnesses):
            for unit in witness:
                found.setdefault(unit, []).append((target_index, witness_index))
    return found


def _overlaps_sibling(witnesses, witness_index: int, updated: set[tuple[str, str]]) -> bool:
    for index, other in enumerate(witnesses):
        if index == witness_index:
            continue
        if updated <= other or other <= updated:
            return True
    return False
