from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiments.evaluation.eval_joint_synergy import (
    DEFAULT_CONFIG,
    PROJECT_ROOT,
    _clamp01,
    _write_csv,
    evaluate,
)
from protection.common.text_utils import write_json


DEFAULT_RESULTS = PROJECT_ROOT / "experiments" / "results" / "cross_layer_synergy"
MIXED_DATASET_ROOT = PROJECT_ROOT / "experiments" / "datasets" / "cogniguard_math_suite" / "mixed_math_suite"

SINGLE_BY_MECHANISM = {
    "FOPD": "FOPD-only",
    "C2RAG": "C2RAG-only",
    "HSWST": "HSWST-only",
}
PAIR_BY_MECHANISMS = {
    "FOPD+C2RAG": "FOPD+C2RAG",
    "FOPD+HSWST": "FOPD+HSWST",
    "C2RAG+HSWST": "C2RAG+HSWST",
}
FULL_NO_CG = "Full CogniGuard w/o CG"
FULL_CG = "Full CogniGuard+CG"


def _default_student_data_root() -> Path:
    mixed = MIXED_DATASET_ROOT / "student_profile" / "data"
    return mixed if mixed.exists() else PROJECT_ROOT / "protection" / "student_profile" / "data"


def _default_teacher_data_root() -> Path:
    mixed = MIXED_DATASET_ROOT / "teacher_resource" / "data"
    return mixed if mixed.exists() else PROJECT_ROOT / "protection" / "teacher_resource" / "data"


def _load_joint_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["rows"])


def _cross_metrics(row: dict[str, Any]) -> dict[str, float]:
    privacy = float(row["PrivacyLeak"])
    copyright = float(row["CopyrightLeak"])
    audit_failure = float(row["AuditFailure"])
    unauthorized = float(row["UnauthorizedAccess"])
    tamper = float(row["TamperUndetected"])
    trace_bind = float(row["TraceBindRate"])
    raw_profile = float(row.get("RawProfileSentFlag", 0.0))
    indirect = float(row.get("IndirectLeakFlag", 0.0))

    privacy_via_resource = _clamp01(
        privacy * copyright
        + 0.12 * raw_profile
        + 0.08 * indirect
        - 0.10 * trace_bind
    )
    profile_conditioned_copyright = _clamp01(
        copyright * (0.60 + 0.40 * privacy) * (1.0 - 0.25 * trace_bind)
    )
    trace_unrecoverable_cross_event = _clamp01(
        0.55 * copyright * audit_failure
        + 0.30 * privacy * tamper
        + 0.15 * (1.0 - trace_bind) * max(privacy, copyright)
    )
    cg_cross_layer_exposure = _clamp01(
        unauthorized * max(privacy, copyright)
        + 0.25 * raw_profile
    )
    cross_layer_attack_risk = _clamp01(
        0.35 * privacy_via_resource
        + 0.25 * profile_conditioned_copyright
        + 0.25 * trace_unrecoverable_cross_event
        + 0.15 * cg_cross_layer_exposure
    )
    return {
        "PrivacyViaResourceLeak": privacy_via_resource,
        "ProfileConditionedCopyrightLeak": profile_conditioned_copyright,
        "TraceUnrecoverableCrossEvent": trace_unrecoverable_cross_event,
        "cgCrossLayerExposure": cg_cross_layer_exposure,
        "CrossLayerAttackRisk": cross_layer_attack_risk,
    }


def _mean(values: list[float]) -> float:
    return sum(values) / max(len(values), 1)


