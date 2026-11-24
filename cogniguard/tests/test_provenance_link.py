"""Adapter tests for the provenance link. No ledger write and no X3 rerun."""

from __future__ import annotations

from pathlib import Path

import pytest

from cogniguard.governance.provenance_link import MODES, open_provenance_link


def _row(evidence_id: str, evidence_type: str, issuance_id: str | None, **extra) -> dict:
    payload = {
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "artifact_id": "art-1",
        "candidate_issuance_ids": [] if issuance_id is None else [issuance_id],
        "matched_knowledge_units": extra.pop("units", []),
        "confidence": extra.pop("confidence", 1.0),
        "verification_status": extra.pop("status", "verified"),
        "trusted_event_id": extra.pop("event", None),
        "policy_version": 1,
    }
    payload.update(extra)
    return payload


def _bundle(**extra) -> dict:
    payload = {
        "round_id": 1,
        "artifact_id": "art-1",
        "expected_source_ids": ["iss-a", "iss-b", "iss-c"],
        "evidence": [
            _row("mark", "watermark", "iss-a", confidence=1.0, event="mark-hop"),
            _row("print", "fingerprint", "iss-a", units=[["doc", "u"]]),
            _row(
                "ideal-b",
                "ideal",
                "iss-b",
                units=[["doc", "b"]],
                event="ideal-hop",
                holder_principal_id="s2",
                holdings_asserted=True,
            ),
            _row(
                "log-a",
                "trusted_log",
                "iss-a",
                units=[["doc", "a"]],
                event="log-hop",
                holder_principal_id="s1",
                holdings_asserted=True,
            ),
            _row("cred-a", "signed_credential", "iss-a"),
        ],
    }
    payload.update(extra)
    return payload


def _by_id(snapshot):
    return {item.source_id: item for item in snapshot.sources}


def test_missing_recovery_is_not_treated_as_unpropagated() -> None:
    payload = {"round_id": 1, "artifact_id": "art-1", "expected_source_ids": ["iss-a", "iss-b"]}
    for mode in MODES:
        snapshot = open_provenance_link(mode).update(payload)
        assert snapshot.recovery == "none"
        assert snapshot.admitted == ()
        assert snapshot.writes_disclosure_store is False
        assert snapshot.evaluation_status == "interface_only"
        assert {item.source_id for item in snapshot.sources} == {"iss-a", "iss-b"}
        for item in snapshot.sources:
            assert item.source_class == "unknown"
            assert item.issuance_status == "unknown"
            assert item.propagated is None
            assert item.ledger_writable is False


def test_four_modes_keep_candidates_out_of_the_ledger() -> None:
    payload = _bundle()
    static = open_provenance_link("static").update(payload)
    fingerprint = open_provenance_link("fingerprint").update(payload)
    ideal = open_provenance_link("ideal").update(payload)
    real = open_provenance_link("real").update(payload)

    assert {item.source_class for item in static.sources} == {"unknown"}
    assert static.admitted == ()

    finger = _by_id(fingerprint)
    assert finger["iss-a"].source_class == "candidate"
    assert finger["iss-a"].issuance_status == "candidate"
    assert finger["iss-a"].propagated is None
    assert finger["iss-b"].source_class == "unknown"
    assert fingerprint.admitted == ()
    assert "unverified_candidate" in {item.reason for item in fingerprint.rejected}

    ideal_sources = _by_id(ideal)
    assert ideal_sources["iss-b"].source_class == "verified"
    assert ideal_sources["iss-b"].propagated is True
    assert ideal_sources["iss-a"].source_class == "unknown"
    assert [item.source_id for item in ideal.admitted] == ["iss-b"]
    assert "mode_excluded" in {item.reason for item in ideal.rejected}

    real_sources = _by_id(real)
    assert real_sources["iss-a"].source_class == "verified"
    assert real_sources["iss-a"].issuance_status == "verified"
    assert real_sources["iss-a"].propagated is True
    assert real_sources["iss-c"].source_class == "unknown"
    assert real_sources["iss-c"].propagated is None
    assert [item.source_id for item in real.admitted] == ["iss-a"]
    mark = [item for item in real.rejected if item.evidence_id == "mark"]
    assert mark and all(item.reason == "unverified_candidate" for item in mark)
    blocked = [item for item in real.rejected if item.source_id == "iss-b"]
    assert blocked and all(item.reason == "mode_excluded" for item in blocked)


