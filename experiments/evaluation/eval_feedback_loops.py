from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from cogniguard.compliance import (
    build_compliance_state,
    build_data_categories,
    evaluate_compliance_policy,
)
from experiments.attacks.copyright_reconstruction import leakage_score
from experiments.evaluation.eval_joint_synergy import (
    DEFAULT_CONFIG,
    PROJECT_ROOT,
    _clamp01,
    _privacy_indicators,
    _raw_profile_card,
    _write_csv,
)
from protection.common.text_utils import read_jsonl, write_json
from protection.student_profile.src.fopd.context_card import build_context_card
from protection.student_profile.src.fopd.fopd_metrics import compute_fopd_metrics
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
from protection.student_profile.src.fopd.task_parser import parse_task
from protection.student_profile.src.pipeline.run_demo import load_config, load_profiles, load_resources
from protection.teacher_resource.src.c2rag.exposure_budget import ExposureBudget
from protection.teacher_resource.src.c2rag.retriever import CopyrightAwareRetriever
from protection.teacher_resource.src.c2rag.return_policy import (
    produce_controlled_resource,
    render_controlled_resource,
)


DEFAULT_RESULTS = PROJECT_ROOT / "experiments" / "results" / "feedback_loops"
MIXED_DATASET_ROOT = PROJECT_ROOT / "experiments" / "datasets" / "cogniguard_math_suite" / "mixed_math_suite"


def _default_student_data_root() -> Path:
    mixed = MIXED_DATASET_ROOT / "student_profile" / "data"
    return mixed if mixed.exists() else PROJECT_ROOT / "protection" / "student_profile" / "data"


def _default_teacher_data_root() -> Path:
    mixed = MIXED_DATASET_ROOT / "teacher_resource" / "data"
    return mixed if mixed.exists() else PROJECT_ROOT / "protection" / "teacher_resource" / "data"


def _ag2_request(task: Any) -> dict[str, Any]:
    return {
        "question": task.question,
        "knowledge": task.knowledge,
        "difficulty": task.difficulty,
        "teaching_goal": "scaffolded_practice_with_minimal_student_context",
        "resource_type": "open_problem_source",
    }


def _ambiguous_ag2_request(task: Any) -> dict[str, Any]:
    return {
        "question": "",
        "knowledge": "",
        "difficulty": task.difficulty,
        "teaching_goal": "choose a resource using only the minimized student context",
        "resource_type": "open_problem_source",
    }


def _retrieval_trace(retrieved: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "rank": rank,
            "resource_id": item.resource.resource_id,
            "chunk_id": item.resource.chunk_id,
            "score": item.score,
            "components": item.components,
        }
        for rank, item in enumerate(retrieved, start=1)
    ]


def _privacy_leak_from_fopd(profile: Any, task: Any, card: str, selected: list[Any]) -> float:
    fopd_metrics = compute_fopd_metrics(profile, task, card, selected)
    flags = _privacy_indicators(profile, card, raw_profile_sent=False)
    return _clamp01(
        0.55 * float(fopd_metrics["PER"])
        + 0.20 * float(fopd_metrics["SensitiveLeakFlag"])
        + 0.10 * flags["PIILeak"]
        + 0.10 * flags["IndirectLeak"]
        + 0.15 * flags["RawProfileSent"]
    )


def _candidate_downgrade_modes(mode: str) -> list[str]:
    if mode == "quote":
        return ["summary", "outline", "variant", "refuse"]
    if mode == "summary":
        return ["outline", "variant", "refuse"]
    if mode == "variant":
        return ["outline", "summary", "refuse"]
    if mode == "outline":
        return ["refuse"]
    return []


def _apply_hsw_feedback(resource: Any, mode: str, text: str, config: dict[str, Any], leak: float, threshold: float) -> dict[str, Any]:
    if leak < threshold or mode == "refuse":
        return {
            "mode": mode,
            "text": text,
            "downgraded": False,
            "reason": "no_hsw_alert",
        }
    candidates = []
    for next_mode in _candidate_downgrade_modes(mode):
        downgraded_text, _ = render_controlled_resource(resource, next_mode, config)
        candidates.append((leakage_score(downgraded_text, resource), next_mode, downgraded_text))
    if not candidates:
        return {
            "mode": mode,
            "text": text,
            "downgraded": False,
            "reason": "already_at_minimum_mode",
        }
    safer_candidates = [item for item in candidates if item[0] < leak]
    if not safer_candidates:
        return {
            "mode": mode,
            "text": text,
            "downgraded": False,
            "reason": "hsw_alert_found_no_lower_leakage_mode",
        }
    non_refuse = [item for item in safer_candidates if item[1] != "refuse"]
    best_leak, best_mode, best_text = (non_refuse or safer_candidates)[0]
    return {
        "mode": best_mode,
        "text": best_text,
        "downgraded": True,
        "reason": "hsw_leakage_alert_triggered_c2rag_downgrade",
    }


