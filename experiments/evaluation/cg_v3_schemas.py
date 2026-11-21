"""Serializable schemas for the experimental CG V3 adapter."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


def _copy_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


@dataclass(slots=True)
class CGInput:
    q_t: str
    student_id: str
    session_id: str
    round_id: str
    resource_id: str = ""
    chunk_ids: list[str] = field(default_factory=list)
    C_u_t: dict[str, Any] = field(default_factory=dict)
    Pi_priv: dict[str, Any] = field(default_factory=dict)
    CR_t: dict[str, Any] = field(default_factory=dict)
    Pi_copy: dict[str, Any] = field(default_factory=dict)
    provenance_evidence: dict[str, Any] = field(default_factory=dict)
    capability_context: dict[str, Any] = field(default_factory=dict)
    previous_state: dict[str, Any] = field(default_factory=dict)
    previous_audit_hash: str = "GENESIS"

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CGInput":
        data = dict(value)
        return cls(
            q_t=str(data.get("q_t", "")),
            student_id=str(data.get("student_id", "")),
            session_id=str(data.get("session_id", "")),
            round_id=str(data.get("round_id", "")),
            resource_id=str(data.get("resource_id", "")),
            chunk_ids=[str(item) for item in data.get("chunk_ids", [])],
            C_u_t=_copy_mapping(data.get("C_u_t")),
            Pi_priv=_copy_mapping(data.get("Pi_priv")),
            CR_t=_copy_mapping(data.get("CR_t")),
            Pi_copy=_copy_mapping(data.get("Pi_copy")),
            provenance_evidence=_copy_mapping(data.get("provenance_evidence")),
            capability_context=_copy_mapping(data.get("capability_context")),
            previous_state=_copy_mapping(data.get("previous_state")),
            previous_audit_hash=str(data.get("previous_audit_hash", "GENESIS")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CGState:
    E_priv: float = 0.0
    E_copy: float = 0.0
    B_priv_remaining: float = 0.0
    B_copy_remaining: float = 0.0
    privacy_risk: float = 0.0
    copyright_risk: float = 0.0
    audit_risk: float = 0.0
    trust_score: float = 1.0
    request_frequency: int = 0
    semantic_repetition: int = 0
    previous_actions: list[list[str]] = field(default_factory=list)
    previous_attack_indicators: list[str] = field(default_factory=list)
    previous_audit_result: str = "not_available"
    last_semantic_intent: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "CGState":
        if not value:
            return cls()
        data = dict(value)
        return cls(
            E_priv=float(data.get("E_priv", 0.0)),
            E_copy=float(data.get("E_copy", 0.0)),
            B_priv_remaining=float(data.get("B_priv_remaining", 0.0)),
            B_copy_remaining=float(data.get("B_copy_remaining", 0.0)),
            privacy_risk=float(data.get("privacy_risk", 0.0)),
            copyright_risk=float(data.get("copyright_risk", 0.0)),
            audit_risk=float(data.get("audit_risk", 0.0)),
            trust_score=float(data.get("trust_score", 1.0)),
            request_frequency=int(data.get("request_frequency", 0)),
            semantic_repetition=int(data.get("semantic_repetition", 0)),
            previous_actions=[list(item) for item in data.get("previous_actions", [])],
            previous_attack_indicators=[str(item) for item in data.get("previous_attack_indicators", [])],
            previous_audit_result=str(data.get("previous_audit_result", "not_available")),
            last_semantic_intent=str(data.get("last_semantic_intent", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActionPlan:
    selected_actions: list[str]
    affected_fields: list[str]
    affected_resources: list[str]
    parameters: dict[str, Any]
    decision_reason: str
    risk_before: dict[str, float]
    expected_risk_after: dict[str, float]
    privacy_cost: float
    copyright_cost: float
    privacy_budget_before: float
    privacy_budget_after: float
    copyright_budget_before: float
    copyright_budget_after: float
    audit_evidence_required: list[str]
    feasible: bool = True
    score: float = 0.0
    infeasible_reason: str = ""
    allowed_payload: dict[str, Any] = field(default_factory=dict)
    score_breakdown: dict[str, float] = field(default_factory=dict)
    projected_privacy_cost: float = 0.0
    projected_copyright_cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CGOutput:
    Pi_joint: dict[str, Any]
    action_plan: ActionPlan
    allowed_student_context: dict[str, Any]
    allowed_teacher_resource: dict[str, Any]
    updated_state: CGState
    audit_record: dict[str, Any]
    audit_hash: str
    execution_result: str
    candidate_plans: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "Pi_joint": self.Pi_joint,
            "action_plan": self.action_plan.to_dict(),
            "allowed_student_context": self.allowed_student_context,
            "allowed_teacher_resource": self.allowed_teacher_resource,
            "updated_state": self.updated_state.to_dict(),
            "audit_record": self.audit_record,
            "audit_hash": self.audit_hash,
            "execution_result": self.execution_result,
            "candidate_plans": self.candidate_plans,
        }
