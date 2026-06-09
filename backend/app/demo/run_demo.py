from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agents.agent_orchestrator import TPCSController
from backend.app.agents.base_agent import AgentValidationError, utc_now_iso
from backend.app.agents.copyright_aware_resource_agent import (
    CopyrightAwareResourceAgent,
)
from backend.app.agents.learning_assessment_agent import LearningAssessmentAgent
from backend.app.agents.pedagogical_teaching_agent import PedagogicalTeachingAgent
from backend.app.agents.profile_diagnosis_agent import ProfileDiagnosisAgent
from backend.app.demo.demo_cases import load_demo_case
from backend.app.runtime.mode import (
    build_guardrail_adapter,
    build_runtime_llm_client,
    get_runtime_status,
)


FRAMEWORK_ARCHITECTURE = {
    "top_level_architecture": "three_layer_protection_framework_plus_horizontal_tpcs_governance",
    "vertical_layers": [
        "User-side MM-FOPD minimum disclosure",
        "Teaching-side C2-RAG copyright and exposure control",
        "Output-side HSW-ST watermark, trace, and audit",
    ],
    "horizontal_governance": "TPCSController mediates every protected transfer and profile update decision.",
    "agent_role": "LLM tutoring agents are controlled execution nodes, not the top-level architecture.",
}


