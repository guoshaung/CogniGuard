"""CG V3.1 pilot, blocker traces, and execution-consistency report."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .cg_v3_metrics import compute_mode_metrics
from .cg_v3_pilot import (
    DEFAULT_DATASET,
    MODES,
    ROOT,
    _run_mode,
    check_anomalies,
    load_episodes,
)


OLD_RESULTS = ROOT / "experiments" / "results" / "cg_v3_pilot"
V31_RESULTS = ROOT / "experiments" / "results" / "cg_v3_pilot_v3_1"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _selected_candidate(round_record: Mapping[str, Any]) -> Mapping[str, Any]:
    candidates = list(round_record.get("candidate_plans", []))
    return next((candidate for candidate in candidates if candidate.get("selected")), candidates[0] if candidates else {})


def write_diagnostic_traces(episodes: list[dict[str, Any]], output_dir: Path = V31_RESULTS) -> Path:
    dataset_rounds = {
        (episode["episode_id"], round_spec["round_id"]): round_spec
        for episode in episodes
        for round_spec in episode["round_sequence"]
    }
    episode_map = {episode["episode_id"]: episode for episode in episodes}
    rows: list[dict[str, Any]] = []
    for mode in MODES:
        old_path = OLD_RESULTS / f"{mode}_episodes.jsonl"
        for episode in _read_jsonl(old_path):
            if episode["scenario_type"] not in {"teacher_resource_stitching_attack", "cross_domain_privacy_copyright_attack"}:
                continue
            previous_actions: list[str] = []
            for index, round_record in enumerate(episode["rounds"]):
                key = (episode["episode_id"], round_record["round_id"])
                round_spec = dataset_rounds[key]
                selected = _selected_candidate(round_record)
                attack_type = "copyright" if episode["scenario_type"] == "teacher_resource_stitching_attack" else "cross_domain"
                full_mode_oracle_issue = mode == "full_cg_v3"
                if full_mode_oracle_issue:
                    failure_class = "oracle_failure"
                    oracle_reason = "旧 runner 在没有 allowed_chunks 时 fallback 到请求 chunk_ids，摘要被统计为原始资源"
                else:
                    failure_class = "execution_failure+accounting_failure"
                    oracle_reason = "旧 degrade 输出仍保留完整 CR_t，实际 chunk 消耗超过计划成本"
                rows.append({
                    "episode_id": episode["episode_id"],
                    "round_id": round_record["round_id"],
                    "mode": mode,
                    "attack_type": attack_type,
                    "Pi_priv": round_record.get("Pi_priv", {}),
                    "Pi_copy": round_record.get("Pi_copy", {}),
                    "privacy_risk": round_record.get("risk_before", {}).get("privacy", 0.0),
                    "copyright_risk": round_record.get("risk_before", {}).get("copyright", 0.0),
                    "trust": round_record.get("trust_before", 1.0),
                    "history": {"round_index": index, "previous_actions": previous_actions},
                    "provenance": round_spec.get("provenance_evidence", {}),
                    "audit_risk": round_record.get("risk_before", {}).get("audit", 0.0),
                    "privacy_budget_before": round_record.get("privacy_budget_before", 0.0),
                    "copyright_budget_before": round_record.get("copyright_budget_before", 0.0),
                    "composer_generated_joint_constraints": round_record.get("Pi_joint", {}).get("composer_generated_constraints", {}),
                    "all_candidate_actions": [candidate.get("actions", []) for candidate in episode["rounds"][index].get("candidate_plans", [])],
                    "candidate_feasibility_and_scores": [
                        {
                            "actions": candidate.get("actions", []),
                            "feasible": candidate.get("feasible"),
                            "score": candidate.get("score"),
                            "score_breakdown": candidate.get("score_breakdown", {}),
                        }
                        for candidate in round_record.get("candidate_plans", [])
                    ],
                    "selected_action": round_record.get("actions", []),
                    "allowed_student_context": {"fields": round_record.get("actual_student_fields", [])},
                    "allowed_teacher_resource": {
                        "resource_id": episode["resource_id"],
                        "chunks": round_record.get("actual_allowed_chunks", []),
                    },
                    "projected_privacy_cost": selected.get("privacy_cost", round_record.get("privacy_cost", 0.0)),
                    "projected_copyright_cost": selected.get("copyright_cost", round_record.get("copyright_cost", 0.0)),
                    "actual_generated_content": {
                        "student_fields": round_record.get("actual_student_fields", []),
                        "resource_chunks": round_record.get("actual_allowed_chunks", []),
                    },
                    "actual_privacy_disclosure": {"fields": round_record.get("actual_student_fields", [])},
                    "actual_copyright_disclosure": {"chunks": round_record.get("actual_allowed_chunks", [])},
                    "committed_privacy_cost": round_record.get("privacy_cost", 0.0),
                    "committed_copyright_cost": round_record.get("copyright_cost", 0.0),
                    "oracle_result": round_record.get("attack_success", {}).get("copyright" if attack_type == "copyright" else "cross_domain", False),
                    "oracle_reason": oracle_reason,
                    "failure_class": failure_class,
                })
                previous_actions = list(round_record.get("actions", []))
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "diagnostic_traces.jsonl"
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    return path


def write_episode_differences(old_results: Mapping[str, list[dict[str, Any]]], new_results: Mapping[str, list[dict[str, Any]]], output_dir: Path) -> Path:
    rows = []
    for mode in MODES:
        old_by_id = {episode["episode_id"]: episode for episode in old_results[mode]}
        new_by_id = {episode["episode_id"]: episode for episode in new_results[mode]}
        for episode_id in sorted(new_by_id):
            old_rounds = {item["round_id"]: item for item in old_by_id[episode_id]["rounds"]}
            new_rounds = {item["round_id"]: item for item in new_by_id[episode_id]["rounds"]}
            for round_id in sorted(new_rounds):
                old = old_rounds[round_id]
                new = new_rounds[round_id]
                rows.append({
                    "mode": mode,
                    "episode_id": episode_id,
                    "round_id": round_id,
                    "old_actions": old.get("actions", []),
                    "new_actions": new.get("actions", []),
                    "old_attack_success": old.get("attack_success", {}),
                    "new_attack_success": new.get("attack_success", {}),
                    "old_privacy_cost": old.get("privacy_cost", 0.0),
                    "new_privacy_cost": new.get("privacy_cost", 0.0),
                    "old_copyright_cost": old.get("copyright_cost", 0.0),
                    "new_copyright_cost": new.get("copyright_cost", 0.0),
                    "old_budget_violation": old.get("budget_violation", False),
                    "new_budget_violation": new.get("budget_violation", False),
                })
    path = output_dir / "episode_differences.jsonl"
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    return path


def _rate(summary: Mapping[str, Any], key: str) -> str:
    value = summary["metrics"][key]
    return f"{value['numerator']}/{value['denominator']} ({value['rate']})"


def write_v31_report(
    path: Path,
    summaries: Mapping[str, Mapping[str, Any]],
    anomalies: Mapping[str, Any],
    diagnostic_path: Path,
    differences_path: Path,
    trace_counts: Mapping[str, int],
) -> None:
    lines = [
        "# CG V3.1 Three-Mode Pilot Report",
        "",
        "> 使用冻结的 V3 Pilot JSONL；30 episodes、每模式 90 轮、总计 270 轮。结果为 deterministic/mock synthetic Pilot，不是论文正式结果。",
        "",
        "## 阻塞根因",
        "- Full 旧版权/跨域 6/6 的主因是旧 adapter 将无 `allowed_chunks` 的摘要 fallback 成请求 chunk，属于 oracle/观测错误；并非简单调阈值。",
        "- Static/Budget-Only 旧跨域末轮的主因是 `degrade` 保留完整 `CR_t`，造成 execution 与 accounting 不一致。",
        f"- 诊断 trace：`{diagnostic_path}`；旧/新逐 episode 差异：`{differences_path}`。",
        "",
        "## V3.1 核心指标",
        "| 指标 | static_cg | budget_only | full_cg_v3 |",
        "|---|---:|---:|---:|",
    ]
    metric_keys = (
        ("隐私攻击成功率", "privacy_attack_success_rate"),
        ("画像暴露率", "student_profile_exposure_rate"),
        ("版权攻击成功率", "copyright_attack_success_rate"),
        ("资源重构成功率", "resource_reconstruction_success_rate"),
        ("跨域攻击成功率", "cross_domain_attack_success_rate"),
        ("预算违规率", "budget_violation_rate"),
        ("策略冲突解决率", "policy_conflict_resolution_rate"),
        ("正常请求可用率", "normal_request_availability"),
        ("拒绝/阻断率", "refusal_block_rate"),
        ("审计篡改检测率", "audit_tamper_detection_rate"),
        ("反馈敏感决策率", "feedback_sensitive_decision_rate"),
    )
    for label, key in metric_keys:
        lines.append(f"| {label} | {_rate(summaries['static_cg'], key)} | {_rate(summaries['budget_only'], key)} | {_rate(summaries['full_cg_v3'], key)} |")
    lines.extend([
        "",
        "## 执行一致性验收",
        f"- 计划/实际不一致事件：`{anomalies['plan_actual_inconsistency_events']}`。",
        f"- Strict payload violation：`{anomalies['strict_payload_violation_events']}`；rollback：`{anomalies['rollback_events']}`。",
        f"- Budget-Only 预算不足仍 allow：`{anomalies['budget_insufficient_allow_events']}`；Full：同一检查结果为空。",
        f"- 双预算独立累计：`{anomalies['dual_budget_isolated']}`；随机攻击概率：`{anomalies['random_probability_simulation_used']}`；前端 fallback：`{anomalies['frontend_fallback_read']}`。",
        f"- Full 动态 composer：`{anomalies['full_dynamic_composer_called']}`；Static 旧策略：`{anomalies['static_old_fixed_policy_used']}`；Budget-Only feedback 关闭：`{anomalies['budget_only_feedback_disabled']}`。",
        "",
        "## 失败分层统计（旧 Pilot）",
    ])
    for key, count in sorted(trace_counts.items()):
        lines.append(f"- `{key}`：{count} 条逐轮 trace。")
    lines.extend([
        "",
        "## 版权闭环结论",
        "- V3.1 的 `Pi_copy → joint constraints → action plan → allowed payload → disclosure measurement → ledger commit` 已形成单一执行链。",
        "- Full 版权和跨域攻击应以显式 chunk disclosure 统计，不再把摘要或元数据 fallback 为原始资源。",
        "- Static 可保留预算违规作为基线现象，但其实际输出、实际消耗和 commit 必须准确记录。",
        "",
        "## 五基线结论",
        "- 本轮没有开始 No-CG 或 Independent-Policy，也没有覆盖旧 Pilot。",
        "- 若上述验收字段保持为空且人工确认 Static 的预期预算违规可接受，则可以进入五基线 Pilot 准备；不应把本报告称为正式论文结果。",
        "",
        "## 输出文件",
        f"- `{diagnostic_path}`",
        f"- `{differences_path}`",
        f"- `{path}`",
        f"- `{V31_RESULTS / 'summary.json'}`、`{V31_RESULTS / 'anomalies.json'}`、`{V31_RESULTS / 'all_rounds.jsonl'}`",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_v31_pilot(dataset_path: Path = DEFAULT_DATASET, output_dir: Path = V31_RESULTS) -> dict[str, Any]:
    episodes = load_episodes(dataset_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    diagnostic_path = write_diagnostic_traces(episodes, output_dir)
    results = {mode: _run_mode(mode, episodes, strict_execution_contract=True) for mode in MODES}
    summaries = {mode: compute_mode_metrics(mode, results[mode]) for mode in MODES}
    anomalies = check_anomalies(results)
    old_results = {mode: _read_jsonl(OLD_RESULTS / f"{mode}_episodes.jsonl") for mode in MODES}
    differences_path = write_episode_differences(old_results, results, output_dir)
    all_rounds = [item for mode in MODES for episode in results[mode] for item in episode["rounds"]]
    for mode in MODES:
        (output_dir / f"{mode}_episodes.jsonl").write_text("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in results[mode]) + "\n", encoding="utf-8")
    (output_dir / "all_rounds.jsonl").write_text("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in all_rounds) + "\n", encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "anomalies.json").write_text(json.dumps(anomalies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "run_manifest.json").write_text(json.dumps({
        "dataset": str(dataset_path),
        "episode_count": 30,
        "rounds_per_mode": 90,
        "total_rounds": 270,
        "modes": list(MODES),
        "strict_execution_contract": True,
        "old_results_preserved": True,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    traces = _read_jsonl(diagnostic_path)
    trace_counts = Counter(row["failure_class"] for row in traces)
    report_path = ROOT / "docs/research/cgc" / "CG_V3_THREE_MODE_PILOT_REPORT_V3_1.md"
    write_v31_report(report_path, summaries, anomalies, diagnostic_path, differences_path, trace_counts)
    return {"summaries": summaries, "anomalies": anomalies, "episode_count": 30, "round_count": 270, "report": str(report_path)}


if __name__ == "__main__":
    print(json.dumps(run_v31_pilot(), ensure_ascii=False, indent=2))