def _summarize(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    methods = sorted({str(row["method"]) for row in rows})
    metric_names = [
        "PrivacyViaResourceLeak",
        "ProfileConditionedCopyrightLeak",
        "TraceUnrecoverableCrossEvent",
        "cgCrossLayerExposure",
        "CrossLayerAttackRisk",
        "Utility",
    ]
    for method in methods:
        subset = [row for row in rows if row["method"] == method]
        summary[method] = {
            f"avg_{metric}": _mean([float(row[metric]) for row in subset])
            for metric in metric_names
        }
        summary[method]["n"] = float(len(subset))
    return summary


def _expected_independent_risk(
    *,
    base_risk: float,
    summary: dict[str, dict[str, float]],
    mechanisms: list[str],
) -> float:
    if base_risk <= 0:
        return 0.0
    expected = base_risk
    for mechanism in mechanisms:
        single_method = SINGLE_BY_MECHANISM[mechanism]
        single_risk = float(summary[single_method]["avg_CrossLayerAttackRisk"])
        expected *= single_risk / base_risk
    return _clamp01(expected)


def _interaction_rows(summary: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    base_risk = float(summary["None"]["avg_CrossLayerAttackRisk"])
    rows: list[dict[str, Any]] = []
    for label, method in PAIR_BY_MECHANISMS.items():
        mechanisms = label.split("+")
        expected = _expected_independent_risk(
            base_risk=base_risk,
            summary=summary,
            mechanisms=mechanisms,
        )
        observed = float(summary[method]["avg_CrossLayerAttackRisk"])
        rows.append(
            {
                "configuration": method,
                "mechanisms": label,
                "observed_cross_layer_risk": observed,
                "expected_independent_cross_layer_risk": expected,
                "interaction_gain_vs_independence": expected - observed,
                "relative_interaction_gain": (expected - observed) / expected if expected else 0.0,
                "interaction_positive": observed < expected,
            }
        )

    expected_full = _expected_independent_risk(
        base_risk=base_risk,
        summary=summary,
        mechanisms=["FOPD", "C2RAG", "HSWST"],
    )
    observed_full = float(summary[FULL_NO_CG]["avg_CrossLayerAttackRisk"])
    observed_full_cg = float(summary[FULL_CG]["avg_CrossLayerAttackRisk"])
    rows.append(
        {
            "configuration": FULL_NO_CG,
            "mechanisms": "FOPD+C2RAG+HSWST",
            "observed_cross_layer_risk": observed_full,
            "expected_independent_cross_layer_risk": expected_full,
            "interaction_gain_vs_independence": expected_full - observed_full,
            "relative_interaction_gain": (expected_full - observed_full) / expected_full if expected_full else 0.0,
            "interaction_positive": observed_full < expected_full,
        }
    )
    rows.append(
        {
            "configuration": FULL_CG,
            "mechanisms": "FOPD+C2RAG+HSWST+CG",
            "observed_cross_layer_risk": observed_full_cg,
            "expected_independent_cross_layer_risk": expected_full,
            "interaction_gain_vs_independence": expected_full - observed_full_cg,
            "relative_interaction_gain": (expected_full - observed_full_cg) / expected_full if expected_full else 0.0,
            "cg_controller_gain": observed_full - observed_full_cg,
            "interaction_positive": observed_full_cg < expected_full,
        }
    )
    return rows


def evaluate_cross_layer_synergy(
    *,
    config_path: str | Path = DEFAULT_CONFIG,
    results_root: str | Path = DEFAULT_RESULTS,
    student_data_root: str | Path | None = None,
    teacher_data_root: str | Path | None = None,
) -> dict[str, Any]:
    results_root = Path(results_root)
    student_dir = Path(student_data_root) if student_data_root else _default_student_data_root()
    teacher_dir = Path(teacher_data_root) if teacher_data_root else _default_teacher_data_root()
    joint_results_root = results_root / "joint_base"
    evaluate(
        config_path,
        joint_results_root,
        student_data_root=student_dir,
        teacher_data_root=teacher_dir,
    )
    joint_rows = _load_joint_rows(joint_results_root / "joint_synergy_results.json")
    rows = []
    for row in joint_rows:
        rows.append({**row, **_cross_metrics(row)})

    summary = _summarize(rows)
    interactions = _interaction_rows(summary)
    full_interaction = next(row for row in interactions if row["configuration"] == FULL_CG)
    compact_summary = {
        "num_rows": len(rows),
        "base_cross_layer_risk": summary["None"]["avg_CrossLayerAttackRisk"],
        "best_pair_cross_layer_risk": min(
            summary[method]["avg_CrossLayerAttackRisk"]
            for method in PAIR_BY_MECHANISMS.values()
        ),
        "full_without_cg_cross_layer_risk": summary[FULL_NO_CG]["avg_CrossLayerAttackRisk"],
        "full_with_cg_cross_layer_risk": summary[FULL_CG]["avg_CrossLayerAttackRisk"],
        "full_interaction_gain_vs_independence": full_interaction["interaction_gain_vs_independence"],
        "full_relative_interaction_gain": full_interaction["relative_interaction_gain"],
        "cg_controller_gain": full_interaction["cg_controller_gain"],
    }

    payload = {
        "summary": summary,
        "compact_summary": compact_summary,
        "interactions": interactions,
        "rows": rows,
        "note": (
            "Cross-layer synergy uses interaction metrics such as PrivacyLeak x CopyrightLeak "
            "and CopyrightLeak x AuditFailure. Positive interaction gain means observed "
            "combined risk is lower than the multiplicative independent-risk expectation."
        ),
    }
    write_json(results_root / "cross_layer_synergy_results.json", payload)
    _write_csv(results_root / "cross_layer_rows.csv", rows)
    _write_csv(
        results_root / "cross_layer_summary.csv",
        [{"method": method, **values} for method, values in summary.items()],
    )
    _write_csv(results_root / "cross_layer_interactions.csv", interactions)
    _write_csv(results_root / "cross_layer_compact_summary.csv", [compact_summary])
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate cross-layer interaction synergy.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--student-data-root", type=Path)
    parser.add_argument("--teacher-data-root", type=Path)
    args = parser.parse_args()
    result = evaluate_cross_layer_synergy(
        config_path=args.config,
        results_root=args.results_root,
        student_data_root=args.student_data_root,
        teacher_data_root=args.teacher_data_root,
    )
    print(result["compact_summary"])


if __name__ == "__main__":
    main()
