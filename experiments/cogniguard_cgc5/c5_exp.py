"""CGC5 runner: A1 (frozen CGC4) vs strong baselines on the CGC4 Task A instances.

Two passes per method and instance: a timing pass (no tracemalloc) over all episodes, and a memory pass with
tracemalloc over the first 3 episodes. Decisions of A1 and A1_FULL are logged step by step to verify that the
incremental update makes exactly the same decisions."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import random
import time
import tracemalloc
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from experiments.cogniguard_cgc4 import a_exp as AX
from experiments.cogniguard_cgc4.a_engine import Policy, check_safe, popcount
from experiments.cogniguard_cgc5.baselines import Baseline

OUT = Path(__file__).parent / "results"
DATA = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data")
GAMMA = 0.3          # CGC4 dev choice for A1 (frozen)
STATE_LIMIT = 1_500_000


class TooBig(Exception):
    pass


def build(kind, key):
    if kind == "synth":
        return AX.gen_synth(key[0], key[1])
    if kind == "ksl":
        inst = AX.gen_ksl(key[0])
        if inst is None:
            return None
        from experiments.cogniguard_cgc3.cand_a import make_instance
        Ls = make_instance(inst.meta["name"], key[0], 0.5)["Ls"]
        inst.leak = lambda K, Ls=Ls: float(Ls[K])
        return inst
    if kind == "eedi":
        inst = AX.gen_eedi(key[0])
        if inst is None:
            return None
        w = json.loads((DATA / "eedi_exam/witness_sets.jsonl").read_text().splitlines()[key[0]])
        tgt = {json.loads(l)["target_id"]: json.loads(l) for l in (DATA / "eedi_exam/targets.jsonl").read_text().splitlines()}[w["target_id"]]
        sup = {}
        for l in (DATA / "eedi_exam/units.jsonl").read_text().splitlines():
            r = json.loads(l)
            if r["target_id"] == w["target_id"]:
                sup[r["unit_id"]] = set(r["satisfied_by"])
        uni = w["universe"]
        dom = set(tgt["domain"])

        def leak(K, uni=uni, sup=sup, dom=dom):
            s = set(dom)
            for i, u in enumerate(uni):
                if K >> i & 1:
                    s &= sup[u]
            return math.log2(len(dom) / max(1, len(s)))
        inst.leak = leak
        return inst
    if kind == "sumleaks":
        return AX.gen_sumleaks(key[0])
    raise ValueError(kind)


def make_policy(name, inst, q, ch):
    if name == "A1":
        return Policy("A1", inst, q, gamma=GAMMA)                  # unchanged CGC4 implementation
    kw = {"gamma": GAMMA}
    if name.startswith("OCELOT_P"):
        kw["budget"] = math.inf if name == "OCELOT_P" else None
    if name == "PFLOW_P":
        kw["rho"] = ch.get("rho", 1.01)
    if name == "DYNCQE_P":
        kw["samples"], kw["seed"] = 256, 0
    if name == "MPC_OPT":
        kw["d"] = ch.get("mpc_d", 3)
    return Baseline(name, inst, q, **kw)


def run_method(inst, name, q, seqs, seed, ch, budget=None):
    pol = make_policy(name, inst, q, ch)
    if budget is not None:
        pol.kw["budget"] = budget
    served, decisions, unsafe, leak = [], [], 0, []
    t0 = time.perf_counter()
    try:
        for e, seq in enumerate(seqs):
            if hasattr(pol, "reset_episode"):
                pol.reset_episode()
            state = inst.K0
            dec = []
            s = 0
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
                if hasattr(pol, "_ocache") and len(pol._ocache) + len(getattr(pol, "_mcache", {})) > STATE_LIMIT:
                    raise TooBig
            served.append(s / inst.H)
            decisions.append(dec)
            unsafe += not check_safe(inst, state)
            if hasattr(inst, "leak"):
                leak.append(inst.leak(state[0]))
    except TooBig:
        return {"skipped": "state limit"}, None
    secs = time.perf_counter() - t0
    # memory pass on a fresh policy object
    pol2 = make_policy(name, inst, q, ch)
    if budget is not None:
        pol2.kw["budget"] = budget
    tracemalloc.start()
    try:
        for e, seq in enumerate(seqs[:3]):
            if hasattr(pol2, "reset_episode"):
                pol2.reset_episode()
            state = inst.K0
            rng = random.Random(hash((seed, e, 1)) & 0xFFFFFFFF)
            for t, ti in enumerate(seq):
                o = pol2.act(t, state, ti, rng)
                if o is not None:
                    g = inst.group(inst.types[ti][0])
                    st = list(state)
                    st[g] |= o
                    state = tuple(st)
    finally:
        mem = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
    cache = len(getattr(pol, "_mcache", {})) + len(getattr(pol, "_ocache", {})) + len(pol.eng.alive_cache)
    extra = {"censor_mode": getattr(pol, "censor_mode", None), "n_censors": len(getattr(pol, "censors", []) or [])}
    return {"completion": float(np.mean(served)), "per_episode": served, "unsafe_episodes": unsafe,
            "ms_per_decision": 1000 * secs / max(1, pol.calls), "peak_mem_kb": mem / 1024, "cache_entries": cache,
            "final_leak": float(np.mean(leak)) if leak else None, **extra}, decisions


METHODS = ["A1", "A1_FULL", "OCELOT_P", "PFLOW_P", "DYNCQE_P", "OCOST", "MPC_OPT", "OPT_CANON_SERVE", "OPT_CANON"]


def evaluate(args):
    kind, key, E, ch, methods = args
    inst = build(kind, key)
    if inst is None:
        return None
    seed = key[0]
    q = AX.q_variants(inst, seed)["emp"]                     # every method gets the same history estimate
    seqs = AX.sequences(inst, seed, E, inst.q)
    res, decs = {}, {}
    for m in methods:
        if m.startswith("OPT_CANON") and inst.n > 30:
            res[m] = {"skipped": "too large"}
            continue
        r, d = run_method(inst, m, q, seqs, seed, ch)
        res[m] = r
        decs[m] = d
    # OCELOT with a strict budget: 80% of what the unbudgeted proxy spends on average (same instance)
    if "OCELOT_P" in methods and hasattr(inst, "leak"):
        tau_like = max(inst.leak((1 << inst.n) - 1), 1e-9)
        r, _ = run_method(inst, "OCELOT_P", q, seqs, seed, ch, budget=0.8 * tau_like)
        res["OCELOT_P|B=0.8max"] = r
    agree = None
    if decs.get("A1") and decs.get("A1_FULL"):
        a, b = decs["A1"], decs["A1_FULL"]
        agree = sum(x == y for da, db in zip(a, b) for x, y in zip(da, db)) / sum(len(d) for d in a)
    return {"kind": kind, "key": list(key), "n": inst.n, "m": len(inst.W), "P": len(inst.types), "H": inst.H,
            "N": inst.N, "pooled": inst.pooled, "meta": inst.meta, "res": res, "a1_full_agreement": agree}


def dev():
    jobs = []
    for c in ("base", "small", "conflict"):
        jobs += [("synth", (s, c), 8, {}, ["A1"]) for s in range(40)]
    rows = []
    grid_rho = [1.01, 0.99, 0.75, 0.67]
    grid_d = [2, 3, 4]
    out = {}
    with Pool(9) as pool:
        for rho in grid_rho:
            r = [x for x in pool.imap_unordered(evaluate, [(k, key, E, {"rho": rho}, ["PFLOW_P"]) for k, key, E, _, _ in jobs]) if x]
            out[f"rho={rho}"] = float(np.mean([x["res"]["PFLOW_P"]["completion"] for x in r]))
        for d in grid_d:
            r = [x for x in pool.imap_unordered(evaluate, [(k, key, E, {"mpc_d": d}, ["MPC_OPT"]) for k, key, E, _, _ in jobs]) if x]
            out[f"mpc_d={d}"] = {"completion": float(np.mean([x["res"]["MPC_OPT"]["completion"] for x in r])),
                                 "ms": float(np.mean([x["res"]["MPC_OPT"]["ms_per_decision"] for x in r]))}
    rho = max(grid_rho, key=lambda v: out[f"rho={v}"])
    # MPC depth: best completion; ties (within 0.001) broken by lower cost
    best = max(out[f"mpc_d={d}"]["completion"] for d in grid_d)
    d = min([d for d in grid_d if out[f"mpc_d={d}"]["completion"] >= best - 0.001], key=lambda d: out[f"mpc_d={d}"]["ms"])
    ch = {"rho": rho, "mpc_d": d}
    (OUT / "dev_choices.json").write_text(json.dumps({"choice": ch, "dev": out}, indent=1) + "\n")
    print(ch, out)


def test():
    ch = json.loads((OUT / "dev_choices.json").read_text())["choice"]
    jobs = []
    for c in ("base", "tight", "overlap", "conflict", "small"):
        jobs += [("synth", (100000 + s, c), 20, ch, METHODS) for s in range(60)]
    for c in ("large_kN", "large_k1"):
        jobs += [("synth", (100000 + s, c), 6, ch, METHODS) for s in range(16)]
    jobs += [("ksl", (100000 + s,), 20, ch, METHODS) for s in range(120)]
    sl = sorted(int(p.name.split("_")[1]) for p in AX.RAW.glob("experiment_*_def_adv_both.json"))
    jobs += [("sumleaks", (sid,), 20, ch, METHODS) for sid in sl if sid % 2 == 1]
    jobs += [("eedi", (i,), 20, ch, METHODS) for i in range(1, 835, 2)]
    with Pool(9) as pool:
        rows = [r for r in pool.imap_unordered(evaluate, jobs, chunksize=1) if r]
    with gzip.open(OUT / "test_raw.json.gz", "wt") as h:
        json.dump(rows, h, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(len(rows))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["dev", "test"])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    dev() if a.stage == "dev" else test()
