from __future__ import annotations

import hashlib
import math
import random
from typing import Iterable

from protection.common.schemas import ProfileRecord, StudentProfile, Task
from _synfrozen.profile_selector import ProfileSelector, ScoredProfileRecord


def as_scored(records: Iterable[ProfileRecord], *, component: str) -> list[ScoredProfileRecord]:
    return [ScoredProfileRecord(record=record, score=1.0, components={component: 1.0}) for record in records]


def full_profile(profile: StudentProfile, task: Task, config: dict) -> list[ScoredProfileRecord]:
    del task, config
    return as_scored(profile.profile_records, component="full_profile")


def lamp_style_retrieval(profile: StudentProfile, task: Task, config: dict) -> list[ScoredProfileRecord]:
    """Retrieval-only personalization baseline; it intentionally has no privacy gate."""
    selector = ProfileSelector(config)
    return selector.score_records(profile, task)[: selector.top_k]


def gpg_style_task_profile(profile: StudentProfile, task: Task, config: dict) -> list[ScoredProfileRecord]:
    """Deterministic extractive GPG adapter used before the real local-LLM adapter is enabled."""
    selector = ProfileSelector(config)
    priority = {"mastery": 0, "error_pattern": 1, "preference": 2, "learning_state": 3}
    candidates = [record for record in profile.profile_records if record.knowledge == task.knowledge]
    candidates.sort(key=lambda record: (priority.get(record.type, 9), -record.confidence))
    return as_scored(candidates[: selector.top_k], component="gpg_extractive_adapter")


def papillon_style_local_cloud(profile: StudentProfile, task: Task, config: dict) -> list[ScoredProfileRecord]:
    """Outbound disclosure of a local/cloud adapter: relevant, coarse, low-risk facts only."""
    selector = ProfileSelector(config)
    allowed_types = {"mastery", "preference", "learning_state"}
    candidates = [
        item for item in selector.score_records(profile, task)
        if item.record.knowledge == task.knowledge
        and item.record.type in allowed_types
        and item.record.sensitivity <= 0.55
    ]
    return candidates[: selector.top_k]


def privacy_funnel(profile: StudentProfile, task: Task, config: dict) -> list[ScoredProfileRecord]:
    """Inference-time privacy-funnel adapter balancing relevance against sensitivity."""
    selector = ProfileSelector(config)
    candidates: list[ScoredProfileRecord] = []
    for item in selector.score_records(profile, task):
        utility = item.components.get("rel", 0.0) + item.components.get("tag", 0.0)
        score = utility - 0.65 * item.record.sensitivity
        if utility > 0.0:
            candidates.append(ScoredProfileRecord(item.record, score, {**item.components, "privacy_funnel": score}))
    return sorted(candidates, key=lambda item: item.score, reverse=True)[: selector.top_k]


def dp_exponential_retrieval(profile: StudentProfile, task: Task, config: dict) -> list[ScoredProfileRecord]:
    """Seeded exponential-mechanism adapter (epsilon=1) for reproducible pilot comparisons."""
    selector = ProfileSelector(config)
    candidates = selector.score_records(profile, task)
    seed = int(hashlib.sha256(f"{task.request_id}:dp-exp-v1".encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    remaining = list(candidates)
    chosen: list[ScoredProfileRecord] = []
    while remaining and len(chosen) < selector.top_k:
        utilities = [item.score - 0.5 * item.record.sensitivity for item in remaining]
        peak = max(utilities)
        weights = [math.exp(0.5 * (value - peak)) for value in utilities]
        picked = rng.choices(range(len(remaining)), weights=weights, k=1)[0]
        item = remaining.pop(picked)
        chosen.append(ScoredProfileRecord(item.record, utilities[picked], {**item.components, "dp_epsilon": 1.0}))
    return chosen


def llm_data_minimization_proxy(profile: StudentProfile, task: Task, config: dict) -> list[ScoredProfileRecord]:
    """Deterministic self-critique proxy; a real local-Qwen implementation will replace it."""
    selector = ProfileSelector(config)
    priority = {"error_pattern": 0, "mastery": 1, "preference": 2, "learning_state": 3}
    candidates = [
        record for record in profile.profile_records
        if record.knowledge == task.knowledge and record.sensitivity <= 0.65
    ]
    candidates.sort(key=lambda record: (priority.get(record.type, 9), record.sensitivity, -record.confidence))
    return as_scored(candidates[: min(2, selector.top_k)], component="llm_minimization_proxy")


def mmfopd(profile: StudentProfile, task: Task, config: dict) -> list[ScoredProfileRecord]:
    return ProfileSelector(config).select(profile, task)


METHODS = {
    "FullProfile": full_profile,
    "LaMP-style-Retrieval": lamp_style_retrieval,
    "GPG-style-TaskProfile-extractive": gpg_style_task_profile,
    "PAPILLON-style-LocalCloud-adapter": papillon_style_local_cloud,
    "Privacy-Funnel-adapter": privacy_funnel,
    "DP-Exponential-Retrieval-eps1": dp_exponential_retrieval,
    "LLM-Data-Minimization-proxy": llm_data_minimization_proxy,
    "MM-FOPD": mmfopd,
}
