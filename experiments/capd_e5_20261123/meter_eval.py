"""H4 (descriptive): LexicalMeter on the synthetic texts.

The unit store holds each unit rendered with template 0 ("Item property {f} is {v}.").
The meter's scope is the six units of the text's own target. Thresholds are the
LexicalMeter defaults (n=4, coverage 0.5, LCS 0.3).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from cogniguard.runtime.meters import LexicalMeter, UnitContentStore

from experiments.capd_e5_20261123.data import load_predicates, load_texts

HERE = Path(__file__).resolve().parent
STORE_TEMPLATE = "Item property {f} is {v}."
KS = (8, 16, 32)


def evaluate(K: int) -> dict:
    predicates = load_predicates(K)
    store = UnitContentStore(
        {ref: STORE_TEMPLATE.format(f=p["feature"], v=p["value"]) for ref, p in predicates.items()}
    )
    meter = LexicalMeter(store)
    scope_of = defaultdict(set)
    for ref in predicates:
        scope_of[ref[0]].add(ref)
    stats = {role: defaultdict(int) for role in ("unit", "combo", "decoy")}
    for text in load_texts(K):
        tid = text["target_id"]
        scope = frozenset(scope_of[tid])
        found = meter.measure(text["text"], candidate_units=scope).units
        gold = {(tid, unit_id) for unit_id in text["gold_units"]}
        s = stats[text["role"]]
        s["texts"] += 1
        if text["role"] == "decoy":
            s["flagged_texts"] += bool(found)
            s["flagged_units"] += len(found)
            continue
        s["gold_units"] += len(gold)
        s["missed_units"] += len(gold - found)
        s["texts_with_miss"] += bool(gold - found)
        s["extra_units"] += len(found - gold)
    out = {}
    for role in ("unit", "combo"):
        s = stats[role]
        out[role] = {
            "texts": s["texts"],
            "unit_miss_rate": s["missed_units"] / s["gold_units"],
            "text_miss_rate": s["texts_with_miss"] / s["texts"],
            "extra_units_per_text": s["extra_units"] / s["texts"],
        }
    d = stats["decoy"]
    out["decoy"] = {
        "texts": d["texts"],
        "false_flag_rate": d["flagged_texts"] / d["texts"],
        "flagged_units_per_text": d["flagged_units"] / d["texts"],
    }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=HERE / "results" / "meter.json")
    parser.add_argument("--counts-only", action="store_true")
    args = parser.parse_args()
    result = {str(K): evaluate(K) for K in KS}
    if args.counts_only:
        print(json.dumps({K: {r: v["texts"] for r, v in res.items()} for K, res in result.items()}))
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
