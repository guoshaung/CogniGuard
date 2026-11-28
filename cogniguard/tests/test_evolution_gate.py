"""Commit gate and in-memory ledger."""

from __future__ import annotations

from uuid import uuid4

from cogniguard.evolution.events import EvolutionEvent
from cogniguard.evolution.gate import CheckResult, EvolutionGate
from cogniguard.evolution.ledger import EvolutionLedger


class _Allow:
    name = "allow"

    def check(self, event, ledger) -> CheckResult:
        del event, ledger
        return CheckResult(True)


class _Deny:
    name = "deny"

    def check(self, event, ledger) -> CheckResult:
        del event, ledger
        return CheckResult(False, "no")


def _event(target: str, payload: str, parent: str | None, provenance: tuple[str, ...] = ()) -> EvolutionEvent:
    return EvolutionEvent(
        event_id=uuid4().hex,
        kind="memory_write",
        agent_id="teacher",
        target=target,
        payload=payload,
        parent_version=parent,
        provenance=provenance,
    )


def test_commit_updates_current():
    ledger = EvolutionLedger()
    gate = EvolutionGate(ledger, {"memory_write": [_Allow()]})
    decision = gate.propose(_event("t", "alpha", None))
    assert decision.allowed
    assert gate.commit(decision) is True
    assert ledger.current("t") == decision.version_id
    assert ledger.content(decision.version_id) == "alpha"


def test_checker_rejection_reserves_nothing():
    ledger = EvolutionLedger()
    gate = EvolutionGate(ledger, {"memory_write": [_Deny()]})
    decision = gate.propose(_event("t", "alpha", None))
    assert decision.allowed is False
    assert decision.reason == "deny:no"
    assert ledger.history("t") == []


def test_stale_parent_is_rejected():
    ledger = EvolutionLedger()
    gate = EvolutionGate(ledger, {})
    decision = gate.propose(_event("t", "alpha", "not-the-current"))
    assert decision.allowed is False
    assert decision.reason == "stale_parent"
    assert ledger.history("t") == []


def test_recheck_failure_cancels_and_keeps_current():
    ledger = EvolutionLedger()
    gate = EvolutionGate(ledger, {}, recheck=lambda event: False)
    decision = gate.propose(_event("t", "alpha", None))
    assert gate.commit(decision) is False
    assert ledger.current("t") is None
    assert ledger.history("t") == [(decision.version_id, "cancelled")]


def test_second_commit_raises():
    ledger = EvolutionLedger()
    gate = EvolutionGate(ledger, {})
    decision = gate.propose(_event("t", "alpha", None))
    gate.commit(decision)
    try:
        gate.commit(decision)
    except ValueError:
        return
    raise AssertionError("duplicate commit did not raise")


def test_lineage_is_newest_first():
    ledger = EvolutionLedger()
    gate = EvolutionGate(ledger, {})
    first = gate.propose(_event("t", "one", None))
    gate.commit(first)
    second = gate.propose(_event("t", "two", first.version_id))
    gate.commit(second)
    third = gate.propose(_event("t", "three", second.version_id))
    gate.commit(third)
    assert ledger.lineage(third.version_id) == [third.version_id, second.version_id, first.version_id]


def test_rollback_restores_current_and_keeps_rows():
    ledger = EvolutionLedger()
    gate = EvolutionGate(ledger, {})
    first = gate.propose(_event("t", "one", None))
    gate.commit(first)
    second = gate.propose(_event("t", "two", first.version_id))
    gate.commit(second)
    third = gate.propose(_event("t", "three", second.version_id))
    gate.commit(third)
    ledger.rollback("t", first.version_id)
    assert ledger.current("t") == first.version_id
    history = ledger.history("t")
    assert [status for _, status in history] == ["committed", "rolled_back", "rolled_back"]
    assert len(history) == 3
    assert ledger.content(third.version_id) == "three"


def test_descendants_follow_provenance_and_parent():
    ledger = EvolutionLedger()
    gate = EvolutionGate(ledger, {})
    origin = gate.propose(_event("a", "from-s", None, ("s",)))
    gate.commit(origin)
    child = gate.propose(_event("b", "from-a", None, (origin.version_id,)))
    gate.commit(child)
    assert ledger.descendants_of_source("s") == {origin.version_id, child.version_id}


def test_quarantine_restores_clean_version_or_clears_target():
    ledger = EvolutionLedger()
    gate = EvolutionGate(ledger, {})
    clean = gate.propose(_event("kept", "clean", None, ("ok",)))
    gate.commit(clean)
    dirty = gate.propose(_event("kept", "dirty", clean.version_id, ("s",)))
    gate.commit(dirty)
    only = gate.propose(_event("emptied", "only-dirty", None, ("s",)))
    gate.commit(only)
    affected = ledger.quarantine_source("s")
    assert set(affected) == {"kept", "emptied"}
    assert ledger.current("kept") == clean.version_id
    assert ledger.current("emptied") is None
    assert ledger.history("emptied") == [(only.version_id, "quarantined")]
    assert ledger.history("kept")[1][1] == "rolled_back"


def test_audit_does_not_store_payload():
    secret = "PAYLOAD_SHOULD_NOT_APPEAR_IN_AUDIT"
    ledger = EvolutionLedger()
    gate = EvolutionGate(ledger, {"memory_write": [_Deny()]})
    gate.propose(_event("t", secret, None))
    allowed = EvolutionGate(ledger, {})
    decision = allowed.propose(_event("u", secret, None))
    allowed.commit(decision)
    allowed.cancel(allowed.propose(_event("u", secret, decision.version_id)))
    rendered = " ".join(" ".join(row) for row in gate.audit + allowed.audit)
    assert secret not in rendered
    assert gate.audit[0][3] == "rejected"
