"""Task A experiments: synthetic stress conditions, KSL-exact small instances, Sum Leaks / Eedi DERIVED
task sequences. Dev seeds choose parameters (a_dev); test seeds report (a_test). See SEEDS.md."""

from __future__ import annotations

import argparse
import gzip
import itertools
import json
import math
import random
import re
import time
import tracemalloc
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from experiments.cogniguard_cgc4.a_engine import Instance, Policy, check_safe, popcount, run_episode

OUT = Path(__file__).parent / "results"
DATA = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data")
RAW = Path("/Users/MBP/Exp/CogniGuard/cogniguard_raw/sumleaks_repo/data")

CONDS = {
    #            n   m  wmin wmax  P   H  N  pooled overlap conflict
    "base":     (24, 16, 2, 3, 12, 12, 1, True, 0.2, 0.5),
    "tight":    (24, 32, 2, 3, 12, 12, 1, True, 0.2, 0.5),
    "overlap":  (24, 16, 2, 3, 12, 12, 1, True, 0.8, 0.5),
    "conflict": (24, 16, 2, 3, 12, 12, 1, True, 0.2, 0.9),
    "small":    (12, 8, 2, 3, 6, 8, 1, True, 0.2, 0.6),
    "large_kN": (80, 60, 2, 3, 40, 40, 20, True, 0.2, 0.6),
    "large_k1": (80, 60, 2, 3, 40, 40, 20, False, 0.2, 0.6),
}


