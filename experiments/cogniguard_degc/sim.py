"""DEGC controlled simulation (stage B'): fresh random worlds, k = 1, 2, 3, correlated detector misses.

Not real data. Worlds are generated from a fixed seed; the calibrator is fitted on DEV worlds (seeds
0..199) and every arm is evaluated on separate TEST worlds (seeds 1000..1399), so nothing is tuned on the
test worlds. Every arm sees the same observations, calibrator, verifier and budget.

World: 4 principals P0..P3 (each request comes from one of them); 12 units; 2 witness sets of size 3;
each principal starts with 0-2 trusted units (never a full witness for any coalition of size k). T = 10
requests; each answer discloses 1-2 units (witness units over-represented). A fraction of units are
"bridge" units (join keys): the detector misses them with probability m_b (correlated across answers:
one latent miss per (unit, principal) with prob rho, else independent), distinct units with prob 0.05;
false positive rate 0.01. Verifier accuracy acc (symmetric).
Metrics: new reconstruction (coalition of size <= k, true state, at the end), answer refusal rate on
answers that the oracle gate would release (over-refusal), verification calls.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path

from cogniguard.governance import degc as _degc
from cogniguard.governance.degc import (BetaCalibrator, DegcConfig, DegcPolicy, KnowledgeBelief, Obs,
                                        reconstruction_risk, state_unsafe)
from cogniguard.governance.reconstruction import check_release
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry

P = ["P0", "P1", "P2", "P3"]
OUT = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/degc/sim")


def world(seed, k, m_b=0.4, rho=0.5, acc=0.95, bridge_frac=0.4):
    rng = random.Random(seed)
    units = [f"u{i}" for i in range(12)]
    w = rng.sample(units, 6)
    wits = [w[:3], w[3:]]
    bridge = {u for u in units if rng.random() < bridge_frac}
    while True:
        init = {p: set(rng.sample(units, rng.randint(0, 2))) for p in P}
        know = {p: {("s", u) for u in v} for p, v in init.items()}
        reg = TargetRegistry([ProtectedTarget("t", "o", "org", tuple(frozenset(("s", u) for u in x) for x in wits))])
        if not any(state_unsafe(reg, p, know, k) for p in P):
            break
    latent = {(p, u): rng.random() < rho for p in P for u in units}
    latent_miss = {(p, u): rng.random() < m_b for p in P for u in units}
    reqs = []
    wit_units = set(w)
    for t in range(10):
        p = rng.choice(P)
        n = rng.choice((1, 2))
        pool = list(wit_units) * 2 + units
        disc = set()
        while len(disc) < n:
            disc.add(rng.choice(pool))
        obs = {}
        for u in units:
            true = u in disc
            if true:
                miss_p = m_b if u in bridge else 0.05
                miss = latent_miss[(p, u)] if (u in bridge and latent[(p, u)]) else rng.random() < miss_p
                hit = not miss
            else:
                hit = rng.random() < 0.01
            score = rng.random()
            obs[u] = {"hit": hit, "bridge": u in bridge, "conf": (0.5 + 0.5 * score) if hit else 0.5 * score, "true": true,
                      "ver": true if rng.random() < acc else not true}
        reqs.append({"p": p, "obs": obs})
    return {"reg": reg, "init": init, "reqs": reqs, "units": units, "wits": wits}


def binner(f):
    return (("hit" if f["hit"] else "miss"), "bridge" if f["bridge"] else "distinct", int(f["conf"] * 4))


def vbinner(f):
    return ("ver", f["ver"], "bridge" if f["bridge"] else "distinct")


def fit(k, **kw):
    rows, vrows = [], []
    for s in range(200):
        W = world(s, k, **kw)
        for r in W["reqs"]:
            for u, f in r["obs"].items():
                rows.append((f, f["true"]))
                vrows.append((f, f["true"]))
    return BetaCalibrator(binner).fit(rows), BetaCalibrator(vbinner).fit(vrows)


def play(W, arm, c, k, cal, vcal, rng):
    reg = W["reg"]
    belief = KnowledgeBelief(c.get("combine", "noisy_or"))
    for p in P:
        belief.add_trusted(p, {("s", u) for u in W["init"][p]})
    true_know = {p: {("s", u) for u in W["init"][p]} for p in P}
    det_know = {p: {("s", u) for u in W["init"][p]} for p in P}
    calls, refused, oracle_ok_refused, oracle_ok = 0, 0, 0, 0
    vmemo = {}

    def vout(o):
        f = o.feats["f"]
        return vcal.posterior(f)

    pol = None
    if arm in ("Ours", "B2", "B3", "EC2", "HZ", "B2h"):
        pol = DegcPolicy(reg, DegcConfig(delta=c.get("delta", .1), use_leakage=arm != "B3", use_epistemic=arm not in ("B2", "B2h"),
                                         per_request_cap=c.get("cap", 0), k=k, selector="ec2" if arm == "EC2" else "eig",
                                         trigger="entropy" if arm == "HZ" else "interval", eta=c.get("eta", .5)), verify=vout)
    history = []
    for t, r in enumerate(W["reqs"]):
        p = r["p"]
        true_units = {("s", u) for u, f in r["obs"].items() if f["true"]}
        # oracle gate: true state, true units
        o_ok = not true_units or check_release(reg, p, true_units, {q: frozenset(v) for q, v in true_know.items()}, k).safe
        pend = []
        for u, f in r["obs"].items():
            q, lo, hi = cal.posterior(f)
            pend.append(Obs(f"{t}|{u}", p, ("s", u), q, lo, hi, {"f": f}))
        if pol is not None:
            before = pol.calls
            dec_pend = [o for o in pend if reg.targets_for_unit(o.unit) or arm == "B3"]
            if arm == "B2h":   # current answer deterministic (detector hit), history calibrated
                dec_pend = [Obs(o.obs_id, o.principal, o.unit, *(3 * (float(o.feats["f"]["hit"]),)), o.feats) for o in dec_pend]
            d = pol.decide(p, belief, dec_pend)
            calls += pol.calls - before
            allow = d.allowed
            if allow:
                for o in pend:
                    belief.add_obs(o)
        elif arm == "B7":
            allow, n = voi(reg, belief, pend, p, k, c, vout)
            calls += n
            if allow:
                for o in pend:
                    belief.add_obs(o)
        else:
            if arm == "Oracle":
                units = true_units
                know = true_know
            else:
                units = {("s", u) for u, f in r["obs"].items() if f["hit"]}
                if arm == "OCL":
                    units = {o.unit for o in pend if o.p > c["tau"]}
                ver = {}
                cap = c.get("cap", 0)
                if arm == "B4":
                    pool = [(tt, u) for tt in range(t + 1) for u in W["units"] if (tt, u) not in vmemo]
                    for key in rng.sample(pool, min(cap, len(pool))):
                        vmemo[key] = W["reqs"][key[0]]["obs"][key[1]]["ver"]
                        calls += 1
                elif arm == "B6":
                    held = {u for _, u in det_know[p]}
                    def risk(u):
                        rem = [len(set(w) - held - {u}) for w in W["wits"] if u in w and u not in held]
                        return (0, min(rem), -r["obs"][u]["conf"]) if rem else (1, 0, 0)
                    for u in sorted(W["units"], key=risk)[:cap]:
                        vmemo[(t, u)] = r["obs"][u]["ver"]
                        calls += 1
                elif arm == "B8":
                    for u in W["units"]:
                        vmemo[(t, u)] = r["obs"][u]["ver"]
                        calls += 1
                if arm in ("B4", "B6", "B8"):
                    units = {("s", u) for u in W["units"] if vmemo.get((t, u), ("s", u) in units)}
                    # repair history
                    for p2 in P:
                        det_know[p2] = {("s", u) for u in W["init"][p2]}
                    for (tt, pp, uu) in history:
                        if vmemo.get((tt, uu[1]), True):
                            det_know[pp].add(uu)
                know = det_know
            allow = not units or check_release(reg, p, units, {q: frozenset(v) for q, v in know.items()}, k).safe
            if allow and arm != "Oracle":
                for u in units:
                    det_know[p].add(u)
                    history.append((t, p, u))
        if not allow:
            refused += 1
            oracle_ok_refused += o_ok
        oracle_ok += o_ok
        if allow:
            true_know[p] |= true_units
    leak = any(state_unsafe(reg, q, true_know, k) for q in P)
    return {"leak": leak, "calls": calls, "refused": refused, "over_refusal": oracle_ok_refused / max(1, oracle_ok)}


def voi(reg, belief, pend, p, k, c, vout):
    lam, cap, cost = c["delta"], c.get("cap", 0), c.get("vcost", 0.0)
    rel = [o for o in pend if reg.targets_for_unit(o.unit)]
    R0 = reconstruction_risk(reg, belief, p, k)
    risk = lambda: reconstruction_risk(reg, belief, p, k, rel) - R0
    loss = lambda d: min(d, lam)
    n = 0
    while n < cap:
        dR = risk()
        best, bv = None, max(cost, 1e-9)
        for o in [x for x in list(belief.obs.values()) + rel if not x.verified and 0 < x.p < 1 and reg.targets_for_unit(x.unit)]:
            sp = o.p
            o.p = 1.0
            d1 = risk()
            o.p = 0.0
            d0 = risk()
            o.p = sp
            v = loss(dR) - (sp * loss(d1) + (1 - sp) * loss(d0))
            if v > bv:
                best, bv = o, v
        if best is None:
            break
        best.p, best.lo, best.hi = vout(best)
        best.verified = True
        n += 1
    return risk() <= lam, n


def configs_lite():
    yield "B1", {}
    yield "Oracle", {}
    yield "B8", {}
    yield "OCL", {"tau": 0.05}
    for d in (0.05, 0.1):
        yield "B2", {"delta": d}
        yield "Ours", {"delta": d, "cap": 1}
        yield "Ours", {"delta": d, "cap": 2}
        yield "EC2", {"delta": d, "cap": 1}
        yield "B7", {"delta": d, "cap": 1, "vcost": 0.0}
        yield "B7", {"delta": d, "cap": 1, "vcost": 0.01}
    yield "B3", {"cap": 1, "delta": .1}
    yield "B4", {"cap": 1}
    yield "B6", {"cap": 1}


def configs():
    yield "B1", {}
    yield "Oracle", {}
    yield "B8", {}
    for t in (0.05, 0.2):
        yield "OCL", {"tau": t}
    for d in (0.02, 0.05, 0.1, 0.2):
        yield "B2", {"delta": d}
    for cap in (1, 2):
        yield "B3", {"cap": cap, "delta": .1}
        yield "B4", {"cap": cap}
        yield "B6", {"cap": cap}
        for d in (0.02, 0.05, 0.1, 0.2):
            yield "Ours", {"delta": d, "cap": cap}
            yield "EC2", {"delta": d, "cap": cap}
            yield "HZ", {"delta": d, "cap": cap, "eta": .6}
            for v in (0.0, 0.01):
                yield "B7", {"delta": d, "cap": cap, "vcost": v}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--worlds", type=int, default=400)
    ap.add_argument("--m_b", type=float, default=0.4)
    ap.add_argument("--rho", type=float, default=0.5)
    ap.add_argument("--acc", type=float, default=0.95)
    ap.add_argument("--tag", default="main")
    ap.add_argument("--arms", nargs="*", default=None)
    ap.add_argument("--mc", type=int, default=256)
    ap.add_argument("--lite", action="store_true")
    a = ap.parse_args()
    _degc.MC.update(samples=a.mc, prune=0.005)  # simulation only: Monte Carlo SE ~0.01 at R = 0.02
    OUT.mkdir(parents=True, exist_ok=True)
    res = []
    for k in a.k:
        kw = {"m_b": a.m_b, "rho": a.rho, "acc": a.acc}
        cal, vcal = fit(k, **kw)
        worlds = [world(1000 + s, k, **kw) for s in range(a.worlds)]
        for arm, c in (configs_lite() if a.lite else configs()):
            if a.arms and arm not in a.arms:
                continue
            rng = random.Random(7)
            per = [play(W, arm, c, k, cal, vcal, rng) for W in worlds]
            row = {"k": k, "arm": arm, "config": c, **kw,
                   "leak_rate": statistics.mean(x["leak"] for x in per),
                   "over_refusal": statistics.mean(x["over_refusal"] for x in per),
                   "calls_per_world": statistics.mean(x["calls"] for x in per),
                   "per_world": [[int(x["leak"]), round(x["over_refusal"], 4), x["calls"]] for x in per]}
            res.append(row)
            print(k, arm, c, round(row["leak_rate"], 3), round(row["over_refusal"], 3), round(row["calls_per_world"], 2), flush=True)
    (OUT / f"sim_{a.tag}.json").write_text(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
