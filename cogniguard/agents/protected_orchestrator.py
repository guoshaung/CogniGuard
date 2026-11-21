from __future__ import annotations

import json
import uuid
from typing import Any, Callable

from cogniguard.compliance import (
    append_compliance_audit_event,
    build_compliance_state,
    build_data_categories,
    evaluate_compliance_policy,
    sanitize_context_card,
)
from cogniguard.protection.cg.protocol import (
    AuditChain,
    BudgetManager,
    CapabilityRegistry,
    CGDecision,
    MessageEnvelope,
    PolicyRouter,
    RiskScorer,
    degrade_payload,
    sanitize_payload,
)
from cogniguard.runtime.mode import (
    build_guardrail_adapter,
    build_runtime_llm_client,
    get_runtime_status,
)
from cogniguard.runtime.protection_context import active_protection, charge_domain_budget

from cogniguard.agents.roles.base import (
    COMMON_FORBIDDEN_INPUTS,
    AgentValidationError,
    BaseAgent,
    summarize_text,
    utc_now_iso,
)
from cogniguard.agents.roles.materials import CopyrightAwareResourceAgent
from cogniguard.agents.roles.assessment import LearningAssessmentAgent
from cogniguard.agents.roles.teaching import PedagogicalTeachingAgent
from cogniguard.agents.roles.diagnosis import ProfileDiagnosisAgent

try:
    from protection.audit_trace.src.hybrid_watermark import HybridWatermarkSystem
except ImportError:
    HybridWatermarkSystem = None


