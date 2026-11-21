from __future__ import annotations

import argparse
import copy
import json
import random
import statistics
import tempfile
from pathlib import Path
from typing import Any

import yaml

from experiments.evaluation.eval_joint_synergy import (
    DEFAULT_CONFIG,
    PROJECT_ROOT,
    SYSTEM_VARIANTS,
    _write_csv,
    evaluate,
)
from protection.common.text_utils import write_json


DEFAULT_RESULTS = PROJECT_ROOT / "experiments" / "results" / "joint_synergy_sampling"
FULL_METHOD = "Full CogniGuard+CG"
FULL_NO_CG_METHOD = "Full CogniGuard w/o CG"
SINGLE_METHODS = ["FOPD-only", "C2RAG-only", "HSWST-only"]
PAIR_METHODS = ["FOPD+C2RAG", "FOPD+HSWST", "C2RAG+HSWST"]
METHODS = [variant.method for variant in SYSTEM_VARIANTS]


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _round(value: float) -> float:
    return round(float(value), 4)


def _uniform(rng: random.Random, low: float, high: float) -> float:
    return _round(rng.uniform(low, high))


def _randint(rng: random.Random, low: int, high: int) -> int:
    return int(rng.randint(low, high))


def _sample_dirichlet_like(
    rng: random.Random,
    base_weights: dict[str, float],
    concentration: float,
) -> dict[str, float]:
    samples = {
        key: rng.gammavariate(max(value * concentration, 1e-6), 1.0)
        for key, value in base_weights.items()
    }
    total = sum(samples.values()) or 1.0
    return {key: _round(value / total) for key, value in samples.items()}


def _jitter_positive_weights(
    rng: random.Random,
    base_weights: dict[str, float],
    ratio: float,
) -> dict[str, float]:
    return {
        key: _round(max(0.0, value * rng.uniform(1.0 - ratio, 1.0 + ratio)))
        for key, value in base_weights.items()
    }


