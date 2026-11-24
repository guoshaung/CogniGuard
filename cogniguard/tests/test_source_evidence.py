"""Contract tests for source-evidence records. No release store is opened."""

from __future__ import annotations

import pytest

from cogniguard.governance.source_evidence import SourceEvidence, load_evidence_list


def _row(**overrides) -> dict:
    payload = {
        "evidence_id": "ev-1",
        "evidence_type": "watermark",
        "artifact_id": "art-1",
        "candidate_issuance_ids": ["iss-1"],
        "matched_knowledge_units": [["doc", "u1"]],
        "confidence": 1.0,
        "verification_status": "verified",
        "trusted_event_id": "hop-1",
        "policy_version": 1,
    }
    payload.update(overrides)
    return payload


def test_watermark_confidence_is_not_a_trusted_event() -> None:
    row = SourceEvidence.from_dict(_row())
    assert row.confidence == 1.0
    assert row.is_trusted_event() is False
    assert row.trusted_issuance_ids() == ()
    assert row.trusted_units() == ()
    assert row.confirms_propagation() is False


def test_fingerprint_is_not_a_trusted_event() -> None:
    row = SourceEvidence.from_dict(_row(evidence_type="fingerprint"))
    assert row.is_trusted_event() is False
    assert row.confirms_propagation() is False


def test_credential_identifies_an_issuance_and_not_a_hop() -> None:
    row = SourceEvidence.from_dict(_row(evidence_type="signed_credential", trusted_event_id=None))
    assert row.is_trusted_event() is True
    assert row.trusted_issuance_ids() == ("iss-1",)
    assert row.trusted_units() == (("doc", "u1"),)
    assert row.confirms_propagation() is False


def test_trusted_log_needs_an_event_id() -> None:
    missing = SourceEvidence.from_dict(_row(evidence_type="trusted_log", trusted_event_id=None))
    present = SourceEvidence.from_dict(_row(evidence_type="trusted_log"))
    assert missing.is_trusted_event() is False
    assert present.is_trusted_event() is True
    assert present.confirms_propagation() is True


def test_ideal_evidence_can_confirm_a_hop() -> None:
    row = SourceEvidence.from_dict(_row(evidence_type="ideal"))
    assert row.is_trusted_event() is True
    assert row.confirms_propagation() is True


def test_conflict_and_absent_rows_are_not_trusted() -> None:
    for status in ("conflict", "absent", "unverified"):
        row = SourceEvidence.from_dict(
            _row(evidence_type="signed_credential", verification_status=status)
        )
        assert row.is_trusted_event() is False


def test_round_trip_and_loader() -> None:
    row = SourceEvidence.from_dict(
        _row(evidence_type="trusted_log", holdings_asserted=True, holder_principal_id="s1")
    )
    again = SourceEvidence.from_dict(row.to_dict())
    assert again == row
    loaded = load_evidence_list({"evidence": [row.to_dict()]})
    assert loaded == (row,)


def test_unknown_field_unit_shape_and_confidence_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown"):
        SourceEvidence.from_dict(_row(note="nope"))
    with pytest.raises(ValueError, match="pair"):
        SourceEvidence.from_dict(_row(matched_knowledge_units=["u1"]))
    with pytest.raises(ValueError, match="confidence"):
        SourceEvidence.from_dict(_row(confidence=1.1))
