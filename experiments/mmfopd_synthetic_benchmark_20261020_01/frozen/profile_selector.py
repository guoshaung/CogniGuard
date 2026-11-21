from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from protection.common.schemas import ProfileRecord, StudentProfile, Task
from protection.common.text_utils import SimpleTfidfVectorizer, clamp01, cosine_sparse
from _synfrozen.orthogonal_decoder import OrthogonalDecoder
from _synfrozen.task_attention import InformationBottleneck, TaskAttentionSelector


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
        self.use_taskslot = bool(components.get("use_taskslot", True))
        self.unit_budget = fopd.get("unit_budget", {})

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

        ortho_projection: dict[int, float] = {}
        if self.use_orthogonal:
            representation = self.orthogonal_decoder.decompose(records)
            task_embedding = [(hash(f"{task.knowledge}:{token}") % 1000) / 1000.0 for token in task.text().lower().split()]
            projected = self.orthogonal_decoder.project_to_task(representation, task_embedding)
            ortho_projection = {idx: value for idx, value in enumerate(projected[:len(records)])}

        if self.use_task_attention:
            attention_scores = self.attention_selector.compute_attention(task, records)
        else:
            attention_scores = [
                (record_index[item.record.record_id], item.score)
                for item in baseline_scores
                if item.record.record_id in record_index
            ]
        attention_by_index = {idx: weight for idx, weight in attention_scores}
        if self.use_orthogonal:
            attention_scores = sorted(attention_scores, key=lambda pair: pair[1] + 0.35 * ortho_projection.get(pair[0], 0.0), reverse=True)
            attention_by_index = {idx: weight for idx, weight in attention_scores}
        top_indices = [
            idx
            for idx, _ in attention_scores
            if idx < len(records)
            and (records[idx].sensitivity <= self.sensitivity_threshold)
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
                    "orthogonal_projection": ortho_projection.get(idx, 0.0),
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

        if not self.use_taskslot:
            return sorted(result, key=lambda x: x.score, reverse=True)[: self.top_k]
        selected_ids = {item.record.record_id for item in result}
        baseline_relevant = [
            item
            for item in baseline_scores
            if item.score >= self.threshold
            and (item.record.sensitivity <= self.sensitivity_threshold)
            and (
                item.components.get("tag", 0.0) > 0.0
                or item.components.get("rel", 0.0) >= 0.05
            )
        ]
        if self.use_taskslot:
            distinct_types = set(self.unit_budget.get("distinct_requested_types", ()))
            if distinct_types:
                # Opt-in task schema alignment. Distinct explicitly requested
                # observations (e.g. two grade periods) must not collapse merely
                # because both have the same broad semantic type. Never bypass
                # the sensitivity, relevance, allowed-type or release gates.
                allowed = set(self.unit_budget.get("allowed", ("mastery", "error_pattern", "preference")))
                cap = max(0, min(self.top_k, int(self.unit_budget.get("max_units", self.top_k))))
                safe = [x for x in baseline_relevant
                        if x.record.sensitivity <= self.sensitivity_threshold
                        and x.record.type in allowed]
                reserved = [x for x in safe if x.record.type in distinct_types
                            and re.search(r"(?<!\w)" + re.escape(x.record.record_id) + r"(?!\w)",
                                          task.text(), flags=re.IGNORECASE)]
                safe_ids = {x.record.record_id for x in safe}
                ordered = [*reserved, *(x for x in result if x.record.record_id in safe_ids), *safe]
                aligned = {}
                for item in ordered:
                    if len(aligned) >= cap:
                        break
                    aligned.setdefault(item.record.record_id, item)
                return list(aligned.values())
            # Keep a minimum two-record teaching card when two relevant records
            # fit the gate; this preserves basic task utility without restoring
            # the old unconditional Top-K refill.
            for item in baseline_relevant:
                if len(result) >= min(2, self.top_k):
                    break
                if item.record.record_id not in {x.record.record_id for x in result}:
                    result.append(item)
            # Allocate the release budget by semantic information unit instead
            # of allowing several low-value state/behavior records to crowd out
            # the three complementary teaching facts.
            unit_priority = {
                "mastery": 0,
                "error_pattern": 1,
                "preference": 2,
                "learning_state": 3,
                "multimodal_summary": 4,
                "behavior_aggregate": 5,
            }
            best_by_unit: dict[str, ScoredProfileRecord] = {}
            for item in [*result, *baseline_relevant]:
                if item.record.knowledge != task.knowledge:
                    continue
                unit = item.record.type
                current = best_by_unit.get(unit)
                if current is None or item.score > current.score:
                    best_by_unit[unit] = item
            budget_units = self.unit_budget
            allowed_units = set(budget_units.get("allowed", ("mastery", "error_pattern", "preference")))
            max_units = int(budget_units.get("max_units", self.top_k))
            unit_candidates = [item for unit, item in best_by_unit.items() if unit in allowed_units]
            unit_candidates.sort(key=lambda item: (unit_priority.get(item.record.type, 9), -item.score))
            selected_ids = {item.record.record_id for item in result}
            for item in unit_candidates:
                if len(result) >= max_units:
                    break
                if item.record.record_id not in selected_ids:
                    result.append(item)
                    selected_ids.add(item.record.record_id)
            return sorted(result, key=lambda x: x.score, reverse=True)

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
