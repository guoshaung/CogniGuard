"""Write the NoWM scenario files and the enumeration report.

    PYTHONPATH=. python experiments/nowm_scenarios_20261125/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from experiments.nowm_scenarios_20261125.scenarios import build, target_ids
from experiments.nowm_scenarios_20261125.verify import full_report

ROOT = Path(__file__).resolve().parent


def scenario_document(domain: str) -> dict:
    world = build(domain)
    targets = []
    for target_id in target_ids(domain):
        target = world.registry.get(target_id)
        targets.append({
            "target_id": target.target_id,
            "kind": target.kind,
            "owner_principal_id": target.owner_principal_id,
            "witness_sets": [
                [list(unit) for unit in sorted(witness)]
                for witness in target.witness_sets
            ],
        })
    return {
        "domain": domain,
        "resource_id": world.resource_id,
        "purpose": world.purpose,
        "org_id": "school",
        "now": 50.0,
        "targets": targets,
        "receipts": {
            name: [list(unit) for unit in sorted(units)]
            for name, units in sorted(world.receipt_units.items())
        },
        "evidence": [row.to_dict() for row in world.evidence],
        "requests": [
            {
                "request_id": ask.request_id,
                "principal_id": ask.principal_id,
                "release_units": [list(ask.unit)],
                "purpose": world.purpose,
            }
            for ask in world.requests
        ],
        "admission": {
            "receipts": "recorded holdings only",
            "trusted_event": "SourceEvidence.is_trusted_event, trusted_log or ideal with a holder",
            "all_candidates": "comparison view: every verified holding, including watermark",
        },
        "notes": [
            "Safety labels are not in this file.",
            "all_candidates is not written into source_state.py.",
        ],
    }


def _cell(report: dict, domain: str, k: int) -> dict:
    for cell in report["findings"]["cells"]:
        if cell["domain"] == domain and cell["k"] == k:
            return cell
    raise KeyError((domain, k))


def _md_list(items: list[str]) -> str:
    return ", ".join(items) if items else "—"


def render(report: dict) -> str:
    lines = [
        "# CogniGuard-NoWM 非退化场景核验",
        "",
        "可运行场景在 `results/teacher.scenario.json` 和 `results/student.scenario.json`。",
        "核验命令：`PYTHONPATH=. python experiments/nowm_scenarios_20261125/run.py`。",
        "测试：`PYTHONPATH=. python -m pytest experiments/nowm_scenarios_20261125/test_nowm.py -q`。",
        "本目录不新增 X 系列命题，也不修改 `source_state.py` 的可信事件入账。",
        "",
        "## 1. 场景",
        "",
        "见证大小都在 3–5。教师目标是 `teaching_asset`（design、rubric、placement、lab）。",
        "学生目标经 `attribute_target` 注册（support、family、placement、mobility），种类是 `student_attribute`。",
        "两组请求模式相同。教师 placement 含单元 `a`；学生 placement 用信号 `z`，主体 A 的回执里已经有 `z`。",
        "在这份请求上，两个领域的每个 (k, 信息, 规则) 决策一致。这是同构核验，不是第二份独立样本。",
        "",
        f"穷举比对 {report['enumeration_checks']} 次，不一致 {len(report['mismatches'])} 次。",
        "穷举只做见证包含，不调用 `check_release` 的集合覆盖。",
        "比对范围是回执、可信事件、全部候选，以及与全部候选相同的植入持有。",
        "不安全时，`check_release` 给出的联盟必须包含接收方、人数不超过 k，并且联合持有盖住该见证。",
        "",
        "未登记单元：A 持有 `d`（水印，已核验），B 持有 `e`（水印，已核验）和 `g`（可信日志），D 持有 `i`（水印，已核验）。",
        "同一份证据记录进入每个规则。`all_candidates` 把四条都并入知识；`trusted_event` 只并入 `g`。",
        "授权、请求和效用分母不随规则改变。请求在冻结的初始知识上评分，后一次放行不改写下一次的 Oracle。",
        "",
        "效用 = (Oracle 允许数 − 误拒数) / Oracle 允许数。",
        "Oracle 允许 = 已授权，且植入持有上的穷举在该 k 下安全。",
        "危险放行 = 已授权、规则放行、穷举不安全。",
        "",
        "## 2. 相同信息下的计数",
        "",
        "下表是教师领域。学生领域的决策与之相同。",
        "CA-PD 在 `all_candidates` 上与穷举一致，所以危险放行为 0、效用为 1。",
        "",
        "| k | Oracle 允许/拒绝 | 内容入账翻掉的请求 | 可信事件翻掉的请求 | 可信事件危险放行 | 并集更拒绝 | 配额多拒绝 | 配额漏拒绝 |",
        "|---:|---:|---|---|---:|---|---|---|",
    ]
    for k in (1, 2, 3):
        cell = _cell(report, "teacher", k)
        lines.append(
            "| {k} | {a} / {d} | {flips} | {trusted} | {harm} | {union} | {over} | {miss} |".format(
                k=k,
                a=cell["oracle_allows"],
                d=cell["oracle_denies"],
                flips=_md_list(cell["evidence_flips"]),
                trusted=_md_list(cell["trusted_event_flips"]),
                harm=cell["trusted_event_harmful"],
                union=_md_list(cell["union_stricter_than_capd"]),
                over=_md_list(cell["quota_refuses_capd_allow"]),
                miss=_md_list(cell["quota_allows_capd_deny"]),
            )
        )
    lines.extend([
        "",
        "k = 1 时配额上限是 |W| − 1，拒绝条件就是接收方自己盖住见证，与 CA-PD 的 k = 1 相同。",
        "这一格看不出 CA-PD 相对配额的差别。k = 2 时成对检查与 CA-PD 使用同一个 k，决策一致。",
        "",
        "## 3. 动态证据增益与 CA-PD",
        "",
        "内容入账翻掉的请求，是回执上 CA-PD 放行、全部候选上 CA-PD 拒绝的请求。",
        "全部候选等于植入持有，所以这些拒绝就是植入状态下真实不安全的请求。",
        "增益等于多看见的单元，不是另一条判定规则：同一知识上穷举与 `check_release` 的安全位一致。",
        "可信事件对照不接收已核验水印。",
        "它没有翻掉任何一条内容入账翻掉的请求。",
        "危险放行保持 1（k = 1、2）和 2（k = 3）。",
        "",
        "同一份全部候选上，规则之间仍然不同：",
        "",
        "- k = 3 的 `r10`（主体 C 请求 `m`）穷举安全，CA-PD 允许，全体并集拒绝。",
        "  见证大小是 5。四个缺失单元分在四名主体上，两名帮手盖不住。",
        "- k = 2 的 `r7` 穷举安全，CA-PD 允许，WS04 配额拒绝。",
        "  配额只数接收方自己的单元，上限是 floor((|W| - 1) / k)。",
        "- k = 3 的 `r5` 和 `r9` 穷举不安全，CA-PD 拒绝，配额允许。",
        "  配额没有读其他主体的持有。",
        "",
        "动态证据相对回执的安全变化是额外信息。",
        "信息对齐之后，CA-PD 相对并集和配额仍有不同的允许集。",
        "k 大于等于最大见证（本场景最大为 5）的格子没有构造。",
        "命题 4 说那时 CA-PD 与全体并集等价。本结果不覆盖那一格。",
        "E10 里 k 大于等于 3 时与并集持平的结果保持不变。",
        "",
        "## 4. 对 Claude 综合实验的审计",
        "",
        "对象是 `integration/provenance-governance@0684a77` 的 X3-E2E。",
        "文件是 `build_education.py`、`score.py`、`PREREG_X3E2E.md`、`DEVIATIONS.md`、`RESULT.md`。",
        "没有重跑那 21,120 次。",
        "",
        "基线公平。考题见证是来源事实加考题单元，大小为 2。",
        "k = 2 时 k 不小于见证大小，而且每个事实已经发给某名学生，",
        "所以任何考题放行都能补齐二人见证。",
        "偏离第 4 条事先写明 Oracle 可放行为 0。",
        "机制表里「CA-PD k = 2：0 / 无定义」不是可用性优势，效用分母是 0。",
        "主单元格是 k = 1，只检查接收方自己是否盖住见证。",
        "大小为 2 的见证在 k = 1 时配额上限是 0，会拒绝该见证的每一个单元。",
        "这与 k = 1 的 CA-PD 不是同一个规则。",
        "X3-E2E 的臂里没有配额和全体并集，",
        "这张表不能证明相同证据下 CA-PD 有独立贡献。",
        "正式结果把这件事推给 E5–E10，这个范围是对的。",
        "H-Evidence 比较的是同一 CA-PD、不同知识。",
        "表里 F_STRONG 与 CONTENT_ALL 的危险放行相同。",
        "减少量是指纹确认的单元。",
        "本目录的冻结知识给出同一个拆分：全部候选上 CA-PD 的效用是 1，",
        "可信事件对照留有危险放行。",
        "`score.py` 计算 Oracle 时，把本臂已经放行的单元写进后续真实知识。",
        "效用分母因此可以随臂变化。",
        "预注册写的是决策时刻的真实知识。",
        "在线计分会让后一个请求的 Oracle 依赖本臂自己的历史。",
        "本目录改成冻结初始知识，十个请求共用一个分母。",
        "这是计分审计，不是对那次正式运行的重新记分。",
        "",
        "统计单位。预注册以 15 条传播链为簇，",
        "簇内先对 30 个种子取平均，再做 5,000 次配对 bootstrap。",
        "21,120 是运行次数：4 个变体 × 4 个 (k, f) × 11 条臂 × 4 种模式 × 30 个种子。",
        "种子只重排角色和请求，运行之间不独立。推断单位是链。",
        "正文同时给出每次运行的均值和链 bootstrap 的下界。",
        "不能把 21,120 当成样本容量。",
        "k = 2 的效用无定义，不能读成安全成功。",
        "NLI 的 99/137 和每次运行危险放行从约 18 降到 1.77 不是同一个分母。",
        "137 - 38 = 99 属于固定见证夹具。",
        "教育场景的每次运行均值不能与 99/137 相加。",
        "",
        "结果解释。正式结果先写动态知识状态有安全增益，",
        "随即说明增益来自已有内容检测，F_STRONG 单独达到同一数值。",
        "这里的增益是内容通道相对回执，不是信息对齐之后的算法差。",
        "水印增量为 0 与 Gate W0-Real 的方向一致。本目录没有新的水印测量。",
        "CA-PD 相对并集的优势只可能出现在 k 小于见证大小时。",
        "E10 已报告现有基准在 k 大于等于 3 时与并集持平，因为那些见证大多大小为 2。",
        "本场景补的是那个空格：k = 3、见证大小 5 时，",
        "`r10` 上 CA-PD 允许而并集拒绝，穷举判定该允许是 k-安全的。",
        "这不推翻 E10 的持平结果。",
        "",
        "## 5. 失败项",
        "",
        "非退化检查失败项：" + ("无。" if not report["failures"] else " " + "; ".join(report["failures"])),
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    report = full_report()
    out = ROOT / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    for domain in ("teacher", "student"):
        (out / f"{domain}.scenario.json").write_text(
            json.dumps(scenario_document(domain), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    (ROOT / "RESULT.md").write_text(render(report), encoding="utf-8")
    if report["failures"] or report["mismatches"]:
        print("FAILED", report["failures"], file=sys.stderr)
        return 1
    print(
        f"checks={report['enumeration_checks']} mismatches=0 "
        f"failures=0 wrote {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
