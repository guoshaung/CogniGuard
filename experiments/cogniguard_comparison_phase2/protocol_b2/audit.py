"""B2 follow-up: sample audit of the glm-5.2 reference labels (they are NOT a human gold standard).

Stratified sample of (answer, table) pairs, seed 20261125, by agreement with the joint detector:
FN (ref+, joint-) 15, FP (ref-, joint+) 12, TP 15, TN 8. `make` writes the audit sheet (CSV, blank
human column) and a reading file; the second-annotator column is filled by Claude (a different model
family) and is reported as model-model agreement only. `score` computes agreement per stratum.
"""

from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

from experiments.cogniguard_comparison_phase2.protocol_b2.critical import B2, classify, load

STRATA = {"FN": 15, "FP": 12, "TP": 15, "TN": 8}


def make(out_dir):
    ctx = load()
    answers = {ctx[7](a): a for a in ctx[0]}
    pairs = classify(ctx)
    rng = random.Random(20261125)
    rows = []
    for s, n in STRATA.items():
        pool = [p for p in pairs if (p["gold"], p["joint"]) == {"FN": (True, False), "FP": (False, True),
                                                                 "TP": (True, True), "TN": (False, False)}[s]]
        for p in rng.sample(pool, n):
            rows.append({"id": len(rows), "stratum": s, "stratum_pool": len(pool), "cls": p["cls"],
                         "scenario": p["key"][0], "goal": p["key"][1], "idx": p["key"][2], "table": p["table"],
                         "reference_glm": int(p["gold"]), "joint": int(p["joint"]), "claude": "", "human": ""})
    with open(out_dir / "audit_sheet.csv", "w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(out_dir / "audit_reading.txt", "w") as h:
        for r in rows:
            cfg = ctx[6][r["scenario"]]
            a, t = r["table"].split(".", 1)
            body = cfg["data_distribution"][a]["table"][t]["rows"]
            ans = answers[(r["scenario"], r["goal"], r["idx"])]["answer"]
            h.write(f"### {r['id']}  {r['table']}\nROWS: {json.dumps(body, ensure_ascii=False)}\nANSWER: {ans[:1500]}\n\n")
    print(len(rows))


def score(sheet):
    rows = list(csv.DictReader(open(sheet)))
    out = {}
    for s in list(STRATA) + ["all"]:
        sel = [r for r in rows if (s == "all" or r["stratum"] == s) and r["claude"] != ""]
        agree = sum(int(r["claude"]) == int(r["reference_glm"]) for r in sel)
        out[s] = {"n": len(sel), "claude_agrees_with_reference": agree, "rate": agree / len(sel) if sel else None}
    # stratum-weighted estimate of reference error over all pairs
    pools = {r["stratum"]: int(r["stratum_pool"]) for r in rows}
    tot = sum(pools.values())
    out["weighted_reference_disagreement"] = sum(pools[s] / tot * (1 - out[s]["rate"]) for s in STRATA if out[s]["rate"] is not None)
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    make(Path(sys.argv[2])) if sys.argv[1] == "make" else score(sys.argv[2])
