"""Build the human annotation sample (250 answer-table pairs) for calibrating the knowledge-state evidence.

Stratified by calibration bin (binner in stage_b.py), oversampling the bins the calibrated state depends
on: weak NLI evidence on bridge tables, and the large near-zero negative bins whose rate drives noisy-OR
accumulation. Within each stratum, witness-unit pairs (owner-policy target) come first. The 50 pairs
already in the B2 model-model audit are excluded. Seed 20261126.

Outputs (annotation/):
  sheet_A.csv, sheet_B.csv  blind sheets for two independent annotators; same items, different order;
                            no model labels, detector outputs, bins or scenario ids are shown
  key.csv                   hidden key: item id -> pair, stratum, population, sampling weight, glm label,
                            verifier answer, detector hits (do NOT give to annotators)
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from experiments.cogniguard_comparison_phase2.protocol_b2.diagnose import target_sets
from experiments.cogniguard_degc.stage_b import binner, build

HERE = Path(__file__).parent
AUDIT = HERE.parent.parent / "cogniguard_comparison_phase2" / "results" / "protocol_b2" / "audit_sheet.csv"
PLAN = {  # stratum (bin) -> sample size
    ("nli", "bridge", 2): 45, ("nli", "bridge", 1): 45, ("nli", "distinct", 2): 18,
    ("nli", "bridge", 0): 15, ("nli", "distinct", 1): 15, ("nli", "distinct", 0): 10,
    ("cos", "bridge", 1): 15, ("cos", "bridge", 0): 15, ("cos", "distinct", 1): 15, ("cos", "distinct", 0): 15,
    ("cos", "bridge", 2): 6, ("cos", "distinct", 2): 6, ("norm", "distinct"): 15, ("sem", "bridge"): 15,
}
SEED = 20261126


def main():
    answers, gold, det, runs, by_run, cfgs, key, pairs = build()
    text = {key(a): a["answer"] for a in answers}
    wit = {s: set().union(*map(set, target_sets(c, s, "policy") or [[]])) for s, c in cfgs.items()}
    done = set()
    if AUDIT.exists():
        for r in csv.DictReader(open(AUDIT)):
            done.add((int(r["scenario"]), r["goal"], int(r["idx"]), r["table"]))
    strata = defaultdict(list)
    for k, v in pairs.items():
        if k not in done:
            strata[binner(v)].append(k)
    rng = random.Random(SEED)
    items = []
    for b, n in PLAN.items():
        pool = sorted(strata[b])
        w = [k for k in pool if k[3] in wit[k[0]]]
        o = [k for k in pool if k[3] not in wit[k[0]]]
        rng.shuffle(w)
        rng.shuffle(o)
        pick = (w + o)[:n]
        for k in pick:
            items.append((b, len(pool), len(pick), k))
    rng.shuffle(items)
    keyrows, blind = [], []
    for i, (b, pop, n, k) in enumerate(items):
        sid, goal, idx, table = k
        agent, t = table.split(".", 1)
        rows = cfgs[sid]["data_distribution"][agent]["table"][t]["rows"]
        v = pairs[k]
        iid = f"H{i + 1:03d}"
        blind.append({"item": iid, "table": table, "table_rows": "\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                      "message": text[(sid, goal, idx)], "disclosed (1/0/?)": "", "notes": ""})
        keyrows.append({"item": iid, "scenario": sid, "goal": goal, "idx": idx, "table": table, "stratum": json.dumps(b),
                        "stratum_population": pop, "stratum_sample": n, "weight": round(pop / n, 4),
                        "witness_unit": int(table in wit[sid]), "glm_label": int(v["gold"]),
                        "verifier": "" if v["ver"] is None else int(v["ver"]), "norm": int(v["norm"]), "sem": int(v["sem"]),
                        "nli": "" if v["nli"] is None else round(v["nli"], 4), "cos": round(v["cos"], 4), "bridge": int(v["bridge"])})
    for name, order_seed in (("sheet_A.csv", 1), ("sheet_B.csv", 2)):
        rows = blind[:]
        random.Random(order_seed).shuffle(rows)
        with open(HERE / name, "w", newline="", encoding="utf-8-sig") as h:
            wr = csv.DictWriter(h, fieldnames=list(rows[0]))
            wr.writeheader()
            wr.writerows(rows)
    with open(HERE / "key.csv", "w", newline="", encoding="utf-8-sig") as h:
        wr = csv.DictWriter(h, fieldnames=list(keyrows[0]))
        wr.writeheader()
        wr.writerows(keyrows)
    print(len(items), "items;", sum(r["witness_unit"] for r in keyrows), "witness-unit pairs")


if __name__ == "__main__":
    main()
