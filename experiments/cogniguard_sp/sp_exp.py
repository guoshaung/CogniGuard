"""Shadow-price experiment runner. Stages (PREREG.md):
  p0    LP strength + equivalence on dev states (A1 trajectories): LP(H) vs OPT, dual degeneracy, decision agreement
  p0b   headroom on dev: A1, A1_D, OPT_CANON_SERVE, OPT_CANON per regime
  test  P1 on test seeds (only if p0 and p0b gates pass; checked by the analyze step, not here)
  analyze
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from experiments.cogniguard_cgc4 import a_exp as AX
from experiments.cogniguard_cgc4.a_engine import Policy, check_safe
from experiments.cogniguard_cgc5.baselines import Baseline
from experiments.cogniguard_sp.sp import SPPolicy, solve_lp

OUT = Path(__file__).parent / "results"
GAMMA = 0.3
STATE_LIMIT = 1_500_000

# stress regimes (frozen in PREREG.md); added at runtime, CGC4 file untouched
AX.CONDS.setdefault("long", (24, 16, 2, 3, 12, 24, 1, True, 0.2, 0.5))
AX.CONDS.setdefault("tight_conflict", (24, 32, 2, 3, 12, 12, 1, True, 0.2, 0.9))
AX.CONDS.setdefault("k1_N3", (24, 16, 2, 3, 12, 12, 3, False, 0.2, 0.5))

ORIG = ["base", "tight", "overlap", "conflict", "ksl", "eedi"]
STRESS = ["long", "tight_conflict", "k1_N3"]
REGIMES = ORIG + STRESS


class TooBig(Exception):
    pass


def build(regime, key):
    if regime == "ksl":
        return AX.gen_ksl(key)
    if regime == "eedi":
        return AX.gen_eedi(key)
    return AX.gen_synth(key, regime)


def keys(regime, split):
    if regime == "ksl":
        return list(range(60)) if split == "dev" else [100000 + s for s in range(120)]
    if regime == "eedi":
        return list(range(0, 835, 2)) if split == "dev" else list(range(1, 835, 2))
    return list(range(40)) if split == "dev" else [100000 + s for s in range(60)]


def E_of(split):
    return 8 if split == "dev" else 20


def make(name, inst, q):
    if name == "A1":
        return Policy("A1", inst, q, gamma=GAMMA)
    if name in ("SP_LP", "SP_DISP", "SP_MYOPIC", "SP_D", "A1_D"):
        return SPPolicy(name, inst, q, gamma=GAMMA)
    kw = {"gamma": GAMMA}
    if name == "MPC_OPT":
        kw["d"] = 3                                       # CGC5 dev choice (frozen)
    return Baseline(name, inst, q, **kw)


def run(inst, name, q, seqs, seed):
    pol = make(name, inst, q)
    served, decs, unsafe = [], [], 0
    t0 = time.perf_counter()
    for e, seq in enumerate(seqs):
        state = inst.K0
        s, dec = 0, []
        rng = random.Random(hash((seed, e, 1)) & 0xFFFFFFFF)
        for t, ti in enumerate(seq):
            o = pol.act(t, state, ti, rng)
            dec.append(o)
            if o is not None:
                g = inst.group(inst.types[ti][0])
                st = list(state)
                st[g] |= o
                state = tuple(st)
                s += 1
            if len(getattr(pol, "_ocache", {})) + len(getattr(pol, "_mcache", {})) > STATE_LIMIT:
                raise TooBig
        served.append(s / inst.H)
        decs.append(dec)
        unsafe += not check_safe(inst, state)
    secs = time.perf_counter() - t0
    return {"completion": float(np.mean(served)), "per_episode": served, "unsafe": unsafe,
            "ms": 1000 * secs / max(1, pol.calls)}, decs


def traj_agree(inst, q, seqs, other):
    """Decision agreement with A1 on A1's own trajectory, multi-option states only (PREREG MERGE gate).
    SP_D is compared with A1_D (deferral variants), the others with A1."""
    ref = make("A1_D" if other == "SP_D" else "A1", inst, q)
    a1 = make("A1", inst, q)
    pol = make(other, inst, q)
    n = agree = 0
    for e, seq in enumerate(seqs):
        state = inst.K0
        rng = random.Random(e)
        for t, ti in enumerate(seq):
            g = inst.group(inst.types[ti][0])
            opts = [o for o in inst.types[ti][1] if inst.feasible(state[g], o)]
            if len(opts) > 1:
                n += 1
                agree += ref.act(t, state, ti, rng) == pol.act(t, state, ti, rng)
            o = a1.act(t, state, ti, rng)
            if o is not None:
                s2 = list(state)
                s2[g] |= o
                state = tuple(s2)
    return [agree, n]


def evaluate(args):
    regime, key, split, methods = args
    inst = build(regime, key)
    if inst is None:
        return None
    q = AX.q_variants(inst, key)["emp"]
    seqs = AX.sequences(inst, key, E_of(split), inst.q)
    res, decs = {}, {}
    for m in methods:
        if m.startswith("OPT_CANON") and inst.n > 30:
            res[m] = {"skipped": "n>30"}
            continue
        try:
            res[m], decs[m] = run(inst, m, q, seqs, key)
        except TooBig:
            res[m] = {"skipped": "state limit"}
    traj = {}
    for m in ("SP_LP", "OCOST", "SP_D"):
        if m in methods and "A1" in methods:
            traj[m] = traj_agree(inst, q, seqs, m)
    agree = {"traj_multi": traj}
    for m in methods:
        if m != "A1" and m in decs and "A1" in decs:
            a, b = decs["A1"], decs[m]
            agree[m] = sum(x == y for da, db in zip(a, b) for x, y in zip(da, db)) / sum(len(d) for d in a)
    return {"regime": regime, "key": key, "n": inst.n, "m": len(inst.W), "H": inst.H, "res": res, "agree_A1": agree}


# ------------------------------------------------------------------ P0: LP strength and equivalence
def p0_one(args):
    regime, key = args
    inst = build(regime, key)
    if inst is None:
        return None
    q = AX.q_variants(inst, key)["emp"]
    seqs = AX.sequences(inst, key, 4, inst.q)
    a1 = Policy("A1", inst, q, gamma=GAMMA)
    sp = SPPolicy("SP_LP", inst, q, gamma=GAMMA)
    oc = Baseline("OCOST", inst, q, gamma=GAMMA)
    disp = SPPolicy("SP_DISP", inst, q, gamma=GAMMA)
    ck0 = sp.canon.state_key(inst.K0)
    lp0 = solve_lp(inst, ck0, [inst.H * p for p in q])[0]
    opt0 = None
    if inst.n <= 30:
        try:
            ob = Baseline("OPT_CANON_SERVE", inst, q)
            opt0 = ob._opt_c(ck0, inst.H, False)
            if len(ob._ocache) > STATE_LIMIT:
                opt0 = None
        except RecursionError:
            opt0 = None
    st = {"states": 0, "degenerate": 0, "multi": 0, "agree_A1": 0, "agree_OCOST": 0, "agree_DISP": 0, "lp_ge_alive": 0}
    for e, seq in enumerate(seqs):
        state = inst.K0
        rng = random.Random(e)
        for t, ti in enumerate(seq):
            g = inst.group(inst.types[ti][0])
            opts = [o for o in inst.types[ti][1] if inst.feasible(state[g], o)]
            if not opts:
                continue
            rem = inst.H - t - 1
            ck = sp.canon.state_key(state)
            nvec = [rem * p for p in q]
            val, lam, _, _ = sp.lp(ck, ("h", rem), nvec)
            if rem > 0:
                st["states"] += 1
                st["degenerate"] += all(v < 1e-6 for v in lam.values())
                alive_demand = sum(nvec[t2] for t2, (a2, o2) in enumerate(inst.types)
                                   if any(not any(r & ~o == 0 for r in ck[inst.group(a2)]) for o in o2))
                st["lp_ge_alive"] += bool(val >= alive_demand - 1e-6)
                if len(opts) > 1:
                    st["multi"] += 1
                    o_a1 = a1.act(t, state, ti, rng)
                    o_sp = sp.act(t, state, ti, rng)
                    st["agree_A1"] += o_a1 == o_sp
                    st["agree_OCOST"] += oc.act(t, state, ti, rng) == o_sp
                    st["agree_DISP"] += disp.act(t, state, ti, rng) == o_sp
            o = a1.act(t, state, ti, rng)
            s2 = list(state)
            s2[g] |= o
            state = tuple(s2)
    return {"regime": regime, "key": key, "lp0": float(lp0), "opt0": None if opt0 is None else float(opt0), "H": inst.H, **{k: int(v) for k, v in st.items()}}


def p0():
    jobs = [(r, k) for r in REGIMES for k in keys(r, "dev")]
    with Pool(6) as pool:
        rows = [x for x in pool.imap_unordered(p0_one, jobs, chunksize=2) if x]
    out = {}
    for r in REGIMES + ["ALL"]:
        rr = [x for x in rows if r == "ALL" or x["regime"] == r]
        S = sum(x["states"] for x in rr)
        M = sum(x["multi"] for x in rr)
        ratio = [x["lp0"] / x["opt0"] for x in rr if x["opt0"]]
        out[r] = {"instances": len(rr), "states": S, "degenerate_frac": sum(x["degenerate"] for x in rr) / max(1, S),
                  "lp_ge_all_alive_demand_frac": sum(x["lp_ge_alive"] for x in rr) / max(1, S),
                  "multi_option_states": M,
                  "agree_SP_vs_A1": sum(x["agree_A1"] for x in rr) / max(1, M),
                  "agree_SP_vs_OCOST": sum(x["agree_OCOST"] for x in rr) / max(1, M),
                  "agree_SP_vs_DISP": sum(x["agree_DISP"] for x in rr) / max(1, M),
                  "LP_over_OPT_t0_mean": float(np.mean(ratio)) if ratio else None,
                  "LP_over_OPT_t0_max": float(np.max(ratio)) if ratio else None, "n_opt": len(ratio)}
    g = out["ALL"]
    out["gate_P0"] = {
        "lp_degenerate_stop": g["degenerate_frac"] >= 0.8 and g["lp_ge_all_alive_demand_frac"] >= 0.8,
        "equiv_A1_stop": g["agree_SP_vs_A1"] == 1.0, "equiv_OCOST_stop": g["agree_SP_vs_OCOST"] == 1.0}
    out["gate_P0"]["pass"] = not any(out["gate_P0"].values())
    (OUT / "p0.json").write_text(json.dumps(out, indent=1) + "\n")
    with gzip.open(OUT / "p0_rows.json.gz", "wt") as h:
        json.dump(rows, h)
    print(json.dumps(out, indent=1))


# ------------------------------------------------------------------ P0b headroom (dev)
HEAD = ["A1", "A1_D", "OPT_CANON_SERVE", "OPT_CANON"]


def p0b():
    jobs = [(r, k, "dev", HEAD) for r in REGIMES for k in keys(r, "dev")]
    with Pool(6) as pool:
        rows = [x for x in pool.imap_unordered(evaluate, jobs, chunksize=1) if x]
    with gzip.open(OUT / "p0b_rows.json.gz", "wt") as h:
        json.dump([{k: v for k, v in x.items()} for x in rows], h)
    out = {}
    for r in REGIMES:
        rr = [x for x in rows if x["regime"] == r and "completion" in x["res"].get("OPT_CANON_SERVE", {})
              and "completion" in x["res"].get("OPT_CANON", {})]
        if not rr:
            out[r] = {"n": 0}
            continue
        c = lambda m: float(np.mean([x["res"][m]["completion"] for x in rr]))
        out[r] = {"n": len(rr), "n_total": sum(1 for x in rows if x["regime"] == r),
                  "A1": c("A1"), "A1_D": c("A1_D"), "OPT_SERVE": c("OPT_CANON_SERVE"), "OPT": c("OPT_CANON"),
                  "head_serve_pp": 100 * (c("OPT_CANON_SERVE") - c("A1")), "head_defer_pp": 100 * (c("OPT_CANON") - c("A1_D"))}
    gs = [r for r in REGIMES if out[r].get("head_serve_pp", -1) >= 1.0]
    gd = [r for r in REGIMES if out[r].get("head_defer_pp", -1) >= 1.0]
    out["gate_P0b"] = {"serve_regimes_ge_1pp": gs, "defer_regimes_ge_1pp": gd,
                       "run_SP_serve": bool(gs), "run_SP_defer": bool(gd)}
    (OUT / "p0b.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


# ------------------------------------------------------------------ P1 test
def test():
    g = json.loads((OUT / "p0.json").read_text())["gate_P0"]
    h = json.loads((OUT / "p0b.json").read_text())["gate_P0b"]
    assert g["pass"] and (h["run_SP_serve"] or h["run_SP_defer"]), "gates not passed: no P1"
    methods = ["A1", "OCOST", "SP_LP", "SP_DISP", "SP_MYOPIC"]
    if h["run_SP_defer"]:
        methods += ["A1_D", "SP_D"]
    jobs = []
    for r in REGIMES:
        ms = methods + (["MPC_OPT", "OPT_CANON_SERVE", "OPT_CANON"] if r in STRESS else [])
        jobs += [(r, k, "test", ms) for k in keys(r, "test")]
    with Pool(6) as pool:
        rows = [x for x in pool.imap_unordered(evaluate, jobs, chunksize=1) if x]
    with gzip.open(OUT / "test_rows.json.gz", "wt") as f:
        json.dump(rows, f)
    print(len(rows))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["p0", "p0b", "test"])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    {"p0": p0, "p0b": p0b, "test": test}[a.stage]()
