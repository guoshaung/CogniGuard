"""Coalition reconstruction check for a release that would complete a witness."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    target_id: str
    witness: frozenset
    coalition: tuple[str, ...]
    reason: str = ""


@dataclass(frozen=True)
class ReconstructionVerdict:
    safe: bool
    violations: tuple[Violation, ...]


def check_release(
    registry,
    recipient: str,
    release_units: Iterable[tuple[str, str]],
    knowledge: dict[str, frozenset],
    k: int,
    max_free_units: int = 20,
) -> ReconstructionVerdict:
    """Return whether some coalition of size at most k that includes recipient can finish a witness."""
    if k < 1:
        raise ValueError("coalition size must be at least 1")
    release = frozenset(release_units)
    known = {name: frozenset(units) for name, units in knowledge.items()}
    held = known.get(recipient, frozenset()) | release
    violations: list[Violation] = []
    for target in _affected_targets(registry, release):
        for witness in target.witness_sets:
            missing = witness - held
            if not missing:
                if k >= 1:
                    violations.append(Violation(target.target_id, witness, (recipient,)))
                continue
            if len(missing) > max_free_units:
                # The free set is too large to search. Count it as exposed.
                violations.append(
                    Violation(target.target_id, witness, (recipient,), "too_large")
                )
                continue
            needed, helpers = _minimum_helpers(missing, known, recipient)
            if needed is not None and needed <= k - 1:
                violations.append(
                    Violation(target.target_id, witness, (recipient, *helpers))
                )
    violations.sort(
        key=lambda item: (
            item.target_id,
            tuple(sorted(item.witness)),
            item.coalition,
            item.reason,
        )
    )
    return ReconstructionVerdict(not violations, tuple(violations))


def residual_distance(
    registry,
    recipient: str,
    release_units: Iterable[tuple[str, str]],
    knowledge: dict[str, frozenset],
    k: int,
    max_free_units: int = 20,
) -> dict[str, int]:
    """Units still missing for the closest coalition of size at most k, per affected target.

    A missing set larger than max_free_units is not searched. Its distance is 0,
    the same conservative direction as check_release treating that set as exposed.
    """
    if k < 1:
        raise ValueError("coalition size must be at least 1")
    release = frozenset(release_units)
    known = {name: frozenset(units) for name, units in knowledge.items()}
    held = known.get(recipient, frozenset()) | release
    distances: dict[str, int] = {}
    helpers = max(0, k - 1)
    for target in _affected_targets(registry, release):
        best: int | None = None
        for witness in target.witness_sets:
            missing = witness - held
            if not missing or len(missing) > max_free_units:
                distance = 0
            else:
                covered = _maximum_covered(missing, known, recipient, helpers)
                distance = len(missing) - covered
            best = distance if best is None else min(best, distance)
        distances[target.target_id] = 0 if best is None else best
    return distances


def _affected_targets(registry, release: frozenset):
    found = {}
    for unit in release:
        for target in registry.targets_for_unit(unit):
            found.setdefault(target.target_id, target)
    return tuple(found[target_id] for target_id in sorted(found))


def _masks(missing: frozenset, knowledge: dict[str, frozenset], recipient: str):
    """One bitmask per distinct coverage of `missing`. Identical masks count once."""
    ordered = tuple(sorted(missing))
    index = {unit: bit for bit, unit in enumerate(ordered)}
    chosen: dict[int, str] = {}
    for name in sorted(knowledge):
        if name == recipient:
            continue
        bits = 0
        for unit in knowledge[name]:
            bit = index.get(unit)
            if bit is not None:
                bits |= 1 << bit
        if bits == 0 or bits in chosen:
            continue
        chosen[bits] = name
    return ordered, [(bits, chosen[bits]) for bits in sorted(chosen)]


def _minimum_helpers(
    missing: frozenset, knowledge: dict[str, frozenset], recipient: str
) -> tuple[int | None, tuple[str, ...]]:
    _ordered, masks = _masks(missing, knowledge, recipient)
    width = len(missing)
    full = (1 << width) - 1
    impossible = len(masks) + 1
    fewest = [impossible] * (1 << width)
    # Node ids are parent pointers captured at the moment a state is improved.
    # Rewriting a state's best path later must not change paths already built from it.
    node_of = [-1] * (1 << width)
    nodes: list[tuple[int, int]] = []
    fewest[0] = 0
    for mask_index, (mask, _name) in enumerate(masks):
        for state in range((1 << width) - 1, -1, -1):
            if fewest[state] >= impossible:
                continue
            nxt = state | mask
            cost = fewest[state] + 1
            if cost < fewest[nxt]:
                fewest[nxt] = cost
                nodes.append((mask_index, node_of[state]))
                node_of[nxt] = len(nodes) - 1
    if fewest[full] >= impossible:
        return None, ()
    helpers: list[str] = []
    node_id = node_of[full]
    while node_id != -1:
        mask_index, node_id = nodes[node_id]
        helpers.append(masks[mask_index][1])
    return fewest[full], tuple(sorted(helpers))


def _maximum_covered(
    missing: frozenset,
    knowledge: dict[str, frozenset],
    recipient: str,
    helpers: int,
) -> int:
    """Largest part of `missing` coverable with at most `helpers` distinct masks."""
    if helpers <= 0 or not missing:
        return 0
    _ordered, masks = _masks(missing, knowledge, recipient)
    reachable = [set() for _ in range(helpers + 1)]
    reachable[0].add(0)
    for mask, _name in masks:
        for count in range(helpers - 1, -1, -1):
            for state in tuple(reachable[count]):
                reachable[count + 1].add(state | mask)
    best = 0
    for states in reachable:
        for state in states:
            best = max(best, state.bit_count())
    return best
