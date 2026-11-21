from protection.common.schemas import ResourcePolicy, TeacherResource
from protection.teacher_resource.src.c2rag.c2rag_metrics import (
    CopyrightMetricIndex,
    compute_c2rag_metrics,
)


def _resource(index: int, content: str) -> TeacherResource:
    return TeacherResource(
        resource_id=f"resource_{index}",
        chunk_id=f"chunk_{index}",
        content=content,
        knowledge="algebra",
        difficulty="medium",
        cognitive_level="apply",
        resource_type="synthetic_teacher_explanation",
        copyright_level=0.9,
        policy=ResourcePolicy(),
    )


def test_crr_metric_scans_entire_resource_bank_exactly() -> None:
    answer = "protected teacher solution sequence"
    resources = [
        _resource(index, f"unrelated resource text {index}") for index in range(30)
    ]
    resources[-1] = _resource(29, answer)
    metrics = compute_c2rag_metrics(
        None,
        answer,
        resources,
        metric_index=CopyrightMetricIndex(resources),
    )
    assert metrics["CRR"] == 1.0
    assert metrics["CRRCandidateCount"] == 30
