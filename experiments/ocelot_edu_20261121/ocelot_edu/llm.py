"""API client. Keys stay in the environment or the gitignored RSILab env file."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ENV_CANDIDATES = [
    os.environ.get("OCELOT_ENV_FILE", ""),
    "/Users/MBP/Exp/RSILab/mmfopd-repro/.env",
]


def load_env() -> dict[str, str]:
    env = dict(os.environ)
    for path in ENV_CANDIDATES:
        if path and Path(path).is_file():
            for line in Path(path).read_text().splitlines():
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            break
    return env


def _post_once(url: str, key: str, payload: dict, timeout: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        proc = subprocess.run(
            [
                "curl",
                "-sS",
                "-m",
                str(timeout),
                "-H",
                f"Authorization: Bearer {key}",
                "-H",
                "Content-Type: application/json",
                url,
                "--data-binary",
                "@-",
            ],
            input=data,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"curl failed: {err}")
        return json.loads(proc.stdout.decode("utf-8"))


def _transient(exc: Exception) -> bool:
    msg = str(exc).lower()
    needles = (
        "timed out",
        "timeout",
        "couldn't connect",
        "could not connect",
        "connection",
        "curl: (28)",
        "curl: (35)",
        "curl: (52)",
        "curl: (56)",
        "reset",
        "temporarily",
    )
    return any(needle in msg for needle in needles)


def _post(url: str, key: str, payload: dict, timeout: int = 60) -> dict:
    last: Exception | None = None
    for attempt in range(5):
        try:
            return _post_once(url, key, payload, timeout)
        except Exception as exc:
            last = exc
            if not _transient(exc) or attempt == 4:
                raise
            time.sleep(min(20, 2 ** attempt))
    if last is not None:
        raise last
    raise RuntimeError("request failed")


def chat(base_url: str, key: str, model: str, messages: list[dict], max_tokens: int, extra: dict | None = None) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    if extra:
        payload.update(extra)
    url = base_url.rstrip("/") + "/chat/completions"
    body = _post(url, key, payload)
    if "error" in body:
        raise RuntimeError(json.dumps(body["error"], ensure_ascii=False)[:500])
    choice = body["choices"][0]["message"]
    usage = body.get("usage") or {}
    return {
        "content": choice.get("content") or "",
        "usage": {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
        },
        "model": body.get("model", model),
    }


def chat_compat(base_url: str, key: str, model: str, messages: list[dict], max_tokens: int, extra: dict | None = None) -> dict:
    """Retry once without thinking flags when the endpoint rejects them."""
    try:
        return chat(base_url, key, model, messages, max_tokens, extra)
    except Exception as exc:
        if not extra:
            raise
        msg = str(exc).lower()
        retry = dict(extra)
        changed = False
        for field in ("enable_thinking", "thinking"):
            if field in retry and (
                field.replace("_", "") in msg.replace("_", "")
                or "invalid" in msg
                or "unknown" in msg
                or "unexpected" in msg
                or "extra" in msg
            ):
                retry.pop(field)
                changed = True
        if not changed:
            raise
        return chat(base_url, key, model, messages, max_tokens, retry or None)


def cache_key(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def extract_json(text: str) -> dict:
    raw = text.strip()
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            piece = part.strip()
            if piece.startswith("json"):
                piece = piece[4:].strip()
            if piece.startswith("{"):
                raw = piece
                break
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no json object")
    return json.loads(raw[start : end + 1])
