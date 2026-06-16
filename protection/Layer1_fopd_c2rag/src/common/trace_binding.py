from __future__ import annotations

import hashlib
from typing import Any

from protection.fopd_c2rag_mvp.src.common.logging_utils import now_iso


def new_answer_id(request_id: str) -> str:
    return f"ans_{request_id}"


def new_watermark_id(answer_id: str) -> str:
    digest = hashlib.sha256(answer_id.encode("utf-8")).hexdigest()[:12]
    return f"wm_{digest}"


def build_trace_binding_id(answer_id: str, watermark_id: str, sources: list[dict[str, Any]]) -> str:
    parts = [answer_id, watermark_id]
    for source in sources:
        parts.extend(
            [
                str(source.get("resource_id", "")),
                str(source.get("chunk_id", "")),
                str(source.get("return_mode", "")),
            ]
        )
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"trace_{digest}"


def normalize_source_trace(source_trace: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not source_trace:
        return []
    return [
        {
            "resource_id": source_trace.get("resource_id"),
            "chunk_id": source_trace.get("chunk_id"),
            "return_mode": source_trace.get("return_mode"),
            "copyright_level": source_trace.get("copyright_level"),
            "exposure_before": source_trace.get("exposure_before"),
            "exposure_after": source_trace.get("exposure_after"),
            "extra": source_trace.get("extra") or {},
        }
    ]


def build_watermark_log(
    answer_id: str,
    sample_id: str,
    watermark_id: str,
    model_name: str = "ag2_rule_simulator",
) -> dict[str, Any]:
    return {
        "answer_id": answer_id,
        "sample_id": sample_id,
        "watermark_id": watermark_id,
        "key_id": "c2rag_mvp_prebind",
        "gamma": None,
        "delta": None,
        "window_size": None,
        "z_score_self_check": None,
        "model_name": model_name,
        "watermark_status": "prebound_for_hsw_st",
        "timestamp": now_iso(),
    }


def build_source_trace_log(
    answer_id: str,
    sample_id: str,
    watermark_id: str,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    binding_id = build_trace_binding_id(answer_id, watermark_id, sources)
    return {
        "answer_id": answer_id,
        "sample_id": sample_id,
        "watermark_id": watermark_id,
        "trace_binding_id": binding_id,
        "sources": sources,
        "timestamp": now_iso(),
    }


def build_unified_trace_log(
    answer_id: str,
    request_id: str,
    student_id: str,
    watermark_id: str,
    sources: list[dict[str, Any]],
    return_mode: str,
    final_answer: str,
) -> dict[str, Any]:
    binding_id = build_trace_binding_id(answer_id, watermark_id, sources)
    return {
        "trace_binding_id": binding_id,
        "answer_id": answer_id,
        "request_id": request_id,
        "student_id": student_id,
        "watermark_id": watermark_id,
        "return_mode": return_mode,
        "sources": sources,
        "final_answer_sha256": hashlib.sha256(final_answer.encode("utf-8")).hexdigest(),
        "timestamp": now_iso(),
    }
