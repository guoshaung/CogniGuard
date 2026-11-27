"""Soft-risk A1 (PREREG_SR.md). Risk per unit from the M2 bucket model fitted on the estimation secrets."""

from __future__ import annotations

import json
from collections import defaultdict

import numpy as np

from experiments.cogniguard_cgc4 import a_exp as AX
from experiments.cogniguard_cgc4.a_engine import Instance, Policy, leaf_rate, popcount
from experiments.cogniguard_cgc5.c5_exp import build
from experiments.cogniguard_ms import ms
from experiments.cogniguard_ms.prior.ge import ge_witnesses
from experiments.cogniguard_ms.prior.prior import DATA, OUT, bucket, load

METHODS = ["A1", "A1_SR", "A1_SR_NOREF", "A1_GE", "OCELOT_P", "PFLOW_P", "CAPD_FIRST", "ORACLE_A1"]


class SoftRisk(Policy):
    def __init__(self, inst, q_hat, p_unit, refuse=True, gamma=0.3):
        super().__init__("A1", inst, q_hat, gamma=gamma)
        self.p_unit, self.refuse, self.gamma = p_unit, refuse, gamma
        self.s = 0

    def reset_episode(self):
        self.s = 0

    def risk(self, K, o):
        keep = 1.0
        x = o & ~K
        while x:
            u = (x & -x).bit_length() - 1
            keep *= 1 - self.p_unit.get(u, 0.0)
            x &= x - 1
        return 1 - keep

    def act(self, t, state, ti, rng):
        self.calls += 1
        I = self.I
        g = I.group(I.types[ti][0])
        opts = self.eng.alive(state[g], ti)
        if not opts:
            return None
        rem = I.H - t - 1
        K = state[g]
        best, bv = None, -1e18
        for o in opts:
            st = list(state)
            st[g] = K | o
            v = (1 - self.risk(K, o)) * (self.s + 1 + rem * leaf_rate(self.eng, tuple(st), self.q, self.gamma))
            key = v - 1e-9 * popcount(o & ~K)
            if key > bv:
                best, bv = o, key
        if self.refuse:
            ref = self.s + rem * leaf_rate(self.eng, state, self.q, self.gamma)
            if ref > bv + 1e-9:
                return None
        self.s += 1
        return best


def evaluate(truth_keep):
    units, _, est = load()
    M2 = json.loads((OUT / "prior.json").read_text())["models"]["M2"]
    lines = (DATA / "eedi_exam/witness_sets.jsonl").read_text().splitlines()
    index = {json.loads(l)["target_id"]: i for i, l in enumerate(lines)}
    by_t = defaultdict(list)
    for u in units:
        by_t[u["target"]].append(u)
    rows = []
    for tid in sorted(by_t):
        if tid in est:
            continue                                  # validation secrets only
        i = index[tid]
        inst = build("eedi", (i,))
        if inst is None:
            continue
        w = json.loads(lines[i])
        pos = {u: j for j, u in enumerate(w["universe"])}
        p_unit = {pos[u["unit"]]: M2[bucket(u["consistent"])]["rate"] for u in by_t[tid] if u["unit"] in pos}
        Wh = [1 << pos[u["unit"]] for u in by_t[tid] if u["hid"] and truth_keep(u) and u["unit"] in pos]
        it = ms.true_instance(inst, Wh)
        ige = Instance(inst.n, ge_witnesses(inst, w["tau_bits"]), inst.types, inst.q, inst.H, N=inst.N,
                       pooled=inst.pooled, K0=inst.K0)
        q = AX.q_variants(inst, i)["emp"]
        seqs = AX.sequences(inst, i, 20, inst.q)
        res = {}
        for m in METHODS:
            if m == "A1_SR":
                pol = SoftRisk(inst, q, p_unit, refuse=True)
            elif m == "A1_SR_NOREF":
                pol = SoftRisk(inst, q, p_unit, refuse=False)
            elif m == "A1_GE":
                pol = Policy("A1", ige, q, gamma=ms.GAMMA)
            else:
                pol = ms.make(m, inst, it, q)
            r = ms.run(inst, Wh, pol, seqs, i)
            res[m] = {k: v for k, v in r.items() if k != "U_ep"}
        rows.append({"target": tid, "n_hidden": len(Wh), "res": res})
    rng = np.random.default_rng(0)
    S = {"n": len(rows), "with_hidden": sum(r["n_hidden"] > 0 for r in rows), "U": {}, "raw": {}, "breach": {}, "delta_U_pp": {}}
    for m in METHODS:
        for k, key in (("U", "U"), ("raw", "raw"), ("breach", "breach")):
            S[k][m] = float(np.mean([r["res"][m][key] for r in rows]))
    for a, b in (("A1_SR", "A1"), ("A1_SR", "A1_GE"), ("A1_SR_NOREF", "A1"), ("A1_GE", "A1"), ("OCELOT_P", "A1"),
                 ("PFLOW_P", "A1"), ("CAPD_FIRST", "A1"), ("ORACLE_A1", "A1")):
        d = np.array([100 * (r["res"][a]["U"] - r["res"][b]["U"]) for r in rows])
        s = d[rng.integers(0, len(d), size=(2000, len(d)))].mean(1)
        S["delta_U_pp"][f"{a}-{b}"] = {"mean": float(d.mean()), "lo": float(np.percentile(s, 2.5)), "hi": float(np.percentile(s, 97.5))}
    gap = S["delta_U_pp"]["ORACLE_A1-A1"]["mean"]
    S["capture"] = S["delta_U_pp"]["A1_SR-A1"]["mean"] / gap if gap > 1e-9 else None
    return S


def verdict(S):
    d, g = S["delta_U_pp"]["A1_SR-A1"], S["delta_U_pp"]["A1_SR-A1_GE"]
    if d["mean"] >= 2 and d["lo"] > 0 and g["lo"] > 0:
        return "GO"
    if d["lo"] > 0:
        return "WEAK"
    if d["mean"] >= 0:
        return "INCONCLUSIVE"
    return "STOP"


def main():
    out = {"T1": evaluate(lambda u: True), "T2": evaluate(lambda u: u["consistent"] >= 3)}
    out["verdict_T1"] = verdict(out["T1"])
    (OUT / "sr.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
