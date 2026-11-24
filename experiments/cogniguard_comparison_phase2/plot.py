"""Phase 2 figures: safety-utility Pareto, coalition-size behaviour, efficiency.

  python -m experiments.cogniguard_comparison_phase2.plot --runs <formal/runs.jsonl> --analysis <analysis.json> --out <dir>
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUE, ORANGE, AQUA, YELLOW, GRAY = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#a3a29d"
DATASETS = (("phase1", "Phase-1 world (real propagation + NLI)"), ("eedi", "Eedi exam secrets"),
            ("sumleaks", "Sum Leaks join secrets"))


def style(ax, xgrid=False):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=7)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    if xgrid:
        ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def means(runs_path):
    acc = defaultdict(lambda: defaultdict(list))
    for line in Path(runs_path).read_text().splitlines():
        r = json.loads(line)
        key = (r["dataset"], r["prop"], r["k"], r["mode"], r["rule"])
        for m in ("harmful_rate", "utility", "p50_us", "p95_us"):
            if r.get(m) is not None:
                acc[key][m].append(r[m])
    return {k: {m: sum(v) / len(v) for m, v in d.items()} for k, d in acc.items()}


def save(fig, path):
    for ext in ("png", "svg"):
        fig.savefig(path.with_suffix(f".{ext}"), dpi=200, facecolor=SURFACE)
    plt.close(fig)


def pareto(M, out):
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 8), sharey=True, facecolor=SURFACE)
    for col, (ds, title) in enumerate(DATASETS):
        for row, k in enumerate((2, 3)):
            ax = axes[row, col]
            style(ax, xgrid=True)
            pts = {r: v for (d, p, kk, mode, r), v in M.items() if (d, p, kk, mode) == (ds, "high", k, "snapshot")}
            for fam, color, label in (("OCELOT-PF[field](B=", GRAY, "OCELOT-PF field (B sweep)"),
                                      ("OCELOT-PF[trajectory](B=", "#6d6c68", "OCELOT-PF trajectory (B sweep)"),
                                      ("SumLeaks-ToM(rho=", YELLOW, "Sum Leaks ToM (rho sweep)")):
                curve = sorted((float(r[len(fam):-1]), v["harmful_rate"], v["utility"]) for r, v in pts.items()
                               if r.startswith(fam) and "harmful_rate" in v and "utility" in v)
                ax.plot([c[1] for c in curve], [c[2] for c in curve], color=color, linewidth=2, marker="o",
                        markersize=3.5, label=label, zorder=2)
            for rule, color, mk, label in (("B0-Access", GRAY, "s", "Access control"),
                                           ("SumLeaks-Local(CoT+L+H)", YELLOW, "^", "Sum Leaks local (CoT+L+H)"),
                                           ("SumLeaks-CoDef", YELLOW, "D", "Sum Leaks CoDef (= CA-PD k=1)"),
                                           (f"WS04-quota(k={k})", BLUE, "v", "Woodruff-Staddon quota"),
                                           ("CrowdControl", AQUA, "P", "Staddon crowd control (= Staddon-def)"),
                                           (f"CAPD(k={k})", ORANGE, "*", "CogniGuard-NoWM (CA-PD)")):
                v = pts.get(rule)
                if v and "harmful_rate" in v:
                    ax.scatter(v["harmful_rate"], v["utility"], color=color, marker=mk, s=130 if mk == "*" else 46,
                               edgecolor=SURFACE, linewidth=1.2, zorder=4, label=label)
            ax.set_xlim(-0.03, 1.03)
            ax.set_ylim(0, 1.05)
            ax.set_title(f"{title}, k = {k}", fontsize=9, color=INK)
            if row == 1:
                ax.set_xlabel("Harmful release rate (lower is safer)", fontsize=8, color=MUTED)
    for ax in axes[:, 0]:
        ax.set_ylabel("Task utility", fontsize=8, color=MUTED)
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=7.5, frameon=False)
    fig.suptitle("Protocol A: safety-utility under identical information (snapshot mode, high propagation; "
                 "top-left is better)", fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    save(fig, out / "fig1_pareto")


def coalition(M, points, out):
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 7), facecolor=SURFACE)
    series = [("CAPD(k=K)", ORANGE, "*", "CogniGuard-NoWM"), ("CrowdControl", AQUA, "P", "Staddon crowd control"),
              ("WS04-quota(k=K)", BLUE, "v", "WS04 quota"), ("SumLeaks-CoDef", YELLOW, "D", "Sum Leaks CoDef"),
              ("OCELOT-PF[field]@harm<=0.05", GRAY, "o", "OCELOT-PF field @ dev harm<=5%")]
    for col, (ds, title) in enumerate(DATASETS):
        for row, metric in enumerate(("harmful_rate", "utility")):
            ax = axes[row, col]
            style(ax)
            for rule, color, mk, label in series:
                ys = []
                for k in (1, 2, 3):
                    name = rule.replace("K", str(k))
                    if "@" in name:
                        b = points.get(f"{ds}/high/k{k}", {}).get("OCELOT-PF[field]", {}).get("harm<=0.05")
                        name = None if b is None else f"OCELOT-PF[field](B={b:g})"
                    v = M.get((ds, "high", k, "snapshot", name)) if name else None
                    ys.append(v.get(metric) if v else None)
                xs = [k for k, y in zip((1, 2, 3), ys) if y is not None]
                ax.plot(xs, [y for y in ys if y is not None], color=color, marker=mk, linewidth=2,
                        markersize=8 if mk == "*" else 6, markeredgecolor=SURFACE, label=label)
            ax.set_xticks((1, 2, 3))
            ax.set_ylim(-0.02, 1.05)
            ax.set_title(title, fontsize=9, color=INK)
            ax.set_ylabel("Harmful release rate" if metric == "harmful_rate" else "Task utility", fontsize=8, color=MUTED)
            if row == 1:
                ax.set_xlabel("Coalition bound k", fontsize=8, color=MUTED)
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, fontsize=7.5, frameon=False)
    fig.suptitle("Performance across coalition size (snapshot, high propagation)", fontsize=11, color=INK,
                 x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    save(fig, out / "fig2_coalition_size")


def efficiency(M, out):
    rules = [("B0-Access", "Access"), ("WS04-quota(k=K)", "WS04 quota"), ("SumLeaks-Local(CoT+L+H)", "SL local"),
             ("CrowdControl", "Crowd ctrl"), ("OCELOT-PF[field](B=2)", "OCELOT-PF field"),
             ("OCELOT-PF[trajectory](B=2)", "OCELOT-PF traj"), ("SumLeaks-CoDef", "SL CoDef"),
             ("ExactEnum(k=K)", "Exact enum"), ("CAPD(k=K)", "CA-PD")]
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4), sharey=False, facecolor=SURFACE)
    for ax, (ds, title) in zip(axes, DATASETS):
        style(ax)
        width = 0.26
        for i, (k, color) in enumerate(zip((1, 2, 3), (GRAY, BLUE, ORANGE))):
            vals = [M.get((ds, "high", k, "snapshot", r.replace("K", str(k))), {}).get("p95_us", 0) for r, _ in rules]
            ax.bar([x + (i - 1) * width for x in range(len(rules))], vals, width=width, color=color,
                   edgecolor=SURFACE, linewidth=1.5, label=f"k = {k}")
        ax.set_xticks(range(len(rules)))
        ax.set_xticklabels([lab for _, lab in rules], rotation=35, ha="right", fontsize=7)
        ax.set_title(title, fontsize=9, color=INK)
        ax.set_yscale("log")
        ax.set_ylabel("Decision latency P95 (µs, log scale)", fontsize=8, color=MUTED)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=3, fontsize=7.5, frameon=False)
    fig.suptitle("Governance decision cost (rule only; evidence detection excluded)", fontsize=11, color=INK,
                 x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    save(fig, out / "fig3_efficiency")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, type=Path)
    ap.add_argument("--points", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    M = means(a.runs)
    pts = json.loads(a.points.read_text())
    pareto(M, a.out)
    coalition(M, pts, a.out)
    efficiency(M, a.out)
    print(a.out)


if __name__ == "__main__":
    main()
