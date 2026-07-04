from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS = PROJECT_ROOT / "experiments" / "results" / "joint_synergy"
DEFAULT_OUTPUT = DEFAULT_RESULTS / "figures"

METHOD_ORDER = [
    "None",
    "FOPD-only",
    "C2RAG-only",
    "HSWST-only",
    "FOPD+C2RAG",
    "FOPD+HSWST",
    "C2RAG+HSWST",
    "Full CogniGuard w/o TPCS",
    "Full CogniGuard+TPCS",
]

METHOD_LABELS = {
    "None": "None",
    "FOPD-only": "FOPD",
    "C2RAG-only": "C2-RAG",
    "HSWST-only": "HSW-ST",
    "FOPD+C2RAG": "FOPD+C2",
    "FOPD+HSWST": "FOPD+HSW",
    "C2RAG+HSWST": "C2+HSW",
    "Full CogniGuard w/o TPCS": "Full w/o TPCS",
    "Full CogniGuard+TPCS": "Full+TPCS",
}

RISK_COMPONENTS = [
    ("avg_PrivacyLeak", "Privacy"),
    ("avg_CopyrightLeak", "Copyright"),
    ("avg_AuditFailure", "Audit"),
    ("avg_UnauthorizedAccess", "Unauthorized"),
    ("avg_TamperUndetected", "Tamper"),
    ("avg_JointRisk", "JointRisk"),
    ("avg_Utility", "Utility"),
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run: python -m experiments.evaluation.eval_joint_synergy"
        )
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ordered_summary(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_method = {row["method"]: row for row in rows}
    return [by_method[method] for method in METHOD_ORDER if method in by_method]


def _save(fig: plt.Figure, out_dir: Path, stem: str) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for suffix in ("png", "svg"):
        path = out_dir / f"{stem}.{suffix}"
        fig.savefig(path, dpi=220, bbox_inches="tight")
        written.append(str(path.resolve()))
    plt.close(fig)
    return written


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#d0d7de",
            "axes.labelcolor": "#24292f",
            "xtick.color": "#57606a",
            "ytick.color": "#57606a",
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.grid": True,
            "grid.color": "#d8dee4",
            "grid.alpha": 0.45,
        }
    )


def plot_joint_risk_utility(summary_rows: list[dict[str, str]], out_dir: Path) -> list[str]:
    rows = _ordered_summary(summary_rows)
    labels = [METHOD_LABELS.get(row["method"], row["method"]) for row in rows]
    risk = [_to_float(row["avg_JointRisk"]) for row in rows]
    utility = [_to_float(row["avg_Utility"]) for row in rows]

    x = np.arange(len(rows))
    width = 0.38
    fig, ax = plt.subplots(figsize=(12, 5.6))
    risk_bars = ax.bar(
        x - width / 2,
        risk,
        width,
        label="Joint risk (lower is better)",
        color="#e76f51",
    )
    utility_bars = ax.bar(
        x + width / 2,
        utility,
        width,
        label="Utility (higher is better)",
        color="#2a9d8f",
    )
    ax.set_title("Joint Protection Effect: Risk Drops While Utility Remains Usable")
    ax.set_ylabel("Score")
    ax.set_ylim(0, 1.08)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.legend(loc="upper right", frameon=False)
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    ax.bar_label(risk_bars, fmt="%.2f", padding=2, fontsize=8)
    ax.bar_label(utility_bars, fmt="%.2f", padding=2, fontsize=8)
    ax.text(
        len(rows) - 1.55,
        0.12,
        "Full+TPCS\nlowest risk",
        color="#0a7c59",
        fontsize=10,
        weight="bold",
    )
    return _save(fig, out_dir, "joint_risk_utility_bar")


def plot_risk_component_heatmap(summary_rows: list[dict[str, str]], out_dir: Path) -> list[str]:
    rows = _ordered_summary(summary_rows)
    labels = [METHOD_LABELS.get(row["method"], row["method"]) for row in rows]
    metric_labels = [label for _, label in RISK_COMPONENTS]
    matrix = np.array(
        [[_to_float(row[key]) for key, _ in RISK_COMPONENTS] for row in rows],
        dtype=float,
    )

    fig, ax = plt.subplots(figsize=(11.8, 6.4))
    im = ax.imshow(matrix, cmap="RdYlGn_r", vmin=0, vmax=1, aspect="auto")
    ax.set_title("Risk Component Heatmap Across Mechanism Combinations")
    ax.set_xticks(np.arange(len(metric_labels)))
    ax.set_xticklabels(metric_labels, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels)
    for row_idx in range(matrix.shape[0]):
        for col_idx in range(matrix.shape[1]):
            value = matrix[row_idx, col_idx]
            color = "white" if value > 0.62 else "#24292f"
            ax.text(col_idx, row_idx, f"{value:.2f}", ha="center", va="center", color=color, fontsize=8)
    cbar = fig.colorbar(im, ax=ax, shrink=0.86)
    cbar.set_label("Score")
    ax.grid(False)
    return _save(fig, out_dir, "joint_risk_component_heatmap")


