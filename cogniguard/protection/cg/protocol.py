"""CG v2 protocol primitives.

This module turns CG from a hard-coded middleware class into an explicit
protocol for multi-agent governance: message envelopes, capabilities,
policy routing, field-level risk, multi-scope budgets, and tamper-evident
audit events.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class CGDecision(str, Enum):
    """System-wide actions available to CG."""

    ALLOW = "allow"
    SANITIZE = "sanitize"
    DEGRADE = "degrade"
    DEFER = "defer"
    DENY = "deny"


@dataclass(slots=True)
class MessageEnvelope:
    """Transport-independent envelope for every inter-agent message."""

    sender: str
    receiver: str
    message_type: str
    payload: dict[str, Any]
    privacy_level: str
    round_id: str
    purpose: str = "legitimate_educational_interest"
    message_id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:16]}")
    trace_id: str = field(default_factory=lambda: f"trace_{uuid.uuid4().hex[:16]}")
    parent_message_ids: list[str] = field(default_factory=list)
    disclosure_score: float = 0.0
    risk_breakdown: dict[str, Any] = field(default_factory=dict)
    capabilities_required: tuple[str, ...] = ()
    schema_version: str = "cg/2.0"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    policy_decision: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["capabilities_required"] = list(self.capabilities_required)
        return data


class CapabilityRegistry:
    """Least-privilege contracts for all trusted execution nodes."""

    AGENT_CAPABILITIES: Mapping[str, frozenset[str]] = {

            "MM-FOPD": frozenset({"profile.read.minimized", "diagnosis.request"}),
            "profile_diagnosis_agent": frozenset(
                {"diagnosis.generate", "resource.request", "agent.result.send"}
            ),
            "copyright_aware_resource_agent": frozenset(
                {"resource.retrieve", "resource.return.controlled", "agent.result.send"}
            ),
            "pedagogical_teaching_agent": frozenset(
                {"teaching.generate", "resource.read.controlled_snippet", "agent.result.send"}
            ),
            "learning_assessment_agent": frozenset(
                {"assessment.generate", "profile.update.propose", "agent.result.send"}
            ),
            "CGController": frozenset(
                {"policy.decide", "budget.consume", "audit.write", "profile.update.approve"}
            ),
            "HSW-ST": frozenset({"audit.bind", "watermark.apply"}),
    }


    EXPECTED_RECEIVERS: Mapping[str, str] = {
        "diagnosis_request": "profile_diagnosis_agent",
        "controlled_resource_request": "copyright_aware_resource_agent",
        "teaching_generation_request": "pedagogical_teaching_agent",
        "learning_assessment_request": "learning_assessment_agent",
        "profile_update_evidence": "CGController",
        "final_answer_audit": "HSW-ST",
    }

    MESSAGE_CONTRACTS: Mapping[tuple[str, str], tuple[str, ...]] = {

            ("MM-FOPD", "diagnosis_request"): ("diagnosis.request",),
            ("profile_diagnosis_agent", "controlled_resource_request"): ("resource.request",),
            ("copyright_aware_resource_agent", "teaching_generation_request"): ("resource.return.controlled",),
            ("pedagogical_teaching_agent", "learning_assessment_request"): ("teaching.generate",),
            ("learning_assessment_agent", "profile_update_evidence"): ("profile.update.propose",),
            ("CGController", "final_answer_audit"): ("audit.write",),
    }


    def capabilities(self, agent_id: str) -> frozenset[str]:
        return self.AGENT_CAPABILITIES.get(agent_id, frozenset())

    def required_capabilities(
        self, sender: str, receiver: str, message_type: str
    ) -> tuple[str, ...]:
        if receiver == "CGController":
            return ("agent.result.send",)
        if message_type.endswith(".result"):
            return ("agent.result.send",)
        return self.MESSAGE_CONTRACTS.get((sender, message_type), ())

    def route_allowed(
        self, sender: str, receiver: str, message_type: str
    ) -> tuple[bool, str, tuple[str, ...]]:
        required = self.required_capabilities(sender, receiver, message_type)
        sender_caps = self.capabilities(sender)
        receiver_caps = self.capabilities(receiver)
        missing_sender = set(required) - sender_caps

        if receiver == "CGController":
            if sender_caps and not missing_sender:
                return True, "sender may return an audited result", required
            return False, f"sender lacks result capability: {sorted(missing_sender)}", required

        if not required:
            return False, "no capability contract for requested message type", required
        if missing_sender:
            return False, f"sender lacks capabilities: {sorted(missing_sender)}", required

        expected_receiver = self.EXPECTED_RECEIVERS.get(message_type, receiver)
        if receiver != expected_receiver:
            return False, (
                f"receiver {receiver} is not the least-privilege handler for {message_type}; "
                f"expected {expected_receiver}"
            ), required
        if receiver != "CGController" and not receiver_caps:
            return False, "receiver has no registered capabilities", required
        return True, "least-privilege route contract satisfied", required


class RiskScorer:
    """Field-level disclosure risk adjusted by receiver and purpose."""

    FIELD_SENSITIVITY: Mapping[str, float] = {
        "student_id": 1.0,
        "student_name": 1.0,
        "full_learning_history": 1.0,
        "full_student_profile": 1.0,
        "long_term_student_profile": 1.0,
        "raw_multimodal_data": 1.0,
        "raw_student_data": 1.0,
        "raw_screenshot": 0.95,
        "wrong_answer_image_path": 0.95,
        "voice_recording": 0.95,
        "audio_features": 0.9,
        "emotion_signals": 0.9,
        "handwriting_trace": 0.9,
        "family": 0.9,
        "address": 0.95,
        "phone": 0.95,
        "id_card": 1.0,
        "school": 0.65,
        "full_teacher_resources": 0.8,
        "full_original_teacher_resources": 0.85,
        "learner_state": 0.2,
        "common_error": 0.15,
        "current_error_type": 0.15,
        "knowledge_point": 0.05,
        "task_difficulty": 0.05,
        "recommended_strategy": 0.1,
    }
    RECEIVER_RISK: Mapping[str, float] = {
        "CGController": 0.1,
        "HSW-ST": 0.15,
        "profile_diagnosis_agent": 0.25,
        "learning_assessment_agent": 0.3,
        "copyright_aware_resource_agent": 0.3,
        "pedagogical_teaching_agent": 0.35,
        "external_agent": 0.8,
        "external_llm": 0.8,
    }
    PURPOSE_FACTOR: Mapping[str, float] = {
        "legitimate_educational_interest": 0.6,
        "teaching_generation": 0.5,
        "controlled_resource_retrieval": 0.5,
        "audit_only": 0.3,
        "profile_update_review": 0.45,
        "unspecified": 1.0,
    }
    RAW_FIELDS = frozenset(
        {
            "raw_multimodal_data",
            "raw_student_data",
            "full_student_profile",
            "long_term_student_profile",
            "full_learning_history",
            "raw_screenshot",
            "voice_recording",
            "wrong_answer_image_path",
            "audio_features",
            "emotion_signals",
            "handwriting_trace",
            "student_id",
        }
    )

    def __init__(
        self,
        degrade_threshold: float = 0.65,
        deny_threshold: float = 0.85,
        unknown_field_risk: float = 0.25,
    ) -> None:
        self.degrade_threshold = degrade_threshold
        self.deny_threshold = deny_threshold
        self.unknown_field_risk = unknown_field_risk

    def score(
        self,
        payload: Any,
        receiver: str,
        purpose: str = "legitimate_educational_interest",
    ) -> tuple[float, dict[str, Any]]:
        receiver_risk = self.RECEIVER_RISK.get(receiver, 0.7)
        purpose_factor = self.PURPOSE_FACTOR.get(purpose, self.PURPOSE_FACTOR["unspecified"])
        field_scores = self._score_value(payload, "")
        raw_field_hit = bool(set(field_scores) & self.RAW_FIELDS)
        max_raw = max((score for name, score in field_scores.items() if name in self.RAW_FIELDS), default=0.0)
        normalized = sum(field_scores.values()) / (len(field_scores) or 1)
        adjusted = min(1.0, normalized * receiver_risk * purpose_factor)
        return round(adjusted, 4), {
            "field_count": len(field_scores),
            "raw_field_hit": raw_field_hit,
            "max_raw_field_score": round(max_raw, 4),
            "receiver_risk": receiver_risk,
            "purpose_factor": purpose_factor,
            "field_scores": field_scores,
        }

    def _score_value(self, value: Any, prefix: str) -> dict[str, float]:
        scores: dict[str, float] = {}
        if isinstance(value, Mapping):
            for key, nested in value.items():
                name = str(key)
                path = f"{prefix}.{name}" if prefix else name
                base = self.FIELD_SENSITIVITY.get(name, self.unknown_field_risk)
                scores[path] = float(base)
                scores.update(self._score_value(nested, path))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                scores.update(self._score_value(item, f"{prefix}[{index}]"))
        return scores


class BudgetManager:
    """Round-, session-, and student-level cumulative disclosure budgets."""

    def __init__(
        self,
        round_limit: float = 0.75,
        session_limit: float = 2.0,
        student_limit: float = 4.0,
    ) -> None:
        self.round_limit = round_limit
        self.session_limit = session_limit
        self.student_limit = student_limit
        self.used_by_round: dict[str, float] = {}
        self.used_by_session: dict[str, float] = {}
        self.used_by_student: dict[str, float] = {}

    def check(
        self,
        round_id: str,
        session_id: str,
        student_id: str,
        incremental: float,
    ) -> tuple[bool, dict[str, Any]]:
        round_used = self.used_by_round.get(round_id, 0.0)
        session_used = self.used_by_session.get(session_id, 0.0)
        student_used = self.used_by_student.get(student_id, 0.0)
        projections = {
            "round": round_used + incremental,
            "session": session_used + incremental,
            "student": student_used + incremental,
        }
        exceeded = [scope for scope, limit in (
            ("round", self.round_limit),
            ("session", self.session_limit),
            ("student", self.student_limit),
        ) if projections[scope] > limit + 1e-9]
        return not exceeded, {
            "exceeded_scopes": exceeded,
            "used": {
                "round": round(round_used, 4),
                "session": round(session_used, 4),
                "student": round(student_used, 4),
            },
            "projected": {key: round(value, 4) for key, value in projections.items()},
            "limits": {
                "round": self.round_limit,
                "session": self.session_limit,
                "student": self.student_limit,
            },
        }

    def consume(
        self,
        round_id: str,
        session_id: str,
        student_id: str,
        incremental: float,
    ) -> dict[str, Any]:
        allowed, state = self.check(round_id, session_id, student_id, incremental)
        if not allowed:
            return state
        self.used_by_round[round_id] = round(
            self.used_by_round.get(round_id, 0.0) + incremental, 4
        )
        self.used_by_session[session_id] = round(
            self.used_by_session.get(session_id, 0.0) + incremental, 4
        )
        self.used_by_student[student_id] = round(
            self.used_by_student.get(student_id, 0.0) + incremental, 4
        )
        state["used"] = {
            "round": self.used_by_round[round_id],
            "session": self.used_by_session[session_id],
            "student": self.used_by_student[student_id],
        }
        return state


class PolicyRouter:
    """Composable route, capability, payload, risk, and budget decision engine."""

    def __init__(
        self,
        capability_registry: CapabilityRegistry | None = None,
        risk_scorer: RiskScorer | None = None,
        budget_manager: BudgetManager | None = None,
    ) -> None:
        self.capabilities = capability_registry or CapabilityRegistry()
        self.risk = risk_scorer or RiskScorer()
        self.budget = budget_manager or BudgetManager()

    def evaluate(
        self,
        message: dict[str, Any],
        *,
        session_id: str,
        student_id: str,
        forbidden_fields: set[str] | None = None,
    ) -> tuple[CGDecision, dict[str, Any]]:
        forbidden_fields = forbidden_fields or set()
        sender = str(message.get("sender", ""))
        receiver = str(message.get("receiver", ""))
        message_type = str(message.get("message_type", ""))
        purpose = str(message.get("purpose", "legitimate_educational_interest"))
        route_ok, route_reason, required_caps = self.capabilities.route_allowed(
            sender, receiver, message_type
        )
        if not route_ok:
            return CGDecision.DENY, self._decision(
                "unauthorized_route", route_reason, required_caps
            )

        present_forbidden = find_fields(message.get("payload"), forbidden_fields)
        raw_present = find_fields(message.get("payload"), RiskScorer.RAW_FIELDS)
        if raw_present:
            return CGDecision.DENY, self._decision(
                "raw_or_identifier_payload",
                f"raw/identifier fields are never transportable: {sorted(raw_present)}",
                required_caps,
                matched_fields=sorted(raw_present),
            )

        score, breakdown = self.risk.score(message.get("payload"), receiver, purpose)
        message["disclosure_score"] = score
        message["risk_breakdown"] = breakdown
        if score >= self.risk.deny_threshold:
            return CGDecision.DENY, self._decision(
                "risk_threshold",
                f"disclosure risk {score} exceeds deny threshold {self.risk.deny_threshold}",
                required_caps,
                risk_score=score,
                risk_breakdown=breakdown,
            )

        allowed_budget, budget_state = self.budget.check(
            message.get("round_id", "default"), session_id, student_id, score
        )
        if not allowed_budget:
            return CGDecision.DEGRADE, self._decision(
                "cumulative_budget",
                f"cumulative disclosure budget exceeded: {budget_state['exceeded_scopes']}",
                required_caps,
                risk_score=score,
                risk_breakdown=breakdown,
                budget=budget_state,
            )

        if present_forbidden:
            return CGDecision.SANITIZE, self._decision(
                "sanitizable_fields",
                f"remove non-transportable fields before dispatch: {sorted(present_forbidden)}",
                required_caps,
                matched_fields=sorted(present_forbidden),
                risk_score=score,
                risk_breakdown=breakdown,
                budget=budget_state,
            )

        if score >= self.risk.degrade_threshold:
            return CGDecision.DEGRADE, self._decision(
                "risk_threshold",
                f"disclosure risk {score} exceeds degrade threshold {self.risk.degrade_threshold}",
                required_caps,
                risk_score=score,
                risk_breakdown=breakdown,
                budget=budget_state,
            )

        return CGDecision.ALLOW, self._decision(
            "policy_passed",
            "least-privilege route, payload risk, purpose, and budget passed",
            required_caps,
            risk_score=score,
            risk_breakdown=breakdown,
            budget=budget_state,
        )

    def consume(self, message: dict[str, Any], session_id: str, student_id: str) -> dict[str, Any]:
        return self.budget.consume(
            str(message.get("round_id", "default")),
            session_id,
            student_id,
            float(message.get("disclosure_score", 0.0)),
        )

    def _decision(
        self,
        policy_id: str,
        reason: str,
        capabilities: tuple[str, ...],
        **details: Any,
    ) -> dict[str, Any]:
        return {
            "policy_id": f"cg.v2.{policy_id}",
            "reason": reason,
            "capabilities": list(capabilities),
            **details,
        }


class AuditChain:
    """Minimal tamper-evident hash chain for all CG decisions."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.head_hash = "GENESIS"

    def append(
        self,
        *,
        event_type: str,
        message: dict[str, Any],
        decision: CGDecision,
        reason: str,
        policy_id: str,
        risk_score: float = 0.0,
    ) -> dict[str, Any]:
        payload_hash = stable_hash(message.get("payload"))
        event = {
            "event_id": f"evt_{uuid.uuid4().hex[:16]}",
            "trace_id": message.get("trace_id"),
            "message_id": message.get("message_id"),
            "round_id": message.get("round_id"),
            "sender": message.get("sender"),
            "receiver": message.get("receiver"),
            "message_type": message.get("message_type"),
            "event_type": event_type,
            "decision": decision.value,
            "policy_id": policy_id,
            "reason": reason,
            "risk_score": round(float(risk_score), 4),
            "payload_hash": payload_hash,
            "previous_hash": self.head_hash,
            "timestamp": utc_now_iso(),
        }
        event["event_hash"] = stable_hash(event)
        self.head_hash = event["event_hash"]
        self.events.append(event)
        return event

    def verify(self) -> bool:
        previous = "GENESIS"
        for event in self.events:
            candidate = dict(event)
            claimed_hash = candidate.pop("event_hash", None)
            if candidate.get("previous_hash") != previous:
                return False
            if stable_hash(candidate) != claimed_hash:
                return False
            previous = claimed_hash
        return self.head_hash == previous


