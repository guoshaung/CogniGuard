"""Graph orchestration for the MM-FOPD baseline comparison matrix."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
import json
from pathlib import Path
import statistics
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context

from experiments.mmfopd_v3.baselines import METHODS
from protection.common.schemas import StudentProfile
from protection.common.text_utils import read_jsonl
from protection.student_profile.src.pipeline.run_demo import load_config


class MMState(TypedDict, total=False):
    stage: str
    job_index: int
    job_count: int
    completed: bool


@dataclass
class MMFrame:
    data_root: Path
    config_path: Path
    output: Path
    split: str
    config: dict[str, Any] = field(default_factory=dict)
    profiles: dict[str, StudentProfile] = field(default_factory=dict)
    questions: list[dict] = field(default_factory=list)
    jobs: list[tuple[dict, str]] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    summary: list[dict] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)


@dataclass
class MMContext:
    frame: MMFrame


def load_inputs(state: MMState, runtime: Runtime[MMContext]):
    f = runtime.context.frame
    f.config = load_config(f.config_path)
    f.profiles = {str(row["student_id"]): StudentProfile.from_dict(row)
                  for row in read_jsonl(f.data_root / "profiles.jsonl")}
    f.questions = [row for row in read_jsonl(f.data_root / "student_questions.jsonl")
                   if row.get("split") == f.split]
    f.jobs = [(question, method) for question in f.questions for method in METHODS]
    return {"stage": "load_inputs", "job_index": 0, "job_count": len(f.jobs)}


def evaluate_method(state: MMState, runtime: Runtime[MMContext]):
    f = runtime.context.frame
    from .runner import _metrics, _task
    question, method = f.jobs[state["job_index"]]
    task = _task(question)
    profile = f.profiles[task.student_id]
    selected = METHODS[method](profile, task, f.config)
    f.rows.append({
        "method": method, "request_id": task.request_id,
        "student_id": task.student_id, "split": f.split,
        "selected_ids": "|".join(item.record.record_id for item in selected),
        **_metrics(profile, task, selected),
    })
    return {"stage": "evaluate_method", "job_index": state["job_index"] + 1}


def aggregate(state: MMState, runtime: Runtime[MMContext]):
    f = runtime.context.frame
    metrics = [
        "selected_count", "weighted_profile_exposure", "selection_privacy_cost",
        "released_profile_exposure", "released_sensitive_attribute_exposure",
        "released_value_exposure_t05", "released_value_exposure_t06",
        "released_value_exposure_t07", "released_value_exposure_t08",
        "sensitive_attribute_exposure", "sensitive_exposure_t05",
        "sensitive_exposure_t06", "sensitive_exposure_t08",
        "mean_selected_sensitivity", "required_unit_recall", "unit_precision",
        "unit_reconstruction_f1", "irrelevant_unit_exposure", "irrelevant_exposure_rate",
        "task_relevant_information_recall", "exact_profile_reconstruction_recall",
    ]
    f.summary = []
    for method in METHODS:
        subset = [row for row in f.rows if row["method"] == method]
        f.summary.append({"method": method, "n": len(subset), **{
            metric: statistics.mean(float(row[metric]) for row in subset) if subset else 0.0
            for metric in metrics
        }})
    f.manifest = {
        "status": "PILOT_NOT_PAPER_RESULT", "orchestrator": "langgraph",
        "split": f.split, "case_count": len(f.questions), "methods": list(METHODS),
        "limitations": [
            "GPG is an extractive adapter, not an official LLM reproduction.",
            "PAPILLON and Privacy Funnel are interface-aligned adapters, not official reproductions.",
            "LLM Data Minimization is a deterministic proxy pending the frozen local-Qwen prompt.",
            "PPlug is excluded until a representation-level attribute-inference attacker is implemented.",
            "Teaching utility and learned attribute-inference attacks are not yet included.",
            "Exact reconstruction is a deterministic lower-bound attacker.",
        ],
    }
    return {"stage": "aggregate"}


def persist(state: MMState, runtime: Runtime[MMContext]):
    f = runtime.context.frame
    f.output.mkdir(parents=True, exist_ok=False)
    for name, data in (("rows.csv", f.rows), ("summary.csv", f.summary)):
        with (f.output / name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]) if data else [])
            if data:
                writer.writeheader()
                writer.writerows(data)
    (f.output / "manifest.json").write_text(json.dumps(f.manifest, indent=2), encoding="utf-8")
    return {"stage": "persist", "completed": True}


def build_mm_graph():
    builder = StateGraph(MMState, context_schema=MMContext)
    nodes = (("load_inputs", load_inputs), ("evaluate_method", evaluate_method),
             ("aggregate", aggregate), ("persist", persist))
    for name, fn in nodes:
        builder.add_node(name, fn)
    builder.add_edge(START, "load_inputs")
    builder.add_conditional_edges("load_inputs", lambda s: "run" if s["job_count"] else "aggregate",
                                  {"run": "evaluate_method", "aggregate": "aggregate"})
    builder.add_conditional_edges("evaluate_method",
                                  lambda s: "again" if s["job_index"] < s["job_count"] else "aggregate",
                                  {"again": "evaluate_method", "aggregate": "aggregate"})
    builder.add_edge("aggregate", "persist")
    builder.add_edge("persist", END)
    return builder.compile(checkpointer=False, name="CogniGuardMMFOPDComparison")


MM_GRAPH = build_mm_graph()


def run_mm_graph(*, data_root: Path, config_path: Path, output: Path, split: str = "test"):
    frame = MMFrame(data_root, config_path, output, split)
    with tracing_context(enabled=False):
        state = MM_GRAPH.invoke({}, context=MMContext(frame),
                                config={"recursion_limit": 10000})
    if not state.get("completed"):
        raise RuntimeError("MM-FOPD comparison graph did not complete")
    return {"manifest": frame.manifest, "summary": frame.summary}
