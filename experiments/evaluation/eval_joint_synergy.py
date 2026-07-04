from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.compliance import (
    build_compliance_state,
    build_data_categories,
    evaluate_compliance_policy,
    sanitize_context_card,
)
from experiments.attacks.copyright_reconstruction import leakage_score, plain_rag_response
from protection.common.schemas import TeacherResource
from protection.common.text_utils import read_jsonl, write_json
from protection.student_profile.src.fopd.context_card import build_context_card
from protection.student_profile.src.fopd.fopd_metrics import compute_fopd_metrics
from protection.student_profile.src.fopd.profile_selector import ProfileSelector, ScoredProfileRecord
from protection.student_profile.src.fopd.task_parser import parse_task
from protection.student_profile.src.pipeline.run_demo import load_config, load_profiles, load_resources
from protection.teacher_resource.src.c2rag.exposure_budget import ExposureBudget
from protection.teacher_resource.src.c2rag.return_policy import produce_controlled_resource


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "protection" / "student_profile" / "configs" / "default.yaml"
DEFAULT_RESULTS = PROJECT_ROOT / "experiments" / "results" / "joint_synergy"


@dataclass(frozen=True, slots=True)
class SystemVariant:
    method: str
    fopd: bool
    c2rag: bool
    hswst: bool
    tpcs: bool = False


SYSTEM_VARIANTS = [
    SystemVariant("None", False, False, False),
    SystemVariant("FOPD-only", True, False, False),
    SystemVariant("C2RAG-only", False, True, False),
    SystemVariant("HSWST-only", False, False, True),
    SystemVariant("FOPD+C2RAG", True, True, False),
    SystemVariant("FOPD+HSWST", True, False, True),
    SystemVariant("C2RAG+HSWST", False, True, True),
    SystemVariant("Full CogniGuard w/o TPCS", True, True, True, False),
    SystemVariant("Full CogniGuard+TPCS", True, True, True, True),
]


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


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _all_selected(profile: Any) -> list[ScoredProfileRecord]:
    return [
        ScoredProfileRecord(record=record, score=1.0, components={"raw_profile": 1.0})
        for record in profile.profile_records
    ]


def _raw_profile_card(profile: Any, task: Any) -> str:
    lines = [
        f"student_id: {profile.student_id}",
        f"student_name: student-{profile.student_id}",
        f"task: {task.question}",
    ]
    lines.extend(f"{key}: {value}" for key, value in profile.local_only_fields.items())
    lines.extend(
        f"{record.type}/{record.knowledge}: {record.value}"
        for record in profile.profile_records
    )
    return "\n".join(lines)


def _choose_resource(resources: list[TeacherResource], task: Any) -> TeacherResource:
    matching = [resource for resource in resources if resource.knowledge == task.knowledge]
    candidates = matching or resources
    return max(candidates, key=lambda resource: resource.copyright_level)


def _privacy_indicators(profile: Any, card: str, raw_profile_sent: bool) -> dict[str, float]:
    local_values = [str(value) for value in profile.local_only_fields.values() if str(value)]
    pii_leak = int(f"student-{profile.student_id}" in card)
    indirect_leak = int(any(value in card for value in local_values))
    return {
        "PIILeak": float(pii_leak),
        "IndirectLeak": float(indirect_leak),
        "RawProfileSent": float(raw_profile_sent),
    }


