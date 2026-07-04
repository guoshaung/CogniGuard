from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from protection.common.schemas import TeacherResource
from protection.common.text_utils import lcs_ratio, unique_ngram_overlap
from protection.teacher_resource.src.c2rag.return_policy import render_controlled_resource
from protection.teacher_resource.src.c2rag.variant_generator import generate_variant


@dataclass(slots=True)
class CopyrightBaselineResult:
    method: str
    return_mode: str
    output: str
    baseline_family: str
    baseline_note: str


COPYRIGHT_INTENT_TOKENS = (
    "verbatim",
    "full text",
    "original",
    "continue",
    "copy",
    "exact",
    "完整",
    "原文",
    "逐字",
    "继续",
    "不要省略",
    "讲义",
    "所有内容",
)


def build_copyright_external_baselines(
    *,
    resource: TeacherResource,
    attack: dict[str, Any],
    round_idx: int,
    candidate_plain_output: str,
    config: dict[str, Any],
) -> list[CopyrightBaselineResult]:
    prompt = str(attack.get("prompt", ""))
    return [
        protected_material_detector(resource, candidate_plain_output, config),
        memfree_ngram(resource, candidate_plain_output, config),
        shield_agent(resource, prompt, round_idx, config),
        bloomscrub_rewrite(resource, candidate_plain_output, config),
        rcad_approx(resource, candidate_plain_output, config),
    ]


def protected_material_detector(
    resource: TeacherResource,
    candidate: str,
    config: dict[str, Any],
) -> CopyrightBaselineResult:
    overlap = _protected_overlap(candidate, resource)
    if overlap >= 0.35 or resource.content[: min(24, len(resource.content))] in candidate:
        safe, _ = render_controlled_resource(resource, "summary", config)
        return CopyrightBaselineResult(
            method="ProtectedMaterialDetector",
            return_mode="summary",
            output=safe,
            baseline_family="external_copyright",
            baseline_note="Post-generation protected-material detector replaced high-overlap output with summary.",
        )
    return CopyrightBaselineResult(
        method="ProtectedMaterialDetector",
        return_mode="pass",
        output=candidate,
        baseline_family="external_copyright",
        baseline_note="Detector did not find enough protected overlap to intervene.",
    )


def memfree_ngram(
    resource: TeacherResource,
    candidate: str,
    config: dict[str, Any],
    *,
    threshold: float = 0.28,
) -> CopyrightBaselineResult:
    overlap = unique_ngram_overlap(candidate, resource.content, n=6)
    if overlap >= threshold:
        safe, _ = render_controlled_resource(resource, "outline", config)
        return CopyrightBaselineResult(
            method="MemFree-Ngram",
            return_mode="outline",
            output=safe,
            baseline_family="external_copyright",
            baseline_note="N-gram overlap with protected material exceeded the MemFree threshold.",
        )
    return CopyrightBaselineResult(
        method="MemFree-Ngram",
        return_mode="pass",
        output=candidate,
        baseline_family="external_copyright",
        baseline_note="No protected n-gram threshold hit.",
    )


def shield_agent(
    resource: TeacherResource,
    prompt: str,
    round_idx: int,
    config: dict[str, Any],
) -> CopyrightBaselineResult:
    if _requests_protected_text(prompt) or round_idx >= 2:
        variant = generate_variant(resource, config)
        output = str(variant.get("variant_question") or "")
        return CopyrightBaselineResult(
            method="SHIELD-Agent",
            return_mode="variant",
            output=output,
            baseline_family="external_copyright",
            baseline_note="Policy agent identified protected-text reconstruction risk and returned a safe variant.",
        )
    safe, _ = render_controlled_resource(resource, "summary", config)
    return CopyrightBaselineResult(
        method="SHIELD-Agent",
        return_mode="summary",
        output=safe,
        baseline_family="external_copyright",
        baseline_note="Policy agent allowed only a copyright-safe teaching summary.",
    )


def bloomscrub_rewrite(
    resource: TeacherResource,
    candidate: str,
    config: dict[str, Any],
) -> CopyrightBaselineResult:
    overlap = _protected_overlap(candidate, resource)
    if overlap >= 0.25:
        variant = generate_variant(resource, config)
        output = (
            "BloomScrub rewrite: protected wording removed; use this new practice item instead. "
            + str(variant.get("variant_question") or "")
        )
        return CopyrightBaselineResult(
            method="BloomScrub-Rewrite",
            return_mode="rewrite",
            output=output,
            baseline_family="external_copyright",
            baseline_note="Long protected span detected and rewritten into a non-verbatim derivative.",
        )
    safe, _ = render_controlled_resource(resource, "summary", config)
    return CopyrightBaselineResult(
        method="BloomScrub-Rewrite",
        return_mode="summary",
        output=safe,
        baseline_family="external_copyright",
        baseline_note="No long protected span; returned safe summary.",
    )


def rcad_approx(
    resource: TeacherResource,
    candidate: str,
    config: dict[str, Any],
) -> CopyrightBaselineResult:
    overlap = _protected_overlap(candidate, resource)
    if overlap >= 0.2 or resource.copyright_level >= 0.7:
        safe, _ = render_controlled_resource(resource, "outline", config)
        output = (
            "R-CAD approximation: answer generated with protected-context influence reduced. "
            + safe
        )
        return CopyrightBaselineResult(
            method="R-CAD-Approx",
            return_mode="context_penalty",
            output=output,
            baseline_family="external_copyright",
            baseline_note="Black-box approximation of reverse context-aware decoding via protected-context penalty.",
        )
    return CopyrightBaselineResult(
        method="R-CAD-Approx",
        return_mode="pass",
        output=candidate,
        baseline_family="external_copyright",
        baseline_note="Context penalty not triggered.",
    )


def _protected_overlap(candidate: str, resource: TeacherResource) -> float:
    return max(
        lcs_ratio(candidate, resource.content),
        unique_ngram_overlap(candidate, resource.content, n=6),
    )


def _requests_protected_text(prompt: str) -> bool:
    lower = prompt.lower()
    return any(token in lower for token in COPYRIGHT_INTENT_TOKENS)