class EventedWorkflowSteps(list[dict[str, Any]]):
    def __init__(
        self,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__()
        self.event_sink = event_sink

    def append(self, step: dict[str, Any]) -> None:
        super().append(step)
        if self.event_sink is None:
            return
        try:
            self.event_sink(
                {
                    "type": "workflow_step",
                    "step": step,
                    "completed_steps": len(self),
                    "timestamp": utc_now_iso(),
                }
            )
        except Exception:
            return


class DemoC2RAGService:
    """Small deterministic C2-RAG adapter for the runnable demo."""

    def retrieve(
        self,
        teaching_request: dict[str, Any],
        knowledge_point: str,
        allowed_return_modes: list[str],
    ) -> list[dict[str, Any]]:
        return_mode = "summary" if "summary" in allowed_return_modes else allowed_return_modes[0]
        return [
            {
                "resource_id": f"teacher_resource_{_slug(knowledge_point)}",
                "chunk_id": f"chunk_{_short_hash(json.dumps(teaching_request, sort_keys=True))}",
                "copyright_level": 0.42,
                "return_mode": return_mode,
                "content": (
                    f"For {knowledge_point}, use a brief rule reminder, contrast "
                    "the common mistake, and ask the learner to explain one "
                    "step before giving a full worked solution."
                ),
                "exposure_cost": 0.14,
            }
        ]


class DemoHSWSTBinder:
    """Binds the final answer to a demo watermark and audit trace."""

    def bind(
        self,
        teaching_answer: str,
        answer_id: str,
        profile_card_id: str,
        controlled_resource_snippets: list[dict[str, Any]],
        agent_call_logs: list[dict[str, Any]],
        communication_logs: list[dict[str, Any]],
        profile_update_logs: dict[str, Any],
    ) -> dict[str, Any]:
        watermark_id = f"wm_{_short_hash(answer_id + teaching_answer, length=12)}"
        final_answer = (
            f"{teaching_answer}\n\n"
            f"[HSW-ST audit_ref={watermark_id}; answer_id={answer_id}]"
        )
        resource_bindings = [
            {
                "resource_id": snippet["resource_id"],
                "chunk_id": snippet["chunk_id"],
                "return_mode": snippet["return_mode"],
                "exposure_cost": snippet["exposure_cost"],
            }
            for snippet in controlled_resource_snippets
        ]
        trace = {
            "answer_id": answer_id,
            "watermark_id": watermark_id,
            "profile_card_id": profile_card_id,
            "resource_id": resource_bindings[0]["resource_id"] if resource_bindings else None,
            "chunk_id": resource_bindings[0]["chunk_id"] if resource_bindings else None,
            "resource_bindings": resource_bindings,
            "agent_call_logs": agent_call_logs,
            "communication_logs": communication_logs,
            "profile_update_logs": profile_update_logs,
            "watermarked_answer_sha256": hashlib.sha256(
                final_answer.encode("utf-8")
            ).hexdigest(),
            "audit_status": "auditable_demo_watermark_bound",
            "watermark_note": (
                "Runnable demo uses a visible HSW-ST audit reference. Production "
                "can replace this binder with hsw_st_minimal KGW watermarking."
            ),
            "timestamp": utc_now_iso(),
        }
        return {"final_protected_answer": final_answer, "audit_trace": trace}


def run_demo(
    data_root: str | Path = "data",
    case_index: int = 0,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    demo_case = load_demo_case(data_root=data_root, case_index=case_index)
    round_id = f"round_{demo_case.task_id}_{uuid.uuid4().hex[:12]}"
    answer_id = f"ans_{round_id}"
    runtime_status = get_runtime_status()
    llm_client = build_runtime_llm_client()
    if event_sink is not None:
        event_sink(
            {
                "type": "run_started",
                "round_id": round_id,
                "case_index": case_index,
                "task_id": demo_case.task_id,
                "knowledge_point": demo_case.context_card.get("knowledge_point"),
                "runtime_status": runtime_status,
                "timestamp": utc_now_iso(),
            }
        )
    tpcs = TPCSController(
        max_disclosure_score=0.75,
        guardrail_adapter=build_guardrail_adapter(),
        event_sink=event_sink,
    )
    workflow_steps = EventedWorkflowSteps(event_sink)
    nemo_logs: dict[str, Any] = {}

    profile_agent = ProfileDiagnosisAgent(
        llm_client=llm_client,
        event_sink=event_sink,
    )
    resource_agent = CopyrightAwareResourceAgent(
        c2rag_service=DemoC2RAGService(),
        llm_client=llm_client,
        event_sink=event_sink,
    )
    teaching_agent = PedagogicalTeachingAgent(
        llm_client=llm_client,
        event_sink=event_sink,
    )
    assessment_agent = LearningAssessmentAgent(
        llm_client=llm_client,
        event_sink=event_sink,
    )

    context_card = dict(demo_case.context_card)
    _append_workflow_step(
        workflow_steps,
        "MM-FOPD Context Card Generation",
        "MM-FOPD",
        {
            "student_hash": demo_case.student_hash,
            "task_id": demo_case.task_id,
            "raw_payload_sent_to_agents": False,
            "raw_data_paths_only": True,
        },
        {
            "context_card_id": context_card.get("context_card_id"),
            "knowledge_point": context_card.get("knowledge_point"),
            "allowed_profile_fields": context_card.get("allowed_profile_fields", []),
            "forbidden_profile_fields": context_card.get("forbidden_profile_fields", []),
            "privacy_level": context_card.get("privacy_level"),
            "disclosure_score": context_card.get("disclosure_score"),
        },
        "allow",
        "not_enabled",
        _risk_score(context_card, 0.23),
    )

    tpcs_risk_decision = _tpcs_context_card_decision(tpcs, context_card, round_id)
    _append_workflow_step(
        workflow_steps,
        "TPCS Privacy Pre-check",
        "TPCS",
        {
            "context_card_id": context_card.get("context_card_id"),
            "privacy_level": context_card.get("privacy_level"),
            "disclosure_score": context_card.get("disclosure_score"),
        },
        _summary_dict(tpcs_risk_decision),
        _tpcs_decision_label(tpcs_risk_decision),
        "not_enabled",
        _risk_score(tpcs_risk_decision, 0.2),
    )

    nemo_logs["input_rail"] = _run_nemo_rail(
        tpcs,
        stage="input_rail",
        payload={"context_card": context_card},
        context={"round_id": round_id, "task_id": demo_case.task_id},
    )
    _append_workflow_step(
        workflow_steps,
        "NeMo Input Rail",
        "TPCS Guardrail Adapter",
        {"context_card_id": context_card.get("context_card_id")},
        _summary_dict(nemo_logs["input_rail"]),
        "allow" if nemo_logs["input_rail"]["decision"] != "block" else "refuse",
        nemo_logs["input_rail"]["decision"],
        nemo_logs["input_rail"]["risk_score"],
    )

    diagnosis_request, diagnosis_output, diagnosis_response = tpcs.dispatch(
        sender="MM-FOPD",
        receiver=profile_agent,
        message_type="diagnosis_request",
        payload={"context_card": context_card},
        privacy_level="minimum_context",
        round_id=round_id,
    )
    diagnosis_result = diagnosis_output["diagnosis_result"]
    _append_workflow_step(
        workflow_steps,
        "ProfileDiagnosisAgent Diagnosis",
        "LLM Tutoring Agent",
        _message_summary(diagnosis_request),
        _summary_dict(diagnosis_output),
        _tpcs_message_label(diagnosis_request, diagnosis_response),
        _guardrail_label(diagnosis_request, diagnosis_response),
        _risk_score(diagnosis_response, 0.18),
    )

    resource_payload = {
        "teaching_request": {
            "task_id": context_card["task_id"],
            "knowledge_point": diagnosis_result["knowledge_point"],
            "current_error_type": diagnosis_result["error_type"],
            "learner_state": diagnosis_result["learner_state"],
            "requested_support": diagnosis_result["suggested_teaching_strategy"],
        },
        "knowledge_point": diagnosis_result["knowledge_point"],
        "allowed_return_modes": ["summary", "outline", "snippet", "variant"],
    }
    resource_request, resource_output, resource_response = tpcs.dispatch(
        sender=profile_agent.agent_id,
        receiver=resource_agent,
        message_type="controlled_resource_request",
        payload=resource_payload,
        privacy_level="teaching_need_only",
        round_id=round_id,
    )
    controlled_snippets = resource_output["controlled_resource_snippets"]
    _append_workflow_step(
        workflow_steps,
        "CopyrightAwareResourceAgent Retrieval Request",
        "LLM Tutoring Agent",
        _message_summary(resource_request),
        {"controlled_snippet_count": len(controlled_snippets)},
        _tpcs_message_label(resource_request, resource_response),
        _guardrail_label(resource_request, resource_response),
        _risk_score(resource_response, 0.2),
    )

    nemo_logs["retrieval_rail"] = _run_nemo_rail(
        tpcs,
        stage="retrieval_rail",
        payload={"controlled_resource_snippets": controlled_snippets},
        context={"round_id": round_id, "knowledge_point": resource_payload["knowledge_point"]},
    )
    if "sanitized_chunks" in nemo_logs["retrieval_rail"]:
        controlled_snippets = nemo_logs["retrieval_rail"]["sanitized_chunks"]
        resource_output["controlled_resource_snippets"] = controlled_snippets

    c2rag_log = _c2rag_protection_log(resource_agent, resource_payload, controlled_snippets)
    _append_workflow_step(
        workflow_steps,
        "C2-RAG Copyright Exposure Control",
        "C2-RAG",
        {
            "knowledge_point": resource_payload["knowledge_point"],
            "allowed_return_modes": resource_payload["allowed_return_modes"],
            "exposure_budget_before": c2rag_log["exposure_budget_before"],
        },
        _summary_dict(c2rag_log),
        c2rag_log["tpcs_decision"],
        "not_enabled",
        c2rag_log["risk_score"],
    )
    _append_workflow_step(
        workflow_steps,
        "NeMo Retrieval Rail",
        "TPCS Guardrail Adapter",
        {"controlled_snippet_count": len(controlled_snippets)},
        _summary_dict(nemo_logs["retrieval_rail"]),
        "allow" if nemo_logs["retrieval_rail"]["decision"] != "block" else "refuse",
        nemo_logs["retrieval_rail"]["decision"],
        nemo_logs["retrieval_rail"]["risk_score"],
    )

    teaching_request, teaching_output, teaching_response = tpcs.dispatch(
        sender=resource_agent.agent_id,
        receiver=teaching_agent,
        message_type="teaching_generation_request",
        payload={
            "context_card": context_card,
            "diagnosis_result": diagnosis_result,
            "controlled_resource_snippets": controlled_snippets,
        },
        privacy_level="minimum_context_plus_controlled_resource",
        round_id=round_id,
    )
    _append_workflow_step(
        workflow_steps,
        "PedagogicalTeachingAgent Protected Teaching",
        "LLM Tutoring Agent",
        _message_summary(teaching_request),
        {
            "teaching_strategy_used": teaching_output.get("teaching_strategy_used"),
            "teaching_answer_summary": _text_summary(teaching_output.get("teaching_answer")),
        },
        _tpcs_message_label(teaching_request, teaching_response),
        _guardrail_label(teaching_request, teaching_response),
        _risk_score(teaching_response, 0.22),
    )

    nemo_logs["output_rail"] = _run_nemo_rail(
        tpcs,
        stage="output_rail",
        payload={"teaching_answer": teaching_output["teaching_answer"]},
        context={"round_id": round_id, "profile_card_id": context_card["context_card_id"]},
    )
    _append_workflow_step(
        workflow_steps,
        "NeMo Output Rail",
        "TPCS Guardrail Adapter",
        {"teaching_answer_summary": _text_summary(teaching_output["teaching_answer"])},
        _summary_dict(nemo_logs["output_rail"]),
        "allow" if nemo_logs["output_rail"]["decision"] != "block" else "refuse",
        nemo_logs["output_rail"]["decision"],
        nemo_logs["output_rail"]["risk_score"],
    )

    assessment_request, assessment_output, assessment_response = tpcs.dispatch(
        sender=teaching_agent.agent_id,
        receiver=assessment_agent,
        message_type="learning_assessment_request",
        payload={
            "teaching_answer": teaching_output["teaching_answer"],
            "student_response": demo_case.simulated_student_response,
            "knowledge_point": diagnosis_result["knowledge_point"],
        },
        privacy_level="answer_and_response_only",
        round_id=round_id,
    )
    _append_workflow_step(
        workflow_steps,
        "LearningAssessmentAgent Mastery Check",
        "LLM Tutoring Agent",
        _message_summary(assessment_request),
        {
            "assessment_result": assessment_output.get("assessment_result"),
            "mastery_score": assessment_output.get("mastery_score"),
            "confidence_score": assessment_output.get("confidence_score"),
            "follow_up_question": assessment_output.get("follow_up_question"),
        },
        _tpcs_message_label(assessment_request, assessment_response),
        _guardrail_label(assessment_request, assessment_response),
        _risk_score(assessment_response, 0.2),
    )

    profile_update_decision = tpcs.approve_profile_update_evidence(
        assessment_output["profile_update_evidence"],
        round_id=round_id,
    )
    profile_update_logs = {
        "assessment_evidence": assessment_output["profile_update_evidence"],
        "tpcs_decision": profile_update_decision,
        "direct_profile_update_performed": False,
    }
    _append_workflow_step(
        workflow_steps,
        "TPCS Evidence-Gated Profile Update Approval",
        "TPCS",
        {
            "evidence_type": assessment_output["profile_update_evidence"].get(
                "evidence_type"
            ),
            "direct_profile_update_requested": assessment_output[
                "profile_update_evidence"
            ].get("direct_profile_update_requested"),
        },
        _summary_dict(profile_update_decision),
        _profile_update_tpcs_label(profile_update_decision),
        "not_enabled",
        _risk_score(profile_update_decision, 0.15),
    )

    agent_call_logs = (
        profile_agent.call_log
        + resource_agent.call_log
        + teaching_agent.call_log
        + assessment_agent.call_log
    )
    hsw_st_binding = DemoHSWSTBinder().bind(
        teaching_answer=teaching_output["teaching_answer"],
        answer_id=answer_id,
        profile_card_id=context_card["context_card_id"],
        controlled_resource_snippets=controlled_snippets,
        agent_call_logs=agent_call_logs,
        communication_logs=tpcs.message_log,
        profile_update_logs=profile_update_logs,
    )
    hsw_st_log = _hsw_st_protection_log(hsw_st_binding["audit_trace"])
    _append_workflow_step(
        workflow_steps,
        "HSW-ST Final Answer Binding",
        "HSW-ST",
        {
            "answer_id": answer_id,
            "profile_card_id": context_card.get("context_card_id"),
            "resource_ids": hsw_st_log["resource_ids"],
        },
        _summary_dict(hsw_st_log),
        "allow",
        "not_enabled",
        0.12,
    )

    demo_result = {
        "architecture": FRAMEWORK_ARCHITECTURE,
        "round_id": round_id,
        "runtime_status": runtime_status,
        "workflow_steps": workflow_steps,
        "raw_data_summary": demo_case.raw_data_summary,
        "generated_context_card": context_card,
        "tpcs_risk_decision": tpcs_risk_decision,
        "agent_outputs": {
            "ProfileDiagnosisAgent": diagnosis_output,
            "CopyrightAwareResourceAgent": resource_output,
            "PedagogicalTeachingAgent": teaching_output,
            "LearningAssessmentAgent": {
                "assessment_result": assessment_output["assessment_result"],
                "follow_up_question": assessment_output["follow_up_question"],
                "profile_update_evidence": assessment_output[
                    "profile_update_evidence"
                ],
                "mastery_score": assessment_output["mastery_score"],
                "confidence_score": assessment_output["confidence_score"],
            },
        },
        "profile_update_decision": profile_update_decision,
        "communication_logs": tpcs.message_log,
        "protection_logs": {
            "mm_fopd": _mm_fopd_protection_log(demo_case, context_card),
            "c2_rag": c2rag_log,
            "hsw_st": hsw_st_log,
            "tpcs": _tpcs_protection_log(
                tpcs=tpcs,
                tpcs_risk_decision=tpcs_risk_decision,
                profile_update_decision=profile_update_decision,
            ),
            "nemo_guardrails": {
                "enabled": bool(runtime_status["nemo_guardrails_enabled"]),
                "adapter": (
                    tpcs.guardrail_adapter.provider_name
                    if tpcs.guardrail_adapter is not None
                    else None
                ),
                "rails": nemo_logs,
            },
        },
        "final_protected_teaching_answer": hsw_st_binding["final_protected_answer"],
        "audit_trace": hsw_st_binding["audit_trace"],
    }
    if event_sink is not None:
        event_sink(
            {
                "type": "run_completed",
                "round_id": round_id,
                "result": demo_result,
                "timestamp": utc_now_iso(),
            }
        )
    return demo_result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run CogniGuard protected tutoring demo pipeline."
    )
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--case-index", type=int, default=0)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full demo result as JSON instead of sectioned output.",
    )
    args = parser.parse_args()

    result = run_demo(data_root=args.data_root, case_index=args.case_index)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    _print_sectioned_demo(result)


