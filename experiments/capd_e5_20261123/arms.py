"""Five defenses. Each one picks a single candidate for a recipient.

Budget arms charge bits: a delivery costs the increase of L* on the recipient's
own view, summed over the secrets it touches. They never see other recipients.
"""

from __future__ import annotations

from cogniguard.governance.targets import TargetRegistry
from cogniguard.runtime.release_gate import Candidate, ReleaseGate, ReleaseRequest

from experiments.capd_e5_20261123.data import Secret
from experiments.capd_e5_20261123.memstore import MemoryDisclosureStore


def prefer(candidates) -> Candidate:
    return sorted(candidates, key=lambda item: (-item.utility, len(item.units), item.name))[0]


class BitLedger:
    """Per-recipient held units and the L* cost of adding more."""

    def __init__(self, secrets: tuple[Secret, ...]) -> None:
        self.by_unit = {unit: secret for secret in secrets for unit in secret.units}
        self.held: dict[str, set] = {}

    def cost(self, recipient: str, candidate: Candidate) -> float:
        held = self.held.get(recipient, set())
        added = {(unit.resource_id, unit.unit_id) for unit in candidate.units}
        total = 0.0
        for secret in {self.by_unit[unit] for unit in added if unit in self.by_unit}:
            before = secret.leakage_star(held)
            total += secret.leakage_star(held | added) - before
        return total

    def record(self, recipient: str, candidate: Candidate) -> None:
        self.held.setdefault(recipient, set()).update(
            (unit.resource_id, unit.unit_id) for unit in candidate.units
        )


class NoDefense:
    def select(self, recipient_id: str, candidates) -> Candidate:
        del recipient_id
        return prefer(candidates)


class PerRecipientBits:
    """OCELOT-style ledger: each recipient may gain at most B bits in total."""

    def __init__(self, secrets, budget: float) -> None:
        self.ledger = BitLedger(secrets)
        self.budget = float(budget)
        self.used: dict[str, float] = {}

    def select(self, recipient_id: str, candidates) -> Candidate:
        spent = self.used.get(recipient_id, 0.0)
        priced = [(c, self.ledger.cost(recipient_id, c)) for c in candidates]
        chosen = prefer(c for c, cost in priced if spent + cost <= self.budget + 1e-12)
        cost = dict((id(c), x) for c, x in priced)[id(chosen)]
        self.used[recipient_id] = spent + cost
        self.ledger.record(recipient_id, chosen)
        return chosen


class GlobalBits:
    """One shared bit budget, charged with each recipient's own L* increase."""

    def __init__(self, secrets, budget: float) -> None:
        self.ledger = BitLedger(secrets)
        self.budget = float(budget)
        self.used = 0.0

    def select(self, recipient_id: str, candidates) -> Candidate:
        priced = [(c, self.ledger.cost(recipient_id, c)) for c in candidates]
        chosen = prefer(c for c, cost in priced if self.used + cost <= self.budget + 1e-12)
        self.used += dict((id(c), x) for c, x in priced)[id(chosen)]
        self.ledger.record(recipient_id, chosen)
        return chosen


def no_defense_spend(secrets, requests) -> float:
    """Bits the global ledger would charge if every full candidate were delivered."""
    ledger = BitLedger(secrets)
    total = 0.0
    for request in requests:
        chosen = prefer(request.candidates)
        total += ledger.cost(request.recipient_id, chosen)
        ledger.record(request.recipient_id, chosen)
    return total


class GateArm:
    """ReleaseGate with coalition size k. max_witness=2 gives pairwise_only."""

    def __init__(self, secrets, coalition_k: int, *, max_witness: int | None = None) -> None:
        targets = [s.target(max_witness=max_witness) for s in secrets]
        self.registry = TargetRegistry(t for t in targets if t is not None)
        self.store = MemoryDisclosureStore()
        self.gate = ReleaseGate(self.store, target_registry=self.registry, coalition_k=coalition_k)
        self._now = 0.0

    def select(self, recipient_id: str, candidates) -> Candidate:
        self._now += 1.0
        chosen, decision = self.gate.select_and_reserve(
            ReleaseRequest(
                recipient_principal_id=recipient_id,
                acting_org_id="lab",
                agent_principal_id="capd-e5",
                session_id=recipient_id,
                purpose="learning",
                units=(),
                now=self._now,
            ),
            candidates,
            price_lambda=0.0,
            decay=1.0,
        )
        if decision.allowed:
            self.gate.commit(decision, self._now)
        if chosen is None:
            return prefer(c for c in candidates if c.name == "refuse")
        return chosen
