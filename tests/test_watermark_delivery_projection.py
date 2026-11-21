"""Final delivery receipts take precedence over historical demo watermarks."""

from copy import deepcopy

from cogniguard.protection.text_provenance import TextProvenanceService


def _result(service, *, mode="semantic"):
    record = service.bind("Safe final answer.", answer_id="a1", sources=[{"resource_id": "r1"}])
    return {
        "session_id": "server-session",
        "session_state": {"session_id": "untrusted-old-session"},
        "text_watermark": record,
        "protection": {
            "session_id": "server-session",
            "request_id": "request-1",
            "watermark_verification": service.verify(record["text"], record),
        },
        "output_validation": {"decision": "allow"},
    }


def test_registration_prefers_verified_final_delivery_and_server_session(monkeypatch):
    from cogniguard.api.services import watermarks

    monkeypatch.setattr(watermarks, "RECENT_WATERMARK_SESSIONS", {})
    result = _result(TextProvenanceService(b"s" * 32, required=True))
    watermarks.register_watermark_session(result)
    payload = watermarks.get_watermark_rounds("server-session")
    assert payload["data_source"] == "final-delivery"
    assert "untrusted-old-session" not in watermarks.RECENT_WATERMARK_SESSIONS
    row = payload["rounds"][0]
    assert row["watermark_mode"] == "semantic_marker"
    assert row["watermark_verified"] is True
    assert row["provenance_valid"] is True
    assert row["statistical_watermark"] is False
    assert row["post_watermark_text"] == result["text_watermark"]["text"]
    assert row["pre_watermark_text"] == ""
    assert row["detection_result"]["detection_confidence"] is None


def test_projection_does_not_turn_failed_verification_into_mock_success(monkeypatch):
    from cogniguard.api.services import watermarks

    monkeypatch.setattr(watermarks, "RECENT_WATERMARK_SESSIONS", {})
    result = _result(TextProvenanceService(b"s" * 32, required=True))
    result["protection"]["watermark_verification"]["valid"] = False
    watermarks.register_watermark_session(result)
    row = watermarks.get_watermark_rounds("server-session")["rounds"][0]
    assert row["watermark_verified"] is False
    assert row["chain_valid"] is False
    assert row["detection_result"]["watermark_detected"] is False


def test_optional_provenance_only_receipt_preserves_its_actual_mode(monkeypatch):
    from cogniguard.api.services import watermarks

    monkeypatch.setattr(watermarks, "RECENT_WATERMARK_SESSIONS", {})
    service = TextProvenanceService(b"s" * 32, mode="statistical", required=False)
    result = _result(service)
    watermarks.register_watermark_session(result)
    row = watermarks.get_watermark_rounds("server-session")["rounds"][0]
    assert row["watermark_mode"] == "provenance_only"
    assert row["watermark_verified"] is False
    assert row["provenance_valid"] is True
    assert row["statistical_watermark"] is False


def test_registration_appends_delivery_rounds_and_retains_old_fallback(monkeypatch):
    from cogniguard.api.services import watermarks

    monkeypatch.setattr(watermarks, "RECENT_WATERMARK_SESSIONS", {})
    service = TextProvenanceService(b"s" * 32, required=True)
    first, second = _result(service), _result(service)
    watermarks.register_watermark_session(first)
    watermarks.register_watermark_session(second)
    assert len(watermarks.get_watermark_rounds("server-session")["rounds"]) == 2
    legacy = {
        "session_state": {
            "session_id": "historical",
            "audit_trace": {
                "watermarks": [{"watermark_id": "legacy", "audit_record": {"round_id": 1}}]
            },
        }
    }
    watermarks.register_watermark_session(deepcopy(legacy))
    assert watermarks.get_watermark_rounds("historical")["rounds"][0]["watermark_id"] == "legacy"


def test_final_delivery_detection_rejects_tampering_instead_of_using_demo_similarity(monkeypatch):
    from cogniguard.api.services import watermarks

    monkeypatch.setattr(watermarks, "RECENT_WATERMARK_SESSIONS", {})
    result = _result(TextProvenanceService(b"s" * 32, required=True))
    watermarks.register_watermark_session(result)
    query = {
        "session_id": "server-session",
        "text": result["text_watermark"]["text"],
        "answer_id": "a1",
    }
    detected = watermarks.detect_semantic_watermark(query)
    assert detected["watermark_verified"] is True
    assert detected["statistical_watermark"] is False
    changed = watermarks.detect_semantic_watermark({**query, "text": query["text"] + "changed"})
    assert changed["watermark_detected"] is False
    assert changed["tamper_suspicion"] is True
    assert changed["detection_confidence"] is None
    forged_source = watermarks.detect_semantic_watermark(
        {**query, "audit_fields": {"resource_id": "forged"}}
    )
    assert forged_source["watermark_detected"] is False
    unknown = watermarks.detect_semantic_watermark({**query, "session_id": "unknown"})
    assert unknown["watermark_detected"] is False
    assert unknown["matched_evidence"] == {}
