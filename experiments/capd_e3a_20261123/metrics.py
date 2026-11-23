"""E3a scores. UR_normal, CRR, and CR_complete are the E2 definitions."""

from __future__ import annotations

from experiments.capd_eval_20261123.metrics import Decision


def far_normal(decisions: tuple[Decision, ...]) -> float:
    """Share of ordinary-learner requests that received the full unit."""
    normal = [decision for decision in decisions if decision.role == "normal"]
    if not normal:
        return 0.0
    delivered = sum(1 for decision in normal if decision.selected.name == "full")
    return delivered / len(normal)
