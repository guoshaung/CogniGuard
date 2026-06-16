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
    ) -> None:
        self.max_disclosure_score = max_disclosure_score
        self.cumulative_privacy_budget = cumulative_privacy_budget
        self.hsw_st_auditor = hsw_st_auditor
        self.guardrail_adapter = guardrail_adapter
        self.event_sink = event_sink
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
        }
        if not approved:
            raise AgentValidationError(
                f"TPCS rejected context card disclosure_score={score}"
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
    ) -> None:
        self.mm_fopd_service = mm_fopd_service
        self.runtime_status = get_runtime_status()
        self.tpcs = tpcs_controller or TPCSController(
            hsw_st_auditor=hsw_st_auditor,
            guardrail_adapter=build_guardrail_adapter(),
            event_sink=event_sink,
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

        context_card = self._build_mm_fopd_context_card(student_multimodal_data)
        tpcs_pre_check = self.tpcs.pre_check_context_card(context_card, round_id)

        _, diagnosis_output, _ = self.tpcs.dispatch(
            sender="MM-FOPD",
            receiver=self.profile_diagnosis_agent,
            message_type="diagnosis_request",
            payload={"context_card": context_card},
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
        if self.mm_fopd_service is not None and hasattr(
            self.mm_fopd_service, "build_context_card"
        ):
            return dict(self.mm_fopd_service.build_context_card(student_multimodal_data))
        if callable(self.mm_fopd_service):
            return dict(self.mm_fopd_service(student_multimodal_data))

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