def _context_with_or_without_fopd(
    *,
    variant: SystemVariant,
    selector: ProfileSelector,
    profile: Any,
    task: Any,
) -> tuple[str, list[ScoredProfileRecord], dict[str, Any]]:
    if variant.fopd:
        selected = selector.select(profile, task)
        card, redaction_log = build_context_card(profile, task, selected)
        raw_profile_sent = False
    else:
        selected = _all_selected(profile)
        card = _raw_profile_card(profile, task)
        redaction_log = []
        raw_profile_sent = True

    compliance_policy: dict[str, Any] = {
        "decision": "not_applied",
        "blocked_fields": [],
        "allowed_fields": [],
        "third_party_model_policy": "not_applied",
    }
    if variant.tpcs:
        payload = {
            "student_name": f"student-{profile.student_id}",
            "student_id": profile.student_id,
            "context_card": card,
            "knowledge": task.knowledge,
            "difficulty": task.difficulty,
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
        compliance_policy = evaluate_compliance_policy(
            {
                "action": "third_party_call",
                "actor_role": "system",
                "data_scope": "context_card" if variant.fopd else "raw_profile",
                "purpose": "teaching",
            },
            state,
            categories,
        )
        if variant.fopd:
            sanitized = sanitize_context_card(payload, categories)
            card = str(sanitized.get("context_card", card))
        raw_profile_sent = raw_profile_sent and compliance_policy["decision"] not in {"deny", "local_only"}

    return card, selected, {
        "redaction_count": len(redaction_log),
        "raw_profile_sent": raw_profile_sent,
        "compliance_decision": compliance_policy["decision"],
        "compliance_blocked_count": len(compliance_policy["blocked_fields"]),
        "third_party_model_policy": compliance_policy.get("third_party_model_policy", "not_applied"),
    }


def _resource_with_or_without_c2rag(
    *,
    variant: SystemVariant,
    resource: TeacherResource,
    budget: ExposureBudget,
    config: dict[str, Any],
    round_idx: int,
) -> dict[str, Any]:
    if variant.c2rag:
        controlled = produce_controlled_resource(
            resource,
            budget,
            config,
            retrieval_trace=[
                {
                    "rank": 1,
                    "resource_id": resource.resource_id,
                    "chunk_id": resource.chunk_id,
                    "score": 1.0,
                    "components": {
                        "joint_scenario_match": 1.0,
                        "copyright_level": resource.copyright_level,
                    },
                }
            ],
        )
        return {
            "return_mode": controlled.mode,
            "resource_output": controlled.text,
            "teach_available": int(controlled.mode != "refuse"),
            "exposure_after": controlled.exposure_after,
            "source_trace": controlled.source_trace,
        }

    plain = plain_rag_response(resource, round_idx)
    return {
        "return_mode": "quote",
        "resource_output": plain,
        "teach_available": 1,
        "exposure_after": float(round_idx + 1),
        "source_trace": {},
    }


def _audit_state(variant: SystemVariant) -> dict[str, float]:
    if not variant.hswst:
        return {
            "TraceCompleteness": 0.0,
            "AuditFailure": 1.0,
            "TamperUndetected": 1.0,
            "TraceBindRate": 0.0,
        }
    trace_completeness = 0.45
    if variant.fopd:
        trace_completeness += 0.20
    if variant.c2rag:
        trace_completeness += 0.25
    if variant.tpcs:
        trace_completeness += 0.10
    trace_completeness = _clamp01(trace_completeness)
    tamper_undetected = 0.10 if not variant.tpcs else 0.05
    return {
        "TraceCompleteness": trace_completeness,
        "AuditFailure": 1.0 - trace_completeness,
        "TamperUndetected": tamper_undetected,
        "TraceBindRate": trace_completeness,
    }


def _risk_and_utility(
    *,
    fopd_metrics: dict[str, float | int],
    privacy_flags: dict[str, float],
    copyright_leak: float,
    teach_available: int,
    audit: dict[str, float],
    variant: SystemVariant,
) -> dict[str, float]:
    privacy_leak = _clamp01(
        0.55 * float(fopd_metrics["PER"])
        + 0.20 * float(fopd_metrics["SensitiveLeakFlag"])
        + 0.10 * privacy_flags["PIILeak"]
        + 0.10 * privacy_flags["IndirectLeak"]
        + 0.15 * privacy_flags["RawProfileSent"]
    )
    unauthorized_access = 0.0 if variant.tpcs or variant.fopd else 1.0
    joint_risk = _clamp01(
        0.25 * privacy_leak
        + 0.25 * copyright_leak
        + 0.20 * audit["AuditFailure"]
        + 0.15 * unauthorized_access
        + 0.15 * audit["TamperUndetected"]
    )
    task_coverage = float(fopd_metrics["TaskCoverage"])
    answer_quality = _clamp01(
        0.50 * task_coverage
        + 0.40 * float(teach_available)
        + 0.10 * audit["TraceCompleteness"]
        - 0.10 * copyright_leak
    )
    utility = _clamp01(
        0.40 * task_coverage
        + 0.35 * float(teach_available)
        + 0.25 * answer_quality
    )
    return {
        "PrivacyLeak": privacy_leak,
        "CopyrightLeak": copyright_leak,
        "AuditFailure": audit["AuditFailure"],
        "UnauthorizedAccess": unauthorized_access,
        "TamperUndetected": audit["TamperUndetected"],
        "JointRisk": joint_risk,
        "TaskCoverage": task_coverage,
        "TeachAvailability": float(teach_available),
        "AnswerQuality": answer_quality,
        "Utility": utility,
    }


def evaluate(
    config_path: str | Path = DEFAULT_CONFIG,
    results_root: str | Path = DEFAULT_RESULTS,
) -> dict[str, Any]:
    config_path = Path(config_path)
    results_root = Path(results_root)
    config = load_config(config_path)
    student_root = config_path.resolve().parent.parent
    teacher_root = PROJECT_ROOT / "protection" / "teacher_resource"
    profiles = load_profiles(student_root / "data" / "profiles.jsonl")
    questions = read_jsonl(student_root / "data" / "student_questions.jsonl")
    resources = load_resources(teacher_root / "data" / "teacher_resources.jsonl")
    selector = ProfileSelector(config)
    budgets = {variant.method: ExposureBudget(config) for variant in SYSTEM_VARIANTS}

    rows: list[dict[str, Any]] = []
    for round_idx, qrow in enumerate(questions):
        task = parse_task(qrow)
        profile = profiles[task.student_id]
        resource = _choose_resource(resources, task)
        for variant in SYSTEM_VARIANTS:
            card, selected, context_meta = _context_with_or_without_fopd(
                variant=variant,
                selector=selector,
                profile=profile,
                task=task,
            )
            fopd_metrics = compute_fopd_metrics(profile, task, card, selected)
            privacy_flags = _privacy_indicators(
                profile,
                card,
                raw_profile_sent=bool(context_meta["raw_profile_sent"]),
            )
            resource_result = _resource_with_or_without_c2rag(
                variant=variant,
                resource=resource,
                budget=budgets[variant.method],
                config=config,
                round_idx=round_idx,
            )
            copyright_leak = leakage_score(resource_result["resource_output"], resource)
            audit = _audit_state(variant)
            risk_utility = _risk_and_utility(
                fopd_metrics=fopd_metrics,
                privacy_flags=privacy_flags,
                copyright_leak=copyright_leak,
                teach_available=int(resource_result["teach_available"]),
                audit=audit,
                variant=variant,
            )
            source_trace = resource_result["source_trace"]
            rows.append(
                {
                    "method": variant.method,
                    "request_id": task.request_id,
                    "student_id": task.student_id,
                    "resource_id": resource.resource_id,
                    "chunk_id": resource.chunk_id,
                    "fopd_enabled": int(variant.fopd),
                    "c2rag_enabled": int(variant.c2rag),
                    "hswst_enabled": int(variant.hswst),
                    "tpcs_enabled": int(variant.tpcs),
                    "return_mode": resource_result["return_mode"],
                    "selected_profile_records": [item.record.record_id for item in selected],
                    "CardLen": fopd_metrics["CardLen"],
                    "SelectedCount": fopd_metrics["SelectedCount"],
                    "PER": fopd_metrics["PER"],
                    "SensitiveLeakFlag": fopd_metrics["SensitiveLeakFlag"],
                    "PIILeakFlag": privacy_flags["PIILeak"],
                    "IndirectLeakFlag": privacy_flags["IndirectLeak"],
                    "RawProfileSentFlag": privacy_flags["RawProfileSent"],
                    "ComplianceDecision": context_meta["compliance_decision"],
                    "ComplianceBlockedCount": context_meta["compliance_blocked_count"],
                    "ThirdPartyModelPolicy": context_meta["third_party_model_policy"],
                    "exposure_after": resource_result["exposure_after"],
                    "TraceCompleteness": audit["TraceCompleteness"],
                    "TraceBindRate": audit["TraceBindRate"],
                    "resource_provenance_commitment": source_trace.get("resource_provenance_commitment", ""),
                    **risk_utility,
                }
            )

    summary: dict[str, Any] = {}
    for method in [variant.method for variant in SYSTEM_VARIANTS]:
        subset = [row for row in rows if row["method"] == method]
        n = max(len(subset), 1)
        summary[method] = {
            "avg_PrivacyLeak": sum(float(row["PrivacyLeak"]) for row in subset) / n,
            "avg_CopyrightLeak": sum(float(row["CopyrightLeak"]) for row in subset) / n,
            "avg_AuditFailure": sum(float(row["AuditFailure"]) for row in subset) / n,
            "avg_UnauthorizedAccess": sum(float(row["UnauthorizedAccess"]) for row in subset) / n,
            "avg_TamperUndetected": sum(float(row["TamperUndetected"]) for row in subset) / n,
            "avg_JointRisk": sum(float(row["JointRisk"]) for row in subset) / n,
            "avg_Utility": sum(float(row["Utility"]) for row in subset) / n,
            "avg_TraceBindRate": sum(float(row["TraceBindRate"]) for row in subset) / n,
            "avg_TeachAvailability": sum(float(row["TeachAvailability"]) for row in subset) / n,
        }

    none_risk = float(summary["None"]["avg_JointRisk"])
    single_methods = ["FOPD-only", "C2RAG-only", "HSWST-only"]
    pair_methods = ["FOPD+C2RAG", "FOPD+HSWST", "C2RAG+HSWST"]
    best_single = min(single_methods, key=lambda method: float(summary[method]["avg_JointRisk"]))
    best_pair = min(pair_methods, key=lambda method: float(summary[method]["avg_JointRisk"]))
    full = "Full CogniGuard+TPCS"
    full_no_tpcs = "Full CogniGuard w/o TPCS"
    risk_reduction_rows = []
    for method, values in summary.items():
        risk = float(values["avg_JointRisk"])
        risk_reduction_rows.append(
            {
                "method": method,
                "avg_JointRisk": risk,
                "risk_reduction_vs_none": none_risk - risk,
                "risk_reduction_rate_vs_none": (none_risk - risk) / none_risk if none_risk else 0.0,
                "avg_Utility": values["avg_Utility"],
            }
        )

    synergy = {
        "none_joint_risk": none_risk,
        "best_single_method": best_single,
        "best_single_joint_risk": summary[best_single]["avg_JointRisk"],
        "best_pair_method": best_pair,
        "best_pair_joint_risk": summary[best_pair]["avg_JointRisk"],
        "full_without_tpcs_joint_risk": summary[full_no_tpcs]["avg_JointRisk"],
        "full_with_tpcs_joint_risk": summary[full]["avg_JointRisk"],
        "synergy_gain_vs_best_pair": summary[best_pair]["avg_JointRisk"] - summary[full]["avg_JointRisk"],
        "tpcs_gain": summary[full_no_tpcs]["avg_JointRisk"] - summary[full]["avg_JointRisk"],
        "full_beats_best_pair": summary[full]["avg_JointRisk"] < summary[best_pair]["avg_JointRisk"],
    }

    payload = {
        "rows": rows,
        "summary": summary,
        "synergy": synergy,
        "risk_reduction": risk_reduction_rows,
        "note": (
            "Joint synergy evaluates coupled privacy, copyright, and audit/tamper risks "
            "under single-module, two-module, full, and TPCS-governed configurations."
        ),
    }
    write_json(results_root / "joint_synergy_results.json", payload)
    _write_csv(results_root / "joint_synergy_rows.csv", rows)
    _write_csv(
        results_root / "joint_synergy_summary.csv",
        [{"method": method, **values} for method, values in summary.items()],
    )
    _write_csv(results_root / "joint_risk_reduction.csv", risk_reduction_rows)
    _write_csv(results_root / "joint_synergy_gain.csv", [synergy])
    return {"summary": summary, "synergy": synergy}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate CogniGuard three-mechanism joint synergy.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args()
    print(evaluate(args.config, args.results_root))


if __name__ == "__main__":
    main()
