"""Mock provider for ENGINEERING TESTS ONLY.

Every record it emits has evidence_type "mock", method_version "mock-0" and
extra.mock = true. The X3-E2E runner refuses these in --formal mode, so a mock
result can never be reported as an algorithm result.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from cogniguard.provenance.interfaces import Artifact
from cogniguard.provenance.schema import (
    SCHEMA_VERSION,
    Candidate,
    CandidateSet,
    ConfidenceKind,
    Credential,
    DetectorStatus,
    EventClaim,
    EvidenceType,
    Observation,
    Presence,
    ScanStatus,
    Unit,
    UnitClaim,
)
from cogniguard.provenance.verify import sign

MOCK_VERSION = "mock-0"


@dataclass(frozen=True)
class Planted:
    """What the mock reports for an artifact. Written by the test, not read from labels."""

    units: tuple[Unit, ...] = ()
    issuance_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    error: bool = False


def _cset(ids) -> CandidateSet:
    return CandidateSet(ScanStatus.FOUND, tuple(Candidate(i, 1.0) for i in ids)) if ids \
        else CandidateSet(ScanStatus.NONE)


def observation(obs_id: str, artifact_id: str, holder: str, *, evidence_type=EvidenceType.MOCK,
                units=(), issuance_ids=(), source_ids=(), error=False, event=None, credential=None,
                observed_at=0.0, policy_version=1, method_version=MOCK_VERSION) -> Observation:
    if error:
        err = CandidateSet(ScanStatus.ERROR)
        return Observation(SCHEMA_VERSION, obs_id, artifact_id, holder, evidence_type, method_version,
                           DetectorStatus.ERROR, err, err, (), None, ConfidenceKind.UNCALIBRATED, None,
                           policy_version, observed_at, extra={"mock": True})
    return Observation(SCHEMA_VERSION, obs_id, artifact_id, holder, evidence_type, method_version,
                       DetectorStatus.OK, _cset(source_ids), _cset(issuance_ids),
                       tuple(UnitClaim(u, Presence.PRESENT, 1.0) for u in units), None,
                       ConfidenceKind.UNCALIBRATED, None, policy_version, observed_at,
                       event_claim=event, credential=credential,
                       extra={"mock": True} if evidence_type is EvidenceType.MOCK else {})


def signed_event(log_key: bytes, event_id, sender, receiver, issuance_id=None) -> EventClaim:
    return EventClaim(event_id, sender, receiver, issuance_id,
                      sign(log_key, event_id, sender, receiver, issuance_id))


def signed_credential(credential_key: bytes, issuance_id: str) -> Credential:
    return Credential(issuance_id, sign(credential_key, issuance_id))


@dataclass
class MockDetector:
    planted: Mapping[str, Planted]
    method_version: str = MOCK_VERSION
    _n: int = field(default=0, repr=False)

    def detect(self, artifact: Artifact) -> list[Observation]:
        p = self.planted.get(artifact.artifact_id)
        if p is None:
            return []
        self._n += 1
        return [observation(f"mock-{self._n}", artifact.artifact_id, artifact.holder_principal_id,
                            units=p.units, issuance_ids=p.issuance_ids, source_ids=p.source_ids,
                            error=p.error, observed_at=artifact.observed_at)]
