"""Pick the E3b-v2 secrets and texts. Output stays outside the repository.

Seed 2026: sample `count` K=8 Eedi secrets; keep every unit text, one combo
text and one decoy text per secret; shuffle the eight candidates for display.
"""

from __future__ import annotations

import argparse
import csv
import os
import random
from collections import defaultdict

from experiments.capd_e3b2_20261124.common import REPO, data_root, out_dir, read_jsonl, write_jsonl

SEED = 2026


def raw_questions() -> dict:
    raw = os.environ.get("COGNIGUARD_RAW_DIR")
    folder = (raw and __import__("pathlib").Path(raw) or REPO.parent / "cogniguard_raw") / "eedi"
    with (folder / "train.csv").open(encoding="utf-8-sig", newline="") as stream:
        return {f"eedi:{row['QuestionId']}": row for row in csv.DictReader(stream)}


def build(count: int = 100, dry_run: bool = False) -> list[dict]:
    root = data_root() / "eedi_exam"
    targets = [t for t in read_jsonl(root / "targets.jsonl") if t["K"] == 8]
    pool = [t["target_id"] for t in targets]
    main_sample = sorted(random.Random(SEED).sample(pool, 100))
    if dry_run:
        # Dry-run secrets come from outside the main sample, so the main data stays unseen.
        rest = sorted(set(pool) - set(main_sample))
        chosen = sorted(random.Random(f"{SEED}/dry-run").sample(rest, count))
    else:
        chosen = main_sample[:count]
    wanted = set(chosen)
    by_id = {t["target_id"]: t for t in targets if t["target_id"] in wanted}
    truth = {r["target_id"]: r["value"] for r in read_jsonl(root / "secrets_private.jsonl")
             if r["target_id"] in wanted}
    units = defaultdict(dict)
    for u in read_jsonl(root / "units.jsonl"):
        if u["target_id"] in wanted:
            units[u["target_id"]][u["unit_id"]] = set(u["satisfied_by"])
    texts = defaultdict(list)
    for t in read_jsonl(root / "texts.jsonl"):
        if t["target_id"] in wanted:
            texts[t["target_id"]].append(t)
    questions = raw_questions()
    items = []
    for tid in chosen:
        target = by_id[tid]
        local = random.Random(f"{SEED}/{tid}")
        order = list(target["domain"])
        local.shuffle(order)
        rows = texts[tid]
        keep = [t for t in rows if t["role"] == "unit"]
        keep.append(local.choice([t for t in rows if t["role"] == "combo"]))
        keep.append(local.choice([t for t in rows if t["role"] == "decoy"]))
        views = []
        for t in keep:
            consistent = set(target["domain"]).intersection(*(units[tid][u] for u in t["gold_units"]))
            views.append({"text_id": t["text_id"], "role": t["role"], "gold_units": t["gold_units"],
                          "text": t["text"], "consistent": len(consistent),
                          "truth_consistent": truth[tid] in consistent})
        candidates = []
        for index, qid in enumerate(order, start=1):
            row = questions[qid]
            options = " ".join(f"({c}) {row['Answer' + c + 'Text']}" for c in "ABCD")
            candidates.append(f"[{index}] {row['QuestionText']}\n    Options: {options}")
        items.append({"target_id": tid, "K": 8, "order": order,
                      "truth_index": order.index(truth[tid]) + 1,
                      "candidates": "\n".join(candidates), "views": views})
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    items = build(3 if args.dry_run else args.count, args.dry_run)
    path = out_dir() / ("items_dryrun.jsonl" if args.dry_run else "items.jsonl")
    write_jsonl(path, items)
    views = sum(len(i["views"]) for i in items)
    print(path, len(items), "secrets", views, "texts")


if __name__ == "__main__":
    main()