def plot_synergy_gain(summary_rows: list[dict[str, str]], gain_rows: list[dict[str, str]], out_dir: Path) -> list[str]:
    by_method = {row["method"]: row for row in summary_rows}
    gain = gain_rows[0] if gain_rows else {}
    best_single = gain.get("best_single_method", "FOPD-only")
    best_pair = gain.get("best_pair_method", "FOPD+HSWST")
    path_methods = [
        "None",
        best_single,
        best_pair,
        "Full CogniGuard w/o TPCS",
        "Full CogniGuard+TPCS",
    ]
    labels = [
        "None",
        f"Best single\n{METHOD_LABELS.get(best_single, best_single)}",
        f"Best pair\n{METHOD_LABELS.get(best_pair, best_pair)}",
        "Full\nw/o TPCS",
        "Full\n+TPCS",
    ]
    values = [_to_float(by_method[method]["avg_JointRisk"]) for method in path_methods]
    x = np.arange(len(path_methods))

    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    ax.plot(x, values, color="#3a5a98", marker="o", linewidth=2.5, markersize=8)
    ax.fill_between(x, values, [1.0] * len(values), color="#3a5a98", alpha=0.08)
    ax.set_title("Synergy Gain: Full CogniGuard Beats the Best Two-Module System")
    ax.set_ylabel("Joint risk (lower is better)")
    ax.set_ylim(0, 1.08)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    for xi, value in zip(x, values):
        ax.text(xi, value + 0.035, f"{value:.3f}", ha="center", va="bottom", fontsize=9)

    synergy_gain = _to_float(gain.get("synergy_gain_vs_best_pair"))
    tpcs_gain = _to_float(gain.get("tpcs_gain"))
    ax.annotate(
        f"Synergy gain vs best pair = {synergy_gain:.3f}",
        xy=(4, values[-1]),
        xytext=(2.25, 0.18),
        arrowprops={"arrowstyle": "->", "color": "#0a7c59", "lw": 1.5},
        color="#0a7c59",
        fontsize=10,
        weight="bold",
    )
    ax.annotate(
        f"TPCS gain = {tpcs_gain:.3f}",
        xy=(4, values[-1]),
        xytext=(3.08, values[-2] + 0.12),
        arrowprops={"arrowstyle": "->", "color": "#9a6700", "lw": 1.2},
        color="#9a6700",
        fontsize=9,
    )
    return _save(fig, out_dir, "joint_synergy_gain_bridge")


def plot_risk_reduction(risk_rows: list[dict[str, str]], out_dir: Path) -> list[str]:
    by_method = {row["method"]: row for row in risk_rows}
    rows = [by_method[method] for method in METHOD_ORDER if method in by_method]
    labels = [METHOD_LABELS.get(row["method"], row["method"]) for row in rows]
    reduction = [_to_float(row["risk_reduction_rate_vs_none"]) for row in rows]
    colors = ["#d0d7de" if value <= 0 else "#6f42c1" for value in reduction]

    fig, ax = plt.subplots(figsize=(11.2, 5.2))
    bars = ax.bar(np.arange(len(rows)), reduction, color=colors)
    ax.set_title("Joint Risk Reduction Compared with No Protection")
    ax.set_ylabel("Reduction rate")
    ax.set_ylim(0, 0.82)
    ax.set_xticks(np.arange(len(rows)))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    ax.bar_label(bars, labels=[f"{value:.0%}" for value in reduction], padding=2, fontsize=8)
    return _save(fig, out_dir, "joint_risk_reduction_bar")


def generate_figures(results_root: Path = DEFAULT_RESULTS, output_dir: Path = DEFAULT_OUTPUT) -> list[str]:
    _style()
    summary_rows = _read_csv(results_root / "joint_synergy_summary.csv")
    risk_rows = _read_csv(results_root / "joint_risk_reduction.csv")
    gain_rows = _read_csv(results_root / "joint_synergy_gain.csv")
    written: list[str] = []
    written.extend(plot_joint_risk_utility(summary_rows, output_dir))
    written.extend(plot_risk_component_heatmap(summary_rows, output_dir))
    written.extend(plot_synergy_gain(summary_rows, gain_rows, output_dir))
    written.extend(plot_risk_reduction(risk_rows, output_dir))
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate paper-ready figures for joint synergy results.")
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    written = generate_figures(args.results_root, args.output_dir)
    print("\n".join(written))


if __name__ == "__main__":
    main()
