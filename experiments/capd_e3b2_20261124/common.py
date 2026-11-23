"""Shared paths, model endpoints, and a cached, rate-limited chat client.

Keys come from ../.env (git-ignored) and are never printed or written. Every
call is cached in $COGNIGUARD_DATA_DIR/e3b2/calls/<model>.jsonl, keyed by a hash
of the request and the sample index, so a rerun never pays twice.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def data_root() -> Path:
    root = os.environ.get("COGNIGUARD_DATA_DIR")
    return Path(root) if root else REPO.parent / "cogniguard_data"


def out_dir() -> Path:
    path = data_root() / "e3b2"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


MODELS = {
    # name: (base_url, env key, extra body that switches thinking off)
    "deepseek-flash": ("https://api.deepseek.com", "DEEPSEEK_API_KEY",
                       {"thinking": {"type": "disabled"}}),
    "qwen3.7-plus": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "ALIGENIE_API_KEY",
                     {"enable_thinking": False}),
    "qwen3.7-flash": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "ALIGENIE_API_KEY",
                      {"enable_thinking": False}),
    "glm-5.3": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "ALIGENIE_API_KEY",
                {"enable_thinking": False}),
    "kimi-k3": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "ALIGENIE_API_KEY",
                {"enable_thinking": False}),
}


def _env() -> dict:
    values = {}
    path = REPO.parent / ".env"
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


class Client:
    """At most `workers` requests in flight per model; exponential backoff, 5 retries."""

    def __init__(self, model: str, workers: int = 8, retry_error: str | None = None) -> None:
        self.model = model
        self.base, key_name, self.extra = MODELS[model]
        self._key = _env()[key_name]
        self.workers = workers
        self.cache_path = out_dir() / "calls" / f"{model}.jsonl"
        self.cache_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.cache = {}
        if self.cache_path.exists():
            for line in self.cache_path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                if retry_error and not row["ok"] and retry_error in (row.get("error") or ""):
                    continue  # an outage, not a model failure: call again (DEVIATIONS.md)
                self.cache[row["key"]] = row
        self._write = threading.Lock()

    def key(self, messages, temperature, sample) -> str:
        blob = json.dumps([self.model, messages, temperature, sample, self.extra], ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()

    def call(self, messages, *, temperature: float, sample: int = 0, max_tokens: int = 400) -> dict:
        key = self.key(messages, temperature, sample)
        if key in self.cache:
            return self.cache[key]
        body = {"model": self.model, "messages": messages, "max_tokens": max_tokens, **self.extra}
        if temperature is not None:  # None: the platform's fixed default (kimi-k3)
            body["temperature"] = temperature
        row = {"key": key, "model": self.model, "ok": False, "content": None,
               "reasoning_chars": 0, "usage": {}, "error": None, "time": time.time()}
        for attempt in range(6):
            try:
                request = urllib.request.Request(
                    self.base.rstrip("/") + "/chat/completions",
                    data=json.dumps(body).encode(),
                    headers={"Authorization": "Bearer " + self._key,
                             "Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=120) as response:
                    payload = json.load(response)
                message = payload["choices"][0]["message"]
                row.update(ok=True, content=message.get("content"),
                           reasoning_chars=len(message.get("reasoning_content") or ""),
                           usage=payload.get("usage") or {}, error=None,
                           served_model=payload.get("model"))
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")[:160]
                row["error"] = f"HTTP {exc.code}: {detail}"
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 5:
                    break
            except Exception as exc:  # network errors, timeouts, malformed bodies
                row["error"] = type(exc).__name__
                if attempt == 5:
                    break
            time.sleep(min(60, 2 ** attempt + random.random()))
        with self._write:
            self.cache[key] = row
            with self.cache_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def map(self, jobs):
        """jobs: list of dicts with messages, temperature, sample, max_tokens."""
        with ThreadPoolExecutor(self.workers) as pool:
            return list(pool.map(lambda job: self.call(**job), jobs))


def usage_tokens(rows) -> tuple[int, int]:
    prompt = sum(int((r.get("usage") or {}).get("prompt_tokens") or 0) for r in rows)
    completion = sum(int((r.get("usage") or {}).get("completion_tokens") or 0) for r in rows)
    return prompt, completion


def write_jsonl(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
