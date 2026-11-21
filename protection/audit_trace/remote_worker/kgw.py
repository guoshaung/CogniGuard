"""Original CPU PCG64 greenlist; device only applies the exact +2 indices."""

from __future__ import annotations

import hashlib
import math
import struct
from collections import OrderedDict

import numpy as np

from .protocol import PRF, digest


class Greenlist:
    def __init__(self, key: str, cache_size: int = 16):
        if not key or not 0 <= cache_size <= 64:
            raise ValueError("A private frozen key and bounded cache are required")
        self._key = key.encode()
        self.key_sha256 = digest(self._key)
        self.cache_size = cache_size
        self._cache: OrderedDict[tuple[int, ...], np.ndarray] = OrderedDict()

    def seed(self, history: list[int]) -> int:
        ctx = history[-4:]
        data = self._key + b"".join(struct.pack("<I", int(x) & 0xFFFFFFFF) for x in ctx)
        return int.from_bytes(hashlib.sha256(data).digest()[:16], "big") % 2**32

    def indices(self, history: list[int]) -> np.ndarray:
        if not history:
            return np.array([], dtype=np.int64)
        context = tuple(history[-4:])
        if context in self._cache:
            self._cache.move_to_end(context)
            return self._cache[context]
        green = np.sort(
            np.random.Generator(np.random.PCG64(self.seed(history))).permutation(151643)[:37911]
        )
        green.setflags(write=False)
        if self.cache_size:
            self._cache[context] = green
            if len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        return green


class InternalKGW:
    """Transformers-compatible callback; one instance per independent request.

    No torch/MUSA import at module load. No GPU RNG substitutes the CPU PRF.
    HF receives full prompt + generated history. Left/right padded batches are
    deliberately unsupported: separate requests own separate callbacks.
    """

    def __init__(self, key: str):
        self.greenlist = Greenlist(key)
        self.calls = 0
        self.contexts: list[list[int]] = []
        self.green_hashes: list[str] = []

    def __call__(self, input_ids, scores):
        import torch

        if input_ids.ndim != 2 or input_ids.shape[0] != 1 or scores.shape[0] != 1:
            raise ValueError("One request per callback; padded multi-request batches rejected")
        if scores.shape[-1] < 151643:
            raise ValueError("Wrong model vocabulary")
        context = input_ids[0, -4:].detach().cpu().tolist()
        indices = self.greenlist.indices(context)
        device_indices = torch.tensor(indices.copy(), dtype=torch.long, device=scores.device)
        scores[0, device_indices] += 2.0
        self.calls += 1
        self.contexts.append(context)
        self.green_hashes.append(digest(indices.astype("<u4").tobytes()))
        return scores


def detect_ids(public_ids: list[int], key: str) -> dict:
    """Independent public j>=4 / count_all / strict z>3, matching R18."""
    prf = Greenlist(key)
    rows = []
    grams = []
    for j in range(4, len(public_ids)):
        ctx = public_ids[j - 4 : j]
        idx = prf.indices(ctx)
        pos = int(np.searchsorted(idx, public_ids[j]))
        green = pos < len(idx) and int(idx[pos]) == public_ids[j]
        rows.append({"position": j, "token_id": public_ids[j], "context4": ctx, "is_green": green})
        grams.append(tuple(ctx + [public_ids[j]]))
    t = len(rows)
    g = sum(r["is_green"] for r in rows)
    z = (g - 0.25 * t) / math.sqrt(t * 0.25 * 0.75) if t else None
    return {
        "status": "SCORABLE" if t else "INSUFFICIENT",
        "T": t,
        "G": g,
        "green_fraction": g / t if t else None,
        "z": z,
        "detected": z > 3 if z is not None else None,
        "repeat_policy": "count_all",
        "repeated_positions": t - len(set(grams)),
        "PRF": PRF,
        "rows": rows,
    }
