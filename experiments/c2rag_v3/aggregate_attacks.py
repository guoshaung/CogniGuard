from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


COPYRIGHT_ATTACKS = {
    "copyright_extraction", "adaptive_extraction", "implicit_extraction",
    "cumulative_budget_split", "reconstruction_history",
    "cross_session_extraction", "provenance_invalid_license", "audit_evasion",
    "direct_verbatim", "fragment_splitting", "paraphrase_reconstruction",
    "adaptive_feedback", "implicit_benign", "provenance_spoof",
}


def _read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def aggregate(result_root: Path) -> dict[str, Any]:
    sessions = [row for row in _read(result_root / "session_metrics.jsonl") if row["attack_family"] in COPYRIGHT_ATTACKS]
    raw = _read(result_root / "raw_results.jsonl")
    raw_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in raw:
        raw_by_key[(str(row["method"]), str(row["case_id"]))].append(row)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in sessions:
        grouped[(str(row["method"]), str(row["attack_family"]))].append(row)
    summary = []
    for (method, family), rows in sorted(grouped.items()):
        round_rows = [item for row in rows for item in raw_by_key[(method, str(row["case_id"]))]]
        summary.append({
            "method": method,
            "attack_family": family,
            "sessions": len(rows),
            "attack_success_rate": statistics.mean(float(row["reconstruction_success"]) for row in rows),
            "asr_at_10pct": statistics.mean(float(row.get("query_to_10pct_reconstruction") is not None) for row in rows),
            "asr_at_25pct": statistics.mean(float(row.get("query_to_25pct_reconstruction") is not None) for row in rows),
            "asr_at_50pct": statistics.mean(float(row.get("query_to_50pct_reconstruction") is not None) for row in rows),
            "direct_leakage_rate": statistics.mean(float(row["direct_copyright_leakage"]) for row in rows),
            "semantic_leakage_rate": statistics.mean(float(row["semantic_leakage"]) for row in rows),
            "mean_lcs_coverage": statistics.mean(float(row["lcs_coverage"]) for row in rows),
            "mean_semantic_similarity": statistics.mean(float(row["semantic_similarity"]) for row in rows),
            "mean_key_unit_recovery": statistics.mean(float(row["key_knowledge_unit_recovery"]) for row in rows),
            "mean_reconstruction_auc": statistics.mean(float(row["reconstruction_auc"]) for row in rows),
            "mean_final_exposure_severity": statistics.mean(float(row.get("final_cumulative_reconstruction", 0.0)) for row in rows),
            "mean_peak_incremental_exposure": statistics.mean(float(row.get("peak_incremental_reconstruction", 0.0)) for row in rows),
            "refusal_rate": statistics.mean(float(row["refusal"]) for row in rows),
            "mean_actual_cost": statistics.mean(float(item["actual_cost"]) for item in round_rows) if round_rows else 0.0,
        })
    _write(result_root / "attack_family_metrics.csv", summary)
    ranking = []
    for method in sorted({row["method"] for row in summary}):
        rows = [row for row in summary if row["method"] == method]
        ranking.append({
            "method": method,
            "attack_families": len(rows),
            "macro_attack_success": statistics.mean(row["attack_success_rate"] for row in rows),
            "macro_asr_at_10pct": statistics.mean(row["asr_at_10pct"] for row in rows),
            "macro_asr_at_25pct": statistics.mean(row["asr_at_25pct"] for row in rows),
            "macro_asr_at_50pct": statistics.mean(row["asr_at_50pct"] for row in rows),
            "macro_direct_leakage": statistics.mean(row["direct_leakage_rate"] for row in rows),
            "macro_semantic_leakage": statistics.mean(row["semantic_leakage_rate"] for row in rows),
            "macro_reconstruction_auc": statistics.mean(row["mean_reconstruction_auc"] for row in rows),
            "macro_final_exposure_severity": statistics.mean(row["mean_final_exposure_severity"] for row in rows),
            "macro_peak_incremental_exposure": statistics.mean(row["mean_peak_incremental_exposure"] for row in rows),
            "macro_key_unit_recovery": statistics.mean(row["mean_key_unit_recovery"] for row in rows),
            "macro_refusal_rate": statistics.mean(row["refusal_rate"] for row in rows),
            "mean_actual_cost": statistics.mean(row["mean_actual_cost"] for row in rows),
        })
    ranking.sort(key=lambda row: (row["macro_attack_success"], row["macro_reconstruction_auc"]))
    _write(result_root / "attack_method_ranking.csv", ranking)
    return {"attack_rows": len(sessions), "families": sorted({row["attack_family"] for row in summary}), "ranking": ranking}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("result_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(aggregate(args.result_root), ensure_ascii=False, indent=2))
