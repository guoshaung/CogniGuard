from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml

from protection.student_profile.src.agents.multi_agent_orchestrator import MultiAgentOrchestrator
from protection.teacher_resource.src.c2rag.c2rag_metrics import compute_c2rag_metrics
from protection.teacher_resource.src.c2rag.exposure_budget import ExposureBudget
from protection.teacher_resource.src.c2rag.retriever import CopyrightAwareRetriever
from protection.teacher_resource.src.c2rag.return_policy import produce_controlled_resource
from protection.common.metrics import summarize_metric_rows
from protection.common.schemas import StudentProfile, TeacherResource
from protection.common.text_utils import read_jsonl, write_json, write_jsonl
from protection.common.trace_binding import (
    build_source_trace_log,
    build_unified_trace_log,
    build_watermark_log,
    new_answer_id,
    new_watermark_id,
    normalize_source_trace,
)
from protection.student_profile.src.fopd.context_card import build_context_card
from protection.student_profile.src.fopd.fopd_metrics import compute_fopd_metrics
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
from protection.student_profile.src.fopd.task_parser import parse_task
from protection.student_profile.src.pipeline.ag2_simulator import build_ag2_request, compose_final_answer


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_profiles(path: str | Path) -> dict[str, StudentProfile]:
    return {
        p.student_id: p
        for p in (StudentProfile.from_dict(row) for row in read_jsonl(path))
    }


def load_resources(path: str | Path) -> list[TeacherResource]:
    return [TeacherResource.from_dict(row) for row in read_jsonl(path)]


