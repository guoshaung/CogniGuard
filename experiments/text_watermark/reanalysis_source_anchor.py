"""Re-analyze existing HSW-ST attacks with a separate source-anchor signal.

This does not relabel a missed watermark as detected. It measures whether
critical protected spans still permit source recovery after a summarization
attack, a distinct objective from blind watermark detection.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from experiments.attacks.watermark_attacks import run_all_attacks
from protection.audit_trace.src.semantic_protector import extract_protected_spans

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "experiments/results/text_watermark_selective12/run_20260906_221459_352036"
DATA = ROOT / "protection/audit_trace/data/expanded_edu_dataset.jsonl"


def score(text: str, sample: dict) -> tuple[float, int, int]:
    terms, formulas, numbers = extract_protected_spans(sample, [])
    spans = [x for x in [*terms, *formulas, *numbers] if x]
    hit = sum(x in text for x in spans)
    return (hit / len(spans) if spans else 0.0, hit, len(spans))


def main() -> None:
    samples = {r["sample_id"]: r for r in (json.loads(x) for x in DATA.read_text(encoding="utf8").splitlines() if x.strip())}
    watermarked = [json.loads(x) for x in (RUN / "watermarked_answers.jsonl").read_text(encoding="utf8").splitlines() if x.strip()]
    clean = [json.loads(x) for x in (ROOT / "protection/audit_trace/data/expanded_clean_baseline.jsonl").read_text(encoding="utf8").splitlines() if x.strip()]
    rows = []
    for index, item in enumerate(watermarked):
        sample = samples.get(item["sample_id"], item)
        attacks = run_all_attacks(item["watermarked_answer"], clean[index % len(clean)].get("draft_answer", ""), seed=42 + index)
        for attack, text in attacks.items():
            ratio, hit, total = score(text, sample)
            rows.append({"sample_id": item["sample_id"], "attack": attack, "anchor_ratio": ratio, "anchor_hits": hit, "anchor_total": total, "source_anchor_recovered": ratio >= 0.5})
    summary = []
    for attack in sorted({r["attack"] for r in rows}):
        subset = [r for r in rows if r["attack"] == attack]
        summary.append({"attack": attack, "recovered": sum(r["source_anchor_recovered"] for r in subset), "n": len(subset), "source_anchor_recovery_rate": sum(r["source_anchor_recovered"] for r in subset)/len(subset), "mean_anchor_ratio": sum(r["anchor_ratio"] for r in subset)/len(subset)})
    out = RUN / "source_anchor_reanalysis.csv"
    with out.open("w", newline="", encoding="utf8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    (RUN / "source_anchor_summary.json").write_text(json.dumps({"scope":"source-anchor recovery, not blind watermark detection","threshold":0.5,"summary":summary}, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
