"""Phase 2 runner (METHOD.md §3).

mode="snapshot" (Protocol A primary): the state evolves along ONE reference trajectory (the Oracle's
  releases: authorized and truly safe); every rule is queried on that same state, and its decision is
  scored but not applied. Danger / safe denominators are identical for all rules.
mode="path": each rule's own releases become receipts (Phase-1 style); used for coalition-violation
  and new-secret-reconstruction metrics, which only exist when decisions change the state.

Layers: receipts | nli (BGE+NLI confirmed; phase1 only) | true.
"""

from __future__ import annotations

import itertools
import time

from cogniguard.governance.reconstruction import check_release
from cogniguard.provenance.state import SecurityState
from experiments.cogniguard_comparison_phase2.worlds import PRINCIPALS


def _frozen(d):
    return {p: frozenset(u) for p, u in d.items()}


def reconstructable(world, knowledge, k) -> set:
    names = [p for p in PRINCIPALS if knowledge.get(p)]
    out = set()
    for t in world.targets._by_id.values():
        for w in t.witness_sets:
            if any(w <= frozenset().union(*(knowledge[p] for p in c))
                   for size in range(1, k + 1) for c in itertools.combinations(names, size)):
                out.add(t.target_id)
                break
    return out


def run(world, rules, layer, k, mode, verified, record=True):
    """Snapshot: many rules in one pass over one reference trajectory. Path: exactly one rule."""
    assert mode in ("snapshot", "path") and (mode == "snapshot" or len(rules) == 1)
    deliveries = {p: set() for p in PRINCIPALS}
    untracked = {p: set() for p in PRINCIPALS}
    state = SecurityState(world.receipts) if layer == "nli" else None
    stats = {r.name: dict(requests=0, danger=0, safe=0, harmful=0, unneeded=0, unauth=0, unauth_success=0,
                          danger_nh=0, harmful_nh=0, lat=[]) for r in rules}
    rows = []
    historical = reconstructable(world, _frozen(world.receipts), k)
    for e in world.events:
        if e.kind == "untracked":
            untracked[e.principal].update(e.units)
            continue
        if e.kind == "observation":
            if state is not None:
                state.apply(verified[id(e)])
            continue
        truth = _frozen({p: world.receipts[p] | deliveries[p] | untracked[p] for p in PRINCIPALS})
        view = (_frozen({p: world.receipts[p] | deliveries[p] for p in PRINCIPALS}) if layer == "receipts"
                else state.knowledge("confirmed") if layer == "nli" else truth)
        reg = world.access(e.t)
        authorized = all(reg.is_authorized(e.principal, u[0], e.purpose, "school", e.t) for u in e.units)
        oracle_safe = check_release(world.targets, e.principal, set(e.units), truth, k).safe
        decisions = {}
        for rule in rules:
            t0 = time.perf_counter()
            allowed = authorized and rule.allows(world, e.principal, e.units, view)
            s = stats[rule.name]
            s["lat"].append(time.perf_counter() - t0)
            s["requests"] += 1
            if authorized:
                s["danger" if not oracle_safe else "safe"] += 1
                s["harmful"] += allowed and not oracle_safe
                s["unneeded"] += (not allowed) and oracle_safe
            else:
                s["unauth"] += 1
                s["unauth_success"] += allowed
            decisions[rule.name] = allowed
        hist = any(t.target_id in historical for u in e.units for t in world.targets.targets_for_unit(u))
        for rule in rules:
            if authorized and not hist:
                s = stats[rule.name]
                s["danger_nh"] += not oracle_safe
                s["harmful_nh"] += decisions[rule.name] and not oracle_safe
        if record:
            rows.append(dict(id=e.request_id, t=e.t, p=e.principal, u=list(e.units[0]), auth=authorized,
                             oracle_safe=oracle_safe, historical=hist, decisions=decisions))
        release = (authorized and oracle_safe) if mode == "snapshot" else decisions[rules[0].name]
        if release:
            deliveries[e.principal].update(e.units)
            if state is not None:
                state.record_delivery(e.principal, e.units)
    end = _frozen({p: world.receipts[p] | deliveries[p] | untracked[p] for p in PRINCIPALS})
    external = reconstructable(world, _frozen({p: world.receipts[p] | untracked[p] for p in PRINCIPALS}), k)
    after = reconstructable(world, end, k)
    n_t = len(world.targets._by_id)
    out = {}
    for name, s in stats.items():
        lat = sorted(s.pop("lat"))
        o = dict(**s,
                 harmful_rate=s["harmful"] / s["danger"] if s["danger"] else None,
                 harmful_rate_nonhistorical=s["harmful_nh"] / s["danger_nh"] if s["danger_nh"] else None,
                 utility=1 - s["unneeded"] / s["safe"] if s["safe"] else None,
                 over_refusal=s["unneeded"] / s["safe"] if s["safe"] else None,
                 unauth_success_rate=s["unauth_success"] / s["unauth"] if s["unauth"] else 0.0,
                 p50_us=1e6 * lat[len(lat) // 2], p95_us=1e6 * lat[int(0.95 * (len(lat) - 1))],
                 historical_reconstructable=len(historical) / n_t,
                 external_reconstructable=len(external - historical) / n_t)
        if mode == "path":
            o["new_secret_reconstruction"] = len(after - external) / n_t
            o["coalition_violation"] = len(after - historical) / n_t
        out[name] = o
    return out, rows