def test_credential_verifies_issuance_without_a_propagation_fact() -> None:
    payload = {
        "round_id": 1,
        "artifact_id": "art-1",
        "evidence": [_row("cred", "signed_credential", "iss-a")],
    }
    snapshot = open_provenance_link("real").update(payload)
    source = snapshot.sources[0]
    assert source.source_class == "verified"
    assert source.issuance_status == "verified"
    assert source.issuance_ids == ("iss-a",)
    assert source.propagated is None
    assert snapshot.admitted == ()
    assert snapshot.recovery == "full"


def test_partial_recovery_then_a_later_round_keeps_the_known_source() -> None:
    link = open_provenance_link("ideal")
    first = link.update(
        {
            "round_id": 1,
            "artifact_id": "art-1",
            "expected_source_ids": ["iss-a", "iss-b", "iss-c"],
            "evidence": [
                _row(
                    "ideal-a",
                    "ideal",
                    "iss-a",
                    units=[["doc", "a"]],
                    event="hop-a",
                    holder_principal_id="s1",
                    holdings_asserted=True,
                )
            ],
        }
    )
    assert first.recovery == "partial"
    assert _by_id(first)["iss-b"].propagated is None
    assert _by_id(first)["iss-c"].source_class == "unknown"
    assert [item.source_id for item in first.admitted] == ["iss-a"]

    second = link.update(
        {
            "round_id": 2,
            "artifact_id": "art-1",
            "expected_source_ids": ["iss-a", "iss-b", "iss-c"],
            "evidence": [
                _row(
                    "ideal-b",
                    "ideal",
                    "iss-b",
                    units=[["doc", "b"]],
                    event="hop-b",
                    holder_principal_id="s2",
                    holdings_asserted=True,
                )
            ],
        }
    )
    sources = _by_id(second)
    assert sources["iss-a"].source_class == "verified"
    assert sources["iss-a"].propagated is True
    assert sources["iss-b"].source_class == "verified"
    assert sources["iss-c"].source_class == "unknown"
    assert sources["iss-c"].propagated is None
    assert second.recovery == "partial"
    assert [item.source_id for item in second.admitted] == ["iss-a", "iss-b"]


def test_conflict_removes_the_source_from_the_ledger() -> None:
    link = open_provenance_link("real")
    link.update(
        {
            "round_id": 1,
            "artifact_id": "art-1",
            "evidence": [
                _row(
                    "log",
                    "trusted_log",
                    "iss-a",
                    units=[["doc", "a"]],
                    event="hop",
                    holder_principal_id="s1",
                    holdings_asserted=True,
                )
            ],
        }
    )
    conflict = link.update(
        {
            "round_id": 2,
            "artifact_id": "art-1",
            "evidence": [
                _row(
                    "log-other",
                    "trusted_log",
                    "iss-a",
                    units=[["doc", "z"]],
                    event="hop-2",
                    holder_principal_id="s9",
                    holdings_asserted=True,
                )
            ],
        }
    )
    source = _by_id(conflict)["iss-a"]
    assert source.source_class == "conflict"
    assert source.issuance_status == "conflict"
    assert source.propagated is None
    assert conflict.admitted == ()
    assert "conflict" in {item.reason for item in conflict.rejected}


def test_channels_bundle_is_accepted_for_a_later_codex_drop() -> None:
    snapshot = open_provenance_link("real").update(
        {
            "round_id": 3,
            "artifact_id": "art-9",
            "channels": {
                "watermark": [_row("mark", "watermark", "iss-a", confidence=0.2)],
                "trusted_log": [
                    _row(
                        "log",
                        "trusted_log",
                        "iss-b",
                        units=[["doc", "b"]],
                        event="hop",
                        holder_principal_id="s2",
                    )
                ],
            },
        }
    )
    sources = _by_id(snapshot)
    assert sources["iss-a"].source_class == "candidate"
    assert sources["iss-b"].source_class == "verified"
    assert [item.source_id for item in snapshot.admitted] == ["iss-b"]
    assert snapshot.recovery == "partial"


def test_a_backwards_round_is_rejected() -> None:
    link = open_provenance_link("static")
    link.update({"round_id": 2, "artifact_id": "art-1"})
    with pytest.raises(ValueError, match="round_id"):
        link.update({"round_id": 1, "artifact_id": "art-1"})


def test_link_does_not_touch_the_disclosure_store_or_the_x3_run() -> None:
    text = Path(__file__).resolve().parents[1].joinpath("governance/provenance_link.py").read_text()
    assert "import disclosure_store" not in text
    assert "DisclosureStore(" not in text
    assert "evaluate_and_reserve" not in text
    assert "x3_e2e" not in text
