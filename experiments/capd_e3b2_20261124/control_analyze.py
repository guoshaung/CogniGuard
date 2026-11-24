"""Judgments for the A2 control (PREREG_E3B2C.md).

C1: exceedance share on original-template unit views (same statistic and
    threshold as H3).
C2: paired difference, paraphrase minus original, in the per-view exceedance
    indicator over unit views judged in both runs; bootstrap over secrets.
`--dry-run` prints counts only.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict

from experiments.capd_e3b2_20261124 import analyze as A
from experiments.capd_e3b2_20261124.common import HERE, data_root, out_dir, read_jsonl

BOOT_SEED = 20261125


def exceed_map(attack) -> dict:
    """(target_id, view_id) -> (exceeds by t upper bound, exceeds by point estimate)."""
    out = {}
    for (tid, vid, vtype, consistent), samples in A.attack_views(attack).items():
        if vtype != "unit" or len(samples) < A.MIN_VALID:
            continue
        threshold = 1 / consistent + A.PRIOR_MARGIN
        p = [s["p_true"] for s in samples]
        out[(tid, vid)] = (A.view_upper(p) > threshold, sum(p) / len(p) > threshold)
    return out


def share(values) -> float:
    return sum(values) / len(values) if values else float("nan")


def paired(main, control, index) -> dict:
    keys = sorted(set(main) & set(control))
    by_secret = defaultdict(list)
    for key in keys:
        by_secret[key[0]].append(int(main[key][index]) - int(control[key][index]))
    secrets = sorted(by_secret)
    def mean_diff(chosen):
        diffs = [d for s in chosen for d in by_secret[s]]
        return sum(diffs) / len(diffs)
    rng = random.Random(BOOT_SEED)
    boots = sorted(mean_diff([secrets[rng.randrange(len(secrets))] for _ in secrets])
                   for _ in range(A.BOOTSTRAP))
    return {"views": len(keys), "secrets": len(secrets), "diff": mean_diff(secrets),
            "ci_low": boots[int(0.025 * A.BOOTSTRAP)], "ci_high": boots[int(0.975 * A.BOOTSTRAP) - 1]}


def by_type(main, control) -> dict:
    ftype = {(u["target_id"], u["unit_id"]): u["predicate"]["feature"]
             for u in read_jsonl(data_root() / "eedi_exam" / "units.jsonl")}
    gold = {v["text_id"]: (i["target_id"], v["gold_units"][0])
            for i in read_jsonl(out_dir() / "items.jsonl") for v in i["views"] if v["role"] == "unit"}
    groups = defaultdict(lambda: {"main": [], "control": []})
    for key in sorted(set(main) & set(control)):
        f = ftype[gold[key[1]]]
        groups[f]["main"].append(main[key][1])
        groups[f]["control"].append(control[key][1])
    return {f: {"views": len(g["main"]), "point_exceed_paraphrase": share(g["main"]),
                "point_exceed_original": share(g["control"])} for f, g in sorted(groups.items())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    name = "items_dryrun" if args.dry_run else "items"
    control = exceed_map(read_jsonl(out_dir() / f"{name}_control_attack.jsonl"))
    if args.dry_run:
        print(json.dumps({"C1_judged_views": len(control), "C1_decidable": bool(control),
                          "C2_note": "paired against the main run; main dry-run used kimi-k3, so only C1 counts are checked here"}))
        return
    main_map = exceed_map(read_jsonl(out_dir() / f"{name}_attack.jsonl"))
    c1 = share([v[0] for v in control.values()])
    result = {
        "C1": {"verdict": "原始文本也超标" if c1 > A.FLAG_SHARE else "原始文本不超标",
               "exceed_share_t": c1, "exceed_share_point": share([v[1] for v in control.values()]),
               "judged_views": len(control)},
        "C2_t": paired(main_map, control, 0),
        "C2_point": paired(main_map, control, 1),
        "by_type_point": by_type(main_map, control),
    }
    c2 = result["C2_t"]
    result["C2_t"]["verdict"] = ("改写带出额外信息" if c2["ci_low"] > 0 else
                                 "改写比原文更少" if c2["ci_high"] < 0 else "无显著差别")
    (HERE / "results" / "control_judgments.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
