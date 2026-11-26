"""Misspecified-witness scenario (PREREG.md). Policies see the observed witnesses only; evaluation uses
W_true = W_obs u W_hid. Primary metric U: an episode in which any group's knowledge ever contains a true
witness scores 0, otherwise served / H."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import random
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from experiments.cogniguard_cgc4 import a_exp as AX
from experiments.cogniguard_cgc4.a_engine import Instance, Policy, check_safe, popcount
from experiments.cogniguard_cgc5.baselines import Baseline
from experiments.cogniguard_cgc5.c5_exp import build

OUT = Path(__file__).parent / "results"
GAMMA = 0.3
CH = {"rho": 0.67, "mpc_d": 3}                 # CGC5 dev choices (frozen)
MODES = ("near", "shrink", "random")
RHOS = (0.1, 0.25, 0.5)
SYNTH = ("base", "tight", "overlap", "conflict")
DEV_METHODS = ["A1", "CAPD_FIRST", "OCELOT_P", "PFLOW_P", "DYNCQE_P", "OCOST", "ORACLE_A1"]
TEST_METHODS = DEV_METHODS + ["MPC_OPT"]


def bits(x):
    out = []
    while x:
        u = (x & -x).bit_length() - 1
        out.append(u)
        x &= x - 1
    return out


def optmask(inst):
    m = 0
    for _, opts in inst.types:
        for o in opts:
            m |= o
    return m


def hidden_pool(inst, kind, key, mode):
    """Ordered candidate hidden witnesses for one instance and mode (seed independent of rho -> nested)."""
    rng = random.Random(f"{kind}|{key}|{mode}")
    W = list(inst.W)
    om = bits(optmask(inst))
    cands = []
    if mode == "near":
        order = W[:]
        rng.shuffle(order)
        for w in order:
            ws = bits(w)
            drop = rng.choice(ws)
            outside = [u for u in om if not w >> u & 1]
            if not outside:
                cands.append(None)
                continue
            add = rng.choice(outside)
            cands.append((w & ~(1 << drop)) | (1 << add))
    elif mode == "shrink":
        order = [w for w in W if popcount(w) >= 3]
        rng.shuffle(order)
        for w in order:
            cands.append(w & ~(1 << rng.choice(bits(w))))
    elif mode == "random":
        for _ in range(len(W)):
            k = rng.randint(2, 3)
            if len(om) < k:
                cands.append(None)
                continue
            cands.append(sum(1 << u for u in rng.sample(om, k)))
    else:
        raise ValueError(mode)
    return cands


def hidden(inst, kind, key, mode, rho):
    pool = hidden_pool(inst, kind, key, mode)
    take = pool[: math.ceil(rho * len(pool))]
    out = []
    for h in take:
        if h is None or h in inst.W or h in out:
            continue
        if any(h & ~K == 0 for K in inst.K0):          # already inside the initial knowledge
            continue
        if any(w & ~h == 0 for w in inst.W):          # superset of an observed witness: never binding
            continue
        out.append(h)
    return out


def true_instance(inst, Wh):
    I = Instance(inst.n, list(inst.W) + list(Wh), inst.types, inst.q, inst.H, N=inst.N, pooled=inst.pooled,
                 K0=inst.K0, meta=dict(inst.meta))
    return I


def make(name, inst, inst_true, q):
    if name == "A1":
        return Policy("A1", inst, q, gamma=GAMMA)
    if name == "CAPD_FIRST":
        return Policy("CAPD_FIRST", inst, q)
    if name == "ORACLE_A1":
        return Policy("A1", inst_true, q, gamma=GAMMA)
    kw = {"gamma": GAMMA}
    if name == "OCELOT_P":
        kw["budget"] = math.inf
    if name == "PFLOW_P":
        kw["rho"] = CH["rho"]
    if name == "DYNCQE_P":
        kw["samples"], kw["seed"] = 256, 0
    if name == "MPC_OPT":
        kw["d"] = CH["mpc_d"]
    return Baseline(name, inst, q, **kw)


def run(inst, Wh, pol, seqs, seed):
    U, raw, breach, first, unsafe_obs = [], [], 0, [], 0
    t0 = time.perf_counter()
    for e, seq in enumerate(seqs):
        if hasattr(pol, "reset_episode"):
            pol.reset_episode()
        state = inst.K0
        rng = random.Random(hash((seed, e, 1)) & 0xFFFFFFFF)
        s, b = 0, None
        for t, ti in enumerate(seq):
            o = pol.act(t, state, ti, rng)
            if o is not None:
                g = inst.group(inst.types[ti][0])
                st = list(state)
                st[g] |= o
                state = tuple(st)
                s += 1
                if b is None and any(h & ~state[g] == 0 for h in Wh):
                    b = t
        raw.append(s / inst.H)
        U.append(0.0 if b is not None else s / inst.H)
        breach += b is not None
        if b is not None:
            first.append(b / inst.H)
        unsafe_obs += not check_safe(inst, state)
    return {"U": float(np.mean(U)), "U_ep": U, "raw": float(np.mean(raw)), "breach": breach / len(seqs),
            "first_breach": float(np.mean(first)) if first else None, "unsafe_obs": unsafe_obs,
            "ms": 1000 * (time.perf_counter() - t0) / max(1, pol.calls)}


def evaluate(args):
    kind, key, E, methods = args
    inst = build(kind, key)
    if inst is None:
        return None
    seed = key[0]
    q = AX.q_variants(inst, seed)["emp"]
    seqs = AX.sequences(inst, seed, E, inst.q)
    cells = {}
    for mode in MODES:
        for rho in RHOS:
            Wh = hidden(inst, kind, key, mode, rho)
            it = true_instance(inst, Wh)
            res = {}
            for m in methods:
                res[m] = run(inst, Wh, make(m, inst, it, q), seqs, seed)
            cells[f"{mode}|{rho}"] = {"n_hidden": len(Wh), "res": res}
    reg = key[1] if kind == "synth" else kind
    return {"kind": kind, "regime": reg, "key": list(key), "n": inst.n, "m": len(inst.W), "cells": cells}


def jobs(stage):
    J = []
    if stage == "dev":
        for c in SYNTH:
            J += [("synth", (s, c), 8, DEV_METHODS) for s in range(40)]
        J += [("ksl", (s,), 8, DEV_METHODS) for s in range(60)]
        J += [("eedi", (i,), 8, DEV_METHODS) for i in range(0, 835, 2)]
    else:
        for c in SYNTH:
            J += [("synth", (100000 + s, c), 20, TEST_METHODS) for s in range(60)]
        J += [("ksl", (100000 + s,), 20, TEST_METHODS) for s in range(120)]
        J += [("eedi", (i,), 20, TEST_METHODS) for i in range(1, 835, 2)]
    return J


def main(stage, procs):
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with Pool(procs) as pool:
        rows = [r for r in pool.imap_unordered(evaluate, jobs(stage), chunksize=1) if r]
    with gzip.open(OUT / f"{stage}_rows.json.gz", "wt") as h:
        json.dump(rows, h)
    print(stage, len(rows), f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["dev", "test"])
    ap.add_argument("--procs", type=int, default=6)
    a = ap.parse_args()
    main(a.stage, a.procs)