class CGController:
    """Trusted policy controller for all inter-agent communication."""

    def __init__(
        self,
        max_disclosure_score: float = 0.75,
        cumulative_privacy_budget: float = 3.0,
        session_privacy_budget: float = 2.0,
        hsw_st_auditor: Any | None = None,
        guardrail_adapter: Any | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
        compliance_state: dict[str, Any] | None = None,
        session_id: str = "default_session",
        student_id: str = "anonymous_student",
        capability_registry: CapabilityRegistry | None = None,
        risk_scorer: RiskScorer | None = None,
        budget_manager: BudgetManager | None = None,
        audit_chain: AuditChain | None = None,
    ) -> None:
        self.max_disclosure_score = max_disclosure_score
        self.cumulative_privacy_budget = cumulative_privacy_budget
        self.session_privacy_budget = session_privacy_budget
        self.hsw_st_auditor = hsw_st_auditor
        self.guardrail_adapter = guardrail_adapter
        self.event_sink = event_sink
        self.compliance_state = compliance_state or build_compliance_state()
        self.compliance_audit_log: list[dict[str, Any]] = []
        self.last_compliance_policy: dict[str, Any] | None = None
        self.message_log: list[dict[str, Any]] = []
        self.teacher_review_queue: list[dict[str, Any]] = []
        self.session_id = session_id
        self.student_id = student_id
        self.capability_registry = capability_registry or CapabilityRegistry()
        self.risk_scorer = risk_scorer or RiskScorer(
            degrade_threshold=max_disclosure_score * 0.9,
            deny_threshold=max_disclosure_score,
        )
        self.budget_manager = budget_manager or BudgetManager(
            round_limit=max_disclosure_score,
            session_limit=session_privacy_budget,
            student_limit=cumulative_privacy_budget,
        )
        self.policy_router = PolicyRouter(
            capability_registry=self.capability_registry,
            risk_scorer=self.risk_scorer,
            budget_manager=self.budget_manager,
        )
        self.audit_chain = audit_chain or AuditChain()
        self.profile_update_review_threshold = 0.6
        # Kept as a compatibility view for demos and existing evaluations.
        self.allowed_routes = {
            ("MM-FOPD", "profile_diagnosis_agent"),
            ("profile_diagnosis_agent", "CGController"),
            ("profile_diagnosis_agent", "copyright_aware_resource_agent"),
            ("copyright_aware_resource_agent", "CGController"),
            ("copyright_aware_resource_agent", "pedagogical_teaching_agent"),
            ("pedagogical_teaching_agent", "CGController"),
            ("pedagogical_teaching_agent", "learning_assessment_agent"),
            ("learning_assessment_agent", "CGController"),
            ("CGController", "HSW-ST"),
        }

    @property
    def cumulative_disclosure_by_round(self) -> dict[str, float]:
        return self.budget_manager.used_by_round

    @property
    def audit_events(self) -> list[dict[str, Any]]:
        return self.audit_chain.events

    @property
    def audit_chain_head(self) -> str:
        return self.audit_chain.head_hash

    def verify_audit_chain(self) -> bool:
        return self.audit_chain.verify()

    def build_message(
        self,
        sender: str,
        receiver: str,
        message_type: str,
        payload: dict[str, Any],
        privacy_level: str,
        round_id: str,
        purpose: str = "legitimate_educational_interest",
        parent_message_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        score, breakdown = self.risk_scorer.score(payload, receiver, purpose)
        envelope = MessageEnvelope(
            sender=sender,
            receiver=receiver,
            message_type=message_type,
            payload=payload,
            privacy_level=privacy_level,
            round_id=round_id,
            purpose=purpose,
            parent_message_ids=list(parent_message_ids or []),
            disclosure_score=score,
            risk_breakdown=breakdown,
            capabilities_required=self.capability_registry.required_capabilities(
                sender, receiver, message_type
            ),
        )
        return envelope.to_dict()

    def handle_user_request(
        self,
        request_text: str,
        context_card: dict[str, Any] | None = None,
        round_id: str = "external_request",
    ) -> dict[str, Any]:
        """Handle user-facing sensitive requests before any agent sees them."""
        lowered = request_text.lower()
        if _asks_for_raw_multimodal_data(lowered):
            return {
                "approved": False,
                "decision": "refused_raw_multimodal_disclosure",
                "reason": "Raw screenshots, audio features, emotion signals, and handwriting traces remain in the protected raw-data layer and are never sent to agents.",
                "round_id": round_id,
                "timestamp": utc_now_iso(),
            }
        if _asks_for_full_profile(lowered):
            minimized_summary = _minimized_profile_summary(context_card)
            return {
                "approved": bool(minimized_summary),
                "decision": (
                    "returned_minimized_summary"
                    if minimized_summary
                    else "refused_full_profile_disclosure"
                ),
                "reason": "CG blocks full learning profile disclosure and permits only MM-FOPD minimized teaching fields.",
                "minimized_summary": minimized_summary,
                "round_id": round_id,
                "timestamp": utc_now_iso(),
            }
        return {
            "approved": True,
            "decision": "no_sensitive_profile_or_raw_data_request_detected",
            "round_id": round_id,
            "timestamp": utc_now_iso(),
        }

    def dispatch(
        self,
        sender: str,
        receiver: BaseAgent,
        message_type: str,
        payload: dict[str, Any],
        privacy_level: str,
        round_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        message = self.build_message(
            sender=sender,
            receiver=receiver.agent_id,
            message_type=message_type,
            payload=payload,
            privacy_level=privacy_level,
            round_id=round_id,
            purpose=self._purpose_for_message_type(message_type),
        )
        outbound_payload = self._authorize_message(message)
        frame = active_protection()
        if frame is not None and frame.nemo_colang is not None:
            allowed = frame.nemo_colang.check(
                "execution", json.dumps(outbound_payload, ensure_ascii=False, default=str)
            )
            frame.evidence.append({"stage": "nemo_execution", "decision": "allow" if allowed else "block"})
            if not allowed:
                raise AgentValidationError("Native NeMo execution gate blocked the agent call")
        self._emit_message_event(message, "request")
        receiver.validate_input(outbound_payload)
        output = receiver.generate(outbound_payload)
        response = self.build_message(
            sender=receiver.agent_id,
            receiver="CGController",
            message_type=f"{message_type}.result",
            payload=output,
            privacy_level=privacy_level,
            round_id=round_id,
            purpose="audit_only",
            parent_message_ids=[message["message_id"]],
        )
        audited_output = self._authorize_message(response)
        self._emit_message_event(response, "response")
        self.message_log.extend([message, response])
        return message, audited_output, response

    def pre_check_context_card(
        self, context_card: dict[str, Any], round_id: str
    ) -> dict[str, Any]:
        data_categories = build_data_categories(context_card, payload_kind="context_card")
        compliance_policy = evaluate_compliance_policy(
            {
                "action": "context_card_send",
                "actor_role": "system",
                "data_scope": "context_card",
                "purpose": "legitimate_educational_interest",
            },
            self.compliance_state,
            data_categories,
        )
        if compliance_policy["blocked_fields"]:
            context_card = sanitize_context_card(context_card, data_categories)
            data_categories = build_data_categories(context_card, payload_kind="context_card")
        forbidden = self._find_forbidden_keys(context_card)
        if forbidden:
            raise AgentValidationError(
                f"CG rejected forbidden context fields: {sorted(forbidden)}"
            )
        score, risk_breakdown = self.risk_scorer.score(
            context_card,
            "profile_diagnosis_agent",
            "legitimate_educational_interest",
        )
        approved = score <= self.max_disclosure_score
        policy_decision = {
            "policy_id": "cg.v2.context_precheck",
            "action": "allow" if approved else "degrade",
            "reason": (
                "minimum educational context passed field-level risk scoring"
                if approved
                else "minimum educational context exceeded disclosure threshold"
            ),
            "risk_score": score,
        }
        audit_message = MessageEnvelope(
            sender="MM-FOPD",
            receiver="profile_diagnosis_agent",
            message_type="context_precheck",
            payload=context_card,
            privacy_level="minimum_context",
            round_id=round_id,
            purpose="legitimate_educational_interest",
            disclosure_score=score,
            risk_breakdown=risk_breakdown,
        ).to_dict()
        self.audit_chain.append(
            event_type="context_precheck",
            message=audit_message,
            decision=CGDecision.ALLOW if approved else CGDecision.DEGRADE,
            reason=policy_decision["reason"],
            policy_id=policy_decision["policy_id"],
            risk_score=score,
        )
        result = {
            "approved": approved,
            "stage": "CG pre-check",
            "privacy_level": "minimum_context",
            "disclosure_score": score,
            "risk_breakdown": risk_breakdown,
            "policy_decision": policy_decision,
            "round_id": round_id,
            "timestamp": utc_now_iso(),
            "compliance_policy": compliance_policy,
            "data_categories": data_categories,
            "audit_chain_head": self.audit_chain_head,
        }
        if not approved:
            raise AgentValidationError(
                f"CG rejected context card disclosure_score={score}"
            )
        self.last_compliance_policy = compliance_policy
        self._record_compliance_event(
            event_type="data_minimization",
            actor_role="system",
            data_category="derived_profile",
            decision=compliance_policy["decision"],
            legal_context=compliance_policy.get("legal_context", "internal_policy"),
            details={
                "round_id": round_id,
                "blocked_fields": compliance_policy["blocked_fields"],
                "allowed_fields": compliance_policy["allowed_fields"],
            },
        )
        return result

    def approve_profile_update_evidence(
        self, evidence: dict[str, Any], round_id: str
    ) -> dict[str, Any]:
        message = self.build_message(
            sender="learning_assessment_agent",
            receiver="CGController",
            message_type="profile_update_evidence",
            payload={"profile_update_evidence": evidence},
            privacy_level="evidence_only",
            round_id=round_id,
            purpose="profile_update_review",
        )
        outbound = self._authorize_message(message)
        self._emit_message_event(message, "profile_update_evidence")

        evidence = outbound.get("profile_update_evidence", evidence)
        pollution_reason = _profile_update_pollution_reason(evidence)
        requires_approval = bool(evidence.get("requires_cg_approval", True))
        confidence = _normalized_confidence(evidence.get("confidence"))
        update_fields = _profile_update_fields(evidence)

        if pollution_reason or not requires_approval:
            # Keep an attack-specific lifecycle value for audit, red-team
            # evaluation, and teacher review.  A generic ``rejected`` status
            # makes a direct self-report poisoning attempt indistinguishable
            # from an incomplete benign update.
            lifecycle = pollution_reason or "rejected_missing_cg_approval"
            decision = CGDecision.DENY
            review_reason = pollution_reason or "profile update lacks CG approval requirement"
        elif confidence < self.profile_update_review_threshold:
            lifecycle = "deferred_teacher_review"
            decision = CGDecision.DEFER
            review_reason = (
                f"low-confidence update requires teacher review: {confidence:.2f}"
            )
        else:
            lifecycle = "evidence_logged_for_review"
            decision = CGDecision.ALLOW
            review_reason = (
                f"confidence {confidence:.2f} passed propose-review-commit gate"
            )

        review_entry = {
            "review_id": f"review_{uuid.uuid4().hex[:12]}",
            "round_id": round_id,
            "student_id": self.student_id,
            "evidence": evidence,
            "confidence": confidence,
            "proposed_fields": update_fields,
            "lifecycle": lifecycle,
            "review_reason": review_reason,
            "timestamp": utc_now_iso(),
        }
        if lifecycle == "deferred_teacher_review":
            self.teacher_review_queue.append(review_entry)

        message["policy_decision"] = {
            **message.get("policy_decision", {}),
            "lifecycle": lifecycle,
            "review_reason": review_reason,
        }
        self.audit_chain.append(
            event_type="profile_update_gate",
            message=message,
            decision=decision,
            reason=review_reason,
            policy_id=message["policy_decision"].get("policy_id", "cg.v2.profile_update"),
            risk_score=message.get("disclosure_score", 0.0),
        )
        result = {
            "approved_for_profile_update_review": lifecycle == "evidence_logged_for_review",
            "direct_profile_update_performed": False,
            "decision": lifecycle,
            "action": decision.value,
            "lifecycle": lifecycle,
            "review_reason": review_reason,
            "confidence": confidence,
            "proposed_fields": update_fields,
            "teacher_review_required": lifecycle == "deferred_teacher_review",
            "review_queue_id": review_entry["review_id"]
            if lifecycle == "deferred_teacher_review"
            else None,
            "round_id": round_id,
            "timestamp": utc_now_iso(),
        }
        self.message_log.append(message)
        return result

    def final_answer_audit(
        self,
        teaching_answer: str,
        assessment_result: dict[str, Any],
        round_id: str,
    ) -> dict[str, Any]:
        payload = {
            "teaching_answer": teaching_answer,
            "assessment_result": assessment_result,
        }
        message = self.build_message(
            sender="CGController",
            receiver="HSW-ST",
            message_type="final_answer_audit",
            payload=payload,
            privacy_level="audited_output",
            round_id=round_id,
        )
        self._authorize_message(message)
        self._emit_message_event(message, "final_answer_audit")

        if self.hsw_st_auditor is not None and hasattr(self.hsw_st_auditor, "audit"):
            audit = self.hsw_st_auditor.audit(teaching_answer, assessment_result)
        elif callable(self.hsw_st_auditor):
            audit = self.hsw_st_auditor(teaching_answer, assessment_result)
        else:
            audit = {
                "audit_status": "passed_fallback_audit",
                "watermark_trace_status": "pending_hsw_st_runtime",
                "answer_summary": summarize_text(teaching_answer, 220),
            }

        result = {
            "round_id": round_id,
            "timestamp": utc_now_iso(),
            "audit": audit,
            "cg_policy_decision": message.get("policy_decision"),
            "audit_chain_head": self.audit_chain_head,
        }
        self.message_log.append(message)
        return result

    def _emit_message_event(self, message: dict[str, Any], direction: str) -> None:
        if self.event_sink is None:
            return
        try:
            self.event_sink(
                {
                    "type": "cg_message",
                    "direction": direction,
                    "message": {
                        key: value
                        for key, value in message.items()
                        if key != "payload"
                    },
                    "payload": message.get("payload"),
                    "timestamp": utc_now_iso(),
                }
            )
        except Exception:
            return

    def _purpose_for_message_type(self, message_type: str) -> str:
        if message_type == "controlled_resource_request":
            return "controlled_resource_retrieval"
        if message_type == "teaching_generation_request":
            return "teaching_generation"
        if message_type == "profile_update_evidence":
            return "profile_update_review"
        if message_type.endswith(".result") or message_type == "final_answer_audit":
            return "audit_only"
        return "legitimate_educational_interest"

    def disclosure_score(self, payload: Any) -> float:
        """Compatibility API backed by the v2 field-level RiskScorer."""
        return self.risk_scorer.score(payload, "CGController")[0]

    def _authorize_message(self, message: dict[str, Any]) -> dict[str, Any]:
        decision, policy = self.policy_router.evaluate(
            message,
            session_id=self.session_id,
            student_id=self.student_id,
            forbidden_fields=set(COMMON_FORBIDDEN_INPUTS),
        )
        policy["action"] = decision.value
        message["policy_decision"] = policy

        # Compliance has precedence in the audit story: a policy denial explains
        # the legal reason before the generic raw-boundary violation.
        compliance_policy = self._evaluate_message_compliance(message)
        message["compliance_policy"] = compliance_policy
        self.last_compliance_policy = compliance_policy
        if compliance_policy["decision"] in {"deny", "require_parental_consent"}:
            self._record_compliance_event(
                event_type="policy_denial",
                actor_role="system",
                data_category="education_record",
                decision=compliance_policy["decision"],
                legal_context=compliance_policy.get("legal_context", "internal_policy"),
                details={
                    "sender": message["sender"],
                    "receiver": message["receiver"],
                    "blocked_fields": compliance_policy["blocked_fields"],
                },
            )
            self.audit_chain.append(
                event_type="compliance_decision",
                message=message,
                decision=CGDecision.DENY,
                reason=compliance_policy["reason"],
                policy_id=compliance_policy.get("policy_id", "compliance.policy"),
                risk_score=message.get("disclosure_score", 0.0),
            )
            raise AgentValidationError(
                "CG compliance policy blocked message: "
                f"{compliance_policy['reason']}"
            )

        if decision is CGDecision.DENY:
            self._record_policy_denial(message, policy)
            self.audit_chain.append(
                event_type="message_decision",
                message=message,
                decision=decision,
                reason=policy["reason"],
                policy_id=policy["policy_id"],
                risk_score=policy.get("risk_score", message.get("disclosure_score", 0.0)),
            )
            raise AgentValidationError(
                f"CG denied message ({policy['policy_id']}): {policy['reason']}"
            )

        if decision is CGDecision.DEFER:
            self.audit_chain.append(
                event_type="message_decision",
                message=message,
                decision=decision,
                reason=policy["reason"],
                policy_id=policy["policy_id"],
                risk_score=policy.get("risk_score", 0.0),
            )
            raise AgentValidationError(
                f"CG deferred message for governance review: {policy['reason']}"
            )

        if decision is CGDecision.SANITIZE:
            matched = set(policy.get("matched_fields", []))
            message["payload"] = sanitize_payload(message["payload"], matched)
            message["disclosure_score"], message["risk_breakdown"] = (
                self.risk_scorer.score(
                    message["payload"], message["receiver"], message.get("purpose", "unspecified")
                )
            )
            message["cg_action"] = "sanitized"
        elif decision is CGDecision.DEGRADE:
            if isinstance(message["payload"], dict):
                message["payload"] = degrade_payload(message["payload"])
                message["disclosure_score"], message["risk_breakdown"] = (
                    self.risk_scorer.score(
                        message["payload"], message["receiver"], message.get("purpose", "unspecified")
                    )
                )
            message["cg_action"] = "degraded"

        budget_state = self.policy_router.consume(
            message, self.session_id, self.student_id
        )
        message["budget_state"] = budget_state
        if budget_state.get("exceeded_scopes"):
            self.audit_chain.append(
                event_type="budget_decision",
                message=message,
                decision=CGDecision.DENY,
                reason=f"degraded payload still exceeds budget: {budget_state['exceeded_scopes']}",
                policy_id="cg.v2.cumulative_budget",
                risk_score=message.get("disclosure_score", 0.0),
            )
            raise AgentValidationError(
                "CG cumulative privacy budget exceeded after degradation: "
                f"{budget_state['exceeded_scopes']}"
            )
        self._record_compliance_event(
            event_type=self._compliance_event_type(message),
            actor_role="system",
            data_category=self._message_primary_data_category(message),
            decision=compliance_policy["decision"],
            legal_context=compliance_policy.get("legal_context", "internal_policy"),
            details={
                "sender": message["sender"],
                "receiver": message["receiver"],
                "retention_action": compliance_policy["retention_action"],
                "third_party_model_policy": compliance_policy["third_party_model_policy"],
                "cg_action": decision.value,
            },
        )

        if self.guardrail_adapter is not None:
            # The domain policy, compliance checks and transforms above own
            # their decisions. An integrated adapter may now run independent
            # checks without reapplying broad domain request heuristics.
            trusted_check = getattr(self.guardrail_adapter, "check_authorized_message", None)
            if callable(trusted_check):
                guardrail_decision = trusted_check(message)
            else:
                guardrail_decision = self.guardrail_adapter.check_message(message)
            message["guardrail_decision"] = guardrail_decision
            if not guardrail_decision.get("allowed", True):
                self.audit_chain.append(
                    event_type="guardrail_decision",
                    message=message,
                    decision=CGDecision.DENY,
                    reason=str(guardrail_decision.get("reason") or guardrail_decision.get("decision")),
                    policy_id="cg.v2.guardrail_adapter",
                    risk_score=message.get("disclosure_score", 0.0),
                )
                raise AgentValidationError(
                    "CG guardrail adapter blocked message: "
                    f"{guardrail_decision.get('reason') or guardrail_decision.get('decision')}"
                )

        charge_domain_budget(
            "privacy", float(message.get("disclosure_score", 0.0)),
            key=f"cg-message:{message['message_id']}",
        )
        self.audit_chain.append(
            event_type="message_decision",
            message=message,
            decision=decision,
            reason=policy["reason"],
            policy_id=policy["policy_id"],
            risk_score=message.get("disclosure_score", 0.0),
        )
        return message["payload"]

    def _record_policy_denial(
        self, message: dict[str, Any], policy: dict[str, Any]
    ) -> None:
        self._record_compliance_event(
            event_type="policy_denial",
            actor_role="system",
            data_category=self._message_primary_data_category(message),
            decision="deny",
            legal_context="internal_policy",
            details={
                "sender": message["sender"],
                "receiver": message["receiver"],
                "policy_id": policy.get("policy_id"),
                "reason": policy.get("reason"),
            },
        )

    def _find_forbidden_keys(self, value: Any) -> set[str]:
        forbidden = set()
        forbidden_inputs = set(COMMON_FORBIDDEN_INPUTS)
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in forbidden_inputs:
                    forbidden.add(key)
                forbidden.update(self._find_forbidden_keys(nested))
        elif isinstance(value, list):
            for item in value:
                forbidden.update(self._find_forbidden_keys(item))
        return forbidden

    def _evaluate_message_compliance(self, message: dict[str, Any]) -> dict[str, Any]:
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        data_scope = self._message_data_scope(message)
        payload_kind = (
            "audit"
            if data_scope == "audit_chain"
            else "student_profile"
            if data_scope in {"raw_profile", "raw_multimodal_profile"}
            else "context_card"
            if data_scope == "context_card"
            else "profile_encoding"
        )
        request = {
            "action": self._message_compliance_action(message),
            "actor_role": "system",
            "data_scope": data_scope,
            "purpose": "audit" if data_scope == "audit_chain" else "legitimate_educational_interest",
        }
        category_source = (
            payload
            if data_scope in {"raw_profile", "raw_multimodal_profile"}
            else payload.get("context_card")
            if isinstance(payload.get("context_card"), dict)
            else payload
        )
        return evaluate_compliance_policy(
            request,
            self.compliance_state,
            build_data_categories(category_source, payload_kind=payload_kind),
        )

    def _message_compliance_action(self, message: dict[str, Any]) -> str:
        if message.get("receiver") == "HSW-ST":
            return "audit_persist"
        runtime = get_runtime_status()
        if runtime.get("agent_call_mode") == "real_llm" and message.get("receiver") != "CGController":
            return "third_party_call"
        return "profile_access"

    def _message_data_scope(self, message: dict[str, Any]) -> str:
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        payload_text = str(payload)
        if any(token in payload for token in ("raw_multimodal_data", "raw_student_data", "full_student_profile")):
            return "raw_multimodal_profile"
        if any(token in payload_text for token in ("raw_screenshot", "voice_recording", "handwriting_trace")):
            return "raw_multimodal_profile"
        if message.get("receiver") == "HSW-ST":
            return "audit_chain"
        if isinstance(payload.get("context_card"), dict):
            return "context_card"
        return "derived_profile"

    def _message_primary_data_category(self, message: dict[str, Any]) -> str:
        scope = self._message_data_scope(message)
        if scope == "audit_chain":
            return "audit_metadata"
        if scope in {"raw_profile", "raw_multimodal_profile"}:
            return "education_record"
        return "derived_profile"

    def _compliance_event_type(self, message: dict[str, Any]) -> str:
        if self._message_compliance_action(message) == "third_party_call":
            return "third_party_call"
        if message.get("receiver") == "HSW-ST":
            return "data_minimization"
        return "profile_access"

    def _record_compliance_event(
        self,
        *,
        event_type: str,
        actor_role: str,
        data_category: str,
        decision: str,
        legal_context: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return append_compliance_audit_event(
            self.compliance_audit_log,
            event_type=event_type,
            actor_role=actor_role,
            data_category=data_category,
            decision=decision,
            legal_context=legal_context,
            details=details,
        )


class AgentOrchestrator:
    """Runs the protected MM-FOPD -> CG -> agents -> HSW-ST flow."""

    def __init__(
        self,
        mm_fopd_service: Any | None = None,
        c2rag_service: Any | None = None,
        hsw_st_auditor: Any | None = None,
        llm_client: Any | None = None,
        cg_controller: CGController | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
        compliance_state: dict[str, Any] | None = None,
    ) -> None:
        self.mm_fopd_service = mm_fopd_service
        self.runtime_status = get_runtime_status()
        self.cg = cg_controller or CGController(
            hsw_st_auditor=hsw_st_auditor,
            guardrail_adapter=build_guardrail_adapter(),
            event_sink=event_sink,
            compliance_state=compliance_state,
        )
        if llm_client is None:
            llm_client = build_runtime_llm_client()
        self.profile_diagnosis_agent = ProfileDiagnosisAgent(
            llm_client=llm_client,
            event_sink=event_sink,
        )
        self.resource_agent = CopyrightAwareResourceAgent(
            c2rag_service=c2rag_service,
            llm_client=llm_client,
            event_sink=event_sink,
        )
        
        # 初始化水印系统用于教学代理
        watermark_system = None
        if HybridWatermarkSystem:
            watermark_system = HybridWatermarkSystem({"hsw": {}})
        
        self.teaching_agent = PedagogicalTeachingAgent(
            llm_client=llm_client,
            event_sink=event_sink,
            watermark_system=watermark_system,
        )
        self.assessment_agent = LearningAssessmentAgent(
            llm_client=llm_client,
            event_sink=event_sink,
        )

    def run_protected_flow(
        self,
        student_multimodal_data: dict[str, Any],
        student_response: str = "",
        round_id: str | None = None,
        session_id: str | None = None,
        student_id: str | None = None,
    ) -> dict[str, Any]:
        round_id = round_id or f"round_{uuid.uuid4().hex[:12]}"
        if session_id is not None:
            self.cg.session_id = session_id
        if student_id is not None:
            self.cg.student_id = student_id
        from cogniguard.workflows.education.protected_turn import run_protected_turn
        return run_protected_turn(self, student_multimodal_data, student_response, round_id)

    def _build_mm_fopd_context_card(
        self, student_multimodal_data: dict[str, Any]
    ) -> dict[str, Any]:
        if isinstance(student_multimodal_data.get("context_card"), dict):
            card = dict(student_multimodal_data["context_card"])
            card.setdefault("fopd_path", "enhanced")
            card.setdefault("use_enhanced_fopd", True)
            return card
        if self.mm_fopd_service is not None and hasattr(
            self.mm_fopd_service, "build_context_card"
        ):
            card = dict(self.mm_fopd_service.build_context_card(student_multimodal_data))
            card.setdefault("fopd_path", "enhanced")
            card.setdefault("use_enhanced_fopd", True)
            return card
        if callable(self.mm_fopd_service):
            card = dict(self.mm_fopd_service(student_multimodal_data))
            card.setdefault("fopd_path", "enhanced")
            card.setdefault("use_enhanced_fopd", True)
            return card

        return {
            "knowledge_point": student_multimodal_data.get(
                "knowledge_point", "unknown_knowledge_point"
            ),
            "task_difficulty": student_multimodal_data.get("difficulty", "unknown"),
            "learner_state": student_multimodal_data.get(
                "learner_state", "not_diagnosed"
            ),
            "common_error": student_multimodal_data.get(
                "common_error", "not_enough_evidence"
            ),
            "recommended_strategy": student_multimodal_data.get(
                "recommended_strategy", "step_by_step_scaffold"
            ),
            "privacy_note": (
                "MM-FOPD context card excludes raw multimodal data and full "
                "long-term profile."
            ),
            "fopd_path": "enhanced",
            "use_enhanced_fopd": True,
        }

    def _build_enhanced_profile_encoding(
        self,
        student_multimodal_data: dict[str, Any],
        context_card: dict[str, Any],
    ) -> dict[str, Any]:
        provided = student_multimodal_data.get("profile_encoding")
        if isinstance(provided, dict) and provided:
            return {**provided, "fopd_path": provided.get("fopd_path", "enhanced")}

        labels = {
            "knowledge_point": context_card.get("knowledge_point", "unknown_knowledge_point"),
            "mastery_level": context_card.get("student_level")
            or context_card.get("learner_state")
            or "unknown",
            "error_type": context_card.get("current_error_type")
            or context_card.get("common_error")
            or "not_enough_evidence",
            "learning_stage": context_card.get("learner_state_summary")
            or context_card.get("learner_state")
            or "not_diagnosed",
            "sensitivity_level": context_card.get("risk_level")
            or context_card.get("privacy_level")
            or "bounded",
            "recordable_scope": ",".join(map(str, context_card.get("recordable_scope", [])))
            if isinstance(context_card.get("recordable_scope"), list)
            else context_card.get("recordable_scope", "bounded"),
            "hint_depth": context_card.get("resource_need", "medium"),
            "teaching_strategy": context_card.get("suggested_teaching_strategy")
            or context_card.get("recommended_strategy")
            or "scaffold_then_variant",
        }
        return {
            "fopd_path": "enhanced",
            "base_embedding_dim": 0,
            "subspace_dims": {
                "learning_state": 0,
                "privacy_boundary": 0,
                "teaching_need": 0,
            },
            "labels": labels,
            "textual_cards": {
                "learning_card": (
                    f"knowledge={labels['knowledge_point']}; "
                    f"error={labels['error_type']}; stage={labels['learning_stage']}"
                ),
                "privacy_card": (
                    "Enhanced FOPD exposes only abstract labels and minimum "
                    "task context; raw multimodal artifacts stay local."
                ),
                "teaching_card": str(labels["teaching_strategy"]),
                "abstract_card": "enhanced_fopd_disentangled_profile_bundle",
            },
        }


def _normalized_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _profile_update_fields(evidence: dict[str, Any]) -> list[str]:
    for key in ("proposed_fields", "update_fields", "fields"):
        value = evidence.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, dict):
            return [str(key) for key in value]
    proposed = evidence.get("proposed_update")
    if isinstance(proposed, dict):
        return [str(key) for key in proposed]
    return []


def _teaching_request_from_context(
    context_card: dict[str, Any], diagnosis_result: dict[str, Any]
) -> dict[str, Any]:
    return {
        "knowledge_point": diagnosis_result["knowledge_point"],
        "learner_state": diagnosis_result["learner_state"],
        "suggested_teaching_strategy": diagnosis_result[
            "suggested_teaching_strategy"
        ],
        "task_difficulty": context_card.get("task_difficulty", "unknown"),
    }


def _asks_for_full_profile(lowered_request: str) -> bool:
    return (
        "full learning profile" in lowered_request
        or "full student profile" in lowered_request
        or "long-term student profile" in lowered_request
        or "完整画像" in lowered_request
    )


def _asks_for_raw_multimodal_data(lowered_request: str) -> bool:
    raw_tokens = ("raw", "screenshot", "handwriting trace", "image", "audio")
    return (
        "wrong-answer screenshot" in lowered_request
        or "handwriting trace" in lowered_request
        or "raw multimodal" in lowered_request
        or "原始" in lowered_request
        or ("raw" in lowered_request and any(token in lowered_request for token in raw_tokens))
    )


def _minimized_profile_summary(
    context_card: dict[str, Any] | None,
) -> dict[str, Any]:
    if not context_card:
        return {}
    allowed = context_card.get("allowed_profile_fields")
    if not isinstance(allowed, list):
        allowed = [
            "student_hash",
            "task_id",
            "knowledge_point",
            "current_error_type",
            "learner_state_summary",
            "suggested_teaching_strategy",
        ]
    return {key: context_card[key] for key in allowed if key in context_card}


def _profile_update_pollution_reason(evidence: dict[str, Any]) -> str | None:
    if evidence.get("direct_profile_update_requested"):
        return "rejected_direct_self_report_profile_update"
    source = str(evidence.get("evidence_source", "")).lower()
    if source in {"self_report", "self_report_only"}:
        return "rejected_self_report_only_profile_update"
    summary = str(evidence.get("observed_response_summary", "")).lower()
    if "update my profile" in summary or "profile to excellent" in summary:
        return "rejected_direct_self_report_profile_update"
    return None
