from __future__ import annotations

import pytest

from cogniguard.governance.provenance_evidence import (
    SCHEMA_VERSION,
    EvidenceType,
    ProvenanceEvidence,
    SchemaError,
    VerificationStatus,
    augment_knowledge,
    holding_units,
    trusted_event_credits,
)
from cogniguard.governance.reconstruction import check_release
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry


def _ev(**over):
    base = dict(
        schema_version=SCHEMA_VERSION,
        evidence_id="ev-1",
        artifact_id="art-1",
        holder_principal_id="bob",
        evidence_type="watermark",
        candidate_issuance_ids=("rcpt-1",),
        matched_knowledge_units=(("exam", "u2"),),
        confidence=0.9,
        verification_status="content_verified",
        trusted_event_id=None,
        policy_version=3,
        model_and_detector_version="det@test",
        observed_at=1.0,
    )
    base.update(over)
    return ProvenanceEvidence(**base)


def _registry():
    target = ProtectedTarget(
        target_id="exam",
        owner_principal_id="teacher",
        org_id="school",
        witness_sets=(frozenset({("exam", "u1"), ("exam", "u2"), ("exam", "u3")}),),
    )
    return TargetRegistry([target])


def test_round_trip_and_envelope():
    ev = _ev()
    assert ProvenanceEvidence.from_dict(ev.to_dict()) == ev
    env = ev.to_domain_evidence()
    assert env.domain == "provenance" and env.provenance["schema_version"] == SCHEMA_VERSION


@pytest.mark.parametrize("over", [
    {"schema_version": "pe-0.0"},
    {"confidence": 1.5},
    {"confidence": float("nan")},
    {"trusted_event_id": "evt-9"},                       # content evidence with an event id
    {"verification_status": "event_verified"},           # content evidence claiming an event
    {"evidence_type": "trusted_event"},                  # event without id / sender
    {"matched_knowledge_units": (("exam",),)},
    {"evidence_id": ""},
])
def test_schema_rejects(over):
    with pytest.raises((SchemaError, ValueError)):
        _ev(**over)


def test_unknown_fields_rejected():
    data = _ev().to_dict() | {"grant": "allow"}
    with pytest.raises(SchemaError):
        ProvenanceEvidence.from_dict(data)


def test_watermark_never_reduces_budget():
    evs = [_ev(evidence_type=t) for t in
           ("watermark", "watermark_knowledge", "knowledge_bound_watermark", "fingerprint", "signed_credential")]
    assert trusted_event_credits(evs) == 0


def test_trusted_events_deduplicated():
    ev = dict(evidence_type="trusted_event", verification_status="event_verified",
              trusted_event_id="evt-1", event_sender_principal_id="alice")
    evs = [_ev(evidence_id="a", **ev), _ev(evidence_id="b", **ev),
           _ev(evidence_id="c", **(ev | {"trusted_event_id": "evt-2"})),
           _ev(evidence_id="d", **(ev | {"trusted_event_id": "evt-3", "verification_status": "unverified"}))]
    assert trusted_event_credits(evs) == 2


def test_rejected_adds_nothing_and_threshold_is_explicit():
    assert holding_units(_ev(verification_status="rejected")) == frozenset()
    assert holding_units(_ev(confidence=0.2), min_confidence=0.5) == frozenset()
    assert holding_units(_ev(confidence=0.2)) == {("exam", "u2")}


def test_augment_only_grows_and_feeds_check_release():
    reg = _registry()
    knowledge = {"alice": frozenset({("exam", "u1")})}
    # Receipts alone: alice + carol(u3 release) cannot finish; bob holds nothing on record.
    assert check_release(reg, "carol", {("exam", "u3")}, knowledge, k=2).safe
    grown = augment_knowledge(knowledge, [_ev()])
    assert all(knowledge[p] <= grown[p] for p in knowledge)
    # Evidence that bob holds u2 makes {alice, bob, carol} a 3-coalition; k=3 now refuses.
    assert check_release(reg, "carol", {("exam", "u3")}, knowledge, k=3).safe
    assert not check_release(reg, "carol", {("exam", "u3")}, grown, k=3).safe


def test_trusted_event_charges_sender_holdings():
    ev = _ev(evidence_type="trusted_event", verification_status="event_verified",
             trusted_event_id="evt-1", event_sender_principal_id="alice",
             matched_knowledge_units=())
    knowledge = {"alice": frozenset({("exam", "u1"), ("exam", "u2")})}
    grown = augment_knowledge(knowledge, [ev], sender_holdings=knowledge)
    assert grown["bob"] == knowledge["alice"]
