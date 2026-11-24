"""Four Phase-1 figures from analysis.json (static PNG + SVG for the paper and group meeting).

  python -m experiments.cogniguard_nowm_phase1.plot --analysis <analysis.json> --out <dir>

Colors: reference palette (validated: blue/orange/aqua/yellow pass CVD, contrast WARN relieved by
axis labels and direct labels). Baselines share a neutral gray because identity is carried by the
x-axis label, not by color; the oracle is a dashed reference, never a bar.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUE, ORANGE, AQUA, YELLOW, GRAY = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#a3a29d"
BARS = [  # (analysis key, short label, color)
    ("B0 access control", "B0", GRAY),
    ("B1 budget (best b)", "B1*", GRAY),
    ("B2 fixed quota", "B2", GRAY),
    ("B3 pairwise", "B3", GRAY),
    ("B4 global union", "B4", GRAY),
    ("M1 dyn-state + single", "M1", BLUE),
    ("M2 receipts + CA-PD", "M2", AQUA),
    ("M3 CogniGuard-NoWM", "M3", ORANGE),
]
CELLS = [("low", 1), ("low", 2), ("low", 3), ("high", 1), ("high", 2), ("high", 3)]


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=7)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def bar_grid(a, metric, ylabel, title, path, oracle_metric=True):
    fig, axes = plt.subplots(2, 3, figsize=(13, 6.6), sharey=True, facecolor=SURFACE)
    for ax, (prop, k) in zip(axes.flat, CELLS):
        style(ax)
        cell = a["table"][f"{prop}/k{k}"]
        xs = range(len(BARS))
        for x, (key, _lab, color) in zip(xs, BARS):
            m = cell[key][metric]
            lo, hi = m["ci95"]
            ax.bar(x, m["mean"], width=0.72, color=color, edgecolor=SURFACE, linewidth=2, zorder=2)
            ax.errorbar(x, m["mean"], yerr=[[m["mean"] - lo], [hi - m["mean"]]], color=INK, linewidth=1,
                        capsize=2, zorder=3)
            if key == "M3 CogniGuard-NoWM":
                ax.text(x, m["mean"] + 0.03, f"{m['mean']:.3f}", ha="center", fontsize=7, color=INK)
        if oracle_metric:
            o = cell["Oracle"][metric]["mean"]
            ax.axhline(o, color=INK, linestyle="--", linewidth=1, zorder=4)
            ax.text(-0.4, 1.03, f"Oracle (dashed) = {o:.3f}", ha="left", fontsize=7, color=MUTED)
        ax.set_xticks(list(xs))
        ax.set_xticklabels([b[1] for b in BARS], fontsize=8)
        ax.set_ylim(0, 1.08)
        ax.set_title(f"{prop} propagation, k = {k}", fontsize=9, color=INK)
    for ax in axes[:, 0]:
        ax.set_ylabel(ylabel, fontsize=8, color=MUTED)
    fig.suptitle(title, fontsize=11, color=INK, x=0.01, ha="left")
    fig.text(0.01, 0.005, "B0 access control · B1* cumulative budget (pilot-fixed b) · B2 fixed quota · B3 pairwise (structural "
                          "proxy, not OCELOT) · B4 global union · M1 dynamic state + single-principal · M2 receipts + CA-PD · "
                          "M3 CogniGuard-NoWM.  Mean of 30 paired seeds, whiskers = 95% bootstrap CI; all accounting rules "
                          "read the same BGE+NLI evidence except M2.", fontsize=6.6, color=MUTED, wrap=True)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    for ext in ("png", "svg"):
        fig.savefig(path.with_suffix(f".{ext}"), dpi=200, facecolor=SURFACE)
    plt.close(fig)


def pareto(a, path):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4), sharey=True, facecolor=SURFACE)
    for ax, k in zip(axes, (1, 2, 3)):
        style(ax)
        ax.xaxis.grid(True, color=GRID, linewidth=0.8)
        pts = a["matched"][f"high/k{k}"]["points"]
        b1 = sorted([p for p in pts if p["rule"].startswith("B1") and p["layer"] == "nli"],
                    key=lambda p: int(p["rule"][5:-1]))
        ax.plot([p["harmful_rate"] for p in b1], [p["utility"] for p in b1], color=GRAY, linewidth=2, marker="o",
                markersize=4, label="B1 budget sweep (b = 2…32)", zorder=2)
        marks = [("B0", "receipts", GRAY, "s", "B0 access"), ("B2", "nli", YELLOW, "D", "B2 quota"),
                 ("B3", "nli", GRAY, "^", "B3 pairwise"), ("B4", "nli", GRAY, "v", "B4 union"),
                 ("CAPD(k=1)", "nli", BLUE, "o", "M1 state+single"),
                 (f"CAPD(k={k})", "receipts", AQUA, "o", "M2 receipts+CA-PD"),
                 (f"CAPD(k={k})", "nli", ORANGE, "*", "M3 CogniGuard-NoWM"),
                 (f"CAPD(k={k})", "true", INK, "x", "Oracle")]
        seen = set()
        for rule, layer, color, mk, lab in marks:
            if (rule, layer) in seen:
                continue
            seen.add((rule, layer))
            p = next((p for p in pts if p["rule"] == rule and p["layer"] == layer), None)
            if p is None:
                continue
            ax.scatter(p["harmful_rate"], p["utility"], color=color, marker=mk, s=110 if mk == "*" else 46,
                       edgecolor=None if mk == "x" else SURFACE, linewidth=1.5, zorder=4, label=lab)
        ax.set_xlim(-0.03, 1.03)
        ax.set_ylim(0, 1.05)
        ax.set_xlabel("Harmful release rate (lower is safer)", fontsize=8, color=MUTED)
        ax.set_title(f"high propagation, k = {k}", fontsize=9, color=INK)
    axes[0].set_ylabel("Normal-task utility", fontsize=8, color=MUTED)
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=7, frameon=False)
    fig.suptitle("Safety–utility Pareto view (same BGE+NLI evidence; top-left is better)", fontsize=11,
                 color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.1, 1, 0.94))
    for ext in ("png", "svg"):
        fig.savefig(path.with_suffix(f".{ext}"), dpi=200, facecolor=SURFACE)
    plt.close(fig)


def by_condition(a, path):
    series = [("M1 dyn-state + single", BLUE, "o"), ("M2 receipts + CA-PD", AQUA, "s"),
              ("M3 CogniGuard-NoWM", ORANGE, "*"), ("B2 fixed quota", YELLOW, "D"), ("B4 global union", GRAY, "v")]
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.6), facecolor=SURFACE)
    for col, prop in enumerate(("low", "high")):
        for row, (metric, lab) in enumerate((("harmful_rate", "Harmful release rate"), ("utility", "Normal-task utility"))):
            ax = axes[row, col]
            style(ax)
            for key, color, mk in series:
                ys = [a["table"][f"{prop}/k{k}"][key][metric]["mean"] for k in (1, 2, 3)]
                ax.plot((1, 2, 3), ys, color=color, linewidth=2, marker=mk, markersize=8 if mk == "*" else 6,
                        markeredgecolor=SURFACE, label=key)
            ax.set_xticks((1, 2, 3))
            ax.set_xlim(0.85, 3.15)
            ax.set_ylim(-0.02, 1.05)
            ax.set_xlabel("Coalition bound k", fontsize=8, color=MUTED)
            ax.set_ylabel(lab, fontsize=8, color=MUTED)
            ax.set_title(f"{prop} propagation", fontsize=9, color=INK)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=7, frameon=False)
    fig.suptitle("Performance across coalition size and unrecorded-propagation intensity", fontsize=11, color=INK,
                 x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    for ext in ("png", "svg"):
        fig.savefig(path.with_suffix(f".{ext}"), dpi=200, facecolor=SURFACE)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    x = ap.parse_args()
    a = json.loads(x.analysis.read_text())
    x.out.mkdir(parents=True, exist_ok=True)
    bar_grid(a, "harmful_rate", "Harmful release rate", "Fig. 1  Compositional leakage: harmful release rate",
             x.out / "fig1_leakage")
    bar_grid(a, "utility", "Normal-task utility", "Fig. 2  Normal-task utility", x.out / "fig2_utility")
    pareto(a, x.out / "fig3_pareto")
    by_condition(a, x.out / "fig4_conditions")
    print(x.out)


if __name__ == "__main__":
    main()
