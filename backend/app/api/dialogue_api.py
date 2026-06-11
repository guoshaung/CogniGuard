"""
Multi-round dialogue API for CogniGuard
支持多轮师生对话和攻击注入测试
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.agents.agent_orchestrator import TPCSController
from backend.app.agents.copyright_aware_resource_agent import (
    CopyrightAwareResourceAgent,
)
from backend.app.agents.pedagogical_teaching_agent import PedagogicalTeachingAgent
from backend.app.agents.profile_diagnosis_agent import ProfileDiagnosisAgent
from backend.app.demo.demo_cases import load_demo_case
from backend.app.demo.run_demo import (
    DemoC2RAGService,
    DemoHSWSTBinder,
)
from backend.app.runtime.mode import build_guardrail_adapter, build_runtime_llm_client

router = APIRouter()


class ConversationMessage(BaseModel):
    role: str
    content: str


class NextRoundRequest(BaseModel):
    case_index: int
    round_count: int
    message: str
    is_attack: bool = False
    attack_type: str | None = None
    conversation_history: list[ConversationMessage] = []


class NextRoundResponse(BaseModel):
    success: bool
    teaching_answer: str
    protection_logs: dict[str, Any]
    disclosure_score: float
    attack_blocked: bool
    watermark_id: str
    audit_trace: dict[str, Any]
    workflow_steps: list[dict[str, Any]]
    response_metadata: dict[str, Any]


# In-memory dialogue state storage (简化演示用)
# 生产环境应使用数据库或Redis
dialogue_sessions: dict[str, dict[str, Any]] = {}


@router.post("/next-round", response_model=NextRoundResponse)
async def dialogue_next_round(request: NextRoundRequest) -> NextRoundResponse:
    """
    处理多轮对话的下一轮
    支持学生正常提问和攻击者注入
    """
    session_id = f"case_{request.case_index}_round_{request.round_count}"
    
    try:
        # Load case data
        demo_case = load_demo_case(case_index=request.case_index)
        
        # Initialize or retrieve session state
        if session_id not in dialogue_sessions:
            dialogue_sessions[session_id] = {
                "case_data": demo_case,
                "context_card": dict(demo_case.context_card),
                "round_count": 0,
                "cumulative_disclosure": 0.0,
                "conversation_history": []
            }
        
        session = dialogue_sessions[session_id]
        session["conversation_history"].append({
            "role": "attacker" if request.is_attack else "student",
            "content": request.message,
            "is_attack": request.is_attack,
            "attack_type": request.attack_type
        })
        
        # Initialize components
        llm_client = build_runtime_llm_client()
        tpcs = TPCSController(
            max_disclosure_score=0.75,
            guardrail_adapter=build_guardrail_adapter(),
        )
        
        profile_agent = ProfileDiagnosisAgent(llm_client=llm_client)
        resource_agent = CopyrightAwareResourceAgent(
            c2rag_service=DemoC2RAGService(),
            llm_client=llm_client,
        )
        teaching_agent = PedagogicalTeachingAgent(llm_client=llm_client)
        
        round_id = f"dialogue_{session_id}_{uuid.uuid4().hex[:8]}"
        answer_id = f"ans_{round_id}"
        workflow_steps: list[dict[str, Any]] = []
        
        # Detect attack
        attack_blocked = False
        attack_detection_log = {}
        
        if request.is_attack:
            # Check if attack should be blocked
            attack_detection_log = _detect_attack(request.message, request.attack_type)
            attack_blocked = attack_detection_log.get("blocked", False)
            
            workflow_steps.append({
                "step_id": len(workflow_steps) + 1,
                "step_name": "Attack Detection",
                "layer": "TPCS Guardrail",
                "input_summary": {
                    "message": request.message[:100],
                    "attack_type": request.attack_type
                },
                "output_summary": attack_detection_log,
                "tpcs_decision": "refuse" if attack_blocked else "allow",
                "risk_score": attack_detection_log.get("risk_score", 0.8)
            })
            
            if attack_blocked:
                # Return blocked response
                blocked_answer = _generate_blocked_response(request.attack_type)
                
                session["conversation_history"].append({
                    "role": "teacher",
                    "content": blocked_answer,
                    "attack_blocked": True
                })
                
                return NextRoundResponse(
                    success=True,
                    teaching_answer=blocked_answer,
                    protection_logs={
                        "attack_detection": attack_detection_log,
                        "blocked": True
                    },
                    disclosure_score=0.0,
                    attack_blocked=True,
                    watermark_id=f"blocked_{answer_id}",
                    audit_trace={
                        "answer_id": answer_id,
                        "attack_blocked": True,
                        "attack_type": request.attack_type
                    },
                    workflow_steps=workflow_steps,
                    response_metadata={
                        "session_id": session_id,
                        "round_count": request.round_count
                    }
                )
        
        # Normal dialogue flow
        context_card = session["context_card"]
        
        # Step 1: Profile diagnosis with conversation context
        diagnosis_request, diagnosis_output, diagnosis_response = tpcs.dispatch(
            sender="Student",
            receiver=profile_agent,
            message_type="dialogue_diagnosis_request",
            payload={
                "context_card": context_card,
                "current_message": request.message,
                "conversation_history": request.conversation_history
            },
            privacy_level="minimum_context",
            round_id=round_id,
        )
        
        diagnosis_result = diagnosis_output["diagnosis_result"]
        workflow_steps.append({
            "step_id": len(workflow_steps) + 1,
            "step_name": "Dialogue Context Diagnosis",
            "layer": "Profile Agent",
            "input_summary": {"message": request.message[:100]},
            "output_summary": {
                "learner_state": diagnosis_result.get("learner_state"),
                "suggested_strategy": diagnosis_result.get("suggested_teaching_strategy")
            },
            "tpcs_decision": "allow",
            "risk_score": 0.18
        })
        
        # Step 2: Resource retrieval
        resource_payload = {
            "teaching_request": {
                "task_id": context_card["task_id"],
                "knowledge_point": diagnosis_result["knowledge_point"],
                "current_error_type": diagnosis_result["error_type"],
                "learner_state": diagnosis_result["learner_state"],
                "student_message": request.message
            },
            "knowledge_point": diagnosis_result["knowledge_point"],
            "allowed_return_modes": ["summary", "outline", "snippet"]
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
        workflow_steps.append({
            "step_id": len(workflow_steps) + 1,
            "step_name": "C2-RAG Resource Control",
            "layer": "Copyright Layer",
            "input_summary": {"knowledge_point": diagnosis_result["knowledge_point"]},
            "output_summary": {"snippet_count": len(controlled_snippets)},
            "tpcs_decision": "allow",
            "risk_score": 0.2
        })
        
        # Step 3: Teaching generation
        teaching_request, teaching_output, teaching_response = tpcs.dispatch(
            sender=resource_agent.agent_id,
            receiver=teaching_agent,
            message_type="dialogue_teaching_request",
            payload={
                "context_card": context_card,
                "diagnosis_result": diagnosis_result,
                "controlled_resource_snippets": controlled_snippets,
                "student_message": request.message,
                "conversation_history": request.conversation_history
            },
            privacy_level="minimum_context_plus_controlled_resource",
            round_id=round_id,
        )
        
        teaching_answer = teaching_output["teaching_answer"]
        workflow_steps.append({
            "step_id": len(workflow_steps) + 1,
            "step_name": "Dialogue Teaching Generation",
            "layer": "Teaching Agent",
            "input_summary": {"message": request.message[:100]},
            "output_summary": {"answer_length": len(teaching_answer)},
            "tpcs_decision": "allow",
            "risk_score": 0.22
        })
        
        # Step 4: Watermark binding
        agent_call_logs = (
            profile_agent.call_log
            + resource_agent.call_log
            + teaching_agent.call_log
        )
        
        hsw_st_binding = DemoHSWSTBinder().bind(
            teaching_answer=teaching_answer,
            answer_id=answer_id,
            profile_card_id=context_card["context_card_id"],
            controlled_resource_snippets=controlled_snippets,
            agent_call_logs=agent_call_logs,
            communication_logs=tpcs.message_log,
            profile_update_logs={}
        )
        
        workflow_steps.append({
            "step_id": len(workflow_steps) + 1,
            "step_name": "HSW-ST Watermark Binding",
            "layer": "Audit Layer",
            "input_summary": {"answer_id": answer_id},
            "output_summary": {
                "watermark_id": hsw_st_binding["audit_trace"]["watermark_id"]
            },
            "tpcs_decision": "allow",
            "risk_score": 0.12
        })
        
        # Update session
        disclosure_score = context_card.get("disclosure_score", 0.25)
        session["cumulative_disclosure"] += disclosure_score
        session["round_count"] += 1
        session["conversation_history"].append({
            "role": "teacher",
            "content": hsw_st_binding["final_protected_answer"],
            "watermark_id": hsw_st_binding["audit_trace"]["watermark_id"]
        })
        
        return NextRoundResponse(
            success=True,
            teaching_answer=hsw_st_binding["final_protected_answer"],
            protection_logs={
                "mm_fopd": {"disclosure_score": disclosure_score},
                "c2_rag": {"snippet_count": len(controlled_snippets)},
                "hsw_st": {
                    "watermark_id": hsw_st_binding["audit_trace"]["watermark_id"]
                },
                "attack_detection": attack_detection_log
            },
            disclosure_score=disclosure_score,
            attack_blocked=False,
            watermark_id=hsw_st_binding["audit_trace"]["watermark_id"],
            audit_trace=hsw_st_binding["audit_trace"],
            workflow_steps=workflow_steps,
            response_metadata={
                "session_id": session_id,
                "round_count": request.round_count,
                "cumulative_disclosure": session["cumulative_disclosure"]
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dialogue processing failed: {str(e)}")


def _detect_attack(message: str, attack_type: str | None) -> dict[str, Any]:
    """检测攻击并决定是否拦截"""
    message_lower = message.lower()
    
    # Detection patterns
    injection_keywords = [
        "ignore previous",
        "ignore all previous",
        "disregard",
        "new instructions",
        "you are now",
        "system prompt"
    ]
    
    privacy_keywords = [
        "real name",
        "student id",
        "full history",
        "raw data",
        "personal information"
    ]
    
    copyright_keywords = [
        "complete original",
        "verbatim",
        "full text",
        "entire document",
        "all solutions"
    ]
    
    jailbreak_keywords = [
        "dan mode",
        "do anything now",
        "without restrictions",
        "bypass",
        "jailbreak"
    ]
    
    detected_patterns = []
    risk_score = 0.0
    
    for keyword in injection_keywords:
        if keyword in message_lower:
            detected_patterns.append(f"prompt_injection:{keyword}")
            risk_score = max(risk_score, 0.9)
    
    for keyword in privacy_keywords:
        if keyword in message_lower:
            detected_patterns.append(f"privacy_extraction:{keyword}")
            risk_score = max(risk_score, 0.85)
    
    for keyword in copyright_keywords:
        if keyword in message_lower:
            detected_patterns.append(f"copyright_theft:{keyword}")
            risk_score = max(risk_score, 0.8)
    
    for keyword in jailbreak_keywords:
        if keyword in message_lower:
            detected_patterns.append(f"jailbreak:{keyword}")
            risk_score = max(risk_score, 0.95)
    
    # Block if high risk
    blocked = risk_score >= 0.75
    
    return {
        "attack_type": attack_type,
        "detected_patterns": detected_patterns,
        "risk_score": risk_score,
        "blocked": blocked,
        "detection_method": "keyword_pattern_matching"
    }


def _generate_blocked_response(attack_type: str | None) -> str:
    """生成拦截响应"""
    responses = {
        "prompt_injection": (
            "⚠️ 检测到可疑的提示词注入尝试。\n\n"
            "CogniGuard 系统已拦截该请求。我无法执行违反隐私保护和安全策略的指令。"
            "请继续正常的学习对话。"
        ),
        "privacy_extraction": (
            "⚠️ 检测到隐私信息榨取尝试。\n\n"
            "根据 MM-FOPD 隐私保护机制，学生的原始个人信息和完整学习历史"
            "是受保护的隐私数据，不会被披露。我只能基于匿名化的学习画像提供教学支持。"
        ),
        "copyright_theft": (
            "⚠️ 检测到教学资源版权盗取尝试。\n\n"
            "根据 C²-RAG 版权控制机制，完整的原始教学材料和题库解答是受版权保护的资产，"
            "不能原文输出。我只能提供摘要、概要或变体形式的教学内容。"
        ),
        "jailbreak": (
            "⚠️ 检测到越狱攻击尝试。\n\n"
            "CogniGuard 系统的安全策略不可被绕过。我将继续按照既定的隐私保护、"
            "版权控制和审计追踪机制运行。请继续正常的学习对话。"
        )
    }
    
    return responses.get(
        attack_type,
        "⚠️ 检测到可疑请求，已被安全防护系统拦截。请继续正常的学习对话。"
    )


@router.post("/reset-session")
async def reset_dialogue_session(case_index: int):
    """重置对话会话"""
    session_keys = [k for k in dialogue_sessions.keys() if k.startswith(f"case_{case_index}_")]
    for key in session_keys:
        del dialogue_sessions[key]
    
    return {"success": True, "message": f"Session reset for case {case_index}"}
