"""Reference StateUpdater: a two-layer, grow-only security state (PROVENANCE_INTERFACE.md §5).

  receipts   K_r : DisclosureStore.holders_of (system deliveries)
  confirmed  K_c : K_r ∪ verified unit holdings ∪ worst-case contents of verified events
  suspected  K_s : K_c ∪ unverified claims (holder UNKNOWN -> pseudo-principal "UNKNOWN")

Nothing is ever removed. An observation_id applies once; an event_id applies once,
and a reused event_id with different endpoints is a conflict and is not applied.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from cogniguard.provenance.interfaces import StateDelta
from cogniguard.provenance.schema import UNKNOWN, Unit, VerificationStatus, VerifiedEvidence

LAYERS = ("receipts", "confirmed", "confirmed+suspected")


class SecurityState:
    def __init__(self, receipts: Mapping[str, frozenset[Unit]], enforced_budget_f: int | None = None):
        self._receipts = {p: frozenset(u) for p, u in receipts.items()}
        self._confirmed: dict[str, set[Unit]] = defaultdict(set)
        self._suspected: dict[str, set[Unit]] = defaultdict(set)
        self._observations: set[str] = set()
        self._events: dict[str, tuple[str, str]] = {}
        self._credited: set[str] = set()
        self.enforced_budget_f = enforced_budget_f
        self.conflicts: list[str] = []

    def _held(self, principal: str) -> set[Unit]:
        return set(self._receipts.get(principal, ())) | self._confirmed.get(principal, set())

    def apply(self, ev: VerifiedEvidence) -> StateDelta:
        if ev.observation_id in self._observations:
            return StateDelta(duplicate=True)
        self._observations.add(ev.observation_id)
        if ev.verification_status in (VerificationStatus.REJECTED, VerificationStatus.UNKNOWN):
            return StateDelta()
        conf_add, sus_add, events = set(), set(), []
        holder = ev.holder_principal_id
        for unit in ev.confirmed_units:
            if unit not in self._held(holder):
                self._confirmed[holder].add(unit)
                conf_add.add((holder, unit))
        conflict = ""
        e = ev.verified_event
        if e is not None:
            ends = (e.sender_principal_id, e.receiver_principal_id)
            if e.event_id in self._events:
                if self._events[e.event_id] != ends:
                    conflict = f"event {e.event_id} reused with different endpoints"
                    self.conflicts.append(conflict)
            else:
                self._events[e.event_id] = ends
                events.append(e.event_id)
                if UNKNOWN not in ends:
                    # Worst case: the hop carried everything the sender held at that time.
                    for unit in self._held(e.sender_principal_id) - self._held(e.receiver_principal_id):
                        self._confirmed[e.receiver_principal_id].add(unit)
                        conf_add.add((e.receiver_principal_id, unit))
                    self._credited.add(e.event_id)
        for unit in ev.suspected_units:
            if unit not in self._suspected[holder] and unit not in self._held(holder):
                self._suspected[holder].add(unit)
                sus_add.add((holder, unit))
        return StateDelta(frozenset(conf_add), frozenset(sus_add), tuple(events), False, conflict)

    def record_delivery(self, principal: str, units) -> None:
        """A release the gate allowed becomes a receipt (DisclosureStore semantics)."""
        self._receipts[principal] = self._receipts.get(principal, frozenset()) | frozenset(units)

    def knowledge(self, layer: str) -> dict[str, frozenset[Unit]]:
        if layer not in LAYERS:
            raise ValueError(layer)
        names = set(self._receipts)
        if layer != "receipts":
            names |= set(self._confirmed)
        if layer == "confirmed+suspected":
            names |= set(self._suspected)
        out = {}
        for p in names:
            units = set(self._receipts.get(p, ()))
            if layer != "receipts":
                units |= self._confirmed.get(p, set())
            if layer == "confirmed+suspected":
                units |= self._suspected.get(p, set())
            out[p] = frozenset(units)
        return out

    def trusted_event_credits(self) -> int:
        """d: distinct verified hops with known endpoints, only under an enforced budget f."""
        if self.enforced_budget_f is None:
            return 0
        return min(len(self._credited), self.enforced_budget_f)