def _sample_config(
    base_config: dict[str, Any],
    rng: random.Random,
) -> tuple[dict[str, Any], dict[str, Any]]:
    config = copy.deepcopy(base_config)

    fopd = config.setdefault("fopd", {})
    fopd["top_k_profile_records"] = _randint(rng, 1, 5)
    fopd["relevance_threshold"] = _uniform(rng, 0.05, 0.35)
    fopd["sensitivity_threshold"] = _uniform(rng, 0.50, 0.85)
    fopd_weights = fopd.setdefault("weights", {})
    fopd_weights.update(
        _sample_dirichlet_like(
            rng,
            {
                "rel": 0.50,
                "tag": 0.25,
                "confidence": 0.15,
                "recency": 0.10,
            },
            concentration=40.0,
        )
    )
    fopd_weights["sens_gate"] = _uniform(rng, 0.10, 0.35)

    attention = fopd.setdefault("attention", {})
    attention["temperature"] = _uniform(rng, 0.35, 0.80)
    attention["top_k_dimensions"] = _randint(rng, 4, 12)

    bottleneck = fopd.setdefault("bottleneck", {})
    bottleneck["max_mutual_info_bits"] = _uniform(rng, 2.0, 4.5)
    bottleneck["privacy_lambda"] = _uniform(rng, 0.30, 0.80)

    c2rag = config.setdefault("c2rag", {})
    c2rag["exposure_decay"] = _uniform(rng, 0.85, 1.0)
    c2rag["recent_window"] = _randint(rng, 3, 8)
    c2rag["high_copyright_threshold"] = _uniform(rng, 0.60, 0.85)
    c2rag["quote_copyright_threshold"] = _uniform(
        rng,
        0.25,
        min(0.50, float(c2rag["high_copyright_threshold"]) - 0.05),
    )

    quote = _uniform(rng, 0.08, 0.22)
    summary = max(_uniform(rng, 0.22, 0.40), quote + 0.05)
    outline = max(_uniform(rng, 0.35, 0.55), summary + 0.05)
    variant_threshold = max(_uniform(rng, 0.50, 0.75), outline + 0.05)
    c2rag["thresholds"] = {
        "quote": _round(quote),
        "summary": _round(min(summary, 0.95)),
        "outline": _round(min(outline, 0.95)),
        "variant": _round(min(variant_threshold, 0.95)),
    }
    c2rag["exposure_weights"] = _sample_dirichlet_like(
        rng,
        {"lcs": 0.35, "ngram": 0.25, "sem": 0.30, "focus": 0.10},
        concentration=35.0,
    )
    c2rag["score_weights"] = _jitter_positive_weights(
        rng,
        {
            "rel": 0.45,
            "context": 0.08,
            "fit": 0.20,
            "pedfit": 0.10,
            "copyright": 0.15,
            "exposure": 0.20,
            "focus": 0.10,
        },
        ratio=0.30,
    )

    variant = config.setdefault("variant", {})
    variant["max_lcs_ratio"] = _uniform(rng, 0.35, 0.55)
    variant["max_surface_sim"] = _uniform(rng, 0.55, 0.75)
    variant["numeric_shift_min"] = _randint(rng, 1, 2)
    variant["numeric_shift_max"] = _randint(rng, 4, 8)

    active_parameters = {
        "fopd.top_k_profile_records": fopd["top_k_profile_records"],
        "fopd.relevance_threshold": fopd["relevance_threshold"],
        "fopd.sensitivity_threshold": fopd["sensitivity_threshold"],
        "fopd.weights.rel": fopd_weights["rel"],
        "fopd.weights.tag": fopd_weights["tag"],
        "fopd.weights.confidence": fopd_weights["confidence"],
        "fopd.weights.recency": fopd_weights["recency"],
        "fopd.weights.sens_gate": fopd_weights["sens_gate"],
        "fopd.attention.temperature": attention["temperature"],
        "fopd.attention.top_k_dimensions": attention["top_k_dimensions"],
        "fopd.bottleneck.max_mutual_info_bits": bottleneck["max_mutual_info_bits"],
        "fopd.bottleneck.privacy_lambda": bottleneck["privacy_lambda"],
        "c2rag.exposure_decay": c2rag["exposure_decay"],
        "c2rag.recent_window": c2rag["recent_window"],
        "c2rag.high_copyright_threshold": c2rag["high_copyright_threshold"],
        "c2rag.quote_copyright_threshold": c2rag["quote_copyright_threshold"],
        "c2rag.thresholds.quote": c2rag["thresholds"]["quote"],
        "c2rag.thresholds.summary": c2rag["thresholds"]["summary"],
        "c2rag.thresholds.outline": c2rag["thresholds"]["outline"],
        "c2rag.thresholds.variant": c2rag["thresholds"]["variant"],
        "c2rag.exposure_weights.lcs": c2rag["exposure_weights"]["lcs"],
        "c2rag.exposure_weights.ngram": c2rag["exposure_weights"]["ngram"],
        "c2rag.exposure_weights.sem": c2rag["exposure_weights"]["sem"],
        "c2rag.exposure_weights.focus": c2rag["exposure_weights"]["focus"],
        "c2rag.score_weights.context": c2rag["score_weights"]["context"],
        "variant.max_lcs_ratio": variant["max_lcs_ratio"],
        "variant.max_surface_sim": variant["max_surface_sim"],
        "variant.numeric_shift_min": variant["numeric_shift_min"],
        "variant.numeric_shift_max": variant["numeric_shift_max"],
    }
    return config, active_parameters


def _average(values: list[float]) -> float:
    return sum(values) / max(len(values), 1)


