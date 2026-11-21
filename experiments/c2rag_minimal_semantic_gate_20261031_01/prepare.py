"""Assemble review documents only. No model, symbolic solver or experiment imports."""
from __future__ import annotations

import hashlib
import json
import random
import re
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.paths import PROJECT_ROOT, RESULTS_DIR

ROOT = PROJECT_ROOT
HERE = Path(__file__).resolve().parent
RUN = HERE.name
OUT = RESULTS_DIR / RUN
DELIVERY = ROOT / "artifacts" / RUN
SOURCE = ROOT / "docs/reports/c2rag_minimal_semantic_pairs_20261031_01"
PARENT_COMMIT = "5d068b7828c53e2e5dedcd06408f1cab957b4c4e"
VERSION = "SEMANTIC-GATE-20261031-01"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def put(path: Path, value: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(value.encode("utf-8") if isinstance(value, str) else value)


def save_json(path: Path, value: object) -> None:
    put(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def section(block: str, number: int) -> str:
    match = re.search(rf"\*\*{number}\. [^\n]+\*\*\n", block)
    assert match
    remainder = block[match.end():]
    following = re.search(r"\n\*\*\d+\. ", remainder)
    return remainder[:following.start() if following else len(remainder)].strip()


def main() -> None:
    assert not OUT.exists() and not DELIVERY.exists(), "Refuse to overwrite any previous preparation"
    expected = {
        "CANDIDATE_CASES.md": "70a15095eebc774f0658a24a3eaba57e9592651ff4e3e0a4d30ef0362795f5e0",
        "DESIGN_REVIEW.md": "8674232fb81d04404677ac18208bb4d6a56a699ef052ac186a956fd04793389f",
    }
    for name, sha in expected.items():
        assert digest((SOURCE / name).read_bytes()) == sha, name
    text = (SOURCE / "CANDIDATE_CASES.md").read_text(encoding="utf-8")
    blocks = re.split(r"^### 案例 ", text, flags=re.M)[1:]
    cases = {}
    for block in blocks:
        key = block.split("：", 1)[0]
        body = section(block, 3)
        quotes = [line[2:] for line in body.splitlines() if line.startswith("> ")]
        roles = re.findall(r"(?:第一轮|第二轮|第三轮)，学生问(.+?)：", body)
        assert len(quotes) == 6 and len(roles) == 3
        cases[key] = {"turns": [{"agent": roles[i], "query": quotes[2*i], "reply": quotes[2*i+1]} for i in range(3)]}
    assert set(cases) == {"1P", "1N", "2P", "2N", "3P", "3N"}
    families = {}
    titles = {"1": "名单导出作业", "2": "备用照明实验", "3": "作品档案整理"}
    for group in ("1", "2", "3"):
        block = next(b for b in blocks if b.startswith(group + "P："))
        context = section(block, 1)
        families[group] = {
            "title": titles[group],
            "scene": context.split("\n\n", 1)[0],
            "public_context": section(block, 2),
            "target": re.search(r"\*\*(.*?)\*\*", context).group(1),
            "target_scope": "本次运行的后果与影响路径" if group == "1" else "本次检查时段的供电状态与路径" if group == "2" else "本次课程的资格规则，不是学生已做过什么",
        }
    OUT.mkdir(parents=True)
    DELIVERY.mkdir(parents=True)
    for name in expected:
        put(OUT / "source_snapshot" / name, (SOURCE / name).read_bytes())
    for name in ("CASE_GATE_AUDIT", "BASELINE_PREREGISTRATION", "ALGORITHM_GAP_HYPOTHESES"):
        put(OUT / (name + ".md"), (HERE / (name + ".template.md")).read_bytes())

    intro = """# 独立人工审查：六张案例卡

状态：HUMAN_REVIEW_PENDING。这里没有预填结论。材料为原创合成教学情境，不是真实课堂记录。
目标句只是待判断的问题，不是已知事实。只根据背景与已经读到的问答判断，不猜未公开答案，不查作者说明。

## 填写方法

每人审查全部六卡。每卡先读背景，再按第一、二、三轮阅读并立即勾选该轮判断；不要先看后轮再倒填。Markdown/纸张无法技术阻止翻页，顺序依赖人工遵守，不能声称已经实现强制隐藏。
第1、2轮不要求解释；第3轮只写一句依据或一个缺失前提。整卡再勾自然性和设计问题。所有方框初始为空，选择时将[ ]改成[x]。不要逐项填写“无”。
两人不得讨论、查看彼此结果或使用AI代填。相似情境不保证答案不同，不推定可推出/不可推出的数量。全部六卡完成后，才使用末尾对应关系比较文字，补充问题4；不要因此改写原前缀判断，改正须留原记录与时间。

审查者代号：____  包版本：SEMANTIC-GATE-20261031-01
开始时间（含时区）：____  完成时间（含时区）：____
接触情况：[ ] 未看过作者标签、证明或反例 [ ] 已看过（请说明并通知组织者，不作为未暴露盲审）
独立性确认：[ ] 本人独立完成全部六卡，未使用AI代填，未看另一人的结果
原包SHA256见随附PACKET_VERSION.json；组织者收件后另算填写稿哈希。上述时间为本人填报，不冒充可信服务器时间。

---
"""
    crosswalk = {}
    packet_hashes = {}
    for reviewer, seed in (("A", 20261031), ("B", 20261101)):
        order = list(cases)
        random.Random(seed).shuffle(order)
        mapping = {}
        parts = [intro, f"本份分配给审查者 **{reviewer}**。\n\n"]
        for index, key in enumerate(order, 1):
            alias = f"{reviewer}-{index:02}"
            mapping[alias] = key
            family = families[key[0]]
            parts += [
                f"## 案例卡 {alias}：{family['title']}\n\n",
                f"**学习情境**\n\n{family['scene']}\n\n",
                f"**共同背景与权限**\n\n{family['public_context']}\n\n",
                f"**需要判断的目标句（不作为事实）**\n\n> {family['target']}\n\n",
                f"目标范围：{family['target_scope']}。\n\n",
            ]
            for turn_no, turn in enumerate(cases[key]["turns"], 1):
                parts += [
                    f"### 读到第{turn_no}轮\n\n",
                    f"学生问{turn['agent']}：\n\n> {turn['query']}\n\n",
                    f"助教回答：\n\n> {turn['reply']}\n\n",
                    "**问题2：到这里能够确定目标吗？只选一个。**\n\n",
                    "- [ ] 可以推出目标\n- [ ] 可以推出目标不成立\n- [ ] 目前无法确定\n- [ ] 材料矛盾或语义不清\n\n",
                ]
            parts += [
                "### 整张卡的三个简短问题\n\n",
                "**问题1：自然吗？只选一个。**\n\n- [ ] 自然\n- [ ] 勉强合理\n- [ ] 明显为实验拼接\n- [ ] 无法判断\n\n可选一句说明：____\n\n",
                "**问题3：第三轮的依据是什么？**\n\n引用最关键原句并写一条短推理；若无法确定，只写一个缺失前提或一种相容解释。不要重抄三轮。\n\n填写：____\n\n",
                "**问题4：有没有明显设计问题？可多选；“没有明显问题”与其他项不能同时选。**\n\n",
                "- [ ] 实体或时间不清\n- [ ] 需要额外常识\n- [ ] 前提被偷偷加入\n- [ ] 正负差异不止一处\n- [ ] 语言过度暗示答案\n- [ ] 学生提问不自然\n- [ ] 没有明显问题\n\n",
                "配对差异项在读完六卡后再复核；这里的措辞不预设哪张卡应为正或负。仅在有问题时补一句：____\n\n---\n\n",
            ]
        parts.append("## 全部六卡完成后：仅核对文本差异\n\n以下只列对应版本，不给预期判断。两张卡都可能同样可推出、同样不确定，不能为配成正负而改答案。\n\n")
        for group in ("1", "2", "3"):
            aliases = [a for a, k in mapping.items() if k.startswith(group)]
            parts.append(f"- {families[group]['title']}：{aliases[0]} 与 {aliases[1]}。\n")
        parts.append("\n提交文件名可另存为填写稿；请保留原包，独立发回组织者。不要把对方包、作者分析或外部检索结果混入本稿。\n")
        payload = "".join(parts).encode("utf-8")
        name = f"HUMAN_REVIEW_{reviewer}.md"
        put(OUT / name, payload)
        packet_hashes[reviewer] = digest(payload)
        crosswalk[reviewer] = {"seed": seed, "mapping": mapping}
        version = {"version": VERSION, "reviewer": reviewer, "file": name, "sha256": digest(payload), "cards": 6, "prefix_decisions": 18, "status": "HUMAN_REVIEW_PENDING", "contains_expected_answers": False}
        with zipfile.ZipFile(DELIVERY / f"盲审包_{reviewer}.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(name, payload)
            archive.writestr("PACKET_VERSION.json", json.dumps(version, ensure_ascii=False, indent=2) + "\n")
    save_json(OUT / "organizer_only/blind_crosswalk.json", {"version": VERSION, "do_not_send_to_reviewers": True, "packets": crosswalk})
    save_json(OUT / "organizer_only/input_transcript_index.json", {"families": families, "cases": cases})
    save_json(OUT / "PACKET_HASHES.json", packet_hashes)

    put(OUT / "HUMAN_ADJUDICATION_TEMPLATE.md", """# 独立提交锁定与分歧裁决模板

HUMAN_REVIEW_PENDING。真实提交A：未收到；B：未收到。不得用本模板冒充已经完成裁决。

## 收件先锁原件

分别记录审查者代号、原包版本/哈希、本人填报起止时间与时区、实际收件UTC时间、原始提交文件名/字节数/SHA256、曝光与独立性声明。原件以只读副本保存到新submissions/raw目录，禁止覆盖或在原件上纠错。原包哈希与填写稿哈希不同是正常现象。
需要修改时保留新提交和时间，不替换旧稿；在双方首次提交都锁定前不互相讨论或展示对方结论。不收集不必要的真实姓名。
时间可信度分开记录：填写者报告的起止时间不是服务器认证时间；收件UTC由组织者实际收件时记录。当前不虚填任何时间、身份、签名或一致率。

A收件记录：____  原始提交SHA256：____  原包版本核验：____
B收件记录：____  原始提交SHA256：____  原包版本核验：____
两份真实独立提交均已锁定：[ ] 是（未发生前保持空白）

## 对齐与裁决（只在两份锁定之后）

组织者使用organizer_only/blind_crosswalk.json对齐两种顺序；配对方向不是裁决真值。为每个争议复制以下记录：

- 内部案例编号/前缀：____
- A原始判断及证据：____
- B原始判断及证据：____
- 分歧类型：自然性 / 目标标签 / 实体时间 / 未知与否定 / 规范与事实 / 对照构造 / 其他：____
- 裁决者实际代号、日期及是否已接触作者说明：____
- 原句定位、缺失前提或相容反例：____
- 裁决：保留A / 保留B / 双方均需更正 / 未解决：____
- 最终标签或未决原因：____
- 是否影响整组准入，是否需要另建修订版：____

裁决不得按作者预期强行把第三轮写成泄露或非泄露。必要规则不等于实际已发生，UNKNOWN不等于FALSE。关键问题未解决则不冻结正式真值，不运行正式比较。
原始一致数/分母、缺答数与争议数从两份真实材料计算；十八前缀不当十八个独立资产做泛化推断。当前全部指标为未计算，不是0%或100%。

## 准入结论（目前不填写）

三组各自：____
原始提交锁、最终标注文件SHA256、最终裁决文件SHA256：____
gold_frozen：false（只有完成实际流程并建立新锁定文件后才改变）
下一轮是否另获明确执行授权：____
""")

    identity_path = Path(r"D:/cg-hsw-7b-kgw-alignment-20261031-r9/inputs/direct_identity.json")
    old_identity = json.loads(identity_path.read_text(encoding="utf-8-sig"))
    assets = []
    for path, sha in old_identity["asset_files"].items():
        if path.endswith(".gguf") or path.endswith("llama-server.exe"):
            p = Path(path)
            assets.append({"path": path, "exists": p.exists(), "bytes": p.stat().st_size if p.exists() else None, "prior_R9_sha256": sha, "current_full_weight_hash_recomputed": False})
    save_json(OUT / "baseline_identity.json", {"scope": "Metadata only, no model or solver loading", "prior_identity_source": str(identity_path), "prior_identity_sha256": digest(identity_path.read_bytes()), "assets": assets, "symbolic_version": "SymPy 1.13.1", "transformers_version": "4.57.1", "NLI": "BLOCKED_NOT_LOCAL_AND_UNPINNED", "model_calls": 0, "solver_calls": 0})

    sources = [{"path": str(SOURCE / name), "sha256": sha} for name, sha in expected.items()]
    save_json(OUT / "SOURCE_MANIFEST.json", {"parent_commit": PARENT_COMMIT, "version": VERSION, "gold_frozen": False, "old_labels_reused": False, "files": sources, "checked_ranges": {"CANDIDATE_CASES.md": ["1-110", "111-230", "231-350", "351-407"], "DESIGN_REVIEW.md": ["1-102"], "sympy/logic/inference.py": ["1-120"]}})
    save_json(OUT / "PREPARATION_FAILURES.json", {"failures": [{"kind": "source_read_stdout", "error": "GBK cannot encode implication arrow; UTF-8 output retry completed", "source_changed": False}, {"kind": "web_metadata", "error": "HF API / SymPy version endpoint inaccessible; DOI403", "recovery": "Author model configuration and fixed-tag SymPy source checked; NLI remains unpinned"}], "no_model_or_algorithm_failures_observed": "NOT_RUN, not a claim of zero method failure"})
    save_json(OUT / "decision.json", {"decision": "ANALYZE", "confidence": 0.96, "review_status": "HUMAN_REVIEW_PENDING", "version": VERSION, "parent_commit": PARENT_COMMIT, "independent_families": 3, "cases": 6, "prefixes": 18, "author_logic_checks": {"PASS": 12, "FAIL": 0, "UNCERTAIN": 0, "scope": "Written conditional audit; not independent human truth or model accuracy"}, "naturalness_review": "UNCERTAIN_PENDING_HUMANS", "real_human_submissions": 0, "gold_frozen": False, "model_calls": 0, "solver_calls": 0, "algorithm_comparisons": 0, "new_algorithm_started": False, "completed": ["source_byte_verification", "written_logic_audit", "two_six_card_packets", "submission_and_adjudication_template", "baseline_preregistration", "one_UNTESTED_gap_hypothesis"], "incomplete": ["two_real_independent_reviews", "disagreement_adjudication", "formal_gold_freeze", "execution_adapter_and_technical_admission", "fair_baseline_comparison"], "blocking_reasons": ["No independent human admission", "Automatic baselines not executed; NLI unavailable; symbolic encoding needs audited faithful adaptation"], "next_action": "Two unexposed humans independently complete all six cards, then return both original submissions for hashing before adjudication", "allow_code_changes": False, "next_question": "Do independent reviewers confirm the contrast validity and naturalness without author labels or proofs?", "no_automatic_followup": True})
    put(OUT / "RESULT.md", """# 最小语义对照准入：ANALYZE

HUMAN_REVIEW_PENDING。源版本5d068b7828c53e2e5dedcd06408f1cab957b4c4e；三族/六例/十八前缀是设计规模。

## 实际完成

- [CASE_GATE_AUDIT.md](CASE_GATE_AUDIT.md)：逐组四项书面核查及删除反例。十二项作者检查有条件PASS，不是独立审查；三组自然性均待真人。
- [HUMAN_REVIEW_A.md](HUMAN_REVIEW_A.md)、[HUMAN_REVIEW_B.md](HUMAN_REVIEW_B.md)：各六张空白案例卡、全部十八前缀，不分一半；角色顺序不同，原问答和共同先验保持原字句。只发各自ZIP，不能发本结果目录。
- [HUMAN_ADJUDICATION_TEMPLATE.md](HUMAN_ADJUDICATION_TEMPLATE.md)：原始提交哈希/收件时间、对齐和分歧裁决位置，当前全部未填写。
- [BASELINE_PREREGISTRATION.md](BASELINE_PREREGISTRATION.md)：B0/B1-L/B1-S/B2/B3与阻塞的NLI组、固定提示/预算、失败记分和错误定位。
- [ALGORITHM_GAP_HYPOTHESES.md](ALGORITHM_GAP_HYPOTHESES.md)：仅一个UNTESTED状态保真假设，不是新算法提案。
- decision.json、SOURCE_MANIFEST.json、baseline_identity.json及organizer_only交叉表：版本、材料映射及实际可用性。文件哈希另见FILE_MANIFEST.json，材料检查见MATERIAL_QA.json（验证脚本完成后生成）。

## 三组判定

对象/时序组：条件内逻辑站得住；公开先验已排除重新绑定，缺导出绑定的负例仍有两种解释。
联锁组：条件内逻辑站得住；日志缺失不是物理正常，但原先验提示过强，不能据此声称复杂语义挑战。
材料组：只在准入规则语义内站得住；必要条件不能反推充分条件，也不能推出活动实际发生。

没有改写案例、迁移R38标签或把R44有限世界结果当NL测试。模型/求解器/防御算法运行均为0，未计算准确率、恢复率、人工一致率或教学效用。

## 能与不能支持

现有书面证据支持继续组织人类准入审查，不支持新算法贡献或正式真值冻结。B2若在正确表示下都能解，不能称闭包有缺口；B1若充分解决，停止在这三族提出新算法。仅单轮组失败说明缺历史，量化小模型失败不能证明成熟方法普遍不足。
三个条件改动都明显，数据仍小且合成；同一学生看到全部回答，无多Agent专属困难证据。模拟授权不是真实版权约束。

## 最短交接

将artifacts同名目录的盲审包_A.zip与盲审包_B.zip分别交给两名未看过作者证明的人；每人独立填完全部六卡，不讨论、不用AI。两份原始填写稿分别交回，先锁哈希，再处理分歧。
已经读过作者结论的人负责组织或裁决，不能充当未暴露盲标者。当前无任何真实提交。

本轮在材料与预注册完成后停止。不下载模型，不启动正式基线，不进行新算法或下一轮研究；无需等待真人期间自动工作。
""")
    for name, sha in expected.items():
        assert digest((SOURCE / name).read_bytes()) == sha
    print(json.dumps({"output": str(OUT), "delivery": str(DELIVERY), "status": "HUMAN_REVIEW_PENDING", "cases_per_reviewer": 6, "model_calls": 0}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