def _tpcs_context_card_decision(
    tpcs: TPCSController, context_card: dict[str, Any], round_id: str
) -> dict[str, Any]:
    expected_privacy_level = "MM-FOPD-minimum-context"
    card_privacy_ok = context_card.get("privacy_level") == expected_privacy_level
    card_score = float(context_card.get("disclosure_score", 1.0))
    card_score_ok = card_score <= tpcs.max_disclosure_score
    if not card_privacy_ok:
        raise AgentValidationError(
            f"TPCS rejected privacy_level={context_card.get('privacy_level')}"
        )
    if not card_score_ok:
        raise AgentValidationError(f"TPCS rejected disclosure_score={card_score}")
    base_decision = tpcs.pre_check_context_card(context_card, round_id)
    return {
        **base_decision,
        "card_privacy_level": context_card["privacy_level"],
        "card_disclosure_score": card_score,
        "card_privacy_level_approved": card_privacy_ok,
        "card_disclosure_score_approved": card_score_ok,
        "decision": "approved_minimum_context_card",
    }


def _append_workflow_step(
    steps: list[dict[str, Any]],
    step_name: str,
    layer: str,
    input_summary: dict[str, Any],
    output_summary: dict[str, Any],
    tpcs_decision: str,
    nemo_decision: str,
    risk_score: float,
) -> None:
    steps.append(
        {
            "step_id": len(steps) + 1,
            "step_name": step_name,
            "layer": layer,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "tpcs_decision": tpcs_decision,
            "nemo_decision": nemo_decision,
            "risk_score": round(max(0.0, min(1.0, float(risk_score))), 4),
            "timestamp": utc_now_iso(),
        }
    )


