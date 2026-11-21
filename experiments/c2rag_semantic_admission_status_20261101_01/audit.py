"""Read-only admission check and new status documents; no baseline execution."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.paths import PROJECT_ROOT, RESULTS_DIR

HERE = Path(__file__).resolve().parent
OUT = RESULTS_DIR / HERE.name
PRIOR = RESULTS_DIR / "c2rag_minimal_semantic_gate_20261031_01"
PACKETS = PROJECT_ROOT / "artifacts/c2rag_minimal_semantic_gate_20261031_01"
VERSION = "SEMANTIC-GATE-20261031-01"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def put(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content.encode("utf-8") if isinstance(content, str) else content)


def save_json(path: Path, data) -> None:
    put(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    assert not OUT.exists(), "Do not overwrite a prior admission audit"
    old_manifest = read_json(PRIOR / "FILE_MANIFEST.json")
    verified = []
    for row in old_manifest["files"]:
        p = PROJECT_ROOT / row["path"]
        actual = sha(p.read_bytes()) if p.is_file() else None
        verified.append({"path": row["path"], "expected_sha256": row["sha256"], "actual_sha256": actual, "matches": actual == row["sha256"]})
    assert all(r["matches"] for r in verified), "Evidence changed; stop for manual inspection"

    scopes = [RESULTS_DIR, PROJECT_ROOT / "artifacts", PROJECT_ROOT / "docs/reports"]
    skip = {"node_modules", "__pycache__", ".git", "source_snapshot", "organizer_checks", "_root_workspaces_20261023"}
    known = {str((PROJECT_ROOT / r["path"]).resolve()) for r in old_manifest["files"]}
    known.add(str((PRIOR / "FILE_MANIFEST.json").resolve()))
    version_hits, name_hits, skipped_large = [], [], 0
    inspected_text_files = 0
    for scope in scopes:
        for folder, dirs, files in os.walk(scope):
            dirs[:] = [d for d in dirs if d not in skip]
            for name in files:
                path = Path(folder) / name
                lower = name.lower()
                if any(word in lower for word in ("human_review", "adjudicat", "submission", "盲审", "填写", "裁决", "提交", "gold_freeze")):
                    name_hits.append({"path": str(path.relative_to(PROJECT_ROOT)), "bytes": path.stat().st_size, "classification": "CURRENT_KNOWN_MATERIAL" if str(path.resolve()) in known else "OTHER_OR_UNVERIFIED_VERSION_NOT_ADMISSIBLE_AS_CURRENT_REVIEW"})
                if path.suffix.lower() not in {".md", ".json", ".txt", ".csv"}:
                    continue
                if path.stat().st_size > 524288:
                    skipped_large += 1
                    continue
                inspected_text_files += 1
                content = path.read_text(encoding="utf-8-sig", errors="replace")
                if VERSION in content:
                    version_hits.append({"path": str(path.relative_to(PROJECT_ROOT)), "sha256": sha(path.read_bytes()), "known_prior_material": str(path.resolve()) in known})
    unknown_version_hits = [h for h in version_hits if not h["known_prior_material"]]
    assert not unknown_version_hits, "Potential same-version submission found; inspect it before classifying"

    packet_rows = []
    for reviewer in ("A", "B"):
        p = PACKETS / f"盲审包_{reviewer}.zip"
        with zipfile.ZipFile(p) as archive:
            filename = f"HUMAN_REVIEW_{reviewer}.md"
            assert set(archive.namelist()) == {filename, "PACKET_VERSION.json"}
            raw = archive.read(filename)
            metadata = json.loads(archive.read("PACKET_VERSION.json"))
            assert raw == (PRIOR / filename).read_bytes()
            assert sha(raw) == metadata["sha256"]
            text = raw.decode("utf-8")
            checked_boxes = len(re.findall(r"(?m)^\s*-\s*\[[xX]\]", text))
            assert checked_boxes == 0
            assert metadata["status"] == "HUMAN_REVIEW_PENDING"
            packet_rows.append({"reviewer": reviewer, "path": str(p.relative_to(PROJECT_ROOT)), "zip_sha256": sha(p.read_bytes()), "md_sha256": sha(raw), "cards": 6, "prefix_questions": 18, "checked_response_boxes": checked_boxes, "is_submission": False})
    prior_decision = read_json(PRIOR / "decision.json")
    assert prior_decision["gold_frozen"] is False
    template = (PRIOR / "HUMAN_ADJUDICATION_TEMPLATE.md").read_text(encoding="utf-8")
    assert "真实提交A：未收到；B：未收到" in template

    OUT.mkdir(parents=True)
    save_json(OUT / "SOURCE_INTEGRITY.json", {"prior_manifest_sha256": sha((PRIOR / "FILE_MANIFEST.json").read_bytes()), "checked_files": len(verified), "all_match": True, "old_files_modified": False, "records": verified})
    save_json(OUT / "HUMAN_REVIEW_SEARCH.json", {"client_date": "2026-11-01", "version": VERSION, "scopes": [str(s.relative_to(PROJECT_ROOT)) for s in scopes], "file_name_search_candidates": name_hits, "version_content_matches": version_hits, "unknown_same_version_files": unknown_version_hits, "inspected_text_files": inspected_text_files, "text_file_limit_bytes": 524288, "skipped_large_text_files": skipped_large, "excluded_directory_names": sorted(skip), "in_scope_recorded_completed_human_submissions": 0, "adjudication_completed": False, "gold_frozen": False, "limits": "Scoped search, not a claim that no person has worked offline. External unnamed files and files not returned to this workspace cannot be certified; old R38/R36 files do not satisfy this version."})
    save_json(OUT / "REVIEW_PACKET_CHECK.json", {"status": "ORIGINAL_BLANK_PACKETS_UNCHANGED", "packets": packet_rows, "exposure_limit": "The author design and proofs are public at the parent commit. Reviewers must disclose prior exposure. No universal blindness or model-contamination guarantee is asserted."})

    family_names = {"1": "跨轮实体与可变状态", "2": "未知与物理否定", "3": "规范性必要依赖"}
    records = []
    for group in ("1", "2", "3"):
        for condition in ("P", "N"):
            for method in ("B0", "B1", "B2", "B3"):
                records.append({"case_id": group + condition, "family": family_names[group], "method": method, "planned_prefixes": 3, "executed_prefixes": 0, "status": "NOT_RUN_ADMISSION_BLOCKED", "prediction": None, "gold_label": None, "accuracy": None, "method_error_layer": None, "blocking_layer": "INDEPENDENT_HUMAN_ADMISSION_AND_GOLD_FREEZE", "note": "B1-L/B1-S are planned subarms; neither executed" if method == "B1" else "No raw model/solver output exists because execution was not authorized by the gate"})
    save_json(OUT / "BASELINE_NOT_RUN_STATUS.json", {"record_type": "administrative_status_not_predictions", "rows": records, "CI": None, "correctness_or_recovery_metrics": None})
    table = io.StringIO(newline="")
    writer = csv.DictWriter(table, fieldnames=list(records[0]))
    writer.writeheader()
    writer.writerows(records)
    put(OUT / "BASELINE_NOT_RUN_STATUS.csv", table.getvalue())

    put(OUT / "ADMISSION_CHECK.md", """# 阶段一核查：未通过

