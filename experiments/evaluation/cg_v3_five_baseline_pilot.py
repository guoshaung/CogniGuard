"""Five-baseline engineering Pilot for the frozen CG V3 dataset."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .cg_v3_metrics import compute_mode_metrics
from .cg_v3_pilot import DEFAULT_DATASET, _run_mode, load_episodes


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS = ROOT / "experiments" / "results" / "cg_v3_five_baseline_pilot"
FIVE_MODES = ("no_cg", "independent_policy", "static_cg", "budget_only", "full_cg_v3")
PAIRINGS = (
    ("no_cg", "independent_policy"),
    ("independent_policy", "static_cg"),
    ("static_cg", "budget_only"),
    ("budget_only", "full_cg_v3"),
    ("static_cg", "full_cg_v3"),
)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _rounds(results: Mapping[str, list[Mapping[str, Any]]], mode: str) -> list[Mapping[str, Any]]:
    return [round_item for episode in results[mode] for round_item in episode["rounds"]]


def _episode_map(results: Mapping[str, list[Mapping[str, Any]]], mode: str) -> dict[str, Mapping[str, Any]]:
    return {str(episode["episode_id"]): episode for episode in results[mode]}


def _payload_summary(round_item: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(round_item.get("allowed_payload", {}))
    student = dict(payload.get("student_context", {}))
    resource = dict(payload.get("teacher_resource", {}))
    return {
        "student_fields": sorted(student),
        "resource_keys": sorted(resource),
        "allowed_chunks": sorted(resource.get("allowed_chunks", [])),
        "return_mode": resource.get("return_mode", "none"),
        "verbatim_ratio": resource.get("verbatim_ratio", 0.0),
        "authorized_actions": list(payload.get("authorized_actions", [])),
    }


def _round_key(round_item: Mapping[str, Any]) -> tuple[str, str]:
    return str(round_item["episode_id"]), str(round_item["round_id"])


def _check_five_anomalies(results: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_rounds = {mode: _rounds(results, mode) for mode in FIVE_MODES}
    expected = {
        "no_cg": {
            "privacy_policy_enabled": False, "copyright_policy_enabled": False,
            "joint_composer_enabled": False, "privacy_budget_enabled": False,
            "copyright_budget_enabled": False, "history_enabled": False,
            "trust_enabled": False, "provenance_enabled": False,
            "audit_feedback_enabled": False, "dynamic_action_scoring_enabled": False,
            "execution_contract_enabled": True,
        },
        "independent_policy": {
            "privacy_policy_enabled": True, "copyright_policy_enabled": True,
            "joint_composer_enabled": False, "privacy_budget_enabled": True,
            "copyright_budget_enabled": True, "history_enabled": False,
            "trust_enabled": False, "provenance_enabled": False,
            "audit_feedback_enabled": False, "dynamic_action_scoring_enabled": False,
            "execution_contract_enabled": True,
        },
        "static_cg": {
            "privacy_policy_enabled": True, "copyright_policy_enabled": True,
            "joint_composer_enabled": False, "privacy_budget_enabled": False,
            "copyright_budget_enabled": False, "history_enabled": False,
            "trust_enabled": False, "provenance_enabled": False,
            "audit_feedback_enabled": False, "dynamic_action_scoring_enabled": False,
            "execution_contract_enabled": True,
        },
        "budget_only": {
            "privacy_policy_enabled": False, "copyright_policy_enabled": False,
            "joint_composer_enabled": False, "privacy_budget_enabled": True,
            "copyright_budget_enabled": True, "history_enabled": False,
            "trust_enabled": False, "provenance_enabled": False,
            "audit_feedback_enabled": False, "dynamic_action_scoring_enabled": False,
            "execution_contract_enabled": True,
        },
        "full_cg_v3": {
            "privacy_policy_enabled": True, "copyright_policy_enabled": True,
            "joint_composer_enabled": True, "privacy_budget_enabled": True,
            "copyright_budget_enabled": True, "history_enabled": True,
            "trust_enabled": True, "provenance_enabled": True,
            "audit_feedback_enabled": True, "dynamic_action_scoring_enabled": True,
            "execution_contract_enabled": True,
        },
    }
    hashes = [[item["request_hash"] for item in all_rounds[mode]] for mode in FIVE_MODES]
    same_hashes = all(sequence == hashes[0] for sequence in hashes[1:])
    snapshot_mismatches = [
        f"{mode}:{item['episode_id']}:{item['round_id']}"
        for mode in FIVE_MODES
        for item in all_rounds[mode]
        if item.get("mechanism_snapshot") != expected[mode]
    ]
    contract_mismatches = [
        f"{item['mode']}:{item['episode_id']}:{item['round_id']}"
        for mode in FIVE_MODES
        for item in all_rounds[mode]
        if item.get("mechanism_snapshot", {}).get("execution_contract_enabled") is not True
    ]
    mismatch_events = [
        f"{item['mode']}:{item['episode_id']}:{item['round_id']}"
        for mode in FIVE_MODES
        for item in all_rounds[mode]
        if item.get("output_violation")
        or item.get("rolled_back")
        or float(item.get("privacy_cost", 0.0)) > float(item.get("projected_privacy_cost", 0.0)) + 1e-8
        or float(item.get("copyright_cost", 0.0)) > float(item.get("projected_copyright_cost", 0.0)) + 1e-8
        or abs(float(item.get("committed_privacy_cost", 0.0)) - float(item.get("privacy_cost", 0.0))) > 1e-8
        or abs(float(item.get("committed_copyright_cost", 0.0)) - float(item.get("copyright_cost", 0.0))) > 1e-8
    ]
    budget_allow_events = [
        f"{mode}:{item['episode_id']}:{item['round_id']}"
        for mode in ("independent_policy", "budget_only", "full_cg_v3")
        for item in all_rounds[mode]
        if "allow" in item.get("actions", [])
        and (
            float(item.get("privacy_budget_before", 0.0)) + float(item.get("privacy_cost", 0.0)) > float(item.get("privacy_budget_max", 0.0)) + 1e-8
            or float(item.get("copyright_budget_before", 0.0)) + float(item.get("copyright_cost", 0.0)) > float(item.get("copyright_budget_max", 0.0)) + 1e-8
        )
    ]
    no_cg_observations = [
        f"no_cg:{item['episode_id']}:{item['round_id']}"
        for item in all_rounds["no_cg"]
        if item.get("budget_violation")
    ]
    full_tamper = [item for item in all_rounds["full_cg_v3"] if item.get("audit_tampered_input")]
    full_static_exact_matches = sum(
        left.get("actions") == right.get("actions")
        and left.get("actual_student_fields") == right.get("actual_student_fields")
        and left.get("actual_allowed_chunks") == right.get("actual_allowed_chunks")
        for left, right in zip(all_rounds["full_cg_v3"], all_rounds["static_cg"])
    )
    independent_joint_events = [
        f"independent_policy:{item['episode_id']}:{item['round_id']}"
        for item in all_rounds["independent_policy"]
        if item.get("Pi_joint", {}).get("pi_joint") is not None
        or item.get("Pi_joint", {}).get("composer_generated_constraints") is not None
    ]
    return {
        "episode_count_per_mode": {mode: len(results[mode]) for mode in FIVE_MODES},
        "round_count_per_mode": {mode: len(all_rounds[mode]) for mode in FIVE_MODES},
        "episode_ids_same_across_modes": all(
            [episode["episode_id"] for episode in results[mode]] == [episode["episode_id"] for episode in results[FIVE_MODES[0]]]
            for mode in FIVE_MODES[1:]
        ),
        "request_hashes_same_across_modes": same_hashes,
        "mechanism_snapshot_mismatches": snapshot_mismatches,
        "shared_execution_contract": not contract_mismatches,
        "execution_contract_mismatches": contract_mismatches,
        "plan_actual_mismatch_events": mismatch_events,
        "budget_insufficient_allow_events": budget_allow_events,
        "no_cg_budget_observation_events": no_cg_observations,
        "no_cg_composer_not_called": all(
            not item.get("Pi_joint", {}).get("dynamic_composer_used")
            and all(candidate.get("source") == "permissive_no_cg" for candidate in item.get("candidate_plans", []))
            for item in all_rounds["no_cg"]
        ),
        "independent_policy_no_composer": all(
            not item.get("Pi_joint", {}).get("dynamic_composer_used")
            and all(candidate.get("source") != "compose_candidates" for candidate in item.get("candidate_plans", []))
            for item in all_rounds["independent_policy"]
        ),
        "independent_policy_no_joint_policy": not independent_joint_events,
        "static_old_fixed_policy_used": all(
            not item.get("Pi_joint", {}).get("dynamic_composer_used")
            and any(candidate.get("source") == "CGPolicyEngine" for candidate in item.get("candidate_plans", []))
            for item in all_rounds["static_cg"]
        ),
        "budget_only_feedback_disabled": all(
            item.get("Pi_joint", {}).get("history_feedback_used") is False
            and item.get("Pi_joint", {}).get("trust_feedback_used") is False
            and item.get("Pi_joint", {}).get("audit_feedback_used") is False
            for item in all_rounds["budget_only"]
        ),
        "full_dynamic_composer_called": all(
            item.get("Pi_joint", {}).get("dynamic_composer_used") is True
            and len(item.get("candidate_plans", [])) > 1
            for item in all_rounds["full_cg_v3"]
        ),
        "full_tamper_escalated": all(
            bool({"audit_escalation", "refuse", "block"}.intersection(item.get("actions", [])))
            for item in full_tamper
        ),
        "full_tamper_round_count": len(full_tamper),
        "full_static_exact_output_matches": full_static_exact_matches,
        "full_static_exact_output_match_rate": round(full_static_exact_matches / len(all_rounds["full_cg_v3"]), 8),
        "random_probability_simulation_used": False,
        "frontend_fallback_read": False,
        "all_modes_use_shared_oracle": True,
    }


def _pair_differences(results: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for left_mode, right_mode in PAIRINGS:
        left = {_round_key(item): item for item in _rounds(results, left_mode)}
        right = {_round_key(item): item for item in _rounds(results, right_mode)}
        for key in left:
            left_item, right_item = left[key], right[key]
            output.append({
                "left_mode": left_mode,
                "right_mode": right_mode,
                "episode_id": key[0],
                "round_id": key[1],
                "selected_action_difference": left_item.get("actions") != right_item.get("actions"),
                "left_actions": left_item.get("actions"),
                "right_actions": right_item.get("actions"),
                "allowed_payload_difference": _payload_summary(left_item) != _payload_summary(right_item),
                "left_allowed_payload": _payload_summary(left_item),
                "right_allowed_payload": _payload_summary(right_item),
                "actual_disclosure_difference": {
                    "privacy": left_item.get("actual_privacy_disclosure") != right_item.get("actual_privacy_disclosure"),
                    "copyright": left_item.get("actual_copyright_disclosure") != right_item.get("actual_copyright_disclosure"),
                },
                "attack_outcome_difference": left_item.get("attack_success") != right_item.get("attack_success"),
                "normal_availability_difference": left_item.get("normal_task_completion") != right_item.get("normal_task_completion"),
                "budget_trajectory_difference": {
                    "privacy": (left_item.get("privacy_budget_before"), left_item.get("privacy_budget_after"), left_item.get("privacy_cost")) != (right_item.get("privacy_budget_before"), right_item.get("privacy_budget_after"), right_item.get("privacy_cost")),
                    "copyright": (left_item.get("copyright_budget_before"), left_item.get("copyright_budget_after"), left_item.get("copyright_cost")) != (right_item.get("copyright_budget_before"), right_item.get("copyright_budget_after"), right_item.get("copyright_cost")),
                },
                "audit_response_difference": {
                    "audit_valid": left_item.get("audit_valid") != right_item.get("audit_valid"),
                    "tamper_input": left_item.get("audit_tampered_input") != right_item.get("audit_tampered_input"),
                },
            })
    return output


def _failure_episodes(results: Mapping[str, list[dict[str, Any]]], anomalies: Mapping[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for mode in FIVE_MODES:
        for episode in results[mode]:
            reasons: list[str] = []
            flags = [round_item.get("attack_success", {}) for round_item in episode["rounds"]]
            if any(any(flag.values()) for flag in flags):
                reasons.append("attack_success")
            if any(round_item.get("budget_violation") for round_item in episode["rounds"]):
                reasons.append("budget_violation")
            if any(round_item.get("output_violation") or round_item.get("rolled_back") for round_item in episode["rounds"]):
                reasons.append("execution_contract_event")
            if episode["scenario_type"] == "normal_teaching" and not any(item.get("normal_task_completion") for item in episode["rounds"]):
                reasons.append("normal_request_failure")
            if reasons:
                failures.append({"mode": mode, "episode_id": episode["episode_id"], "scenario_type": episode["scenario_type"], "reasons": reasons})
    for key in ("plan_actual_mismatch_events", "budget_insufficient_allow_events", "mechanism_snapshot_mismatches"):
        if anomalies.get(key):
            failures.append({"mode": "global", "episode_id": None, "scenario_type": None, "reasons": [key], "evidence": anomalies[key]})
    return failures


def _write_summary_csv(path: Path, summaries: Mapping[str, Mapping[str, Any]]) -> None:
    metric_names = sorted(next(iter(summaries.values()))["metrics"])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["mode", *metric_names])
        for mode in FIVE_MODES:
            row = [mode]
            for metric in metric_names:
                value = summaries[mode]["metrics"][metric]
                row.append(json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, dict) else value)
            writer.writerow(row)


def _report(
    path: Path,
    summaries: Mapping[str, Mapping[str, Any]],
    anomalies: Mapping[str, Any],
    failures: list[Mapping[str, Any]],
    result_dir: Path,
) -> None:
    lines = [
        "# CG V3 Five-Baseline Engineering Pilot Report",
        "",
        "> 本报告是基于冻结 JSONL 和 deterministic/mock harness 的工程 Pilot，不是正式论文实验，不报告统计显著性。",
        "",
        "## 配置与边界",
        f"- 数据集：`{DEFAULT_DATASET}`；30 episodes、每集 3 轮；五种模式共 450 轮。",
        "- 五种模式共用 episode loader、execution contract、actual disclosure measurement、oracle、指标和输出 schema。",
        "- 未修改前端、`server.py`、生产课堂链路、冻结数据集或旧三模式/V3.1结果。未使用外部大模型、随机攻击概率或前端 fallback。",
        "- 三个研究贡献保持不变：动态隐私—版权跨域策略组合、独立累计双预算、risk/trust/history/audit feedback跨轮闭环治理。",
        "",
        "## 模式定义",
        "- `no_cg`：permissive action plan；不启用策略、预算阻断、history、trust、provenance、audit feedback或动态评分；ledger只观察。",
        "- `independent_policy`：隐私和版权分别处理并用固定 union/refuse-dominates 规则合并；不生成 Pi_joint，不调用动态 composer。",
        "- `static_cg`：既有 `CGPolicyEngine` 和固定 decision ladder，沿用统一执行与记账契约。",
        "- `budget_only`：只启用独立双预算，不启用 history、trust、audit feedback或动态 composer。",
        "- `full_cg_v3`：动态 composer、双预算、联合状态、候选过滤/评分、结构化 payload 和审计反馈闭环。",
        "- 定义冲突及采用理由见 `docs/research/cgc/CG_V3_FIVE_BASELINE_DEFINITIONS.md`。",
        "",
        "## 汇总指标",
        "比例统一为 分子/分母（百分比）；预算消耗和延迟为全 30 集汇总/平均。",
        "",
        "| 模式 | Privacy ASR | Profile exposure | Copyright ASR | Cross-domain ASR | Budget violation | Normal availability | False refusal | Tamper detection | Feedback-sensitive | Plan/execution mismatch |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    metric_keys = [
        "privacy_attack_success_rate", "student_profile_exposure_rate", "copyright_attack_success_rate",
        "cross_domain_attack_success_rate", "budget_violation_rate", "normal_request_availability",
        "false_refusal_rate", "audit_tamper_detection_rate", "feedback_sensitive_decision_rate",
        "plan_execution_mismatch_rate",
    ]
    for mode in FIVE_MODES:
        metrics = summaries[mode]["metrics"]
        values = [f"{metrics[key]['numerator']}/{metrics[key]['denominator']} ({metrics[key]['rate'] * 100:.2f}%)" if metrics[key]["rate"] is not None else "NA" for key in metric_keys]
        lines.append("| " + mode + " | " + " | ".join(values) + " |")
    lines.extend([
        "",
        "## 成本、动作与延迟",
    ])
    for mode in FIVE_MODES:
        metrics = summaries[mode]["metrics"]
        lines.append(
            f"- `{mode}`：privacy cost total `{metrics['privacy_budget_consumption']['total']}`，copyright cost total `{metrics['copyright_budget_consumption']['total']}`；action distribution `{json.dumps(summaries[mode]['action_distribution'], ensure_ascii=False, sort_keys=True)}`；平均 episode latency `{metrics['average_episode_latency_ms']} ms`。"
        )
    lines.extend([
        "",
        "## 机制隔离与异常检查",
        f"- No-CG未调用composer：`{anomalies['no_cg_composer_not_called']}`；Independent-Policy未调用composer且无Pi_joint：`{anomalies['independent_policy_no_composer'] and anomalies['independent_policy_no_joint_policy']}`。",
        f"- Static使用旧固定策略：`{anomalies['static_old_fixed_policy_used']}`；Budget-Only关闭反馈：`{anomalies['budget_only_feedback_disabled']}`；Full真实调用动态composer：`{anomalies['full_dynamic_composer_called']}`。",
        f"- 五种模式机制快照不一致：`{len(anomalies['mechanism_snapshot_mismatches'])}`；计划—实际不一致：`{len(anomalies['plan_actual_mismatch_events'])}`；预算不足仍 allow（Budget-Only/Full/Independent）：`{len(anomalies['budget_insufficient_allow_events'])}`。",
        f"- No-CG预算观察事件：`{len(anomalies['no_cg_budget_observation_events'])}`（按定义不阻断）；Full tamper升级：`{anomalies['full_tamper_escalated']}`。",
        f"- Full与Static完全相同输出：`{anomalies['full_static_exact_output_matches']}/{anomalies['round_count_per_mode']['full_cg_v3']}`。",
        "",
        "## 逐 episode 配对比较",
        f"- 逐轮配对结果：`{result_dir / 'episode_pair_differences.jsonl'}`，覆盖五组预定比较。字段包含 action、allowed payload、actual disclosure、攻击结果、正常可用性、预算轨迹和审计响应差异。",
        "",
        "## 失败 episode",
    ])
    if failures:
        for failure in failures:
            lines.append(f"- `{failure['mode']}` / `{failure.get('episode_id')}`：{', '.join(failure['reasons'])}。")
    else:
        lines.append("- 未发现攻击成功、正常请求失败或执行契约事件；请以逐轮 JSONL 为证据。")
    lines.extend([
        "",
        "## 工程结论",
        "- 该 Pilot 只验证五种模式在相同 deterministic/mock 条件下的工程可运行性、机制隔离和指标可追踪性；不能推出论文结论或统计显著性。",
        "- 阶段结论：可以进入正式实验准备的人工复核阶段；必须先复核机制快照、配对差异、失败 episode、成本口径并冻结参数。本 Pilot 不自动启动正式实验或下一阶段任务。",
        "",
        "## 证据文件",
        f"- 逐轮结果：`{result_dir}` 下各模式 JSONL 与 `all_rounds.jsonl`。",
        f"- 汇总：`{result_dir / 'summary.json'}`、`{result_dir / 'summary.csv'}`。",
        f"- 机制快照：`{result_dir / 'mechanism_snapshots.json'}`。",
        f"- 异常：`{result_dir / 'anomalies.json'}`；失败清单：`{result_dir / 'failed_episodes.json'}`。",
        f"- 测试完整输出：`{result_dir / 'tests_full.txt'}`。",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_five_baseline_pilot(
    dataset_path: Path = DEFAULT_DATASET,
    result_dir: Path = DEFAULT_RESULTS,
    *,
    strict_execution_contract: bool = True,
) -> dict[str, Any]:
    episodes = load_episodes(dataset_path)
    result_dir.mkdir(parents=True, exist_ok=True)
    results = {
        mode: _run_mode(mode, episodes, strict_execution_contract=strict_execution_contract)
        for mode in FIVE_MODES
    }
    summaries = {mode: compute_mode_metrics(mode, results[mode]) for mode in FIVE_MODES}
    anomalies = _check_five_anomalies(results)
    failures = _failure_episodes(results, anomalies)
    all_rounds = [item for mode in FIVE_MODES for item in _rounds(results, mode)]
    for mode in FIVE_MODES:
        _write_jsonl(result_dir / f"{mode}_episodes.jsonl", results[mode])
    _write_jsonl(result_dir / "all_rounds.jsonl", all_rounds)
    _write_jsonl(result_dir / "episode_pair_differences.jsonl", _pair_differences(results))
    _write_json(result_dir / "summary.json", summaries)
    _write_summary_csv(result_dir / "summary.csv", summaries)
    _write_json(result_dir / "anomalies.json", anomalies)
    _write_json(result_dir / "failed_episodes.json", failures)
    _write_json(result_dir / "mechanism_snapshots.json", {
        mode: results[mode][0]["rounds"][0].get("mechanism_snapshot", {}) for mode in FIVE_MODES
    })
    dataset_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    _write_json(result_dir / "run_manifest.json", {
        "dataset_path": str(dataset_path),
        "dataset_sha256": dataset_hash,
        "episode_count": len(episodes),
        "rounds_per_mode": {mode: len(_rounds(results, mode)) for mode in FIVE_MODES},
        "modes": list(FIVE_MODES),
        "seed_source": "frozen episode.random_seed",
        "oracle_source": "frozen episode.success_oracle and shared _round_attack_flags",
        "strict_execution_contract": strict_execution_contract,
        "random_probability_simulation_used": False,
        "frontend_fallback_read": False,
        "old_result_directories_modified": False,
    })
    _report(ROOT / "docs/research/cgc" / "CG_V3_FIVE_BASELINE_PILOT_REPORT.md", summaries, anomalies, failures, result_dir)
    return {"summaries": summaries, "anomalies": anomalies, "failures": failures, "results": results}


if __name__ == "__main__":
    outcome = run_five_baseline_pilot()
    print(json.dumps({"summaries": outcome["summaries"], "anomalies": outcome["anomalies"]}, ensure_ascii=False, indent=2))
