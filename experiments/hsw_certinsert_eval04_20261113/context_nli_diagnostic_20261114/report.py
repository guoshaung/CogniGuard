"""Verify scored evidence, match PDTB Appendix A, and write the diagnostic report."""

import json
import re
import unicodedata

from context_nli import HERE, OUTPUT, THRESHOLD, digest, read_json


def connective_pages():
    # The LDC PDF's printed pp. 65–70 are PDF pages 70–75.
    from pypdf import PdfReader

    pdf = PdfReader(OUTPUT / "pdtb-annotation-manual.pdf")
    pages = {}
    row_pattern = re.compile(r"^\s*(\S+(?:\s{1,3}\S+)*?)\s{4,}\S+.*\s+\d+\s*$")
    for index in range(69, 75):
        layout = pdf.pages[index].extract_text(extraction_mode="layout")
        start = layout.index("Explicit  Connective")
        for line in layout[start:].splitlines()[1:]:
            row = row_pattern.match(line)
            if row and not line.lstrip().startswith("Table "):
                term = " ".join(unicodedata.normalize("NFKC", row[1]).casefold().split())
                assert term not in pages
                pages[term] = index - 4
    assert len(pages) == 100
    return pages


def main():
    run = read_json(OUTPUT / "RUN.json")
    lines = (OUTPUT / "forward_scores.jsonl").read_text(encoding="utf-8").splitlines()
    scores = {record["term"]: record["rows"] for record in map(json.loads, lines)}
    rows = run["results"]
    assert len(scores) == len(lines) == len(rows) == 55
    assert scores.keys() == {row["term"] for row in rows}
    for row in rows:
        detail = scores[row["term"]]
        assert len(detail) == len({item["sentence_id"] for item in detail}) == row["n"] == 100
        assert all(item["tokens"] <= 512 and 0 <= item["forward_probability"] <= 1 for item in detail)
        assert sum(item["forward_probability"] >= THRESHOLD for item in detail) == row["forward_passed"]
        paired = [item for item in detail if item["original_forward_probability"] is not None]
        assert len(paired) == row["paired_n"]
        assert sum(item["original_forward_probability"] >= THRESHOLD for item in paired) == row["paired_original_passed"]
        assert sum(item["forward_probability"] >= THRESHOLD for item in paired) == row["paired_context_passed"]
    pages = connective_pages()
    original = [row for row in rows if row["existing_candidate"]]
    assert len(original) == 47
    matched = sum(row["term"] in pages for row in original)
    paired_n = sum(row["paired_n"] for row in original)
    old_pass = sum(row["paired_original_passed"] for row in original)
    new_pass = sum(row["paired_context_passed"] for row in original)
    high = [f"`{row['term']}`（{row['forward_passed']}%）" for row in rows if row["forward_pass_rate"] >= .95]
    high_description = '、'.join(high) or '无'
    templates = {row["term"]: row for row in rows if row["template"]}
    max_tokens = max(item["tokens"] for detail in scores.values() for item in detail)
    skipped = sum(row["skipped_overlength"] for row in rows)
    output = [
        "# EVAL-04 开发诊断结果",
        "",
        f"55 个独立词条共完成 5,500 组正向 NLI，使用与阶段 0 同一权重和 tokenizer。达到 95% 正向通过率的词条为 {high_description}。原始阶段 0 仍停在流畅度筛选前，`L*` 未生成。",
        "",
        f"原句池 10,450 句，其中 5,370 句有同一文档且同样在旧句池内的紧邻前句。每词分母 100，阈值为模型蕴含概率 ≥0.9。实际最大 {max_tokens} token，因长度跳过 {skipped} 组。使用本地 {run['device'].upper()} FP32，未调用其他模型。",
        "",
        f"47 个原候选中共有 {paired_n:,} 个同词同句配对，无上下文时通过 {old_pass:,}/{paired_n:,}（{old_pass/paired_n:.1%}），加入上一句后通过 {new_pass:,}/{paired_n:,}（{new_pass/paired_n:.1%}），描述性差值 {(new_pass-old_pass)/paired_n*100:+.1f} 个百分点。分母是词条与句子的配对数，句子可跨词条重复。模型权重一致，旧分数为 CPU，新分数为 CUDA。完整新样本与原 100 句不完全相同，配对子集可减少样本差异。",
        "",
        f"PDTB 匹配 {matched}/47。使用 LDC 公布的 PDTB-2.0 Annotation Manual 附录 A 表 2–7，印刷页 65–70。以附录首列 100 个词形为准，只归一大小写和空白，不用近义词、词干、子串或附录 B 的变体补齐。‘是’表示词形出现过，未对这批句子的具体用法做话语关系标注。[PDTB-2.0 Annotation Manual，附录 A](https://catalog.ldc.upenn.edu/docs/LDC2008T05/manual/pdtb-annotation-manual.pdf#page=70)",
        "",
        "## 原 47 个候选",
        "",
        "旧正向列是保存的原 100 组单向通过率。配对列只比较在新旧两次均出现的原句。",
        "",
        "| 候选 | 上下文正向 | 旧正向 | 配对旧 → 新 | PDTB-2.0 附录 A |",
        "|---|---:|---:|---:|---|",
    ]
    for row in original:
        term = row["term"]
        pdtb = f"是，p. {pages[term]}" if term in pages else "否"
        output.append(f"| `{term}` | {row['forward_passed']}% | {row['original_full_forward_passed']}% | "
                      f"{row['paired_original_passed']}/{row['paired_n']} → "
                      f"{row['paired_context_passed']}/{row['paired_n']} | {pdtb} |")
    output.extend([
        "",
        "## 模板变体",
        "",
        "三列词频分母均为 3,568 个 R_build 文档。冻结 df 沿用阶段 0 的句首紧跟逗号定义。字面匹配在任意位置查找完整词形，可能包含非连接词用法。带逗号列保留任意位置匹配并要求随后为逗号。",
        "",
        "| 模板 | 冻结句首 df | 字面匹配文档 | 带逗号匹配文档 | 上下文正向 |",
        "|---|---:|---:|---:|---:|",
    ])
    for row in run["frequency"]:
        score = templates[row["template"].casefold()]["forward_passed"]
        output.append(f"| `{row['template']}` | {row['original_sentence_prefix_df']} | {row['literal']} | "
                      f"{row['with_comma']} | {score}% |")
    union = run["family_distinct_documents"]
    summed = {key: sum(row[key] for row in run["frequency"])
              for key in ("literal", "with_comma", "original_sentence_prefix_df")}
    output.extend([
        "",
        f"模板家族字面匹配并集 **{union['literal']}** 篇（成员之和 {summed['literal']}），带逗号匹配并集 **{union['with_comma']}** 篇（成员之和 {summed['with_comma']}）。同一文档可命中多个成员，计入并集时只计一次。冻结句首 df 的成员之和为 {summed['original_sentence_prefix_df']}，冻结文件未保存该口径的文档成员关系。",
        "",
        "## 复核",
        "",
        f"- PDTB 手册 PDF SHA-256 `{digest(OUTPUT / 'pdtb-annotation-manual.pdf')}`。",
        f"- 逐句正向分数 `forward_scores.jsonl` SHA-256 `{digest(OUTPUT / 'forward_scores.jsonl')}`。",
        "- `RUN.json` 记录运行版本、模型文件哈希、每词分母、模板文档数和配对计数。全部分数可依据已冻结的 R_build 句子编号回查。",
        "- 复跑用独立工作树，保留当前结果。将冻结的 `stage0` 数据放在原相对路径，用已安装 PyTorch/Transformers 的本地 Python 执行 `python -B context_nli.py --device cuda`。报告脚本应在该工作树中运行，在新运行目录准备 LDC 手册 PDF `pdtb-annotation-manual.pdf`，并将发布的 `RESULT.md` 保留在原工作树，用有 `pypdf` 的 Python 执行 `python -B report.py`。",
        "- 本轮未读取 T1–T6 内容，未修改冻结规则与词表，未进入后续阶段。",
    ])
    with (HERE / "RESULT.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(output) + "\n")


if __name__ == "__main__":
    main()