日期2026-11-01；固定材料版本SEMANTIC-GATE-20261031-01，源参考提交5d068b7828c53e2e5dedcd06408f1cab957b4c4e。

1. **逻辑审查：仅作者层面条件通过。** 上一轮CASE_GATE_AUDIT中三组各四项为PASS；自然性均待真人。没有独立真人确认，不把十二项作者推演变成正式准入。
2. **两份真人提交：未收到可核验记录。** 限定扫描var/results、artifacts、docs/reports中的版本文本及审查/提交文件名，仅发现本版原始空白材料；其他旧版本不计入。没有用户本轮提交附件。不能断言任何人线下没有填写，只能说未收到可用于准入的原稿。
3. **裁决：未完成。** 仅有未填写模板，无两份原始提交SHA锁、收件记录或实际裁决。
4. **冻结：材料版本已锁，正式真值未冻。** 25条既有清单全部匹配，A/B两个ZIP及MD原字节未变；decision.json仍为gold_frozen=false。空白材料的哈希不是人工真值的哈希。
5. **污染与泄漏：未发现包内额外作者答案；仍有外部曝光风险。** 包只含自己的MD和版本JSON，没有交叉表或作者证明。作者原设计已在公开仓库发布，不能保证审查者未读过；须真人声明。旧R38表、Excel临时锁及R36 adjudications均属于其他版本，不迁移标签。当前没有模型运行，不能产生本轮测试调参结果；也不认证全网不存在数据污染。

