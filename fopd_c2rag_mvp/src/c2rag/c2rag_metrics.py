from __future__ import annotations

from src.common.schemas import ControlledResource, TeacherResource
from src.common.text_utils import cosine_text, lcs_ratio


def compute_c2rag_metrics(
    controlled: ControlledResource | None,
    final_answer: str,
    resources: list[TeacherResource],
) -> dict[str, float | int]:
    if not resources:
        return {
            "CRR": 0.0,
            "ORR": 0,
            "MER": 0.0,
            "VariantRate": 0,
            "TeachAvailability": 0,
        }
    similarities = [max(cosine_text(final_answer, r.content), lcs_ratio(final_answer, r.content)) for r in resources]
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
    }
