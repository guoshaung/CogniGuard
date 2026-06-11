"""术语 / 公式 / 数字占位符锁定与恢复。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# 公式：含 =、^、sqrt、frac、括号与常见数学符号的片段
_FORMULA_RE = re.compile(
    r"(?:"
    r"sqrt\s*\([^)]+\)|"
    r"frac\s*\{[^}]+\}\s*\{[^}]+\}|"
    r"[a-zA-Zα-ω]+\s*=\s*[^，。\s]+|"  # 简单赋值式
    r"y\s*=\s*\([^)]+\)\s*\^?\s*\d*|"
    r"\([^)]+\)\s*\^\s*[\d\-+]+|"
    r"x\s*=\s*[\d\-+]+"
    r")",
    re.UNICODE,
)

# 数字：整数、小数、负号、简单分数
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?|(?:\d+)\s*/\s*(?:\d+)")


@dataclass
class PlaceholderMap:
    formulas: dict[str, str] = field(default_factory=dict)
    terms: dict[str, str] = field(default_factory=dict)
    numbers: dict[str, str] = field(default_factory=dict)

    def all_placeholders(self) -> list[str]:
        return sorted(
            list(self.formulas) + list(self.terms) + list(self.numbers),
            key=len,
            reverse=True,
        )


def _unique_key(prefix: str, idx: int) -> str:
    return f"<{prefix}_{idx}>"


def protect_spans(
    text: str,
    terms: list[str],
    formulas: list[str],
    numbers: list[str],
) -> tuple[str, PlaceholderMap]:
    """将保护片段替换为占位符；长串优先，避免子串冲突。"""
    literal_seen: set[str] = set()
    raw: list[tuple[int, int, str, str]] = []  # start, end, kind, literal

    def add_raw(s: int, e: int, kind: str, literal: str) -> None:
        raw.append((s, e, kind, literal))

    for t in sorted({x for x in terms if x}, key=len, reverse=True):
        if t in literal_seen:
            continue
        literal_seen.add(t)
        for m in re.finditer(re.escape(t), text):
            add_raw(m.start(), m.end(), "TERM", t)

    for f in sorted({x for x in formulas if x}, key=len, reverse=True):
        if f in literal_seen:
            continue
        literal_seen.add(f)
        for m in re.finditer(re.escape(f), text):
            add_raw(m.start(), m.end(), "FORMULA", f)

    for m in _FORMULA_RE.finditer(text):
        frag = m.group(0)
        if frag in literal_seen or len(frag) < 3:
            continue
        literal_seen.add(frag)
        add_raw(m.start(), m.end(), "FORMULA", frag)

    for n in sorted({x for x in numbers if x}, key=len, reverse=True):
        if n in literal_seen:
            continue
        literal_seen.add(n)
        for m in re.finditer(re.escape(n), text):
            add_raw(m.start(), m.end(), "NUM", n)

    for m in _NUMBER_RE.finditer(text):
        frag = m.group(0)
        if frag in literal_seen:
            continue
        literal_seen.add(frag)
        add_raw(m.start(), m.end(), "NUM", frag)

    raw.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    kept_meta: list[tuple[int, int, str, str]] = []
    last_end = -1
    for s, e, kind, lit in raw:
        if s >= last_end:
            kept_meta.append((s, e, kind, lit))
            last_end = e

    if not kept_meta:
        return text, PlaceholderMap()

    kept_meta.sort(key=lambda x: x[0])
    pmap = PlaceholderMap()
    fi = ti = ni = 0
    pieces: list[tuple[int, int, str]] = []
    for s, e, kind, lit in kept_meta:
        if kind == "TERM":
            ph = _unique_key("TERM", ti)
            pmap.terms[ph] = lit
            ti += 1
        elif kind == "FORMULA":
            ph = _unique_key("FORMULA", fi)
            pmap.formulas[ph] = lit
            fi += 1
        else:
            ph = _unique_key("NUM", ni)
            pmap.numbers[ph] = lit
            ni += 1
        pieces.append((s, e, ph))

    out: list[str] = []
    pos = 0
    for s, e, ph in pieces:
        out.append(text[pos:s])
        out.append(ph)
        pos = e
    out.append(text[pos:])
    return "".join(out), pmap


def restore_spans(generated_text: str, placeholder_map: PlaceholderMap) -> str:
    """将占位符恢复为原始片段。"""
    t = generated_text
    for ph in placeholder_map.all_placeholders():
        if ph in t:
            val = (
                placeholder_map.formulas.get(ph)
                or placeholder_map.terms.get(ph)
                or placeholder_map.numbers.get(ph)
                or ""
            )
            t = t.replace(ph, val)
    return t


def normalize_placeholder_tokens(text: str, placeholder_map: PlaceholderMap) -> str:
    """把小模型常输出的 `<NUM_0 >`、`<term_0>`、`NUM_0`、`` `NUM_0` `` 等纠正为规范 `<NUM_0>`。"""
    t = text
    for ph in placeholder_map.all_placeholders():
        m = re.match(r"^<([A-Z]+)_(\d+)>$", ph)
        if not m:
            continue
        prefix, idx = m.group(1), m.group(2)
        pat = re.compile(rf"<\s*{prefix}\s*_\s*{re.escape(idx)}\s*>", re.IGNORECASE)
        t = pat.sub(ph, t)
    for ph in placeholder_map.all_placeholders():
        m = re.match(r"^<([A-Z]+)_(\d+)>$", ph)
        if not m:
            continue
        prefix, idx = m.group(1), m.group(2)
        t = re.sub(
            rf"`\s*{prefix}\s*_\s*{re.escape(idx)}\s*`",
            ph,
            t,
            flags=re.IGNORECASE,
        )
        bare = re.compile(rf"(?<![<A-Za-z0-9_]){prefix}_{re.escape(idx)}(?!>)(?![A-Za-z0-9_])", re.IGNORECASE)
        t = bare.sub(ph, t)
    return t


def placeholders_intact(text: str, placeholder_map: PlaceholderMap) -> bool:
    normalized = normalize_placeholder_tokens(text, placeholder_map)
    for ph in placeholder_map.all_placeholders():
        if ph not in normalized:
            return False
    return True


def extract_protected_spans(
    sample: dict[str, Any],
    extra_terms_file: list[str] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """合并样例字段、术语表与从题干/草稿中抽取的数字。"""
    terms = list(sample.get("protected_terms") or [])
    formulas = list(sample.get("protected_formulas") or [])
    numbers = list(sample.get("protected_numbers") or [])
    if extra_terms_file:
        terms.extend(extra_terms_file)
    q = sample.get("question") or ""
    d = sample.get("draft_answer") or ""
    for m in _NUMBER_RE.finditer(q):
        numbers.append(m.group(0))
    # 去重保持顺序
    def uniq(xs: list[str]) -> list[str]:
        out: list[str] = []
        s: set[str] = set()
        for x in xs:
            x = str(x).strip()
            if x and x not in s:
                s.add(x)
                out.append(x)
        return out

    return uniq(terms), uniq(formulas), uniq(numbers)
