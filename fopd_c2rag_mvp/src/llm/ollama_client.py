from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class LLMResult:
    text: str
    ok: bool
    error: str = ""


class OllamaClient:
    def __init__(self, config: dict[str, Any]) -> None:
        llm_cfg = config.get("llm", {})
        self.enabled = bool(llm_cfg.get("enabled", False)) and not os.getenv("COGNIGUARD_DISABLE_LLM")
        self.model = str(llm_cfg.get("model", "qwen2.5:7b"))
        self.base_url = str(llm_cfg.get("base_url", "http://127.0.0.1:11434")).rstrip("/")
        self.timeout = float(llm_cfg.get("timeout_seconds", 90))
        self.temperature = float(llm_cfg.get("temperature", 0.2))
        self.num_predict = int(llm_cfg.get("num_predict", 256))

    def is_enabled(self) -> bool:
        return self.enabled

    def generate(self, prompt: str, *, num_predict: int | None = None, temperature: float | None = None) -> LLMResult:
        if not self.enabled:
            return LLMResult(text="", ok=False, error="llm_disabled")
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature if temperature is None else temperature,
                "num_predict": self.num_predict if num_predict is None else num_predict,
            },
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return LLMResult(text=str(data.get("response", "")).strip(), ok=True)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return LLMResult(text="", ok=False, error=str(exc))


def extract_json_object(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}
