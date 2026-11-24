"""One run = (world, rule, knowledge layer, k). Produces per-request records and a run summary.

Knowledge layers (what the rule sees):
  receipts : initial issuance + this run's own allowed deliveries
  nli      : receipts + units confirmed by the frozen BGE+NLI evidence (pe-1.0 SecurityState, confirmed layer)
  true     : receipts + every untracked acquisition (real retained facts + synthetic leaks)  [upper bound]
The oracle always judges on the TRUE state, with this run's deliveries, at the same k.
"""

from __future__ import annotations

import itertools
import time

from cogniguard.governance.reconstruction import _minimum_helpers, check_release
from cogniguard.provenance.state import SecurityState
from experiments.cogniguard_nowm_phase1.world import PRINCIPALS, World


def _frozen(d):
    return {p: frozenset(u) for p, u in d.items()}


def covered_targets(targets, knowledge, k) -> set:
    names = [p for p in PRINCIPALS if knowledge.get(p)]
    out = set()
    for t in targets._by_id.values():
        for w in t.witness_sets:
            for size in range(1, k + 1):
                if any(w <= frozenset().union(*(knowledge[p] for p in c))
                       for c in itertools.combinations(names, size)):
                    out.add(t.target_id)
                    break
    return out


def danger_profile(targets, recipient, release, truth, k):
    """For an oracle-unsafe request: smallest number of helpers and units they supply."""
    held = truth.get(recipient, frozenset()) | frozenset(release)
    best = None
    for u in release:
        for t in targets.targets_for_unit(u):
            for w in t.witness_sets:
                missing = w - held
                need, _ = _minimum_helpers(missing, truth, recipient) if missing else (0, ())
                if need is not None and need <= k - 1:
                    cand = (need, len(missing), len(w))
                    best = cand if best is None or cand < best else best
    return best


def simulate(world: World, rule, layer: str, k: int, verified: dict, record=True):
    deliveries: dict = {p: set() for p in PRINCIPALS}
    untracked: dict = {p: set() for p in PRINCIPALS}
    state = SecurityState(world.receipts) if layer == "nli" else None
    rows, lat = [], []
    c = dict(requests=0, authorized=0, danger=0, safe=0, allowed=0, harmful=0, unneeded=0, unauth_success=0)
    for e in world.events:
        if e.kind == "untracked":
            untracked[e.principal].update(e.units)
            continue
        if e.kind == "observation":
            if state is not None:
                state.apply(verified[id(e)])
            continue
        # request
        truth = _frozen({p: world.receipts[p] | deliveries[p] | untracked[p] for p in PRINCIPALS})
        if layer == "receipts":
            view = _frozen({p: world.receipts[p] | deliveries[p] for p in PRINCIPALS})
        elif layer == "nli":
            view = state.knowledge("confirmed")
        else:
            view = truth
        reg = world.access(e.t)
        authorized = all(reg.is_authorized(e.principal, u[0], e.purpose, "school", e.t) for u in e.units)
        t0 = time.perf_counter()
        allowed = authorized and rule.allows(world.targets, e.principal, e.units, view)
        lat.append(time.perf_counter() - t0)
        oracle_safe = check_release(world.targets, e.principal, set(e.units), truth, k).safe
        c["requests"] += 1
        c["authorized"] += authorized
        if authorized:
            c["danger" if not oracle_safe else "safe"] += 1
            c["harmful"] += allowed and not oracle_safe
            c["unneeded"] += (not allowed) and oracle_safe
        c["unauth_success"] += allowed and not authorized
        c["allowed"] += allowed
        prof = danger_profile(world.targets, e.principal, e.units, truth, k) if authorized and not oracle_safe else None
        if allowed:
            deliveries[e.principal].update(e.units)
            if state is not None:
                state.record_delivery(e.principal, e.units)
        if record:
            rows.append(dict(id=e.request_id, t=e.t, p=e.principal, u=list(e.units[0]), role=e.role,
                             auth=authorized, allow=allowed, oracle_safe=oracle_safe,
                             helpers=None if prof is None else prof[0], missing=None if prof is None else prof[1],
                             w=None if prof is None else prof[2], us=round(lat[-1] * 1e6, 1)))
    end_truth = _frozen({p: world.receipts[p] | deliveries[p] | untracked[p] for p in PRINCIPALS})
    base_truth = _frozen({p: world.receipts[p] | untracked[p] for p in PRINCIPALS})
    caused = covered_targets(world.targets, end_truth, k) - covered_targets(world.targets, base_truth, k)
    n_targets = len(world.targets._by_id)
    lat_sorted = sorted(lat)
    summary = dict(
        **c,
        harmful_rate=c["harmful"] / c["danger"] if c["danger"] else None,
        utility=1 - c["unneeded"] / c["safe"] if c["safe"] else None,
        unneeded_rate=c["unneeded"] / c["safe"] if c["safe"] else None,
        unauth_success_rate=c["unauth_success"] / (c["requests"] - c["authorized"]) if c["requests"] > c["authorized"] else 0.0,
        violation_rate=len(caused) / n_targets, violated=sorted(caused),
        p50_us=1e6 * lat_sorted[len(lat_sorted) // 2], p95_us=1e6 * lat_sorted[int(0.95 * (len(lat_sorted) - 1))],
    )
    return rows, summary
