"""Offline audit: can protected spans identify their source among 12 texts?"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from experiments.attacks.watermark_attacks import run_all_attacks
from protection.audit_trace.src.semantic_protector import extract_protected_spans


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "experiments/results/text_watermark_selective12/run_20260906_221459_352036"
AUDIT_OUTPUT = ROOT / "experiments/results/text_watermark_source_anchor_audit_20261013/summary.json"
DATA = ROOT / "protection/audit_trace/data/expanded_edu_dataset.jsonl"
CLEAN = ROOT / "protection/audit_trace/data/expanded_clean_baseline.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def score(text: str, anchors: list[str]) -> tuple[float, int, int]:
    hits = sum(anchor in text for anchor in anchors)
    return (hits / len(anchors) if anchors else 0.0, hits, len(anchors))


def main() -> None:
    samples = {item["sample_id"]: item for item in read_jsonl(DATA)}
    answers = read_jsonl(RUN / "watermarked_answers.jsonl")
    clean = read_jsonl(CLEAN)
    expected = {
        (row["sample_id"], row["attack"]): row
        for row in csv.DictReader((RUN / "source_anchor_reanalysis.csv").open(encoding="utf-8", newline=""))
    }
    anchors_by_source = {}
    for answer in answers:
        source = samples.get(answer["sample_id"], answer)
        terms, formulas, numbers = extract_protected_spans(source, [])
        anchors_by_source[answer["sample_id"]] = [*terms, *formulas, *numbers]

    rows = []
    for index, answer in enumerate(answers):
        true_source = answer["sample_id"]
        attacks = run_all_attacks(
            answer["watermarked_answer"],
            clean[index % len(clean)].get("draft_answer", ""),
            seed=42 + index,
        )
        for attack, attacked_text in attacks.items():
            scores = {
                source: score(attacked_text, anchors)
                for source, anchors in anchors_by_source.items()
            }
            own_ratio, own_hits, own_total = scores[true_source]
            original = expected[(true_source, attack)]
            assert own_hits == int(original["anchor_hits"])
            assert own_total == int(original["anchor_total"])
            assert abs(own_ratio - float(original["anchor_ratio"])) < 1e-12
            other_matches = [
                source for source, (ratio, _, _) in scores.items()
                if source != true_source and ratio >= 0.5
            ]
            maximum = max(ratio for ratio, _, _ in scores.values())
            top_sources = [source for source, (ratio, _, _) in scores.items() if ratio == maximum]
            rows.append({
                "attack": attack,
                "own_ratio": own_ratio,
                "other_ratios": [
                    ratio for source, (ratio, _, _) in scores.items() if source != true_source
                ],
                "own_match": own_ratio >= 0.5,
                "wrong_source_matches": len(other_matches),
                "unique_threshold_match": own_ratio >= 0.5 and not other_matches,
                "unique_top_score": top_sources == [true_source],
            })

    grouped = defaultdict(list)
    for row in rows:
        grouped[row["attack"]].append(row)
    summary = {}
    for attack, group in sorted(grouped.items()):
        summary[attack] = {
            "n": len(group),
            "own_anchor_recovery": sum(row["own_match"] for row in group),
            "outputs_matching_at_least_one_wrong_source": sum(row["wrong_source_matches"] > 0 for row in group),
            "wrong_source_matches_out_of_132": sum(row["wrong_source_matches"] for row in group),
            "unique_threshold_attribution": sum(row["unique_threshold_match"] for row in group),
            "unique_top_score_attribution": sum(row["unique_top_score"] for row in group),
        }
    result = {
        "status": "offline_development_audit",
        "sample_count": len(answers),
        "attacks_per_sample": 5,
        "source_anchor_threshold": 0.5,
        "reproduced_existing_reanalysis_rows": len(rows),
        "summary": summary,
        "threshold_sensitivity": {
            str(threshold): {
                "own_match_out_of_60": sum(row["own_ratio"] >= threshold for row in rows),
                "outputs_with_wrong_source_match_out_of_60": sum(
                    any(ratio >= threshold for ratio in row["other_ratios"])
                    for row in rows
                ),
                "unique_threshold_attribution_out_of_60": sum(
                    row["own_ratio"] >= threshold
                    and not any(ratio >= threshold for ratio in row["other_ratios"])
                    for row in rows
                ),
            }
            for threshold in (0.5, 0.75, 1.0)
        },
    }
    AUDIT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