def _evaluate_cg_cross_event(profile: Any, task: Any, context_card: str, leak: float, threshold: float) -> dict[str, Any]:
    payload = {
        "student_id": profile.student_id,
        "student_name": f"student-{profile.student_id}",
        "raw_student_data": _raw_profile_card(profile, task),
        "context_card": context_card,
        "resource_leak_score": leak,
    }
    state = build_compliance_state(
        jurisdiction="US",
        education_stage="K-12",
        student_age=12 if leak >= threshold else 14,
        school_managed_account=True,
        parental_consent="pending" if leak >= threshold else "not_required",
        school_authorization="granted",
        third_party_model_use_allowed=leak < threshold,
    )
    data_scope = "raw_profile" if leak >= threshold else "context_card"
    categories = build_data_categories(payload, payload_kind="student_profile")
    policy = evaluate_compliance_policy(
        {
            "action": "third_party_call",
            "actor_role": "system",
            "data_scope": data_scope,
            "purpose": "teaching",
        },
        state,
        categories,
    )
    blocked = policy["decision"] in {"deny", "local_only", "require_parental_consent"} or bool(policy["blocked_fields"])
    return {
        "decision": policy["decision"],
        "blocked": blocked,
        "blocked_fields": policy["blocked_fields"],
        "third_party_model_policy": policy["third_party_model_policy"],
        "data_scope": data_scope,
    }


def _cross_layer_risk(
    *,
    privacy_leak: float,
    copyright_leak: float,
    trace_bind_rate: float,
    cg_blocked: bool,
) -> float:
    open_cross_channel = 0.0 if cg_blocked else 1.0
    return _clamp01(
        0.35 * privacy_leak * copyright_leak
        + 0.25 * copyright_leak * (1.0 - trace_bind_rate)
        + 0.20 * privacy_leak * (1.0 - trace_bind_rate)
        + 0.20 * open_cross_channel * max(privacy_leak, copyright_leak)
    )


