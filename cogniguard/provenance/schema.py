"""Provenance interface pe-1.0: record types shared by detectors, verifiers and governance.

Normative text: docs/integration/PROVENANCE_INTERFACE.md. JSON Schema:
cogniguard/provenance/schemas/pe-1.0/. Changing a field or a meaning needs pe-1.1+.

Five identities never share a field:
  content source   -> Observation.source_candidates      (which registered source text)
  issuance         -> Observation.issuance_candidates    (which release / receipt)
  knowledge units  -> Observation.unit_claims            (which facts the artifact carries)
  principal        -> holder_principal_id / event ends   (who holds the artifact)
  propagation      -> Observation.event_claim            (one hop, trusted channel only)
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Any

SCHEMA_VERSION = "pe-1.0"
UNKNOWN = "UNKNOWN"
Unit = tuple[str, str]  # (resource_id, unit_id): the key check_release uses

# Field names that would carry evaluation truth. A governance-side record that
# contains any of them is rejected, wherever it appears.
_GOLD_PATTERN = re.compile(r"(^|_)(gold|truth|oracle|label|true)(_|$)", re.IGNORECASE)


class SchemaError(ValueError):
    pass


class GoldLeakError(SchemaError):
    """A record that governance may read carries an evaluation label."""


class EvidenceType(str, Enum):
    FINGERPRINT = "fingerprint"                # exact / MinHash / SimHash
    RETRIEVAL = "retrieval"                    # BM25 / dense / rerank
    WATERMARK = "watermark"                    # detector only (e.g. KBPW M1)
    JOINT = "joint"                            # watermark AND content check (e.g. M1+source, M1 ∩ BGE)
    KNOWLEDGE_BOUND_WATERMARK = "knowledge_bound_watermark"  # e.g. KBPW M2 / M3
    SIGNED_CREDENTIAL = "signed_credential"    # verifiable issuance credential
    TRUSTED_LOG = "trusted_log"                # signed channel log entry for one hop
    IDEAL = "ideal"                            # built from gold; upper-bound arm only
    MOCK = "mock"                              # engineering tests only; never formal


class ScanStatus(str, Enum):
    FOUND = "found"            # >= 1 candidate returned
    NONE = "none"              # checked, nothing matched
    NOT_CHECKED = "not_checked"  # this method does not produce this identity
    ERROR = "error"            # the check failed; treat as UNKNOWN


class Presence(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class ConfidenceKind(str, Enum):
    CALIBRATED = "calibrated"      # P(top claim correct) on calibration split `calibration_id`
    UNCALIBRATED = "uncalibrated"  # confidence must be null; only raw scores are given


class DetectorStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"      # at least one claim independently checked, none contradicted
    UNVERIFIED = "unverified"  # well-formed, nothing could be checked
    CONFLICT = "conflict"      # a claim was contradicted by a check or by another record
    REJECTED = "rejected"      # signature / format / policy failure; record has no effect
    UNKNOWN = "unknown"        # detector error or missing input; no effect, fail closed


def _check_no_gold(data: Any, path: str = "") -> None:
    if isinstance(data, Mapping):
        for key, value in data.items():
            if _GOLD_PATTERN.search(str(key)):
                raise GoldLeakError(f"evaluation field {path}{key!r} in a governance record")
            _check_no_gold(value, f"{path}{key}.")
    elif isinstance(data, (list, tuple)):
        for item in data:
            _check_no_gold(item, path)


def _enum(cls, value, name):
    try:
        return cls(value)
    except ValueError as exc:
        raise SchemaError(f"{name}: {value!r} is not one of {[m.value for m in cls]}") from exc


def _id(value, name, allow_unknown=False):
    if not isinstance(value, str) or not value:
        raise SchemaError(f"{name} must be a non-empty string")
    if value == UNKNOWN and not allow_unknown:
        raise SchemaError(f"{name} may not be UNKNOWN")
    return value


def _unit(value, name="unit") -> Unit:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise SchemaError(f"{name} is a [resource_id, unit_id] pair")
    return (_id(value[0], name), _id(value[1], name))


def _score(value, name):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SchemaError(f"{name} must be a finite number or null")
    return float(value)


@dataclass(frozen=True)
class Candidate:
    id: str
    score: float | None = None  # method-native, larger = stronger; NOT a probability

    @classmethod
    def parse(cls, d) -> Candidate:
        if not isinstance(d, Mapping) or set(d) - {"id", "score"}:
            raise SchemaError("candidate is {id, score}")
        return cls(_id(d.get("id"), "candidate.id"), _score(d.get("score"), "candidate.score"))


@dataclass(frozen=True)
class CandidateSet:
    status: ScanStatus
    items: tuple[Candidate, ...] = ()

    def __post_init__(self) -> None:
        if (self.status is ScanStatus.FOUND) != bool(self.items):
            raise SchemaError("candidate set: status 'found' iff items is non-empty")
        ids = [c.id for c in self.items]
        if len(ids) != len(set(ids)):
            raise SchemaError("candidate ids repeat")

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(c.id for c in self.items)

    @classmethod
    def parse(cls, d) -> CandidateSet:
        if not isinstance(d, Mapping) or set(d) - {"status", "items"}:
            raise SchemaError("candidate set is {status, items}")
        return cls(_enum(ScanStatus, d.get("status"), "candidate_set.status"),
                   tuple(Candidate.parse(c) for c in d.get("items", ())))

    @classmethod
    def not_checked(cls) -> CandidateSet:
        return cls(ScanStatus.NOT_CHECKED)


@dataclass(frozen=True)
class UnitClaim:
    unit: Unit
    presence: Presence
    score: float | None = None

    @classmethod
    def parse(cls, d) -> UnitClaim:
        if not isinstance(d, Mapping) or set(d) - {"unit", "presence", "score"}:
            raise SchemaError("unit claim is {unit, presence, score}")
        return cls(_unit(d.get("unit")), _enum(Presence, d.get("presence"), "presence"),
                   _score(d.get("score"), "unit_claim.score"))


@dataclass(frozen=True)
class EventClaim:
    """One propagation hop as reported by a channel log (or by the IDEAL arm)."""

    event_id: str
    sender_principal_id: str
    receiver_principal_id: str
    issuance_id: str | None = None
    signature: str | None = None

    @classmethod
    def parse(cls, d) -> EventClaim:
        allowed = {"event_id", "sender_principal_id", "receiver_principal_id", "issuance_id", "signature"}
        if not isinstance(d, Mapping) or set(d) - allowed:
            raise SchemaError(f"event_claim keys are {sorted(allowed)}")
        return cls(_id(d.get("event_id"), "event_id"),
                   _id(d.get("sender_principal_id"), "sender_principal_id", allow_unknown=True),
                   _id(d.get("receiver_principal_id"), "receiver_principal_id", allow_unknown=True),
                   d.get("issuance_id"), d.get("signature"))


@dataclass(frozen=True)
class Credential:
    issuance_id: str
    signature: str

    @classmethod
    def parse(cls, d) -> Credential:
        if not isinstance(d, Mapping) or set(d) != {"issuance_id", "signature"}:
            raise SchemaError("credential is {issuance_id, signature}")
        return cls(_id(d["issuance_id"], "credential.issuance_id"), _id(d["signature"], "credential.signature"))


_EVENT_TYPES = {EvidenceType.TRUSTED_LOG, EvidenceType.IDEAL, EvidenceType.MOCK}


@dataclass(frozen=True)
class Observation:
    """Detector output for one artifact and one method. Carries claims, never facts."""

    schema_version: str
    observation_id: str
    artifact_id: str
    holder_principal_id: str              # concrete id or UNKNOWN
    evidence_type: EvidenceType
    method_version: str                   # model, detector, codebook / key epoch, threshold set
    detector_status: DetectorStatus
    source_candidates: CandidateSet
    issuance_candidates: CandidateSet
    unit_claims: tuple[UnitClaim, ...]
    confidence: float | None
    confidence_kind: ConfidenceKind
    calibration_id: str | None
    policy_version: int
    observed_at: float
    artifact_sha256: str | None = None
    event_claim: EventClaim | None = None
    credential: Credential | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SchemaError(f"schema_version must be {SCHEMA_VERSION}")
        _id(self.observation_id, "observation_id")
        _id(self.artifact_id, "artifact_id")
        _id(self.holder_principal_id, "holder_principal_id", allow_unknown=True)
        _id(self.method_version, "method_version")
        if self.confidence_kind is ConfidenceKind.CALIBRATED:
            if self.confidence is None or not 0.0 <= self.confidence <= 1.0 or not self.calibration_id:
                raise SchemaError("calibrated confidence needs a value in [0, 1] and calibration_id")
        elif self.confidence is not None:
            raise SchemaError("uncalibrated observations must have confidence = null")
        units = [c.unit for c in self.unit_claims]
        if len(units) != len(set(units)):
            raise SchemaError("a unit is claimed twice in one observation")
        if self.detector_status is DetectorStatus.ERROR:
            if self.unit_claims or any(s.status is not ScanStatus.ERROR
                                       for s in (self.source_candidates, self.issuance_candidates)):
                raise SchemaError("an error observation has error candidate sets and no unit claims")
        if self.event_claim is not None and self.evidence_type not in _EVENT_TYPES:
            raise SchemaError("only trusted_log / ideal / mock records may carry event_claim")
        if self.evidence_type is EvidenceType.TRUSTED_LOG and self.event_claim is None:
            raise SchemaError("trusted_log needs event_claim")
        if (self.credential is not None) != (self.evidence_type is EvidenceType.SIGNED_CREDENTIAL):
            raise SchemaError("credential is required for, and only for, signed_credential")
        if not isinstance(self.extra, Mapping):
            raise SchemaError("extra must be an object")
        _check_no_gold(self.extra, "extra.")

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Observation:
        _check_no_gold(d)
        names = {f.name for f in fields(cls)}
        unknown = set(d) - names
        if unknown:
            raise SchemaError(f"unknown fields {sorted(unknown)}; method-private data goes in 'extra'")
        required = {"schema_version", "observation_id", "artifact_id", "holder_principal_id", "evidence_type",
                    "method_version", "detector_status", "source_candidates", "issuance_candidates",
                    "unit_claims", "confidence", "confidence_kind", "calibration_id", "policy_version",
                    "observed_at"}
        missing = required - set(d)
        if missing:
            raise SchemaError(f"missing fields {sorted(missing)}")
        if not isinstance(d["policy_version"], int) or isinstance(d["policy_version"], bool):
            raise SchemaError("policy_version must be an integer")
        return cls(
            schema_version=d["schema_version"],
            observation_id=d["observation_id"],
            artifact_id=d["artifact_id"],
            holder_principal_id=d["holder_principal_id"],
            evidence_type=_enum(EvidenceType, d["evidence_type"], "evidence_type"),
            method_version=d["method_version"],
            detector_status=_enum(DetectorStatus, d["detector_status"], "detector_status"),
            source_candidates=CandidateSet.parse(d["source_candidates"]),
            issuance_candidates=CandidateSet.parse(d["issuance_candidates"]),
            unit_claims=tuple(UnitClaim.parse(c) for c in d["unit_claims"]),
            confidence=_score(d["confidence"], "confidence"),
            confidence_kind=_enum(ConfidenceKind, d["confidence_kind"], "confidence_kind"),
            calibration_id=d["calibration_id"],
            policy_version=d["policy_version"],
            observed_at=float(d["observed_at"]),
            artifact_sha256=d.get("artifact_sha256"),
            event_claim=EventClaim.parse(d["event_claim"]) if d.get("event_claim") else None,
            credential=Credential.parse(d["credential"]) if d.get("credential") else None,
            extra=d.get("extra", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        def cset(s: CandidateSet):
            return {"status": s.status.value, "items": [{"id": c.id, "score": c.score} for c in s.items]}
        out = {
            "schema_version": self.schema_version, "observation_id": self.observation_id,
            "artifact_id": self.artifact_id, "holder_principal_id": self.holder_principal_id,
            "evidence_type": self.evidence_type.value, "method_version": self.method_version,
            "detector_status": self.detector_status.value,
            "source_candidates": cset(self.source_candidates),
            "issuance_candidates": cset(self.issuance_candidates),
            "unit_claims": [{"unit": list(c.unit), "presence": c.presence.value, "score": c.score}
                            for c in self.unit_claims],
            "confidence": self.confidence, "confidence_kind": self.confidence_kind.value,
            "calibration_id": self.calibration_id, "policy_version": self.policy_version,
            "observed_at": self.observed_at, "artifact_sha256": self.artifact_sha256,
            "event_claim": None if self.event_claim is None else {
                "event_id": self.event_claim.event_id,
                "sender_principal_id": self.event_claim.sender_principal_id,
                "receiver_principal_id": self.event_claim.receiver_principal_id,
                "issuance_id": self.event_claim.issuance_id, "signature": self.event_claim.signature},
            "credential": None if self.credential is None else {
                "issuance_id": self.credential.issuance_id, "signature": self.credential.signature},
            "extra": dict(self.extra),
        }
        return out


# ------------------------------------------------------------------ verifier output

@dataclass(frozen=True)
class VerifiedEvent:
    event_id: str
    sender_principal_id: str
    receiver_principal_id: str
    issuance_id: str | None = None


@dataclass(frozen=True)
class VerifiedEvidence:
    """What a verifier accepted from one observation. The only input to state updates."""

    schema_version: str
    observation_id: str
    evidence_type: EvidenceType
    verification_status: VerificationStatus
    verifier_version: str
    holder_principal_id: str
    confirmed_units: frozenset[Unit] = frozenset()    # independently checked present
    suspected_units: frozenset[Unit] = frozenset()    # claimed present, not checked
    conflicting_units: frozenset[Unit] = frozenset()  # claimed present, check says absent
    verified_issuance_ids: tuple[str, ...] = ()       # identity only; never a grant
    candidate_issuance_ids: tuple[str, ...] = ()      # audit only
    verified_event: VerifiedEvent | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SchemaError(f"schema_version must be {SCHEMA_VERSION}")
        inert = self.verification_status in (VerificationStatus.REJECTED, VerificationStatus.UNKNOWN)
        if inert and (self.confirmed_units or self.suspected_units or self.verified_event
                      or self.verified_issuance_ids):
            raise SchemaError("rejected / unknown evidence must carry no effects")
        if self.verified_event is not None and self.evidence_type not in _EVENT_TYPES:
            raise SchemaError("only trusted_log / ideal / mock can yield a verified event")
        if self.verification_status is not VerificationStatus.VERIFIED and (
                self.confirmed_units or self.verified_event or self.verified_issuance_ids):
            raise SchemaError("only verified evidence may confirm units, issuances or events")
        if self.confirmed_units & self.suspected_units:
            raise SchemaError("a unit is either confirmed or suspected")
        if self.holder_principal_id == UNKNOWN and self.confirmed_units:
            raise SchemaError("units cannot be confirmed for an UNKNOWN holder")


# ------------------------------------------------------------------ decision records

@dataclass(frozen=True)
class DisclosureRequest:
    request_id: str
    principal_id: str
    purpose: str
    acting_org_id: str
    release_units: tuple[Unit, ...]
    now: float

    @property
    def resources(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(r for r, _ in self.release_units))


@dataclass(frozen=True)
class DisclosureDecision:
    request_id: str
    allowed: bool
    reason: str                     # "allow" | "unauthorized" | "reconstruction"
    governance_mode: str
    coalition_k_effective: int
    trusted_event_credits: int
    knowledge_layer: str            # "receipts" | "confirmed" | "confirmed+suspected"
    evidence_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"request_id": self.request_id, "allowed": self.allowed, "reason": self.reason,
                "governance_mode": self.governance_mode, "coalition_k_effective": self.coalition_k_effective,
                "trusted_event_credits": self.trusted_event_credits, "knowledge_layer": self.knowledge_layer,
                "evidence_ids": list(self.evidence_ids)}