def _run_nemo_rail(
    tpcs: TPCSController,
    stage: str,
    payload: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    adapter = tpcs.guardrail_adapter
    if adapter is None:
        return {
            "stage": stage,
            "enabled": False,
            "decision": "not_enabled",
            "risk_score": 0.0,
            "timestamp": utc_now_iso(),
        }

    context = context or {}
    if stage == "input_rail" and hasattr(adapter, "check_user_input"):
        result = adapter.check_user_input(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            context,
        )
    elif stage == "retrieval_rail" and hasattr(adapter, "check_retrieved_chunks"):
        result = adapter.check_retrieved_chunks(
            payload.get("controlled_resource_snippets", []),
            context,
        )
    elif stage == "output_rail" and hasattr(adapter, "check_output"):
        result = adapter.check_output(str(payload.get("teaching_answer", "")), context)
    else:
        result = adapter.check_message(
            {
                "sender": "TPCSController",
                "receiver": "NeMoGuardrailsAdapter",
                "message_type": stage,
                "payload": payload,
                "timestamp": utc_now_iso(),
            }
        )
    decision = str(result.get("decision", "allow"))
    blocked = decision == "block"
    normalized = {
        "stage": stage,
        **result,
        "risk_score": 0.72 if blocked else (0.22 if decision == "sanitize" else 0.08),
        "timestamp": utc_now_iso(),
    }
    if "sanitized_chunks" in result:
        normalized["sanitized_chunks"] = result["sanitized_chunks"]
    return {
        **normalized,
        "decision": "block" if blocked else decision,
    }


def _mm_fopd_protection_log(
    demo_case: Any, context_card: dict[str, Any]
) -> dict[str, Any]:
    return {
        "student_hash": demo_case.student_hash,
        "task_id": demo_case.task_id,
        "context_card_id": context_card.get("context_card_id"),
        "privacy_level": context_card.get("privacy_level"),
        "disclosure_score": context_card.get("disclosure_score"),
        "allowed_profile_fields": context_card.get("allowed_profile_fields", []),
        "forbidden_profile_fields": context_card.get("forbidden_profile_fields", []),
        "raw_payload_sent_to_agents": False,
        "retention_policy": context_card.get("retention_policy"),
    }


def _c2rag_protection_log(
    resource_agent: CopyrightAwareResourceAgent,
    resource_payload: dict[str, Any],
    snippets: list[dict[str, Any]],
) -> dict[str, Any]:
    exposure_budget_before = float(resource_agent.max_total_exposure)
    exposure_cost = round(
        sum(float(snippet.get("exposure_cost", 0.0)) for snippet in snippets), 4
    )
    exposure_budget_after = round(max(0.0, exposure_budget_before - exposure_cost), 4)
    return_modes = [str(snippet.get("return_mode", "summary")) for snippet in snippets]
    degraded = any(mode == "variant" for mode in return_modes)
    return {
        "query": resource_payload.get("teaching_request", {}),
        "knowledge_point": resource_payload.get("knowledge_point"),
        "allowed_return_modes": resource_payload.get("allowed_return_modes", []),
        "exposure_budget_before": exposure_budget_before,
        "exposure_cost": exposure_cost,
        "exposure_budget_after": exposure_budget_after,
        "return_mode_control": return_modes,
        "controlled_snippet_count": len(snippets),
        "resource_ids": [snippet.get("resource_id") for snippet in snippets],
        "chunk_ids": [snippet.get("chunk_id") for snippet in snippets],
        "copyright_levels": [
            float(snippet.get("copyright_level", 0.0)) for snippet in snippets
        ],
        "full_original_resource_returned": False,
        "prompt_injection_detected": any(
            "[removed unsafe instruction]" in str(snippet.get("content", ""))
            for snippet in snippets
        ),
        "tpcs_decision": "degrade" if degraded else "allow",
        "risk_score": round(min(1.0, exposure_cost), 4),
    }


def _hsw_st_protection_log(audit_trace: dict[str, Any]) -> dict[str, Any]:
    resource_bindings = audit_trace.get("resource_bindings", [])
    return {
        "answer_id": audit_trace.get("answer_id"),
        "watermark_id": audit_trace.get("watermark_id"),
        "profile_card_id": audit_trace.get("profile_card_id"),
        "resource_ids": [
            binding.get("resource_id") for binding in resource_bindings if binding
        ],
        "chunk_ids": [
            binding.get("chunk_id") for binding in resource_bindings if binding
        ],
        "audit_status": audit_trace.get("audit_status"),
        "watermarked_answer_sha256": audit_trace.get("watermarked_answer_sha256"),
        "audit_complete": bool(
            audit_trace.get("watermark_id")
            and audit_trace.get("profile_card_id")
            and audit_trace.get("watermarked_answer_sha256")
        ),
    }


def _tpcs_protection_log(
    tpcs: TPCSController,
    tpcs_risk_decision: dict[str, Any],
    profile_update_decision: dict[str, Any],
) -> dict[str, Any]:
    return {
        "pre_check": tpcs_risk_decision,
        "profile_update_approval": profile_update_decision,
        "max_disclosure_score": tpcs.max_disclosure_score,
        "cumulative_privacy_budget": tpcs.cumulative_privacy_budget,
        "cumulative_disclosure_by_round": tpcs.cumulative_disclosure_by_round,
        "communication_log_count": len(tpcs.message_log),
        "all_inter_agent_communication_via_tpcs": True,
    }


def _message_summary(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "sender": message.get("sender"),
        "receiver": message.get("receiver"),
        "message_type": message.get("message_type"),
        "privacy_level": message.get("privacy_level"),
        "disclosure_score": message.get("disclosure_score"),
        "round_id": message.get("round_id"),
    }


def _tpcs_decision_label(decision: dict[str, Any]) -> str:
    if not decision.get("approved", True):
        return "refuse"
    raw = str(decision.get("decision", "")).lower()
    if "sanitize" in raw:
        return "sanitize"
    if "degrade" in raw:
        return "degrade"
    return "allow"


def _tpcs_message_label(*messages: dict[str, Any]) -> str:
    text = " ".join(str(message.get("guardrail_decision", "")) for message in messages)
    if "blocked" in text:
        return "refuse"
    return "allow"


def _guardrail_label(*messages: dict[str, Any]) -> str:
    decisions = [
        message.get("guardrail_decision")
        for message in messages
        if message.get("guardrail_decision")
    ]
    if not decisions:
        return "not_enabled"
    if any(not decision.get("allowed", True) for decision in decisions):
        return "block"
    return "allow"


def _profile_update_tpcs_label(decision: dict[str, Any]) -> str:
    if decision.get("direct_profile_update_performed"):
        return "refuse"
    if decision.get("approved_for_profile_update_review"):
        return "allow"
    return "degrade"


def _risk_score(value: Any, default: float) -> float:
    if isinstance(value, dict):
        for key in (
            "risk_score",
            "disclosure_score",
            "card_disclosure_score",
            "exposure_cost",
        ):
            if key in value:
                try:
                    return max(0.0, min(1.0, float(value[key])))
                except (TypeError, ValueError):
                    pass
    return default


def _summary_dict(value: Any, max_chars: int = 240) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            str(key): _summary_value(nested, max_chars=max_chars)
            for key, nested in value.items()
        }
    return {"summary": _text_summary(value, max_chars=max_chars)}


