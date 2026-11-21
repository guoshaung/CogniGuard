"""Candidate-plan policy composition for the CG V3 experiment adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .cg_v3_budget import BudgetProjection
from .cg_v3_schemas import ActionPlan, CGInput, CGState
from .cg_v3_state import derive_risks


@dataclass(slots=True)
class ComposerConfig:
    """Provisional, explicit scoring parameters for reproducible experiments."""

    privacy_field_cost: float = 0.1
    copyright_chunk_cost: float = 0.2
    privacy_penalty: float = 1.0
    copyright_penalty: float = 1.0
    audit_penalty: float = 0.8
    execution_cost: float = 0.04
    repetition_penalty: float = 0.05
    low_trust_penalty: float = 0.2
    config_version: str = "cg-v3-provisional-1"
    parameter_status: str = "provisional_not_paper_calibrated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "privacy_field_cost": self.privacy_field_cost,
            "copyright_chunk_cost": self.copyright_chunk_cost,
            "privacy_penalty": self.privacy_penalty,
            "copyright_penalty": self.copyright_penalty,
            "audit_penalty": self.audit_penalty,
            "execution_cost": self.execution_cost,
            "repetition_penalty": self.repetition_penalty,
            "low_trust_penalty": self.low_trust_penalty,
            "config_version": self.config_version,
            "parameter_status": self.parameter_status,
        }


PLAN_LIBRARY: tuple[tuple[str, ...], ...] = (
    ("allow",),
    ("minimize",),
    ("mask",),
    ("summarize",),
    ("controlled_excerpt",),
    ("controlled_excerpt", "watermark"),
    ("minimize", "summarize"),
    ("regenerate", "watermark"),
    ("degrade", "audit_escalation"),
    ("refuse", "audit_escalation"),
    ("block",),
)


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def _allowed_fields(request: CGInput) -> list[str]:
    all_fields = list(request.C_u_t)
    allowed = request.Pi_priv.get("allowed_fields")
    if allowed is None:
        allowed = all_fields
    forbidden = set(request.Pi_priv.get("forbidden_fields", []))
    return [field for field in allowed if field in request.C_u_t and field not in forbidden]


def _resource_ids(request: CGInput) -> list[str]:
    values = request.Pi_copy.get("allowed_resources", request.CR_t.get("allowed_resources", []))
    if values:
        return [str(value) for value in values]
    return _unique([request.resource_id, *request.chunk_ids])


def _raw_fields(request: CGInput) -> list[str]:
    raw_names = {"student_id", "address", "raw_audio", "raw_image", "raw_screenshot", "handwriting_trace", "full_history"}
    return sorted(raw_names.intersection(request.C_u_t))


def _has_copy_restriction(request: CGInput) -> bool:
    if bool(request.Pi_copy.get("allow_original", True)) is False:
        return True
    max_exposure = request.Pi_copy.get("max_exposure_score")
    exposure = float(request.CR_t.get("exposure_score", request.Pi_copy.get("exposure_score", 0.0)))
    return max_exposure is not None and exposure > float(max_exposure)


def _has_privacy_restriction(request: CGInput) -> bool:
    allowed = set(request.Pi_priv.get("allowed_fields", request.C_u_t))
    forbidden = set(request.Pi_priv.get("forbidden_fields", []))
    return bool(set(request.C_u_t) - allowed or forbidden.intersection(request.C_u_t))


def _action_text(actions: tuple[str, ...]) -> str:
    return "+".join(actions)


def _residual_risk(base: float, actions: tuple[str, ...], domain: str) -> float:
    if "block" in actions or "refuse" in actions:
        return 0.0
    reduction = 1.0
    if domain == "privacy":
        if "minimize" in actions:
            reduction *= 0.55
        if "mask" in actions:
            reduction *= 0.45
        if "summarize" in actions:
            reduction *= 0.55
        if "degrade" in actions:
            reduction *= 0.45
    if domain == "copyright":
        if "controlled_excerpt" in actions:
            reduction *= 0.55
        if "summarize" in actions:
            reduction *= 0.45
        if "watermark" in actions:
            reduction *= 0.7
        if "degrade" in actions:
            reduction *= 0.5
    if domain == "audit":
        if "watermark" in actions:
            reduction *= 0.55
        if "audit_escalation" in actions:
            reduction *= 0.35
        if "regenerate" in actions:
            reduction *= 0.75
    return round(min(1.0, max(0.0, base * reduction)), 8)


def _utility(actions: tuple[str, ...]) -> float:
    values = {
        "allow": 1.0,
        "minimize": 0.86,
        "mask": 0.78,
        "summarize": 0.74,
        "controlled_excerpt": 0.84,
        "watermark": -0.04,
        "regenerate": 0.62,
        "degrade": 0.48,
        "audit_escalation": -0.05,
        "refuse": 0.08,
        "block": 0.0,
    }
    return round(sum(values.get(action, 0.0) for action in actions), 8)


def _costs(request: CGInput, actions: tuple[str, ...], config: ComposerConfig) -> tuple[float, float]:
    privacy_fields = _allowed_fields(request)
    resource_count = max(len(request.chunk_ids), 1) if request.resource_id or request.chunk_ids else 0
    privacy_multiplier = 1.0
    copyright_multiplier = 1.0
    if "minimize" in actions or "mask" in actions:
        privacy_multiplier *= 0.5
    if "summarize" in actions:
        privacy_multiplier *= 0.5
        copyright_multiplier *= 0.45
    if "degrade" in actions:
        privacy_multiplier *= 0.45
        copyright_multiplier *= 0.5
    if "refuse" in actions or "block" in actions:
        privacy_multiplier = 0.0
        copyright_multiplier = 0.0
    if "controlled_excerpt" in actions:
        copyright_multiplier *= 0.55
    return (
        round(len(privacy_fields) * config.privacy_field_cost * privacy_multiplier, 8),
        round(resource_count * config.copyright_chunk_cost * copyright_multiplier, 8),
    )


def _parameters(request: CGInput, actions: tuple[str, ...]) -> dict[str, Any]:
    return {
        "summary_max_chars": 280 if "summarize" in actions else None,
        "excerpt_max_chunks": 1 if "controlled_excerpt" in actions else 0,
        "masked_fields": _raw_fields(request) if "mask" in actions else [],
        "watermark_required": "watermark" in actions,
        "regeneration_required": "regenerate" in actions,
        "audit_escalation": "audit_escalation" in actions,
    }


def _allowed_outputs(request: CGInput, actions: tuple[str, ...]) -> tuple[dict[str, Any], dict[str, Any]]:
    if "block" in actions or "refuse" in actions:
        return {}, {}
    fields = _allowed_fields(request)
    student = {field: request.C_u_t[field] for field in fields}
    if "mask" in actions:
        for field in _raw_fields(request):
            student.pop(field, None)
    if "summarize" in actions:
        student = {"summary": " ".join(f"{key}={value}" for key, value in student.items())[:280]}
    resources = dict(request.CR_t)
    copy_restricted = _has_copy_restriction(request)
    if (
        "allow" in actions
        or ("minimize" in actions and not copy_restricted)
    ) and "summarize" not in actions and "degrade" not in actions and "controlled_excerpt" not in actions:
        resources["allowed_chunks"] = list(request.chunk_ids)
        resources["verbatim_ratio"] = 1.0
        resources["return_mode"] = "original"
    if "controlled_excerpt" in actions or "degrade" in actions or (copy_restricted and "minimize" in actions):
        chunks = request.chunk_ids[:1] or [request.resource_id]
        resources = {key: resources[key] for key in resources if key in {"resource_id", "chunk_id", "title", "summary", "exposure_score"}}
        resources["allowed_chunks"] = chunks
        resources["verbatim_ratio"] = 0.55 if "controlled_excerpt" in actions else 0.5
        resources["return_mode"] = "controlled_excerpt"
    if "summarize" in actions:
        resources = {"resource_id": request.resource_id, "summary": str(resources.get("summary", resources.get("title", "")))[:280]}
        resources["allowed_chunks"] = []
        resources["verbatim_ratio"] = 0.0
        resources["return_mode"] = "summary"
    if "degrade" in actions:
        if not resources:
            resources = {"resource_id": request.resource_id}
        resources.setdefault("allowed_chunks", request.chunk_ids[:1] or [request.resource_id])
        resources["verbatim_ratio"] = min(float(resources.get("verbatim_ratio", 0.5)), 0.5)
        resources["return_mode"] = "controlled_excerpt"
        resources["degraded"] = True
    if "watermark" in actions:
        resources["watermark_required"] = True
        resources["watermark_applied"] = True
    return student, resources


def compose_candidates(
    request: CGInput,
    state: CGState,
    privacy_projection: BudgetProjection,
    copyright_projection: BudgetProjection,
    config: ComposerConfig,
) -> list[ActionPlan]:
    risks = derive_risks(request, state)
    raw_fields = _raw_fields(request)
    source_confidence = float(request.provenance_evidence.get("confidence", 1.0))
    candidates: list[ActionPlan] = []
    for actions in PLAN_LIBRARY:
        privacy_cost, copyright_cost = _costs(request, actions, config)
        after_privacy = privacy_projection.before + privacy_cost
        after_copyright = copyright_projection.before + copyright_cost
        feasible = True
        reasons: list[str] = []
        if bool(request.capability_context.get("allowed", True)) is False:
            feasible = False
            reasons.append("capability context is not allowed")
        if raw_fields and "allow" in actions:
            feasible = False
            reasons.append(f"raw fields are not transportable: {raw_fields}")
        if source_confidence <= 0.0 and not ({"refuse", "block"} & set(actions)):
            feasible = False
            reasons.append("provenance evidence is invalid")
        if _has_copy_restriction(request) and actions == ("allow",):
            feasible = False
            reasons.append("copyright policy does not allow original return")
        if _has_privacy_restriction(request) and actions == ("allow",):
            feasible = False
            reasons.append("privacy policy does not allow all requested fields")
        if after_privacy > privacy_projection.maximum + 1e-9 and not ({"refuse", "block"} & set(actions)):
            feasible = False
            reasons.append("projected privacy budget exceeds maximum")
        if after_copyright > copyright_projection.maximum + 1e-9 and not ({"refuse", "block"} & set(actions)):
            feasible = False
            reasons.append("projected copyright budget exceeds maximum")
        expected = {
            "privacy": _residual_risk(risks["privacy"], actions, "privacy"),
            "copyright": _residual_risk(risks["copyright"], actions, "copyright"),
            "audit": _residual_risk(risks["audit"], actions, "audit"),
        }
        score_breakdown = {
            "utility": _utility(actions),
            "privacy_penalty": -config.privacy_penalty * expected["privacy"],
            "copyright_penalty": -config.copyright_penalty * expected["copyright"],
            "audit_penalty": -config.audit_penalty * expected["audit"],
            "execution_penalty": -config.execution_cost * len(actions),
            "repetition_penalty": -config.repetition_penalty * state.semantic_repetition,
            "trust_penalty": -config.low_trust_penalty * (1.0 - state.trust_score),
        }
        score = sum(score_breakdown.values())
        score_breakdown["total"] = score
        candidates.append(ActionPlan(
            selected_actions=list(actions),
            affected_fields=_allowed_fields(request),
            affected_resources=_resource_ids(request),
            parameters=_parameters(request, actions),
            decision_reason="candidate evaluated under provisional V3 constraints",
            risk_before={"privacy": risks["privacy"], "copyright": risks["copyright"], "audit": risks["audit"]},
            expected_risk_after=expected,
            privacy_cost=privacy_cost,
            copyright_cost=copyright_cost,
            privacy_budget_before=privacy_projection.before,
            privacy_budget_after=round(max(0.0, privacy_projection.maximum - after_privacy), 8),
            copyright_budget_before=copyright_projection.before,
            copyright_budget_after=round(max(0.0, copyright_projection.maximum - after_copyright), 8),
            audit_evidence_required=["action_plan", "actual_disclosure", "audit_hash"],
            feasible=feasible,
            score=round(score, 8) if feasible else float("-inf"),
            infeasible_reason="; ".join(reasons),
            score_breakdown={key: round(value, 8) for key, value in score_breakdown.items()},
        ))
    return sorted(candidates, key=lambda candidate: (-candidate.score, tuple(candidate.selected_actions)))


def select_plan(candidates: list[ActionPlan]) -> ActionPlan:
    for candidate in candidates:
        if candidate.feasible:
            candidate.decision_reason = "selected highest-scoring feasible candidate"
            return candidate
    fallback = next(candidate for candidate in candidates if candidate.selected_actions == ["block"])
    fallback.decision_reason = "all non-block candidates are infeasible"
    return fallback


def candidate_summary(candidates: list[ActionPlan], selected: ActionPlan) -> list[dict[str, Any]]:
    selected_name = tuple(selected.selected_actions)
    return [
        {
            "actions": candidate.selected_actions,
            "score": candidate.score,
            "feasible": candidate.feasible,
            "infeasible_reason": candidate.infeasible_reason,
            "selected": tuple(candidate.selected_actions) == selected_name,
            "expected_risk_after": candidate.expected_risk_after,
            "privacy_cost": candidate.privacy_cost,
            "copyright_cost": candidate.copyright_cost,
            "score_breakdown": candidate.score_breakdown,
        }
        for candidate in candidates
    ]
