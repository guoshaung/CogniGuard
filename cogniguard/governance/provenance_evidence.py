"""Versioned source-evidence records and the only two ways they may affect a decision.

Schema `pe-0.1`. Semantics are in `docs/integration/PROVENANCE_EVIDENCE_SCHEMA.md`.

Four identities are kept apart:

* content identity   -> `matched_knowledge_units`: units the observed artifact carries;
* issuance identity  -> `candidate_issuance_ids`: receipts the content may come from;
* propagation event  -> `trusted_event_id`: set only by a trusted channel log;
* retained knowledge -> the holdings `check_release` sees. It only grows.

A record never authorizes anything. Authorization stays with
`AccessRegistry.is_authorized`. A record can do two things:

1. `holding_units` adds units to the holder's knowledge before `check_release`.
   Any evidence type may do this. Adding units only makes the gate stricter,
   so a wrong detection costs utility, not safety.
2. `trusted_event_credits` counts verified, de-duplicated trusted events that
   may reduce the unknown-propagation budget f (Theory sec. 4.2). Watermark,
   fingerprint, retrieval and credential matches never count here.

The records travel inside the existing `DomainEvidence(domain="provenance")`
envelope; no second pipeline is introduced.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum

from cogniguard.governance.evidence import DomainEvidence

SCHEMA_VERSION = "pe-0.1"


class EvidenceType(str, Enum):
    FINGERPRINT = "fingerprint"            # exact / MinHash / SimHash content match
    RETRIEVAL = "retrieval"                # BM25 / dense retrieval match
    SIGNED_CREDENTIAL = "signed_credential"  # embedded or attached signed issuance credential
    WATERMARK = "watermark"                # watermark detector only
    WATERMARK_KNOWLEDGE = "watermark_knowledge"  # watermark AND knowledge-unit check
    KNOWLEDGE_BOUND_WATERMARK = "knowledge_bound_watermark"  # candidate method under test
    TRUSTED_EVENT = "trusted_event"        # trusted channel log entry for one propagation


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"            # detector output, not checked
    CONTENT_VERIFIED = "content_verified"  # units confirmed present in the artifact
    EVENT_VERIFIED = "event_verified"    # trusted channel signature checked; TRUSTED_EVENT only
    INCONCLUSIVE = "inconclusive"
    REJECTED = "rejected"


CONTENT_TYPES = frozenset(EvidenceType) - {EvidenceType.TRUSTED_EVENT}


class SchemaError(ValueError):
    pass


Unit = tuple[str, str]  # (resource_id, unit_id), the key used by check_release


@dataclass(frozen=True)
class ProvenanceEvidence:
    schema_version: str
    evidence_id: str
    artifact_id: str
    holder_principal_id: str
    evidence_type: EvidenceType
    candidate_issuance_ids: tuple[str, ...]
    matched_knowledge_units: tuple[Unit, ...]
    confidence: float
    verification_status: VerificationStatus
    trusted_event_id: str | None
    policy_version: int
    model_and_detector_version: str
    observed_at: float
    event_sender_principal_id: str | None = None
    extra: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_type", EvidenceType(self.evidence_type))
        object.__setattr__(self, "verification_status", VerificationStatus(self.verification_status))
        object.__setattr__(self, "candidate_issuance_ids", tuple(self.candidate_issuance_ids))
        object.__setattr__(
            self, "matched_knowledge_units", tuple(tuple(u) for u in self.matched_knowledge_units)
        )
        if self.schema_version != SCHEMA_VERSION:
            raise SchemaError(f"unsupported schema_version {self.schema_version!r}")
        for name in ("evidence_id", "artifact_id", "holder_principal_id", "model_and_detector_version"):
            if not getattr(self, name):
                raise SchemaError(f"{name} is required")
        if not (isinstance(self.confidence, (int, float)) and math.isfinite(self.confidence)
                and 0.0 <= self.confidence <= 1.0):
            raise SchemaError("confidence must be a number in [0, 1]")
        if any(len(u) != 2 or not all(u) for u in self.matched_knowledge_units):
            raise SchemaError("matched_knowledge_units are (resource_id, unit_id) pairs")
        is_event = self.evidence_type is EvidenceType.TRUSTED_EVENT
        if is_event:
            if not self.trusted_event_id or not self.event_sender_principal_id:
                raise SchemaError("trusted_event needs trusted_event_id and event_sender_principal_id")
        else:
            if self.trusted_event_id is not None:
                raise SchemaError("only trusted_event records may carry trusted_event_id")
            if self.verification_status is VerificationStatus.EVENT_VERIFIED:
                raise SchemaError("content evidence cannot be event_verified")

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ProvenanceEvidence:
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(data) - known
        if unknown:
            raise SchemaError(f"unknown fields {sorted(unknown)}; put them under 'extra'")
        return cls(**data)  # type: ignore[arg-type]

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "evidence_id": self.evidence_id,
            "artifact_id": self.artifact_id,
            "holder_principal_id": self.holder_principal_id,
            "evidence_type": self.evidence_type.value,
            "candidate_issuance_ids": list(self.candidate_issuance_ids),
            "matched_knowledge_units": [list(u) for u in self.matched_knowledge_units],
            "confidence": self.confidence,
            "verification_status": self.verification_status.value,
            "trusted_event_id": self.trusted_event_id,
            "policy_version": self.policy_version,
            "model_and_detector_version": self.model_and_detector_version,
            "observed_at": self.observed_at,
            "event_sender_principal_id": self.event_sender_principal_id,
            "extra": dict(self.extra),
        }

    def to_domain_evidence(self) -> DomainEvidence:
        """Wrap in the existing envelope type. risk_score is not a decision input."""
        return DomainEvidence(domain="provenance", risk_score=0.0, provenance=self.to_dict())


def holding_units(evidence: ProvenanceEvidence, min_confidence: float = 0.0) -> frozenset[Unit]:
    """Units this record adds to the holder's knowledge. Never removes anything.

    REJECTED records add nothing. Every other status adds its matched units once
    confidence reaches `min_confidence`; the default 0 is the conservative choice
    (any detection makes the gate stricter). Raising it trades safety for utility
    and must be reported as a parameter.
    """
    if evidence.verification_status is VerificationStatus.REJECTED:
        return frozenset()
    if evidence.confidence < min_confidence:
        return frozenset()
    return frozenset(evidence.matched_knowledge_units)


def augment_knowledge(
    knowledge: Mapping[str, frozenset],
    evidences: Iterable[ProvenanceEvidence],
    min_confidence: float = 0.0,
    sender_holdings: Mapping[str, frozenset] | None = None,
) -> dict[str, frozenset]:
    """Receipt knowledge (`DisclosureStore.holders_of`) plus evidence holdings.

    The result is a superset of `knowledge` for every principal, so passing it to
    `check_release` can only turn allow into deny. For a verified trusted event the
    receiver is charged the sender's full holdings (Theory sec. 4.2, condition 3);
    pass `sender_holdings` to apply that, otherwise only matched units are added.
    """
    out = {name: frozenset(units) for name, units in knowledge.items()}
    for ev in evidences:
        add = set(holding_units(ev, min_confidence))
        if (ev.evidence_type is EvidenceType.TRUSTED_EVENT
                and ev.verification_status is VerificationStatus.EVENT_VERIFIED
                and sender_holdings is not None):
            add |= set(sender_holdings.get(ev.event_sender_principal_id, frozenset()))
        if add:
            out[ev.holder_principal_id] = out.get(ev.holder_principal_id, frozenset()) | add
    return out


def trusted_event_credits(evidences: Iterable[ProvenanceEvidence]) -> int:
    """d in k + (f - d): distinct verified trusted events. Content evidence never counts."""
    return len({
        ev.trusted_event_id
        for ev in evidences
        if ev.evidence_type is EvidenceType.TRUSTED_EVENT
        and ev.verification_status is VerificationStatus.EVENT_VERIFIED
    })
