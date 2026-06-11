from __future__ import annotations

from collections import deque

from protection.common.schemas import TeacherResource
from protection.common.text_utils import cosine_text, lcs_ratio, unique_ngram_overlap


class ExposureBudget:
    def __init__(self, config: dict) -> None:
        c2 = config.get("c2rag", {})
        self.decay = float(c2.get("exposure_decay", 1.0))
        self.weights = c2.get("exposure_weights", {})
        self.recent_window = int(c2.get("recent_window", 5))
        self.values: dict[str, float] = {}
        self.recent_hits: deque[str] = deque(maxlen=self.recent_window)

    def get(self, chunk_id: str) -> float:
        return float(self.values.get(chunk_id, 0.0))

    def focus(self, chunk_id: str) -> float:
        if not self.recent_hits:
            return 0.0
        return sum(1 for x in self.recent_hits if x == chunk_id) / len(self.recent_hits)

    def update(self, resource: TeacherResource, output: str) -> dict[str, float]:
        before = self.get(resource.chunk_id)
        focus = self.focus(resource.chunk_id)
        lcs = lcs_ratio(output, resource.content)
        ngram = unique_ngram_overlap(output, resource.content)
        sem = cosine_text(output, resource.content)
        delta = (
            float(self.weights.get("lcs", 0.35)) * lcs
            + float(self.weights.get("ngram", 0.25)) * ngram
            + float(self.weights.get("sem", 0.30)) * sem
            + float(self.weights.get("focus", 0.10)) * focus
        )
        after = self.decay * before + delta
        self.values[resource.chunk_id] = after
        self.recent_hits.append(resource.chunk_id)
        return {
            "before": before,
            "after": after,
            "delta": delta,
            "lcs": lcs,
            "ngram": ngram,
            "sem": sem,
            "focus": focus,
        }
