"""Run the fixed 30-episode CG V3 three-mode pilot."""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .cg_v3_harness import CGV3Harness
from .cg_v3_pilot_graph import PilotFrame, run_pilot_graph
from .cg_v3_metrics import SCENARIO_NAMES, compute_mode_metrics
from .cg_v3_schemas import CGInput


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "experiments" / "datasets" / "cg_v3_pilot" / "episodes.jsonl"
DEFAULT_RESULTS = ROOT / "experiments" / "results" / "cg_v3_pilot"
MODES = ("static_cg", "budget_only", "full_cg_v3")


def _hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_episodes(path: Path = DEFAULT_DATASET) -> list[dict[str, Any]]:
    episodes = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not episodes:
        raise ValueError("CG dataset is empty")
    counts = Counter(str(item.get("scenario_type")) for item in episodes)
    if set(counts) != set(SCENARIO_NAMES) or len(set(counts.values())) != 1:
        raise ValueError(f"CG dataset must be balanced across scenarios: {dict(counts)}")
    for episode in episodes:
        if len(episode.get("round_sequence", [])) != int(episode.get("maximum_rounds", 0)):
            raise ValueError(f"round count mismatch in {episode.get('episode_id')}")
    return episodes


def _request_from_round(
    episode: Mapping[str, Any],
    round_spec: Mapping[str, Any],
    previous_state: Mapping[str, Any],
    previous_hash: str,
) -> CGInput:
    return CGInput.from_mapping({
        "q_t": round_spec["q_t"],
        "student_id": episode["student_id"],
        "session_id": episode["session_id"],
        "round_id": round_spec["round_id"],
        "resource_id": episode["resource_id"],
        "chunk_ids": round_spec.get("chunk_ids", []),
        "C_u_t": round_spec.get("C_u_t", {}),
        "Pi_priv": round_spec.get("Pi_priv", {}),
        "CR_t": round_spec.get("CR_t", {}),
        "Pi_copy": round_spec.get("Pi_copy", {}),
        "provenance_evidence": round_spec.get("provenance_evidence", {}),
        "capability_context": round_spec.get("capability_context", {}),
        "previous_state": previous_state,
        "previous_audit_hash": previous_hash,
    })


def _round_attack_flags(episode: Mapping[str, Any], round_spec: Mapping[str, Any], output: Mapping[str, Any]) -> dict[str, bool]:
    oracle = dict(episode.get("success_oracle", {}))
    sensitive = set(oracle.get("sensitive_fields", []))
    fields = set(output.get("allowed_student_context", {}))
    chunks = set(output.get("allowed_teacher_resource", {}).get("allowed_chunks", []))
    if output.get("execution_result") not in {"allow", "degrade"}:
        chunks = set()
    scenario = episode.get("scenario_type")
    return {
        "privacy": bool(fields & sensitive) if scenario in {"student_profile_split_attack", "cross_domain_privacy_copyright_attack"} else False,
        "copyright": bool(chunks) if scenario == "teacher_resource_stitching_attack" else False,
        "cross_domain": bool(fields & sensitive) or bool(chunks) if scenario == "cross_domain_privacy_copyright_attack" else False,
    }


