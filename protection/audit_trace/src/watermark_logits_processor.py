"""KGW 类绿色 token LogitsProcessor（与检测器算法一致）。"""

from __future__ import annotations

import hashlib
import struct
from typing import Any

import numpy as np
import torch
from transformers import LogitsProcessor


def _context_hash(context_ids: list[int], key: str) -> int:
    h = hashlib.sha256()
    h.update(key.encode("utf-8"))
    for tid in context_ids:
        h.update(struct.pack("<I", int(tid) & 0xFFFFFFFF))
    return int.from_bytes(h.digest()[:16], "big")


class KGWLogitsProcessor(LogitsProcessor):
    """对绿色词表子集施加 logits bias；batch 维逐行独立计算 greenlist。"""

    def __init__(
        self,
        vocab_size: int,
        gamma: float = 0.25,
        delta: float = 2.0,
        key: str = "secret",
        window_size: int = 4,
    ):
        self.vocab_size = int(vocab_size)
        self.gamma = float(gamma)
        self.delta = float(delta)
        self.key = key
        self.window_size = int(window_size)
        self._n_green = max(1, int(round(self.gamma * self.vocab_size)))

    def _greenlist(self, context_ids: list[int]) -> np.ndarray:
        seed = _context_hash(context_ids, self.key) % (2**32)
        rng = np.random.default_rng(seed)
        perm = rng.permutation(self.vocab_size)
        return perm[: self._n_green]

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor) -> torch.FloatTensor:
        if input_ids.dim() == 1:
            input_ids = input_ids.unsqueeze(0)
            scores = scores.unsqueeze(0)
            squeeze = True
        else:
            squeeze = False

        for b in range(input_ids.shape[0]):
            row_ids = input_ids[b].tolist()
            ctx = row_ids[-self.window_size :] if len(row_ids) >= self.window_size else row_ids
            green = self._greenlist(ctx)
            scores[b, green] = scores[b, green] + self.delta

        if squeeze:
            scores = scores.squeeze(0)
        return scores


def greenlist_for_prefix(
    prefix_ids: list[int],
    vocab_size: int,
    gamma: float,
    key: str,
    window_size: int,
) -> set[int]:
    """根据「当前 token 之前」的前缀（与生成时 input_ids 一致）计算绿色 token 集合。"""
    if not prefix_ids:
        return set()
    ctx = prefix_ids[-window_size:] if len(prefix_ids) >= window_size else prefix_ids
    seed = _context_hash(ctx, key) % (2**32)
    rng = np.random.default_rng(seed)
    n_green = max(1, int(round(gamma * vocab_size)))
    perm = rng.permutation(vocab_size)
    return set(perm[:n_green].tolist())
