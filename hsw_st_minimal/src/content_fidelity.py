"""教学语义保真：防止「二次函数→椭圆」类漂移；防止与草稿几乎无异导致统计水印失效。"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

# 草稿/题干未出现时，输出里不应凭空出现的高中数学「另一类对象」(典型模型胡编)
DEFAULT_DRIFT_MARKERS = (
    "椭圆",
    "双曲线",
    "焦距",
    "准线",
    "离心率",
    "渐近线",
    "抛物线的焦点",
)


@dataclass
class FidelityConfig:
    enabled: bool = True
    max_attempts: int = 5
    # SequenceMatcher 比值高于此视为「几乎复制粘贴」，不利于植入水印信号
    max_draft_similarity: float = 0.985
    # protected_terms 至少要有多少比例出现在最终正文（1.0 = 全部）
    min_term_coverage: float = 1.0
    #  persistent 概念漂移时是否退回草稿（宁可 Z 低也不输出错误概念）
    fallback_to_draft_on_drift: bool = True


def parse_fidelity(cfg: dict[str, Any]) -> FidelityConfig:
    raw = (cfg.get("experiment") or {}).get("content_fidelity") or {}
    return FidelityConfig(
        enabled=bool(raw.get("enabled", True)),
        max_attempts=max(1, int(raw.get("max_attempts", 5))),
        max_draft_similarity=float(raw.get("max_draft_similarity", 0.985)),
        min_term_coverage=float(raw.get("min_term_coverage", 1.0)),
        fallback_to_draft_on_drift=bool(raw.get("fallback_to_draft_on_drift", True)),
    )


def _reference_context(draft: str, question: str) -> str:
    return f"{draft or ''}\n{question or ''}"


def has_forbidden_concept_drift(output: str, draft: str, question: str, markers: tuple[str, ...] | None = None) -> bool:
    ref = _reference_context(draft, question)
    markers = markers or DEFAULT_DRIFT_MARKERS
    for m in markers:
        if m in output and m not in ref:
            return True
    return False


def term_coverage_ratio(output: str, terms: list[str]) -> float:
    if not terms:
        return 1.0
    hits = sum(1 for t in terms if t and str(t).strip() and str(t).strip() in output)
    return hits / len(terms)


def draft_too_similar(output: str, draft: str, max_similarity: float) -> bool:
    d, o = (draft or "").strip(), (output or "").strip()
    if len(d) < 12:
        return False
    return SequenceMatcher(None, d, o).ratio() >= max_similarity


def fidelity_violations(
    output: str,
    draft: str,
    question: str,
    terms: list[str],
    fc: FidelityConfig,
) -> list[str]:
    bad: list[str] = []
    if has_forbidden_concept_drift(output, draft, question):
        bad.append("concept_drift")
    if term_coverage_ratio(output, terms) + 1e-9 < fc.min_term_coverage:
        bad.append("missing_protected_terms")
    if draft_too_similar(output, draft, fc.max_draft_similarity):
        bad.append("too_similar_to_draft")
    return bad


def build_extra_system_constraints(question: str, draft: str, terms: list[str]) -> str:
    """附加到 system，强化最小改动与禁止换题。"""
    lines: list[str] = []
    if terms:
        must = "、".join(str(t) for t in terms[:14] if t)
        if must:
            lines.append(f"以下术语必须在输出中出现且语义不变（不可替换为近义词以外的数学对象）：{must}")
    ref = _reference_context(draft, question)
    if any(k in ref for k in ("二次函数", "顶点式", "顶点坐标", "一元二次", "判别式", "对称轴")):
        lines.append(
            "本题语境为二次函数或一元二次方程时：禁止改写成椭圆、双曲线、焦距、准线等其它曲线章节的内容。"
        )
    return "\n".join(lines)
