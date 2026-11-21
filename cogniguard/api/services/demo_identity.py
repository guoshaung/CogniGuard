"""Local synthetic identity exercise. Never use for actual accounts."""
from __future__ import annotations

import hmac
import time

from cogniguard.runtime.sessions import InvalidSessionToken

_ACCOUNT = "student-demo"
_PASSWORD = "demo-only-2026"
_SUBJECT = "synthetic-student-001"
_TTL_SECONDS = 3600


def login(account, password):
    from cogniguard.runtime.gateway import get_gateway

    if not isinstance(account, str) or not isinstance(password, str):
        raise ValueError("Account and password must be strings")
    if len(account) > 128 or len(password) > 128:
        raise PermissionError("Invalid demonstration credentials")
    if not (hmac.compare_digest(account.encode(), _ACCOUNT.encode())
            and hmac.compare_digest(password.encode(), _PASSWORD.encode())):
        raise PermissionError("Invalid demonstration credentials")
    # Always issue a new opaque session after login; do not upgrade a known token.
    session = get_gateway().store.get_or_create()
    with session.transaction() as state:
        state["synthetic_identity_demo"] = {
            "subject": _SUBJECT, "expires_at": time.time() + _TTL_SECONDS,
        }
    return session.token


def current(token):
    from cogniguard.runtime.gateway import get_gateway

    if not token:
        return None
    try:
        session = get_gateway().store.get_or_create(token)
    except InvalidSessionToken:
        return None
    identity = session.load_state().get("synthetic_identity_demo")
    if not isinstance(identity, dict) or identity.get("subject") != _SUBJECT:
        return None
    if not isinstance(identity.get("expires_at"), (int, float)) or identity["expires_at"] <= time.time():
        return None
    return {"display_name": "模拟学生 001", "simulation": True}


def logout(token):
    from cogniguard.runtime.gateway import get_gateway

    if not token:
        return
    try:
        session = get_gateway().store.get_or_create(token)
    except InvalidSessionToken:
        return
    with session.transaction() as state:
        state.pop("synthetic_identity_demo", None)