def _summarize_sample(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    summary: dict[str, dict[str, float]] = {}
    for method in METHODS:
        subset = [row for row in rows if row["method"] == method]
        summary[method] = {
            "avg_PrivacyLeak": _average([float(row["PrivacyLeak"]) for row in subset]),
            "avg_CopyrightLeak": _average([float(row["CopyrightLeak"]) for row in subset]),
            "avg_AuditFailure": _average([float(row["AuditFailure"]) for row in subset]),
            "avg_CGControlLeak": _average([float(row["CGControlLeak"]) for row in subset]),
            "avg_PrivacyAxisRisk": _average([float(row["PrivacyAxisRisk"]) for row in subset]),
            "avg_CopyrightAxisRisk": _average([float(row["CopyrightAxisRisk"]) for row in subset]),
            "avg_AuditAxisRisk": _average([float(row["AuditAxisRisk"]) for row in subset]),
            "avg_JointRisk": _average([float(row["JointRisk"]) for row in subset]),
            "avg_Utility": _average([float(row["Utility"]) for row in subset]),
            "avg_TraceBindRate": _average([float(row["TraceBindRate"]) for row in subset]),
            "avg_TeachAvailability": _average([float(row["TeachAvailability"]) for row in subset]),
        }

    best_single = min(SINGLE_METHODS, key=lambda method: summary[method]["avg_JointRisk"])
    best_pair = min(PAIR_METHODS, key=lambda method: summary[method]["avg_JointRisk"])
    synergy = {
        "best_single_method": best_single,
        "best_single_joint_risk": summary[best_single]["avg_JointRisk"],
        "best_pair_method": best_pair,
        "best_pair_joint_risk": summary[best_pair]["avg_JointRisk"],
        "full_without_cg_joint_risk": summary[FULL_NO_CG_METHOD]["avg_JointRisk"],
        "full_with_cg_joint_risk": summary[FULL_METHOD]["avg_JointRisk"],
        "synergy_gain_vs_best_pair": summary[best_pair]["avg_JointRisk"]
        - summary[FULL_METHOD]["avg_JointRisk"],
        "cg_gain": summary[FULL_NO_CG_METHOD]["avg_JointRisk"]
        - summary[FULL_METHOD]["avg_JointRisk"],
        "full_beats_best_pair": float(
            summary[FULL_METHOD]["avg_JointRisk"] < summary[best_pair]["avg_JointRisk"]
        ),
        "full_beats_best_single": float(
            summary[FULL_METHOD]["avg_JointRisk"] < summary[best_single]["avg_JointRisk"]
        ),
    }
    return summary, synergy


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def _bootstrap_mean_ci(
    values: list[float],
    rng: random.Random,
    iterations: int,
) -> tuple[float, float]:
    if len(values) <= 1 or iterations <= 0:
        mean = _average(values)
        return mean, mean
    boot_means = []
    for _ in range(iterations):
        boot_sample = [values[rng.randrange(len(values))] for _ in values]
        boot_means.append(_average(boot_sample))
    return _percentile(boot_means, 0.025), _percentile(boot_means, 0.975)


def _metric_ci_rows(
    rows: list[dict[str, Any]],
    *,
    group_key: str,
    value_fields: list[str],
    bootstrap_iterations: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    groups = sorted({str(row[group_key]) for row in rows})
    ci_rows: list[dict[str, Any]] = []
    for group in groups:
        subset = [row for row in rows if str(row[group_key]) == group]
        for field in value_fields:
            values = [float(row[field]) for row in subset]
            ci_low, ci_high = _bootstrap_mean_ci(values, rng, bootstrap_iterations)
            ci_rows.append(
                {
                    group_key: group,
                    "metric": field,
                    "n": len(values),
                    "mean": _average(values),
                    "std": statistics.stdev(values) if len(values) > 1 else 0.0,
                    "min": min(values) if values else 0.0,
                    "p025": _percentile(values, 0.025),
                    "p50": _percentile(values, 0.50),
                    "p975": _percentile(values, 0.975),
                    "max": max(values) if values else 0.0,
                    "ci95_mean_low": ci_low,
                    "ci95_mean_high": ci_high,
                }
            )
    return ci_rows


def _load_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["rows"])


def evaluate_sampling(
    *,
    config_path: str | Path = DEFAULT_CONFIG,
    results_root: str | Path = DEFAULT_RESULTS,
    student_data_root: str | Path | None = None,
    teacher_data_root: str | Path | None = None,
    samples: int = 64,
    seed: int = 2026,
    bootstrap_iterations: int = 1000,
) -> dict[str, Any]:
    config_path = Path(config_path)
    results_root = Path(results_root)
    results_root.mkdir(parents=True, exist_ok=True)

    base_config = _read_yaml(config_path)
    rng = random.Random(seed)
    ci_rng = random.Random(seed + 17)

    sample_config_rows: list[dict[str, Any]] = []
    method_rows: list[dict[str, Any]] = []
    synergy_rows: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="cogniguard_joint_sampling_") as tmp:
        tmp_root = Path(tmp)
        for sample_id in range(samples):
            config, active_parameters = _sample_config(base_config, rng)

            sample_config_path = tmp_root / f"sample_{sample_id:04d}" / "config.yaml"
            sample_results_root = tmp_root / f"sample_{sample_id:04d}" / "results"
            _write_yaml(sample_config_path, config)
            evaluate(
                sample_config_path,
                sample_results_root,
                student_data_root=student_data_root,
                teacher_data_root=teacher_data_root,
            )
            rows = _load_rows(sample_results_root / "joint_synergy_results.json")
            summary, synergy = _summarize_sample(rows)

            sample_config_rows.append(
                {
                    "sample_id": sample_id,
                    "seed": seed,
                    **active_parameters,
                }
            )
            for method, values in summary.items():
                method_rows.append(
                    {
                        "sample_id": sample_id,
                        "method": method,
                        **values,
                    }
                )
            synergy_rows.append(
                {
                    "sample_id": sample_id,
                    **synergy,
                }
            )

    method_ci_rows = _metric_ci_rows(
        method_rows,
        group_key="method",
        value_fields=[
            "avg_PrivacyLeak",
            "avg_CopyrightLeak",
            "avg_AuditFailure",
            "avg_CGControlLeak",
            "avg_PrivacyAxisRisk",
            "avg_CopyrightAxisRisk",
            "avg_AuditAxisRisk",
            "avg_JointRisk",
            "avg_Utility",
            "avg_TraceBindRate",
            "avg_TeachAvailability",
        ],
        bootstrap_iterations=bootstrap_iterations,
        rng=ci_rng,
    )
    synergy_ci_rows = []
    for field in [
        "best_pair_joint_risk",
        "full_with_cg_joint_risk",
        "synergy_gain_vs_best_pair",
        "cg_gain",
        "full_beats_best_pair",
        "full_beats_best_single",
    ]:
        values = [float(row[field]) for row in synergy_rows]
        ci_low, ci_high = _bootstrap_mean_ci(values, ci_rng, bootstrap_iterations)
        synergy_ci_rows.append(
            {
                "metric": field,
                "n": len(values),
                "mean": _average(values),
                "std": statistics.stdev(values) if len(values) > 1 else 0.0,
                "min": min(values) if values else 0.0,
                "p025": _percentile(values, 0.025),
                "p50": _percentile(values, 0.50),
                "p975": _percentile(values, 0.975),
                "max": max(values) if values else 0.0,
                "ci95_mean_low": ci_low,
                "ci95_mean_high": ci_high,
            }
        )

    robustness = {
        "samples": samples,
        "seed": seed,
        "bootstrap_iterations": bootstrap_iterations,
        "full_beats_best_pair_rate": _average(
            [float(row["full_beats_best_pair"]) for row in synergy_rows]
        ),
        "full_beats_best_single_rate": _average(
            [float(row["full_beats_best_single"]) for row in synergy_rows]
        ),
        "mean_synergy_gain_vs_best_pair": _average(
            [float(row["synergy_gain_vs_best_pair"]) for row in synergy_rows]
        ),
        "mean_cg_gain": _average([float(row["cg_gain"]) for row in synergy_rows]),
    }

    _write_csv(results_root / "sampled_configs.csv", sample_config_rows)
    _write_csv(results_root / "sample_method_summary.csv", method_rows)
    _write_csv(results_root / "sample_synergy.csv", synergy_rows)
    _write_csv(results_root / "method_metric_ci.csv", method_ci_rows)
    _write_csv(results_root / "synergy_metric_ci.csv", synergy_ci_rows)
    _write_csv(results_root / "robustness_summary.csv", [robustness])
    write_json(
        results_root / "joint_synergy_sampling_results.json",
        {
            "sampled_configs": sample_config_rows,
            "method_summary": method_rows,
            "sample_synergy": synergy_rows,
            "method_metric_ci": method_ci_rows,
            "synergy_metric_ci": synergy_ci_rows,
            "robustness": robustness,
            "note": (
                "This experiment samples active FOPD/C2-RAG hyperparameters while keeping "
                "JointRisk and Utility as fixed architecture-aligned equal aggregations. "
                "It reports percentile intervals and bootstrap confidence intervals over "
                "sampled configurations."
            ),
        },
    )
    return {
        "robustness": robustness,
        "method_metric_ci": method_ci_rows,
        "synergy_metric_ci": synergy_ci_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sample CogniGuard mechanism hyperparameters for joint synergy CIs."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--student-data-root", type=Path)
    parser.add_argument("--teacher-data-root", type=Path)
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--bootstrap-iterations", type=int, default=1000)
    args = parser.parse_args()
    result = evaluate_sampling(
        config_path=args.config,
        results_root=args.results_root,
        student_data_root=args.student_data_root,
        teacher_data_root=args.teacher_data_root,
        samples=args.samples,
        seed=args.seed,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    print(result["robustness"])


if __name__ == "__main__":
    main()
