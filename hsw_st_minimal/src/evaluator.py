"""实验指标聚合并导出 CSV。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _count_kept(items: list[str], text: str) -> tuple[int, int]:
    kept = 0
    for x in items:
        if x and x in text:
            kept += 1
    return kept, len(items)


def compute_row_metrics(
    draft: str,
    watermarked: str,
    terms: list[str],
    formulas: list[str],
    numbers: list[str],
    detect_full: dict[str, Any],
    detect_after_attacks: dict[str, dict[str, Any]],
    placeholder_ok: bool,
    trace_ok: bool,
) -> dict[str, float]:
    kt, tt = _count_kept(terms, watermarked)
    kf, tf = _count_kept(formulas, watermarked)
    kn, tn = _count_kept(numbers, watermarked)
    tkr = kt / tt if tt else 1.0
    fkr = kf / tf if tf else 1.0
    nkr = kn / tn if tn else 1.0

    adr_denom = len(detect_after_attacks)
    adr_hit = sum(1 for v in detect_after_attacks.values() if v.get("is_watermarked"))
    adr = adr_hit / adr_denom if adr_denom else 0.0

    return {
        "TKR": tkr,
        "FKR": fkr,
        "NKR": nkr,
        "PlaceholderPass": 1.0 if placeholder_ok else 0.0,
        "AvgZ_single": float(detect_full.get("z_score", 0.0)),
        "TraceBindRate_single": 1.0 if trace_ok else 0.0,
        "ADR_single": adr,
    }


def aggregate_and_write_csv(
    summary_rows: list[dict[str, Any]],
    attack_rows: list[dict[str, Any]],
    out_metrics: Path,
    out_attacks: Path,
) -> None:
    out_metrics.parent.mkdir(parents=True, exist_ok=True)
    if summary_rows:
        keys = list(summary_rows[0].keys())
        with out_metrics.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(summary_rows)
    out_attacks.parent.mkdir(parents=True, exist_ok=True)
    if attack_rows:
        keys = list(attack_rows[0].keys())
        with out_attacks.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(attack_rows)
    else:
        with out_attacks.open("w", encoding="utf-8", newline="") as f:
            f.write("sample_id,attack,z_score,is_watermarked\n")


def final_summary_stats(
    watermarked_flags: list[bool],
    clean_flags: list[bool],
    attack_detected: list[bool],
    z_scores: list[float],
    placeholder_pass: list[bool],
    trace_bind: list[bool],
    tkr_list: list[float],
    fkr_list: list[float],
    nkr_list: list[float],
) -> dict[str, Any]:
    tw = len(watermarked_flags)
    wdr = sum(1 for x in watermarked_flags if x) / tw if tw else 0.0
    tc = len(clean_flags)
    fpr = sum(1 for x in clean_flags if x) / tc if tc else 0.0
    ta = len(attack_detected)
    adr = sum(1 for x in attack_detected if x) / ta if ta else 0.0
    return {
        "WDR": wdr,
        "FPR": fpr,
        "ADR": adr,
        "TKR_mean": sum(tkr_list) / len(tkr_list) if tkr_list else 0.0,
        "FKR_mean": sum(fkr_list) / len(fkr_list) if fkr_list else 0.0,
        "NKR_mean": sum(nkr_list) / len(nkr_list) if nkr_list else 0.0,
        "PlaceholderPass_mean": sum(placeholder_pass) / len(placeholder_pass) if placeholder_pass else 0.0,
        "AvgZ_mean": sum(z_scores) / len(z_scores) if z_scores else 0.0,
        "TraceBindRate_mean": sum(trace_bind) / len(trace_bind) if trace_bind else 0.0,
        "total_watermarked": tw,
        "total_clean": tc,
        "total_attacked": ta,
    }
