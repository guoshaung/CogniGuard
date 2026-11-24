"""Fixed prompts and the attacker-output parser."""

from __future__ import annotations

import json
import re

PARAPHRASE_TEMPERATURE = 0.7
ATTACK_TEMPERATURE = 0.7
ATTACK_SAMPLES = 5


def paraphrase_messages(text: str) -> list[dict]:
    return [
        {"role": "system", "content": "You rewrite short revision hints. Output only the rewritten hint."},
        {"role": "user", "content": (
            "把下面这句复习提示改写成老师在复习课上会说的一两句自然的话。"
            "必须保留原句的全部事实，不得添加任何新的事实，不要逐字照抄。"
            "用英文输出，只输出改写后的话。\n\n原句：" + text)},
    ]


def attack_messages(candidates: str, view: str | None) -> list[dict]:
    hint = view if view else "（没有任何提示）"
    return [
        {"role": "system", "content": "You judge which question will be set on a final exam. Reply with JSON only."},
        {"role": "user", "content": (
            "下面是 8 道候选题，期末考的是其中一道。\n\n" + candidates +
            "\n\n老师在复习课上说过的话：" + hint +
            "\n\n期末考的是哪一道？只输出 JSON：{\"choice\": <1-8 的编号>, "
            "\"probs\": [8 个概率，依次对应编号 1 到 8，总和为 1]}")},
    ]


def parse_attack(content: str | None) -> dict | None:
    """Return {"choice": int, "probs": [8 floats]} or None when the reply is not usable."""
    if not content:
        return None
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        choice = int(data["choice"])
        probs = [float(x) for x in data["probs"]]
    except (ValueError, KeyError, TypeError):
        return None
    if not 1 <= choice <= 8 or len(probs) != 8 or any(p < 0 for p in probs) or sum(probs) <= 0:
        return None
    total = sum(probs)
    return {"choice": choice, "probs": [p / total for p in probs]}
