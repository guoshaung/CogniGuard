"""Commit gate: checkers run before a version is reserved."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from cogniguard.evolution.events import EvolutionEvent
from cogniguard.evolution.ledger import EvolutionLedger


@dataclass(frozen=True)
class CheckResult:
    allowed: bool
    reason: str = ""


class Checker(Protocol):
    name: str

    def check(self, event: EvolutionEvent, ledger: EvolutionLedger) -> CheckResult: ...


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str
    version_id: str | None
    event: object


class EvolutionGate:
    def __init__(
        self,
        ledger: EvolutionLedger,
        checkers: dict[str, list[Checker]],
        recheck: Callable | None = None,
    ) -> None:
        self.ledger = ledger
        self.checkers = checkers
        self.recheck = recheck
        self.audit: list[tuple[str, str, str, str, str]] = []

    def propose(self, event: EvolutionEvent) -> GateDecision:
        if event.parent_version != self.ledger.current(event.target):
            return self._reject(event, "stale_parent")
        for checker in self.checkers.get(event.kind, []):
            result = checker.check(event, self.ledger)
            if not result.allowed:
                return self._reject(event, f"{checker.name}:{result.reason}")
        version_id = self.ledger.reserve(event)
        return GateDecision(True, "", version_id, event)

    def commit(self, decision: GateDecision) -> bool:
        if not decision.allowed or decision.version_id is None:
            raise ValueError("cannot commit a rejected decision")
        event = decision.event
        if self.recheck is not None and not self.recheck(event):
            self.ledger.cancel(decision.version_id)
            self._record(event, "cancelled", "recheck_failed")
            return False
        self.ledger.commit(decision.version_id)
        self._record(event, "committed", "")
        return True

    def cancel(self, decision: GateDecision) -> None:
        if decision.version_id is None:
            return
        self.ledger.cancel(decision.version_id)
        self._record(decision.event, "cancelled", "cancelled")

    def _reject(self, event: EvolutionEvent, reason: str) -> GateDecision:
        self._record(event, "rejected", reason)
        return GateDecision(False, reason, None, event)

    def _record(self, event: object, outcome: str, reason: str) -> None:
        # Payload is intentionally absent. Audit stores only the decision facts.
        self.audit.append((event.event_id, event.kind, event.agent_id, outcome, reason))
