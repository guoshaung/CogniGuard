from __future__ import annotations

import uuid
from typing import Any, Callable

from .base_agent import (
    COMMON_FORBIDDEN_INPUTS,
    AgentValidationError,
    BaseAgent,
    summarize_text,
    utc_now_iso,
)
from .copyright_aware_resource_agent import CopyrightAwareResourceAgent
from .learning_assessment_agent import LearningAssessmentAgent
from .pedagogical_teaching_agent import PedagogicalTeachingAgent
from .profile_diagnosis_agent import ProfileDiagnosisAgent
from backend.app.compliance import (
    append_compliance_audit_event,
    build_compliance_state,
    build_data_categories,
    evaluate_compliance_policy,
    sanitize_context_card,
)
from backend.app.runtime.mode import (
    build_guardrail_adapter,
    build_runtime_llm_client,
    get_runtime_status,
)

try:
    from protection.audit_trace.src.hybrid_watermark import HybridWatermarkSystem
except ImportError:
    HybridWatermarkSystem = None


class TPCSController:
    """Trusted policy controller for all inter-agent communication."""

    def __init__(
        self,
        max_disclosure_score: float = 0.75,
        cumulative_privacy_budget: float = 3.0,
        hsw_st_auditor: Any | None = None,
        guardrail_adapter: Any | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
        compliance_state: dict[str, Any] | None = None,
    ) -> None:
        self.max_disclosure_score = max_disclosure_score
        self.cumulative_privacy_budget = cumulative_privacy_budget
        self.hsw_st_auditor = hsw_st_auditor
        self.guardrail_adapter = guardrail_adapter
        self.event_sink = event_sink
        self.compliance_state = compliance_state or build_compliance_state()
        self.compliance_audit_log: list[dict[str, Any]] = []
        self.last_compliance_policy: dict[str, Any] | None = None
        self.message_log: list[dict[str, Any]] = []
        self.cumulative_disclosure_by_round: dict[str, float] = {}
        self.allowed_routes = {
            ("MM-FOPD", "profile_diagnosis_agent"),
            ("profile_diagnosis_agent", "TPCSController"),
            ("profile_diagnosis_agent", "copyright_aware_resource_agent"),
            ("copyright_aware_resource_agent", "TPCSController"),
            ("copyright_aware_resource_agent", "pedagogical_teaching_agent"),
            ("pedagogical_teaching_agent", "TPCSController"),
            ("pedagogical_teaching_agent", "learning_assessment_agent"),
            ("learning_assessment_agent", "TPCSController"),
            ("TPCSController", "HSW-ST"),
        }

    def build_message(
        self,
        sender: str,
        receiver: str,
        message_type: str,
        payload: dict[str, Any],
        privacy_level: str,
        round_id: str,
    ) -> dict[str, Any]:
        return {
            "sender": sender,
            "receiver": receiver,
            "message_type": message_type,
            "privacy_level": privacy_level,
            "disclosure_score": self.disclosure_score(payload),
            "round_id": round_id,
            "timestamp": utc_now_iso(),
            "payload": payload,
        }

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
                "reason": "TPCS blocks full learning profile disclosure and permits only MM-FOPD minimized teaching fields.",
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
        )
        self._authorize_message(message)
        self._emit_message_event(message, "request")
        receiver.validate_input(payload)
        output = receiver.generate(payload)
        response = self.build_message(
            sender=receiver.agent_id,
            receiver="TPCSController",
            message_type=f"{message_type}.result",
            payload=output,
            privacy_level=privacy_level,
            round_id=round_id,
        )
        self._authorize_message(response)
        self._emit_message_event(response, "response")
        self.message_log.extend([message, response])
        return message, output, response

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
                f"TPCS rejected forbidden context fields: {sorted(forbidden)}"
            )
        score = self.disclosure_score(context_card)
        approved = score <= self.max_disclosure_score
        result = {
            "approved": approved,
            "stage": "TPCS pre-check",
            "privacy_level": "minimum_context",
            "disclosure_score": score,
            "round_id": round_id,
            "timestamp": utc_now_iso(),
            "compliance_policy": compliance_policy,
            "data_categories": data_categories,
        }
        if not approved:
            raise AgentValidationError(
                f"TPCS rejected context card disclosure_score={score}"
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
            receiver="TPCSController",
            message_type="profile_update_evidence",
            payload={"profile_update_evidence": evidence},
            privacy_level="evidence_only",
            round_id=round_id,
        )
        self._authorize_message(message)
        self._emit_message_event(message, "profile_update_evidence")
        pollution_reason = _profile_update_pollution_reason(evidence)
        approved = bool(evidence.get("requires_tpcs_approval", True)) and not pollution_reason
        result = {
            "approved_for_profile_update_review": approved,
            "direct_profile_update_performed": False,
            "decision": (
                "evidence_logged_for_review"
                if approved
                else pollution_reason or "rejected"
            ),
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
            sender="TPCSController",
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
        }
        self.message_log.append(message)
        return result

    def _emit_message_event(self, message: dict[str, Any], direction: str) -> None:
        if self.event_sink is None:
            return
        try:
            self.event_sink(
                {
                    "type": "tpcs_message",
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

    def disclosure_score(self, payload: Any) -> float:
        text = str(payload)
        score = min(0.45, len(text) / 4000)
        sensitive_tokens = (
            "raw_multimodal_data",
            "full_student_profile",
            "long_term_student_profile",
            "full_teacher_resources",
            "school",
            "family",
            "address",
            "phone",
            "id_card",
        )
        score += sum(0.1 for token in sensitive_tokens if token in text)
        return round(min(1.0, score), 4)

    def _authorize_message(self, message: dict[str, Any]) -> None:
        route = (message["sender"], message["receiver"])
        if route not in self.allowed_routes:
            raise AgentValidationError(f"TPCS route denied: {route}")
        forbidden = self._find_forbidden_keys(message.get("payload"))
        if forbidden:
            raise AgentValidationError(
                f"TPCS rejected forbidden payload fields: {sorted(forbidden)}"
            )
        if message["disclosure_score"] > self.max_disclosure_score:
            raise AgentValidationError(
                "TPCS disclosure score exceeded: "
                f"{message['disclosure_score']} > {self.max_disclosure_score}"
            )
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
            raise AgentValidationError(
                "TPCS compliance policy blocked message: "
                f"{compliance_policy['reason']}"
            )
        if (
            compliance_policy["decision"] == "local_only"
            and self._message_data_scope(message) in {"raw_profile", "raw_multimodal_profile"}
        ):
            self._record_compliance_event(
                event_type="policy_denial",
                actor_role="system",
                data_category="education_record",
                decision="local_only",
                legal_context=compliance_policy.get("legal_context", "internal_policy"),
                details={
                    "sender": message["sender"],
                    "receiver": message["receiver"],
                    "blocked_fields": compliance_policy["blocked_fields"],
                },
            )
            raise AgentValidationError(
                "TPCS compliance policy kept payload local-only: "
                f"{compliance_policy['reason']}"
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
            },
        )
        round_id = str(message.get("round_id") or "default")
        current = self.cumulative_disclosure_by_round.get(round_id, 0.0)
        updated = current + float(message["disclosure_score"])
        if updated > self.cumulative_privacy_budget:
            raise AgentValidationError(
                "TPCS cumulative privacy budget exceeded: "
                f"{updated:.4f} > {self.cumulative_privacy_budget}"
            )
        self.cumulative_disclosure_by_round[round_id] = round(updated, 4)
        if self.guardrail_adapter is not None:
            guardrail_decision = self.guardrail_adapter.check_message(message)
            message["guardrail_decision"] = guardrail_decision
            if not guardrail_decision.get("allowed", True):
                raise AgentValidationError(
                    "TPCS guardrail adapter blocked message: "
                    f"{guardrail_decision.get('reason') or guardrail_decision.get('decision')}"
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
        if runtime.get("agent_call_mode") == "real_llm" and message.get("receiver") != "TPCSController":
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
    """Runs the protected MM-FOPD -> TPCS -> agents -> HSW-ST flow."""

    def __init__(
        self,
        mm_fopd_service: Any | None = None,
        c2rag_service: Any | None = None,
        hsw_st_auditor: Any | None = None,
        llm_client: Any | None = None,
        tpcs_controller: TPCSController | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
        compliance_state: dict[str, Any] | None = None,
    ) -> None:
        self.mm_fopd_service = mm_fopd_service
        self.runtime_status = get_runtime_status()
        self.tpcs = tpcs_controller or TPCSController(
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
    ) -> dict[str, Any]:
        round_id = round_id or f"round_{uuid.uuid4().hex[:12]}"

        context_card = sanitize_context_card(
            self._build_mm_fopd_context_card(student_multimodal_data)
        )
        profile_encoding = self._build_enhanced_profile_encoding(
            student_multimodal_data,
            context_card,
        )
        tpcs_pre_check = self.tpcs.pre_check_context_card(context_card, round_id)

        _, diagnosis_output, _ = self.tpcs.dispatch(
            sender="MM-FOPD",
            receiver=self.profile_diagnosis_agent,
            message_type="diagnosis_request",
            payload={
                "profile_encoding": profile_encoding,
                "context_card": context_card,
            },
            privacy_level="minimum_context",
            round_id=round_id,
        )
        diagnosis_result = diagnosis_output["diagnosis_result"]

        resource_payload = {
            "teaching_request": _teaching_request_from_context(
                context_card, diagnosis_result
            ),
            "knowledge_point": diagnosis_result["knowledge_point"],
            "allowed_return_modes": ["summary", "outline", "snippet", "variant"],
        }
        _, resource_output, _ = self.tpcs.dispatch(
            sender=self.profile_diagnosis_agent.agent_id,
            receiver=self.resource_agent,
            message_type="controlled_resource_request",
            payload=resource_payload,
            privacy_level="teaching_need_only",
            round_id=round_id,
        )

        teaching_payload = {
            "context_card": context_card,
            "diagnosis_result": diagnosis_result,
            "controlled_resource_snippets": resource_output[
                "controlled_resource_snippets"
            ],
            "profile_encoding": profile_encoding,
        }
        _, teaching_output, _ = self.tpcs.dispatch(
            sender=self.resource_agent.agent_id,
            receiver=self.teaching_agent,
            message_type="teaching_generation_request",
            payload=teaching_payload,
            privacy_level="minimum_context_plus_controlled_resource",
            round_id=round_id,
        )

        assessment_payload = {
            "teaching_answer": teaching_output["teaching_answer"],
            "student_response": student_response,
            "knowledge_point": diagnosis_result["knowledge_point"],
            "profile_encoding": profile_encoding,
        }
        _, assessment_output, _ = self.tpcs.dispatch(
            sender=self.teaching_agent.agent_id,
            receiver=self.assessment_agent,
            message_type="learning_assessment_request",
            payload=assessment_payload,
            privacy_level="answer_and_response_only",
            round_id=round_id,
        )

        profile_update_approval = self.tpcs.approve_profile_update_evidence(
            assessment_output["profile_update_evidence"],
            round_id=round_id,
        )
        final_answer_audit = self.tpcs.final_answer_audit(
            teaching_output["teaching_answer"],
            assessment_output,
            round_id=round_id,
        )

        return {
            "round_id": round_id,
            "context_card": context_card,
            "profile_encoding": profile_encoding,
            "tpcs_pre_check": tpcs_pre_check,
            "diagnosis_result": diagnosis_result,
            "controlled_resource_snippets": resource_output[
                "controlled_resource_snippets"
            ],
            "teaching_answer": teaching_output["teaching_answer"],
            "teaching_strategy_used": teaching_output["teaching_strategy_used"],
            "assessment_result": assessment_output,
            "profile_update_approval": profile_update_approval,
            "final_answer_audit": final_answer_audit,
            "agent_messages": list(self.tpcs.message_log),
        }

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
