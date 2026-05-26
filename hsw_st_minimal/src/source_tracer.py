"""水印日志与教师资源来源日志绑定。"""

from __future__ import annotations

import hashlib
from typing import Any

from utils import now_iso


def build_watermark_log(
    answer_id: str,
    sample_id: str,
    watermark_id: str,
    wm_cfg: dict[str, Any],
    z_self: float,
    model_name: str,
) -> dict[str, Any]:
    return {
        "answer_id": answer_id,
        "sample_id": sample_id,
        "watermark_id": watermark_id,
        "key_id": wm_cfg.get("key_id", "key_default"),
        "gamma": wm_cfg.get("gamma", 0.25),
        "delta": wm_cfg.get("delta", 2.0),
        "window_size": wm_cfg.get("window_size", 4),
        "z_score_self_check": float(z_self),
        "model_name": model_name,
        "timestamp": now_iso(),
    }


def _normalize_source(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "resource_id": s.get("resource_id"),
        "chunk_id": s.get("chunk_id"),
        "return_mode": s.get("return_mode"),
        "retrieval_score": s.get("retrieval_score"),
        "copyright_level": s.get("copyright_level"),
        "exposure_before": s.get("exposure_before"),
        "exposure_after": s.get("exposure_after"),
        "trace_binding_id": s.get("trace_binding_id"),
        "upstream_watermark_id": s.get("upstream_watermark_id"),
        "extra": s.get("extra") or {},
    }


def build_trace_binding_id(
    answer_id: str,
    watermark_id: str | None,
    sources: list[dict[str, Any]],
) -> str:
    parts = [answer_id, watermark_id or ""]
    for s in sources:
        parts.extend(
            [
                str(s.get("resource_id", "")),
                str(s.get("chunk_id", "")),
                str(s.get("return_mode", "")),
            ]
        )
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"trace_{digest}"


def build_source_trace_log(
    answer_id: str,
    sample_id: str,
    sources: list[dict[str, Any]],
    watermark_id: str | None = None,
) -> dict[str, Any]:
    slim = [_normalize_source(s) for s in sources or []]
    return {
        "answer_id": answer_id,
        "sample_id": sample_id,
        "watermark_id": watermark_id,
        "trace_binding_id": build_trace_binding_id(answer_id, watermark_id, slim),
        "sources": slim,
        "timestamp": now_iso(),
    }


def build_unified_trace_log(
    watermark_log: dict[str, Any],
    source_trace_log: dict[str, Any],
    answer_text: str = "",
) -> dict[str, Any]:
    answer_id = str(watermark_log.get("answer_id") or source_trace_log.get("answer_id") or "")
    watermark_id = str(watermark_log.get("watermark_id") or source_trace_log.get("watermark_id") or "")
    sources = list(source_trace_log.get("sources") or [])
    return {
        "trace_binding_id": source_trace_log.get("trace_binding_id")
        or build_trace_binding_id(answer_id, watermark_id, sources),
        "answer_id": answer_id,
        "sample_id": watermark_log.get("sample_id") or source_trace_log.get("sample_id"),
        "watermark_id": watermark_id,
        "key_id": watermark_log.get("key_id"),
        "z_score_self_check": watermark_log.get("z_score_self_check"),
        "sources": sources,
        "watermarked_answer_sha256": hashlib.sha256(answer_text.encode("utf-8")).hexdigest()
        if answer_text
        else None,
        "timestamp": now_iso(),
    }
