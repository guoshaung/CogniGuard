"""Opt-in, loopback-only synthetic login routes."""
from __future__ import annotations

from http.cookies import CookieError, SimpleCookie

from ..routing import Route
from .profile_consent_demo import _require_demo


def _cookie(handler):
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get("Cookie", ""))
    except CookieError:
        return None
    return cookie["cgc_demo_identity"].value if "cgc_demo_identity" in cookie else None


def login(handler, request):
    _require_demo(handler)
    from ..services import demo_identity

    payload = handler._read_json()
    if set(payload) != {"account", "password"}:
        raise ValueError("Only demonstration account and password are accepted")
    handler._demo_identity_cookie = demo_identity.login(payload["account"], payload["password"])
    handler._send_json({"signed_in": True, "display_name": "模拟学生 001", "simulation": True})


def status(handler, request):
    _require_demo(handler)
    from ..services import demo_identity

    identity = demo_identity.current(_cookie(handler))
    handler._send_json({"signed_in": bool(identity), "identity": identity, "simulation": True})


def logout(handler, request):
    _require_demo(handler)
    from ..services import demo_identity

    payload = handler._read_json()
    if payload:
        raise ValueError("Demonstration logout has no parameters")
    demo_identity.logout(_cookie(handler))
    handler._demo_identity_cookie = ""
    handler._send_json({"signed_in": False, "simulation": True})


ROUTES = (
    Route("POST", "/api/demo-identity/login", login),
    Route("GET", "/api/demo-identity/status", status),
    Route("POST", "/api/demo-identity/logout", logout),
)
