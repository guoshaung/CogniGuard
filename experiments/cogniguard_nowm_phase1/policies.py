"""Decision rules (METHOD.md §3). Every rule first requires AccessRegistry authorization;
evidence never authorizes. Each rule reads a knowledge map {principal: units} supplied by the
runner from ONE state layer (receipts | nli | true), so the same rule can be run under every
evidence condition: rule differences = algorithm, layer differences = information.
"""

from __future__ import annotations

from cogniguard.governance.reconstruction import check_release
from cogniguard.governance.targets import TargetRegistry


def _touched(targets: TargetRegistry, release):
    seen = {}
    for u in release:
        for t in targets.targets_for_unit(u):
            seen[t.target_id] = t
    return list(seen.values())


def protected_units(targets: TargetRegistry) -> frozenset:
    return frozenset(u for t in targets._by_id.values() for w in t.witness_sets for u in w)


class Rule:
    name = "rule"

    def allows(self, targets, recipient, release, knowledge) -> bool:  # pragma: no cover
        raise NotImplementedError


class B0_Access(Rule):
    """Traditional access control: authorization only."""
    name = "B0"

    def allows(self, targets, recipient, release, knowledge):
        return True


class B1_Budget(Rule):
    """Cumulative disclosure budget: a recipient may hold at most `budget` protected units."""

    def __init__(self, budget: int, protected: frozenset):
        self.budget, self.protected, self.name = budget, protected, f"B1(b={budget})"

    def allows(self, targets, recipient, release, knowledge):
        held = (knowledge.get(recipient, frozenset()) | frozenset(release)) & self.protected
        return len(held) <= self.budget


class B2_Quota(Rule):
    """Fixed quota (Woodruff-Staddon CCS'04 §8 allocation): per witness W a recipient holds at most
    floor((|W|-1)/k) of its units, so any k recipients jointly hold at most |W|-1."""

    def __init__(self, k: int):
        self.k, self.name = k, "B2"

    def allows(self, targets, recipient, release, knowledge):
        held = knowledge.get(recipient, frozenset()) | frozenset(release)
        for t in _touched(targets, release):
            for w in t.witness_sets:
                if len(held & w) > (len(w) - 1) // self.k:
                    return False
        return True


class B3_Pairwise(Rule):
    """Pairwise joint-leakage control (structural proxy, NOT OCELOT): the coalition check is applied
    only to witnesses of size <= 2, i.e. leakage that two units jointly produce."""

    def __init__(self, k: int, small_targets: TargetRegistry):
        self.k, self.small, self.name = k, small_targets, "B3"

    def allows(self, targets, recipient, release, knowledge):
        return check_release(self.small, recipient, set(release), knowledge, self.k).safe


class B4_Union(Rule):
    """Global knowledge-union control: nobody in the system may jointly complete any witness."""
    name = "B4"

    def allows(self, targets, recipient, release, knowledge):
        union = frozenset().union(*knowledge.values()) | frozenset(release)
        return not any(w <= union for t in _touched(targets, release) for w in t.witness_sets)


class CAPD(Rule):
    """CA-PD: no coalition of at most k principals including the recipient completes a witness."""

    def __init__(self, k: int):
        self.k, self.name = k, f"CAPD(k={k})"

    def allows(self, targets, recipient, release, knowledge):
        return check_release(targets, recipient, set(release), knowledge, self.k).safe
