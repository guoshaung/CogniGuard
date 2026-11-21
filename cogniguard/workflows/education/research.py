"""Graph execution for the research FOPD → C²-RAG → audit flow."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from cogniguard.observability.graphs import invoke_observed_graph, observed_node
from cogniguard.observability.telemetry import SafeTelemetry
from protection.common.schemas import StudentProfile, Task, TeacherResource

if TYPE_CHECKING:
    from cogniguard.agents.research_orchestrator import MultiAgentOrchestrator


class ResearchState(TypedDict, total=False):
    stage: str
    completed: bool


@dataclass
class ResearchFrame:
    owner: MultiAgentOrchestrator
    query: str
    student_profile: StudentProfile
    teacher_resources: list[TeacherResource]
    teaching_phase: str
    task: Task | None = None
    result: dict[str, Any] = field(
        default_factory=lambda: {
            "answer": "",
            "fopd_context": [],
            "c2rag_context": [],
            "audit_chain_id": None,
            "metadata": {},
        }
    )
    recorder: SafeTelemetry = field(default_factory=SafeTelemetry)


@dataclass
class ResearchContext:
    frame: ResearchFrame


def prepare(state: ResearchState, runtime: Runtime[ResearchContext]):
    f = runtime.context.frame
    request_id = hashlib.sha256(
        (f.student_profile.student_id + "|" + f.query).encode()
    ).hexdigest()[:16]
    f.task = Task(
        request_id=request_id,
        student_id=f.student_profile.student_id,
        question=f.query,
        knowledge=f.owner._extract_knowledge(f.query),
        difficulty="unknown",
        need_resource=bool(f.teacher_resources),
    )
    return {"stage": "prepare"}


def select_profile(state: ResearchState, runtime: Runtime[ResearchContext]):
    f = runtime.context.frame
    if f.owner.enable_fopd:
        selected = f.owner.profile_selector.select(f.student_profile, f.task)
        f.result["fopd_context"] = [
            {
                "record": asdict(item.record),
                "score": item.score,
                "protected": item.record.sensitivity > 0.7,
            }
            for item in selected
        ]
        f.result["metadata"]["fopd_used"] = len(selected)
    return {"stage": "select_profile"}


def control_resources(state: ResearchState, runtime: Runtime[ResearchContext]):
    f = runtime.context.frame
    if not f.owner.enable_c2rag:
        return {"stage": "control_resources"}
    protected = []
    for resource in f.teacher_resources:
        budget = f.owner.budget_allocator.allocate(
            chunk_id=resource.resource_id,
            copyright_level=resource.copyright_level,
            teaching_phase=f.teaching_phase,
        )
        if resource.copyright_level > 0.8:
            variant = f.owner.variant_generator.adaptive_select(resource, resource.copyright_level)
            item = {
                "resource_id": resource.resource_id,
                "content": variant["variant_text"],
                "return_mode": "variant",
                "copyright_level": resource.copyright_level,
                "budget_used": budget,
                "granularity": variant["granularity"],
            }
        elif resource.copyright_level > 0.5:
            item = {
                "resource_id": resource.resource_id,
                "content": resource.content[: int(len(resource.content) * budget)],
                "return_mode": "partial",
                "copyright_level": resource.copyright_level,
                "budget_used": budget,
            }
        else:
            item = {
                "resource_id": resource.resource_id,
                "content": resource.content,
                "return_mode": "direct",
                "copyright_level": resource.copyright_level,
                "budget_used": budget,
            }
        protected.append(item)
        f.owner.budget_allocator.record_exposure(resource.resource_id, budget)
    f.result["c2rag_context"] = protected
    f.result["metadata"]["c2rag_resources"] = len(protected)
    return {"stage": "control_resources"}


def audit_answer(state: ResearchState, runtime: Runtime[ResearchContext]):
    f = runtime.context.frame
    if not f.owner.enable_audit:
        return {"stage": "audit_answer"}
    answer = f.owner._generate_answer(f.query, f.result["fopd_context"], f.result["c2rag_context"])
    answer_id = "answer_" + hashlib.sha256(f.query.encode()).hexdigest()[:16]
    watermarked = f.owner.watermark_system.embed_hybrid(
        text=answer,
        resource_id=answer_id,
        mode="both",
    )
    f.result["answer"] = watermarked["watermarked_text"]
    sources = [
        {
            "resource_id": item["resource_id"],
            "chunk_id": item["resource_id"],
            "copyright_level": item["copyright_level"],
            "exposure_before": 0.0,
            "exposure_after": item["budget_used"],
            "return_mode": item["return_mode"],
        }
        for item in f.result["c2rag_context"]
    ]
    marker = next(
        (
            value
            for value in watermarked.get("semantic_markers", [])
            if value in watermarked["watermarked_text"]
        ),
        None,
    )
    watermark_info = {
        **watermarked.get("statistical_config", {}),
        "semantic_marker": marker,
        "watermarked_text_sha256": hashlib.sha256(
            watermarked["watermarked_text"].encode()
        ).hexdigest(),
        "verification_method": "exact_text_digest_and_semantic_marker",
    }
    f.result["audit_chain_id"] = f.owner.audit_chain.create_link(
        student_answer_id=answer_id,
        teacher_resources=sources,
        watermark_info=watermark_info,
        context_type="c2rag_resource",
    )
    f.result["metadata"]["answer_id"] = answer_id
    f.result["metadata"]["watermark_confidence"] = watermarked.get("statistical_config", {}).get(
        "gamma", 0.0
    )
    return {"stage": "audit_answer"}


def finish(state: ResearchState, runtime: Runtime[ResearchContext]):
    return {"stage": "finish", "completed": True}


def build_research_flow_graph():
    builder = StateGraph(ResearchState, context_schema=ResearchContext)
    nodes = (
        ("prepare", prepare),
        ("select_profile", select_profile),
        ("control_resources", control_resources),
        ("audit_answer", audit_answer),
        ("finish", finish),
    )
    for name, node in nodes:
        builder.add_node(name, observed_node("research", name, node))
    builder.add_edge(START, nodes[0][0])
    for (left, _), (right, _) in zip(nodes, nodes[1:]):
        builder.add_edge(left, right)
    builder.add_edge(nodes[-1][0], END)
    return builder.compile(checkpointer=False, name="CogniGuardResearchFlow")


RESEARCH_FLOW_GRAPH = build_research_flow_graph()


def run_research_flow(
    owner, query, student_profile, teacher_resources, teaching_phase, monitor=None
):
    frame = ResearchFrame(owner, query, student_profile, teacher_resources, teaching_phase)
    state = invoke_observed_graph(
        RESEARCH_FLOW_GRAPH, {}, context=ResearchContext(frame), frame=frame, monitor=monitor
    )
    if not state.get("completed"):
        raise RuntimeError("Research graph did not complete")
    return frame.result
