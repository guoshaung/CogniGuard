"""Synthetic-only browser flow using the real HTTP and teaching boundaries."""
import json
import threading
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from http.server import ThreadingHTTPServer

import pytest

from cogniguard.api.http_server import CogniGuardDashboardAPIHandler
from cogniguard.protection.text_provenance import TextProvenanceService
from cogniguard.runtime.gateway import ProtectionGateway
from cogniguard.runtime.sessions import SessionStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    gateway = ProtectionGateway(
        store=SessionStore(tmp_path / "sessions.sqlite"),
        provenance=TextProvenanceService(b"synthetic-test-key" * 4, required=True),
    )
    monkeypatch.setattr("cogniguard.runtime.gateway.get_gateway", lambda: gateway)
    monkeypatch.setenv("COGNIGUARD_PROFILE_CONSENT_DEMO", "on")
    server = ThreadingHTTPServer(("127.0.0.1", 0), CogniGuardDashboardAPIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def post(path, data, headers=None):
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}{path}", data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json", **(headers or {})}, method="POST",
        )
        try:
            response = opener.open(request, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    try:
        yield post
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_full_synthetic_http_approve_then_revoke(client):
    status, initial = client("/api/consent-demo/turn", {"message": "解一元一次方程"})
    assert status == 200
    assert "visual_support" not in initial["context_card"]
    request_id = initial["profile_consent_requests"][0]["request_id"]
    assert "session_token" not in initial
    status, _ = client("/api/consent-demo/decision", {"action": "approve", "request_id": request_id})
    assert status == 200
    status, approved = client("/api/consent-demo/turn", {"message": "继续解释方程"})
    assert status == 200 and "visual_support" in approved["context_card"]
    assert client("/api/consent-demo/decision", {"action": "revoke"})[0] == 200
    status, revoked = client("/api/consent-demo/turn", {"message": "再解释一次方程"})
    assert status == 200 and "visual_support" not in revoked["context_card"]


def test_disabled_or_untrusted_origin_cannot_use_demo(client, monkeypatch):
    monkeypatch.setenv("COGNIGUARD_PROFILE_CONSENT_DEMO", "off")
    assert client("/api/consent-demo/turn", {"message": "hi"})[0] == 403
    monkeypatch.setenv("COGNIGUARD_PROFILE_CONSENT_DEMO", "on")
    assert client("/api/consent-demo/turn", {"message": "hi"}, {"Origin": "https://evil.example"})[0] == 403
    assert client("/api/consent-demo/turn", {"message": "hi", "student_id": "real"})[0] == 400
