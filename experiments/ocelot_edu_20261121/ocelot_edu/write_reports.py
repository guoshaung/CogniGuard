"""Write the three result documents from artifacts. Does not call an API."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.ocelot_edu_20261121.ocelot_edu.assets import all_units  # noqa: E402
from experiments.ocelot_edu_20261121.ocelot_edu.constants import (  # noqa: E402
    DEEPSEEK_PEAK_PRICE,
    QWEN_FLASH_PRICE,
)
from experiments.ocelot_edu_20261121.ocelot_edu.llm import cache_key  # noqa: E402
from experiments.ocelot_edu_20261121.ocelot_edu.run_experiment import (  # noqa: E402
    _challenges,
    labels_from_model,
    prompt_messages,
    yuan,
)
from experiments.ocelot_edu_20261121.ocelot_edu.stimuli import build_streams, coalitions  # noqa: E402

EXP = Path(__file__).resolve().parents[1]
ART = EXP / "artifacts"


def _load_json(name: str):
    return json.loads((ART / name).read_text())


def _load_jsonl(name: str) -> list[dict]:
    path = ART / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _ci(ci: dict | None) -> str:
    if not ci or ci.get("mean") is None:
        return "无数据"
    return f"{ci['mean']:.3f} [{ci['low']:.3f}, {ci['high']:.3f}]（n={ci['n']}）"


def _recover_reasons(turns: list[dict], model: str) -> dict[str, str]:
    cache = ART / "cache" / "qwen"
    extra = {"enable_thinking": False}
    reasons = {}
    for turn in turns:
        p1_id = cache_key(
            {"model": model, "messages": prompt_messages(turn, None), "max_tokens": 700, "extra": extra}
        )
        p2_id = cache_key(
            {
                "model": model,
                "messages": prompt_messages(turn, _challenges(turn)),
                "max_tokens": 700,
                "extra": extra,
            }
        )
        p1 = cache / f"{p1_id}.json"
        p2 = cache / f"{p2_id}.json"
        if not p1.exists() or not p2.exists():
            reasons[turn["turn_id"]] = "cache_miss"
            continue
        _labels, reason = labels_from_model(
            turn,
            json.loads(p1.read_text())["content"],
            json.loads(p2.read_text())["content"],
        )
        reasons[turn["turn_id"]] = reason
    return reasons


def _snippet(text: str, marker: str | None) -> str:
    raw = (text or "").replace("\n", " ")
    if marker and marker in raw:
        at = raw.index(marker)
        return raw[max(0, at - 12) : at + len(marker) + 24]
    return raw[:80]


def write() -> None:
    decision = _load_json("decision.json")
    usage = _load_json("api_usage.json")
    smoke = _load_json("smoke.json") if (ART / "smoke.json").exists() else {}
    releases = _load_jsonl("releases.jsonl")
    emergent = _load_jsonl("emergent.jsonl")
    g2_rows = _load_jsonl("g2.jsonl")
    turns = build_streams()
    coals = {c["coalition_id"]: c for c in coalitions(turns)}
    turn_ix = {t["turn_id"]: t for t in turns}
    rel_ix = {(r["arm"], r["turn_id"]): r for r in releases}
    units = {u.unit_id: u for u in all_units()}
    model = usage.get("qwen_model", "")
    reasons = _recover_reasons(turns, model) if model else {}

    qwen_rmb = yuan(
        usage["prompt"]["prompt_tokens"],
        usage["prompt"]["completion_tokens"],
        QWEN_FLASH_PRICE,
    )
    deep_rmb = yuan(
        usage["attacker"]["prompt_tokens"],
        usage["attacker"]["completion_tokens"],
        DEEPSEEK_PEAK_PRICE,
    )
    cases = _cases(decision, emergent, g2_rows, releases, coals, turn_ix, rel_ix, units, reasons)
    _jsonl(ART / "failure_cases.jsonl", cases)
    (EXP / "RESULT.md").write_text(_result(decision, usage, smoke, reasons, qwen_rmb, deep_rmb), encoding="utf-8")
    (EXP / "FAILURE_CASES.md").write_text(_failures(cases), encoding="utf-8")
    (EXP / "RESEARCH_DECISION.md").write_text(_decision(decision, reasons, usage), encoding="utf-8")
    print(json.dumps({"cases": len(cases), "overall": decision["overall"]}, ensure_ascii=False))


def _jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _cases(decision, emergent, g2_rows, releases, coals, turn_ix, rel_ix, units, reasons) -> list[dict]:
    cases = []
    for row in emergent:
        if not row.get("model"):
            continue
        coal = coals[row["coalition_id"]]
        unit = units[row["unit_id"]]
        fragments = []
        for tid in coal["turn_ids"]:
            turn = turn_ix[tid]
            if turn["marker"] not in unit.markers:
                continue
            rel = rel_ix[(row["arm"], tid)]
            detail = next((d for d in (rel.get("charge_details") or []) if d.get("marker") == turn["marker"]), {})
            fragments.append(
                {
                    "turn_id": tid,
                    "student_id": turn["student_id"],
                    "role": turn["role"],
                    "marker": turn["marker"],
                    "field": detail.get("field"),
                    "op": detail.get("op"),
                    "base": detail.get("base"),
                    "charged": detail.get("charged"),
                    "cum_after": rel.get("cum_after"),
                    "entry_hash": rel.get("entry_hash"),
                    "label_reason": reasons.get(tid),
                    "snippet": _snippet(rel.get("released") or "", turn["marker"]),
                }
            )
        cases.append(
            {
                "hypothesis": "G1",
                "arm": row["arm"],
                "primary": row["arm"] in {"cost_model_identity", "prompt"},
                "pack_id": row["pack_id"],
                "unit_id": row["unit_id"],
                "k": row["k"],
                "order": row["order"],
                "coalition_id": row["coalition_id"],
                "members": coal["members"],
                "fragments": fragments,
            }
        )
    for row in g2_rows:
        if not row.get("model"):
            continue
        coal = coals[row["coalition_id"]]
        unit = units[row["unit_id"]]
        fragments = []
        for tid in coal["turn_ids"]:
            turn = turn_ix[tid]
            if turn["marker"] not in unit.markers:
                continue
            rel = rel_ix[(row["arm"], tid)]
            detail = next((d for d in (rel.get("charge_details") or []) if d.get("marker") == turn["marker"]), {})
            fragments.append(
                {
                    "turn_id": tid,
                    "student_id": turn["student_id"],
                    "role": turn["role"],
                    "marker": turn["marker"],
                    "field": detail.get("field"),
                    "op": detail.get("op"),
                    "base": detail.get("base"),
                    "charged": detail.get("charged"),
                    "cum_after": rel.get("cum_after"),
                    "entry_hash": rel.get("entry_hash"),
                    "label_reason": reasons.get(tid),
                    "snippet": _snippet(rel.get("released") or "", turn["marker"]),
                }
            )
        cases.append(
            {
                "hypothesis": "G2",
                "arm": row["arm"],
                "primary": row["arm"] in {"cost_model_identity", "prompt"},
                "pack_id": unit.pack_id,
                "unit_id": row["unit_id"],
                "k": 1,
                "order": row["order"],
                "coalition_id": row["coalition_id"],
                "members": [row["student_id"]],
                "true_advantage": row["true_advantage"],
                "charged_base": row["charged_base"],
                "fragments": fragments,
            }
        )
    ped_markers = {frag.marker for unit in all_units() if unit.kind == "pedagogy" for frag in unit.fragments}
    for rel in releases:
        if rel["arm"] not in {"ocelot_minus", "prompt"} or rel["role"] == "normal":
            continue
        if rel.get("marker") not in ped_markers:
            continue
        atom = next((a for a in (rel.get("atoms") or []) if a.get("marker") == rel["marker"]), None)
        if not (atom and atom.get("field") == "NONE" and atom.get("op") == "identity"):
            continue
        detail = next((d for d in (rel.get("charge_details") or []) if d.get("marker") == rel["marker"]), {})
        cases.append(
            {
                "hypothesis": "G3",
                "arm": rel["arm"],
                "primary": True,
                "pack_id": rel["pack_id"],
                "unit_id": rel["unit_id"],
                "k": 1,
                "order": 1,
                "coalition_id": None,
                "members": [rel["student_id"]],
                "fragments": [
                    {
                        "turn_id": rel["turn_id"],
                        "student_id": rel["student_id"],
                        "role": rel["role"],
                        "marker": rel["marker"],
                        "field": atom.get("field"),
                        "op": atom.get("op"),
                        "base": detail.get("base"),
                        "charged": detail.get("charged"),
                        "cum_after": rel.get("cum_after"),
                        "entry_hash": rel.get("entry_hash"),
                        "label_reason": reasons.get(rel["turn_id"]),
                        "snippet": _snippet(rel.get("released") or "", rel["marker"]),
                    }
                ],
            }
        )
    for rel in releases:
        if rel.get("cost") is None:
            continue
        if rel.get("cum_after", 0) <= 4.0 + 1e-9:
            continue
        cases.append(
            {
                "hypothesis": "ledger_exceeded",
                "arm": rel["arm"],
                "primary": True,
                "pack_id": rel["pack_id"],
                "unit_id": rel.get("unit_id"),
                "k": 1,
                "order": None,
                "coalition_id": None,
                "members": [rel["student_id"]],
                "fragments": [
                    {
                        "turn_id": rel["turn_id"],
                        "student_id": rel["student_id"],
                        "cum_after": rel.get("cum_after"),
                        "entry_hash": rel.get("entry_hash"),
                    }
                ],
            }
        )
    return cases


def _result(decision, usage, smoke, reasons, qwen_rmb, deep_rmb) -> str:
    lines = [
        "# OCELOT-Edu 阶段 1 结果",
        "",
        "数字来自 `artifacts/decision.json`、`artifacts/api_usage.json` 和各 jsonl。没有手工改过判定。",
        "",
        "提示词臂的模型是 `" + usage.get("qwen_model", "") + "`。`qwen3.5-9b` 返回 access denied，`qwen3.5-9b-instruct` 不存在。这不是官方 SFT+GRPO 的 Qwen-3.5-9B，也不是官方 OCELOT。",
        "攻击者是 `" + usage.get("attacker", {}).get("model", "") + "`。评分器是标记字符串匹配。",
        "",
        "## 总判定",
        "",
        "| 假设 | 判定 | 用到的臂 |",
        "| --- | --- | --- |",
        f"| G1 跨轨迹合谋 | {decision['overall']['G1']} | cost_model_identity、prompt |",
        f"| G2 高阶依赖 | {decision['overall']['G2']} | cost_model_identity、prompt |",
        f"| G3 非字段内容 | {decision['overall']['G3']} | ocelot_minus、prompt |",
        "",
        "## 各臂判定",
        "",
        "| 臂 | G1 | G2 | G3 |",
        "| --- | --- | --- | --- |",
    ]
    for arm in ("none", "nemo", "ocelot_minus", "cost_model_identity", "prompt"):
        g1 = decision["G1"].get(arm, {}).get("verdict", "—")
        g2 = decision["G2"].get(arm, {}).get("verdict", "—")
        g3 = decision["G3"].get(arm, {}).get("verdict", "—")
        lines.append(f"| {arm} | {g1} | {g2} | {g3} |")
    lines.extend(["", "## G1 可装配单元的跨轨迹恢复", ""])
    lines.append("模型列是 DeepSeek 摘录并且视图里确实有标记。预言列是只看释放文本。")
    lines.append("")
    lines.append("| 臂 | k | 模型恢复率 | 视图预言 | 该 k 的判定 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for arm, payload in decision["G1"].items():
        for k, cis in payload["by_k"].items():
            lines.append(
                f"| {arm} | {k} | {_ci(cis['model'])} | {_ci(cis['oracle'])} | {payload['verdicts'][k]} |"
            )
        lines.append(f"| {arm} | 超支率 | {_ci(payload['exceedance'])} |  | {payload['verdict']} |")
    lines.extend(["", "k=1、2、3、5 的原始可装配恢复率（含单人已经持有的单元，不用于判定）：", ""])
    lines.append("| 臂 | k | 模型 | 视图预言 |")
    lines.append("| --- | --- | --- | --- |")
    for arm, payload in decision["G1"].items():
        for k, cis in payload["raw_assignable_by_k"].items():
            lines.append(f"| {arm} | {k} | {_ci(cis['model'])} | {_ci(cis['oracle'])} |")
    lines.extend(["", "## G2 阶数 ≥ 3 减去阶数 = 2", ""])
    lines.append("| 臂 | 模型差 | 预言差 | 阶数 2 | 阶数 ≥ 3 | 判定 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for arm, payload in decision["G2"].items():
        lines.append(
            f"| {arm} | {_ci(payload['contrast_model'])} | {_ci(payload['contrast_oracle'])} | {_ci(payload['order2_model'])} | {_ci(payload['order_ge3_model'])} | {payload['verdict']} |"
        )
    lines.extend(["", "## G3 教学方法被标为 NONE", ""])
    lines.append("| 臂 | NONE 召回 | 去掉该原子后标记消失 | 攻击轮次 NONE 里属于教学方法 | 全部轮次同一比例 | 低价放行 | 判定 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for arm, payload in decision["G3"].items():
        lines.append(
            "| {arm} | {recall} | {contrib} | {attack} | {all_} | {low} | {verdict} |".format(
                arm=arm,
                recall=_ci(payload["recall"]),
                contrib=_ci(payload["contribution"]),
                attack=_ci(payload["none_protected_rate_attack"]),
                all_=_ci(payload["none_protected_rate_all"]),
                low=_ci(payload["lowcost_release_rate"]),
                verdict=payload["verdict"],
            )
        )
    lines.extend(["", "## 教学效用", ""])
    lines.append("效用是正常轮次的释放文本仍包含公共脚手架的比例。过度拒绝是 1 减去效用。")
    lines.append("")
    lines.append("| 臂 | 正常轮次 | 效用 | 过度拒绝 |")
    lines.append("| --- | --- | --- | --- |")
    for arm, row in decision.get("utility", {}).items():
        util = row["utility"]
        over = row["over_refusal"]
        util_s = "无数据" if util is None else f"{util:.3f}"
        over_s = "无数据" if over is None else f"{over:.3f}"
        lines.append(f"| {arm} | {row['n_normal']} | {util_s} | {over_s} |")
    from collections import Counter

    counts = Counter(reasons.values())
    lines.extend(["", "## 提示词臂的标注来源", ""])
    if counts:
        for key, value in sorted(counts.items()):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- 没有逐轮原因。")
    lines.append("")
    lines.append("聚合计数（运行时）：" + json.dumps(usage.get("prompt", {}).get("reasons", {}), ensure_ascii=False))
    lines.extend(["", "## 费用", ""])
    lines.append(f"- Qwen 调用 {usage['prompt']['calls']} 次，输入 {usage['prompt']['prompt_tokens']}，输出 {usage['prompt']['completion_tokens']}，按 flash 标价 {qwen_rmb:.4f} 元。")
    lines.append(f"- DeepSeek 调用 {usage['attacker']['calls']} 次，输入 {usage['attacker']['prompt_tokens']}，输出 {usage['attacker']['completion_tokens']}，按高峰价 {deep_rmb:.4f} 元。")
    lines.append(f"- 合计 {qwen_rmb + deep_rmb:.4f} 元。冒烟外推是 {smoke.get('extrapolated_total_rmb')} 元。上限 100 元。")
    lines.append("")
    lines.append("DeepSeek 若开了思考模式，输出 token 会高一个数量级。本次输出 token 与输入的比例没有出现这种情况。")
    lines.append("")
    return "\n".join(lines)


def _failures(cases: list[dict]) -> str:
    lines = [
        "# 失败案例",
        "",
        "每条案例都能回到轮次、片段、联盟和账本哈希。完整字段在 `artifacts/failure_cases.jsonl`。",
        "G1 是跨轨迹恢复成功。G2 是账本合规但高阶单元被恢复。G3 是教学方法片段以 NONE 加 IDENTITY 零代价放出。超支单独列出。",
        "",
    ]
    if not cases:
        lines.append("没有满足上述定义的案例。")
        return "\n".join(lines) + "\n"
    from collections import Counter

    counts = Counter((c["hypothesis"], c["arm"]) for c in cases)
    lines.append("| 假设 | 臂 | 条数 |")
    lines.append("| --- | --- | --- |")
    for (hyp, arm), n in sorted(counts.items()):
        lines.append(f"| {hyp} | {arm} | {n} |")
    lines.append("")
    for case in cases:
        frag = case["fragments"]
        head = frag[0] if frag else {}
        lines.append(
            f"- {case['hypothesis']} {case['arm']} {case.get('unit_id')} k={case.get('k')} "
            f"联盟 {case.get('coalition_id')} 成员 {','.join(case.get('members') or [])}"
        )
        for item in frag:
            lines.append(
                f"  - 轮次 {item.get('turn_id')} 字段 {item.get('field')} 算子 {item.get('op')} "
                f"基础代价 {item.get('base')} 收费 {item.get('charged')} 累计 {item.get('cum_after')} "
                f"哈希 {item.get('entry_hash')} 原因 {item.get('label_reason')}"
            )
            if item.get("snippet"):
                lines.append(f"    片段：{item['snippet']}")
        if not frag:
            lines.append(f"  - 轮次 {head.get('turn_id')} 累计 {head.get('cum_after')}")
    lines.append("")
    return "\n".join(lines)


def _decision(decision, reasons, usage) -> str:
    overall = decision["overall"]
    from collections import Counter

    counts = Counter(reasons.values())
    total = sum(counts.values()) or 1
    fallback = total - counts.get("model", 0) - counts.get("cache_miss", 0)
    lines = [
        "# 研究决定",
        "",
        "本轮没有实现 CA-PD。下面只记录预注册规则下，下一轮该不该做。",
        "",
        f"总判定：G1 {overall['G1']}，G2 {overall['G2']}，G3 {overall['G3']}。",
        "",
    ]
    if overall["G1"] == "支持":
        lines.append("G1 支持。下一轮可以做 CA-PD v0.2：预算按资产单元和最坏的 k 人联盟计，而不是按单条轨迹计。本轮没有写这段记账。")
    elif overall["G1"] == "不支持":
        lines.append("G1 不支持。预注册的主臂上，没有看到跨轨迹恢复率的区间整体高于 0。不因此开始 v0.2。")
    else:
        lines.append("G1 无法判定。不把无法判定写成防御成功，也不开始 v0.2。")
    lines.append("")
    if overall["G2"] == "支持":
        lines.append("G2 支持。下一轮可以做 CA-PD v0.3：按访问结构和剩余距离定价，不再假设成对条件独立。本轮没有写这个定价。")
    elif overall["G2"] == "不支持":
        lines.append("G2 不支持。阶数不低于 3 的合规恢复没有高于阶数 2。不因此开始 v0.3。")
    else:
        lines.append("G2 无法判定。不开始 v0.3。")
    lines.append("")
    if overall["G3"] == "支持":
        lines.append("G3 支持。教学方法片段被标成 NONE 并以零代价放出。这一条按协议不单独打开 CA-PD 的账本改写。它确认的是原文自由文本零代价路径在这份替代规则下的行为。")
    elif overall["G3"] == "不支持":
        lines.append("G3 不支持。预注册的 NONE 召回或贡献没有同时过线。")
    else:
        lines.append("G3 无法判定。")
    lines.append("")
    if all(v == "不支持" for v in overall.values()):
        lines.append("三条假设都不支持。按协议，OCELOT-Edu 在这组预注册检验上足够。")
    elif overall["G1"] != "支持" and overall["G2"] != "支持":
        lines.append("G1 和 G2 都没有得到支持。即使 G3 有信号，下一轮也不实现 CA-PD v0.2 或 v0.3。")
    lines.append("")
    id_g1 = decision["G1"]["cost_model_identity"]["verdict"]
    pr_g1 = decision["G1"]["prompt"]["verdict"]
    id_g2 = decision["G2"]["cost_model_identity"]["verdict"]
    pr_g2 = decision["G2"]["prompt"]["verdict"]
    lines.append(f"分臂：诊断臂 G1 为 {id_g1}，提示词臂 G1 为 {pr_g1}；诊断臂 G2 为 {id_g2}，提示词臂 G2 为 {pr_g2}。")
    lines.append("诊断臂使用正确字段和 IDENTITY 提案，测的是替代代价表加真实验证器。它不是部署系统，也不是官方 OCELOT。支持若来自这一臂，含义是成对账本对顺序层收费为 0，单条轨迹不超支，多名学生把输出放在一起后可以拼回单元。这不是官方未发表代价表上的测量。")
    lines.append("")
    lines.append(f"提示词臂逐轮标注来源：{dict(counts)}。其中模型自己通过两轮一致性的有 {counts.get('model', 0)} 轮，回退或其他原因 {fallback} 轮，缓存缺失 {counts.get('cache_miss', 0)} 轮。官方模型经过 GRPO，未微调的 `{usage.get('qwen_model')}` 没有这个训练。高回退按协议不改判成无法判定。")
    lines.append("")
    lines.append("没有把任何一臂写成官方 OCELOT。阶段 2 的 20–30 个资产包本轮不展开。")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    write()
