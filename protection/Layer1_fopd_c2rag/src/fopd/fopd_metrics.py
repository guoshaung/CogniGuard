from __future__ import annotations

from protection.fopd_c2rag_mvp.src.common.schemas import StudentProfile, Task
from protection.fopd_c2rag_mvp.src.fopd.profile_selector import ScoredProfileRecord


def compute_fopd_metrics(
    profile: StudentProfile,
    task: Task,
    context_card: str,
    selected_records: list[ScoredProfileRecord],
) -> dict[str, float | int]:
    all_sens = sum(max(0.0, r.sensitivity) for r in profile.profile_records)
    selected_sens = sum(max(0.0, x.record.sensitivity) for x in selected_records)
    local_values = [str(v) for v in profile.local_only_fields.values() if str(v)]
    sensitive_leak = any(value in context_card for value in local_values)
    if selected_records:
        coverage = sum(1 for x in selected_records if x.record.knowledge == task.knowledge) / len(selected_records)
    else:
        coverage = 0.0
    return {
        "CardLen": len(context_card),
        "SelectedCount": len(selected_records),
        "PER": selected_sens / all_sens if all_sens else 0.0,
        "TaskCoverage": coverage,
        "SensitiveLeakFlag": int(sensitive_leak),
    }
