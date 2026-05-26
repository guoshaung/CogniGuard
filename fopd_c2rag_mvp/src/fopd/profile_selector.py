from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.common.schemas import ProfileRecord, StudentProfile, Task
from src.common.text_utils import SimpleTfidfVectorizer, clamp01, cosine_sparse


@dataclass(slots=True)
class ScoredProfileRecord:
    record: ProfileRecord
    score: float
    components: dict[str, float]


def _parse_date(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value[:10])
    except Exception:
        return None


class ProfileSelector:
    def __init__(self, config: dict) -> None:
        fopd = config.get("fopd", {})
        self.top_k = int(fopd.get("top_k_profile_records", 3))
        self.threshold = float(fopd.get("relevance_threshold", 0.15))
        self.sensitivity_threshold = float(fopd.get("sensitivity_threshold", 0.70))
        self.weights = fopd.get("weights", {})

    def score_records(self, profile: StudentProfile, task: Task) -> list[ScoredProfileRecord]:
        records = profile.profile_records
        texts = [r.text() for r in records] + [task.text()]
        vectorizer = SimpleTfidfVectorizer().fit(texts)
        task_vec = vectorizer.transform_one(task.text())
        dates = [_parse_date(r.updated_at) for r in records]
        valid_dates = [d for d in dates if d is not None]
        newest = max(valid_dates) if valid_dates else None
        oldest = min(valid_dates) if valid_dates else None
        span_days = max((newest - oldest).days if newest and oldest else 1, 1)

        scored: list[ScoredProfileRecord] = []
        for record, date in zip(records, dates):
            rec_vec = vectorizer.transform_one(record.text())
            rel = cosine_sparse(rec_vec, task_vec)
            tag = 1.0 if record.knowledge == task.knowledge else (0.4 if record.knowledge in task.text() else 0.0)
            conf = clamp01(record.confidence)
            if date and newest:
                recency = 1.0 - ((newest - date).days / span_days)
            else:
                recency = 0.5
            sens_penalty = max(0.0, record.sensitivity - self.sensitivity_threshold)
            score = (
                float(self.weights.get("rel", 0.50)) * rel
                + float(self.weights.get("tag", 0.25)) * tag
                + float(self.weights.get("confidence", 0.15)) * conf
                + float(self.weights.get("recency", 0.10)) * recency
                - float(self.weights.get("sens_gate", 0.20)) * sens_penalty
            )
            scored.append(
                ScoredProfileRecord(
                    record=record,
                    score=score,
                    components={
                        "rel": rel,
                        "tag": tag,
                        "confidence": conf,
                        "recency": recency,
                        "sens_penalty": sens_penalty,
                    },
                )
            )
        return sorted(scored, key=lambda x: x.score, reverse=True)

    def select(self, profile: StudentProfile, task: Task) -> list[ScoredProfileRecord]:
        scored = self.score_records(profile, task)
        selected = [
            x
            for x in scored
            if x.score >= self.threshold
            and x.record.sensitivity <= self.sensitivity_threshold
            and (x.components.get("tag", 0.0) > 0.0 or x.components.get("rel", 0.0) >= 0.05)
        ]
        return selected[: self.top_k]
