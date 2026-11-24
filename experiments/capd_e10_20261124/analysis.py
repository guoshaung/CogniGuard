"""E10 judgments (section 5 of PREREG_E10.md)."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOOT, BOOT_SEED = 5000, 20261124


def lower(values):
    rng = random.Random(BOOT_SEED)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(BOOT))
    return means[int(0.025 * BOOT)]


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def index(rows):
    idx = defaultdict(dict)
    for r in rows:
        idx[(r["dataset"], int(float(r["K"])), float(r["c"]), r["arm"], str(r["param"]))][int(r["seed"])] = r
    return idx


def pkey(arm, p):
    if p is None:
        return ""
    return str(float(p)) if arm == "union_view" else str(int(p))


def cells(idx):
    return sorted({(k[0], k[1], k[2]) for k in idx})


def paired(idx, cell, a, b, metric):
    A, B = idx[cell + a], idx[cell + b]
    pairs = [(_num(A[s][metric]), _num(B[s][metric])) for s in sorted(set(A) & set(B))]
    d = [x - y for x, y in pairs if x is not None and y is not None]
    if not d:
        return None
    return {"mean_diff": sum(d) / len(d), "lower": lower(d), "n": len(d)}


def judge(rows, groups):
    idx = index(rows)
    out = {}
    q = [g for g in groups if g["arm"] == "ws04_quota" and int(g["g"]) <= int(float(g["param"]))]
    out["H0"] = {"verdict": "支持" if q and all(int(g["violated"]) == 0 for g in q) else ("无法判定" if not q else "不支持"),
                 "groups": len(q), "violations": sum(int(g["violated"]) for g in q)}
    u = [g for g in groups if g["arm"] == "union_view" and float(g["param"]) == 0.0]
    out["H1"] = {"verdict": "支持" if u and all(int(g["violated"]) == 0 for g in u) else "不支持",
                 "groups": len(u), "violations": sum(int(g["violated"]) for g in u)}
    hq, verdicts = {}, []
    for cell in cells(idx):
        for k in (2, 3, 4):
            res = paired(idx, cell, ("ours", pkey("ours", k)), ("ws04_quota", pkey("ws04_quota", k)), "UR_normal")
            strat = {m: paired(idx, cell, ("ours", pkey("ours", k)), ("ws04_quota", pkey("ws04_quota", k)), m)
                     for m in ("UR_w2", "UR_w3plus", "CR_complete", "DR_normal", "gini_user_UR")}
            v = "支持" if res and res["lower"] > 0 else "不支持"
            verdicts.append(v)
            hq[f"{cell[0]}{cell[1]}/c{cell[2]}/k{k}"] = {"verdict": v, "UR": res, **strat}
    out["H-Q"] = {"verdict": "支持" if all(v == "支持" for v in verdicts) else "不支持",
                  "cells_supported": sum(v == "支持" for v in verdicts), "cells_total": len(verdicts), "cells": hq}
    h2 = {}
    for cell in cells(idx):
        for k in (2, 3, 4):
            h2[f"{cell[0]}{cell[1]}/c{cell[2]}/k{k}"] = paired(idx, cell, ("ours", pkey("ours", k)),
                                                             ("union_view", "0.0"), "UR_normal")
    out["H2_descriptive"] = h2
    return out


def decidability(rows, groups):
    idx = index(rows)
    return {"cells": len(cells(idx)),
            "quota_groups_g_le_k": sum(1 for g in groups if g["arm"] == "ws04_quota" and int(g["g"]) <= int(g["param"])),
            "union0_groups": sum(1 for g in groups if g["arm"] == "union_view" and float(g["param"]) == 0.0),
            "strata_nonempty": {s: sum(1 for r in rows if r[f"n_{s}"]) for s in ("w2", "w3plus")}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", type=Path, default=HERE / "results")
    a = p.parse_args()
    rows = list(csv.DictReader((a.results / "raw.csv").open()))
    groups = list(csv.DictReader((a.results / "groups.csv").open()))
    out = judge(rows, groups)
    (a.results / "judgments.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v.get("verdict", "描述") if isinstance(v, dict) and "verdict" in v else "描述"
                      for k, v in out.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
