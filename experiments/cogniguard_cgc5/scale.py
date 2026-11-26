"""Scaling benchmark (run ALONE, single process, no tracemalloc during timing): per-decision time of A1 vs
A1_FULL and the other baselines as the hypergraph grows. Memory measured in a separate tracemalloc pass.
Decision agreement A1 vs A1_FULL is checked on every step."""

from __future__ import annotations

import json
import random
import time
import tracemalloc
from pathlib import Path

import numpy as np

from experiments.cogniguard_cgc4 import a_exp as AX
from experiments.cogniguard_cgc4.a_engine import Policy
from experiments.cogniguard_cgc5.baselines import Baseline

OUT = Path(__file__).parent / "results"
SIZES = [24, 60, 120, 240, 400]
METHODS = ["A1", "A1_FULL", "OCOST", "OCELOT_P", "PFLOW_P", "DYNCQE_P", "MPC_OPT"]


def make(name, inst, q):
    if name == "A1":
        return Policy("A1", inst, q, gamma=0.3)
    kw = {"gamma": 0.3, "d": 2, "rho": 1.01, "samples": 256, "seed": 0}
    return Baseline(name, inst, q, **kw)


def run_one(inst, name, seqs, limit_s=60.0):
    pol = make(name, inst, inst.q)
    decs, t0, n = [], time.perf_counter(), 0
    for seq in seqs:
        state = inst.K0
        d = []
        for t, ti in enumerate(seq):
            o = pol.act(t, state, ti, random.Random(t))
            d.append(o)
            n += 1
            if o is not None:
                st = list(state)
                st[inst.group(inst.types[ti][0])] |= o
                state = tuple(st)
            if time.perf_counter() - t0 > limit_s:
                return None, None, None
        decs.append(d)
    ms = 1000 * (time.perf_counter() - t0) / n
    pol2 = make(name, inst, inst.q)
    tracemalloc.start()
    state = inst.K0
    for t, ti in enumerate(seqs[0]):
        o = pol2.act(t, state, ti, random.Random(t))
        if o is not None:
            st = list(state)
            st[inst.group(inst.types[ti][0])] |= o
            state = tuple(st)
    mem = tracemalloc.get_traced_memory()[1] / 1024
    tracemalloc.stop()
    return ms, mem, decs


def main():
    rows = []
    for n in SIZES:
        AX.CONDS[f"scale_{n}"] = (n, n, 2, 3, n // 2, 40, 1, True, 0.2, 0.6)
        for seed in range(3):
            inst = AX.gen_synth(200000 + seed, f"scale_{n}")
            seqs = AX.sequences(inst, 200000 + seed, 2, inst.q)
            r = {"n": n, "m": len(inst.W), "P": len(inst.types), "seed": seed, "res": {}}
            decs = {}
            for mname in METHODS:
                ms, mem, d = run_one(inst, mname, seqs)
                r["res"][mname] = {"ms": ms, "mem_kb": mem}
                decs[mname] = d
                print(n, seed, mname, ms, mem, flush=True)
            if decs["A1"] and decs["A1_FULL"]:
                a, b = decs["A1"], decs["A1_FULL"]
                r["agreement"] = sum(x == y for da, db in zip(a, b) for x, y in zip(da, db)) / sum(len(x) for x in a)
            rows.append(r)
    (OUT / "scale.json").write_text(json.dumps(rows, indent=1) + "\n")


if __name__ == "__main__":
    main()
