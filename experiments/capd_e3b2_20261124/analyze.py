"""Meters on the paraphrases (A1), attacker statistics (A2), and the section-5 judgments.

`--dry-run` reads the dry-run files and prints only whether each hypothesis can be
decided (counts), never a rate or a direction.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path

from cogniguard.runtime.meters import (
    LexicalMeter,
    PredicateMeter,
    UnitContentStore,
    UnitPredicate,
    UnitPredicateStore,
    _ngram_coverage,
    _normalize,
)

from experiments.capd_e3b2_20261124.common import HERE, data_root, out_dir, read_jsonl
from experiments.capd_e3b2_20261124.paraphrase import PARAPHRASERS
from experiments.capd_e6_20261123.meter_eval import TEMPLATE_0, raw_names

BOOTSTRAP = 5000
BOOT_SEED = 20261124
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776}
MISS_POINT, MISS_UPPER = 0.05, 0.10
PRIOR_MARGIN = 0.15
FLAG_SHARE = 0.10
MIN_VALID = 3


def meters():
    names = raw_names()
    shown = {}
    for u in read_jsonl(data_root() / "eedi_exam" / "units.jsonl"):
        f, v = u["predicate"]["feature"], u["predicate"]["value"]
        shown[(u["target_id"], u["unit_id"])] = (f, names[f].get(v, v) if f in names else v)
    lexical = LexicalMeter(UnitContentStore(
        {ref: TEMPLATE_0[f].format(v=v) for ref, (f, v) in shown.items()}))
    predicate = PredicateMeter(UnitPredicateStore(
        {ref: UnitPredicate((v,), (v,)) for ref, (_, v) in shown.items()}))
    scope = defaultdict(set)
    for ref in shown:
        scope[ref[0]].add(ref)
    return {"lexical": lexical, "predicate": predicate}, scope


def meter_rows(items_name: str) -> list[dict]:
    items = read_jsonl(out_dir() / f"{items_name}.jsonl")
    originals = {v["text_id"]: v for i in items for v in i["views"]}
    by_meter, scope = meters()
    rows = []
    for p in read_jsonl(out_dir() / f"{items_name}_paraphrases.jsonl"):
        original = originals[p["text_id"]]
        if not p["ok"]:
            rows.append({"text_id": p["text_id"], "target_id": p["target_id"], "role": p["role"],
                         "paraphraser": p["paraphraser"], "meter": "", "missing": 1})
            continue
        gold = {(p["target_id"], u) for u in original["gold_units"]}
        overlap = _ngram_coverage(_normalize(original["text"]), _normalize(p["text"]), 4)
        for name, meter in by_meter.items():
            found = meter.measure(p["text"], candidate_units=frozenset(scope[p["target_id"]])).units
            rows.append({"text_id": p["text_id"], "target_id": p["target_id"], "role": p["role"],
                         "paraphraser": p["paraphraser"], "meter": name, "missing": 0,
                         "gold": len(gold), "missed": len(gold - found),
                         "extra": len(found - gold), "overlap": round(overlap, 4)})
    return rows


def _boot_upper(groups: dict, ratio) -> float:
    keys = sorted(groups)
    rng = random.Random(BOOT_SEED)
    stats = sorted(ratio([groups[keys[rng.randrange(len(keys))]] for _ in keys])
                   for _ in range(BOOTSTRAP))
    return stats[int(0.975 * BOOTSTRAP) - 1]


def h1(rows) -> dict:
    out, verdicts = {}, []
    for model in PARAPHRASERS:
        per_secret = defaultdict(lambda: [0, 0])
        for r in rows:
            if r["meter"] == "predicate" and r["paraphraser"] == model and r["role"] in ("unit", "combo"):
                per_secret[r["target_id"]][0] += r["missed"]
                per_secret[r["target_id"]][1] += r["gold"]
        gold = sum(g for _, g in per_secret.values())
        if not gold:
            out[model] = {"verdict": "无法判定"}
            verdicts.append("无法判定")
            continue
        point = sum(m for m, _ in per_secret.values()) / gold
        upper = _boot_upper(per_secret, lambda s: sum(m for m, _ in s) / max(1, sum(g for _, g in s)))
        ok = point <= MISS_POINT and upper <= MISS_UPPER
        out[model] = {"verdict": "支持" if ok else "不支持", "miss_rate": point,
                      "upper95": upper, "gold_units": gold, "secrets": len(per_secret)}
        verdicts.append(out[model]["verdict"])
    overall = "支持" if all(v == "支持" for v in verdicts) else (
        "不支持" if "不支持" in verdicts else "无法判定")
    return {"verdict": overall, "by_paraphraser": out}


def view_upper(values: list[float]) -> float:
    n = len(values)
    mean = sum(values) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    return min(1.0, mean + T975[n - 1] * sd / math.sqrt(n))


def wilson_upper(hits: int, n: int) -> float:
    z = 1.96
    p = hits / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return min(1.0, (centre + margin) / (1 + z * z / n))


def attack_views(attack) -> dict:
    views = defaultdict(list)
    for r in attack:
        if r["valid"]:
            views[(r["target_id"], r["view_id"], r["view_type"], r["consistent"])].append(r)
    return views


def h2(attack) -> dict:
    per_secret = defaultdict(lambda: [0, 0])
    for r in attack:
        if r["view_type"] == "V0" and r["valid"]:
            per_secret[r["target_id"]][0] += r["hit"]
            per_secret[r["target_id"]][1] += 1
    if not per_secret:
        return {"verdict": "无法判定", "secrets": 0}
    n = sum(t for _, t in per_secret.values())
    rate = sum(h for h, _ in per_secret.values()) / n
    upper = _boot_upper(per_secret, lambda s: sum(h for h, _ in s) / max(1, sum(t for _, t in s)))
    return {"verdict": "支持" if upper <= 1 / 8 + PRIOR_MARGIN else "不支持",
            "hit_rate": rate, "upper95": upper, "samples": n, "secrets": len(per_secret)}


def h3(attack) -> dict:
    judged, flagged, too_few, wilson_flagged = 0, [], 0, 0
    for (tid, vid, vtype, consistent), samples in sorted(attack_views(attack).items()):
        if vtype != "unit":
            continue
        if len(samples) < MIN_VALID:
            too_few += 1
            continue
        judged += 1
        threshold = 1 / consistent + PRIOR_MARGIN
        upper = view_upper([s["p_true"] for s in samples])
        hits = sum(s["hit"] for s in samples)
        if wilson_upper(hits, len(samples)) > threshold:
            wilson_flagged += 1
        if upper > threshold:
            flagged.append({"view_id": vid, "consistent": consistent, "threshold": round(threshold, 4),
                            "mean_p_true": round(sum(s["p_true"] for s in samples) / len(samples), 4),
                            "upper95": round(upper, 4), "hits": hits, "samples": len(samples)})
    if not judged:
        return {"verdict": "无法判定", "judged_views": 0, "too_few_valid": too_few}
    share = len(flagged) / judged
    return {"verdict": "支持" if share <= FLAG_SHARE else "不支持", "flagged_share": share,
            "judged_views": judged, "too_few_valid": too_few, "flagged": flagged,
            "sensitivity_hit_wilson_flagged_share": wilson_flagged / judged}


def h4(attack) -> dict:
    out = {}
    for vtype in ("combo", "decoy"):
        diffs_p, diffs_hit, n = [], [], 0
        for (_, _, t, consistent), samples in attack_views(attack).items():
            if t != vtype:
                continue
            expected = 1 / consistent if vtype == "combo" else 1 / 8
            diffs_p.append(sum(s["p_true"] for s in samples) / len(samples) - expected)
            diffs_hit.append(sum(s["hit"] for s in samples) / len(samples) - expected)
            n += 1
        out[vtype] = {"views": n,
                      "mean_p_true_minus_expected": sum(diffs_p) / n if n else None,
                      "mean_hit_minus_expected": sum(diffs_hit) / n if n else None}
    return out


def meter_summary(rows) -> dict:
    out = {}
    for model in PARAPHRASERS:
        for meter in ("lexical", "predicate"):
            sel = [r for r in rows if r["paraphraser"] == model and r["meter"] == meter]
            entry = {}
            for role in ("unit", "combo", "decoy"):
                part = [r for r in sel if r["role"] == role]
                if not part:
                    continue
                if role == "decoy":
                    entry[role] = {"texts": len(part),
                                   "false_flag_rate": sum(r["extra"] > 0 for r in part) / len(part),
                                   "extra_per_text": sum(r["extra"] for r in part) / len(part)}
                else:
                    gold = sum(r["gold"] for r in part)
                    entry[role] = {"texts": len(part), "miss_rate": sum(r["missed"] for r in part) / gold,
                                   "extra_per_text": sum(r["extra"] for r in part) / len(part)}
            out[f"{model}/{meter}"] = entry
        overlaps = sorted(r["overlap"] for r in rows if r["paraphraser"] == model and r["meter"] == "predicate")
        if overlaps:
            q = lambda f: overlaps[min(len(overlaps) - 1, int(f * len(overlaps)))]
            out[f"{model}/overlap_4gram"] = {"p10": q(0.1), "p50": q(0.5), "p90": q(0.9)}
    out["missing_paraphrases"] = sum(1 for r in rows if r["missing"])
    return out


def write_csv(path: Path, rows, columns) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    name = "items_dryrun" if args.dry_run else "items"
    rows = meter_rows(name)
    attack_path = out_dir() / f"{name}_attack.jsonl"
    attack = read_jsonl(attack_path) if attack_path.exists() else []
    judgments = {"H1": h1(rows), "H2": h2(attack), "H3": h3(attack)}
    if args.dry_run:
        print(json.dumps({
            "H1": {m: {"decidable": v["verdict"] != "无法判定", "gold_units": v.get("gold_units", 0)}
                   for m, v in judgments["H1"]["by_paraphraser"].items()},
            "H2": {"decidable": judgments["H2"]["verdict"] != "无法判定",
                   "secrets": judgments["H2"]["secrets"]},
            "H3": {"decidable": judgments["H3"]["verdict"] != "无法判定",
                   "judged_views": judgments["H3"]["judged_views"],
                   "too_few_valid": judgments["H3"]["too_few_valid"]},
            "H4_views": {k: v["views"] for k, v in h4(attack).items()},
            "invalid_attack_samples": sum(not r["valid"] for r in attack),
            "missing_paraphrases": sum(1 for r in rows if r["missing"]),
        }, indent=2, ensure_ascii=False))
        return
    results = HERE / "results"
    write_csv(results / "meter.csv", rows, ("text_id", "role", "paraphraser", "meter", "missing",
                                            "gold", "missed", "extra", "overlap"))
    write_csv(results / "attack.csv", attack, ("target_id", "view_id", "view_type", "sample",
                                               "valid", "choice", "hit", "p_true", "consistent"))
    judgments["H4"] = h4(attack)
    judgments["meters"] = meter_summary(rows)
    (results / "judgments.json").write_text(json.dumps(judgments, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    print(json.dumps({k: v.get("verdict", "") for k, v in judgments.items() if k.startswith("H")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
