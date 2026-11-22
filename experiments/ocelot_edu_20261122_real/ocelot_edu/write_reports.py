"""Write the three result documents from public artifacts only."""

from __future__ import annotations

import json
from pathlib import Path


def _fmt(ci: dict | None) -> str:
    if not ci or ci.get("mean") is None:
        return "无"
    return f"{ci['mean']:.3f} [{ci['low']:.3f}, {ci['high']:.3f}] n={ci.get('n')}"


def write_reports(exp: Path, decision: dict, table: dict, failures: list[dict]) -> None:
    overall = decision["overall"]
    lines = [
        "# OCELOT-Edu 阶段 1b 结果",
        "",
        "上一轮使用了自建的合成单元，G1、G2 是按构造成立的，不用于判定。",
        "",
        "本轮的单元、层次和依赖来自外部资产包。仓库里没有资产原文。",
        "主判定的 G1 只看 `ocelot_minus` 和 `prompt`。G2 是代价网格上“实测高阶代价减成对预测”的包聚类区间，两个主臂共用这张表，诊断臂不能改写它。",
        "",
        f"总判定：G1 {overall.get('G1')}，G2 {overall.get('G2')}，G3 {overall.get('G3')}。",
        f"攻击者轮次：{decision.get('active_round')}。费用 {decision.get('spend_rmb')} 元。预算中止：{decision.get('budget_stop')}。",
        f"提示词臂回退比例：{decision.get('prompt_fallback_rate')}。",
        "",
        "## G1",
        "",
        "一个 k 要同时满足：跨轨迹恢复区间下界大于 0，攻击者与释放文本上限的差距不超过 0.15，并且账本超支率区间上界不超过 0.05。",
        "轨迹代价必须落在 (0, 4]，k 人的代价之和必须大于 4。代价为 0 的单元不进入分母。空集是无法判定。",
        "",
    ]
    for arm, payload in decision["g1"].items():
        lines.append(f"### {arm}：{payload['arm']}")
        lines.append("")
        for k, cell in payload["per_k"].items():
            lines.append(
                f"- k={k}：{cell['verdict']}，恢复 {_fmt(cell['recovery'])}，"
                f"上限 {_fmt(cell['oracle'])}，攻击者 {_fmt(cell['attacker'])}，"
                f"跳过 {cell['skipped']}，差距拦截 {cell['gap_blocked']}"
            )
        lines.append(f"- 超支 {_fmt(payload['exceedance'])}")
        lines.append("")
    grid = decision["g2_grid"]
    lines.extend(
        [
            "## G2",
            "",
            f"网格判定：{decision['g2_grid_verdict']}。{_fmt(grid)}，包数 {grid.get('n_clusters')}。",
            "delta 是实测高阶代价减去成对外推。成对外推只读空视图、单片段和成对的猜中数。",
            "下面各臂的释放子集是描述。它不改网格判定。诊断臂 `cost_model_identity` 不进入总判定。",
            "",
        ]
    )
    for arm, payload in decision["g2"].items():
        lines.append(f"- {arm} 释放子集：{payload['verdict']}，{_fmt(payload['ci'])}")
    lines.extend(["", "## G3", ""])
    for arm, payload in decision["g3"].items():
        if arm == "cost_model_identity":
            continue
        lines.append(
            f"- {arm}：{payload['verdict']}。召回 {_fmt(payload['recall'])}（{payload['recall_verdict']}），"
            f"贡献 {_fmt(payload['contribution'])}（{payload['contribution_verdict']}）。"
        )
    lines.extend(["", "## 效用", ""])
    for arm, payload in decision["utility"].items():
        kept = payload["kept"]
        kept_s = "无" if kept is None else f"{kept:.3f}"
        lines.append(f"- {arm}：公开轮次仍保留的比例 {kept_s}，过度拒绝 {payload['over_refusal']}，n={payload['n']}")
    lines.extend(
        [
            "",
            "## 差距和模型",
            "",
            "```json",
            json.dumps({"gap": decision.get("gap"), "ollama_ids": table.get("ollama_ids")}, ensure_ascii=False, indent=2),
            "```",
            "",
            "若攻击者明显低于释放文本上限，协议规定先换成带单元格式说明的三次抽样，再判定。上表的 active_round 记录实际用的是哪一轮。",
            "",
        ]
    )
    (exp / "RESULT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    hit_rows = [row for row in failures if row["kind"] == "attacker_hit"]
    gap_rows = [row for row in failures if row["kind"] == "g2_undercharge"]
    fail_lines = [
        "# 失败案例",
        "",
        "这里没有资产原文。逐条记录在 `artifacts/failure_cases.jsonl`，用单元编号、哈希和代价追溯。",
        "",
        f"攻击者判为恢复的记录：{len(hit_rows)}。网格 delta 大于 0.18 且该臂确实放出对应视图的记录：{len(gap_rows)}。",
        "",
        "## 攻击者恢复",
        "",
    ]
    for row in hit_rows:
        fail_lines.append(
            f"- {row['arm']} {row['package_id']} {row['coalition']} k={row['k']} {row['target_id']} "
            f"units={','.join(row['unit_ids'])} oracle={row['oracle']} quote={row['quote_sha256'][:12]}"
        )
    if not hit_rows:
        fail_lines.append("没有攻击者恢复记录。")
    fail_lines.extend(["", "## 成对预测低于实测高阶代价", ""])
    for row in gap_rows:
        fail_lines.append(
            f"- {row['arm']} {row['package_id']} {row['target_id']} order={row['order']} "
            f"view={','.join(row['view'])} meas={row['cost_meas']} pred={row['cost_pred']} delta={row['delta']}"
        )
    if not gap_rows:
        fail_lines.append("没有超过 0.18 比特的释放子集。")
    fail_lines.append("")
    (exp / "FAILURE_CASES.md").write_text("\n".join(fail_lines) + "\n", encoding="utf-8")

    open_section = bool(decision.get("section4"))
    decision_lines = [
        "# 研究决定",
        "",
        "CA-PD 的第 4 节本轮没有实现。",
        "",
    ]
    if open_section:
        decision_lines.append("预注册规则允许进入下一轮设计，本轮仍然只写决定、不写实现。")
        if overall.get("G1") == "支持":
            decision_lines.append("G1 支持：下一轮可以做跨接收者记账，预算按资产单元和最坏的 k 人联盟来计。")
        if overall.get("G2") == "支持":
            decision_lines.append("G2 支持：下一轮可以做访问结构和剩余距离定价，不再只用成对外推。")
    else:
        decision_lines.append("G1 和 G2 的总判定都不是支持，所以不进入第 4 节。")
    decision_lines.extend(
        [
            "",
            f"网格 G2 是 {decision.get('g2_grid_verdict')}，{_fmt(grid)}。",
            "诊断臂的释放子集写在结果里，不参与这个判定。",
            "G3 单独成立也不进入第 4 节。",
            "",
        ]
    )
    (exp / "RESEARCH_DECISION.md").write_text("\n".join(decision_lines) + "\n", encoding="utf-8")
