"""Historical FOPD/C2-RAG report entrypoint, now orchestrated by LangGraph.

The file and return contracts remain compatible with existing evaluation jobs.
The domain algorithms are kept as normal Python functions and graph nodes own
the stateful Agent handoffs and cross-question exposure-budget sequencing.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from protection.common.metrics import summarize_metric_rows
from protection.common.schemas import StudentProfile, TeacherResource
from protection.common.text_utils import read_jsonl, write_json, write_jsonl
from protection.student_profile.src.agents.multi_agent_orchestrator import MultiAgentOrchestrator
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
from protection.student_profile.src.pipeline.legacy_graph import LegacyFrame, run_legacy_batch
from protection.teacher_resource.src.c2rag.c2rag_metrics import CopyrightMetricIndex
from protection.teacher_resource.src.c2rag.exposure_budget import ExposureBudget
from protection.teacher_resource.src.c2rag.retriever import CopyrightAwareRetriever


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
    frame = run_legacy_batch(LegacyFrame(
        questions=questions,
        profiles=profiles,
        resources=resources,
        config=config,
        selector=selector,
        budget=budget,
        retriever=retriever,
        metric_index=CopyrightMetricIndex(resources),
        agents=agents,
    ))

    out_path = Path(out_path)
    write_jsonl(out_path, frame.rows)
    write_jsonl(out_path.parent / "watermark_logs.jsonl", frame.watermark_logs)
    write_jsonl(out_path.parent / "source_trace_logs.jsonl", frame.source_trace_logs)
    write_jsonl(out_path.parent / "unified_trace_logs.jsonl", frame.unified_trace_logs)
    write_jsonl(out_path.parent / "hsw_st_input.jsonl", frame.hsw_rows)
    summary = summarize_metric_rows(frame.metric_rows)
    summary["llm_enabled"] = agents.enabled
    summary["llm_model"] = config.get("llm", {}).get("model", "")
    summary["mode_counts"] = {}
    for row in frame.rows:
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
    return {"rows": frame.rows, "summary": summary}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", default="protection/student_profile/data/profiles.jsonl")
    ap.add_argument("--questions", default="protection/student_profile/data/student_questions.jsonl")
    ap.add_argument("--resources", default="protection/teacher_resource/data/teacher_resources.jsonl")
    ap.add_argument("--config", default="protection/student_profile/configs/default.yaml")
    ap.add_argument("--out", default="protection/student_profile/outputs/demo_results.jsonl")
    args = ap.parse_args()
    result = run_pipeline(args.profiles, args.questions, args.resources, args.config, args.out)
    print(f"Wrote {args.out}")
    print(result["summary"])


if __name__ == "__main__":
    main()