def run_pipeline(
    profiles_path: str | Path,
    questions_path: str | Path,
    resources_path: str | Path,
    config_path: str | Path,
    out_path: str | Path,
) -> dict[str, Any]:
    config = load_config(config_path)
    profiles = load_profiles(profiles_path)
    questions = read_jsonl(questions_path)
    resources = load_resources(resources_path)
    selector = ProfileSelector(config)
    budget = ExposureBudget(config)
    retriever = CopyrightAwareRetriever(resources, budget, config)
    agents = MultiAgentOrchestrator(config)

    rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    watermark_logs: list[dict[str, Any]] = []
    source_trace_logs: list[dict[str, Any]] = []
    unified_trace_logs: list[dict[str, Any]] = []
    hsw_rows: list[dict[str, Any]] = []

    for qrow in questions:
        task = parse_task(qrow)
        agent1_log = agents.agent1_task_model(qrow, task)
        answer_id = new_answer_id(task.request_id)
        watermark_id = new_watermark_id(answer_id)
        profile = profiles[task.student_id]
        selected = selector.select(profile, task)
        context_card, redaction_log = build_context_card(profile, task, selected)
        fopd_metrics = compute_fopd_metrics(profile, task, context_card, selected)
        ag2_request, agent2_request_log = agents.agent2_resource_request(task, context_card)

        retrieved = []
        controlled = None
        if task.need_resource:
            retrieved = retriever.retrieve(ag2_request, task, context_card)
            if retrieved:
                retrieval_trace = [
                    {
                        "rank": rank,
                        "resource_id": item.resource.resource_id,
                        "chunk_id": item.resource.chunk_id,
                        "score": item.score,
                        "components": item.components,
                    }
                    for rank, item in enumerate(retrieved, start=1)
                ]
                controlled = produce_controlled_resource(
                    retrieved[0].resource,
                    budget,
                    config,
                    retrieval_trace=retrieval_trace,
                )

        final_answer, agent2_answer_log = agents.agent2_final_answer(task, context_card, controlled)
        sources = normalize_source_trace(controlled.source_trace if controlled else None)
        source_trace_log = build_source_trace_log(
            answer_id=answer_id,
            sample_id=task.request_id,
            watermark_id=watermark_id,
            sources=sources,
        )
        watermark_log = build_watermark_log(
            answer_id=answer_id,
            sample_id=task.request_id,
            watermark_id=watermark_id,
        )
        unified_trace_log = build_unified_trace_log(
            answer_id=answer_id,
            request_id=task.request_id,
            student_id=task.student_id,
            watermark_id=watermark_id,
            sources=sources,
            return_mode=controlled.mode if controlled else "none",
            final_answer=final_answer,
        )
        watermark_logs.append(watermark_log)
        source_trace_logs.append(source_trace_log)
        unified_trace_logs.append(unified_trace_log)
        agent3_log = agents.agent3_policy_explain(
            return_mode=controlled.mode if controlled else "none",
            retrieved_chunks=[x.resource.chunk_id for x in retrieved],
            source_trace=controlled.source_trace if controlled else {},
        )
        agent4_log = agents.agent4_trace_explain(
            watermark_id=watermark_id,
            trace_binding_id=str(unified_trace_log["trace_binding_id"]),
            source_trace_log=source_trace_log,
        )
        hsw_sources = []
        for source in sources:
            hsw_sources.append(
                {
                    **source,
                    "trace_binding_id": unified_trace_log["trace_binding_id"],
                    "upstream_watermark_id": watermark_id,
                }
            )
        hsw_rows.append(
            {
                "sample_id": task.request_id,
                "answer_id": answer_id,
                "watermark_id": watermark_id,
                "trace_binding_id": unified_trace_log["trace_binding_id"],
                "subject": "math",
                "topic": task.knowledge,
                "question": task.question,
                "draft_answer": final_answer,
                "source_trace": hsw_sources,
                "protected_terms": [task.knowledge],
                "protected_formulas": re.findall(r"[a-zA-Z]\s*=\s*[^，。；\s]+|[a-zA-Z]\^\d+", task.question + final_answer),
                "protected_numbers": re.findall(r"-?\d+(?:\.\d+)?", task.question + final_answer),
            }
        )

        c2_metrics = compute_c2rag_metrics(controlled, final_answer, resources)
        metrics = {**fopd_metrics, **c2_metrics}
        metric_rows.append(metrics)

        rows.append(
            {
                "answer_id": answer_id,
                "request_id": task.request_id,
                "student_id": task.student_id,
                "watermark_id": watermark_id,
                "trace_binding_id": unified_trace_log["trace_binding_id"],
                "task": {
                    "knowledge": task.knowledge,
                    "difficulty": task.difficulty,
                    "need_resource": task.need_resource,
                },
                "question": task.question,
                "context_card": context_card,
                "selected_profile_records": [x.record.record_id for x in selected],
                "profile_selection_scores": [
                    {"record_id": x.record.record_id, "score": x.score, "components": x.components}
                    for x in selected
                ],
                "privacy_redaction_log": redaction_log,
                "ag2_request": ag2_request,
                "retrieved_chunks": [x.resource.chunk_id for x in retrieved],
                "retrieval_scores": [
                    {"chunk_id": x.resource.chunk_id, "score": x.score, "components": x.components}
                    for x in retrieved
                ],
                "return_mode": controlled.mode if controlled else "none",
                "controlled_resource": controlled.text if controlled else "",
                "final_answer": final_answer,
                "source_trace": controlled.source_trace if controlled else {},
                "source_trace_log": source_trace_log,
                "agent_logs": {
                    "AG1": agent1_log,
                    "AG2_request": agent2_request_log,
                    "AG2_answer": agent2_answer_log,
                    "AG3": agent3_log,
                    "AG4": agent4_log,
                },
                "algorithm_links": agents.algorithm_links(),
                "metrics": metrics,
            }
        )

    out_path = Path(out_path)
    write_jsonl(out_path, rows)
    write_jsonl(out_path.parent / "watermark_logs.jsonl", watermark_logs)
    write_jsonl(out_path.parent / "source_trace_logs.jsonl", source_trace_logs)
    write_jsonl(out_path.parent / "unified_trace_logs.jsonl", unified_trace_logs)
    write_jsonl(out_path.parent / "hsw_st_input.jsonl", hsw_rows)
    summary = summarize_metric_rows(metric_rows)
    summary["llm_enabled"] = agents.enabled
    summary["llm_model"] = config.get("llm", {}).get("model", "")
    summary["mode_counts"] = {}
    for row in rows:
        mode = str(row["return_mode"])
        summary["mode_counts"][mode] = summary["mode_counts"].get(mode, 0) + 1
    write_json(out_path.parent / "metrics_summary.json", summary)
    report_lines = [
        "# FOPD + C2-RAG MVP Report",
        "",
        f"- Requests: {summary['num_requests']}",
        f"- Avg PER: {summary.get('avg_PER', 0):.3f}",
        f"- Avg TaskCoverage: {summary.get('avg_TaskCoverage', 0):.3f}",
        f"- Avg CRR: {summary.get('avg_CRR', 0):.3f}",
        f"- Avg MER: {summary.get('avg_MER', 0):.3f}",
        f"- Return modes: {summary['mode_counts']}",
    ]
    (out_path.parent / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    return {"rows": rows, "summary": summary}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--profiles",
        default="protection/student_profile/data/profiles.jsonl",
    )
    ap.add_argument(
        "--questions",
        default="protection/student_profile/data/student_questions.jsonl",
    )
    ap.add_argument(
        "--resources",
        default="protection/teacher_resource/data/teacher_resources.jsonl",
    )
    ap.add_argument(
        "--config",
        default="protection/student_profile/configs/default.yaml",
    )
    ap.add_argument(
        "--out",
        default="protection/student_profile/outputs/demo_results.jsonl",
    )
    args = ap.parse_args()
    result = run_pipeline(args.profiles, args.questions, args.resources, args.config, args.out)
    print(f"Wrote {args.out}")
    print(result["summary"])


if __name__ == "__main__":
    main()
