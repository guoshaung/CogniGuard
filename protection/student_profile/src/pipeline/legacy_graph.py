"""LangGraph orchestration for the historical FOPD/C2-RAG batch contract.

This graph preserves the old report/artifact schema while moving the actual
per-question Agent handoffs and shared exposure budget loop into graph nodes.
Sensitive profile, question and resource values stay in call-local context;
only counters and control flags are graph state. No checkpoint/retry is used
because exposure-budget commits are not idempotent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context

from protection.common.trace_binding import (
    build_source_trace_log, build_unified_trace_log, build_watermark_log,
    new_answer_id, new_watermark_id, normalize_source_trace,
)
from protection.student_profile.src.fopd.context_card import build_context_card
from protection.student_profile.src.fopd.fopd_metrics import compute_fopd_metrics
from protection.student_profile.src.fopd.task_parser import parse_task
from protection.teacher_resource.src.c2rag.return_policy import produce_controlled_resource
from protection.teacher_resource.src.c2rag.c2rag_metrics import compute_c2rag_metrics


class LegacyState(TypedDict, total=False):
    index: int
    resource_required: bool
    selected_count: int
    retrieved_count: int
    return_mode: str
    completed: bool


@dataclass
class LegacyFrame:
    questions: list[dict[str, Any]]
    profiles: dict[str, Any]
    resources: list[Any]
    config: dict[str, Any]
    selector: Any
    budget: Any
    retriever: Any
    metric_index: Any
    agents: Any
    rows: list[dict[str, Any]] = field(default_factory=list)
    metric_rows: list[dict[str, Any]] = field(default_factory=list)
    watermark_logs: list[dict[str, Any]] = field(default_factory=list)
    source_trace_logs: list[dict[str, Any]] = field(default_factory=list)
    unified_trace_logs: list[dict[str, Any]] = field(default_factory=list)
    hsw_rows: list[dict[str, Any]] = field(default_factory=list)
    task: Any = None
    agent1_log: dict[str, Any] = field(default_factory=dict)
    answer_id: str = ""
    watermark_id: str = ""
    profile: Any = None
    selected: list[Any] = field(default_factory=list)
    context_card: str = ""
    redaction_log: Any = None
    fopd_metrics: dict[str, Any] = field(default_factory=dict)
    ag2_request: dict[str, Any] = field(default_factory=dict)
    agent2_request_log: dict[str, Any] = field(default_factory=dict)
    retrieved: list[Any] = field(default_factory=list)
    controlled: Any = None
    final_answer: str = ""
    agent2_answer_log: dict[str, Any] = field(default_factory=dict)
    source_trace_log: dict[str, Any] = field(default_factory=dict)
    unified_trace_log: dict[str, Any] = field(default_factory=dict)
    agent3_log: dict[str, Any] = field(default_factory=dict)
    agent4_log: dict[str, Any] = field(default_factory=dict)


@dataclass
class LegacyContext:
    frame: LegacyFrame


def select_task(state: LegacyState, runtime: Runtime[LegacyContext]):
    f = runtime.context.frame
    qrow = f.questions[state["index"]]
    f.task = parse_task(qrow)
    f.agent1_log = f.agents.agent1_task_model(qrow, f.task)
    f.answer_id = new_answer_id(f.task.request_id)
    f.watermark_id = new_watermark_id(f.answer_id)
    f.profile = f.profiles[f.task.student_id]
    f.selected = f.selector.select(f.profile, f.task)
    f.context_card, f.redaction_log = build_context_card(f.profile, f.task, f.selected)
    f.fopd_metrics = compute_fopd_metrics(f.profile, f.task, f.context_card, f.selected)
    f.ag2_request, f.agent2_request_log = f.agents.agent2_resource_request(
        f.task, f.context_card)
    return {"resource_required": bool(f.task.need_resource),
            "selected_count": len(f.selected)}


def retrieve_and_control(state: LegacyState, runtime: Runtime[LegacyContext]):
    f = runtime.context.frame
    f.retrieved = []
    f.controlled = None
    if f.task.need_resource:
        f.retrieved = f.retriever.retrieve(f.ag2_request, f.task, f.context_card)
        if f.retrieved:
            retrieval_trace = [
                {"rank": rank, "resource_id": item.resource.resource_id,
                 "chunk_id": item.resource.chunk_id, "score": item.score,
                 "components": item.components}
                for rank, item in enumerate(f.retrieved, start=1)
            ]
            f.controlled = produce_controlled_resource(
                f.retrieved[0].resource, f.budget, f.config,
                retrieval_trace=retrieval_trace,
            )
    return {"retrieved_count": len(f.retrieved),
            "return_mode": f.controlled.mode if f.controlled else "none"}


def answer_and_bind(state: LegacyState, runtime: Runtime[LegacyContext]):
    f = runtime.context.frame
    task = f.task
    f.final_answer, f.agent2_answer_log = f.agents.agent2_final_answer(
        task, f.context_card, f.controlled)
    sources = normalize_source_trace(f.controlled.source_trace if f.controlled else None)
    f.source_trace_log = build_source_trace_log(
        answer_id=f.answer_id, sample_id=task.request_id,
        watermark_id=f.watermark_id, sources=sources)
    watermark_log = build_watermark_log(
        answer_id=f.answer_id, sample_id=task.request_id,
        watermark_id=f.watermark_id)
    f.unified_trace_log = build_unified_trace_log(
        answer_id=f.answer_id, request_id=task.request_id,
        student_id=task.student_id, watermark_id=f.watermark_id,
        sources=sources, return_mode=f.controlled.mode if f.controlled else "none",
        final_answer=f.final_answer)
    f.watermark_logs.append(watermark_log)
    f.source_trace_logs.append(f.source_trace_log)
    f.unified_trace_logs.append(f.unified_trace_log)
    f.agent3_log = f.agents.agent3_policy_explain(
        return_mode=f.controlled.mode if f.controlled else "none",
        retrieved_chunks=[x.resource.chunk_id for x in f.retrieved],
        source_trace=f.controlled.source_trace if f.controlled else {})
    f.agent4_log = f.agents.agent4_trace_explain(
        watermark_id=f.watermark_id,
        trace_binding_id=str(f.unified_trace_log["trace_binding_id"]),
        source_trace_log=f.source_trace_log)
    hsw_sources = [
        {**source, "trace_binding_id": f.unified_trace_log["trace_binding_id"],
         "upstream_watermark_id": f.watermark_id}
        for source in sources
    ]
    f.hsw_rows.append({
        "sample_id": task.request_id, "answer_id": f.answer_id,
        "watermark_id": f.watermark_id,
        "trace_binding_id": f.unified_trace_log["trace_binding_id"],
        "subject": "math", "topic": task.knowledge,
        "question": task.question, "draft_answer": f.final_answer,
        "source_trace": hsw_sources, "protected_terms": [task.knowledge],
        "protected_formulas": re.findall(
            r"[a-zA-Z]\s*=\s*[^，。；\s]+|[a-zA-Z]\^\d+",
            task.question + f.final_answer),
        "protected_numbers": re.findall(
            r"-?\d+(?:\.\d+)?", task.question + f.final_answer),
    })
    return {}


def score_and_package(state: LegacyState, runtime: Runtime[LegacyContext]):
    f = runtime.context.frame
    task = f.task
    metrics = {**f.fopd_metrics, **compute_c2rag_metrics(
        f.controlled, f.final_answer, f.resources,
        metric_index=f.metric_index)}
    f.metric_rows.append(metrics)
    f.rows.append({
        "answer_id": f.answer_id,
        "request_id": task.request_id,
        "student_id": task.student_id,
        "watermark_id": f.watermark_id,
        "trace_binding_id": f.unified_trace_log["trace_binding_id"],
        "task": {"knowledge": task.knowledge, "difficulty": task.difficulty,
                 "need_resource": task.need_resource},
        "question": task.question,
        "context_card": f.context_card,
        "selected_profile_records": [x.record.record_id for x in f.selected],
        "profile_selection_scores": [
            {"record_id": x.record.record_id, "score": x.score,
             "components": x.components} for x in f.selected],
        "privacy_redaction_log": f.redaction_log,
        "ag2_request": f.ag2_request,
        "retrieved_chunks": [x.resource.chunk_id for x in f.retrieved],
        "retrieval_scores": [
            {"chunk_id": x.resource.chunk_id, "score": x.score,
             "components": x.components} for x in f.retrieved],
        "return_mode": f.controlled.mode if f.controlled else "none",
        "controlled_resource": f.controlled.text if f.controlled else "",
        "final_answer": f.final_answer,
        "source_trace": f.controlled.source_trace if f.controlled else {},
        "source_trace_log": f.source_trace_log,
        "agent_logs": {
            "AG1": f.agent1_log,
            "AG2_request": f.agent2_request_log,
            "AG2_answer": f.agent2_answer_log,
            "AG3": f.agent3_log,
            "AG4": f.agent4_log,
        },
        "algorithm_links": f.agents.algorithm_links(),
        "metrics": metrics,
    })
    return {}


def advance(state: LegacyState, runtime: Runtime[LegacyContext]):
    index = state["index"] + 1
    return {"index": index, "completed": index == len(runtime.context.frame.questions)}


def _route(state: LegacyState, runtime: Runtime[LegacyContext]):
    return END if state["index"] >= len(runtime.context.frame.questions) else "select_task"


def build_legacy_graph():
    builder = StateGraph(LegacyState, context_schema=LegacyContext)
    for name, fn in (
        ("select_task", select_task),
        ("retrieve_and_control", retrieve_and_control),
        ("answer_and_bind", answer_and_bind),
        ("score_and_package", score_and_package),
        ("advance", advance),
    ):
        builder.add_node(name, fn)
    builder.add_conditional_edges(START, _route)
    builder.add_edge("select_task", "retrieve_and_control")
    builder.add_edge("retrieve_and_control", "answer_and_bind")
    builder.add_edge("answer_and_bind", "score_and_package")
    builder.add_edge("score_and_package", "advance")
    builder.add_conditional_edges("advance", _route)
    return builder.compile(checkpointer=False, name="CogniGuardLegacyEducationBatch")


LEGACY_GRAPH = build_legacy_graph()


def run_legacy_batch(frame: LegacyFrame) -> LegacyFrame:
    with tracing_context(enabled=False):
        result = LEGACY_GRAPH.invoke(
            {"index": 0, "completed": not bool(frame.questions)},
            context=LegacyContext(frame),
            config={"recursion_limit": max(50, 6 * len(frame.questions) + 10)},
        )
    if not result.get("completed") or len(frame.rows) != len(frame.questions):
        raise RuntimeError("Legacy batch graph did not complete every request")
    return frame
