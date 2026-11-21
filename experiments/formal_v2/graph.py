"""LangGraph for the deterministic formal-v2 method-by-case matrix."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context


class FormalState(TypedDict, total=False):
    stage: str
    job_index: int
    job_count: int
    completed: bool


@dataclass
class FormalFrame:
    split_root: Path
    output_root: Path
    seeds: list[int]
    case_limit: int | None
    cases: list[dict] = field(default_factory=list)
    jobs: list[tuple[int, dict, str, str]] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    aggregate_rows: list[dict] = field(default_factory=list)
    cis: list[dict] = field(default_factory=list)
    significance: list[dict] = field(default_factory=list)
    manifest: dict[str, Any] = field(default_factory=dict)


@dataclass
class FormalContext:
    frame: FormalFrame


def load_cases(state: FormalState, runtime: Runtime[FormalContext]):
    f = runtime.context.frame
    from .run_formal import _load_cases, FOPD_METHODS, C2_METHODS, CG_METHODS
    f.cases = _load_cases(f.split_root)
    if f.case_limit is not None:
        if f.case_limit <= 0:
            raise ValueError("case_limit must be positive")
        f.cases = f.cases[:f.case_limit]
    f.jobs = [
        (seed, case, family, method)
        for seed in f.seeds for case in f.cases
        for family, methods in (("MM-FOPD", FOPD_METHODS), ("C2-RAG", C2_METHODS), ("CG", CG_METHODS))
        for method in methods
    ]
    return {"stage": "load_cases", "job_index": 0, "job_count": len(f.jobs)}


def evaluate_job(state: FormalState, runtime: Runtime[FormalContext]):
    f = runtime.context.frame
    from .run_formal import _fopd_row, _c2_row, _cg_row, _evaluate
    seed, case, family, method = f.jobs[state["job_index"]]
    builder = {"MM-FOPD": _fopd_row, "C2-RAG": _c2_row, "CG": _cg_row}[family]
    row = builder(case, method, seed)
    row["evaluation"] = _evaluate(row, case)
    f.rows.append(row)
    return {"stage": "evaluate_job", "job_index": state["job_index"] + 1}


def aggregate(state: FormalState, runtime: Runtime[FormalContext]):
    f = runtime.context.frame
    from .run_formal import _aggregate
    f.aggregate_rows = _aggregate(f.rows)
    return {"stage": "aggregate"}


def statistics(state: FormalState, runtime: Runtime[FormalContext]):
    f = runtime.context.frame
    from .run_formal import _stats
    f.cis, f.significance = _stats(f.rows, f.aggregate_rows)
    return {"stage": "statistics"}


def persist(state: FormalState, runtime: Runtime[FormalContext]):
    f = runtime.context.frame
    from .run_formal import (ROOT, FOPD_METHODS, C2_METHODS, CG_METHODS,
                             _json_hash, _write_jsonl, _write_csv)
    f.output_root.mkdir(parents=True, exist_ok=False)
    _write_jsonl(f.output_root / "raw_results.jsonl", f.rows)
    _write_csv(f.output_root / "aggregated_metrics.csv", f.aggregate_rows)
    _write_csv(f.output_root / "confidence_intervals.csv", f.cis)
    _write_csv(f.output_root / "significance_tests.csv", f.significance)
    failures = [row for row in f.rows if any(row["evaluation"].get(metric, 0)
                for metric in ("plan_execution_mismatch", "over_refusal", "privacy_attack_success",
                               "copyright_attack_success", "cross_domain_attack_success"))]
    _write_jsonl(f.output_root / "failure_cases.jsonl", failures)
    f.manifest = {
        "status": "COMPLETED_LIMITED_SCALE_DETERMINISTIC",
        "orchestrator": "langgraph", "split": str(f.split_root.relative_to(ROOT)),
        "case_count": len(f.cases), "seed_count": len(f.seeds), "seed_values": f.seeds,
        "methods": {"MM-FOPD": list(FOPD_METHODS), "C2-RAG": list(C2_METHODS),
                    "CG": list(CG_METHODS)},
        "row_count": len(f.rows), "hidden_labels_passed_to_methods": False,
        "external_llm_used": False,
        "multi_round_reconstruction": "NOT_EVALUABLE_FROM_CURRENT_ONE-ROW-PER-PAIR_TEST_SCHEMA",
        "output_protection": {"HSW-ST": "BLOCKED_MODEL_CACHE_AND_INPUTS",
                              "SCE-LocGuard": "BLOCKED_ATTACK_PIPELINE_AND_PAPER_MODE"},
        "source_hash": _json_hash([case["case_id"] for case in f.cases]),
        "evaluator_version": "formal-v2-posthoc-1", "case_limit": f.case_limit,
    }
    (f.output_root / "run_manifest.json").write_text(
        json.dumps(f.manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"stage": "persist", "completed": True}


def build_formal_graph():
    builder = StateGraph(FormalState, context_schema=FormalContext)
    nodes = (("load_cases", load_cases), ("evaluate_job", evaluate_job),
             ("aggregate", aggregate), ("statistics", statistics), ("persist", persist))
    for name, fn in nodes:
        builder.add_node(name, fn)
    builder.add_edge(START, "load_cases")
    builder.add_conditional_edges("load_cases", lambda s: "run" if s["job_count"] else "aggregate",
                                  {"run": "evaluate_job", "aggregate": "aggregate"})
    builder.add_conditional_edges("evaluate_job",
                                  lambda s: "again" if s["job_index"] < s["job_count"] else "aggregate",
                                  {"again": "evaluate_job", "aggregate": "aggregate"})
    builder.add_edge("aggregate", "statistics")
    builder.add_edge("statistics", "persist")
    builder.add_edge("persist", END)
    return builder.compile(checkpointer=False, name="CogniGuardFormalV2")


FORMAL_GRAPH = build_formal_graph()


def run_formal_graph(split_root: Path, output_root: Path, seeds: list[int], case_limit=None):
    frame = FormalFrame(split_root, output_root, seeds, case_limit)
    with tracing_context(enabled=False):
        state = FORMAL_GRAPH.invoke({}, context=FormalContext(frame),
                                    config={"recursion_limit": 100000})
    if not state.get("completed"):
        raise RuntimeError("Formal-v2 graph did not complete")
    return frame.manifest
