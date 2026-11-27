"""Protocol D analysis (PREREG_D.md sections 4-5). Paired bootstrap over scenarios, 10,000 resamples, seed 20261128."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

RES = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/protocol_d/results")
OUT = Path(__file__).parent / "results"
B_GRID = (0.2, 0.34, 0.5, 0.67, 0.75, 0.99)
NB, SEED = 10_000, 20261128


def arrays(rows, c, m):
    L = np.array([float(r["conds"][str(c)]["methods"][m]["leak"]) for r in rows])
    U = np.array([r["conds"][str(c)]["methods"][m]["benign_served"] / max(1, r["conds"][str(c)]["methods"][m]["benign_total"])
                  for r in rows])
    return L, U


def frontier_value(points, leak):
    """OCELOT's achievable benign service at a given leak level: the upper concave envelope of its budget points
    (randomising between two budgets is a valid policy; a lower-leak point is always admissible). Below the
    lowest-leak point the lowest-leak point's benign service is used (PREREG_D section 4)."""
    pts = sorted(points)
    if leak < pts[0][0]:                                       # D3: below every point -> best of the lowest-leak ties
        return max(u for l, u in pts if l == pts[0][0])
    best = max(u for l, u in pts if l <= leak)
    for i, (l0, u0) in enumerate(pts):
        for l1, u1 in pts[i + 1:]:
            if l0 <= leak <= l1 and l1 > l0:
                best = max(best, u0 + (u1 - u0) * (leak - l0) / (l1 - l0))
    return best


def main():
    rows = [json.loads(p.read_text()) for p in sorted(RES.glob("*.json"))]
    n = len(rows)
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, n, size=(NB, n))
    out = {"n": n, "summary": {}, "H_F": {}, "H_LLM": {}, "secondary": {}}
    methods = list(rows[0]["conds"]["2"]["methods"])
    for c in (2, 3):
        out["summary"][c] = {}
        A = {m: arrays(rows, c, m) for m in methods}
        for m in methods:
            out["summary"][c][m] = {"leak": float(A[m][0].mean()), "benign": float(A[m][1].mean()),
                                    "formal_leak": float(np.mean([r["conds"][str(c)]["methods"][m]["formal_leak"] for r in rows]))}
        cap = f"capd{c}"
        for led in ("recip", "global"):
            ms = [f"ocelot_{led}@{b}" for b in B_GRID]
            def delta(ix):
                pts = [(A[m][0][ix].mean(), A[m][1][ix].mean()) for m in ms]
                return A[cap][1][ix].mean() - frontier_value(pts, A[cap][0][ix].mean())
            ds = np.array([delta(ix) for ix in idx])
            d0 = delta(np.arange(n))
            out["H_F"][f"c{c}_{led}"] = {"delta": float(d0), "lo": float(np.percentile(ds, 2.5)), "hi": float(np.percentile(ds, 97.5)),
                                         "holds": bool(np.percentile(ds, 2.5) > 0)}
        for b in ("tom", "codef"):
            dl = A[cap][0] - A[b][0]
            du = A[cap][1] - A[b][1]
            sl, su = dl[idx].mean(1), du[idx].mean(1)
            out["H_LLM"][f"c{c}_{b}"] = {"d_leak": [float(dl.mean()), float(np.percentile(sl, 2.5)), float(np.percentile(sl, 97.5))],
                                         "d_benign": [float(du.mean()), float(np.percentile(su, 2.5)), float(np.percentile(su, 97.5))],
                                         "holds": bool(np.percentile(sl, 97.5) < 0 and np.percentile(su, 2.5) > -0.05)}
        # secondary: balanced and safe*benign vs every baseline; OCELOT at its test-optimal B (favourable to OCELOT)
        bal = {m: (1 - A[m][0] + A[m][1]) / 2 for m in methods}
        prod = {m: (1 - A[m][0]) * A[m][1] for m in methods}
        sec = {}
        for name, met in (("balanced", bal), ("safe_x_benign", prod)):
            best = {led: max((f"ocelot_{led}@{b}" for b in B_GRID), key=lambda m: met[m].mean()) for led in ("recip", "global")}
            for ref in ["tom", "codef", "capd1", best["recip"], best["global"]]:
                d = met[cap] - met[ref]
                s = d[idx].mean(1)
                sec[f"{name}:{cap}-{ref}"] = [float(d.mean()), float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))]
        out["secondary"][c] = sec
    hf = all(v["holds"] for v in out["H_F"].values())
    hl = all(v["holds"] for v in out["H_LLM"].values())
    out["verdict"] = "GO" if hf and hl else ("PARTIAL" if hf or hl else "STOP")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "d_analysis.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("n", "verdict", "H_F", "H_LLM")}, indent=1))
    for c in (2, 3):
        print("c", c)
        for m, v in out["summary"][c].items():
            print(f"  {m:20s} leak={v['leak']:.3f} benign={v['benign']:.3f} formal={v['formal_leak']:.3f}")
        for k, v in out["secondary"][c].items():
            print("  ", k, [round(x, 3) for x in v])


if __name__ == "__main__":
    main()
