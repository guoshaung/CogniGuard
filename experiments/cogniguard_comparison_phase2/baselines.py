"""External baselines under Protocol A (same information). Fidelity labels follow BASELINE_AUDIT.md:

  PF  = paper-formula reproduction (rule implemented from the paper's equations; learned
        components replaced by exact quantities on our data)
  DEF = definition-level reconstruction (original algorithm text not accessible; the published
        definition is implemented exactly)
  STR = structural formalisation of an LLM-judgment defense (no LLM in the loop)

Every rule receives the SAME knowledge view (one state layer), the same authorization result
(checked by the runner), the same candidate (the requested unit) and the same k.
`allows(world, recipient, release, view) -> bool`.
"""

from __future__ import annotations

import itertools

from cogniguard.governance.reconstruction import check_release


def _touched(world, release):
    seen = {}
    for u in release:
        for t in world.targets.targets_for_unit(u):
            seen[t.target_id] = t
    return list(seen.values())


def _union(view):
    return frozenset().union(*view.values()) if view else frozenset()


class CAPD:
    """CogniGuard decision kernel (M3 when run on the nli layer)."""
    fidelity = "ours"

    def __init__(self, k):
        self.k, self.name = k, f"CAPD(k={k})"

    def allows(self, world, r, release, view):
        return check_release(world.targets, r, set(release), view, self.k).safe


class ExactEnum:
    """Same safety definition as CA-PD, decided by brute-force enumeration of every coalition of
    at most k principals that contains the recipient. Used to measure CA-PD's overhead against an
    equivalent exact algorithm (decisions must be identical)."""
    fidelity = "exact"

    def __init__(self, k):
        self.k, self.name = k, f"ExactEnum(k={k})"

    def allows(self, world, r, release, view):
        held = view.get(r, frozenset()) | frozenset(release)
        others = [p for p in view if p != r]
        for t in _touched(world, release):
            for w in t.witness_sets:
                for size in range(0, self.k):
                    for c in itertools.combinations(others, size):
                        if w <= held.union(*(view[p] for p in c)):
                            return False
        return True


class OcelotPF:
    """OCELOT (Xie & Li, arXiv:2606.12341) — paper-formula reproduction, PF.

    Eq.(4)  per-instance advantage  L = log2(max_s P(s|view) / max_s P(s))            [exact posterior here]
    Eq.(7)  c_i = max_f C(o_i, f)   ; identity operator only (atomic units: identity or drop)
    Eq.(8)  cost = mu(z) * sum_i c_i ; mu = 1 required-service, 2 semi-trusted, 4 adversarial (Pre-Reg. A)
    App.C-D each release is costed against the UNION of prior cross-sink releases (arbitrary collusion)
    Phase 4 commit iff L_cum + cost <= B ; otherwise escalate to drop (= refuse)

    Learned parts we cannot reproduce (no code / weights / C-tables / B_0 / U_R released) are replaced
    by exact quantities: C(identity, f) = the exact incremental min-entropy leakage of the unit given the
    union view (an oracle-calibrated cost, i.e. the best case for OCELOT's calibration).
    scope="field": one ledger per protected target (most permissive reading);
    scope="trajectory": one ledger per protected owner (all of an owner's fields share B, as in Eq.(1)).
    L_cum is derived from the shared state: L_cum(t) = mu_min * L_t(union) (telescoping sum of
    incremental costs; mu_min = cheapest trust class among holders, charitable to OCELOT)."""
    fidelity = "PF"

    def __init__(self, budget, mu, scope="field"):
        self.B, self.mu, self.scope = budget, mu, scope
        self.name = f"OCELOT-PF[{scope}](B={budget:g})"

    def _spent(self, world, t_id, union, view):
        wit_units = frozenset().union(*world.targets.get(t_id).witness_sets)
        held = union & wit_units
        if not held:
            return 0.0
        mu_min = min(self.mu.get(p, 4.0) for p, v in view.items() if v & held)
        return mu_min * world.leak[t_id](held)

    def allows(self, world, r, release, view):
        union = _union(view)
        new = union | frozenset(release)
        cost, spent = {}, {}
        for t in _touched(world, release):
            inc = world.leak[t.target_id](new) - world.leak[t.target_id](union)
            cost[t.target_id] = self.mu.get(r, 4.0) * max(inc, 0.0)
            spent[t.target_id] = self._spent(world, t.target_id, union, view)
        if self.scope == "field":
            return all(spent[t] + cost[t] <= self.B + 1e-9 for t in cost)
        by_owner = {}
        for t in cost:
            o = world.owner[t]
            by_owner.setdefault(o, [0.0, 0.0])
            by_owner[o][1] += cost[t]
        for o in by_owner:
            by_owner[o][0] = sum(self._spent(world, t, union, view) for t in world.owner if world.owner[t] == o)
        return all(s + c <= self.B + 1e-9 for s, c in by_owner.values())


