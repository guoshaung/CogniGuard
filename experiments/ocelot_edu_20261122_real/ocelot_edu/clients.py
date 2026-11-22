"""Local Ollama and DeepSeek. Paid calls are DeepSeek only."""

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
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


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


def extract_json(text: str) -> dict:
    raw = (text or "").strip()
    if "```" in raw:
        for part in raw.split("```"):
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


def ollama_chat(model: str, messages: list[dict], temperature: float, num_predict: int, seed: int, timeout: int = 180) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict, "seed": seed},
        "keep_alive": "2h",
    }
    data = json.dumps(payload).encode("utf-8")
    last: Exception | None = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                OLLAMA_URL.rstrip("/") + "/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            message = body.get("message") or {}
            return {
                "content": message.get("content") or "",
                "eval_count": int(body.get("eval_count") or 0),
                "model": body.get("model", model),
            }
        except Exception as exc:
            last = exc
            if not _transient(exc) or attempt == 2:
                raise
            time.sleep(min(10, 2 ** attempt))
    raise RuntimeError(str(last))


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


def deepseek_chat(base_url: str, key: str, model: str, messages: list[dict], max_tokens: int, temperature: float) -> dict:
    extra = {"thinking": {"type": "disabled"}}
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        **extra,
    }
    url = base_url.rstrip("/") + "/chat/completions"
    last: Exception | None = None
    for attempt in range(5):
        try:
            body = _post_once(url, key, payload, 90)
            if "error" in body and attempt == 0 and "thinking" in json.dumps(body["error"]).lower():
                payload.pop("thinking", None)
                continue
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
        except Exception as exc:
            last = exc
            if not _transient(exc) or attempt == 4:
                raise
            time.sleep(min(20, 2 ** attempt))
    raise RuntimeError(str(last))


def cache_path(cache: Path, payload: dict) -> Path:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return cache / f"{hashlib.sha256(raw).hexdigest()}.json"


def cached_json(cache: Path, payload: dict, producer) -> dict:
    path = cache_path(cache, payload)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    result = producer()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result
