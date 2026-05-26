"""规则型水印攻击（不依赖额外 LLM）。"""

from __future__ import annotations

import random
import re
from typing import Any


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？\n])", text)
    return [p for p in parts if p.strip()]


def attack_delete_sentences(text: str, ratio: float = 0.2, seed: int | None = None) -> str:
    rng = random.Random(seed)
    sents = _split_sentences(text)
    if not sents:
        return text
    k = max(1, int(round(len(sents) * ratio)))
    idx = set(rng.sample(range(len(sents)), min(k, len(sents))))
    kept = [s for i, s in enumerate(sents) if i not in idx]
    return "".join(kept)


def attack_truncate(text: str, mode: str = "middle") -> str:
    sents = _split_sentences(text)
    if not sents:
        return text
    n = len(sents)
    if mode == "first_half":
        return "".join(sents[: max(1, n // 2)])
    if mode == "middle":
        lo = n // 4
        hi = lo + max(1, n // 2)
        return "".join(sents[lo:hi])
    return "".join(sents[: max(1, n // 2)])


def attack_mix_with_clean(text: str, clean_text: str, seed: int | None = None) -> str:
    rng = random.Random(seed)
    a = text.strip()
    b = clean_text.strip()
    if rng.random() < 0.5:
        return a + "\n\n" + b
    return b + "\n\n" + a


def attack_light_paraphrase(text: str, seed: int | None = None) -> str:
    rng = random.Random(seed)
    t = text
    reps = [
        ("因此", "所以"),
        ("所以", "因此"),
        ("首先", "第一"),
        ("此外", "另外"),
        ("另外", "此外"),
        ("我们可以", "不妨"),
        ("注意到", "可以看到"),
    ]
    for a, b in reps:
        if a in t and rng.random() < 0.4:
            t = t.replace(a, b, 1)
    t = re.sub(r"\s+", " ", t)
    return t


def attack_summary_like(text: str) -> str:
    sents = _split_sentences(text)
    if len(sents) <= 2:
        return text
    return "".join(sents[:2])


def run_all_attacks(text: str, clean_snippet: str, seed: int = 42) -> dict[str, str]:
    return {
        "delete_sentences": attack_delete_sentences(text, 0.2, seed),
        "truncate_middle": attack_truncate(text, "middle"),
        "mix_with_clean": attack_mix_with_clean(text, clean_snippet, seed),
        "light_paraphrase": attack_light_paraphrase(text, seed),
        "summary_like": attack_summary_like(text),
    }
