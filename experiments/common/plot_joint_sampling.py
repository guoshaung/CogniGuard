from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS = PROJECT_ROOT / "experiments" / "results" / "joint_synergy_sampling"

METHOD_ORDER = [
    "None",
    "FOPD-only",
    "C2RAG-only",
    "HSWST-only",
    "FOPD+C2RAG",
    "FOPD+HSWST",
    "C2RAG+HSWST",
    "Full CogniGuard w/o CG",
    "Full CogniGuard+CG",
]

METHOD_LABELS = {
    "None": "None",
    "FOPD-only": "FOPD",
    "C2RAG-only": "C2-RAG",
    "HSWST-only": "HSW-ST",
    "FOPD+C2RAG": "FOPD+C2-RAG",
    "FOPD+HSWST": "FOPD+HSW-ST",
    "C2RAG+HSWST": "C2-RAG+HSW-ST",
    "Full CogniGuard w/o CG": "Full w/o CG",
    "Full CogniGuard+CG": "Full+CG",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run: python -m experiments.evaluation.eval_joint_synergy_sampling"
        )
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _to_float(value: str) -> float:
    return float(value or 0.0)


def _save(fig: plt.Figure, out_dir: Path, name: str) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for suffix in ["png", "svg"]:
        path = out_dir / f"{name}.{suffix}"
        fig.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(str(path))
    plt.close(fig)
    return paths


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "#fbfbfd",
            "axes.edgecolor": "#c8ccd7",
            "axes.grid": True,
            "grid.color": "#d9dde8",
            "grid.alpha": 0.55,
            "font.size": 10,
            "axes.titleweight": "bold",
            "axes.labelcolor": "#242936",
            "xtick.color": "#242936",
            "ytick.color": "#242936",
        }
    )


def plot_method_ci(ci_rows: list[dict[str, str]], out_dir: Path) -> list[str]:
    by_metric = {
        metric: {row["method"]: row for row in ci_rows if row["metric"] == metric}
        for metric in ["avg_JointRisk", "avg_Utility"]
    }
    methods = [method for method in METHOD_ORDER if method in by_metric["avg_JointRisk"]]
    labels = [METHOD_LABELS.get(method, method) for method in methods]
    y = list(range(len(methods)))

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2), sharey=True)
    specs = [
        ("avg_JointRisk", "Joint Risk (lower is better)", "#be4b49"),
        ("avg_Utility", "Utility (higher is better)", "#2f7d6d"),
    ]
    for ax, (metric, title, color) in zip(axes, specs):
        rows = by_metric[metric]
        means = [_to_float(rows[method]["mean"]) for method in methods]
        lows = [_to_float(rows[method]["ci95_mean_low"]) for method in methods]
        highs = [_to_float(rows[method]["ci95_mean_high"]) for method in methods]
        xerr = [
            [max(0.0, mean - low) for mean, low in zip(means, lows)],
            [max(0.0, high - mean) for mean, high in zip(means, highs)],
        ]
        ax.errorbar(
            means,
            y,
            xerr=xerr,
            fmt="o",
            color=color,
            ecolor="#575d6d",
            elinewidth=1.4,
            capsize=4,
            markersize=5,
        )
        ax.set_title(title)
        ax.set_xlim(0, 1.04)
        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.axvline(means[-1], color=color, linestyle="--", linewidth=1.0, alpha=0.5)
    fig.suptitle("Hyperparameter Sampling Robustness with 95% Bootstrap CIs", fontsize=14)
    fig.tight_layout()
    return _save(fig, out_dir, "joint_sampling_method_ci")


def plot_synergy_ci(ci_rows: list[dict[str, str]], out_dir: Path) -> list[str]:
    wanted = [
        ("synergy_gain_vs_best_pair", "Gain vs\nBest Pair", "#3f6ba5"),
        ("cg_gain", "CG\nGain", "#8967aa"),
        ("full_beats_best_pair", "Win Rate\nvs Pair", "#2f7d6d"),
        ("full_beats_best_single", "Win Rate\nvs Single", "#9a7a35"),
    ]
    by_metric = {row["metric"]: row for row in ci_rows}
    labels = [label for metric, label, _ in wanted if metric in by_metric]
    colors = [color for metric, _, color in wanted if metric in by_metric]
    means = [_to_float(by_metric[metric]["mean"]) for metric, _, _ in wanted if metric in by_metric]
    lows = [
        _to_float(by_metric[metric]["ci95_mean_low"])
        for metric, _, _ in wanted
        if metric in by_metric
    ]
    highs = [
        _to_float(by_metric[metric]["ci95_mean_high"])
        for metric, _, _ in wanted
        if metric in by_metric
    ]
    x = list(range(len(labels)))

    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    bars = ax.bar(x, means, color=colors, edgecolor="#2b2f3a", linewidth=0.6)
    ax.errorbar(
        x,
        means,
        yerr=[
            [max(0.0, mean - low) for mean, low in zip(means, lows)],
            [max(0.0, high - mean) for mean, high in zip(means, highs)],
        ],
        fmt="none",
        ecolor="#303642",
        capsize=5,
        elinewidth=1.3,
    )
    ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=9)
    ax.set_ylim(0, 1.08)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Mean with 95% bootstrap CI")
    ax.set_title("Joint Synergy Remains Stable Under Sampling")
    fig.tight_layout()
    return _save(fig, out_dir, "joint_sampling_synergy_ci")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot joint synergy sampling confidence intervals.")
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    _style()
    output_dir = args.output_dir or args.results_root / "figures"
    method_ci = _read_csv(args.results_root / "method_metric_ci.csv")
    synergy_ci = _read_csv(args.results_root / "synergy_metric_ci.csv")
    written = []
    written.extend(plot_method_ci(method_ci, output_dir))
    written.extend(plot_synergy_ci(synergy_ci, output_dir))
    print("\n".join(written))


if __name__ == "__main__":
    main()
