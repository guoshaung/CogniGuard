"""Four defenses. Each one picks a single candidate for a recipient."""

from __future__ import annotations

from cogniguard.runtime.release_gate import (
    Candidate,
    ReleaseGate,
    ReleaseRequest,
)

from experiments.capd_eval_20261123.memstore import MemoryDisclosureStore


def leakage(candidate: Candidate) -> float:
    """Disclosed exposure. Empty answers, including refusal, add nothing."""
    return sum(unit.exposure_delta for unit in candidate.units)


def prefer(candidates) -> Candidate:
    return sorted(candidates, key=lambda item: (-item.utility, len(item.units), item.name))[0]


class NoDefense:
    """Always return the highest-utility candidate."""

    def select(self, recipient_id: str, candidates: tuple[Candidate, ...]) -> Candidate:
        del recipient_id
        return prefer(candidates)


class PerRecipientBudget:
    """OCELOT-style ledger: each recipient has a private leakage budget."""

    def __init__(self, budget: float) -> None:
        if budget < 0:
            raise ValueError("budget must be non-negative")
        self.budget = float(budget)
        self.used: dict[str, float] = {}

    def select(self, recipient_id: str, candidates: tuple[Candidate, ...]) -> Candidate:
        spent = self.used.get(recipient_id, 0.0)
        chosen = prefer(self._affordable(candidates, spent))
        self.used[recipient_id] = spent + leakage(chosen)
        return chosen

    def _affordable(self, candidates, spent: float) -> list[Candidate]:
        return [
            candidate
            for candidate in candidates
            if spent + leakage(candidate) <= self.budget
        ]


class GlobalBudget:
    """One shared leakage budget for every recipient."""

    def __init__(self, budget: float) -> None:
        if budget < 0:
            raise ValueError("budget must be non-negative")
        self.budget = float(budget)
        self.used = 0.0

    def select(self, recipient_id: str, candidates: tuple[Candidate, ...]) -> Candidate:
        del recipient_id
        chosen = prefer(
            candidate
            for candidate in candidates
            if self.used + leakage(candidate) <= self.budget
        )
        self.used += leakage(chosen)
        return chosen


class Capd:
    """ReleaseGate with a configurable coalition size. State stays in memory."""

    def __init__(
        self,
        target_registry,
        coalition_k: int,
        *,
        price_lambda: float = 1.0,
        price_decay: float = 1.0,
    ) -> None:
        self.store = MemoryDisclosureStore()
        self.gate = ReleaseGate(
            self.store,
            target_registry=target_registry,
            coalition_k=coalition_k,
        )
        self.price_lambda = price_lambda
        self.price_decay = price_decay
        self._now = 0.0

    def select(self, recipient_id: str, candidates: tuple[Candidate, ...]) -> Candidate:
        self._now += 1.0
        chosen, decision = self.gate.select_and_reserve(
            ReleaseRequest(
                recipient_principal_id=recipient_id,
                acting_org_id="lab",
                agent_principal_id="capd-eval",
                session_id=recipient_id,
                purpose="learning",
                units=(),
                now=self._now,
            ),
            candidates,
            price_lambda=self.price_lambda,
            decay=self.price_decay,
        )
        self.gate.commit(decision, self._now)
        if chosen is None or chosen.name == "refuse":
            return prefer(candidate for candidate in candidates if candidate.name == "refuse")
        return chosen
