"""H4 (descriptive): LexicalMeter and PredicateMeter on the Eedi texts.

Unit text shown to a meter uses the display value: misconception, subject and
construct names from the raw CSVs, the normalized answer string, or the number.
Lexical store: template 0 of the unit's type. Predicate store: slot alias =
value alias = display value, so a unit counts as disclosed when its value occurs.
Scope: the units of the text's own secret.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import defaultdict
from pathlib import Path

from cogniguard.runtime.meters import (
    LexicalMeter,
    PredicateMeter,
    UnitContentStore,
    UnitPredicate,
    UnitPredicateStore,
)

from experiments.capd_e5_20261123.data import REPO, _jsonl
from experiments.capd_e6_20261123.run import KS, data_dir

HERE = Path(__file__).resolve().parent
TEMPLATE_0 = {
    "subject": "The question comes from the topic {v}.",
    "construct": "It tests the skill: {v}.",
    "misconception": "A common wrong idea here is: {v}.",
    "answer": "The correct answer is {v}.",
    "number": "The question mentions the number {v}.",
}


def raw_names() -> dict:
    raw = Path(os.environ.get("COGNIGUARD_RAW_DIR", REPO.parent / "cogniguard_raw")) / "eedi"
    names = {"misconception": {}, "subject": {}, "construct": {}}
    with (raw / "misconception_mapping.csv").open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = re.sub(r"(?<=\d)\.0+$", "", row["MisconceptionId"].strip())
            names["misconception"][key] = row["MisconceptionName"]
    with (raw / "train.csv").open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            names["subject"][row["SubjectId"]] = row["SubjectName"]
            names["construct"][row["ConstructId"]] = row["ConstructName"]
    return names


def evaluate(K: int, names: dict) -> dict:
    root = data_dir()
    wanted = {r["target_id"] for r in _jsonl(root / "targets.jsonl") if r["K"] == K}
    shown, scope_of = {}, defaultdict(set)
    for u in _jsonl(root / "units.jsonl"):
        if u["target_id"] not in wanted:
            continue
        ref = (u["target_id"], u["unit_id"])
        f, v = u["predicate"]["feature"], u["predicate"]["value"]
        shown[ref] = (f, names[f].get(v, v) if f in names else v)
        scope_of[u["target_id"]].add(ref)
    meters = {
        "lexical": LexicalMeter(UnitContentStore(
            {ref: TEMPLATE_0[f].format(v=v) for ref, (f, v) in shown.items()})),
        "predicate_text": PredicateMeter(UnitPredicateStore(
            {ref: UnitPredicate((v,), (v,)) for ref, (_, v) in shown.items()})),
    }
    texts = [t for t in _jsonl(root / "texts.jsonl") if t["target_id"] in wanted]
    out = {}
    for name, meter in meters.items():
        s = defaultdict(lambda: defaultdict(int))
        for t in texts:
            tid = t["target_id"]
            found = meter.measure(t["text"], candidate_units=frozenset(scope_of[tid])).units
            gold = {(tid, u) for u in t["gold_units"]}
            r = s[t["role"]]
            r["texts"] += 1
            if t["role"] == "decoy":
                r["flagged"] += bool(found)
                r["extra"] += len(found)
            else:
                r["gold"] += len(gold)
                r["missed"] += len(gold - found)
                r["text_miss"] += bool(gold - found)
                r["extra"] += len(found - gold)
        out[name] = {
            role: ({"texts": r["texts"], "false_flag_rate": r["flagged"] / r["texts"],
                    "extra_per_text": r["extra"] / r["texts"]} if role == "decoy" else
                   {"texts": r["texts"], "unit_miss_rate": r["missed"] / r["gold"],
                    "text_miss_rate": r["text_miss"] / r["texts"],
                    "extra_per_text": r["extra"] / r["texts"]})
            for role, r in s.items()
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=HERE / "results" / "meter.json")
    parser.add_argument("--counts-only", action="store_true")
    args = parser.parse_args()
    names = raw_names()
    if args.counts_only:
        root = data_dir()
        counts = defaultdict(lambda: defaultdict(int))
        ks = {r["target_id"]: r["K"] for r in _jsonl(root / "targets.jsonl")}
        for t in _jsonl(root / "texts.jsonl"):
            counts[ks[t["target_id"]]][t["role"]] += 1
        print(json.dumps(counts))
        return
    result = {str(K): evaluate(K, names) for K in KS}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