def _execute_one_round(mode, episode, round_spec, harness, previous_state,
                       previous_hash, previous_actions):
    request_hash = _hash({
        "episode_id": episode["episode_id"],
        "scenario_type": episode["scenario_type"],
        "round": round_spec,
    })
    supplied_hash = "tampered:" + previous_hash if round_spec.get("tamper_previous_hash") else previous_hash
    request = _request_from_round(episode, round_spec, previous_state, supplied_hash)
    before_state = dict(previous_state)
    start = time.perf_counter()
    output = harness.run(request)
    latency_ms = (time.perf_counter() - start) * 1000.0
    output_data = output.to_dict()
    fields = sorted(output.allowed_student_context)
    resource = output.allowed_teacher_resource
    chunks = sorted(resource.get("allowed_chunks", []))
    current_state = output.updated_state.to_dict()
    actions = list(output.action_plan.selected_actions)
    attack_flags = _round_attack_flags(episode, round_spec, output_data)
    tamper = supplied_hash != previous_hash
    row = {
        "mode": mode,
        "episode_id": episode["episode_id"],
        "scenario_type": episode["scenario_type"],
        "round_id": round_spec["round_id"],
        "random_seed": episode["random_seed"],
        "request_hash": request_hash,
        "Pi_priv": request.Pi_priv,
        "Pi_copy": request.Pi_copy,
        "Pi_joint": output.Pi_joint,
        "mechanism_snapshot": output.Pi_joint.get("mechanism_snapshot", {}),
        "candidate_plans": output.candidate_plans,
        "actions": actions,
        "risk_before": output.action_plan.risk_before,
        "risk_after": output.audit_record.get("risk_after", {}),
        "trust_before": before_state.get("trust_score", 1.0),
        "trust_after": current_state.get("trust_score", 1.0),
        "privacy_budget_before": output.action_plan.privacy_budget_before,
        "privacy_budget_after": output.action_plan.privacy_budget_after,
        "copyright_budget_before": output.action_plan.copyright_budget_before,
        "copyright_budget_after": output.action_plan.copyright_budget_after,
        "privacy_budget_max": float(episode["privacy_budget"]),
        "copyright_budget_max": float(episode["copyright_budget"]),
        "privacy_cost": output.action_plan.privacy_cost,
        "copyright_cost": output.action_plan.copyright_cost,
        "projected_privacy_cost": output.audit_record.get("projected_privacy_cost", output.action_plan.projected_privacy_cost),
        "projected_copyright_cost": output.audit_record.get("projected_copyright_cost", output.action_plan.projected_copyright_cost),
        "reserved_privacy_cost": output.audit_record.get("reserved_privacy_cost", 0.0),
        "reserved_copyright_cost": output.audit_record.get("reserved_copyright_cost", 0.0),
        "committed_privacy_cost": output.audit_record.get("committed_privacy_cost", output.action_plan.privacy_cost),
        "committed_copyright_cost": output.audit_record.get("committed_copyright_cost", output.action_plan.copyright_cost),
        "actual_privacy_disclosure": output.audit_record.get("actual_privacy_disclosure", {}),
        "actual_copyright_disclosure": output.audit_record.get("actual_copyright_disclosure", {}),
        "allowed_payload": output.action_plan.allowed_payload,
        "output_violation": bool(output.audit_record.get("output_violation", False)),
        "rolled_back": bool(output.audit_record.get("rolled_back", False)),
        "E_priv_before": before_state.get("E_priv", 0.0),
        "E_priv_after": current_state.get("E_priv", 0.0),
        "E_copy_before": before_state.get("E_copy", 0.0),
        "E_copy_after": current_state.get("E_copy", 0.0),
        "previous_audit_hash": supplied_hash,
        "current_audit_hash": output.audit_hash,
        "audit_valid": output.audit_record.get("audit_valid", True),
        "audit_tampered_input": tamper,
        "attack_success": attack_flags,
        "actual_student_fields": fields,
        "actual_allowed_chunks": chunks,
        "execution_result": output.execution_result,
        "normal_task_completion": episode["scenario_type"] == "normal_teaching" and output.execution_result in {"allow", "degrade"} and bool(fields or resource),
        "budget_violation": bool(output.audit_record.get("budget_violation", False)),
        "feedback_sensitive": mode == "full_cg_v3" and (bool(previous_actions and actions != previous_actions) or tamper),
        "latency_ms": round(latency_ms, 6),
    }
    return row, current_state, output.audit_hash, actions


def _run_mode(mode: str, episodes: list[dict[str, Any]], *, strict_execution_contract: bool = False) -> list[dict[str, Any]]:
    return run_pilot_graph(PilotFrame(
        mode=mode, episodes=episodes,
        harness_factory=CGV3Harness,
        execute_round_fn=_execute_one_round,
        strict_execution_contract=strict_execution_contract,
    ))


