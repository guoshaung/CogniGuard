"""Scores for one defense over one request stream."""

from __future__ import annotations

from dataclasses import dataclass

from cogniguard.governance.targets import TargetRegistry
from cogniguard.runtime.release_gate import Candidate


@dataclass(frozen=True)
class Decision:
    recipient_id: str
    role: str
    group_id: str | None
    selected: Candidate
    elapsed_seconds: float
    undefended_utility: float = 1.0


def reconstruction_success_rate(registry: TargetRegistry, decisions: tuple[Decision, ...]) -> float:
    """CRR: share of coalition groups whose delivered units cover some witness."""
    groups: dict[str, set[tuple[str, str]]] = {}
    for decision in decisions:
        if decision.role != "coalition" or decision.group_id is None:
            continue
        groups.setdefault(decision.group_id, set()).update(
            (unit.resource_id, unit.unit_id) for unit in decision.selected.units
        )
    if not groups:
        return 0.0
    covered = sum(1 for units in groups.values() if _covers_witness(registry, units))
    return covered / len(groups)


def crr(registry: TargetRegistry, decisions: tuple[Decision, ...]) -> float:
    return reconstruction_success_rate(registry, decisions)


def false_refusal_rate(decisions: tuple[Decision, ...]) -> float:
    """FRR: refusals among ordinary-learner requests."""
    normal = [decision for decision in decisions if decision.role == "normal"]
    if not normal:
        return 0.0
    refused = sum(1 for decision in normal if decision.selected.name == "refuse")
    return refused / len(normal)


def frr(decisions: tuple[Decision, ...]) -> float:
    return false_refusal_rate(decisions)


def ur_normal(decisions: tuple[Decision, ...]) -> float:
    """Utility retained by ordinary learners, against the undefended baseline."""
    normal = [decision for decision in decisions if decision.role == "normal"]
    if not normal:
        return 0.0
    delivered = sum(decision.selected.utility for decision in normal)
    undefended = sum(decision.undefended_utility for decision in normal)
    return utility_retention(delivered, undefended)


def cr_complete(decisions: tuple[Decision, ...]) -> float:
    """Share of complete-learner requests that were refused."""
    complete = [decision for decision in decisions if decision.role == "complete"]
    if not complete:
        return 0.0
    refused = sum(1 for decision in complete if decision.selected.name == "refuse")
    return refused / len(complete)


def utility_retention(delivered: float, undefended: float) -> float:
    """Delivered utility divided by the no-defense utility on the same stream."""
    if undefended == 0.0:
        return 0.0
    return delivered / undefended


def mean_decision_seconds(decisions: tuple[Decision, ...]) -> float:
    if not decisions:
        return 0.0
    return sum(decision.elapsed_seconds for decision in decisions) / len(decisions)


def delivered_utility(decisions: tuple[Decision, ...]) -> float:
    return sum(decision.selected.utility for decision in decisions)


def _covers_witness(registry: TargetRegistry, units: set[tuple[str, str]]) -> bool:
    held = frozenset(units)
    seen: set[str] = set()
    for unit in held:
        for target in registry.targets_for_unit(unit):
            if target.target_id in seen:
                continue
            seen.add(target.target_id)
            for witness in target.witness_sets:
                if witness <= held:
                    return True
    return False