结论：阶段一NOT_PASSED。阶段二四种方法以及B1两个子组全部NOT_RUN_ADMISSION_BLOCKED，不启动任何模型、求解器或服务。阶段三没有新的方法误差可归因。

尚存技术条件也未消失：B2保真关系编码和执行adapter尚待审查，NLI权重/完整revision未准入；不能声称真人一交稿就已有完整可运行的成熟方法比较。

原案例没有被改写或替换。对象绑定、记录状态和模态风险维持上一轮结论，未增加新的成功/失败实验样本。
""")
    put(OUT / "PENDING_HUMAN_REVIEW.md", """# 交给两名真人的最少操作

HUMAN_REVIEW_PENDING。只发送各自原样ZIP，不发送本结果目录或作者分析。

- A：D:/pycharm/CogniGuard/artifacts/c2rag_minimal_semantic_gate_20261031_01/盲审包_A.zip
- B：D:/pycharm/CogniGuard/artifacts/c2rag_minimal_semantic_gate_20261031_01/盲审包_B.zip

每人各填全部六卡/十八前缀，按轮阅读，不讨论、不用AI。保留版本及起止时间，填完另存为原始填写稿，分别发回。先锁定两份原稿SHA256和收件时间，再处理分歧。
已经看过作者预期、证明或反例的人做组织/裁决，不冒充未暴露盲审者。当前可见卡片均为空，不能当作已经提交。

可直接填写的原文件：
D:/pycharm/CogniGuard/var/results/c2rag_minimal_semantic_gate_20261031_01/HUMAN_REVIEW_A.md
D:/pycharm/CogniGuard/var/results/c2rag_minimal_semantic_gate_20261031_01/HUMAN_REVIEW_B.md

实际裁决位置：上一轮HUMAN_ADJUDICATION_TEMPLATE.md；未收稿前不填写结果，不改变gold_frozen。
""")
    put(OUT / "FAILURES_AND_LIMITS.md", """# 阻塞与未证明事项

本轮失败发生在研究准入，不是B0/B1/B2/B3语义能力失败。

- 缺两份当前版本真人提交、独立性/曝光声明、裁决和正式真值锁。
- 三组只有作者条件逻辑复核：对象组须保持绑定不变；联锁组的公开先验已强提示缺记录语义；材料组只讨论准入规则，不是事实已发生。没有独立自然性结论。
- 没有任何方法输出，无法归因实体状态、否定、模态、提示格式或评分错误。各方法accuracy为null，不是0；NOT_RUN不是UNKNOWN预测或防御成功。
- B2保真编码与自动adapter未实现/验收；预留NLI不具备本地权重及完整不可变revision。量化7B即使将来失败，也不能证明成熟方法普遍不足。
- 原设计/证明已经公开；盲包不含作者标签不等于能证明所有审查者未曝光。旧R38数据不移作新真值；三个资产和十八相关前缀不能支撑泛化置信区间。

仅保留上一轮H-STATE为UNTESTED：增量状态是否错误压缩未知、实体和时点。它还可能完全被标准解析、带来源状态和精确推理解决，尚无独立算法贡献证据。没有新增第二个假设。

停止当前算法追求的反证维持不变：关键对照不能获独立确认；成熟完整历史方法解决全部已准入例；或者错误只是已知绑定、状态schema、格式/评分工程问题。不得换样本追求失败。
""")
    put(OUT / "RESULT.md", """# C²-RAG 2026-11-01：准入仍阻塞，正式基线未启动

**决策ANALYZE / HUMAN_REVIEW_PENDING。** 本轮只完成阶段一的证据核查；阶段一未通过，因此未进入阶段二或产生阶段三算法比较结论。不是实验失败，也不是新方向失败。

## 实际证据

