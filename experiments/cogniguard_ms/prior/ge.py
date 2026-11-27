""">= tau baseline (PREREG_GE.md): A1 on the minimal sets with leakage >= tau, under truths T1 and T2."""

from __future__ import annotations

import json
from collections import defaultdict

import numpy as np

from experiments.cogniguard_cgc4 import a_exp as AX
from experiments.cogniguard_cgc4.a_engine import Instance, Policy, popcount
from experiments.cogniguard_cgc5.c5_exp import build
from experiments.cogniguard_ms import ms
from experiments.cogniguard_ms.prior.prior import DATA, OUT, load

METHODS = ["A1", "A1_GE", "ORACLE_A1", "CAPD_FIRST", "OCELOT_P", "PFLOW_P"]


def ge_witnesses(inst, tau):
    over = [k for k in range(1, 1 << inst.n) if inst.leak(k) >= tau - 1e-9]
    S = set(over)
    return [k for k in over if not any((k & ~(1 << j)) in S for j in range(inst.n) if k >> j & 1)]


def run_truth(units, keep):
    lines = (DATA / "eedi_exam/witness_sets.jsonl").read_text().splitlines()
    index = {json.loads(l)["target_id"]: i for i, l in enumerate(lines)}
    hid = defaultdict(list)
    for u in units:
        if u["hid"] and keep(u):
            hid[u["target"]].append(u["unit"])
    rows = []
    for tid in sorted({u["target"] for u in units}):
        i = index[tid]
        inst = build("eedi", (i,))
        if inst is None:
            continue
        w = json.loads(lines[i])
        pos = {u: j for j, u in enumerate(w["universe"])}
        Wh = [1 << pos[u] for u in hid[tid] if u in pos]
        Wge = ge_witnesses(inst, w["tau_bits"])
        assert all(any(g & ~o == 0 for g in Wge) for o in inst.W)        # every formal witness is covered
        ige = Instance(inst.n, Wge, inst.types, inst.q, inst.H, N=inst.N, pooled=inst.pooled, K0=inst.K0)
        it = ms.true_instance(inst, Wh)
        q = AX.q_variants(inst, i)["emp"]
        seqs = AX.sequences(inst, i, 20, inst.q)
        res = {}
        for m in METHODS:
            pol = Policy("A1", ige, q, gamma=ms.GAMMA) if m == "A1_GE" else ms.make(m, inst, it, q)
            r = ms.run(inst, Wh, pol, seqs, i)
            res[m] = {k: v for k, v in r.items() if k != "U_ep"}
        rows.append({"target": tid, "n_hidden": len(Wh), "n_ge_singletons": sum(popcount(g) == 1 for g in Wge), "res": res})
    rng = np.random.default_rng(0)
    S = {"n": len(rows), "with_hidden": sum(r["n_hidden"] > 0 for r in rows),
         "mean_ge_singletons": float(np.mean([r["n_ge_singletons"] for r in rows])), "U": {}, "raw": {}, "breach": {}, "delta_U_pp": {}}
    for m in METHODS:
        S["U"][m] = float(np.mean([r["res"][m]["U"] for r in rows]))
        S["raw"][m] = float(np.mean([r["res"][m]["raw"] for r in rows]))
        S["breach"][m] = float(np.mean([r["res"][m]["breach"] for r in rows]))
    for a, b in (("A1_GE", "A1"), ("ORACLE_A1", "A1"), ("ORACLE_A1", "A1_GE"), ("OCELOT_P", "A1"), ("PFLOW_P", "A1"), ("CAPD_FIRST", "A1")):
        d = np.array([100 * (r["res"][a]["U"] - r["res"][b]["U"]) for r in rows])
        s = d[rng.integers(0, len(d), size=(2000, len(d)))].mean(1)
        S["delta_U_pp"][f"{a}-{b}"] = {"mean": float(d.mean()), "lo": float(np.percentile(s, 2.5)), "hi": float(np.percentile(s, 97.5))}
    gap = S["delta_U_pp"]["ORACLE_A1-A1"]["mean"]
    S["capture"] = S["delta_U_pp"]["A1_GE-A1"]["mean"] / gap if gap > 1e-9 else None
    return S


def main():
    units, _, _ = load()
    out = {"T1": run_truth(units, lambda u: True), "T2": run_truth(units, lambda u: u["consistent"] >= 3)}
    t1 = out["T1"]
    ok = t1["capture"] is not None and t1["capture"] >= 0.5 and t1["delta_U_pp"]["A1_GE-A1"]["lo"] > 0
    out["verdict"] = "GE_SUFFICIENT" if ok else "HEADROOM_REMAINS"
    (OUT / "ge.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
