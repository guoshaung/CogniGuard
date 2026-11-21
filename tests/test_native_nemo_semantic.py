"""Real NeMo self-check rails against a local fake service; no model is invoked."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from cogniguard.integrations.nemo.native import NativeNeMoUnavailable, configured_semantic_guard


@pytest.fixture
def fake_safety_service(monkeypatch):
    pytest.importorskip("nemoguardrails")
    state = {"verdict": "NO", "requests": [], "status": 200, "reject_on": None}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(
                {"body": body, "authorization": self.headers.get("Authorization")}
            )
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if state["status"] != 200:
                self.wfile.write(b'{"error":"fixture unavailable"}')
                return
            verdict = state["verdict"]
            if state["reject_on"] and state["reject_on"] in json.dumps(body, ensure_ascii=False):
                verdict = "YES"
            if verdict in {"YES", "NO"}:
                key = "Response Safety" if "Response Safety" in str(body) else "User Safety"
                verdict = json.dumps({key: "unsafe" if verdict == "YES" else "safe"})
            self.wfile.write(
                json.dumps(
                    {
                        "id": "test",
                        "object": "chat.completion",
                        "created": 0,
                        "model": body["model"],
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": verdict},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    }
                ).encode()
            )

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("COGNIGUARD_NEMO_SEMANTIC", "on")
    monkeypatch.setenv("COGNIGUARD_NEMO_SEMANTIC_URL", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setenv("COGNIGUARD_NEMO_SEMANTIC_MODEL", "test-local-fixture")
    monkeypatch.setenv("COGNIGUARD_LOCAL_MODEL_KEY", "fixture-only")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-sent")
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_nemo_semantic_input_and_output_call_local_model(fake_safety_service):
    guard = configured_semantic_guard()
    try:
        assert guard.check_input("Explain a physical principle.")
        assert len(fake_safety_service["requests"]) == 2
        assert guard.check_output("An educational response.")
        assert len(fake_safety_service["requests"]) == 3
        assert all(
            r["body"]["model"] == "test-local-fixture" for r in fake_safety_service["requests"]
        )
        assert all("must-not-be-sent" not in str(r) for r in fake_safety_service["requests"])
        fake_safety_service["verdict"] = "YES"
        assert not guard.check_input("Potentially harmful instruction.")
        assert not guard.check_output("Potentially harmful response.")
        fake_safety_service["verdict"] = "uncertain"
        assert not guard.check_input("Ambiguous model verdict.")
        fake_safety_service["verdict"] = '{"User Safety":"safe unsafe"}'
        assert not guard.check_input("Contradictory model verdict.")
    finally:
        guard.close()


def test_semantic_remote_endpoint_is_rejected(monkeypatch):
    monkeypatch.setenv("COGNIGUARD_NEMO_SEMANTIC", "on")
    monkeypatch.setenv("COGNIGUARD_NEMO_SEMANTIC_URL", "https://example.com/v1")
    monkeypatch.setenv("COGNIGUARD_NEMO_SEMANTIC_MODEL", "fixture")
    with pytest.raises(NativeNeMoUnavailable):
        configured_semantic_guard()


def test_local_endpoint_cannot_be_sent_through_proxy(monkeypatch):
    import cogniguard.integrations.nemo.native as native

    monkeypatch.setenv("COGNIGUARD_NEMO_SEMANTIC", "on")
    monkeypatch.setenv("COGNIGUARD_NEMO_SEMANTIC_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("COGNIGUARD_NEMO_SEMANTIC_MODEL", "fixture")
    monkeypatch.setattr(native, "getproxies", lambda: {"http": "http://proxy.invalid"})
    monkeypatch.setattr(native, "proxy_bypass", lambda _host: False)
    with pytest.raises(NativeNeMoUnavailable, match="bypass"):
        configured_semantic_guard()


def test_semantic_service_error_fails_closed(fake_safety_service):
    guard = configured_semantic_guard()
    fake_safety_service["status"] = 503
    try:
        try:
            allowed = guard.check_input("Check this request.")
        except NativeNeMoUnavailable:
            allowed = False
        assert not allowed
    finally:
        guard.close()


def test_real_gateway_calls_nemo_semantic_before_execution_and_delivery(
    fake_safety_service, tmp_path
):
    from cogniguard.integrations.nemo.native import NativeNeMoGuard
    from cogniguard.protection.text_provenance import TextProvenanceService
    from cogniguard.runtime.gateway import ProtectionGateway
    from cogniguard.runtime.protection_context import transport_scope
    from cogniguard.runtime.sessions import SessionStore

    base = NativeNeMoGuard()
    semantic = configured_semantic_guard()
    gateway = ProtectionGateway(
        store=SessionStore(tmp_path / "session.sqlite3"),
        provenance=TextProvenanceService(b"fixture-key" * 4, required=True),
        native_guard=base,
        semantic_guard=semantic,
    )
    try:
        with transport_scope(None, None, lambda token: None):
            first = gateway.run(
                "test",
                {"message": "A normal question"},
                lambda frame: {"answer": "A normal answer."},
                request_id="safe",
            )
            assert first["protection"]["watermark_verification"]["valid"]
            assert {e["stage"] for e in first["protection"]["evidence"]} >= {
                "nemo_semantic_input",
                "nemo_semantic_output",
            }
            fake_safety_service["reject_on"] = "INPUT_ATTACK_MARKER"
            blocked = gateway.run(
                "test",
                {"message": "INPUT_ATTACK_MARKER"},
                lambda frame: pytest.fail("blocked semantic input reached operation"),
                request_id="blocked-input",
            )
            assert blocked["input_blocked"]
            assert "nemo_semantic_backend" not in json.dumps(
                fake_safety_service["requests"][-1]["body"]
            )
            replay = gateway.run(
                "test",
                {"message": "INPUT_ATTACK_MARKER"},
                lambda frame: pytest.fail("cached refusal reached operation"),
                session_token=blocked["session_token"],
                request_id="blocked-input",
            )
            assert replay == blocked
            fake_safety_service["reject_on"] = "OUTPUT_ATTACK_MARKER"
            blocked_output = gateway.run(
                "test",
                {"message": "An ordinary question"},
                lambda frame: {"answer": "OUTPUT_ATTACK_MARKER"},
                request_id="blocked-output",
            )
            assert blocked_output["semantic_output_blocked"]
            assert "OUTPUT_ATTACK_MARKER" not in json.dumps(blocked_output)
            assert blocked_output["protection"]["watermark_verification"]["valid"]
            spoofed = gateway.run(
                "test",
                {"message": "An ordinary question"},
                lambda frame: {"answer": "OUTPUT_ATTACK_MARKER", "input_blocked": True},
                request_id="spoofed-block",
            )
            assert spoofed["semantic_output_blocked"]
    finally:
        semantic.close()
        base.close()
