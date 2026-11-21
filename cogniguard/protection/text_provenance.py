"""HSW-ST local semantic watermark plus authenticated final-text provenance.

Semantic markers are a real, weak local watermark, not a KGW statistical claim.
KGW requires an explicitly injected logits-capable backend with a detector. HMAC
binds final bytes and approved sources independently of marker robustness.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import secrets
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

from cogniguard.governance import AuditLedger
from protection.audit_trace.src.hybrid_watermark import HybridWatermarkSystem
from protection.audit_trace.src.watermark_policy import WatermarkEvidence, WatermarkPolicy

SEMANTIC_MARKERS = ("教学说明", "学习提示", "推理说明")


class WatermarkUnavailableError(RuntimeError):
    """A required watermark cannot be embedded and independently detected."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _slim_sources(sources) -> list[dict[str, Any]]:
    keys = (
        "resource_id",
        "chunk_id",
        "return_mode",
        "source_trace_id",
        "trace_binding_id",
        "controlled_output_hash",
        "resource_provenance_commitment",
    )
    slim = []
    for source in sources:
        item = {key: deepcopy(source[key]) for key in keys if source.get(key) is not None}
        if source.get("content"):
            item["approved_content_sha256"] = _content_hash(str(source["content"]))
        slim.append(item)
    return slim


