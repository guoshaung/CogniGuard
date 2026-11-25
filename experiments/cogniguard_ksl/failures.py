"""Concrete failure cases (exact) for the KSL-V2 report: CA-PD partial-leak misses, denial leaks of a
realized-value gate, and LLM-attacker disagreements with the exact Bayes vulnerability."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from experiments.cogniguard_ksl import engine, structures as S

R = Path(__file__).parent / "results"
D = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/ksl")
TAU = 0.5


def capd_misses():
    out = []
    for st in S.all_structures():
        T = engine.build(st)
        reg = engine.registry(T)
        best = None
        for K in range(1 << len(T.units)):
            if T.cov[K] or not K & T.relevant:
                continue
            for j in range(len(T.units)):
                Ku = K | 1 << j
                if K >> j & 1 or T.cov[Ku]:
                    continue
                safe = engine.capd_safe(T, reg, "A", 1 << j, {"A": K}, 1)
                ev_b, ev_a = float(T.V1[K] @ T.prior), float(T.V1[Ku] @ T.prior)
                if safe and ev_a >= TAU and (best is None or ev_a - ev_b > best["gain"]):
                    best = {"structure": st.name, "known": T.names(K), "release": T.units[j], "capd": "safe (no witness)",
                            "E_V1_before": round(ev_b, 3), "E_V1_after": round(ev_a, 3), "prior_V1": round(T.prior_V1(), 4),
                            "gain": ev_a - ev_b}
        if best:
            best.pop("gain")
            out.append(best)
    return out


def denial_examples():
    out = []
    T = engine.build(S.and_join("max"))
    j = T.bit("in_a")
    harm = (T.V1[j] >= TAU) & (T.V1[j] > T.V1[0] + 1e-12)
    refused = [i for i in range(len(T.prior)) if harm[i]]
    ps = np.bincount(T.sidx[refused], weights=T.prior[refused], minlength=len(T.svals))
    ps /= ps.sum()
    out.append({"structure": "and_max", "attacker_knows": [], "requests": "in_a",
                "REAL_gate_refuses_iff": sorted({T.st.worlds[i][0][0] for i in refused}),
                "attacker_posterior_after_refusal": {str(T.svals[s]): round(float(p), 3) for s, p in enumerate(ps) if p > 0},
                "V1_before": round(T.prior_V1(), 3), "V1_after_refusal": round(float(ps.max()), 3)})
    return out


def llm_cases():
    f = D / "attack_llm.jsonl"
    if not f.exists():
        return {}
    rows = [json.loads(l) for l in f.read_text().splitlines()]
    pick = lambda cond, n=3: [{k: r[k] for k in ("structure", "mask", "x", "V1", "cov", "hit1", "hit3", "raw")}
                              for r in rows if cond(r)][:n]
    return {"noncovered_V1>=0.5_but_wrong": pick(lambda r: not r["cov"] and r["V1"] >= 0.5 and not r["hit1"]),
            "covered_witness_but_wrong": pick(lambda r: r["cov"] and not r["hit1"]),
            "V1<0.2_but_right": pick(lambda r: not r["cov"] and r["V1"] < 0.2 and r["hit1"]),
            "realized_determination_no_witness_right": pick(lambda r: not r["cov"] and r["det"] and r["hit1"])}


def main():
    res = {"capd_partial_leak_misses": capd_misses(), "denials_leak": denial_examples(), "llm": llm_cases()}
    (R / "failures.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    for x in res["capd_partial_leak_misses"]:
        print(x)
    print(res["denials_leak"])
    print({k: len(v) for k, v in res["llm"].items()})


if __name__ == "__main__":
    main()
