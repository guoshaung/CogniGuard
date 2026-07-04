from __future__ import annotations

import hashlib
import json
from typing import Any

from protection.common.logging_utils import now_iso
from protection.common.schemas import TeacherResource


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _policy_snapshot(resource: TeacherResource) -> dict[str, Any]:
    return {
        "allow_quote": resource.policy.allow_quote,
        "allow_summary": resource.policy.allow_summary,
        "allow_outline": resource.policy.allow_outline,
        "allow_variant": resource.policy.allow_variant,
        "max_quote_len": resource.policy.max_quote_len,
        "max_exposure": resource.policy.max_exposure,
    }


def _quote_span_hash(resource: TeacherResource, mode: str, controlled_text: str | None) -> str | None:
    if mode != "quote" or not controlled_text:
        return None
    return _stable_hash(
        {
            "resource_id": resource.resource_id,
            "chunk_id": resource.chunk_id,
            "mode": mode,
            "quoted_text": controlled_text,
        }
    )


def build_source_trace(
    resource: TeacherResource,
    mode: str,
    exposure_before: float,
    exposure_after: float,
    extra: dict[str, Any] | None = None,
    controlled_text: str | None = None,
    retrieval_trace: list[dict[str, Any]] | None = None,
    policy_reason: str | None = None,
    decision_factors: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quote_hash = _quote_span_hash(resource, mode, controlled_text)
    output_hash = _stable_hash(controlled_text or "")
    provenance_core = {
        "resource_id": resource.resource_id,
        "chunk_id": resource.chunk_id,
        "return_mode": mode,
        "copyright_level": resource.copyright_level,
        "exposure_before": exposure_before,
        "exposure_after": exposure_after,
        "quote_span_hash": quote_hash,
        "controlled_output_hash": output_hash,
        "license_policy": _policy_snapshot(resource),
    }
    trace = {
        "trace_scope": "resource_level_provenance",
        "trace_owner": "C2-RAG",
        "watermark_boundary": "generation_watermarking_is_owned_by_HSW-ST",
        "resource_id": resource.resource_id,
        "chunk_id": resource.chunk_id,
        "return_mode": mode,
        "copyright_level": resource.copyright_level,
        "exposure_before": exposure_before,
        "exposure_after": exposure_after,
        "license_policy": provenance_core["license_policy"],
        "policy_reason": policy_reason or "",
        "decision_factors": decision_factors or {},
        "retrieval_trace": retrieval_trace or [],
        "quote_span_hash": quote_hash,
        "controlled_output_hash": output_hash,
        "resource_provenance_commitment": _stable_hash(provenance_core),
        "timestamp": now_iso(),
        "extra": extra or {},
    }
    return trace
