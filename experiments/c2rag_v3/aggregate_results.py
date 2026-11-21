from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import math
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from .core import C2RAGResult
from .dataset import load_isolated_dev_sessions
from .evaluator import OfflineEvaluator, SemanticEvaluator


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _result_from_row(row: dict[str, Any]) -> C2RAGResult:
    names = {
        "session_id", "round_id", "method", "query", "selected_chunks", "planned_action", "executed_action",
        "mismatch_reason", "allowed_evidence", "generated_answer", "released_answer", "actual_disclosure",
        "estimated_cost", "actual_cost", "committed_cost", "plan_execution_match", "refusal", "timings_ms",
        "target_resource_id", "principal_id", "cross_session_linked", "session_cost_before", "session_cost_after",
        "cross_session_cost_before", "cross_session_cost_after", "remaining_budget", "generation_calls",
        "input_tokens", "output_tokens",
    }
    return C2RAGResult(**{name: row[name] for name in names if name in row})


def _rate(method: str, metric: str, numerator: int, denominator: int, **extra: Any) -> dict[str, Any]:
    return {"method": method, "metric": metric, "numerator": numerator, "denominator": denominator, "rate": numerator / denominator if denominator else None, **extra}


def _latency_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    values = sorted(float(row.get("timings_ms", {}).get("total_ms", 0.0)) for row in rows)
    if not values:
        return {"mean_latency_ms": 0.0, "p95_latency_ms": 0.0, "mean_retrieval_ms": 0.0, "mean_generation_ms": 0.0, "mean_posthoc_ms": 0.0}
    return {
        "mean_latency_ms": statistics.mean(values),
        "p95_latency_ms": values[min(len(values) - 1, max(0, math.ceil(0.95 * len(values)) - 1))],
        "mean_retrieval_ms": statistics.mean(float(row.get("timings_ms", {}).get("retrieval_ms", 0.0)) for row in rows),
        "mean_generation_ms": statistics.mean(float(row.get("timings_ms", {}).get("generation_ms", 0.0)) for row in rows),
        "mean_posthoc_ms": 0.0,
    }


