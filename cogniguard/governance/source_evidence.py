"""Replaceable source-evidence records for a shadow governance path.

Four facts stay on separate fields: content identity, issuance identity, an
actual propagation event, and the knowledge units a check still matches.
Watermark and fingerprint confidence never becomes a trusted event.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

EVIDENCE_TYPES = (
    "fingerprint",
    "watermark",
    "signed_credential",
    "trusted_log",
    "ideal",
)
VERIFICATION_STATUSES = ("verified", "unverified", "conflict", "absent")
TRUSTED_TYPES = frozenset({"signed_credential", "trusted_log", "ideal"})
REQUIRED_FIELDS = (
    "evidence_id",
    "evidence_type",
    "artifact_id",
    "candidate_issuance_ids",
    "matched_knowledge_units",
    "confidence",
    "verification_status",
    "trusted_event_id",
    "policy_version",
)
OPTIONAL_FIELDS = ("holdings_asserted", "holder_principal_id")

UnitRef = tuple[str, str]


def _ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("candidate_issuance_ids must be a list")
    return tuple(str(item) for item in value)


def _units(value: Any) -> tuple[UnitRef, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("matched_knowledge_units must be a list")
    found: list[UnitRef] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("a knowledge unit is a [resource_id, unit_id] pair")
        found.append((str(item[0]), str(item[1])))
    return tuple(found)


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    """One observation. `confidence` is not an authorization input."""

    evidence_id: str
    evidence_type: str
    artifact_id: str
    candidate_issuance_ids: tuple[str, ...]
    matched_knowledge_units: tuple[UnitRef, ...]
    confidence: float
    verification_status: str
    trusted_event_id: str | None
    policy_version: int
    holdings_asserted: bool = False
    holder_principal_id: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_id or not self.artifact_id:
            raise ValueError("evidence_id and artifact_id must be non-empty")
        if self.evidence_type not in EVIDENCE_TYPES:
            raise ValueError(self.evidence_type)
        if self.verification_status not in VERIFICATION_STATUSES:
            raise ValueError(self.verification_status)
        confidence = float(self.confidence)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must lie in [0, 1]")
        event = self.trusted_event_id
        if event is not None:
            event = str(event) or None
        holder = self.holder_principal_id
        if holder is not None:
            holder = str(holder) or None
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "policy_version", int(self.policy_version))
        object.__setattr__(self, "candidate_issuance_ids", tuple(self.candidate_issuance_ids))
        object.__setattr__(self, "matched_knowledge_units", tuple(self.matched_knowledge_units))
        object.__setattr__(self, "trusted_event_id", event)
        object.__setattr__(self, "holdings_asserted", bool(self.holdings_asserted))
        object.__setattr__(self, "holder_principal_id", holder)

    def is_trusted_event(self) -> bool:
        """Verified credential, log, or ideal evidence only.

        A trusted log also needs `trusted_event_id`. Fingerprint and watermark
        rows return False even when `verification_status` is verified and
        `confidence` is 1.
        """
        if self.verification_status != "verified":
            return False
        if self.evidence_type not in TRUSTED_TYPES:
            return False
        if self.evidence_type == "trusted_log" and not self.trusted_event_id:
            return False
        return True

    def trusted_issuance_ids(self) -> tuple[str, ...]:
        if not self.is_trusted_event():
            return ()
        return self.candidate_issuance_ids

    def trusted_units(self) -> tuple[UnitRef, ...]:
        if not self.is_trusted_event():
            return ()
        return self.matched_knowledge_units

    def confirms_propagation(self) -> bool:
        """A credential identifies an issuance. It does not prove a later hop.

        Only a verified trusted log or ideal row that carries an event id does.
        """
        if not self.is_trusted_event() or not self.trusted_event_id:
            return False
        return self.evidence_type in {"trusted_log", "ideal"}

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type,
            "artifact_id": self.artifact_id,
            "candidate_issuance_ids": list(self.candidate_issuance_ids),
            "matched_knowledge_units": [list(unit) for unit in self.matched_knowledge_units],
            "confidence": self.confidence,
            "verification_status": self.verification_status,
            "trusted_event_id": self.trusted_event_id,
            "policy_version": self.policy_version,
        }
        if self.holdings_asserted:
            payload["holdings_asserted"] = True
        if self.holder_principal_id is not None:
            payload["holder_principal_id"] = self.holder_principal_id
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SourceEvidence:
        unknown = set(payload) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"unknown evidence fields: {names}")
        missing = [key for key in REQUIRED_FIELDS if key not in payload]
        if missing:
            raise ValueError("missing " + ", ".join(missing))
        event = payload["trusted_event_id"]
        if event is not None and not isinstance(event, str):
            raise ValueError("trusted_event_id must be a string or null")
        holder = payload.get("holder_principal_id")
        if holder is not None and not isinstance(holder, str):
            raise ValueError("holder_principal_id must be a string or null")
        return cls(
            evidence_id=str(payload["evidence_id"]),
            evidence_type=str(payload["evidence_type"]),
            artifact_id=str(payload["artifact_id"]),
            candidate_issuance_ids=_ids(payload["candidate_issuance_ids"]),
            matched_knowledge_units=_units(payload["matched_knowledge_units"]),
            confidence=float(payload["confidence"]),
            verification_status=str(payload["verification_status"]),
            trusted_event_id=event,
            policy_version=int(payload["policy_version"]),
            holdings_asserted=bool(payload.get("holdings_asserted", False)),
            holder_principal_id=holder,
        )


def load_evidence_list(payload: Mapping[str, Any] | list) -> tuple[SourceEvidence, ...]:
    if isinstance(payload, list):
        rows = payload
    elif "evidence" in payload:
        rows = payload["evidence"]
    else:
        raise ValueError("evidence list is missing")
    return tuple(SourceEvidence.from_dict(row) for row in rows)
