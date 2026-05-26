from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agents.agent_orchestrator import TPCSController
from backend.app.agents.base_agent import AgentValidationError, utc_now_iso
from backend.app.agents.copyright_aware_resource_agent import (
    CopyrightAwareResourceAgent,
)
from backend.app.agents.learning_assessment_agent import LearningAssessmentAgent
from backend.app.agents.minimax_client import build_default_llm_client
from backend.app.agents.pedagogical_teaching_agent import PedagogicalTeachingAgent
from backend.app.agents.profile_diagnosis_agent import ProfileDiagnosisAgent
from backend.app.demo.demo_cases import load_demo_case


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


def run_demo(data_root: str | Path = "data", case_index: int = 0) -> dict[str, Any]:
    demo_case = load_demo_case(data_root=data_root, case_index=case_index)
    round_id = f"demo_{demo_case.task_id}"
    answer_id = f"ans_{demo_case.task_id}"
    llm_client = build_default_llm_client()
    tpcs = TPCSController(max_disclosure_score=0.75)

    profile_agent = ProfileDiagnosisAgent(llm_client=llm_client)
    resource_agent = CopyrightAwareResourceAgent(
        c2rag_service=DemoC2RAGService(),
        llm_client=llm_client,
    )
    teaching_agent = PedagogicalTeachingAgent(llm_client=llm_client)
    assessment_agent = LearningAssessmentAgent(llm_client=llm_client)

    context_card = dict(demo_case.context_card)
    tpcs_risk_decision = _tpcs_context_card_decision(tpcs, context_card, round_id)

    _, diagnosis_output, _ = tpcs.dispatch(
        sender="MM-FOPD",
        receiver=profile_agent,
        message_type="diagnosis_request",
        payload={"context_card": context_card},
        privacy_level="minimum_context",
        round_id=round_id,
    )
    diagnosis_result = diagnosis_output["diagnosis_result"]

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
    _, resource_output, _ = tpcs.dispatch(
        sender=profile_agent.agent_id,
        receiver=resource_agent,
        message_type="controlled_resource_request",
        payload=resource_payload,
        privacy_level="teaching_need_only",
        round_id=round_id,
    )
    controlled_snippets = resource_output["controlled_resource_snippets"]

    _, teaching_output, _ = tpcs.dispatch(
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

    _, assessment_output, _ = tpcs.dispatch(
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

    profile_update_decision = tpcs.approve_profile_update_evidence(
        assessment_output["profile_update_evidence"],
        round_id=round_id,
    )
    profile_update_logs = {
        "assessment_evidence": assessment_output["profile_update_evidence"],
        "tpcs_decision": profile_update_decision,
        "direct_profile_update_performed": False,
    }

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

    demo_result = {
        "architecture": FRAMEWORK_ARCHITECTURE,
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
        "final_protected_teaching_answer": hsw_st_binding["final_protected_answer"],
        "audit_trace": hsw_st_binding["audit_trace"],
    }
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


def _print_sectioned_demo(result: dict[str, Any]) -> None:
    sections = (
        ("Architecture", result["architecture"]),
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