def _mean(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return sum(float(row[key]) for row in rows) / len(rows)


def evaluate_feedback_loops(
    *,
    config_path: str | Path = DEFAULT_CONFIG,
    results_root: str | Path = DEFAULT_RESULTS,
    student_data_root: str | Path | None = None,
    teacher_data_root: str | Path | None = None,
    hsw_leak_threshold: float = 0.35,
) -> dict[str, Any]:
    config = load_config(config_path)
    results_root = Path(results_root)
    student_dir = Path(student_data_root) if student_data_root else _default_student_data_root()
    teacher_dir = Path(teacher_data_root) if teacher_data_root else _default_teacher_data_root()
    profiles = load_profiles(student_dir / "profiles.jsonl")
    questions = read_jsonl(student_dir / "student_questions.jsonl")
    resources = load_resources(teacher_dir / "teacher_resources.jsonl")

    selector = ProfileSelector(config)
    request_only_budget = ExposureBudget(config)
    context_budget = ExposureBudget(config)
    ambiguous_request_only_budget = ExposureBudget(config)
    ambiguous_context_budget = ExposureBudget(config)
    request_only_retriever = CopyrightAwareRetriever(resources, request_only_budget, config)
    context_retriever = CopyrightAwareRetriever(resources, context_budget, config)
    ambiguous_request_only_retriever = CopyrightAwareRetriever(resources, ambiguous_request_only_budget, config)
    ambiguous_context_retriever = CopyrightAwareRetriever(resources, ambiguous_context_budget, config)

    rows: list[dict[str, Any]] = []
    for qrow in questions:
        task = parse_task(qrow)
        profile = profiles[task.student_id]
        selected = selector.select(profile, task)
        context_card, _ = build_context_card(profile, task, selected)
        ag2_request = _ag2_request(task)
        ambiguous_request = _ambiguous_ag2_request(task)

        request_only = request_only_retriever.retrieve(ag2_request, task, "")
        context_guided = context_retriever.retrieve(ag2_request, task, context_card)
        ambiguous_request_only = ambiguous_request_only_retriever.retrieve(ambiguous_request, task, "")
        ambiguous_context_guided = ambiguous_context_retriever.retrieve(ambiguous_request, task, context_card)
        if not request_only or not context_guided:
            continue

        top_request_only = request_only[0]
        top_context = context_guided[0]
        top_ambiguous_request_only = ambiguous_request_only[0] if ambiguous_request_only else top_request_only
        top_ambiguous_context = ambiguous_context_guided[0] if ambiguous_context_guided else top_context
        controlled = produce_controlled_resource(
            top_context.resource,
            context_budget,
            config,
            retrieval_trace=_retrieval_trace(context_guided),
        )
        leak_before = leakage_score(controlled.text, top_context.resource)
        hsw_feedback = _apply_hsw_feedback(
            top_context.resource,
            controlled.mode,
            controlled.text,
            config,
            leak_before,
            hsw_leak_threshold,
        )
        leak_after = leakage_score(str(hsw_feedback["text"]), top_context.resource)
        privacy_after_fopd = _privacy_leak_from_fopd(profile, task, context_card, selected)
        cg = _evaluate_cg_cross_event(profile, task, context_card, leak_before, hsw_leak_threshold)

        independent_cross_risk = _cross_layer_risk(
            privacy_leak=1.0,
            copyright_leak=leak_before,
            trace_bind_rate=0.0,
            cg_blocked=False,
        )
        closed_loop_cross_risk = _cross_layer_risk(
            privacy_leak=privacy_after_fopd,
            copyright_leak=leak_after,
            trace_bind_rate=1.0,
            cg_blocked=bool(cg["blocked"]),
        )

        rows.append(
            {
                "request_id": task.request_id,
                "student_id": task.student_id,
                "knowledge": task.knowledge,
                "request_only_top_resource": top_request_only.resource.resource_id,
                "context_guided_top_resource": top_context.resource.resource_id,
                "retrieval_top1_changed": int(top_request_only.resource.resource_id != top_context.resource.resource_id),
                "request_only_top_score": top_request_only.score,
                "context_guided_top_score": top_context.score,
                "retrieval_score_delta": top_context.score - top_request_only.score,
                "context_component": top_context.components.get("context", 0.0),
                "ambiguous_request_only_top_resource": top_ambiguous_request_only.resource.resource_id,
                "ambiguous_context_guided_top_resource": top_ambiguous_context.resource.resource_id,
                "ambiguous_retrieval_top1_changed": int(
                    top_ambiguous_request_only.resource.resource_id
                    != top_ambiguous_context.resource.resource_id
                ),
                "ambiguous_retrieval_score_delta": top_ambiguous_context.score - top_ambiguous_request_only.score,
                "ambiguous_context_component": top_ambiguous_context.components.get("context", 0.0),
                "mode_before_hsw_feedback": controlled.mode,
                "mode_after_hsw_feedback": hsw_feedback["mode"],
                "hsw_feedback_downgraded": int(bool(hsw_feedback["downgraded"])),
                "copyright_leak_before_hsw": leak_before,
                "copyright_leak_after_hsw": leak_after,
                "copyright_leak_delta_from_hsw": leak_before - leak_after,
                "privacy_leak_after_fopd": privacy_after_fopd,
                "cg_decision": cg["decision"],
                "cg_data_scope": cg["data_scope"],
                "cg_blocked_cross_layer_event": int(bool(cg["blocked"])),
                "cg_blocked_field_count": len(cg["blocked_fields"]),
                "independent_cross_layer_risk": independent_cross_risk,
                "closed_loop_cross_layer_risk": closed_loop_cross_risk,
                "closed_loop_cross_layer_risk_delta": independent_cross_risk - closed_loop_cross_risk,
            }
        )

    summary = {
        "num_requests": len(rows),
        "retrieval_top1_shift_rate": _mean(rows, "retrieval_top1_changed"),
        "avg_retrieval_score_delta": _mean(rows, "retrieval_score_delta"),
        "avg_context_component": _mean(rows, "context_component"),
        "ambiguous_retrieval_top1_shift_rate": _mean(rows, "ambiguous_retrieval_top1_changed"),
        "avg_ambiguous_retrieval_score_delta": _mean(rows, "ambiguous_retrieval_score_delta"),
        "avg_ambiguous_context_component": _mean(rows, "ambiguous_context_component"),
        "hsw_return_mode_downgrade_rate": _mean(rows, "hsw_feedback_downgraded"),
        "avg_copyright_leak_delta_from_hsw": _mean(rows, "copyright_leak_delta_from_hsw"),
        "cg_cross_layer_block_rate": _mean(rows, "cg_blocked_cross_layer_event"),
        "avg_independent_cross_layer_risk": _mean(rows, "independent_cross_layer_risk"),
        "avg_closed_loop_cross_layer_risk": _mean(rows, "closed_loop_cross_layer_risk"),
        "avg_closed_loop_cross_layer_risk_delta": _mean(rows, "closed_loop_cross_layer_risk_delta"),
    }
    mode_transitions: dict[str, int] = {}
    for row in rows:
        transition = f"{row['mode_before_hsw_feedback']}->{row['mode_after_hsw_feedback']}"
        mode_transitions[transition] = mode_transitions.get(transition, 0) + 1
    summary["mode_transitions"] = mode_transitions

    payload = {
        "summary": summary,
        "rows": rows,
        "note": (
            "Feedback-loop evaluation verifies whether cross-module signals change downstream "
            "decisions: FOPD context changes C2-RAG retrieval scores, HSW-ST alerts can "
            "downgrade return modes, and CG blocks high-risk cross-layer third-party calls."
        ),
    }
    write_json(results_root / "feedback_loop_results.json", payload)
    _write_csv(results_root / "feedback_loop_rows.csv", rows)
    _write_csv(results_root / "feedback_loop_summary.csv", [summary])
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate CogniGuard closed-loop feedback effects.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--student-data-root", type=Path)
    parser.add_argument("--teacher-data-root", type=Path)
    parser.add_argument("--hsw-leak-threshold", type=float, default=0.35)
    args = parser.parse_args()
    result = evaluate_feedback_loops(
        config_path=args.config,
        results_root=args.results_root,
        student_data_root=args.student_data_root,
        teacher_data_root=args.teacher_data_root,
        hsw_leak_threshold=args.hsw_leak_threshold,
    )
    print(result["summary"])


if __name__ == "__main__":
    main()