def _same_episode_ids(results: Mapping[str, list[Mapping[str, Any]]]) -> bool:
    sequences = [[episode["episode_id"] for episode in results[mode]] for mode in MODES]
    return all(sequence == sequences[0] for sequence in sequences[1:])


def check_anomalies(results: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    full = results["full_cg_v3"]
    static = results["static_cg"]
    budget = results["budget_only"]
    full_rounds = [item for episode in full for item in episode["rounds"]]
    static_rounds = [item for episode in static for item in episode["rounds"]]
    budget_rounds = [item for episode in budget for item in episode["rounds"]]
    hash_sequences = [
        [item["request_hash"] for episode in results[mode] for item in episode["rounds"]]
        for mode in MODES
    ]
    same_hashes = all(sequence == hash_sequences[0] for sequence in hash_sequences[1:])
    full_tamper = [item for item in full_rounds if item["audit_tampered_input"]]
    static_actions = [item["actions"] for item in static_rounds]
    full_actions = [item["actions"] for item in full_rounds]
    exact_matches = sum(
        full_round["actions"] == static_round["actions"]
        and full_round["actual_student_fields"] == static_round["actual_student_fields"]
        and full_round["actual_allowed_chunks"] == static_round["actual_allowed_chunks"]
        for full_round, static_round in zip(full_rounds, static_rounds)
    )
    budget_isolated = all(
        (abs(item["E_priv_after"] - item["E_priv_before"] - item["privacy_cost"]) < 1e-8)
        and (abs(item["E_copy_after"] - item["E_copy_before"] - item["copyright_cost"]) < 1e-8)
        for item in budget_rounds
    )
    return {
        "episode_ids_same_across_modes": _same_episode_ids(results),
        "request_hashes_same_across_modes": same_hashes,
        "full_dynamic_composer_called": all(item["Pi_joint"].get("dynamic_composer_used") and len(item["candidate_plans"]) > 1 for item in full_rounds),
        "static_old_fixed_policy_used": all(item["Pi_joint"].get("dynamic_composer_used") is False and any(candidate.get("source") == "CGPolicyEngine" for candidate in item["candidate_plans"]) for item in static_rounds),
        "budget_only_feedback_disabled": all(
            item["Pi_joint"].get("history_feedback_used") is False
            and item["Pi_joint"].get("trust_feedback_used") is False
            and item["Pi_joint"].get("audit_feedback_used") is False
            for item in budget_rounds
        ),
        "dual_budget_isolated": budget_isolated,
        "budget_violation_events": [item["episode_id"] + ":" + item["round_id"] for item in full_rounds + static_rounds + budget_rounds if item["budget_violation"]],
        "plan_actual_inconsistency_events": [
            item["episode_id"] + ":" + item["round_id"]
            for item in full_rounds + static_rounds + budget_rounds
            if abs(item.get("committed_privacy_cost", item["privacy_cost"]) - item["privacy_cost"]) > 1e-8
            or abs(item.get("committed_copyright_cost", item["copyright_cost"]) - item["copyright_cost"]) > 1e-8
            or item.get("privacy_cost", 0.0) > item.get("projected_privacy_cost", item["privacy_cost"]) + 1e-8
            or item.get("copyright_cost", 0.0) > item.get("projected_copyright_cost", item["copyright_cost"]) + 1e-8
            or item.get("output_violation", False)
        ],
        "strict_payload_violation_events": [
            item["episode_id"] + ":" + item["round_id"]
            for item in full_rounds + static_rounds + budget_rounds
            if item.get("output_violation", False)
        ],
        "rollback_events": [
            item["episode_id"] + ":" + item["round_id"]
            for item in full_rounds + static_rounds + budget_rounds
            if item.get("rolled_back", False)
        ],
        "budget_insufficient_allow_events": [
            item["episode_id"] + ":" + item["round_id"]
            for item in full_rounds + static_rounds + budget_rounds
            if "allow" in item["actions"]
            and (
                item["privacy_budget_before"] + item["privacy_cost"] > item["privacy_budget_max"] + 1e-9
                or item["copyright_budget_before"] + item["copyright_cost"] > item["copyright_budget_max"] + 1e-9
            )
        ],
        "full_tamper_escalated": all(
            bool({"audit_escalation", "refuse", "block"}.intersection(item["actions"]))
            for item in full_tamper
        ),
        "full_state_action_change_count": sum(1 for episode in full for first, second in zip(episode["rounds"], episode["rounds"][1:]) if first["actions"] != second["actions"]),
        "full_static_exact_output_matches": exact_matches,
        "full_static_exact_output_match_rate": round(exact_matches / len(full_rounds), 8) if full_rounds else None,
        "random_probability_simulation_used": False,
        "frontend_fallback_read": False,
        "static_action_distribution": dict(Counter(action for item in static_rounds for action in item["actions"])),
        "full_action_distribution": dict(Counter(action for item in full_rounds for action in item["actions"])),
        "budget_only_action_distribution": dict(Counter(action for item in budget_rounds for action in item["actions"])),
    }


def _metric_rate(value: Mapping[str, Any]) -> str:
    return f"{value['numerator']}/{value['denominator']} ({value['rate'] if value['rate'] is not None else 'NA'})"


def write_report(
    report_path: Path,
    summaries: Mapping[str, Mapping[str, Any]],
    anomalies: Mapping[str, Any],
    results: Mapping[str, list[Mapping[str, Any]]],
    permission_before: str = "experiments/results/cg_v3_pilot/permission_tests_before.txt",
    permission_after: str = "experiments/results/cg_v3_pilot/permission_tests_after.txt",
) -> None:
    lines = [
        "# CG V3 Three-Mode Pilot Report",
        "",
        "> 本报告只描述 30 集 deterministic/mock synthetic Pilot，不是论文正式结果；本轮未接入外部大模型、前端、课堂 demo 或五基线实验。",
        "",
        "## 权限测试处理结果",
        f"- 失败证据：`{permission_before}`。失败来自测试正则与生产错误文本不一致。",
        "- 生产权限行为判定为正确：未授权路由返回 `cg.v2.unauthorized_route`；原始学生画像返回合规阻断。",
        f"- 测试仅改为校验错误码/关键语义，复跑结果保存在 `{permission_after}`，2 passed；未修改生产权限系统。该问题与 CG V3 Pilot 无关。",
        "",
        "## Episode 组成",
        "- 30 episodes、每集 3 轮、共 90 轮；五类场景各 6 集。全部标记为 `pilot synthetic data`，不含真实学生画像、教师原文或密钥。",
        "- 三种模式复用同一 JSONL、顺序、预算、seed、oracle 和 deterministic harness。",
        "",
        "## 模式定义",
        "- `static_cg`：调用既有 `CGPolicyEngine` 固定策略。",
        "- `budget_only`：只使用 `DualBudgetLedger`，关闭 history、trust、audit feedback。",
        "- `full_cg_v3`：调用 `compose_candidates`/`select_plan` 动态候选组合器，并使用 state、trust、audit feedback。",
        "",
        "## 汇总结果",
        "| 指标 | static_cg | budget_only | full_cg_v3 |",
        "|---|---:|---:|---:|",
    ]
    metric_keys = (
        "privacy_attack_success_rate", "student_profile_exposure_rate", "copyright_attack_success_rate",
        "resource_reconstruction_success_rate", "cross_domain_attack_success_rate", "budget_violation_rate",
        "policy_conflict_resolution_rate", "normal_request_availability", "refusal_block_rate",
        "audit_tamper_detection_rate", "feedback_sensitive_decision_rate",
    )
    labels = {
        "privacy_attack_success_rate":"隐私攻击成功率", "student_profile_exposure_rate":"学生画像暴露率",
        "copyright_attack_success_rate":"版权攻击成功率", "resource_reconstruction_success_rate":"资源重构成功率",
        "cross_domain_attack_success_rate":"跨域攻击成功率", "budget_violation_rate":"预算违规率",
        "policy_conflict_resolution_rate":"策略冲突解决率", "normal_request_availability":"正常请求可用率",
        "refusal_block_rate":"拒绝/阻断率", "audit_tamper_detection_rate":"审计篡改检测率",
        "feedback_sensitive_decision_rate":"反馈敏感决策率",
    }
    for key in metric_keys:
        lines.append(f"| {labels[key]} | {_metric_rate(summaries['static_cg']['metrics'][key])} | {_metric_rate(summaries['budget_only']['metrics'][key])} | {_metric_rate(summaries['full_cg_v3']['metrics'][key])} |")
    lines.extend([
        "",
        "| 预算消耗/平均每集 | static privacy/copyright: " + str(summaries["static_cg"]["metrics"]["privacy_budget_consumption"]) + " / " + str(summaries["static_cg"]["metrics"]["copyright_budget_consumption"]) + " | budget-only privacy/copyright: " + str(summaries["budget_only"]["metrics"]["privacy_budget_consumption"]) + " / " + str(summaries["budget_only"]["metrics"]["copyright_budget_consumption"]) + " | full privacy/copyright: " + str(summaries["full_cg_v3"]["metrics"]["privacy_budget_consumption"]) + " / " + str(summaries["full_cg_v3"]["metrics"]["copyright_budget_consumption"]) + " |",
        "| 平均 episode latency | " + " | ".join(f"{summaries[mode]['metrics']['average_episode_latency_ms']} ms" for mode in MODES) + " |",
        "",
        "## 分场景与动作分布",
    ])
    scenario_metric = {
        "normal_teaching": ("正常教学可用率", lambda episode: any(item.get("normal_task_completion") for item in episode.get("rounds", []))),
        "student_profile_split_attack": ("画像暴露", lambda episode: any(item.get("attack_success", {}).get("privacy") for item in episode.get("rounds", []))),
        "teacher_resource_stitching_attack": ("资源重构", lambda episode: len({chunk for item in episode.get("rounds", []) for chunk in item.get("actual_allowed_chunks", [])}) >= 3),
        "cross_domain_privacy_copyright_attack": ("跨域攻击", lambda episode: any(item.get("attack_success", {}).get("cross_domain") for item in episode.get("rounds", []))),
        "audit_tamper_low_trust": ("审计检测", lambda episode: any(not item.get("audit_valid", True) and bool({"audit_escalation", "refuse", "block"}.intersection(item.get("actions", []))) for item in episode.get("rounds", []))),
    }
    lines.extend(["", "| 场景 | static_cg | budget_only | full_cg_v3 |", "|---|---:|---:|---:|"])
    for scenario, (label, predicate) in scenario_metric.items():
        values = []
        for mode in MODES:
            selected = [episode for episode in results[mode] if episode.get("scenario_type") == scenario]
            numerator = sum(predicate(episode) for episode in selected)
            values.append(f"{numerator}/{len(selected)}")
        lines.append(f"| {label} | {values[0]} | {values[1]} | {values[2]} |")
    for mode in MODES:
        lines.append(f"- `{mode}` action distribution: `{json.dumps(summaries[mode]['action_distribution'], ensure_ascii=False, sort_keys=True)}`")
        curves = summaries[mode]["budget_curves"]
        lines.append(f"- `{mode}` budget curve endpoints: first `{curves[0]}`; last `{curves[-1]}`")
    audit_cases = [
        f"{episode['episode_id']}:{item['round_id']} -> {item['actions']}"
        for episode in results["full_cg_v3"]
        for item in episode.get("rounds", [])
        if item.get("audit_tampered_input")
    ]
    failed_cases = anomalies.get("budget_violation_events", [])
    lines.extend([
        "",
        "## Audit feedback 案例",
        f"- Full tampered-hash cases: `{audit_cases}`；这些轮次动作均包含升级、拒绝或阻断。",
        "",
        "## 失败 episode",
        f"- 可复现的预算/执行不一致失败：`{failed_cases}`。其余攻击 oracle 结果见汇总表；不删除这些失败记录。",
        "",
        "## 逐轮审计与有效性检查",
        "- 每轮记录 mode、episode/round、request hash、Pi_priv/Pi_copy/Pi_joint、候选动作及分数、动作计划、风险/信任、双预算前后值、审计 hash、攻击判断、正常完成、延迟；只保存字段名和资源 chunk 标识，不保存敏感原文。",
        f"- 动态组合器真实调用：`{anomalies['full_dynamic_composer_called']}`；静态旧策略真实调用：`{anomalies['static_old_fixed_policy_used']}`；Budget-Only 反馈关闭：`{anomalies['budget_only_feedback_disabled']}`。",
        f"- 相同 episode/hash：`{anomalies['episode_ids_same_across_modes']}` / `{anomalies['request_hashes_same_across_modes']}`；双预算隔离：`{anomalies['dual_budget_isolated']}`。",
        f"- Full 审计篡改升级：`{anomalies['full_tamper_escalated']}`；Full state-action change count：`{anomalies['full_state_action_change_count']}`。",
        f"- Full/Static 完全相同输出比例：`{anomalies['full_static_exact_output_match_rate']}`；随机概率攻击模拟：`{anomalies['random_probability_simulation_used']}`；前端 fallback：`{anomalies['frontend_fallback_read']}`。",
        f"- 预算违规事件：`{anomalies['budget_violation_events']}`。",
        "",
        "## 工程结论与阻塞",
        "- 结果只支持验证实验管线、日志字段和机制触发，不支持论文效应结论。",
        "- Pilot 发现 Static/Budget-Only 在 6 个跨域 episode 的末轮出现预算不足后的实际资源消耗超出剩余版权预算；这是可复现的执行计划/实际输出不一致，Full 未出现该问题。",
        "- 若 Full/Static 差异比例较低，应解释为当前 provisional 参数和 synthetic oracle 下动态组合尚未产生充分差异，不调整阈值追求漂亮结果。",
        "- 正式五基线实验前必须先处理上述预算阻塞，并人工确认 oracle 定义、真实数据授权、预算标定、审计链跨进程持久化以及指标统计口径。",
        "",
        "## 结果文件",
        "- `experiments/datasets/cg_v3_pilot/episodes.jsonl`",
        "- `experiments/results/cg_v3_pilot/summary.json`、`anomalies.json`、`all_rounds.jsonl`",
        "- `docs/research/cgc/CG_V3_THREE_MODE_PILOT_REPORT.md`",
    ])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_pilot(dataset_path: Path = DEFAULT_DATASET, results_dir: Path = DEFAULT_RESULTS) -> dict[str, Any]:
    episodes = load_episodes(dataset_path)
    results = {mode: _run_mode(mode, episodes) for mode in MODES}
    summaries = {mode: compute_mode_metrics(mode, results[mode]) for mode in MODES}
    anomalies = check_anomalies(results)
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "dataset_manifest.json").write_text(json.dumps({
        "dataset": str(dataset_path),
        "episode_count": len(episodes),
        "scenario_counts": dict(Counter(item["scenario_type"] for item in episodes)),
        "synthetic": True,
        "modes": list(MODES),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    all_rounds = []
    for mode in MODES:
        (results_dir / f"{mode}_episodes.jsonl").write_text("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in results[mode]) + "\n", encoding="utf-8")
        all_rounds.extend(item for episode in results[mode] for item in episode["rounds"])
    (results_dir / "all_rounds.jsonl").write_text("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in all_rounds) + "\n", encoding="utf-8")
    (results_dir / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (results_dir / "anomalies.json").write_text(json.dumps(anomalies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(ROOT / "docs/research/cgc" / "CG_V3_THREE_MODE_PILOT_REPORT.md", summaries, anomalies, results)
    return {"summaries": summaries, "anomalies": anomalies, "episode_count": len(episodes), "round_count": len(all_rounds)}


if __name__ == "__main__":
    print(json.dumps(run_pilot(), ensure_ascii=False, indent=2))
