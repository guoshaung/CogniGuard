from __future__ import annotations

import argparse
import csv
import copy
from pathlib import Path
from typing import Any

from backend.app.compliance import (
    build_compliance_state,
    build_data_categories,
    evaluate_compliance_policy,
    sanitize_context_card,
)
from experiments.baselines.privacy_baselines import build_privacy_baseline_rows
from protection.common.text_utils import read_jsonl, write_json
from protection.student_profile.src.fopd.context_card import build_context_card
from protection.student_profile.src.fopd.fopd_metrics import compute_fopd_metrics
from protection.student_profile.src.fopd.profile_selector import ProfileSelector, ScoredProfileRecord
from protection.student_profile.src.fopd.task_parser import parse_task
from protection.student_profile.src.pipeline.run_demo import load_config, load_profiles


def _csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return "|".join(f"{key}={item}" for key, item in value.items())
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key, "")) for key in fieldnames})


def _variant_config(
    base_config: dict[str, Any],
    *,
    use_enhanced: bool,
    use_orthogonal: bool = True,
    use_task_attention: bool = True,
    use_bottleneck: bool = True,
) -> dict[str, Any]:
    config = copy.deepcopy(base_config)
    fopd = config.setdefault("fopd", {})
    fopd["use_enhanced_fopd"] = use_enhanced
    fopd.setdefault("components", {}).update(
        {
            "use_orthogonal": use_orthogonal,
            "use_task_attention": use_task_attention,
            "use_bottleneck": use_bottleneck,
        }
    )
    return config


def _metric_row(
    method: str,
    profile: Any,
    task: Any,
    context_card: str,
    selected: list[ScoredProfileRecord],
    **extra: Any,
) -> dict[str, Any]:
    row = {
        "method": method,
        "request_id": task.request_id,
        "student_id": task.student_id,
        "selected_ids": [item.record.record_id for item in selected],
        **compute_fopd_metrics(profile, task, context_card, selected),
    }
    row.update(extra)
    return row


def _run_fopd_method(
    method: str,
    config: dict[str, Any],
    profile: Any,
    task: Any,
) -> dict[str, Any]:
    selector = ProfileSelector(config)
    selected = selector.select(profile, task)
    card, redaction_log = build_context_card(profile, task, selected)
    return _metric_row(
        method,
        profile,
        task,
        card,
        selected,
        RedactionCount=len(redaction_log),
        ComplianceBlockedCount=0,
        ComplianceDecision="not_applied",
    )


def _run_tpcs_policy_row(
    config: dict[str, Any],
    profile: Any,
    task: Any,
) -> dict[str, Any]:
    selector = ProfileSelector(config)
    selected = selector.select(profile, task)
    card, redaction_log = build_context_card(profile, task, selected)
    payload = {
        "student_name": f"student-{profile.student_id}",
        "request_id": task.request_id,
        "knowledge": task.knowledge,
        "difficulty": task.difficulty,
        "context_card": card,
    }
    state = build_compliance_state(
        jurisdiction="US",
        education_stage="K-12",
        student_age=14,
        school_managed_account=True,
        parental_consent="not_required",
        school_authorization="granted",
        third_party_model_use_allowed=True,
    )
    categories = build_data_categories(payload, payload_kind="context_card")
    policy = evaluate_compliance_policy(
        {
            "action": "third_party_call",
            "actor_role": "system",
            "data_scope": "context_card",
            "purpose": "teaching",
        },
        state,
        categories,
    )
    sanitized_payload = sanitize_context_card(payload, categories)
    sanitized_card = str(sanitized_payload.get("context_card", ""))
    return _metric_row(
        "EnhancedFOPD+TPCS",
        profile,
        task,
        sanitized_card,
        selected,
        RedactionCount=len(redaction_log),
        ComplianceBlockedCount=len(policy["blocked_fields"]),
        ComplianceDecision=policy["decision"],
        ThirdPartyModelPolicy=policy["third_party_model_policy"],
        BlockedFields=policy["blocked_fields"],
        AllowedFields=policy["allowed_fields"],
    )


