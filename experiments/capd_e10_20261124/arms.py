"""E10 arms: WS04 Sec.8 quota rule and the union-view ledger. Gate arm and no-defence come from E5."""

from __future__ import annotations

from collections import defaultdict

from experiments.capd_e5_20261123.arms import prefer


class Ws04Quota:
    """Each user may hold at most floor((|W|-1)/k) units of every witness W (allocation rule
    of Woodruff & Staddon, CCS 2004, Sec. 8; the private-retrieval protocol is not modelled)."""

    def __init__(self, secrets, k: int) -> None:
        self.k = k
        self.witnesses_of = defaultdict(list)
        for s in secrets:
            for w in s.witness_sets:
                for unit in w:
                    self.witnesses_of[unit].append(w)
        self.held: dict[str, set] = defaultdict(set)

    def _ok(self, recipient, candidate) -> bool:
        mine = self.held[recipient]
        for unit in candidate.units:
            ref = (unit.resource_id, unit.unit_id)
            for w in self.witnesses_of.get(ref, ()):
                cap = (len(w) - 1) // self.k
                if len((mine | {ref}) & w) > cap:
                    return False
        return True

    def select(self, recipient_id, candidates):
        chosen = prefer(c for c in candidates if self._ok(recipient_id, c))
        self.held[recipient_id].update((u.resource_id, u.unit_id) for u in chosen.units)
        return chosen


class UnionView:
    """Deliver only if L*(all recipients' holdings + candidate) <= tau + delta for every secret."""

    def __init__(self, secrets, delta: float) -> None:
        self.delta = delta
        self.by_unit = {u: s for s in secrets for u in s.units}
        self.all_held: set = set()

    def _ok(self, candidate) -> bool:
        added = {(u.resource_id, u.unit_id) for u in candidate.units}
        for secret in {self.by_unit[u] for u in added if u in self.by_unit}:
            if secret.leakage_star(self.all_held | added) > secret.tau + self.delta + 1e-9:
                return False
        return True

    def select(self, recipient_id, candidates):
        chosen = prefer(c for c in candidates if self._ok(c))
        self.all_held.update((u.resource_id, u.unit_id) for u in chosen.units)
        return chosen
