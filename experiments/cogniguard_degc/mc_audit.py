"""Monte Carlo error and knowledge-unit correlation for coalition risk (k = 2, 3), controlled simulation.

(1) MC error: collect decision states from probabilistic (B2-style, zero-verification) replays on test
worlds; for each, estimate R with N in {64, 128, 256, 1024} samples x 5 seeds and compare with a reference
estimate of 16,384 samples (exact enumeration when <= 12 uncertain variables). Report bias, SD and the
probability that the MC decision (dR > delta) differs from the reference decision.
(2) Correlation: detector misses of bridge units correlated with rho in {0, 0.9}; belief combination
noisy-OR (independence) vs max (comonotone); arms L1-style deterministic calibrated MAP and B2.
"""

from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

from cogniguard.governance import degc as G
from cogniguard.governance.degc import KnowledgeBelief, Obs, reconstruction_risk
from experiments.cogniguard_degc import sim as S

OUT = Path(__file__).parent / "results" / "mc_audit.json"


def collect_states(k, n_worlds=12, delta=0.05):
    cal, _ = S.fit(k)
    states = []
    G.MC.update(samples=1024, prune=1e-6)
    for s in range(n_worlds):
        W = S.world(2000 + s, k)
        b = KnowledgeBelief()
        for p in S.P:
            b.add_trusted(p, {("s", u) for u in W["init"][p]})
        for t, r in enumerate(W["reqs"]):
            pend = [Obs(f"{t}|{u}", r["p"], ("s", u), *cal.posterior(f), {}) for u, f in r["obs"].items()
                    if W["reg"].targets_for_unit(("s", u))]
            states.append((W["reg"], b, r["p"], list(pend)))
            R0 = reconstruction_risk(W["reg"], b, r["p"], k)
            R = reconstruction_risk(W["reg"], b, r["p"], k, pend)
            if R - R0 <= delta:
                for o in pend:
                    b.add_obs(o)
            # snapshot belief (copy) for later re-evaluation
            nb = KnowledgeBelief()
            nb.trusted = {p: set(v) for p, v in b.trusted.items()}
            nb.obs = dict(b.obs)
            states[-1] = (W["reg"], nb, r["p"], list(pend))
    return states


def mc_error(k, delta=0.05):
    states = collect_states(k)
    out = {}
    refs = []
    for reg, b, p, pend in states:
        G.MC.update(prune=1e-6)
        r1 = reconstruction_risk(reg, b, p, k, pend, samples=16384, seed=99)
        r0 = reconstruction_risk(reg, b, p, k, (), samples=16384, seed=98)
        refs.append((r1, r0))
    for N in (64, 128, 256, 1024):
        for prune in (1e-6, 0.005):
            G.MC.update(prune=prune)
            errs, flips, sds = [], [], []
            for (reg, b, p, pend), (r1, r0) in zip(states, refs):
                est = [reconstruction_risk(reg, b, p, k, pend, samples=N, seed=s) - reconstruction_risk(reg, b, p, k, (), samples=N, seed=100 + s)
                       for s in range(5)]
                ref = r1 - r0
                errs += [e - ref for e in est]
                sds.append(statistics.pstdev(est))
                flips += [int((e > delta) != (ref > delta)) for e in est]
            out[f"N={N} prune={prune}"] = {"bias": statistics.mean(errs), "rmse": statistics.mean(e * e for e in errs) ** .5,
                                           "mean_sd": statistics.mean(sds), "decision_flip_rate": statistics.mean(flips),
                                           "states": len(states)}
            print(k, N, prune, out[f"N={N} prune={prune}"], flush=True)
    G.MC.update(samples=1024, prune=1e-6)
    return out


def correlation(k, n_worlds):
    G.MC.update(samples=256, prune=0.005)
    out = {}
    for rho in (0.0, 0.9):
        cal, vcal = S.fit(k, rho=rho)
        worlds = [S.world(3000 + s, k, rho=rho) for s in range(n_worlds)]
        for arm, c in (("B1", {}), ("B2", {"delta": 0.05, "combine": "noisy_or"}), ("B2", {"delta": 0.05, "combine": "max"})):
            per = [S.play(W, arm, c, k, cal, vcal, random.Random(0)) for W in worlds]
            key = f"rho={rho} {arm} {c.get('combine', '')}".strip()
            out[key] = {"leak": statistics.mean(x["leak"] for x in per), "over_refusal": statistics.mean(x["over_refusal"] for x in per)}
            print(k, key, out[key], flush=True)
    return out


def main():
    res = {"mc_error": {}, "correlation": {}}
    for k in (2, 3):
        res["mc_error"][k] = mc_error(k)
    for k, n in ((1, 200), (2, 60), (3, 60)):
        res["correlation"][k] = correlation(k, n)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1) + "\n")


if __name__ == "__main__":
    main()