def gen_synth(seed, cond):
    """Options first, then witnesses. A witness joins units taken from options of DIFFERENT task types with
    probability `conflict` (so serving one task can kill another), otherwise random units; with probability
    `overlap` its units come from a small hot set (high witness overlap)."""
    n, m, wmin, wmax, P, H, N, pooled, overlap, conflict = CONDS[cond]
    rng = random.Random(seed)
    types = []
    for _ in range(P):
        a = rng.randrange(N)
        opts = []
        for _ in range(rng.choice([1, 2, 3])):
            o = sum(1 << u for u in rng.sample(range(n), rng.choice([1, 2])))
            if o not in opts:
                opts.append(o)
        types.append((a, opts))
    hot = rng.sample(range(n), max(4, n // 4))
    W = set()
    tries = 0
    while len(W) < m and tries < 50 * m:
        tries += 1
        k = rng.randint(wmin, wmax)
        if rng.random() < conflict and P >= 2:
            ts = rng.sample(range(P), min(k, P))
            units = set()
            for t in ts:
                o = rng.choice(types[t][1])
                units.add(rng.choice([u for u in range(n) if o >> u & 1]))
        elif rng.random() < overlap:
            units = set(rng.sample(hot, min(k, len(hot))))
        else:
            units = set(rng.sample(range(n), k))
        if len(units) >= 2:
            W.add(sum(1 << u for u in units))
    W = [w for w in W if not any(v != w and v & ~w == 0 for v in W)]
    inst0 = Instance(n, W, [(0, (1,))], [1.0], H)
    types = [(a, tuple(o for o in opts if inst0.feasible(0, o))) for a, opts in types]
    types = [t for t in types if t[1]]
    q = list(np.random.default_rng(seed).dirichlet(np.ones(len(types))))
    return Instance(n, W, types, q, H, N=N, pooled=pooled, meta={"cond": cond, "seed": seed})


def gen_ksl(seed, v_thr=0.5):
    """KSL structure as a hypergraph: witnesses = formal derivation sets at x* (Lemma 1 makes this exact)."""
    from experiments.cogniguard_cgc3.cand_a import make_instance
    from experiments.cogniguard_cgc3.common import NAMES, table
    name = NAMES[seed % len(NAMES)]
    inst = make_instance(name, seed, v_thr)
    if inst is None:
        return None
    Ls, tau, m = inst["Ls"], inst["tau"], inst["m"]
    over = [k for k in range(1 << m) if Ls[k] > tau + 1e-12]
    W = [k for k in over if not any(Ls[k & ~(1 << j)] > tau + 1e-12 for j in range(m) if k >> j & 1)]
    types = [(0, opts) for opts in inst["types"]]
    I = Instance(m, W, types, list(inst["q"]), 8, meta={"cond": "ksl", "seed": seed, "name": name, "x": inst["x"]})
    I.V1 = table(name).V1[:, inst["x"]]
    return I


def gen_sumleaks(sid):
    """DERIVED: units = tables; witnesses = computed E7 sets + owner-declared combination; tasks = the
    benign-run queries of Protocol B2 (real query strings); options = tables whose columns cover the two
    column names in the query (alternatives derived from the schema). Alice's own tables are K0."""
    cfg = json.loads((RAW / f"experiment_{sid}_def_adv_both.json").read_text())
    tables = [(f"{a}.{t}", sorted({c for r in b["rows"] for c in r})) for a, s in sorted(cfg["data_distribution"].items())
              for t, b in sorted(s.get("table", {}).items())]
    idx = {nm: i for i, (nm, _) in enumerate(tables)}
    from experiments.cogniguard_comparison_phase2.protocol_b2.diagnose import target_sets
    W = set()
    for kind in ("e7", "policy"):
        for s in target_sets(cfg, sid, kind) or []:
            if all(u in idx for u in s):
                W.add(sum(1 << idx[u] for u in s))
    W = [w for w in W if not any(v != w and v & ~w == 0 for v in W)]
    if not W:
        return None
    K0 = sum(1 << idx[nm] for nm in idx if nm.startswith("Alice."))
    if any(w & ~K0 == 0 for w in W):
        return None                                  # secret already inside Alice's tables (A3) - excluded
    ans = [json.loads(l) for l in (DATA / "protocol_b2/answers.jsonl").read_text().splitlines()]
    qs = [a["query"] for a in ans if a["scenario"] == sid and a["goal"] == "benign"]
    types = []
    for qtext in qs:
        cols = [c for c in re.split(r"[^A-Za-z_]+", qtext.lower()) if c]
        opts = []
        for i, (nm, cs) in enumerate(tables):
            if nm.startswith("Alice."):
                continue
            hit = sum(1 for c in cs if c.lower() in cols or c.lower().replace("_", " ") in qtext.lower())
            if hit >= 2:
                opts.append(1 << i)
        if opts:
            types.append((0, tuple(opts[:3])))
    if not types:
        return None
    inst = Instance(len(tables), W, types, [1 / len(types)] * len(types), 2 * len(types), K0=[K0],
                    meta={"cond": "sumleaks_derived", "scenario": sid})
    # drop options that are unsafe from K0 alone; drop empty types
    keep = []
    for a, opts in types:
        ok = tuple(o for o in opts if inst.feasible(K0, o))
        if ok:
            keep.append((a, ok))
    if len(keep) < 2:
        return None
    return Instance(len(tables), W, keep, [1 / len(keep)] * len(keep), 2 * len(keep), K0=[K0],
                    meta={"cond": "sumleaks_derived", "scenario": sid})


def gen_eedi(tid_index):
    """DERIVED: one Eedi target; units = retained attribute predicates; witnesses = stored derivation sets;
    task types = 'give one hint of feature f' (any unit of that feature serves)."""
    lines = (DATA / "eedi_exam/witness_sets.jsonl").read_text().splitlines()
    if tid_index >= len(lines):
        return None
    w = json.loads(lines[tid_index])
    uni = w["universe"]
    pos = {u: i for i, u in enumerate(uni)}
    W = [sum(1 << pos[u] for u in s) for s in w["sets"]]
    feats = {}
    for l in (DATA / "eedi_exam/units.jsonl").read_text().splitlines():
        r = json.loads(l)
        if r["target_id"] == w["target_id"] and r["unit_id"] in pos:
            feats.setdefault(r["predicate"]["feature"], []).append(1 << pos[r["unit_id"]])
    inst0 = Instance(len(uni), W, [(0, (1,))], [1.0], 1)
    types = [(0, tuple(o for o in opts if inst0.feasible(0, o))) for f, opts in sorted(feats.items())]
    types = [t for t in types if t[1]]
    if len(types) < 2:
        return None
    return Instance(len(uni), W, types, [1 / len(types)] * len(types), 6, meta={"cond": "eedi_derived", "target": w["target_id"]})


# ---------------------------------------------------------------- q estimation and evaluation

def q_variants(inst, seed):
    rng = np.random.default_rng(seed + 17)
    P = len(inst.q)
    hist = rng.choice(P, size=3 * P, p=np.array(inst.q) / sum(inst.q))
    emp = (np.bincount(hist, minlength=P) + 1) / (3 * P + P)
    return {"true": list(inst.q), "emp": list(emp), "unif": [1 / P] * P}


def sequences(inst, seed, E, q):
    out = []
    for e in range(E):
        rng = random.Random(hash((seed, e)) & 0xFFFFFFFF)
        out.append([rng.choices(range(len(q)), weights=q)[0] for _ in range(inst.H)])
    return out


def policy_specs(choice, small):
    g, r = choice["gamma"], choice["r"]
    P = [("CAPD_FIRST", {}), ("A0", {}), ("A1", {"gamma": g}), ("A1_DRO", {"gamma": g, "r": r}),
         ("MPC", {"d": choice["mpc_d"], "gamma": g}), ("BEAM", {"w": choice["beam_w"], "h": choice["beam_h"], "S": 8, "gamma": g}),
         ("SAA", {"S": choice["saa_S"], "h": choice["saa_h"], "gamma": g})]
    P.append(("SAA_DEFER", {"S": choice["saa_S"], "h": choice["saa_h"], "gamma": g, "defer": True}))
    if small:
        P += [("OPT_SERVE", {}), ("OPT", {})]
    return P


def evaluate(args):
    kind, key, choice, E, extra = args
    inst = {"synth": lambda: gen_synth(key[0], key[1]), "ksl": lambda: gen_ksl(key[0]),
            "sumleaks": lambda: gen_sumleaks(key[0]), "eedi": lambda: gen_eedi(key[0])}[kind]()
    if inst is None:
        return None
    seed = key[0]
    qv = q_variants(inst, seed)
    seq_in = sequences(inst, seed, E, inst.q)
    shift_q = list(0.5 * np.array(inst.q) + 0.5 * np.random.default_rng(seed + 31).dirichlet(np.ones(len(inst.q))))
    seq_shift = sequences(inst, seed + 7, E, shift_q)
    small = inst.n <= 14 and inst.pooled and inst.H <= 10
    specs = policy_specs(choice, small) + extra
    res = {}
    for name, kw in specs:
        label = name + ("" if not kw else "|" + ",".join(f"{k}={v}" for k, v in sorted(kw.items())))
        r = {}
        for qname in (("true", "emp", "unif") if name != "CAPD_FIRST" else ("true",)):
            pol = Policy(name, inst, qv[qname], **kw)
            tracemalloc.start()
            served, secs, unsafe, v1 = [], 0.0, 0, []
            for e, seq in enumerate(seq_in):
                s, sec, st = run_episode(inst, pol, seq, hash((seed, e, 1)) & 0xFFFFFFFF)
                served.append(s / inst.H)
                secs += sec
                unsafe += not check_safe(inst, st)
                if hasattr(inst, "V1"):
                    v1.append(float(inst.V1[st[0]]))
            mem = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            shift = []
            if qname == "emp":
                pol2 = Policy(name, inst, qv[qname], **kw)
                for e, seq in enumerate(seq_shift):
                    shift.append(run_episode(inst, pol2, seq, hash((seed, e, 2)) & 0xFFFFFFFF)[0] / inst.H)
            r[qname] = {"completion": float(np.mean(served)), "per_episode": served, "unsafe_episodes": unsafe,
                        "ms_per_decision": 1000 * secs / max(1, pol.calls), "peak_mem_kb": mem / 1024,
                        "cache_entries": len(pol.eng.alive_cache), "final_V1": float(np.mean(v1)) if v1 else None,
                        "shift_completion": float(np.mean(shift)) if shift else None, "shift_per_episode": shift or None}
        res[label] = r
    return {"kind": kind, "key": list(key), "n": inst.n, "m": len(inst.W), "P": len(inst.types), "H": inst.H,
            "N": inst.N, "pooled": inst.pooled, "meta": inst.meta, "res": res}


DEFAULT = {"gamma": 0.5, "r": 0.2, "mpc_d": 2, "beam_w": 3, "beam_h": 3, "saa_S": 8, "saa_h": 3}
GRID = {"gamma": [0.3, 0.5, 0.7], "r": [0.2, 0.5], "mpc_d": [1, 2, 3], "beam": [(2, 3), (4, 4)], "saa": [(8, 3), (16, 4)]}


def dev():
    """Choose free parameters on dev seeds (base + small + conflict), then freeze them."""
    import os
    jobs = [("synth", (s, c)) for c in ("base", "small", "conflict") for s in range(0, int(os.environ.get("DEV_N", 40)))]
    extra = []
    for g in GRID["gamma"]:
        extra.append(("A1", {"gamma": g}))
        for r in GRID["r"]:
            extra.append(("A1_DRO", {"gamma": g, "r": r}))
    for d in GRID["mpc_d"]:
        extra.append(("MPC", {"d": d, "gamma": 0.5}))
    for w, h in GRID["beam"]:
        extra.append(("BEAM", {"w": w, "h": h, "S": 8, "gamma": 0.5}))
    for S, h in GRID["saa"]:
        extra.append(("SAA", {"S": S, "h": h, "gamma": 0.5}))
    with Pool(9) as pool:
        rows = [r for r in pool.imap_unordered(evaluate, [(k, key, DEFAULT, 8, extra) for k, key in jobs]) if r]
    def score(label):
        q = "emp" if "emp" in rows[0]["res"].get(label, {"emp": 1}) else "true"
        return float(np.mean([r["res"][label][q]["completion"] for r in rows if label in r["res"]]))
    labs = rows[0]["res"].keys()
    pick = lambda pref: max([l for l in labs if l.startswith(pref + "|")], key=score)
    ch = {}
    best_a1 = pick("A1")
    ch["gamma"] = float(best_a1.split("gamma=")[1])
    best_dro = max([l for l in labs if l.startswith("A1_DRO|") and f"gamma={ch['gamma']}" in l], key=score)
    ch["r"] = float(best_dro.split("r=")[1].split(",")[0])
    mp = pick("MPC")
    ch["mpc_d"] = int(mp.split("d=")[1].split(",")[0])
    bm = pick("BEAM")
    ch["beam_w"], ch["beam_h"] = int(bm.split("w=")[1]), int(bm.split("h=")[1].split(",")[0])
    sa = pick("SAA")
    ch["saa_S"], ch["saa_h"] = int(sa.split("S=")[1].split(",")[0]), int(sa.split("h=")[1].split(",")[0])
    scores = {l: score(l) for l in labs}
    (OUT / "a_dev_choices.json").write_text(json.dumps({"choice": ch, "dev_scores_emp_q": scores, "n_dev": len(rows)}, indent=1) + "\n")
    print(ch)


def test():
    ch = json.loads((OUT / "a_dev_choices.json").read_text())["choice"]
    jobs = []
    for c in ("base", "tight", "overlap", "conflict", "small"):
        jobs += [("synth", (100000 + s, c), ch, 20, []) for s in range(60)]
    for c in ("large_kN", "large_k1"):
        jobs += [("synth", (100000 + s, c), ch, 6, []) for s in range(16)]
    jobs += [("ksl", (100000 + s,), ch, 20, []) for s in range(120)]
    # horizon ablation on base / conflict
    hz = [("MPC", {"d": d, "gamma": ch["gamma"]}) for d in (1, 2, 3)] + [("SAA", {"S": ch["saa_S"], "h": h, "gamma": ch["gamma"]}) for h in (2, 4, 6)]
    jobs += [("synth", (100000 + s, c), ch, 20, hz) for c in ("base", "conflict") for s in range(60, 90)]
    sl = sorted(int(p.name.split("_")[1]) for p in RAW.glob("experiment_*_def_adv_both.json"))
    jobs += [("sumleaks", (sid,), ch, 20, []) for sid in sl if sid % 2 == 1]
    jobs += [("eedi", (i,), ch, 20, []) for i in range(1, 835, 2)]
    with Pool(9) as pool:
        rows = [r for r in pool.imap_unordered(evaluate, jobs, chunksize=1) if r]
    with gzip.open(OUT / "a_test_raw.json.gz", "wt") as h:
        json.dump(rows, h, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(len(rows))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["dev", "test"])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    dev() if a.stage == "dev" else test()
