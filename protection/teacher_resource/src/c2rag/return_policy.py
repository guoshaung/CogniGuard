from __future__ import annotations

from protection.teacher_resource.src.c2rag.exposure_budget import ExposureBudget
from protection.teacher_resource.src.c2rag.variant_generator import generate_variant
from protection.common.schemas import ControlledResource, TeacherResource
from protection.teacher_resource.src.c2rag.source_trace import build_source_trace


def permit(resource: TeacherResource, exposure: float) -> bool:
    return exposure <= resource.policy.max_exposure


def decide_return_mode(resource: TeacherResource, exposure: float, config: dict) -> str:
    c2 = config.get("c2rag", {})
    thresholds = c2.get("thresholds", {})
    high_copyright = float(c2.get("high_copyright_threshold", 0.70))
    quote_copyright = float(c2.get("quote_copyright_threshold", 0.35))

    if not permit(resource, exposure):
        if resource.policy.allow_variant and exposure < float(thresholds.get("variant", 0.60)):
            return "variant"
        return "refuse"

    if (
        resource.policy.allow_quote
        and exposure < float(thresholds.get("quote", 0.15))
        and resource.copyright_level < quote_copyright
    ):
        return "quote"

    if resource.copyright_level >= high_copyright and resource.policy.allow_variant:
        return "variant"

    if resource.policy.allow_summary and exposure < float(thresholds.get("summary", 0.30)):
        return "summary"

    if resource.policy.allow_outline and exposure < float(thresholds.get("outline", 0.45)):
        return "outline"

    if resource.policy.allow_variant and exposure < float(thresholds.get("variant", 0.60)):
        return "variant"

    return "refuse"


def explain_return_policy(resource: TeacherResource, exposure: float, mode: str, config: dict) -> dict[str, object]:
    c2 = config.get("c2rag", {})
    thresholds = c2.get("thresholds", {})
    high_copyright = float(c2.get("high_copyright_threshold", 0.70))
    quote_copyright = float(c2.get("quote_copyright_threshold", 0.35))
    over_budget = not permit(resource, exposure)
    if over_budget:
        reason = "exposure_budget_exceeded"
    elif mode == "quote":
        reason = "low_copyright_quote_within_threshold"
    elif mode == "variant":
        reason = "high_copyright_or_reconstruction_risk_variant"
    elif mode == "summary":
        reason = "summary_allowed_within_exposure_threshold"
    elif mode == "outline":
        reason = "outline_allowed_after_summary_threshold"
    else:
        reason = "refuse_due_to_policy_or_budget"
    return {
        "policy_reason": reason,
        "over_budget": over_budget,
        "allow_quote": resource.policy.allow_quote,
        "allow_summary": resource.policy.allow_summary,
        "allow_outline": resource.policy.allow_outline,
        "allow_variant": resource.policy.allow_variant,
        "copyright_level": resource.copyright_level,
        "max_exposure": resource.policy.max_exposure,
        "exposure_before": exposure,
        "high_copyright_threshold": high_copyright,
        "quote_copyright_threshold": quote_copyright,
        "thresholds": thresholds,
    }


def render_controlled_resource(
    resource: TeacherResource,
    mode: str,
    config: dict,
) -> tuple[str, dict[str, object]]:
    if mode == "quote":
        return resource.content[: resource.policy.max_quote_len], {}
    if mode == "summary":
        return (
            f"资源摘要：该材料围绕“{resource.knowledge}”，适合 {resource.difficulty} 难度，"
            f"可用于帮助学生抓住概念关系和解题目标。",
            {},
        )
    if mode == "outline":
        return (
            f"资源提纲：知识点={resource.knowledge}；题型={resource.resource_type}；"
            "步骤=识别条件、匹配公式、给出结论、解释理由。",
            {},
        )
    if mode == "variant":
        result = generate_variant(resource, config)
        return str(result["variant_question"]), result
    return (
        f"该资料当前不适合继续提供原文或细节。建议围绕“{resource.knowledge}”复习概念、步骤和易错点。",
        {},
    )


def produce_controlled_resource(
    resource: TeacherResource,
    budget: ExposureBudget,
    config: dict,
    retrieval_trace: list[dict[str, object]] | None = None,
) -> ControlledResource:
    exposure_before = budget.get(resource.chunk_id)
    mode = decide_return_mode(resource, exposure_before, config)
    policy_explanation = explain_return_policy(resource, exposure_before, mode, config)
    text, extra = render_controlled_resource(resource, mode, config)
    exposure_info = budget.update(resource, text)
    trace = build_source_trace(
        resource=resource,
        mode=mode,
        exposure_before=exposure_before,
        exposure_after=exposure_info["after"],
        extra=extra,
        controlled_text=text,
        retrieval_trace=retrieval_trace,
        policy_reason=str(policy_explanation["policy_reason"]),
        decision_factors=policy_explanation,
    )
    return ControlledResource(
        mode=mode,
        text=text,
        resource=resource,
        exposure_before=exposure_before,
        exposure_after=exposure_info["after"],
        source_trace=trace,
    )
