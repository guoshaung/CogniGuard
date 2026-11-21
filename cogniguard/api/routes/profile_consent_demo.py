"""Local opt-in routes for fixed synthetic data only."""
from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlsplit

from ..routing import Route


def _require_demo(handler):
    if os.environ.get("COGNIGUARD_PROFILE_CONSENT_DEMO", "off").strip().lower() != "on":
        raise PermissionError("Synthetic consent demo is disabled")
    try:
        if not ipaddress.ip_address(handler.client_address[0]).is_loopback:
            raise PermissionError("Synthetic consent demo requires loopback")
        origin = handler.headers.get("Origin")
        if origin and urlsplit(origin).hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise PermissionError("Synthetic consent demo requires a local origin")
    except ValueError as exc:
        raise PermissionError("Invalid local client") from exc


def turn(handler, request):
    _require_demo(handler)
    from ..services import profile_consent_demo

    payload = handler._read_json()
    if set(payload) != {"message"}:
        raise ValueError("Only a synthetic teaching message is accepted")
    handler._send_json(profile_consent_demo.turn(payload["message"]))


def decide(handler, request):
    _require_demo(handler)
    from ..services import profile_consent_demo

    payload = handler._read_json()
    if set(payload) - {"action", "request_id"}:
        raise ValueError("Only a demo decision and request ID are accepted")
    handler._send_json(profile_consent_demo.decision(payload))


ROUTES = (
    Route("POST", "/api/consent-demo/turn", turn),
    Route("POST", "/api/consent-demo/decision", decide),
)
