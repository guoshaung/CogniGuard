from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from protection.common.schemas import StudentProfile


@dataclass(slots=True)
class PrivacyEvidence:
    selected_record_ids: list[str]
    selection_cost: float
    released_exposure: float
    sensitive_value_hits: int
    budget_before: float
    budget_after: float
    budget_exhausted: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PrivacyBudgetLedger:
    """MM-FOPD-owned ledger; the general governance core only consumes evidence."""

    def __init__(self, maximum: float = 1.0) -> None:
        self.maximum = float(maximum)
        self.consumed_by_subject: dict[str, float] = {}

    def remaining(self, subject_id: str) -> float:
        return max(0.0, self.maximum - self.consumed_by_subject.get(subject_id, 0.0))

    def measure_and_commit(self, profile: StudentProfile, selected_ids: list[str], released_text: str) -> PrivacyEvidence:
        before = self.remaining(profile.student_id)
        selected = [record for record in profile.profile_records if record.record_id in set(selected_ids)]
        total_sensitivity = sum(max(0.0, record.sensitivity) for record in profile.profile_records) or 1.0
        selection_cost = sum(max(0.0, record.sensitivity) for record in selected) / total_sensitivity
        visible_values = [str(record.value) for record in selected if str(record.value) and str(record.value) in released_text]
        released_exposure = sum(max(0.0, record.sensitivity) for record in selected if str(record.value) in released_text) / total_sensitivity
        actual = min(before, released_exposure)
        self.consumed_by_subject[profile.student_id] = self.consumed_by_subject.get(profile.student_id, 0.0) + actual
        after = self.remaining(profile.student_id)
        return PrivacyEvidence(
            selected_record_ids=[record.record_id for record in selected],
            selection_cost=selection_cost,
            released_exposure=released_exposure,
            sensitive_value_hits=len(visible_values),
            budget_before=before,
            budget_after=after,
            budget_exhausted=released_exposure > before + 1e-9,
        )

