"""Section 6 judgments, computed from results/raw.csv and results/groups.csv."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
UTILITY_MARGIN = 0.02
REFERENCE_K = 4
BUDGET_ARMS = ("per_recipient_bits", "global_bits")
BOOTSTRAP = 5000
BOOTSTRAP_SEED = 20261123


def _f(value):
    return None if value in ("", None) else float(value)


def normalize(rows):
    out = []
    for row in rows:
        item = dict(row)
        for key in ("param", "c", "violation_rate", "UR_normal", "FAR_normal",
                    "max_coalition_bits", "L_star_bits"):
            if key in item:
                item[key] = _f(item[key])
        for key in ("K", "seed", "g", "w", "violated"):
            if key in item and item[key] not in ("", None):
                item[key] = int(item[key])
        out.append(item)
    return out


def h1(groups) -> dict:
    checked = [r for r in groups if r["arm"] == "ours" and r["g"] <= r["param"]]
    bad = sum(r["violated"] for r in checked)
    if not checked:
        return {"verdict": "无法判定", "groups": 0}
    return {"verdict": "支持" if bad == 0 else "不支持", "groups": len(checked), "violations": bad}


def h2(groups) -> dict:
    per_k = {}
    verdicts = []
    for k in sorted({r["param"] for r in groups if r["arm"] == "pairwise_only"}):
        rows = [r for r in groups if r["arm"] == "pairwise_only" and r["param"] == k]
        two = [r for r in rows if r["w"] == 2]
        large = [r for r in rows if r["w"] >= 3]
        if not two or not large:
            per_k[k] = {"verdict": "无法判定", "w2": len(two), "w3plus": len(large)}
            verdicts.append("无法判定")
            continue
        ok = sum(r["violated"] for r in two) == 0 and sum(r["violated"] for r in large) > 0
        verdict = "支持" if ok else "不支持"
        per_k[k] = {
            "verdict": verdict,
            "w2": len(two),
            "w2_violations": sum(r["violated"] for r in two),
            "w3plus": len(large),
            "w3plus_violation_rate": sum(r["violated"] for r in large) / len(large),
        }
        verdicts.append(verdict)
    return {"verdict": _combine(verdicts), "by_k": per_k}


def _cells(rows):
    cells = defaultdict(list)
    for row in rows:
        cells[(row["K"], row["c"])].append(row)
    return cells


def _mean(values):
    values = list(values)
    return sum(values) / len(values)


def eligible(cell_rows, baseline):
    ours = [r for r in cell_rows if r["arm"] == "ours" and r["param"] == REFERENCE_K]
    floor = _mean(r["UR_normal"] for r in ours) - UTILITY_MARGIN
    params = sorted({r["param"] for r in cell_rows if r["arm"] == baseline})
    keep = []
    for param in params:
        mine = [r for r in cell_rows if r["arm"] == baseline and r["param"] == param]
        if _mean(r["UR_normal"] for r in mine) >= floor:
            keep.append(param)
    return ours, keep


def paired_lower_bound(diffs) -> float:
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(diffs)
    means = sorted(_mean(diffs[rng.randrange(n)] for _ in range(n)) for _ in range(BOOTSTRAP))
    return means[int(0.025 * BOOTSTRAP)]


def h3(rows) -> dict:
    result = {}
    for baseline in BUDGET_ARMS:
        cells = {}
        verdicts = []
        for (K, c), cell_rows in sorted(_cells(rows).items()):
            ours, params = eligible(cell_rows, baseline)
            if not params:
                cells[f"K={K},c={c}"] = {"verdict": "不可比"}
                verdicts.append("不可比")
                continue
            ours_by_seed = {r["seed"]: r["violation_rate"] for r in ours}
            tested = {}
            passed = True
            for param in params:
                mine = {
                    r["seed"]: r["violation_rate"]
                    for r in cell_rows
                    if r["arm"] == baseline and r["param"] == param
                }
                diffs = [mine[s] - ours_by_seed[s] for s in sorted(ours_by_seed)]
                lower = paired_lower_bound(diffs)
                tested[str(param)] = {"mean_diff": _mean(diffs), "ci_lower": lower}
                passed &= lower > 0
            verdict = "支持" if passed else "不支持"
            cells[f"K={K},c={c}"] = {"verdict": verdict, "eligible": tested}
            verdicts.append(verdict)
        if "不支持" in verdicts:
            overall = "不支持"
        elif "支持" in verdicts:
            overall = "支持"
        else:
            overall = "无法判定"
        result[baseline] = {"verdict": overall, "cells": cells}
    overall = [result[b]["verdict"] for b in BUDGET_ARMS]
    return {"verdict": _combine(overall), "by_baseline": result}


def _combine(verdicts) -> str:
    if "不支持" in verdicts:
        return "不支持"
    if verdicts and all(v == "支持" for v in verdicts):
        return "支持"
    return "无法判定"


def decidability(rows, groups) -> dict:
    """Dry-run check. Reports counts only, never metric values or directions."""
    rows, groups = normalize(rows), normalize(groups)
    h1_groups = sum(1 for r in groups if r["arm"] == "ours" and r["g"] <= r["param"])
    h2_counts = {}
    for k in sorted({r["param"] for r in groups if r["arm"] == "pairwise_only"}):
        sel = [r for r in groups if r["arm"] == "pairwise_only" and r["param"] == k]
        h2_counts[str(k)] = {
            "w2": sum(r["w"] == 2 for r in sel),
            "w3plus": sum(r["w"] >= 3 for r in sel),
        }
    h3_counts = {}
    for baseline in BUDGET_ARMS:
        comparable = 0
        for _cell, cell_rows in _cells(rows).items():
            _ours, params = eligible(cell_rows, baseline)
            comparable += bool(params)
        h3_counts[baseline] = {"comparable_cells": comparable, "cells": len(_cells(rows))}
    return {
        "H1_groups_with_g_le_k": h1_groups,
        "H1_decidable": h1_groups > 0,
        "H2_counts": h2_counts,
        "H2_decidable": all(v["w2"] > 0 and v["w3plus"] > 0 for v in h2_counts.values()),
        "H3_counts": h3_counts,
        "H3_decidable": all(v["comparable_cells"] > 0 for v in h3_counts.values()),
    }


def describe(rows) -> list[dict]:
    """Seed means per arm, parameter and cell, for the Pareto table."""
    groups = defaultdict(list)
    for row in rows:
        groups[(row["arm"], row["param"], row["K"], row["c"])].append(row)
    table = []
    for (arm, param, K, c), items in sorted(groups.items(), key=lambda kv: (kv[0][2], kv[0][3], kv[0][0], kv[0][1] or 0)):
        table.append({
            "arm": arm, "param": param, "K": K, "c": c,
            "violation_rate": _mean(r["violation_rate"] for r in items),
            "max_coalition_bits": _mean(r["max_coalition_bits"] for r in items),
            "FAR_normal": _mean(r["FAR_normal"] for r in items),
            "UR_normal": _mean(r["UR_normal"] for r in items),
        })
    return table


def _read(path: Path):
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=HERE / "results")
    args = parser.parse_args()
    rows = normalize(_read(args.results / "raw.csv"))
    groups = normalize(_read(args.results / "groups.csv"))
    judgments = {"H1": h1(groups), "H2": h2(groups), "H3": h3(rows)}
    (args.results / "judgments.json").write_text(
        json.dumps(judgments, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    table = describe(rows)
    with (args.results / "pareto.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table[0]))
        writer.writeheader()
        for row in table:
            writer.writerow({k: f"{v:.6f}" if isinstance(v, float) else v for k, v in row.items()})
    print(json.dumps({k: v["verdict"] for k, v in judgments.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
