"""Plan-to-execution contract for the CG V3.1 experiment adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .cg_v3_policy_composer import ComposerConfig, _allowed_fields, _allowed_outputs, _costs
from .cg_v3_schemas import ActionPlan, CGInput


@dataclass(slots=True)
class ExecutionMeasurement:
    student_context: dict[str, Any]
    teacher_resource: dict[str, Any]
    actual_student_fields: list[str]
    actual_allowed_chunks: list[str]
    actual_privacy_cost: float
    actual_copyright_cost: float
    actual_privacy_disclosure: dict[str, Any]
    actual_copyright_disclosure: dict[str, Any]
    output_violation: bool = False
    rolled_back: bool = False
    fallback_reason: str = ""
    effective_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "actual_student_fields": self.actual_student_fields,
            "actual_allowed_chunks": self.actual_allowed_chunks,
            "actual_privacy_cost": self.actual_privacy_cost,
            "actual_copyright_cost": self.actual_copyright_cost,
            "actual_privacy_disclosure": self.actual_privacy_disclosure,
            "actual_copyright_disclosure": self.actual_copyright_disclosure,
            "output_violation": self.output_violation,
            "rolled_back": self.rolled_back,
            "fallback_reason": self.fallback_reason,
            "effective_actions": self.effective_actions,
        }


def _resource_keys() -> set[str]:
    return {
        "resource_id", "chunk_id", "title", "summary", "exposure_score", "allowed_chunks",
        "verbatim_ratio", "return_mode", "degraded", "watermark_required", "watermark_applied",
    }


def _within_allowed(candidate: Mapping[str, Any], allowed: Mapping[str, Any]) -> bool:
    candidate_keys = set(candidate)
    if "allowed_chunks" in candidate_keys and not candidate.get("allowed_chunks") and "allowed_chunks" not in allowed:
        candidate_keys.remove("allowed_chunks")
    if not candidate_keys.issubset(set(allowed)):
        return False
    if "allowed_chunks" in candidate:
        allowed_chunks = set(allowed.get("allowed_chunks", []))
        if not set(candidate.get("allowed_chunks", [])) <= allowed_chunks:
            return False
    return True


def _privacy_cost(request: CGInput, actions: tuple[str, ...], student: Mapping[str, Any], config: ComposerConfig) -> float:
    if not student or "refuse" in actions or "block" in actions:
        return 0.0
    fields = len(set(student).intersection(request.C_u_t))
    if "summary" in student:
        fields = len(_allowed_fields(request))
    multiplier = 1.0
    if "minimize" in actions or "mask" in actions:
        multiplier *= 0.5
    if "summarize" in actions:
        multiplier *= 0.5
    if "degrade" in actions:
        multiplier *= 0.45
    return round(fields * config.privacy_field_cost * multiplier, 8)


def _copyright_cost(request: CGInput, actions: tuple[str, ...], resource: Mapping[str, Any], config: ComposerConfig) -> float:
    if not resource or "refuse" in actions or "block" in actions:
        return 0.0
    if "allowed_chunks" in resource and not resource.get("allowed_chunks") and len(resource) == 1:
        return 0.0
    resource_count = max(len(request.chunk_ids), 1) if request.resource_id or request.chunk_ids else 0
    return_mode = str(resource.get("return_mode", ""))
    if return_mode == "summary" or "summarize" in actions:
        multiplier = 0.45
    elif "allowed_chunks" in resource:
        ratio = float(resource.get("verbatim_ratio", 1.0))
        multiplier = ratio
    else:
        multiplier = 1.0
    return round(resource_count * config.copyright_chunk_cost * multiplier, 8)


def _empty_measurement(actions: list[str], *, violation: bool, rolled_back: bool, reason: str) -> ExecutionMeasurement:
    return ExecutionMeasurement(
        student_context={},
        teacher_resource={},
        actual_student_fields=[],
        actual_allowed_chunks=[],
        actual_privacy_cost=0.0,
        actual_copyright_cost=0.0,
        actual_privacy_disclosure={"fields": [], "summary": False},
        actual_copyright_disclosure={"chunks": [], "verbatim_ratio": 0.0, "return_mode": "none"},
        output_violation=violation,
        rolled_back=rolled_back,
        fallback_reason=reason,
        effective_actions=actions,
    )


def execute_plan(
    request: CGInput,
    plan: ActionPlan,
    config: ComposerConfig,
    *,
    privacy_remaining: float,
    copyright_remaining: float,
    supplied_student_context: Mapping[str, Any] | None = None,
    supplied_teacher_resource: Mapping[str, Any] | None = None,
    allow_static_budget_violation: bool = False,
    strict_output_enforcement: bool = True,
) -> ExecutionMeasurement:
    actions = tuple(plan.selected_actions)
    allowed_student, allowed_resource = _allowed_outputs(request, actions)
    if not strict_output_enforcement and (supplied_student_context is not None or supplied_teacher_resource is not None):
        legacy_student = dict(supplied_student_context or {})
        legacy_resource = dict(supplied_teacher_resource or {})
        fields = sorted(set(legacy_student).intersection(request.C_u_t))
        chunks = sorted(str(chunk) for chunk in legacy_resource.get("allowed_chunks", []))
        return ExecutionMeasurement(
            student_context=legacy_student,
            teacher_resource=legacy_resource,
            actual_student_fields=fields,
            actual_allowed_chunks=chunks,
            actual_privacy_cost=round(len(fields) * config.privacy_field_cost, 8),
            actual_copyright_cost=round(len(chunks) * config.copyright_chunk_cost, 8),
            actual_privacy_disclosure={"fields": fields, "summary": False, "raw_values": bool(fields)},
            actual_copyright_disclosure={"chunks": chunks, "verbatim_ratio": 1.0 if chunks else 0.0, "return_mode": "legacy_override", "raw_original": False},
            effective_actions=list(actions),
        )
    candidate_student = allowed_student if supplied_student_context is None else dict(supplied_student_context)
    candidate_resource = allowed_resource if supplied_teacher_resource is None else dict(supplied_teacher_resource)
    if (
        not _within_allowed(candidate_student, allowed_student)
        and "summary" in allowed_student
        and set(candidate_student).issubset(set(request.C_u_t))
        and not {"full_history", "raw_audio", "raw_image", "raw_screenshot"}.intersection(candidate_student)
    ):
        candidate_student = dict(allowed_student)
    if (
        not _within_allowed(candidate_resource, allowed_resource)
        and str(allowed_resource.get("return_mode", "")) in {"summary", "controlled_excerpt"}
        and set(candidate_resource).issubset(set(request.CR_t) | {"allowed_chunks"})
        and not {"full_text", "raw_content", "original_text"}.intersection(candidate_resource)
    ):
        candidate_resource = dict(allowed_resource)
    if not _within_allowed(candidate_student, allowed_student) or not _within_allowed(candidate_resource, allowed_resource):
        return _empty_measurement(
            ["refuse", "audit_escalation"],
            violation=True,
            rolled_back=True,
            reason="executor output exceeded structured allowed payload",
        )

    actual_privacy = _privacy_cost(request, actions, candidate_student, config)
    actual_copyright = _copyright_cost(request, actions, candidate_resource, config)
    calculated_privacy, calculated_copyright = _costs(request, actions, config)
    projected_privacy = plan.projected_privacy_cost if plan.projected_privacy_cost > 0.0 else plan.privacy_cost
    projected_copyright = plan.projected_copyright_cost if plan.projected_copyright_cost > 0.0 else plan.copyright_cost
    if projected_privacy == 0.0 and calculated_privacy == 0.0:
        projected_privacy = 0.0
    if projected_copyright == 0.0 and calculated_copyright == 0.0:
        projected_copyright = 0.0
    if actual_privacy > projected_privacy + 1e-9 or actual_copyright > projected_copyright + 1e-9:
        return _empty_measurement(
            ["refuse", "audit_escalation"],
            violation=True,
            rolled_back=True,
            reason="actual disclosure exceeded projected action-plan cost",
        )
    if (
        (actual_privacy > privacy_remaining + 1e-9 or actual_copyright > copyright_remaining + 1e-9)
        and not allow_static_budget_violation
    ):
        return _empty_measurement(
            ["refuse", "audit_escalation"],
            violation=False,
            rolled_back=True,
            reason="actual disclosure exceeded remaining budget",
        )
    fields = sorted(set(candidate_student).intersection(request.C_u_t))
    if "summary" in candidate_student:
        fields = sorted(_allowed_fields(request))
    chunks = sorted(str(chunk) for chunk in candidate_resource.get("allowed_chunks", []))
    return ExecutionMeasurement(
        student_context=dict(candidate_student),
        teacher_resource=dict(candidate_resource),
        actual_student_fields=fields,
        actual_allowed_chunks=chunks,
        actual_privacy_cost=actual_privacy,
        actual_copyright_cost=actual_copyright,
        actual_privacy_disclosure={
            "fields": fields,
            "summary": "summary" in candidate_student,
            "raw_values": False,
        },
        actual_copyright_disclosure={
            "chunks": chunks,
            "verbatim_ratio": float(candidate_resource.get("verbatim_ratio", 1.0 if candidate_resource else 0.0)),
            "return_mode": str(candidate_resource.get("return_mode", "original" if candidate_resource else "none")),
            "watermark_applied": bool(candidate_resource.get("watermark_applied", False)),
            "raw_original": "full_text" in candidate_resource or "raw_content" in candidate_resource,
        },
        effective_actions=list(actions),
    )


def attach_allowed_payload(request: CGInput, plan: ActionPlan) -> None:
    student, resource = _allowed_outputs(request, tuple(plan.selected_actions))
    plan.allowed_payload = {
        "student_context": student,
        "teacher_resource": resource,
        "authorized_actions": list(plan.selected_actions),
        "projected_privacy_cost": plan.privacy_cost,
        "projected_copyright_cost": plan.copyright_cost,
    }
