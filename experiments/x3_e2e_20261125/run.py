#!/usr/bin/env python3
"""Run the shadow X3-E2E loop and write summary.json plus RESULT.md."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.x3_e2e_20261125.evaluate import evaluate  # noqa: E402
from experiments.x3_e2e_20261125.gate_probe import education_probe, software_probe  # noqa: E402
from experiments.x3_e2e_20261125.scenarios import build_scenarios  # noqa: E402

HERE = Path(__file__).resolve().parent
PILOT_NAMES = (
    "PILOT_RESULTS.md",
    "evaluation.json",
    "evaluation_38.json",
    "watermark/orphan_stress.json",
)


def _git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    text = (completed.stdout or completed.stderr).strip()
    return f"exit {completed.returncode}: {text}"


def locate_pilot(explicit: str | None) -> dict:
    roots = []
    if explicit:
        roots.append(Path(explicit))
    roots.append(ROOT / "experiments" / "hsw_provenance")
    found = []
    missing = []
    for root in roots:
        for name in PILOT_NAMES:
            path = root / name
            if path.is_file():
                found.append(str(path))
            else:
                missing.append(str(path))
    status = "ABSENT" if not found else "PRESENT_UNMAPPED"
    return {
        "pilot_status": status,
        "found": found,
        "missing": missing,
        "git_cat_file_d7239c4": _git(["cat-file", "-t", "d7239c4"]),
        "origin_codex_hsw_st": _git(["rev-parse", "origin/codex/hsw-st"]),
        "note": (
            "The cited server pilot was not measured here. "
            "38 sources, 1288 endpoints, and 616/2052 are unverified user-side claims."
        ),
    }


def _pct(value) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def _result_md(report: dict) -> str:
    metrics = report["metrics"]
    lines = [
        "# X3-E2E 来源证据影子闭环",
        "",
        "本目录是一次可运行的接入实验。它不是新的定理，也不把工程集成写成科研贡献。",
        "历史 X1–X5 的 STOP / ANALYZE 与冻结协议没有改写。X3 的五个合法翻转仍然不是水印试点。",
        "",
        "## 试点数据",
        "",
        f"- 状态：`{report['pilot']['pilot_status']}`",
        f"- `git cat-file -t d7239c4`：{report['pilot']['git_cat_file_d7239c4']}",
        f"- `origin/codex/hsw-st`：{report['pilot']['origin_codex_hsw_st']}",
        f"- {report['pilot']['note']}",
        "- 下表的水印行全部是受控夹具，标签为 `controlled_fixture`。理想证据列是 Oracle 臂。",
        "",
        "## 对照",
        "",
        "| 臂 | 未授权成功率 | 正常任务成功率 | 误拒率 | 放行中的联盟违规 | 错误归因授权次数 | 相对 B0 新增正确决策 | 传播确认次数 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, row in metrics.items():
        lines.append(
            "| {arm} | {unauth} ({uh}/{un}) | {benign} | {false} | {coal} | {wrong} | {extra} | {conf} |".format(
                arm=arm,
                unauth=_pct(row["unauthorized_success"]),
                uh=row["unauthorized_success_count"][0],
                un=row["unauthorized_success_count"][1],
                benign=_pct(row["benign_success"]),
                false=_pct(row["false_reject"]),
                coal=_pct(row["coalition_violation_among_allows"]),
                wrong=row["wrong_attribution_authorization_count"],
                extra=row["additional_correct_vs_b0"],
                conf=row["confirmed_propagation_count"],
            )
        )
    latency = report["latency_ms"]["median_ms"]
    overhead = report["latency_ms"]["overhead_vs_b0"]
    lines.extend(
        [
            "",
            "## 延迟",
            "",
            "中位值为单次影子决策的毫秒数，重复 5 轮。没有调用 MySQL，也没有调用水印服务器。",
            "",
        ]
    )
    for arm in metrics:
        lines.append(f"- {arm}: {latency[arm]:.4f} ms，相对 B0 {overhead[arm]:.2f} 倍")
    lines.extend(["", "## 分场景", ""])
    for row in report["scenarios"]:
        bits = " ".join(
            f"{arm}={'Y' if item['allowed'] else 'N'}" for arm, item in row["arms"].items()
        )
        lines.append(
            f"- `{row['scenario_id']}` oracle={'Y' if row['oracle_allow'] else 'N'} {bits}。"
            f"{row['note']}"
        )
    edu = report["education_gate"]
    soft = report["software_gate"]
    lines.extend(
        [
            "",
            "## 真实 ReleaseGate",
            "",
            "教育探针走现有 `ReleaseGate`：学生 s1 取得教材的一个单元并提交回执；",
            f"s2 再取互补单元的原因是 `{edu['teaching_completing_unit_reason']}`；",
            f"无授权陌生人的原因是 `{edu['stranger_reason']}`；",
            f"学生属性一个信号允许={edu['attribute_one_signal_allowed']}，",
            f"互补信号的原因是 `{edu['attribute_completing_reason']}`。",
            "属性目标种类是 "
            f"`{edu['attribute_kind']}`。",
            "",
            "软件探针同样走 `ReleaseGate` 和 `RegistryHolder`。",
            f"runbook 预留={soft['runbook_reserved']}；策略版本升到 2 之后提交成功="
            f"{soft['commit_after_policy_bump']}；",
            f"再次申请密钥的原因是 `{soft['key_after_bump_reason']}`；",
            f"readme 仍允许={soft['readme_still_allowed']}。",
            "影子模块没有调用 `evaluate_and_reserve`。",
            "",
            "## 接口回归",
            "",
            "五个历史翻转在去掉注册表回退时：普通水印不允许，内嵌签名凭证允许。",
            "这只说明适配器没有把水印置信度当成授权。它不推翻 X3 的 STOP。",
            "",
        ]
    )
    for row in report["interface_regression"]:
        lines.append(
            f"- `{row['scenario_id']}` watermark_only={row['watermark_only_allowed']} "
            f"credential={row['credential_allowed']} "
            f"production_change={row['changes_production_path']}"
        )
    lines.extend(
        [
            "",
            "## 怎么读这些数",
            "",
            "B4 与 B0 的授权应当一致：普通水印不授予、不确认传播、不把单元写入知识。",
            "B3 只在可信日志写明持有者时补上未记录传播，从而拦下 B0 会放行的联盟完成。",
            "Ours 在残留标记且知识检查为空时，会否决仍有效的签名凭证。",
            "检测器把仍在的单元报成空时，Ours 会误拒，B2 不会。两种结果都保留。",
            "全部决策的 `charged_budget` 都是 false。",
            "",
        ]
    )
    return "\n".join(lines)


def _example_bundle(scenarios) -> dict:
    scenario = next(row for row in scenarios if row.scenario_id == "rounds-1")
    channels = {
        name: [item.to_dict() for item in rows]
        for name, rows in scenario.channels.items()
        if name != "ideal"
    }
    return {
        "bundle_id": "controlled-rounds-1",
        "artifact_id": "rounds",
        "text_sha256": "",
        "propagation_rounds": 1,
        "transform": "identity",
        "channels": channels,
        "origin": "controlled_fixture",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-dir", default=None)
    args = parser.parse_args()
    scenarios = build_scenarios()
    report = evaluate(scenarios)
    report["pilot"] = locate_pilot(args.pilot_dir)
    report["education_gate"] = education_probe()
    report["software_gate"] = software_probe()
    report["round_trip_note"] = (
        "Replace fixtures by dropping a propagation bundle that validates against "
        "schema/propagation_bundle.schema.json. This run did not receive one."
    )
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    (HERE / "RESULT.md").write_text(_result_md(report))
    example = HERE / "fixtures"
    example.mkdir(exist_ok=True)
    (example / "controlled_rounds_1.bundle.json").write_text(
        json.dumps(_example_bundle(scenarios), indent=2) + "\n"
    )
    print(json.dumps({"pilot": report["pilot"]["pilot_status"], "metrics": report["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
