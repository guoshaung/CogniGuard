"""Compiled LangGraph for the dashboard's protected multi-agent turn.

The graph state contains stage markers only. Student content and agent payloads
stay in the invocation context and are never checkpointed or traced natively.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from cogniguard.observability.graphs import invoke_observed_graph, observed_node
from cogniguard.observability.telemetry import SafeTelemetry
from cogniguard.protection.retrieval import retrieval_context

if TYPE_CHECKING:
    from cogniguard.agents.protected_orchestrator import AgentOrchestrator


class ProtectedTurnState(TypedDict, total=False):
    stage: str
    completed: bool
    blocked: bool


@dataclass
class ProtectedTurnFrame:
    owner: AgentOrchestrator
    student_data: dict[str, Any]
    student_response: str
    round_id: str
    context_card: dict[str, Any] = field(default_factory=dict)
    profile_encoding: dict[str, Any] = field(default_factory=dict)
    cg_pre_check: dict[str, Any] = field(default_factory=dict)
    diagnosis_result: dict[str, Any] = field(default_factory=dict)
    resource_output: dict[str, Any] = field(default_factory=dict)
    teaching_output: dict[str, Any] = field(default_factory=dict)
    assessment_output: dict[str, Any] = field(default_factory=dict)
    profile_update_approval: dict[str, Any] = field(default_factory=dict)
    final_answer_audit: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    recorder: SafeTelemetry = field(default_factory=SafeTelemetry)


@dataclass
class ProtectedTurnContext:
    frame: ProtectedTurnFrame


def _prepare(state: ProtectedTurnState, runtime: Runtime[ProtectedTurnContext]):
    f = runtime.context.frame
    owner = f.owner
    # Local import avoids a circular dependency with the service container.
    from cogniguard.agents.protected_orchestrator import sanitize_context_card

    f.context_card = sanitize_context_card(owner._build_mm_fopd_context_card(f.student_data))
    f.profile_encoding = owner._build_enhanced_profile_encoding(f.student_data, f.context_card)
    f.cg_pre_check = owner.cg.pre_check_context_card(f.context_card, f.round_id)
    return {"stage": "prepare"}


def _diagnose(state: ProtectedTurnState, runtime: Runtime[ProtectedTurnContext]):
    f = runtime.context.frame
    _, output, _ = f.owner.cg.dispatch(
        sender="MM-FOPD",
        receiver=f.owner.profile_diagnosis_agent,
        message_type="diagnosis_request",
        payload={"profile_encoding": f.profile_encoding, "context_card": f.context_card},
        privacy_level="minimum_context",
        round_id=f.round_id,
    )
    f.diagnosis_result = output["diagnosis_result"]
    return {"stage": "diagnose"}


def _retrieve(state: ProtectedTurnState, runtime: Runtime[ProtectedTurnContext]):
    f = runtime.context.frame
    from cogniguard.agents.protected_orchestrator import _teaching_request_from_context

    diagnosis = f.diagnosis_result
    _, f.resource_output, _ = f.owner.cg.dispatch(
        sender=f.owner.profile_diagnosis_agent.agent_id,
        receiver=f.owner.resource_agent,
        message_type="controlled_resource_request",
        payload={
            "teaching_request": _teaching_request_from_context(f.context_card, diagnosis),
            "knowledge_point": diagnosis["knowledge_point"],
            "allowed_return_modes": ["summary", "outline", "snippet", "variant"],
        },
        privacy_level="teaching_need_only",
        round_id=f.round_id,
    )
    # Retrieval checks run inside the domain Agent before release and binding.
    # A later transport/domain transform must not silently rewrite that release
    # while retaining its old source hashes and approved output context.
    checked = getattr(f.owner.resource_agent, "last_retrieval_context", None)
    if checked is not None:
        forwarded = retrieval_context([], f.resource_output.get("controlled_resource_snippets", []))
        if forwarded["approved_chunks"] != checked["approved_chunks"]:
            raise ValueError("Controlled resource changed after C2-RAG release")
    return {"stage": "retrieve"}


def _teach(state: ProtectedTurnState, runtime: Runtime[ProtectedTurnContext]):
    f = runtime.context.frame
    _, f.teaching_output, _ = f.owner.cg.dispatch(
        sender=f.owner.resource_agent.agent_id,
        receiver=f.owner.teaching_agent,
        message_type="teaching_generation_request",
        payload={
            "context_card": f.context_card,
            "diagnosis_result": f.diagnosis_result,
            "controlled_resource_snippets": f.resource_output["controlled_resource_snippets"],
            "profile_encoding": f.profile_encoding,
        },
        privacy_level="minimum_context_plus_controlled_resource",
        round_id=f.round_id,
    )
    return {"stage": "teach"}


def _assess(state: ProtectedTurnState, runtime: Runtime[ProtectedTurnContext]):
    f = runtime.context.frame
    _, f.assessment_output, _ = f.owner.cg.dispatch(
        sender=f.owner.teaching_agent.agent_id,
        receiver=f.owner.assessment_agent,
        message_type="learning_assessment_request",
        payload={
            "teaching_answer": f.teaching_output["teaching_answer"],
            "student_response": f.student_response,
            "knowledge_point": f.diagnosis_result["knowledge_point"],
            "profile_encoding": f.profile_encoding,
        },
        privacy_level="answer_and_response_only",
        round_id=f.round_id,
    )
    return {"stage": "assess"}


def _audit(state: ProtectedTurnState, runtime: Runtime[ProtectedTurnContext]):
    f = runtime.context.frame
    f.profile_update_approval = f.owner.cg.approve_profile_update_evidence(
        f.assessment_output["profile_update_evidence"],
        round_id=f.round_id,
    )
    f.final_answer_audit = f.owner.cg.final_answer_audit(
        f.teaching_output["teaching_answer"],
        f.assessment_output,
        round_id=f.round_id,
    )
    return {"stage": "audit"}


def _finish(state: ProtectedTurnState, runtime: Runtime[ProtectedTurnContext]):
    f = runtime.context.frame
    cg = f.owner.cg
    f.result = {
        "round_id": f.round_id,
        "context_card": f.context_card,
        "profile_encoding": f.profile_encoding,
        "cg_pre_check": f.cg_pre_check,
        "diagnosis_result": f.diagnosis_result,
        "controlled_resource_snippets": f.resource_output["controlled_resource_snippets"],
        "teaching_answer": f.teaching_output["teaching_answer"],
        "teaching_strategy_used": f.teaching_output["teaching_strategy_used"],
        "assessment_result": f.assessment_output,
        "profile_update_approval": f.profile_update_approval,
        "final_answer_audit": f.final_answer_audit,
        "agent_messages": list(cg.message_log),
        "cg_audit_chain": list(cg.audit_events),
        "cg_audit_verified": cg.verify_audit_chain(),
        "cg_budget_state": {
            "round": cg.budget_manager.used_by_round.get(f.round_id, 0.0),
            "session": cg.budget_manager.used_by_session.get(cg.session_id, 0.0),
            "student": cg.budget_manager.used_by_student.get(cg.student_id, 0.0),
            "limits": {
                "round": cg.budget_manager.round_limit,
                "session": cg.budget_manager.session_limit,
                "student": cg.budget_manager.student_limit,
            },
        },
    }
    return {"stage": "finish", "completed": True, "blocked": False}


def build_protected_turn_graph():
    builder = StateGraph(ProtectedTurnState, context_schema=ProtectedTurnContext)
    nodes = (
        ("prepare", _prepare),
        ("diagnose", _diagnose),
        ("retrieve", _retrieve),
        ("teach", _teach),
        ("assess", _assess),
        ("audit", _audit),
        ("finish", _finish),
    )
    for name, node in nodes:
        builder.add_node(name, observed_node("protected_turn", name, node))
    builder.add_edge(START, nodes[0][0])
    for (left, _), (right, _) in zip(nodes, nodes[1:]):
        builder.add_edge(left, right)
    builder.add_edge(nodes[-1][0], END)
    return builder.compile(checkpointer=False, name="CogniGuardProtectedTurn")


PROTECTED_TURN_GRAPH = build_protected_turn_graph()


def run_protected_turn(
    owner: AgentOrchestrator,
    student_multimodal_data: dict[str, Any],
    student_response: str,
    round_id: str,
    monitor=None,
) -> dict[str, Any]:
    frame = ProtectedTurnFrame(owner, student_multimodal_data, student_response, round_id)
    state = invoke_observed_graph(
        PROTECTED_TURN_GRAPH, {}, context=ProtectedTurnContext(frame), frame=frame, monitor=monitor
    )
    if not state.get("completed") or frame.result is None:
        raise RuntimeError("Protected turn graph did not produce a result")
    return frame.result
