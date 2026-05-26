"""水印检测：全文 Z-score 与滑动窗口局部检测。"""

from __future__ import annotations

from typing import Any

from watermark_logits_processor import greenlist_for_prefix


def _count_green_stats(
    token_ids: list[int],
    vocab_size: int,
    gamma: float,
    key: str,
    window_size: int,
) -> tuple[int, int]:
    """对位置 j>=1 的 token，用前缀 context 计算绿色集合并统计命中。"""
    n_green = 0
    checked = 0
    for j in range(1, len(token_ids)):
        prefix = token_ids[:j]
        green = greenlist_for_prefix(prefix, vocab_size, gamma, key, window_size)
        tid = token_ids[j]
        if tid in green:
            n_green += 1
        checked += 1
    return n_green, checked


def _z_score(n_green: int, T: int, gamma: float) -> float:
    if T <= 0:
        return 0.0
    import math

    exp = gamma * T
    var = T * gamma * (1.0 - gamma)
    if var <= 0:
        return 0.0
    return (n_green - exp) / math.sqrt(var)


def detect_full_text(
    text: str,
    tokenizer: Any,
    vocab_size: int,
    gamma: float,
    key: str,
    window_size: int,
    z_threshold: float,
) -> dict[str, Any]:
    token_ids = tokenizer.encode(text, add_special_tokens=False)
    n_green, T = _count_green_stats(token_ids, vocab_size, gamma, key, window_size)
    z = _z_score(n_green, T, gamma)
    return {
        "z_score": float(z),
        "n_green": int(n_green),
        "T": int(T),
        "is_watermarked": bool(z > z_threshold),
    }


def detect_by_windows(
    text: str,
    tokenizer: Any,
    vocab_size: int,
    gamma: float,
    key: str,
    window_size: int,
    window_tokens: int = 80,
    stride: int = 20,
) -> dict[str, Any]:
    token_ids = tokenizer.encode(text, add_special_tokens=False)
    if len(token_ids) < 2:
        return {"max_z": 0.0, "best_span_tokens": [0, 0], "best_span_char": [0, 0]}

    max_z = -1e9
    best_lo = best_hi = 0
    for start in range(0, max(1, len(token_ids) - window_tokens + 1), stride):
        end = min(len(token_ids), start + window_tokens)
        if end - start < 2:
            continue
        chunk = token_ids[start:end]
        n_green, T = _count_green_stats(chunk, vocab_size, gamma, key, window_size)
        z = _z_score(n_green, T, gamma)
        if z > max_z:
            max_z = z
            best_lo, best_hi = start, end

    char_start = len(tokenizer.decode(token_ids[:best_lo], skip_special_tokens=False))
    char_end = len(tokenizer.decode(token_ids[:best_hi], skip_special_tokens=False))
    return {
        "max_z": float(max_z),
        "best_span_tokens": [int(best_lo), int(best_hi)],
        "best_span_char": [int(char_start), int(char_end)],
    }
