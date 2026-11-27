"""Protocol C analysis (PREREG_C.md sections 5-6). Paired bootstrap over targets, 10,000 resamples, seed 20261128."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PC = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/protocol_c/results")
OUT = Path(__file__).parent / "results"
B, SEED = 10_000, 20261128


def load(stage):
    return [json.loads(p.read_text()) for p in sorted((PC / stage).glob("*.json"))]


def leak(r, c, m):
    return float(r["conds"][str(c)]["methods"][m]["leak"])


def benign(r, c, m):
    x = r["conds"][str(c)]["methods"][m]
    return x["benign_served"] / x["benign_total"] if x["benign_total"] else 1.0


def choose():
    rows = load("dev")
    out = {"n": len(rows), "grid": {}}
    base = np.mean([leak(r, c, "nogate") for r in rows for c in (1, 2, 3)])
    for o in ("ocelot_recip", "ocelot_global"):
        pts = {}
        for b in (0.5, 1.0, 1.5, 2.0, 2.5):
            m = f"{o}@{b}"
            pts[b] = {"leak": float(np.mean([leak(r, c, m) for r in rows for c in (1, 2, 3)])),
                      "benign": float(np.mean([benign(r, c, m) for r in rows for c in (1, 2, 3)]))}
        ok = [b for b in pts if pts[b]["leak"] <= 0.2 * base + 1e-12]
        pick = max(ok, key=lambda b: (pts[b]["benign"], b)) if ok else min(pts, key=lambda b: (pts[b]["leak"], -b))
        out["grid"][o] = pts
        out[o] = pick
    out["nogate_leak"] = float(base)
    (OUT / "c_dev_choices.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


def boot(x, rng):
    x = np.asarray(x, float)
    s = x[rng.integers(0, len(x), size=(B, len(x)))].mean(1)
    return {"mean": float(x.mean()), "lo": float(np.percentile(s, 2.5)), "hi": float(np.percentile(s, 97.5)), "n": len(x)}


def main():
    rows = load("test")
    ch = json.loads((OUT / "c_dev_choices.json").read_text())
    rec, glob = f"ocelot_recip@{ch['ocelot_recip']}", f"ocelot_global@{ch['ocelot_global']}"
    methods = ["nogate", "oracle", "capd1", "capd2", "capd3", rec, glob, "tom", "codef"]
    rng = np.random.default_rng(SEED)
    out = {"n": len(rows), "methods_by_c": {}, "pairs": {}, "hypotheses": {},
           "meter": {"exact_rate": float(np.mean([r["meter_exact"] / len(r["units"]) for r in rows])),
                     "unparsable": int(sum(r["meter_unparsable"] for r in rows))}}
    for c in (1, 2, 3):
        out["methods_by_c"][c] = {m: {"leak": float(np.mean([leak(r, c, m) for r in rows])),
                                      "formal_leak": float(np.mean([r["conds"][str(c)]["methods"][m]["formal_leak"] for r in rows])),
                                      "benign_served": float(np.mean([benign(r, c, m) for r in rows]))} for m in methods}
        for a in methods:
            for b in methods:
                if a < b or a == b:
                    continue
                out["pairs"][f"c{c}:{a}-{b}"] = {
                    "d_leak": boot([leak(r, c, a) - leak(r, c, b) for r in rows], rng),
                    "d_benign": boot([benign(r, c, a) - benign(r, c, b) for r in rows], rng)}

    def pair(c, a, b):
        key = f"c{c}:{a}-{b}" if f"c{c}:{a}-{b}" in out["pairs"] else f"c{c}:{b}-{a}"
        p = out["pairs"][key]
        sign = 1 if key == f"c{c}:{a}-{b}" else -1
        return {k: {"mean": sign * v["mean"], "lo": sign * (v["lo"] if sign > 0 else v["hi"]),
                    "hi": sign * (v["hi"] if sign > 0 else v["lo"])} for k, v in p.items()}

    for c in (2, 3):
        d = pair(c, rec, f"capd{c}")["d_leak"]
        out["hypotheses"][f"H1_c{c}"] = {"d_leak(recip-capd)": d, "holds": d["lo"] > 0}
        d = pair(c, glob, f"capd{c}")["d_benign"]
        out["hypotheses"][f"H2_c{c}"] = {"d_benign(global-capd)": d, "holds": d["hi"] < 0}
    p = pair(1, "capd1", rec)
    out["hypotheses"]["H3_c1"] = {**p, "holds": all(v["lo"] <= 0 <= v["hi"] for v in p.values())}
    for c in (1, 2, 3):
        for b in ("tom", "codef"):
            out["hypotheses"][f"vs_{b}_c{c}"] = pair(c, f"capd{c}", b)
    (OUT / "c_analysis.json").write_text(json.dumps(out, indent=1) + "\n")
    for c in (1, 2, 3):
        print(f"c={c}")
        for m, v in out["methods_by_c"][c].items():
            print(f"  {m:20s} leak={v['leak']:.3f} formal={v['formal_leak']:.3f} benign={v['benign_served']:.3f}")
    print(json.dumps(out["hypotheses"], indent=1))


if __name__ == "__main__":
    {"choose": choose, "test": main}[sys.argv[1] if len(sys.argv) > 1 else "test"]()
