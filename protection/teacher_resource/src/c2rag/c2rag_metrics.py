from __future__ import annotations

from protection.common.schemas import ControlledResource, TeacherResource
from protection.common.text_utils import cosine_text, lcs_ratio


class CopyrightMetricIndex:
    """Reusable exact resource set for CRR computation."""

    def __init__(self, resources: list[TeacherResource]) -> None:
        self.resources = resources

    def candidate_indices(
        self,
        final_answer: str,
        controlled: ControlledResource | None,
    ) -> list[int]:
        # lcs_ratio uses an exact bit-parallel implementation, so the full
        # resource bank can be scanned without changing the historical metric.
        return list(range(len(self.resources)))


def compute_c2rag_metrics(
    controlled: ControlledResource | None,
    final_answer: str,
    resources: list[TeacherResource],
    metric_index: CopyrightMetricIndex | None = None,
) -> dict[str, float | int]:
    if not resources:
        return {
            "CRR": 0.0,
            "ORR": 0,
            "MER": 0.0,
            "VariantRate": 0,
            "TeachAvailability": 0,
            "CRRCandidateCount": 0,
        }
    candidate_indices = (
        metric_index.candidate_indices(final_answer, controlled)
        if metric_index is not None
        else list(range(len(resources)))
    )
    similarities = [
        max(
            cosine_text(final_answer, resources[index].content),
            lcs_ratio(final_answer, resources[index].content),
        )
        for index in candidate_indices
    ]
    crr = max(similarities) if similarities else 0.0
    mode = controlled.mode if controlled else "none"
    direct = 0
    if controlled and controlled.resource:
        direct = int(
            mode == "quote"
            or controlled.resource.content[: min(24, len(controlled.resource.content))] in controlled.text
        )
    teach_available = int(mode in {"quote", "summary", "outline", "variant"})
    return {
        "CRR": crr,
        "ORR": direct,
        "MER": controlled.exposure_after if controlled else 0.0,
        "VariantRate": int(mode == "variant"),
        "TeachAvailability": teach_available,
        "CRRCandidateCount": len(candidate_indices),
    }
