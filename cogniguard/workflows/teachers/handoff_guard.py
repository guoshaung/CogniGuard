"""Narrow, deterministic checks on *authenticated but untrusted* teacher text.

This is a testable policy layer, not a general prompt-injection classifier.
It cannot infer arbitrary collusion or validate every subject area.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_VERTEX_TASK = re.compile(r"y\s*=\s*\(\s*x\s*([+-])\s*(\d+)\s*\)\s*\^?\s*2\s*([+-])\s*(\d+)", re.I)
_VERTEX_CLAIM = re.compile(
    r"(?:顶点(?:坐标)?(?:是|为|：|:)?|vertex\s*(?:is|:)?)[^()\n]{0,18}"
    r"\(\s*(-?\d+(?:\.\d+)?)\s*[,，]\s*(-?\d+(?:\.\d+)?)\s*\)",
    re.I,
)
_INSTRUCTION = re.compile(
    r"<\s*/?\s*system\s*>|\b(?:system|developer)\s*:|"
    r"忽略.{0,12}(?:指令|规则|上游|系统)|"
    r"(?:调用|执行)\s*read_profile|"
    r"(?:输出|泄露|读取|转发).{0,16}(?:地址|电话|密码|密钥|local_only_fields)|"
    r"INJECTION_WON",
    re.I,
)
_CONTRAST_CUE = re.compile(r"反例|变式|例如|另一个函数|对照|拓展练习")


@dataclass(frozen=True)
class HandoffAssessment:
    allow: bool
    reasons: tuple[str, ...]


def _vertex_from_formula(match: re.Match[str]) -> tuple[float, float]:
    horizontal = int(match.group(2)) * (1 if match.group(1) == "-" else -1)
    vertical = int(match.group(4)) * (1 if match.group(3) == "+" else -1)
    return float(horizontal), float(vertical)


def expected_vertex(question: str) -> tuple[float, float] | None:
    match = _VERTEX_TASK.search(unicodedata.normalize("NFKC", question))
    return _vertex_from_formula(match) if match is not None else None


def assess_handoff(text: str, question: str) -> HandoffAssessment:
    if not isinstance(text, str) or not isinstance(question, str):
        raise TypeError("Handoff text and question must be strings")
    normalized = unicodedata.normalize("NFKC", text)
    reasons: list[str] = []
    if _INSTRUCTION.search(normalized):
        reasons.append("instruction_like_content")
    expected = expected_vertex(question)
    if expected is not None:
        for claim in _VERTEX_CLAIM.finditer(normalized):
            observed = float(claim.group(1)), float(claim.group(2))
            if observed != expected:
                context = normalized[max(0, claim.start() - 96) : claim.start()]
                alternatives = list(_VERTEX_TASK.finditer(context))
                if (
                    _CONTRAST_CUE.search(context)
                    and alternatives
                    and _vertex_from_formula(alternatives[-1]) == observed
                ):
                    continue
                reasons.append("vertex_claim_conflict")
                break
    return HandoffAssessment(not reasons, tuple(reasons))