class StaddonDef:
    """Staddon 2003, definition-level (DEF): c-collusion resistance (no <= c users jointly complete an
    inference channel) AND crowd control (once the users jointly hold all but the last object of a
    channel, nobody gets the last one, regardless of collusion level). Token construction not verified."""
    fidelity = "DEF"

    def __init__(self, k):
        self.k, self.name = k, f"Staddon-def(k={k})"

    def allows(self, world, r, release, view):
        return CAPD(self.k).allows(world, r, release, view) and CrowdControl().allows(world, r, release, view)


class CrowdControl:
    """Staddon 2003 crowd-control property alone (DEF): deny an object if, with it, all users jointly
    hold a complete channel."""
    fidelity = "DEF"
    name = "CrowdControl"

    def allows(self, world, r, release, view):
        u = _union(view) | frozenset(release)
        return not any(w <= u for t in _touched(world, release) for w in t.witness_sets)


class WS04Quota:
    """Woodruff & Staddon CCS'04 §8 allocation (as recorded in PRIOR_ART_AUDIT from the user's reading):
    each user holds at most floor((|W|-1)/k) objects of every channel W."""
    fidelity = "DEF"

    def __init__(self, k):
        self.k, self.name = k, f"WS04-quota(k={k})"

    def allows(self, world, r, release, view):
        held = view.get(r, frozenset()) | frozenset(release)
        return all(len(held & w) <= (len(w) - 1) // self.k
                   for t in _touched(world, release) for w in t.witness_sets)


class SumLeaksLocal:
    """Sum Leaks 'CoT + Sensitive Set L' (Patil et al. 2025, Table 1), STR: each defender guards one
    resource (table) and blocks if the questioner's history WITH THIS DEFENDER plus the answer completes a
    sensitive combination. Defenders are content-blind to each other."""
    fidelity = "STR"
    name = "SumLeaks-Local(CoT+L+H)"

    def allows(self, world, r, release, view):
        res = {u[0] for u in release}
        local = frozenset(u for u in view.get(r, frozenset()) if u[0] in res) | frozenset(release)
        return not any(w <= local for t in _touched(world, release) for w in t.witness_sets)


class SumLeaksCoDef:
    """Sum Leaks CoDef (Collaborative Consensus Defense), STR: defenders share their (non-private)
    query/response histories, i.e. the questioner's union view across all defenders, and block if the
    answer completes a sensitive combination for THAT questioner ('any defender flags' rule). No
    cross-questioner aggregation (the paper studies a single adversary). Under Protocol A this is exactly
    the single-principal check on the shared view, i.e. CA-PD with k = 1."""
    fidelity = "STR"
    name = "SumLeaks-CoDef"

    def allows(self, world, r, release, view):
        return CAPD(1).allows(world, r, release, view)


class SumLeaksToM:
    """Sum Leaks ToM defense, STR: block if the questioner's question sequence aims at 'all/most' parts of
    a sensitive combination; 'most' formalised as a fraction rho of the witness (swept)."""
    fidelity = "STR"

    def __init__(self, rho):
        self.rho, self.name = rho, f"SumLeaks-ToM(rho={rho:g})"

    def allows(self, world, r, release, view):
        held = view.get(r, frozenset()) | frozenset(release)
        return not any(len(held & w) >= max(self.rho * len(w), 1.0) - 1e-9 and (held & frozenset(release) & w)
                       for t in _touched(world, release) for w in t.witness_sets)


class AccessOnly:
    fidelity = "classic"
    name = "B0-Access"

    def allows(self, world, r, release, view):
        return True
