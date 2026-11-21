"""Test-only synthetic identity session; this is not production authentication."""
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
        provenance=TextProvenanceService(b"synthetic-demo-test" * 4, required=True),
    )
    monkeypatch.setattr("cogniguard.runtime.gateway.get_gateway", lambda: gateway)
    monkeypatch.setenv("COGNIGUARD_PROFILE_CONSENT_DEMO", "on")
    server = ThreadingHTTPServer(("127.0.0.1", 0), CogniGuardDashboardAPIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def request(path, body=None, headers=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        try:
            response = opener.open(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, json.loads(response.read())

    try:
        yield request
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_synthetic_login_session_and_logout(client):
    assert not client('/api/demo-identity/status')[2]['signed_in']
    assert client('/api/demo-identity/login', {'account': 'student-demo', 'password': 'wrong'})[0] == 403
    status, headers, response = client('/api/demo-identity/login',
                                       {'account': 'student-demo', 'password': 'demo-only-2026'})
    assert status == 200 and response['simulation']
    assert 'HttpOnly' in headers['Set-Cookie'] and 'SameSite=Strict' in headers['Set-Cookie']
    assert 'demo-only-2026' not in json.dumps(response)
    assert client('/api/demo-identity/status')[2]['identity']['display_name'] == '模拟学生 001'
    assert client('/api/demo-identity/logout', {})[0] == 200
    assert not client('/api/demo-identity/status')[2]['signed_in']


def test_login_demo_is_disabled_by_default_and_rejects_remote_origin(client, monkeypatch):
    monkeypatch.setenv('COGNIGUARD_PROFILE_CONSENT_DEMO', 'off')
    assert client('/api/demo-identity/status')[0] == 403
    monkeypatch.setenv('COGNIGUARD_PROFILE_CONSENT_DEMO', 'on')
    assert client('/api/demo-identity/status', headers={'Origin': 'https://other.example'})[0] == 403
