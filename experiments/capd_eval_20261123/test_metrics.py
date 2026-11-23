"""Metric definitions over a recorded decision list."""

from __future__ import annotations

from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from cogniguard.runtime.release_gate import Candidate, UnitRelease

from experiments.capd_eval_20261123.metrics import (
    Decision,
    false_refusal_rate,
    mean_decision_seconds,
    reconstruction_success_rate,
    utility_retention,
)


def _registry() -> TargetRegistry:
    witness = frozenset({("course", "a"), ("course", "b")})
    return TargetRegistry((ProtectedTarget("only", "owner", "org", (witness,)),))


def _full(unit_id: str) -> Candidate:
    return Candidate("full", (UnitRelease("course", unit_id, unit_id, 1.0),), 1.0)


def _decision(
    role: str,
    group_id: str | None,
    selected: Candidate,
    *,
    elapsed: float = 0.0,
    recipient: str = "student",
) -> Decision:
    return Decision(recipient, role, group_id, selected, elapsed)


def test_reconstruction_counts_groups_that_cover_a_witness() -> None:
    registry = _registry()
    covered = (
        _decision("coalition", "group-0", _full("a"), recipient="student-00"),
        _decision("coalition", "group-0", _full("b"), recipient="student-01"),
    )
    assert reconstruction_success_rate(registry, covered) == 1.0
    missing = (_decision("coalition", "group-0", _full("a")),)
    assert reconstruction_success_rate(registry, missing) == 0.0
    mixed = covered + (_decision("coalition", "group-1", _full("a"), recipient="student-02"),)
    assert reconstruction_success_rate(registry, mixed) == 0.5
    assert reconstruction_success_rate(registry, ()) == 0.0


def test_false_refusal_ignores_summaries_and_coalition_requests() -> None:
    decisions = (
        _decision("normal", None, Candidate("refuse", (), 0.0)),
        _decision("normal", None, Candidate("summary", (), 0.4)),
        _decision("coalition", "group-0", Candidate("refuse", (), 0.0)),
    )
    assert false_refusal_rate(decisions) == 0.5
    summary_only = (_decision("normal", None, Candidate("summary", (), 0.4)),)
    assert false_refusal_rate(summary_only) == 0.0
    assert false_refusal_rate(()) == 0.0


def test_utility_retention_and_mean_decision_time() -> None:
    assert utility_retention(1.0, 2.0) == 0.5
    assert utility_retention(3.0, 0.0) == 0.0
    timed = (
        _decision("normal", None, _full("a"), elapsed=1.0),
        _decision("normal", None, _full("b"), elapsed=3.0),
    )
    assert mean_decision_seconds(timed) == 2.0
    assert mean_decision_seconds(()) == 0.0
