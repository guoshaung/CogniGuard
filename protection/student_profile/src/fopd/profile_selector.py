from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from protection.common.schemas import ProfileRecord, StudentProfile, Task
from protection.common.text_utils import SimpleTfidfVectorizer, clamp01, cosine_sparse
from protection.student_profile.src.fopd.orthogonal_decoder import OrthogonalDecoder
from protection.student_profile.src.fopd.task_attention import InformationBottleneck, TaskAttentionSelector


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
        self.use_enhanced = fopd.get("use_enhanced_fopd", True)
        components = fopd.get("components", {})
        self.use_orthogonal = bool(components.get("use_orthogonal", True))
        self.use_task_attention = bool(components.get("use_task_attention", True))
        self.use_bottleneck = bool(components.get("use_bottleneck", True))

        if self.use_enhanced:
            if self.use_orthogonal:
                self.orthogonal_decoder = OrthogonalDecoder(config)
            if self.use_task_attention:
                self.attention_selector = TaskAttentionSelector(config)
            if self.use_bottleneck:
                self.info_bottleneck = InformationBottleneck(config)

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
        if self.use_enhanced:
            return self.select_enhanced(profile, task)

        scored = self.score_records(profile, task)
        selected = [
            x
            for x in scored
            if x.score >= self.threshold
            and x.record.sensitivity <= self.sensitivity_threshold
            and (x.components.get("tag", 0.0) > 0.0 or x.components.get("rel", 0.0) >= 0.05)
        ]
        return selected[: self.top_k]

    def select_enhanced(self, profile: StudentProfile, task: Task) -> list[ScoredProfileRecord]:
        records = profile.profile_records
        record_index = {record.record_id: idx for idx, record in enumerate(records)}
        baseline_scores = self.score_records(profile, task)
        baseline_by_id = {item.record.record_id: item for item in baseline_scores}

        if self.use_orthogonal:
            self.orthogonal_decoder.decompose(records)

        if self.use_task_attention:
            attention_scores = self.attention_selector.compute_attention(task, records)
        else:
            attention_scores = [
                (record_index[item.record.record_id], item.score)
                for item in baseline_scores
                if item.record.record_id in record_index
            ]
        attention_by_index = {idx: weight for idx, weight in attention_scores}
        top_indices = [
            idx
            for idx, _ in attention_scores
            if idx < len(records)
            and (not self.use_orthogonal or records[idx].sensitivity <= self.sensitivity_threshold)
        ]
        top_records = [records[i] for i in top_indices]
        top_weights = [attention_by_index.get(idx, 0.0) for idx in top_indices]

        if self.use_bottleneck:
            compressed_records = self.info_bottleneck.compress(top_records, top_weights)
        else:
            compressed_records = top_records[: self.top_k]

        result: list[ScoredProfileRecord] = []
        for record in compressed_records:
            idx = record_index.get(record.record_id, -1)
            weight = attention_by_index.get(idx, 0.0)
            baseline = baseline_by_id.get(record.record_id)
            components = dict(baseline.components) if baseline else {}
            components.update(
                {
                    "attention": weight if self.use_task_attention else 0.0,
                    "orthogonal": float(self.use_orthogonal),
                    "bottleneck": float(self.use_bottleneck),
                }
            )
            result.append(
                ScoredProfileRecord(
                    record=record,
                    score=weight,
                    components=components,
                )
            )

        selected_ids = {item.record.record_id for item in result}
        baseline_relevant = [
            item
            for item in baseline_scores
            if item.score >= self.threshold
            and (not self.use_orthogonal or item.record.sensitivity <= self.sensitivity_threshold)
            and (
                item.components.get("tag", 0.0) > 0.0
                or item.components.get("rel", 0.0) >= 0.05
            )
        ]
        for item in baseline_relevant:
            if len(result) >= self.top_k:
                break
            if item.record.record_id in selected_ids:
                continue
            idx = record_index.get(item.record.record_id, -1)
            result.append(
                ScoredProfileRecord(
                    record=item.record,
                    score=max(item.score, attention_by_index.get(idx, 0.0)),
                    components={
                        **item.components,
                        "attention": attention_by_index.get(idx, 0.0) if self.use_task_attention else 0.0,
                        "orthogonal": float(self.use_orthogonal),
                        "bottleneck": float(self.use_bottleneck),
                        "enhanced_recall_guard": 1.0,
                    },
                )
            )
            selected_ids.add(item.record.record_id)

        return sorted(result, key=lambda x: x.score, reverse=True)[: self.top_k]
