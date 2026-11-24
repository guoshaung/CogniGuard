"""Section 6 judgments from results/raw.csv. Each gate is judged on its own."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOOT, BOOT_SEED = 5000, 20261124
SYN = [("synthetic", 16), ("synthetic", 32)]
FS = (2, 4, 8)


def lower(values):
    rng = random.Random(BOOT_SEED)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(BOOT))
    return means[int(0.025 * BOOT)]


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return x


def index(rows):
    idx = defaultdict(dict)
    for r in rows:
        key = (r["phase"], r["dataset"], int(r["K"]), r["graph"], r["mode"], int(r["f"]), r["noise"], r["arm"])
        idx[key][int(r["seed"])] = {k: _f(v) for k, v in r.items()}
    return idx


def paired(idx, key_a, key_b, metric):
    a, b = idx[key_a], idx[key_b]
    seeds = sorted(set(a) & set(b))
    diffs = [a[s][metric] - b[s][metric] for s in seeds]
    return {"mean_diff": sum(diffs) / len(diffs), "lower": lower(diffs), "n": len(diffs)}


def judge(rows):
    idx = index(rows)
    out = {}
    # Gate 0
    cells = {}
    for ds, K in SYN + [("eedi_exam", 16)]:
        for mode in ("coalition", "benign"):
            for f in FS:
                runs = idx[("G01", ds, K, "sparse", mode, f, "base", "B0")]
                harm = [runs[s]["harmful_releases"] for s in sorted(runs)]
                prop = sum(runs[s]["prop_induced"] for s in runs)
                rho = sum(harm) / (sum(harm) + prop) if (sum(harm) + prop) else 0.0
                cells[f"{ds}{K}/{mode}/f{f}"] = {"mean_harmful": sum(harm) / len(harm),
                                                 "lower": lower(harm), "sum_harmful": sum(harm),
                                                 "sum_prop": prop, "rho": rho}
    passed = [c for c, v in cells.items() if "synthetic" in c and "/coalition/" in c
              and v["lower"] > 0 and v["rho"] >= 0.3]
    out["Gate0"] = {"verdict": "支持" if passed else "不支持", "passing_cells": passed, "cells": cells}
    # Gate 1A
    bad = [k for k, runs in idx.items() if k[0] == "G01" and k[-1] in ("B1", "B2", "B2b", "Ours")
           and any(v["harmful_releases"] > 0 for v in runs.values())]
    g1a = {}
    for ds, K in SYN:
        for f in FS:
            base = ("G01", ds, K, "sparse", "coalition", f, "base")
            g1a[f"{ds}{K}/f{f}"] = paired(idx, base + ("B2b",), base + ("B1",), "UR_normal")
    n1a = sum(v["lower"] > 0 for v in g1a.values())
    out["Gate1A"] = {"check_harmful_zero": "通过" if not bad else f"失败: {bad[:5]}",
                     "verdict": ("支持" if n1a >= 3 else "不支持") if not bad else "无法判定（实现核对失败）",
                     "cells_supported": n1a, "cells": g1a}
    # Gate 1B
    mismatch = []
    for ds, K in SYN + [("eedi_exam", 16)]:
        for mode in ("coalition", "benign"):
            for f in FS:
                a = idx[("G01", ds, K, "complete", mode, f, "base", "Ours")]
                b = idx[("G01", ds, K, "complete", mode, f, "base", "B2b")]
                for s in a:
                    keys = ("harmful_releases", "UR_normal", "DR_normal", "unneeded_refusal_rate")
                    if any(a[s][k] != b[s][k] for k in keys):
                        mismatch.append((ds, K, mode, f, s))
    g1b = {}
    for ds, K in SYN:
        for f in FS:
            base = ("G01", ds, K, "sparse", "coalition", f, "base")
            g1b[f"{ds}{K}/f{f}"] = paired(idx, base + ("Ours",), base + ("B2b",), "UR_normal")
    n1b = sum(v["lower"] > 0 for v in g1b.values())
    out["Gate1B"] = {"check_complete_equal": "通过" if not mismatch else f"失败: {mismatch[:5]}",
                     "verdict": ("支持" if n1b >= 3 else "不支持") if not mismatch else "无法判定（实现核对失败）",
                     "cells_supported": n1b, "cells": g1b}
    # Gate 2
    checks, units = [], {}
    for ds, K in SYN + [("eedi_exam", 16)]:
        for f in FS:
            for cell in ("r0.8", "r0.5", "q0.05", "q0.2", "dup0.1", "phi0.01", "mix0.2", "delay5", "combined"):
                for arm in ("Ours", "B2b"):
                    runs = idx[("G2", ds, K, "sparse", "coalition", f, cell, arm)]
                    if any(v["harmful_releases"] > 0 or v["underestimate_steps"] > 0 for v in runs.values()):
                        checks.append((ds, K, f, cell, arm))
                if (ds, K) in SYN:
                    b1 = ("G01", ds, K, "sparse", "coalition", f, "base", "B1")
                    units[f"{ds}{K}/f{f}/{cell}"] = paired(
                        idx, ("G2", ds, K, "sparse", "coalition", f, cell, "Ours"), b1, "UR_normal")
    n2 = sum(v["lower"] > 0 for v in units.values())
    descr = {}
    for cell in ("q0.05", "q0.2", "dup0.1", "phi0.01", "mix0.2", "combined", "phic0.01", "phic0.05"):
        for arm in ("B2", "Ours"):
            runs = [v for (ph, ds, K, g, mo, f, ce, a), rr in idx.items() if ph == "G2" and ce == cell and a == arm
                    for v in rr.values()]
            if runs:
                descr[f"{cell}/{arm}"] = {"runs": len(runs),
                                          "runs_with_underestimate": sum(v["underestimate_steps"] > 0 for v in runs),
                                          "sum_harmful": sum(v["harmful_releases"] for v in runs)}
    out["Gate2"] = {"check_sound": "通过" if not checks else f"失败: {checks[:5]}",
                    "verdict": ("支持" if n2 >= len(units) / 2 else "不支持") if not checks else "无法判定（实现核对失败）",
                    "units_supported": n2, "units_total": len(units), "units": units, "descriptive": descr}
    # Budget violation (descriptive)
    bv = {}
    for arm in ("B0", "B1", "B2", "B2b", "B3", "B4", "Ours", "Oracle"):
        runs = [v for (ph, ds, K, g, mo, f, ce, a), rr in idx.items() if ph == "BV" and a == arm for v in rr.values()]
        bv[arm] = {"sum_harmful": sum(v["harmful_releases"] for v in runs),
                   "mean_UR": sum(v["UR_normal"] for v in runs) / len(runs)}
    out["BudgetViolation"] = bv
    return out


def decidability(rows):
    idx = index(rows)
    syn_b0 = sum(1 for k in idx if k[0] == "G01" and k[-1] == "B0" and k[1] == "synthetic")
    return {"G01_B0_keys": syn_b0, "phases": sorted({k[0] for k in idx}),
            "complete_pairs": sum(1 for k in idx if k[0] == "G01" and k[3] == "complete" and k[-1] == "Ours"),
            "g2_keys": sum(1 for k in idx if k[0] == "G2")}


def describe(rows):
    agg = defaultdict(list)
    for r in rows:
        if r["phase"] == "G01" and r["graph"] == "sparse":
            agg[(r["dataset"] + r["K"], r["mode"], r["f"], r["arm"])].append(r)
    table = []
    for (ds, mode, f, arm), rr in sorted(agg.items()):
        table.append({"dataset": ds, "mode": mode, "f": f, "arm": arm,
                      **{m: sum(float(x[m]) for x in rr) / len(rr) for m in
                         ("harmful_releases", "prop_induced", "UR_normal", "DR_normal",
                          "unneeded_refusal_rate", "VR_actual", "fallbacks", "mean_decision_ms")}})
    return table


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=HERE / "results")
    args = parser.parse_args()
    with (args.results / "raw.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    out = judge(rows)
    (args.results / "judgments.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    table = describe(rows)
    with (args.results / "summary_sparse.csv").open("w", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    print(json.dumps({k: v.get("verdict", "描述") for k, v in out.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
