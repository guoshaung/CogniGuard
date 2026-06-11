from __future__ import annotations

from typing import Any

from protection.common.logging_utils import now_iso
from protection.common.schemas import TeacherResource


def build_source_trace(
    resource: TeacherResource,
    mode: str,
    exposure_before: float,
    exposure_after: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "resource_id": resource.resource_id,
        "chunk_id": resource.chunk_id,
        "return_mode": mode,
        "copyright_level": resource.copyright_level,
        "exposure_before": exposure_before,
        "exposure_after": exposure_after,
        "timestamp": now_iso(),
        "extra": extra or {},
    }
