"""Protocol B figure + unified table (held-out 116 scenarios).

  python -m experiments.cogniguard_comparison_phase2.protocol_b.plot_b --runs <full dir> --out <results/protocol_b>
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from experiments.cogniguard_comparison_phase2.protocol_b.analyze_b import METHODS, load, per_scenario

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COLORS = {"cot": "#a3a29d", "cotlh": "#6d6c68", "tom": "#2a78d6", "codef": "#1baf7a", "cogniguard": "#eb6834"}
LABELS = {"cot": "CoT (no defense)", "cotlh": "CoT + L + H", "tom": "ToM", "codef": "CoDef",
          "cogniguard": "CogniGuard gate"}
PILOT = {5, 40, 100}


def boot(vals, n=5000, seed=20261127):
    v = [int(x) for x in vals if x is not None]
    rng = random.Random(seed)
    ms = sorted(sum(v[rng.randrange(len(v))] for _ in v) / len(v) for _ in range(n))
    return sum(v) / len(v), ms[int(0.025 * n)], ms[int(0.975 * n) - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    R = load(a.runs)
    S = sorted({s for v in R.values() for s in v} - PILOT)
    rows = []
    for m in METHODS:
        per = per_scenario(R, m, S)
        runs = [r for g in ("sensitive", "benign") for s, r in R[(m, g)].items() if s in S]
        row = {"protocol": "B (native, glm-5.2 all roles)", "method": LABELS[m], "scenarios": len(S)}
        for key, name in (("blocked", "sensitive_blocked"), ("benign_ok", "benign_succeeded"), ("overall", "overall")):
            mu, lo, hi = boot([per[s][key] for s in S])
            row[name], row[name + "_lo"], row[name + "_hi"] = mu, lo, hi
        row["balanced"] = (row["sensitive_blocked"] + row["benign_succeeded"]) / 2
        row["harmful_release_rate(scenario)"] = 1 - row["sensitive_blocked"]
        row["calls_per_run"] = sum(r["calls"] for r in runs) / len(runs)
        row["tokens_per_run"] = sum(r["prompt_tokens"] + r["completion_tokens"] for r in runs) / len(runs)
        row["seconds_per_run"] = sum(r["seconds"] for r in runs) / len(runs)
        row["total_calls"] = sum(r["calls"] for r in runs)
        row["total_tokens"] = sum(r["prompt_tokens"] + r["completion_tokens"] for r in runs)
        row["official_code_errors"] = sum(1 for r in runs if r["error"])
        rows.append(row)
    with open(a.out / "protocol_b_unified_table.csv", "w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw={"width_ratios": [2.2, 1]}, facecolor=SURFACE)
    ax = axes[0]
    metrics = [("sensitive_blocked", "Sensitive blocked"), ("benign_succeeded", "Benign succeeded"),
               ("overall", "Overall (paired)")]
    width = 0.16
    for i, row in enumerate(rows):
        m = METHODS[i]
        xs = [j + (i - 2) * width for j in range(len(metrics))]
        ys = [row[k] for k, _ in metrics]
        err = [[row[k] - row[k + "_lo"] for k, _ in metrics], [row[k + "_hi"] - row[k] for k, _ in metrics]]
        ax.bar(xs, ys, width=width, color=COLORS[m], edgecolor=SURFACE, linewidth=1.5, label=LABELS[m], zorder=2)
        ax.errorbar(xs, ys, yerr=err, fmt="none", ecolor=INK, elinewidth=1, capsize=2, zorder=3)
    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels([n for _, n in metrics], fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Rate (held-out 116 scenarios, 95% CI)", fontsize=8, color=MUTED)
    ax.legend(fontsize=7, frameon=False, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.1))
    ax2 = axes[1]
    for i, row in enumerate(rows):
        ax2.barh(i, row["tokens_per_run"] / 1000, color=COLORS[METHODS[i]], edgecolor=SURFACE, zorder=2)
        ax2.text(row["tokens_per_run"] / 1000 + 0.4, i, f"{row['calls_per_run']:.1f} calls · {row['seconds_per_run']:.0f}s",
                 va="center", fontsize=7, color=INK)
    ax2.set_yticks(range(len(rows)))
    ax2.set_yticklabels([LABELS[m] for m in METHODS], fontsize=8)
    ax2.set_xlabel("Tokens per run (thousands)", fontsize=8, color=MUTED)
    ax2.set_xlim(0, max(r["tokens_per_run"] for r in rows) / 1000 * 1.6)
    for x in (ax, ax2):
        x.set_facecolor(SURFACE)
        for s in ("top", "right"):
            x.spines[s].set_visible(False)
        x.tick_params(colors=MUTED, labelsize=7)
        x.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID)
    ax2.xaxis.grid(True, color=GRID)
    fig.suptitle("Protocol B: official Sum Leaks multi-agent tasks, native defenses vs CogniGuard gate "
                 "(same backbone glm-5.2, official judge)", fontsize=10.5, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    for ext in ("png", "svg"):
        fig.savefig(a.out / f"fig4_protocol_b.{ext}", dpi=200, facecolor=SURFACE)
    print(json.dumps([{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()} for r in rows], indent=0)[:2500])


if __name__ == "__main__":
    main()