def _summary_value(value: Any, max_chars: int = 240) -> Any:
    if isinstance(value, dict):
        return _summary_dict(value, max_chars=max_chars)
    if isinstance(value, list):
        return [_summary_value(item, max_chars=max_chars) for item in value[:5]]
    if isinstance(value, str):
        return _text_summary(value, max_chars=max_chars)
    return value


def _text_summary(value: Any, max_chars: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3]}..."


def _print_sectioned_demo(result: dict[str, Any]) -> None:
    sections = (
        ("Architecture", result["architecture"]),
        ("Round ID", result["round_id"]),
        ("Workflow Steps", result["workflow_steps"]),
        ("Raw Data Summary", result["raw_data_summary"]),
        ("Generated Context Card", result["generated_context_card"]),
        ("TPCS Risk Decision", result["tpcs_risk_decision"]),
        ("Agent Outputs", result["agent_outputs"]),
        ("Final Protected Teaching Answer", result["final_protected_teaching_answer"]),
        ("Audit Trace", result["audit_trace"]),
    )
    for title, payload in sections:
        print(f"\n=== {title} ===")
        if isinstance(payload, str):
            print(payload)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))


def _slug(value: str) -> str:
    return "_".join(str(value).lower().split())


def _short_hash(value: str, length: int = 8) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


if __name__ == "__main__":
    main()
