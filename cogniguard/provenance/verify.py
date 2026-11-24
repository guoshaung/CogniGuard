"""Reference EvidenceVerifier for pe-1.0 (rules in PROVENANCE_INTERFACE.md §4)."""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from cogniguard.provenance.interfaces import Artifact
from cogniguard.provenance.schema import (
    SCHEMA_VERSION,
    UNKNOWN,
    DetectorStatus,
    EvidenceType,
    Observation,
    Presence,
    Unit,
    VerificationStatus,
    VerifiedEvent,
    VerifiedEvidence,
)

UnitChecker = Callable[[Artifact | None, Unit], Presence]


def sign(key: bytes, *parts: str | None) -> str:
    msg = "|".join("" if p is None else p for p in parts).encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def _tokens(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9μ]+", text.lower()))


@dataclass
class TextUnitChecker:
    """Knowledge check: is a registered phrasing of the unit in some sentence of the artifact?
    Containment |sentence ∩ phrasing| / |phrasing| >= threshold over lower-cased word sets.
    Containment, not Jaccard, so surrounding words (a watermark carrier, "Note:") do not hide
    a fact that is fully present. Default 0.95; formal runs fix it in PREREG_X3E2E.
    A lexical miss is not proof of absence, so a miss returns UNKNOWN (claim stays suspected);
    ABSENT is returned only when the artifact has no text at all."""

    phrasings: Mapping[Unit, tuple[str, ...]]
    threshold: float = 0.95

    def __call__(self, artifact: Artifact | None, unit: Unit) -> Presence:
        if artifact is None or unit not in self.phrasings:
            return Presence.UNKNOWN
        if not artifact.text.strip():
            return Presence.ABSENT
        refs = [_tokens(p) for p in self.phrasings[unit]]
        for sentence in re.split(r"(?<=[.!?])\s+", artifact.text):
            s = _tokens(sentence)
            if s and any(len(s & r) / len(r) >= self.threshold for r in refs if r):
                return Presence.PRESENT
        return Presence.UNKNOWN


@dataclass
class RuleVerifier:
    log_key: bytes
    credential_key: bytes
    unit_checker: UnitChecker = field(default=lambda artifact, unit: Presence.UNKNOWN)
    allow_ideal: bool = False
    allow_mock: bool = False
    verifier_version: str = "rule-verifier-1.0"

    def _out(self, obs: Observation, status: VerificationStatus, reason: str, **kw) -> VerifiedEvidence:
        return VerifiedEvidence(SCHEMA_VERSION, obs.observation_id, obs.evidence_type, status,
                                self.verifier_version, kw.pop("holder", obs.holder_principal_id),
                                candidate_issuance_ids=obs.issuance_candidates.ids, reason=reason, **kw)

    def verify(self, obs: Observation, artifact: Artifact | None) -> VerifiedEvidence:
        if obs.detector_status is DetectorStatus.ERROR:
            return self._out(obs, VerificationStatus.UNKNOWN, "detector_error")
        if obs.evidence_type is EvidenceType.MOCK and not self.allow_mock:
            return self._out(obs, VerificationStatus.REJECTED, "mock_not_allowed")
        if obs.evidence_type is EvidenceType.IDEAL:
            if not self.allow_ideal:
                return self._out(obs, VerificationStatus.REJECTED, "ideal_not_allowed")
            return self._ideal(obs)

        holder = obs.holder_principal_id
        event = None
        issuances: tuple[str, ...] = ()
        if obs.event_claim is not None:  # trusted_log (or mock)
            e = obs.event_claim
            good = e.signature is not None and hmac.compare_digest(
                e.signature, sign(self.log_key, e.event_id, e.sender_principal_id,
                                  e.receiver_principal_id, e.issuance_id))
            if not good:
                return self._out(obs, VerificationStatus.REJECTED, "bad_log_signature")
            if holder not in (UNKNOWN, e.receiver_principal_id):
                return self._out(obs, VerificationStatus.CONFLICT, "log_receiver_is_not_holder")
            holder = e.receiver_principal_id
            event = VerifiedEvent(e.event_id, e.sender_principal_id, e.receiver_principal_id, e.issuance_id)
        if obs.credential is not None:
            c = obs.credential
            if not hmac.compare_digest(c.signature, sign(self.credential_key, c.issuance_id)):
                return self._out(obs, VerificationStatus.REJECTED, "bad_credential_signature", holder=holder)
            issuances = (c.issuance_id,)

        confirmed, suspected, conflicting = set(), set(), set()
        for claim in obs.unit_claims:
            if claim.presence is not Presence.PRESENT:
                continue  # absence never removes knowledge
            seen = self.unit_checker(artifact, claim.unit)
            if seen is Presence.PRESENT and holder != UNKNOWN:
                confirmed.add(claim.unit)
            elif seen is Presence.ABSENT:
                conflicting.add(claim.unit)
            else:
                suspected.add(claim.unit)
        if conflicting:
            return self._out(obs, VerificationStatus.CONFLICT, "unit_check_failed", holder=holder,
                             suspected_units=frozenset(suspected | confirmed),
                             conflicting_units=frozenset(conflicting))
        verified = bool(confirmed or event or issuances)
        return self._out(obs, VerificationStatus.VERIFIED if verified else VerificationStatus.UNVERIFIED,
                         "ok" if verified else "nothing_checkable", holder=holder,
                         confirmed_units=frozenset(confirmed), suspected_units=frozenset(suspected),
                         verified_issuance_ids=issuances, verified_event=event)

    def _ideal(self, obs: Observation) -> VerifiedEvidence:
        units = frozenset(c.unit for c in obs.unit_claims if c.presence is Presence.PRESENT)
        e = obs.event_claim
        event = None if e is None else VerifiedEvent(e.event_id, e.sender_principal_id,
                                                     e.receiver_principal_id, e.issuance_id)
        known = obs.holder_principal_id != UNKNOWN
        return self._out(obs, VerificationStatus.VERIFIED, "ideal_upper_bound",
                         confirmed_units=units if known else frozenset(),
                         suspected_units=frozenset() if known else units,
                         verified_issuance_ids=obs.issuance_candidates.ids, verified_event=event)
