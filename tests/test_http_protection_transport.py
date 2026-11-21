"""Cookies, session statuses and reviewed streaming at the HTTP boundary."""

import json
import threading
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from cogniguard.api.http_server import CogniGuardDashboardAPIHandler
from cogniguard.api.routes import cases, dialogue
from cogniguard.api.routes import watermarks as watermark_routes
from cogniguard.runtime.protection_context import publish_session_token, transport_credentials
from cogniguard.runtime.sessions import (
    BudgetExceeded,
    InvalidSessionToken,
    RequestConflict,
    SessionBusy,
)


@pytest.fixture()
def transport_api():
    server = ThreadingHTTPServer(("127.0.0.1", 0), CogniGuardDashboardAPIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def exchange(base_url, path, *, body=None, headers=None, opener=None, method="POST"):
    request = urllib.request.Request(
        base_url + path,
        data=None if method == "GET" else json.dumps(body or {}).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    try:
        response = (opener.open if opener else urllib.request.urlopen)(request, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, response.read().decode()


def test_http_transport_hides_recursive_tokens_and_issues_an_httponly_cookie(
    transport_api, monkeypatch
):
    observed = []

    def fake_chat(**kwargs):
        observed.append(transport_credentials())
        publish_session_token("server-issued-token")
        return {
            "success": True,
            "answer": "Safe",
            "session_token": "server-issued-token",
            "nested": [
                {"session_token": "hidden-nested", "traceback": "private-trace", "ok": True}
            ],
        }

    monkeypatch.setattr(dialogue, "run_free_chat", fake_chat)
    status, headers, body = exchange(
        transport_api,
        "/api/dialogue/free-chat",
        body={"message": "Hello"},
        headers={"Authorization": "Bearer incoming-token", "Idempotency-Key": "req-1"},
    )
    assert status == 200
    assert observed == [("incoming-token", "req-1")]
    assert not any(
        secret in body for secret in ("server-issued-token", "hidden-nested", "private-trace")
    )
    assert json.loads(body)["nested"] == [{"ok": True}]
    cookie = headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie and "Path=/api" in cookie


@pytest.mark.parametrize(
    "error,status,code",
    [
        (InvalidSessionToken, 401, "invalid_session"),
        (RequestConflict, 409, "request_conflict"),
        (SessionBusy, 409, "request_conflict"),
        (BudgetExceeded, 429, "budget_exceeded"),
    ],
)
def test_session_errors_have_json_statuses_without_internal_details(
    transport_api, monkeypatch, error, status, code
):
    def fail(**kwargs):
        raise error("INTERNAL_PRIVATE_SENTINEL")

    monkeypatch.setattr(dialogue, "run_free_chat", fail)
    actual, headers, body = exchange(transport_api, "/api/dialogue/free-chat")
    assert actual == status
    assert headers["Content-Type"] == "application/json"
    assert json.loads(body)["code"] == code
    assert "INTERNAL_PRIVATE_SENTINEL" not in body
    assert "traceback" not in body


def test_stream_waits_for_validation_and_sends_only_reviewed_progress(transport_api, monkeypatch):
    def execute(index, **kwargs):
        assert kwargs["event_sink"] is None
        publish_session_token("stream-token")
        return {
            "success": True,
            "answer": "Validated final",
            "session_token": "stream-token",
            "workflow_steps": [
                {"step_id": 1, "step_name": "finish", "input_summary": "DO_NOT_STREAM_RAW"}
            ],
        }

    monkeypatch.setattr(cases, "execute_case", execute)
    status, headers, body = exchange(transport_api, "/api/run-case/stream")
    assert status == 200
    assert headers["Content-Type"].startswith("application/x-ndjson")
    assert "stream-token" not in body
    assert "HttpOnly" in headers["Set-Cookie"]
    events = [json.loads(line) for line in body.splitlines()]
    progress = next(event for event in events if event["type"] == "workflow_step")
    assert progress["step"] == {"step_id": 1, "step_name": "finish"}
    assert events[-1]["type"] == "run_completed"
    assert events[-1]["result"]["answer"] == "Validated final"


def test_stream_budget_failure_happens_before_200_headers(transport_api, monkeypatch):
    def fail(*args, **kwargs):
        raise BudgetExceeded("INTERNAL_PRIVATE_SENTINEL")

    monkeypatch.setattr(cases, "execute_case", fail)
    status, headers, body = exchange(transport_api, "/api/run-case/stream")
    assert status == 429
    assert headers["Content-Type"] == "application/json"
    assert "INTERNAL_PRIVATE_SENTINEL" not in body


def test_real_anonymous_session_uses_cookie_replay_and_server_budget(
    transport_api, monkeypatch, tmp_path
):
    from cogniguard.protection.text_provenance import TextProvenanceService
    from cogniguard.runtime.gateway import ProtectionGateway
    from cogniguard.runtime.sessions import SessionStore

    store = SessionStore(tmp_path / "sessions.sqlite3", limits={"requests": 1})
    gateway = ProtectionGateway(
        store=store, provenance=TextProvenanceService(b"t" * 32, required=True)
    )
    calls = []

    def chat(**kwargs):
        def operation(frame):
            calls.append(frame.session.session_id)
            return {"success": True, "answer": "Safe offline response"}

        return gateway.run("free_chat", {"message": kwargs.get("message")}, operation)

    monkeypatch.setattr(dialogue, "run_free_chat", chat)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    first = exchange(
        transport_api,
        "/api/dialogue/free-chat",
        body={"message": "Hello"},
        headers={"Idempotency-Key": "request-1"},
        opener=opener,
    )
    assert first[0] == 200
    first_payload = json.loads(first[2])
    assert "session_token" not in first_payload
    second = exchange(
        transport_api,
        "/api/dialogue/free-chat",
        body={"message": "Hello"},
        headers={"Idempotency-Key": "request-1"},
        opener=opener,
    )
    assert second[0] == 200
    assert json.loads(second[2])["session_id"] == first_payload["session_id"]
    assert len(calls) == 1
    assert (
        exchange(
            transport_api,
            "/api/dialogue/free-chat",
            body={"message": "Another"},
            headers={"Idempotency-Key": "request-2"},
            opener=opener,
        )[0]
        == 429
    )
    cookie = SimpleCookie()
    cookie.load(first[1]["Set-Cookie"])
    assert (
        store.get_or_create(cookie["cgc_session"].value).budget_snapshot()["requests"]["used"] == 1
    )


def test_malformed_or_conflicting_credentials_are_not_silently_replaced(transport_api):
    for headers in (
        {"Authorization": "Bearer "},
        {"Cookie": "cgc_session="},
        {"Authorization": "Bearer token-b", "Cookie": "cgc_session=token-a"},
    ):
        status, _, body = exchange(transport_api, "/api/dialogue/free-chat", headers=headers)
        assert status == 401
        assert "Set-Cookie" not in body


@pytest.fixture()
def protected_store(tmp_path, monkeypatch):
    from cogniguard.api.services import watermarks
    from cogniguard.protection.text_provenance import TextProvenanceService
    from cogniguard.runtime import gateway
    from cogniguard.runtime.sessions import SessionStore

    store = SessionStore(tmp_path / "owner-sessions.sqlite3", limits={"images": 1})
    service = gateway.ProtectionGateway(
        store=store,
        provenance=TextProvenanceService(b"t" * 32, required=True),
    )
    monkeypatch.setattr(gateway, "_gateway", service)
    monkeypatch.setattr(watermarks, "RECENT_WATERMARK_SESSIONS", {})
    return store, service


def test_real_watermark_rounds_require_owner_credentials_and_demo_is_explicit(
    transport_api, protected_store
):
    from cogniguard.api.services import watermarks

    store, gateway = protected_store
    owner, other = store.get_or_create(), store.get_or_create()
    receipt = gateway.provenance.bind("OWNER_FINAL", answer_id="owner-answer")
    watermarks.register_watermark_session(
        {
            "session_id": owner.session_id,
            "text_watermark": receipt,
            "protection": {
                "watermark_verification": gateway.provenance.verify(receipt["text"], receipt)
            },
        }
    )
    path = "/api/watermark/rounds?session_id=" + owner.session_id
    assert exchange(transport_api, path, method="GET")[0] == 401
    assert (
        exchange(
            transport_api, path, method="GET", headers={"Authorization": "Bearer " + other.token}
        )[0]
        == 403
    )
    valid = exchange(
        transport_api, path, method="GET", headers={"Authorization": "Bearer " + owner.token}
    )
    assert valid[0] == 200
    assert "OWNER_FINAL" in valid[2]
    assert json.loads(valid[2])["data_source"] == "final-delivery"
    demo = exchange(transport_api, "/api/watermark/rounds?scope=demo", method="GET")
    assert demo[0] == 200
    assert json.loads(demo[2])["data_source"] == "demo-derived"
    assert "OWNER_FINAL" not in demo[2]
    payload = {"session_id": owner.session_id, "text": receipt["text"]}
    assert exchange(transport_api, "/api/watermark/detect", body=payload)[0] == 401
    assert (
        exchange(
            transport_api,
            "/api/watermark/detect",
            body=payload,
            headers={"Authorization": "Bearer " + other.token},
        )[0]
        == 403
    )
    detected = exchange(
        transport_api,
        "/api/watermark/detect",
        body=payload,
        headers={"Authorization": "Bearer " + owner.token},
    )
    assert detected[0] == 200
    assert json.loads(detected[2])["watermark_verified"] is True


def test_image_and_artifact_downloads_require_the_generated_owner_allowlist(
    transport_api, protected_store, monkeypatch, tmp_path
):
    store, _ = protected_store
    owner, other = store.get_or_create(), store.get_or_create()
    output = tmp_path / "outputs"
    monkeypatch.setattr(watermark_routes, "OUTPUTS_DIR", output)
    artifact = output / "generated.png"
    artifact_url = "/api/watermark/artifact?" + urllib.parse.urlencode({"path": str(artifact)})
    image_url = "/api/teaching-images/owner.png"
    owner.save_state({"authorized_artifact_urls": [artifact_url, image_url]})
    monkeypatch.setattr(
        watermark_routes, "image_file_response", lambda filename: (b"IMAGE", "image/png")
    )
    monkeypatch.setattr(
        watermark_routes, "watermark_artifact_response", lambda path: (b"ARTIFACT", "image/png")
    )
    for path in (artifact_url, image_url):
        assert exchange(transport_api, path, method="GET")[0] == 401
        assert (
            exchange(
                transport_api,
                path,
                method="GET",
                headers={"Authorization": "Bearer " + other.token},
            )[0]
            == 403
        )
        assert (
            exchange(
                transport_api,
                path,
                method="GET",
                headers={"Authorization": "Bearer " + owner.token},
            )[0]
            == 200
        )
    assert (
        exchange(
            transport_api,
            "/api/teaching-images/never-generated.png",
            method="GET",
            headers={"Authorization": "Bearer " + owner.token},
        )[0]
        == 403
    )


def test_image_attack_is_budgeted_idempotent_and_registers_only_its_actual_outputs(
    transport_api, protected_store, monkeypatch, tmp_path
):
    store, _ = protected_store
    output = tmp_path / "outputs"
    monkeypatch.setattr(watermark_routes, "OUTPUTS_DIR", output)
    monkeypatch.setattr(
        watermark_routes, "decode_data_url_or_base64", lambda value: b"uploaded-image"
    )
    calls = []

    def attack(data, **kwargs):
        calls.append(kwargs)
        output.mkdir(exist_ok=True)
        source = output / "actual.png"
        source.write_bytes(b"ACTUAL_IMAGE_BYTES")
        return {
            "success": True,
            "source_image_path": str(source),
            "source_image_url": "/api/teaching-images/forged.png",
            "mask_path": str(tmp_path / "outside.png"),
            "mask_url": "https://untrusted.invalid/forged",
        }

    monkeypatch.setattr(watermark_routes, "attack_image_watermark", attack)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    payload = {"image_data": "test", "attack_type": "inpainting", "prompt": "Change the color"}
    first = exchange(
        transport_api,
        "/api/watermark/image-attack",
        body=payload,
        headers={"Idempotency-Key": "attack-1"},
        opener=opener,
    )
    assert first[0] == 200
    body = json.loads(first[2])
    assert body["source_image_url"].startswith("/api/watermark/artifact?")
    assert "/forged.png" not in first[2]
    assert "mask_path" not in body and "mask_url" not in body
    assert Path(body["source_image_path"]).read_bytes() == b"ACTUAL_IMAGE_BYTES"
    second = exchange(
        transport_api,
        "/api/watermark/image-attack",
        body=payload,
        headers={"Idempotency-Key": "attack-1"},
        opener=opener,
    )
    assert second[0] == 200
    assert len(calls) == 1
    assert (
        exchange(
            transport_api,
            "/api/watermark/image-attack",
            body=payload,
            headers={"Idempotency-Key": "attack-2"},
            opener=opener,
        )[0]
        == 429
    )
    cookie = SimpleCookie()
    cookie.load(first[1]["Set-Cookie"])
    session = store.get_or_create(cookie["cgc_session"].value)
    assert session.load_state()["authorized_artifact_urls"] == [body["source_image_url"]]
    assert session.budget_snapshot()["images"]["used"] == 1


def test_case_history_does_not_invent_missing_measurements(monkeypatch):
    from cogniguard.api.services import case_execution

    monkeypatch.setattr(
        case_execution.dependencies, "run_demo", lambda **kwargs: {"round_id": "offline"}
    )
    monkeypatch.setattr(
        case_execution.dependencies, "get_runtime_status", lambda: {"runtime_mode": "mock"}
    )
    records = []
    monkeypatch.setattr(case_execution, "append_log", records.append)
    case_execution.execute_case(0, runtime_mode="mock")
    assert records[0]["disclosure_score"] is None
    assert records[0]["copyright_leakage_rate"] is None
    assert records[0]["privacy_budget_used"] is None
    assert records[0]["watermark_bound"] is False


def test_history_metrics_ignore_unknown_samples_without_replacing_them_with_scores(
    monkeypatch, tmp_path
):
    from cogniguard.api.services import history

    monkeypatch.setattr(history, "OUTPUTS_DIR", tmp_path)
    history.append_log({"type": "normal", "disclosure_score": None, "copyright_leakage_rate": None})
    metrics = history.build_history_metrics()
    assert metrics["privacy_leakage_rate"] is None
    assert metrics["copyright_leakage_rate"] is None
    assert metrics["privacy_metric_observations"] == 0
    history.append_log({"type": "normal", "disclosure_score": 0.4, "copyright_leakage_rate": 0.1})
    metrics = history.build_history_metrics()
    assert metrics["privacy_leakage_rate"] == 0.4
    assert metrics["copyright_leakage_rate"] == 0.1
    assert metrics["privacy_metric_observations"] == 1


def test_final_delivery_cache_is_restored_and_reverified_from_server_state(
    transport_api, protected_store, monkeypatch
):
    from cogniguard.api.services import watermarks
    from cogniguard.protection.text_provenance import TextProvenanceService

    store, gateway = protected_store
    owner = store.get_or_create()
    result = gateway.run(
        "free_chat",
        {"message": "Hello"},
        lambda frame: {"success": True, "answer": "PERSISTED_SAFE_ANSWER"},
        session_token=owner.token,
        request_id="persisted-request",
    )
    assert owner.load_state()["final_deliveries"]
    watermarks.RECENT_WATERMARK_SESSIONS.clear()
    # A new verifier with the same durable signing key simulates process restart.
    monkeypatch.setattr(gateway, "provenance", TextProvenanceService(b"t" * 32, required=True))
    credentials = {"Authorization": "Bearer " + owner.token}
    restored = exchange(transport_api, "/api/watermark/rounds", method="GET", headers=credentials)
    assert restored[0] == 200
    row = json.loads(restored[2])["rounds"][0]
    assert row["watermark_verified"] is True
    assert row["post_watermark_text"] == result["text_watermark"]["text"]
    detected = exchange(
        transport_api,
        "/api/watermark/detect",
        headers=credentials,
        body={"text": row["post_watermark_text"]},
    )
    assert json.loads(detected[2])["watermark_verified"] is True
    # Corrupted durable receipts are not shown using a historical True default.
    with owner.transaction() as state:
        state["final_deliveries"][0]["text_watermark"]["text"] += "TAMPERED"
    invalid = exchange(transport_api, "/api/watermark/rounds", method="GET", headers=credentials)
    assert json.loads(invalid[2])["rounds"] == []
    assert "TAMPERED" not in invalid[2]
