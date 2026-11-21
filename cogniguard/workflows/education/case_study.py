"""Dashboard demo graph: load → protected agents → watermark → compliance → view."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from cogniguard.observability.graphs import invoke_observed_graph, observed_node
from cogniguard.observability.telemetry import SafeTelemetry


class DemoState(TypedDict, total=False):
    stage: str
    completed: bool


@dataclass
class DemoFrame:
    data_root: str | Path
    case_index: int
    event_sink: Callable[[dict[str, Any]], None] | None
    episode_id: str | None
    demo_case: Any = None
    round_id: str = ""
    runtime_status: dict[str, Any] = field(default_factory=dict)
    orchestrator: Any = None
    protected_flow: dict[str, Any] = field(default_factory=dict)
    final_answer: str = ""
    audit_trace: dict[str, Any] = field(default_factory=dict)
    compliance_state: dict[str, Any] = field(default_factory=dict)
    compliance_policy: dict[str, Any] = field(default_factory=dict)
    data_categories: list[Any] = field(default_factory=list)
    compliance_audit_log: list[Any] = field(default_factory=list)
    result: dict[str, Any] | None = None
    recorder: SafeTelemetry = field(default_factory=SafeTelemetry)


@dataclass
class DemoContext:
    frame: DemoFrame


def load_case(state: DemoState, runtime: Runtime[DemoContext]):
    f = runtime.context.frame
    from cogniguard.applications.education.case_study import _emit, _utc_now
    from cogniguard.applications.education.cases import load_demo_case
    from cogniguard.runtime.mode import get_runtime_status

    f.demo_case = load_demo_case(
        data_root=f.data_root, case_index=f.case_index, episode_id=f.episode_id
    )
    f.round_id = f"round_{uuid.uuid4().hex[:12]}"
    f.runtime_status = get_runtime_status()
    _emit(
        f.event_sink,
        {
            "type": "run_started",
            "round_id": f.round_id,
            "case_index": f.case_index,
            "episode_id": f.demo_case.episode_id or f.episode_id,
            "fopd_path": "enhanced",
            "timestamp": _utc_now(),
        },
    )
    return {"stage": "load_case"}


def protected_agents(state: DemoState, runtime: Runtime[DemoContext]):
    f = runtime.context.frame
    from cogniguard.agents.protected_orchestrator import AgentOrchestrator
    from cogniguard.applications.education.case_study import DemoC2RAGService

    f.orchestrator = AgentOrchestrator(c2rag_service=DemoC2RAGService(f.demo_case), event_sink=None)
    f.protected_flow = f.orchestrator.run_protected_flow(
        student_multimodal_data={
            "context_card": f.demo_case.context_card,
            "profile_encoding": f.demo_case.profile_encoding or {},
            "knowledge_point": f.demo_case.context_card.get("knowledge_point"),
            "difficulty": f.demo_case.context_card.get("task_type", "unknown"),
        },
        student_response=f.demo_case.simulated_student_response,
        round_id=f.round_id,
    )
    return {"stage": "protected_agents"}


def watermark_bind(state: DemoState, runtime: Runtime[DemoContext]):
    f = runtime.context.frame
    from cogniguard.applications.education.case_study import DemoHSWSTBinder, _profile_card_id

    agent_logs = (
        f.orchestrator.profile_diagnosis_agent.call_log
        + f.orchestrator.resource_agent.call_log
        + f.orchestrator.teaching_agent.call_log
        + f.orchestrator.assessment_agent.call_log
    )
    binding = DemoHSWSTBinder().bind(
        teaching_answer=f.protected_flow["teaching_answer"],
        answer_id=f"ans_{f.round_id}",
        profile_card_id=_profile_card_id(f.protected_flow["context_card"], f.demo_case),
        controlled_resource_snippets=f.protected_flow["controlled_resource_snippets"],
        agent_call_logs=agent_logs,
        communication_logs=f.protected_flow["agent_messages"],
        profile_update_logs=f.protected_flow["profile_update_approval"],
    )
    f.final_answer = binding["final_protected_answer"]
    f.audit_trace = binding["audit_trace"]
    return {"stage": "watermark_bind"}


def compliance(state: DemoState, runtime: Runtime[DemoContext]):
    f = runtime.context.frame
    from cogniguard.compliance import build_data_categories

    f.compliance_state = dict(f.orchestrator.cg.compliance_state)
    f.compliance_policy = (
        f.protected_flow["cg_pre_check"].get("compliance_policy")
        or f.orchestrator.cg.last_compliance_policy
        or {}
    )
    f.data_categories = (
        build_data_categories(f.protected_flow["context_card"], payload_kind="context_card")
        + build_data_categories(
            f.protected_flow["profile_encoding"], payload_kind="profile_encoding"
        )
        + build_data_categories(f.audit_trace, payload_kind="audit")
    )
    f.compliance_audit_log = list(f.orchestrator.cg.compliance_audit_log)
    return {"stage": "compliance"}


def package_view(state: DemoState, runtime: Runtime[DemoContext]):
    f = runtime.context.frame
    from cogniguard.applications.education.case_study import (
        _build_protection_logs,
        _build_workflow_steps,
        _emit,
    )

    flow = f.protected_flow
    outputs = {
        "ProfileDiagnosisAgent": {"diagnosis_result": flow["diagnosis_result"]},
        "CopyrightAwareResourceAgent": {
            "controlled_resource_snippets": flow["controlled_resource_snippets"]
        },
        "PedagogicalTeachingAgent": {
            "teaching_answer": flow["teaching_answer"],
            "teaching_strategy_used": flow["teaching_strategy_used"],
        },
        "LearningAssessmentAgent": flow["assessment_result"],
    }
    protection_logs = _build_protection_logs(
        context_card=flow["context_card"],
        profile_encoding=flow["profile_encoding"],
        snippets=flow["controlled_resource_snippets"],
        audit_trace=f.audit_trace,
        cg_pre_check=flow["cg_pre_check"],
        profile_update=flow["profile_update_approval"],
        runtime_status=f.runtime_status,
        compliance_state=f.compliance_state,
        compliance_policy=f.compliance_policy,
        compliance_audit_log=f.compliance_audit_log,
    )
    steps = _build_workflow_steps(
        demo_case=f.demo_case,
        flow=flow,
        final_answer=f.final_answer,
        audit_trace=f.audit_trace,
        runtime_status=f.runtime_status,
        protection_logs=protection_logs,
    )
    for step in steps:
        _emit(f.event_sink, {"type": "workflow_step", "step": step})
    f.result = {
        "round_id": f.round_id,
        "case_index": f.case_index,
        "episode_id": f.demo_case.episode_id or f.episode_id,
        "fopd_path": "enhanced",
        "use_enhanced_fopd": True,
        "runtime_status": f.runtime_status,
        "raw_data_summary": f.demo_case.raw_data_summary,
        "generated_context_card": flow["context_card"],
        "abstract_profile": f.demo_case.abstract_profile or {},
        "profile_encoding": flow["profile_encoding"],
        "educational_semantics": f.demo_case.educational_semantics,
        "simulated_student_response": f.demo_case.simulated_student_response,
        "cg_risk_decision": flow["cg_pre_check"],
        "compliance_state": f.compliance_state,
        "compliance_policy": f.compliance_policy,
        "data_categories": f.data_categories,
        "compliance_audit_log": f.compliance_audit_log,
        "agent_outputs": outputs,
        "workflow_steps": steps,
        "communication_logs": flow["agent_messages"],
        "profile_update_decision": flow["profile_update_approval"],
        "protection_logs": protection_logs,
        "final_protected_teaching_answer": f.final_answer,
        "audit_trace": f.audit_trace,
    }
    return {"stage": "package_view", "completed": True}


def build_demo_graph():
    builder = StateGraph(DemoState, context_schema=DemoContext)
    nodes = (
        ("load_case", load_case),
        ("protected_agents", protected_agents),
        ("watermark_bind", watermark_bind),
        ("compliance", compliance),
        ("package_view", package_view),
    )
    for name, fn in nodes:
        builder.add_node(name, observed_node("dashboard", name, fn))
    builder.add_edge(START, nodes[0][0])
    for (left, _), (right, _) in zip(nodes, nodes[1:]):
        builder.add_edge(left, right)
    builder.add_edge(nodes[-1][0], END)
    return builder.compile(checkpointer=False, name="CogniGuardDashboardDemo")


DEMO_GRAPH = build_demo_graph()


def run_demo_graph(data_root="data", case_index=0, event_sink=None, episode_id=None, monitor=None):
    frame = DemoFrame(data_root, case_index, event_sink, episode_id)
    state = invoke_observed_graph(
        DEMO_GRAPH, {}, context=DemoContext(frame), frame=frame, monitor=monitor
    )
    if not state.get("completed") or frame.result is None:
        raise RuntimeError("Demo graph did not complete")
    return frame.result
