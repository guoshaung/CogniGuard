"""Experiment 1 (exact): how much attacker guessing power exists before any complete witness is covered.

(a) Static: every view mask x every true world, prior-weighted.
(b) Trajectories: single agent over multiple rounds, and N agents with coalition size k = 1 and k = N (grand
    coalition). Units are released one at a time in random order with no gate; we record when CA-PD would
    first fire versus when the partial-leak threshold V1 >= tau is first crossed.
"""

from __future__ import annotations

import itertools
import json
import random
from pathlib import Path

import numpy as np

from experiments.cogniguard_ksl import engine, structures as S

OUT = Path(__file__).parent / "results"
TAUS = (0.25, 0.5)


def static(T):
    M = len(T.V1)
    pri = T.prior_V1()
    nonw = [k for k in range(M) if not T.cov[k] and k & T.relevant]
    w = T.prior
    v = T.V1[nonw]                         # (masks, worlds)
    lk = np.log2(v / pri)                  # realized min-entropy leakage, bits
    out = {"prior_V1": pri, "n_worlds": len(T.st.worlds), "n_secrets": len(T.svals), "n_units": len(T.units),
           "witnesses": [T.names(x) for x in T.witnesses], "n_noncovering_views": len(nonw),
           "max_V1_without_witness": float(v.max()),
           "mean_V1_without_witness": float((v @ w).mean()),
           "frac_views_any_leak": float(np.mean((v @ w) > pri + 1e-12)),
           "realized_determination_without_witness": float(np.mean(T.det[nonw] @ w)),
           "max_leak_bits_without_witness": float(lk.max()),
           "max_shannon_drop_without_witness": float(T.H[0, 0] - T.H[nonw].min())}
    for t in TAUS:
        out[f"frac_view_world_V1_ge_{t}"] = float(np.mean((v >= t - 1e-12) @ w))
    for b in (1, 2):
        out[f"frac_view_world_leak_ge_{b}bit"] = float(np.mean((lk >= b - 1e-9) @ w))
    # same witness verdict, different guessing power: spread among non-covering views (prior-averaged)
    ev = v @ w
    out["noncovering_expected_V1_range"] = [float(ev.min()), float(ev.max())]
    kx = nonw[int(np.argmax(ev))]
    out["most_leaky_noncovering_view"] = T.names(kx)
    return out


def trajectories(T, n_agents, k, reps=2000, seed=0, tau=0.5):
    rng = random.Random(seed)
    rel = [u for u in T.units if T.bit(u) & T.relevant]
    res = {"cross_before_witness": 0, "witness_reached": 0, "cross_reached": 0, "lead_steps": [],
           "steps_in_partial_zone": 0, "steps": 0, "realized_det_before_witness": 0}
    for _ in range(reps):
        x = rng.choices(range(len(T.st.worlds)), weights=T.prior)[0]
        seq = [(rng.randrange(n_agents), u) for u in rng.sample(rel, len(rel))] * 1
        know = [0] * n_agents
        t_cross = t_cov = t_det = None
        for step, (a, u) in enumerate(seq):
            know[a] |= T.bit(u)
            coal = [c for r in range(1, k + 1) for c in itertools.combinations(range(n_agents), r) if a in c]
            masks = [int(np.bitwise_or.reduce([know[i] for i in c])) for c in coal]
            v = max(T.V1[m, x] for m in masks)
            cov = any(T.cov[m] for m in masks)
            det = max(T.det[m, x] for m in masks)
            res["steps"] += 1
            if v >= tau and not cov:
                res["steps_in_partial_zone"] += 1
            if t_cross is None and v >= tau:
                t_cross = step
            if t_det is None and det:
                t_det = step
            if t_cov is None and cov:
                t_cov = step
        if t_cov is not None:
            res["witness_reached"] += 1
        if t_cross is not None:
            res["cross_reached"] += 1
        if t_cross is not None and (t_cov is None or t_cross < t_cov):
            res["cross_before_witness"] += 1
            res["lead_steps"].append((t_cov if t_cov is not None else len(seq)) - t_cross)
        if t_det is not None and (t_cov is None or t_det < t_cov):
            res["realized_det_before_witness"] += 1
    L = res.pop("lead_steps")
    res["mean_lead_steps"] = float(np.mean(L)) if L else 0.0
    for key in ("cross_before_witness", "witness_reached", "cross_reached", "realized_det_before_witness"):
        res[key] /= reps
    res["partial_zone_step_share"] = res.pop("steps_in_partial_zone") / res.pop("steps")
    return res


def main():
    OUT.mkdir(exist_ok=True)
    out = {}
    for st in S.all_structures():
        T = engine.build(st)
        out[st.name] = {"static": static(T), "traj": {}}
        for n, k in ((1, 1), (3, 1), (3, 2), (3, 3), (5, 5)):
            for tau in TAUS:
                out[st.name]["traj"][f"N={n},k={k},tau={tau}"] = trajectories(T, n, k, tau=tau, reps=1000)
        print(st.name, json.dumps({k: v for k, v in out[st.name]["static"].items() if "frac" in k or "max_V1" in k}))
    (OUT / "partial.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