def sanitize_payload(value: Any, forbidden_fields: set[str]) -> dict[str, Any] | list[Any]:
    if isinstance(value, Mapping):
        return {
            key: sanitize_payload(nested, forbidden_fields)
            for key, nested in value.items()
            if str(key) not in forbidden_fields
        }
    if isinstance(value, list):
        return [sanitize_payload(item, forbidden_fields) for item in value]
    return value


def degrade_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep only bounded teaching fields when a message must be degraded."""
    allowed_keys = (
        "knowledge_point",
        "learner_state",
        "task_difficulty",
        "suggested_teaching_strategy",
        "teaching_request",
        "context_card",
        "diagnosis_result",
        "controlled_resource_snippets",
        "profile_encoding",
        "teaching_answer",
        "student_response",
        "profile_update_evidence",
    )
    degraded: dict[str, Any] = {}
    for key in allowed_keys:
        if key in payload:
            degraded[key] = _bounded_copy(payload[key])
    degraded["cg_degraded"] = True
    return degraded


def _bounded_copy(value: Any, max_items: int = 12, max_text: int = 500) -> Any:
    if isinstance(value, Mapping):
        items = list(value.items())[:max_items]
        return {key: _bounded_copy(nested, max_items, max_text) for key, nested in items}
    if isinstance(value, list):
        return [_bounded_copy(item, max_items, max_text) for item in value[:max_items]]
    if isinstance(value, str) and len(value) > max_text:
        return value[:max_text]
    return value


def find_fields(value: Any, field_names: set[str] | frozenset[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            canonical = _canonical_field_name(str(key))
            if canonical in field_names:
                found.add(canonical)
            found.update(find_fields(nested, field_names))
    elif isinstance(value, list):
        for item in value:
            found.update(find_fields(item, field_names))
    return found


def _canonical_field_name(name: str) -> str:
    """Match JSON-style camelCase fields to the protocol's snake_case schema."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(name or ""))
    return re.sub(r"[^a-z0-9]+", "_", spaced.lower()).strip("_")


def stable_hash(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "AuditChain",
    "BudgetManager",
    "CapabilityRegistry",
    "MessageEnvelope",
    "PolicyRouter",
    "RiskScorer",
    "CGDecision",
    "degrade_payload",
    "find_fields",
    "sanitize_payload",
    "stable_hash",
]
