"""Windows-only original-answer API adapter. Calling this function is billable opt-in."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from .protocol import digest


class RefuseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError("Do not forward source API credentials to a redirect")


def generate_original(
    base_url: str,
    model: str,
    messages: list[dict],
    api_key: str,
    max_tokens: int = 1600,
    *,
    opener=None,
) -> dict:
    """Exactly one HTTP attempt; never automatically retries or judges quality."""
    parsed = urllib.parse.urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use a credential-free HTTPS API base URL")
    if not api_key or not model or not 1 <= max_tokens <= 1600:
        raise ValueError("Explicit credential, model and bounded token allowance required")
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    wire = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=wire,
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    if opener is None:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), RefuseRedirect())
    start = time.perf_counter()
    with opener.open(request, timeout=240) as response:
        raw = response.read(2 * 1024**2 + 1)
        if len(raw) > 2 * 1024**2:
            raise ValueError("Oversized API response")
        data = json.loads(raw)
    choice = data["choices"][0]
    text = choice["message"]["content"]
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Empty original; no fallback or repeat sampling")
    return {
        "text": text,
        "text_sha256": digest(text.encode()),
        "request": body,
        "request_sha256": digest(wire),
        "requested_model": model,
        "returned_model": data.get("model"),
        "identity_scope": "SERVER_REPORTED_ONLY",
        "usage": data.get("usage"),
        "finish_reason": choice.get("finish_reason"),
        "seconds": time.perf_counter() - start,
        "HTTP_attempts": 1,
        "retries": 0,
        "monetary_cost": None,
        "knowledge_review": "REQUIRED_NOT_AUTOMATIC",
        "authorization_saved": False,
    }
