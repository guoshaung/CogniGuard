"""The four pe-1.0 interfaces. Codex implements SourceDetector; Grok implements
StateUpdater / DisclosurePolicy (or wraps his shadow path in them). Reference
implementations live in verify.py, state.py and decision.py.

    artifact ──SourceDetector.detect──► Observation*
             ──EvidenceVerifier.verify──► VerifiedEvidence
             ──StateUpdater.apply──────► StateDelta  (ledger only grows)
    request  ──DisclosurePolicy.decide─► DisclosureDecision

No interface receives evaluation labels. A detector may be offline (replay of a
JSONL file) or online (called per artifact); governance cannot tell the difference.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from cogniguard.provenance.schema import (
    DisclosureDecision,
    DisclosureRequest,
    Observation,
    Unit,
    VerifiedEvidence,
)


@dataclass(frozen=True)
class Artifact:
    """What governance actually observed: text plus who holds it. No labels."""

    artifact_id: str
    holder_principal_id: str  # or UNKNOWN
    text: str
    observed_at: float


@runtime_checkable
class SourceDetector(Protocol):
    """Detection. Must not raise on bad input: return detector_status=error instead."""

    method_version: str

    def detect(self, artifact: Artifact) -> list[Observation]: ...


@runtime_checkable
class EvidenceVerifier(Protocol):
    """Verification. Pure function of the observation and verifier-side context
    (keys, registered unit texts, the artifact text). Never sees labels."""

    verifier_version: str

    def verify(self, observation: Observation, artifact: Artifact | None) -> VerifiedEvidence: ...


@dataclass(frozen=True)
class StateDelta:
    confirmed_added: frozenset[tuple[str, Unit]] = frozenset()
    suspected_added: frozenset[tuple[str, Unit]] = frozenset()
    events_added: tuple[str, ...] = ()
    duplicate: bool = False
    conflict: str = ""


@runtime_checkable
class StateUpdater(Protocol):
    """Security-state update. Ledger (confirmed) and overlay (suspected) only grow;
    the same observation_id or event_id applies at most once."""

    def apply(self, evidence: VerifiedEvidence) -> StateDelta: ...

    def record_delivery(self, principal: str, units: Iterable[Unit]) -> None: ...

    def knowledge(self, layer: str) -> Mapping[str, frozenset[Unit]]: ...

    def trusted_event_credits(self) -> int: ...


@runtime_checkable
class DisclosurePolicy(Protocol):
    """Disclosure decision. Authorization comes only from AccessRegistry."""

    governance_mode: str

    def decide(self, request: DisclosureRequest, state: StateUpdater) -> DisclosureDecision: ...


def run_pipeline(
    artifacts: Iterable[Artifact],
    observations: Iterable[Observation],
    verifier: EvidenceVerifier,
    state: StateUpdater,
) -> list[StateDelta]:
    """Replay helper: verify and apply observations in arrival order."""
    by_artifact = {a.artifact_id: a for a in artifacts}
    deltas = []
    for obs in sorted(observations, key=lambda o: (o.observed_at, o.observation_id)):
        deltas.append(state.apply(verifier.verify(obs, by_artifact.get(obs.artifact_id))))
    return deltas
