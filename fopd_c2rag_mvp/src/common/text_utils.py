from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_LATIN_RE = re.compile(r"[a-zA-Z]+|\d+(?:\.\d+)?|[+\-*/^=()]+")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    tokens: list[str] = []
    for m in _LATIN_RE.finditer(text):
        tokens.append(m.group(0))
    for m in _CJK_RE.finditer(text):
        seg = m.group(0)
        tokens.extend(seg)
        if len(seg) > 1:
            tokens.extend(seg[i : i + 2] for i in range(len(seg) - 1))
        if len(seg) > 2:
            tokens.extend(seg[i : i + 3] for i in range(len(seg) - 2))
    return [t for t in tokens if t.strip()]


class SimpleTfidfVectorizer:
    def __init__(self) -> None:
        self.idf: dict[str, float] = {}

    def fit(self, texts: list[str]) -> "SimpleTfidfVectorizer":
        docs = [set(tokenize(t)) for t in texts]
        n_docs = max(len(docs), 1)
        df: Counter[str] = Counter()
        for doc in docs:
            df.update(doc)
        self.idf = {
            term: math.log((1 + n_docs) / (1 + freq)) + 1.0 for term, freq in df.items()
        }
        return self

    def transform_one(self, text: str) -> dict[str, float]:
        counts = Counter(tokenize(text))
        if not counts:
            return {}
        max_count = max(counts.values())
        vec = {
            term: (count / max_count) * self.idf.get(term, 1.0)
            for term, count in counts.items()
        }
        norm = math.sqrt(sum(v * v for v in vec.values()))
        if norm <= 0:
            return vec
        return {k: v / norm for k, v in vec.items()}

    def transform(self, texts: list[str]) -> list[dict[str, float]]:
        return [self.transform_one(t) for t in texts]

    def fit_transform(self, texts: list[str]) -> list[dict[str, float]]:
        self.fit(texts)
        return self.transform(texts)


def cosine_sparse(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return float(sum(v * b.get(k, 0.0) for k, v in a.items()))


def cosine_text(a: str, b: str) -> float:
    vec = SimpleTfidfVectorizer().fit([a, b])
    va, vb = vec.transform([a, b])
    return cosine_sparse(va, vb)


def lcs_length(a: str, b: str) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for ca in a:
        cur = [0]
        for j, cb in enumerate(b, start=1):
            if ca == cb:
                cur.append(prev[j - 1] + 1)
            else:
                cur.append(max(prev[j], cur[-1]))
        prev = cur
    return prev[-1]


def lcs_ratio(a: str, b: str) -> float:
    denom = max(min(len(a or ""), len(b or "")), 1)
    return lcs_length(a or "", b or "") / denom


def unique_ngram_overlap(a: str, b: str, n: int = 3) -> float:
    def grams(s: str) -> set[str]:
        s = re.sub(r"\s+", "", s or "")
        if len(s) < n:
            return {s} if s else set()
        return {s[i : i + n] for i in range(len(s) - n + 1)}

    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / max(len(ga), 1)


def difficulty_match(a: str, b: str) -> float:
    order = ["easy", "basic", "medium", "hard", "challenge"]
    zh_map = {"基础": "basic", "简单": "easy", "中等": "medium", "困难": "hard"}
    a = zh_map.get(str(a).lower(), str(a).lower())
    b = zh_map.get(str(b).lower(), str(b).lower())
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in order and b in order and abs(order.index(a) - order.index(b)) == 1:
        return 0.6
    return 0.2


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
