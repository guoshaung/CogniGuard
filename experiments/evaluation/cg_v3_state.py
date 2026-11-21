"""State and feedback adapter for CG V3 experiments."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .cg_v3_schemas import CGInput, CGState


def _clamp(value: float) -> float:
    return round(min(1.0, max(0.0, float(value))), 8)


def semantic_intent(value: str) -> str:
    normalized = " ".join(str(value).lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _provenance_confidence(evidence: Mapping[str, Any]) -> float:
    for key in ("confidence", "provenance_confidence", "source_confidence"):
        if key in evidence:
            return _clamp(float(evidence[key]))
    return 1.0


def derive_risks(request: CGInput, previous: CGState) -> dict[str, float]:
    privacy_fields = list(request.C_u_t)
    allowed_fields = set(request.Pi_priv.get("allowed_fields", privacy_fields))
    restricted_fields = set(request.Pi_priv.get("forbidden_fields", []))
    privacy_risk = len([field for field in privacy_fields if field not in allowed_fields or field in restricted_fields]) / max(len(privacy_fields), 1)
    copyright_risk = float(request.CR_t.get("exposure_score", request.Pi_copy.get("exposure_score", 0.0)))
    repeated_risk = min(1.0, previous.semantic_repetition * 0.12)
    audit_risk = float(request.provenance_evidence.get("audit_risk", previous.audit_risk))
    if request.previous_audit_hash != "GENESIS" and request.previous_audit_hash != request.previous_state.get("audit_hash", request.previous_audit_hash):
        audit_risk = max(audit_risk, 0.85)
    return {
        "privacy": _clamp(privacy_risk + repeated_risk),
        "copyright": _clamp(copyright_risk + repeated_risk),
        "audit": _clamp(audit_risk + (1.0 - _provenance_confidence(request.provenance_evidence)) * 0.5),
    }


def update_state(
    request: CGInput,
    previous: CGState,
    *,
    privacy_exposure: float,
    copyright_exposure: float,
    budget_snapshot: Mapping[str, Any],
    audit_valid: bool,
    attack_indicators: list[str] | None = None,
    runtime_signals: Mapping[str, Any] | None = None,
    trust_update: float | None = None,
) -> CGState:
    current_intent = semantic_intent(request.q_t)
    repetition = previous.semantic_repetition + 1 if current_intent == previous.last_semantic_intent else 0
    provenance = _provenance_confidence(request.provenance_evidence)
    runtime_signals = runtime_signals or {}
    detector_score = float(runtime_signals.get("detector_risk", 0.0))
    detector_penalty = min(0.35, max(0.0, detector_score) * 0.35)
    trust = previous.trust_score if trust_update is None else trust_update
    trust = _clamp(trust + (provenance - 0.5) * 0.08 - detector_penalty - (0.2 if not audit_valid else 0.0))
    privacy_snapshot = budget_snapshot["privacy"]
    copyright_snapshot = budget_snapshot["copyright"]
    risks = derive_risks(request, previous)
    return CGState(
        E_priv=float(privacy_snapshot["E_priv"]),
        E_copy=float(copyright_snapshot["E_copy"]),
        B_priv_remaining=float(privacy_snapshot["B_priv_remaining"]),
        B_copy_remaining=float(copyright_snapshot["B_copy_remaining"]),
        privacy_risk=_clamp(risks["privacy"] + privacy_exposure),
        copyright_risk=_clamp(risks["copyright"] + copyright_exposure),
        audit_risk=_clamp(risks["audit"] + (0.25 if not audit_valid else 0.0)),
        trust_score=trust,
        request_frequency=previous.request_frequency + 1,
        semantic_repetition=repetition,
        previous_actions=[*previous.previous_actions, list(previous.previous_actions[-1] if previous.previous_actions else [])][-8:],
        previous_attack_indicators=[],
        previous_audit_result="valid" if audit_valid else "tampered",
        last_semantic_intent=current_intent,
    )


def state_hash(state: CGState) -> str:
    payload = json.dumps(state.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