def aggregate(output: Path, source_root: Path, fixture_root: Path, report_path: Path, readiness_path: Path) -> dict[str, Any]:
    raw_rows = _read_jsonl(output / "raw_results.jsonl")
    rounds = max((int(row["round_id"]) for row in raw_rows), default=4)
    sessions = load_isolated_dev_sessions(source_root, fixture_root, rounds=rounds)
    hidden = {session.case.case_id: session.case for session in sessions}
    model_manifest = json.loads((output / "model_manifest.json").read_text(encoding="utf-8")) if (output / "model_manifest.json").exists() else {}
    dense = model_manifest.get("dense", {})
    semantic = SemanticEvaluator(backend="neural" if not dense.get("fallback", True) else "auto", model_name=dense.get("name", "sentence-transformers/all-MiniLM-L6-v2"), revision=dense.get("revision", "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"), model_path=dense.get("snapshot_path"), device=dense.get("device", "auto"))
    evaluator = OfflineEvaluator(semantic)
    by_session: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        by_session[(str(row["method"]), str(row["case_id"]))].append(row)
        by_method[str(row["method"])].append(row)
    session_metrics: list[dict[str, Any]] = []
    for (method, case_id), rows in sorted(by_session.items()):
        if case_id not in hidden:
            continue
        evaluated = evaluator.evaluate_session(hidden[case_id], [_result_from_row(row) for row in rows])
        evaluated["method"] = method
        session_metrics.append(evaluated)
    _write_jsonl(output / "session_metrics.jsonl", session_metrics)

    metrics: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"total_rounds": len(raw_rows), "total_sessions": len({row["case_id"] for row in raw_rows}), "expected_sessions": len(sessions), "complete_development_run": len({row["case_id"] for row in raw_rows}) == len(sessions), "methods": {}, "semantic_evaluator": semantic.manifest()}
    for method, rows in sorted(by_method.items()):
        session_rows = [row for row in session_metrics if row["method"] == method]
        attack_rows = [row for row in session_rows if row["is_attack"]]
        clean_rows = [row for row in session_rows if not row["is_attack"]]
        latency = _latency_summary(rows)
        round_mismatch = sum(int(not row["plan_execution_match"]) for row in rows)
        session_mismatch = sum(int(row["plan_execution_mismatch"]) for row in session_rows)
        summary["methods"][method] = {"rounds": len(rows), "round_mismatch": round_mismatch, "round_mismatch_rate": round_mismatch / len(rows) if rows else None, "sessions": len(session_rows), "session_mismatch": session_mismatch, "session_mismatch_rate": session_mismatch / len(session_rows) if session_rows else None}
        for metric, group, field in [
            ("direct_copyright_leakage", attack_rows, "direct_copyright_leakage"),
            ("semantic_leakage", attack_rows, "semantic_leakage"),
            ("reconstruction_success", attack_rows, "reconstruction_success"),
            ("normal_session_availability", clean_rows, "normal_available"),
            ("over_refusal", clean_rows, "over_refusal"),
            ("budget_violation", session_rows, "budget_violation"),
            ("session_plan_execution_mismatch", session_rows, "plan_execution_mismatch"),
        ]:
            metrics.append(_rate(method, metric, sum(int(row[field]) for row in group), len(group), **latency))
        metrics.append(_rate(method, "round_plan_execution_mismatch", round_mismatch, len(rows), **latency))
        for field in ["lcs_coverage", "ngram_coverage", "lexical_cosine", "semantic_similarity", "key_knowledge_unit_recovery", "recall_at_1", "recall_at_3", "mrr", "ndcg_at_3", "context_precision", "source_attribution_accuracy", "turn_availability", "reconstruction_auc", "peak_incremental_reconstruction", "final_cumulative_reconstruction"]:
            values = [float(row[field]) for row in session_rows]
            metrics.append({"method": method, "metric": f"mean_{field}", "numerator": None, "denominator": len(values), "rate": statistics.mean(values) if values else None, **latency})
        metrics.append({"method": method, "metric": "mean_actual_copyright_cost", "numerator": None, "denominator": len(rows), "rate": statistics.mean(float(row["actual_cost"]) for row in rows) if rows else 0.0, **latency})
        metrics.append({"method": method, "metric": "generation_calls", "numerator": None, "denominator": len(rows), "rate": sum(int(row.get("generation_calls", 0)) for row in rows), **latency})
    _write_csv(output / "aggregated_metrics.csv", metrics)
    curve_fields = [
        "method", "case_id", "attack_family", "is_attack",
        "cumulative_lcs_by_round", "cumulative_ngram_by_round",
        "cumulative_semantic_by_round", "cumulative_knowledge_units_by_round",
        "incremental_lcs_by_round", "incremental_ngram_by_round",
        "incremental_semantic_by_round", "incremental_knowledge_units_by_round",
        "peak_incremental_reconstruction", "final_cumulative_reconstruction",
        "reconstruction_auc", "query_to_10pct_reconstruction",
        "query_to_25pct_reconstruction", "query_to_50pct_reconstruction",
    ]
    _write_jsonl(output / "cumulative_reconstruction_curves.jsonl", [
        {field: row.get(field) for field in curve_fields} for row in session_metrics
    ])
    (output / "mismatch_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (output / "evaluator_manifest.json").write_text(json.dumps(semantic.manifest() | {"hidden_labels_runtime_access": False, "thresholds_locked": True, "metrics_use_actual_released_output": True, "ndcg": "binary target-resource relevance, log2 discount, per-round macro mean"}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    diagnostics = [{"method": row["method"], "case_id": row["case_id"], "round_id": row["round_id"], "target_resource_id": row.get("target_resource_id", ""), "selected_document_ids": [item.get("document_id") for item in row.get("selected_chunks", [])], "target_hit": any(item.get("document_id") == row.get("target_resource_id") for item in row.get("selected_chunks", []))} for row in raw_rows]
    _write_jsonl(output / "target_retrieval_diagnostics.jsonl", diagnostics)
    ledger = [{"method": row["method"], "case_id": row["case_id"], "session_id": row["session_id"], "principal_id": row.get("principal_id"), "link_group": row.get("link_group"), "session_cost_before": row.get("session_cost_before", 0.0), "session_cost_after": row.get("session_cost_after", 0.0), "cross_session_cost_before": row.get("cross_session_cost_before", 0.0), "cross_session_cost_after": row.get("cross_session_cost_after", 0.0), "current_round_actual_cost": row.get("actual_cost", 0.0), "committed_cost": row.get("committed_cost", 0.0), "remaining_budget": row.get("remaining_budget", 0.0)} for row in raw_rows]
    _write_jsonl(output / "budget_ledger_trace.jsonl", ledger)
    clean_over = {method: {"clean_sessions": sum(1 for row in values if not row["is_attack"]), "over_refusal_sessions": sum(int(row["over_refusal"]) for row in values if not row["is_attack"]), "normal_session_availability": sum(int(row["normal_available"]) for row in values if not row["is_attack"]), "normal_turn_availability_mean": statistics.mean([float(row["turn_availability"]) for row in values if not row["is_attack"]]) if any(not row["is_attack"] for row in values) else 0.0} for method, values in ((method, [row for row in session_metrics if row["method"] == method]) for method in sorted(by_method))}
    (output / "over_refusal_report.json").write_text(json.dumps(clean_over, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    failures = []
    for row in session_metrics:
        reasons = []
        if row["is_attack"] and row["reconstruction_success"]: reasons.append("reconstruction_success")
        if not row["is_attack"] and row["over_refusal"]: reasons.append("clean_over_refusal")
        if row["plan_execution_mismatch"]: reasons.append("plan_execution_mismatch")
        if row["budget_violation"]: reasons.append("budget_violation")
        if reasons: failures.append({"method": row["method"], "case_id": row["case_id"], "attack_family": row["attack_family"], "failure_types": reasons})
    _write_jsonl(output / "failure_cases.jsonl", failures)
    linked = _linked_metrics(by_session, hidden, evaluator)
    _write_jsonl(output / "linked_group_metrics.jsonl", linked)
    _write_reports(output, report_path, readiness_path, summary, failures, linked)
    return {"raw_rows": len(raw_rows), "session_rows": len(session_metrics), "summary": summary, "failure_rows": len(failures), "linked_groups": len(linked)}


def _linked_metrics(by_session: dict[tuple[str, str], list[dict[str, Any]]], hidden: dict[str, Any], evaluator: OfflineEvaluator) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for (_, case_id), rows in by_session.items():
        case = hidden.get(case_id)
        if case and case.link_group:
            groups[(str(rows[0]["method"]), case.link_group)].append(case_id)
    result = []
    for (method, group), case_ids in sorted(groups.items()):
        case_ids.sort()
        rows = [_result_from_row(row) for case_id in case_ids for row in sorted(by_session[(method, case_id)], key=lambda item: int(item["round_id"]))]
        evaluated = evaluator.evaluate_session(hidden[case_ids[0]], rows)
        result.append({"method": method, "link_group": group, "case_ids": case_ids, "session_a_case_id": case_ids[0], "session_b_case_id": case_ids[-1], "combined_reconstruction_success": evaluated["reconstruction_success"], "combined_semantic_similarity": evaluated["semantic_similarity"], "combined_lexical_coverage": evaluated["lcs_coverage"]})
    return result


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_reports(output: Path, report_path: Path, readiness_path: Path, summary: dict[str, Any], failures: list[dict[str, Any]], linked: list[dict[str, Any]]) -> None:
    result_dir = output.as_posix()
    status_line = "完整 development_v5 已完成" if summary.get("complete_development_run") else f"仅完成限量 development_v5：{summary['total_sessions']}/{summary['expected_sessions']} sessions；完整运行未完成"
    lines = ["# C²-RAG V3 Development Pilot V5", "", "## Status", "", f"{status_line}。本轮仅运行 development split，禁止解读为 held-out formal test；V4及更早结果保持不变。所有数字由 `aggregate_results.py` 从 raw trace 生成。", "", "## Design", "", f"{summary['total_sessions']} sessions、最大 {max((v['rounds'] for v in summary['methods'].values()), default=0)} rounds/session、{summary['total_rounds']} 条逐轮记录。target resource 由运行时 resource_id 显式绑定，攻击标签仅由 post-hoc evaluator 读取。", "所有方法共用 BM25、neural dense、RRF 和 cross-encoder base；方法差异只来自已登记的保护机制。", "指标使用最终 released_answer 和真实 selected chunks；计划动作不直接作为攻击判定。", "", "## Mismatch", "", "| method | round mismatch | session mismatch |", "|---|---:|---:|"]
    lines += [f"| {method} | {item['round_mismatch']}/{item['rounds']} | {item['session_mismatch']}/{item['sessions']} |" for method, item in summary["methods"].items()]
    lines += ["", "## Retrieval and accounting", "", "Recall@1/Recall@3/MRR/nDCG@3/Context Precision 见 `aggregated_metrics.csv` 和 `target_retrieval_diagnostics.jsonl`。由于运行时按目标 resource scope 检索，结果应解释为目标绑定下的检索正确性，而不是无条件开放库排名。", "账本同时保存 session cost、cross-session cost、当前轮 actual cost 和 remaining budget；`budget_ledger_trace.jsonl` 可审计是否重复扣费。", "", "## Model and evaluator", "", f"模型与权重状态见 `{result_dir}/model_manifest.json`；独立语义 evaluator 见 `{result_dir}/evaluator_manifest.json`。RAGFort/CanaryRAG 仍为 NOT_RUN，不冒充强外部基线。", "", "## Linked sessions", "", f"共享 principal 的跨 session 组合记录：{len(linked)} 组，详见 `linked_group_metrics.jsonl`。", "", "## Readiness", "", "NOT_READY_FOR_HELD_OUT_FORMAL_TEST；本轮完成后停止。", f"失败案例：{len(failures)}，详见 `{result_dir}/failure_cases.jsonl`。"]
    text = "\n".join(lines) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    readiness_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    readiness_path.write_text("# RUN_READINESS\n\n**NOT_READY_FOR_HELD_OUT_FORMAL_TEST**\n\n- V5 仅使用 development split。\n- 当前仅完成限量真实 Qwen run；完整 development_v5 未完成，不能报告为完整结果。\n- 原因：当前 CPU 环境下 0.5B Qwen 的完整 3888 轮执行为小时级资源开销。\n- RAGFort 和 CanaryRAG 尚未忠实复现。\n- 运行输出、检索诊断、账本和失败证据已冻结在本目录。\n", encoding="utf-8")


def dependency_manifest() -> dict[str, str]:
    names = ["numpy", "scikit-learn", "torch", "transformers", "huggingface-hub"]
    return {name: importlib.metadata.version(name) for name in names if _has_distribution(name)}


def _has_distribution(name: str) -> bool:
    try:
        importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return False
    return True


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
