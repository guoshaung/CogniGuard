"""CGC5 analysis: A1 vs strong baselines (paired bootstrap over instances), decision agreement, OPT gap,
runtime and memory, scaling."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

R = Path(__file__).parent / "results"
CGC4 = Path(__file__).parents[1] / "cogniguard_cgc4" / "results" / "a_test_raw.json.gz"
rng = np.random.default_rng(0)
ORDER = ["A1", "A1_FULL", "OCELOT_P", "OCELOT_P|B=0.8max", "PFLOW_P", "DYNCQE_P", "OCOST", "MPC_OPT", "OPT_CANON_SERVE", "OPT_CANON"]


def boot(d, n=4000):
    d = np.asarray(d, float)
    if len(d) == 0:
        return None
    bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(n)]
    return {"mean": float(d.mean()), "lo": float(np.quantile(bs, .025)), "hi": float(np.quantile(bs, .975)), "n": int(len(d))}


def main():
    rows = json.load(gzip.open(R / "test_raw.json.gz", "rt"))
    capd = {}
    if CGC4.exists():
        for r in json.load(gzip.open(CGC4, "rt")):
            if "CAPD_FIRST" in r["res"]:
                capd[(r["kind"], tuple(r["key"]))] = r["res"]["CAPD_FIRST"]["true"]["completion"]
    out = {"conditions": {}, "agreement": {}, "notes": []}
    conds = sorted({r["meta"].get("cond") for r in rows})
    for c in conds:
        rs = [r for r in rows if r["meta"].get("cond") == c]
        tab = {}
        for m in ORDER:
            ok = [r for r in rs if m in r["res"] and "completion" in r["res"][m]]
            if not ok:
                tab[m] = {"skipped": rs[0]["res"].get(m, {}).get("skipped", "n/a") if m in rs[0]["res"] else "n/a"}
                continue
            tab[m] = {"n": len(ok), "completion": float(np.mean([r["res"][m]["completion"] for r in ok])),
                      "minus_A1": boot([r["res"][m]["completion"] - r["res"]["A1"]["completion"] for r in ok]),
                      "ms": float(np.mean([r["res"][m]["ms_per_decision"] for r in ok])),
                      "ms_median": float(np.median([r["res"][m]["ms_per_decision"] for r in ok])),
                      "mem_kb": float(np.mean([r["res"][m]["peak_mem_kb"] for r in ok])),
                      "cache": float(np.mean([r["res"][m]["cache_entries"] for r in ok])),
                      "unsafe": int(sum(r["res"][m]["unsafe_episodes"] for r in ok)),
                      "final_leak": float(np.mean([r["res"][m]["final_leak"] for r in ok])) if ok[0]["res"][m].get("final_leak") is not None else None,
                      "censor_mode": ok[0]["res"][m].get("censor_mode")}
        cp = [capd.get((r["kind"], tuple(r["key"]))) for r in rs]
        if all(x is not None for x in cp):
            tab["CAPD_FIRST (CGC4, same seqs)"] = {"completion": float(np.mean(cp)),
                                                   "minus_A1": boot([x - r["res"]["A1"]["completion"] for x, r in zip(cp, rs)])}
            if all("completion" in r["res"].get("OPT_CANON", {}) for r in rs):
                num = sum(r["res"]["A1"]["completion"] - x for x, r in zip(cp, rs))
                den = sum(r["res"]["OPT_CANON"]["completion"] - x for x, r in zip(cp, rs))
                tab["A1 share of OPT gain over CAPD"] = num / den if den > 0 else None
        out["conditions"][c] = {"n_instances": len(rs), "size": {k: float(np.mean([r[k] for r in rs])) for k in ("n", "m", "P", "H")},
                                "table": tab}
        ag = [r["a1_full_agreement"] for r in rs if r["a1_full_agreement"] is not None]
        out["agreement"][c] = {"mean": float(np.mean(ag)), "min": float(np.min(ag)), "n": len(ag)}
    if (R / "scale.json").exists():
        sc = json.loads((R / "scale.json").read_text())
        agg = {}
        for r in sc:
            for m, v in r["res"].items():
                agg.setdefault((r["n"], m), []).append(v)
        out["scale"] = {f"n={n}|{m}": {"ms": (float(np.mean([v["ms"] for v in vs])) if all(v["ms"] is not None for v in vs) else None),
                                       "mem_kb": (float(np.mean([v["mem_kb"] for v in vs])) if all(v["mem_kb"] is not None for v in vs) else None)}
                        for (n, m), vs in sorted(agg.items())}
        out["scale_agreement"] = [r.get("agreement") for r in sc]
    (R / "analysis.json").write_text(json.dumps(out, indent=1) + "\n")
    print("ok")


if __name__ == "__main__":
    main()