上一轮RESULT、CASE_GATE_AUDIT、decision、人工裁决模板和完整BASELINE_PREREGISTRATION均已读取；上一轮FILE_MANIFEST的25条文件哈希全部匹配，源案例、盲包、提示和预注册未改。
同版卡片没有填写，未发现可核验的两份提交、裁决记录或正式真值锁。扫描范围与限制见HUMAN_REVIEW_SEARCH.json；材料核验见SOURCE_INTEGRITY.json和REVIEW_PACKET_CHECK.json。来源三组只具有作者逻辑条件PASS，自然性未准入。

## 四种基线的逐案例状态

- 1P、1N：B0/B1/B2/B3均NOT_RUN_ADMISSION_BLOCKED；暂无实体状态更新误差可报告。
- 2P、2N：四组均NOT_RUN_ADMISSION_BLOCKED；暂无“未记录→未发生”方法误判可报告。
- 3P、3N：四组均NOT_RUN_ADMISSION_BLOCKED；暂无规范模态/必要充分条件方法误判可报告。

24条case×method行政状态见BASELINE_NOT_RUN_STATUS.csv/JSON；每条计划有3前缀，实际执行0。不是24条预测，也没有72个独立样本。预测、真值、准确率与错误层均为null；B1-L/B1-S也均未运行。
本轮模型调用0、求解器调用0、付费0、GPU任务0、训练0。没有伪造原始模型输入输出或将作者证明作为B2运行成绩。

## 算法空间

没有新数据支持或否定成熟方法能力，不能说B1/B3已解决，也不能说发现缺口。只有既有H-STATE保持UNTESTED；自然语言表示/增量维护错误只有在真正公平比较后才能分开，不能直接宣布新推理算法。
不重启A1/A2/B；不改测试集、不继承R38标签、不以R44有限世界诊断冒充NL结果。三族样本不足以作一般教学场景或多Agent专属性推断。

## 唯一下一步与停止

按PENDING_HUMAN_REVIEW.md把原A/B包分别给两名未曝光真人，每人各做全部六卡并独立回传；先锁原稿再裁决。完成前不进入正式实验。技术adapter/编码准入仍须在之后核验，不因收到两份表就自动假定全部条件已具备。
本轮结果及必要上一轮材料按append-only同步，新目录保留状态与哈希；不同版本均不覆盖。远端SHA及回读收据单独记录，避免自引用。

本轮到此结束，不自动等待、运行模型或启动下一轮研究。
""")
    save_json(OUT / "decision.json", {"decision": "ANALYZE", "client_date": "2026-11-01", "confidence_in_gate_decision": 0.99, "source_version": VERSION, "source_reference_commit": "5d068b7828c53e2e5dedcd06408f1cab957b4c4e", "phase1": "NOT_PASSED", "phase2": "NOT_RUN_ADMISSION_BLOCKED", "phase3": "NO_NEW_EXPERIMENTAL_EVIDENCE", "recorded_human_submissions_in_scope": 0, "adjudication_completed": False, "gold_frozen": False, "material_manifest_all_25_match": True, "model_calls": 0, "solver_calls": 0, "training": 0, "paid_API": 0, "GPU_tasks": 0, "method_accuracy": None, "new_algorithms": 0, "hypotheses": [{"id": "H-STATE", "status": "UNTESTED", "source": "previous ALGORITHM_GAP_HYPOTHESES.md", "new_support_this_round": False}], "next_action": "Receive two independent complete six-card reviews, lock original submissions and adjudicate before reconsidering execution", "allow_algorithm_changes": False, "no_automatic_followup": True})
    for row in verified:
        assert sha((PROJECT_ROOT / row["path"]).read_bytes()) == row["expected_sha256"]
    files = [p for parent in (OUT, HERE) for p in parent.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    save_json(OUT / "FILE_MANIFEST.json", {"scope": "This admission status audit, excluding this manifest itself", "files": [{"path": str(p.relative_to(PROJECT_ROOT)), "bytes": p.stat().st_size, "sha256": sha(p.read_bytes())} for p in sorted(files)]})
    print(json.dumps({"output": str(OUT), "decision": "ANALYZE", "prior_files_checked": len(verified), "all_unchanged": True, "unknown_same_version_files": 0, "recorded_human_submissions": 0, "model_or_solver_calls": 0, "baseline_status_rows_not_predictions": len(records)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