def evaluate(config_path: str | Path) -> dict[str, Any]:
    config = load_config(config_path)
    root = Path(config_path).resolve().parent.parent
    project_root = Path(__file__).resolve().parents[2]
    output_root = project_root / "experiments" / "results" / "evaluation"
    ablation_root = project_root / "experiments" / "results" / "ablation"
    baselines_root = project_root / "experiments" / "results" / "baselines"
    profiles = load_profiles(root / "data/profiles.jsonl")
    questions = read_jsonl(root / "data/student_questions.jsonl")
    rows: list[dict[str, Any]] = []

    fopd_methods = [
        (
            "BasicFOPD",
            _variant_config(config, use_enhanced=False),
        ),
        (
            "EnhancedFOPD-Full",
            _variant_config(config, use_enhanced=True),
        ),
        (
            "EnhancedFOPD-w/o-Orthogonal",
            _variant_config(config, use_enhanced=True, use_orthogonal=False),
        ),
        (
            "EnhancedFOPD-w/o-TaskAttention",
            _variant_config(config, use_enhanced=True, use_task_attention=False),
        ),
        (
            "EnhancedFOPD-w/o-Bottleneck",
            _variant_config(config, use_enhanced=True, use_bottleneck=False),
        ),
    ]

    for qrow in questions:
        task = parse_task(qrow)
        profile = profiles[task.student_id]

        rows.append(
            {
                "method": "NoProfile",
                "request_id": task.request_id,
                "student_id": task.student_id,
                "selected_ids": [],
                "CardLen": 0,
                "SelectedCount": 0,
                "PER": 0.0,
                "TaskCoverage": 0.0,
                "SensitiveLeakFlag": 0,
                "RedactionCount": 0,
                "ComplianceBlockedCount": 0,
                "ComplianceDecision": "not_applied",
            }
        )

        full_selected = [
            ScoredProfileRecord(record=r, score=1.0, components={})
            for r in profile.profile_records
        ]
        full_card = "\n".join(str(r.value) for r in profile.profile_records) + "\n" + str(profile.local_only_fields)
        rows.append(
            _metric_row(
                "FullProfile",
                profile,
                task,
                full_card,
                full_selected,
                RedactionCount=0,
                ComplianceBlockedCount=0,
                ComplianceDecision="not_applied",
            )
        )

        rule_selected = [
            ScoredProfileRecord(record=r, score=1.0, components={})
            for r in profile.profile_records
            if r.type in {"mastery", "error_pattern", "preference"}
        ][:3]
        rule_card, rule_redactions = build_context_card(profile, task, rule_selected)
        rows.append(
            _metric_row(
                "RuleSummary",
                profile,
                task,
                rule_card,
                rule_selected,
                RedactionCount=len(rule_redactions),
                ComplianceBlockedCount=0,
                ComplianceDecision="not_applied",
            )
        )
        rows.extend(
            build_privacy_baseline_rows(
                profile=profile,
                task=task,
                config=config,
                metric_row_builder=_metric_row,
            )
        )

        for method, method_config in fopd_methods:
            rows.append(_run_fopd_method(method, method_config, profile, task))
        rows.append(_run_tpcs_policy_row(_variant_config(config, use_enhanced=True), profile, task))

    summary: dict[str, Any] = {}
    for method in sorted({r["method"] for r in rows}):
        subset = [r for r in rows if r["method"] == method]
        summary[method] = {
            "avg_PER": sum(float(r["PER"]) for r in subset) / len(subset),
            "avg_TaskCoverage": sum(float(r["TaskCoverage"]) for r in subset) / len(subset),
            "avg_SelectedCount": sum(float(r["SelectedCount"]) for r in subset) / len(subset),
            "avg_CardLen": sum(float(r["CardLen"]) for r in subset) / len(subset),
            "avg_ComplianceBlockedCount": sum(float(r.get("ComplianceBlockedCount", 0)) for r in subset) / len(subset),
            "pii_leak_count": sum(int(r.get("PIILeakFlag", 0)) for r in subset),
            "indirect_leak_count": sum(int(r.get("IndirectLeakFlag", 0)) for r in subset),
            "raw_profile_sent_rate": sum(float(r.get("RawProfileSentFlag", 0)) for r in subset) / len(subset),
            "third_party_raw_profile_rate": sum(float(r.get("ThirdPartyRawProfileRate", 0)) for r in subset) / len(subset),
            "unauthorized_access_block_rate": sum(float(r.get("UnauthorizedAccessBlocked", 0)) for r in subset) / len(subset),
            "leak_count": sum(int(r["SensitiveLeakFlag"]) for r in subset),
    }

    payload = {
        "rows": rows,
        "summary": summary,
        "ablation_note": (
            "EnhancedFOPD-Full is compared with orthogonal privacy gating, task attention, "
            "information bottleneck, and TPCS compliance policy ablations."
        ),
        "baseline_note": (
            "External privacy baselines include PII-Redaction, PresidioStyle-PII-Masking, "
            "RBAC-only, ABAC-PurposeOnly, DP-NoisyTopK, and LocalOnly-NoThirdParty."
        ),
    }
    write_json(output_root / "eval_fopd.json", payload)
    write_json(ablation_root / "fopd_component_ablation.json", payload)
    write_json(baselines_root / "privacy_baseline_comparison.json", payload)
    summary_rows = [{"method": method, **values} for method, values in summary.items()]
    _write_csv(ablation_root / "fopd_component_ablation_rows.csv", rows)
    _write_csv(ablation_root / "fopd_component_ablation_summary.csv", summary_rows)
    _write_csv(baselines_root / "privacy_baseline_comparison_rows.csv", rows)
    _write_csv(baselines_root / "privacy_baseline_comparison_summary.csv", summary_rows)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        default="protection/student_profile/configs/default.yaml",
    )
    args = ap.parse_args()
    print(evaluate(args.config))


if __name__ == "__main__":
    main()
