"""pe-0.1 -> pe-1.0 conversion (one-way, lossless into `extra`).

pe-0.1 records were produced against integration@f65ebab (e.g. Codex Gate W0-Real,
codex/gate-w0-real@40213d3). Rules:

* evidence_id -> observation_id; model_and_detector_version -> method_version.
* evidence_type: watermark_knowledge -> joint; trusted_event -> trusted_log; others unchanged.
* matched_knowledge_units -> unit_claims (present). pe-0.1 `verification_status` was set by
  the detector; in pe-1.0 the verifier decides, so it moves to extra.pe01_verification_status.
* confidence: pe-0.1 values were uncalibrated -> confidence null, original in extra.
* extra.candidate_source_ids + match_scores -> source_candidates / issuance_candidates.
* A holder bound only to a simulation placeholder (extra.holder_binding ==
  "caller_supplied_simulation_id" and no run context) -> UNKNOWN unless `bind_holders` is set.
* A non-null trusted_event_id cannot be converted: pe-1.0 needs signed endpoints. Raises.
"""

from __future__ import annotations

from collections.abc import Mapping

from cogniguard.provenance.schema import (
    SCHEMA_VERSION,
    UNKNOWN,
    Candidate,
    CandidateSet,
    ConfidenceKind,
    DetectorStatus,
    EvidenceType,
    Observation,
    Presence,
    ScanStatus,
    SchemaError,
    UnitClaim,
    _check_no_gold,
)

_TYPE = {"watermark_knowledge": "joint", "trusted_event": "trusted_log"}


def _cset(ids, scores: Mapping | None) -> CandidateSet:
    ids = list(dict.fromkeys(ids))
    if not ids:
        return CandidateSet(ScanStatus.NONE)
    scores = scores or {}
    return CandidateSet(ScanStatus.FOUND, tuple(
        Candidate(i, float(scores[i]) if isinstance(scores.get(i), (int, float)) else None) for i in ids))


def from_pe01(d: Mapping, *, bind_holders: bool = False) -> Observation:
    if d.get("schema_version") != "pe-0.1":
        raise SchemaError("not a pe-0.1 record")
    _check_no_gold(d)
    if d.get("trusted_event_id") is not None:
        raise SchemaError("pe-0.1 trusted events carry no signed endpoints; cannot convert")
    extra = dict(d.get("extra") or {})
    holder = d["holder_principal_id"]
    if extra.get("holder_binding") == "caller_supplied_simulation_id" and not bind_holders:
        extra["pe01_holder_placeholder"] = holder
        holder = UNKNOWN
    scores = extra.get("match_scores") or {}
    out_extra = {k: v for k, v in extra.items() if k not in ("candidate_source_ids", "match_scores")}
    out_extra.update(pe01_verification_status=d.get("verification_status"),
                     pe01_confidence=d.get("confidence"), pe01_evidence_type=d.get("evidence_type"))
    units = tuple(dict.fromkeys(tuple(u) for u in d.get("matched_knowledge_units", ())))
    return Observation(
        schema_version=SCHEMA_VERSION,
        observation_id=d["evidence_id"],
        artifact_id=d["artifact_id"],
        holder_principal_id=holder,
        evidence_type=EvidenceType(_TYPE.get(d["evidence_type"], d["evidence_type"])),
        method_version=d["model_and_detector_version"],
        detector_status=DetectorStatus.OK,
        source_candidates=_cset(extra.get("candidate_source_ids", ()), scores.get("source")),
        issuance_candidates=_cset(d.get("candidate_issuance_ids", ()), scores.get("issuance")),
        unit_claims=tuple(UnitClaim(u, Presence.PRESENT) for u in units),
        confidence=None,
        confidence_kind=ConfidenceKind.UNCALIBRATED,
        calibration_id=None,
        policy_version=int(d.get("policy_version", 0)),
        observed_at=float(d.get("observed_at", 0.0)),
        extra=out_extra,
    )