class TextProvenanceService:
    """One service per trusted signing key; no automatic model initialization.

    Callers persist their signing secret securely if records must survive process
    restarts. With no secret supplied the key is process-local. A statistical
    backend must expose embed(text, *, answer_id, sources) and detect(text, *,
    metadata); it is trusted application code and is never selected by task text.
    """

    def __init__(self, secret=None, *, mode="semantic", required=False, statistical_backend=None):
        if mode not in {"semantic", "statistical", "provenance_only"}:
            raise ValueError("Unsupported text watermark mode")
        self.secret = secret.encode("utf-8") if isinstance(secret, str) else secret
        if self.secret is None:
            self.secret = secrets.token_bytes(32)
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise ValueError("Text provenance signing secret must contain at least 32 bytes")
        self.mode, self.required = mode, bool(required)
        self.statistical_backend = statistical_backend
        self.hybrid = HybridWatermarkSystem({"hsw": {"semantic_markers": list(SEMANTIC_MARKERS)}})
        self.policy = WatermarkPolicy()
        self.audit = AuditLedger()
        self._lock = RLock()

    def _sign(self, record: dict) -> str:
        payload = {key: value for key, value in record.items() if key != "signature"}
        return hmac.new(self.secret, _canonical(payload), hashlib.sha256).hexdigest()

    def bind(self, text: str, *, answer_id: str, sources=()) -> dict[str, Any]:
        with self._lock:
            return self._bind(text, answer_id=answer_id, sources=sources)

    def _bind(self, text: str, *, answer_id: str, sources=()) -> dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Cannot bind an empty final answer")
        if not answer_id:
            raise ValueError("answer_id is required")
        if not self.audit.verify():
            raise WatermarkUnavailableError("Text provenance audit chain is invalid")
        approved_sources = _slim_sources(sources)
        final_text, mode = text, self.mode
        detection, metadata, fallback_reason = {}, {}, ""
        if mode == "semantic":
            try:
                embedded = self.hybrid.embed_hybrid(
                    text,
                    str(approved_sources[0].get("resource_id") if approved_sources else answer_id),
                    mode="semantic",
                )
                final_text = embedded["watermarked_text"]
                # No tokenizer: never uses the old detector's statistical stub.
                detected = self.hybrid.detect_hybrid(final_text)
                detection = {"detected": bool(detected["has_semantic"]), "statistical": False}
                metadata = {"semantic_markers": list(detected["detected_markers"])}
                if not detection["detected"]:
                    fallback_reason = "semantic_detection_failed"
            except Exception:
                fallback_reason = "semantic_backend_failed"
        elif mode == "statistical":
            backend = self.statistical_backend
            if (
                backend is None
                or not callable(getattr(backend, "embed", None))
                or not callable(getattr(backend, "detect", None))
            ):
                fallback_reason = "statistical_backend_unavailable"
            else:
                try:
                    embedded = backend.embed(
                        text, answer_id=answer_id, sources=deepcopy(approved_sources)
                    )
                    final_text = embedded["text"]
                    if not isinstance(final_text, str) or not final_text.strip():
                        raise ValueError("Invalid statistical watermark text")
                    metadata = deepcopy(embedded.get("metadata") or {})
                    measured = backend.detect(final_text, metadata=deepcopy(metadata))
                    detection = {"detected": measured.get("detected") is True, "statistical": True}
                    if "z_score" in measured:
                        detection["z_score"] = float(measured["z_score"])
                        if not math.isfinite(detection["z_score"]):
                            raise ValueError("Invalid statistical detection score")
                    if not detection["detected"]:
                        fallback_reason = "statistical_detection_failed"
                except Exception:
                    fallback_reason = "statistical_backend_failed"
        if fallback_reason:
            if self.required:
                raise WatermarkUnavailableError(fallback_reason)
            final_text, mode, detection, metadata = text, "provenance_only", {}, {}
        verified = detection.get("detected") is True
        if self.required and not verified:
            raise WatermarkUnavailableError("Required text watermark was not detected")
        if not isinstance(final_text, str) or not final_text.strip():
            raise WatermarkUnavailableError("Watermark backend returned empty output")
        content_hash = _content_hash(final_text)
        source_hash = _digest(approved_sources)
        watermark_id = "wm_" + uuid4().hex
        trace_id = "trace_" + _digest([answer_id, watermark_id, content_hash, source_hash])[:32]
        audit = self.audit.append(
            {
                "event": "text_provenance_bound",
                "answer_id": str(answer_id),
                "watermark_id": watermark_id,
                "content_hash": content_hash,
                "source_binding_hash": source_hash,
                "mode": mode,
            }
        )
        record = {
            "version": "cogniguard-text-provenance-v1",
            "answer_id": str(answer_id),
            "watermark_id": watermark_id,
            "text": final_text,
            "content_hash": content_hash,
            "sources": approved_sources,
            "source_binding_hash": source_hash,
            "trace_binding_id": trace_id,
            "mode": mode,
            "requested_mode": self.mode,
            "watermark_applied": verified,
            "watermark_verified": verified,
            "statistical_watermark": bool(detection.get("statistical") and verified),
            "verification_required": self.required,
            "detection": detection,
            "watermark_metadata": metadata,
            "fallback_reason": fallback_reason,
            "implementation": "HSW-ST local semantic marker" if mode == "semantic" else mode,
            "fidelity_metrics_status": "not_measured",
            "audit": deepcopy(audit),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        record["signature"] = self._sign(record)
        self.policy.register(
            WatermarkEvidence(
                watermark_id,
                verified,
                float(detection.get("z_score", 0.0)),
                0.0,
                0.0,
                0.0,
                trace_id,
                provenance_valid=True,
            ),
            answer_hash=content_hash,
            sources=deepcopy(approved_sources),
        )
        return record

    def verify(self, text: str, record: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(text, str) or not isinstance(record, dict):
            return {
                "valid": False,
                "provenance_valid": False,
                "watermark_verified": False,
                "mode": None,
                "content_hash": _content_hash(text) if isinstance(text, str) else "",
                "reasons": ["invalid_provenance_record"],
            }
        reasons = []
        try:
            if not hmac.compare_digest(str(record.get("signature", "")), self._sign(record)):
                reasons.append("signature_mismatch")
            if record.get("text") != text or record.get("content_hash") != _content_hash(text):
                reasons.append("content_hash_mismatch")
            if record.get("source_binding_hash") != _digest(record.get("sources")):
                reasons.append("source_binding_mismatch")
            expected_trace = (
                "trace_"
                + _digest(
                    [
                        record.get("answer_id"),
                        record.get("watermark_id"),
                        record.get("content_hash"),
                        record.get("source_binding_hash"),
                    ]
                )[:32]
            )
            if record.get("trace_binding_id") != expected_trace:
                reasons.append("trace_binding_mismatch")
            audit = record.get("audit") or {}
            if audit.get("record_hash") != _digest(
                {key: value for key, value in audit.items() if key != "record_hash"}
            ):
                reasons.append("audit_record_mismatch")
        except (TypeError, ValueError, KeyError, AttributeError):
            reasons.append("invalid_provenance_record")
        watermark_verified = False
        # Only invoke an optional backend after authentication; attacker-supplied
        # metadata is never handed to a model or detector on invalid records.
        if not reasons:
            if record.get("mode") == "semantic":
                detection = self.hybrid.detect_hybrid(text)
                expected = (record.get("watermark_metadata") or {}).get("semantic_markers", [])
                watermark_verified = bool(expected) and all(
                    marker in detection["detected_markers"] for marker in expected
                )
            elif record.get("mode") == "statistical" and self.statistical_backend is not None:
                try:
                    measured = self.statistical_backend.detect(
                        text, metadata=deepcopy(record.get("watermark_metadata") or {})
                    )
                    watermark_verified = measured.get("detected") is True
                except Exception:
                    watermark_verified = False
            if (self.required or record.get("verification_required")) and not watermark_verified:
                reasons.append("required_watermark_not_verified")
        return {
            "valid": not reasons,
            "provenance_valid": not reasons,
            "watermark_verified": watermark_verified,
            "mode": record.get("mode"),
            "content_hash": _content_hash(text),
            "reasons": reasons,
        }
