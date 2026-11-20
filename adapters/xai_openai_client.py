"""
xAI Grok OpenAI-compatible client for EvoMemBench-style callers.

Intent (user override): run reproduction with Grok instead of DeepSeek-V3.2
when Volcengine/DeepSeek quota is unavailable.

Drop-in shape mirrors common Ark/OpenAI chat.completions usage:
  client.chat.completions.create(...)
Optional batch-like helper batches sequential calls (xAI has no Ark batch API).

Env:
  XAI_API_KEY   required
  XAI_BASE_URL  default https://api.x.ai/v1
  XAI_MODEL     default grok-2-latest (override to the exact id you are billed for)

Do not commit real keys. Load from .env outside git.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence


DEFAULT_BASE_URL = "https://api.x.ai/v1"
DEFAULT_MODEL = os.environ.get("XAI_MODEL", "grok-2-latest")


class XAIConfigError(RuntimeError):
    pass


def _require_api_key() -> str:
    key = os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY")
    if not key:
        raise XAIConfigError(
            "Missing XAI_API_KEY (or GROK_API_KEY). Put it in local .env only."
        )
    return key


@dataclass
class _Message:
    role: str
    content: str
    tool_calls: Any = None


@dataclass
class _Choice:
    index: int
    message: _Message
    finish_reason: Optional[str] = None


@dataclass
class _Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class _Response:
    id: str
    model: str
    choices: List[_Choice]
    usage: _Usage


class _ChatCompletions:
    def __init__(self, client: "XAIOpenAIClient") -> None:
        self._client = client

    def create(
        self,
        *,
        model: Optional[str] = None,
        messages: Sequence[Dict[str, Any]],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Any = None,
        stop: Any = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:
        if stream:
            raise NotImplementedError("stream=True not used by this adapter")

        # Prefer official openai SDK when installed (EvoMemBench stacks usually have it).
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise XAIConfigError(
                "Package openai is required: pip install openai"
            ) from e

        oai = OpenAI(
            api_key=self._client.api_key,
            base_url=self._client.base_url,
        )
        payload: Dict[str, Any] = {
            "model": model or self._client.model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if stop is not None:
            payload["stop"] = stop
        # Pass through unknown kwargs (top_p, etc.) unchanged — DEVIATIONS: params not retuned.
        for k, v in kwargs.items():
            if k not in payload and v is not None:
                payload[k] = v

        return oai.chat.completions.create(**payload)


class _BatchChatCompletions:
    """Sequential stand-in for Ark client.batch.chat.completions.create."""

    def __init__(self, chat: _ChatCompletions) -> None:
        self._chat = chat

    def create(self, **kwargs: Any) -> Any:
        # Ark batch API accepts bulk jobs; xAI path runs one create at a time.
        return self._chat.create(**kwargs)


class _BatchNamespace:
    def __init__(self, chat: _ChatCompletions) -> None:
        self.chat = type("BatchChat", (), {"completions": _BatchChatCompletions(chat)})()


class _ChatNamespace:
    def __init__(self, client: "XAIOpenAIClient") -> None:
        self.completions = _ChatCompletions(client)


class XAIOpenAIClient:
    """OpenAI-compatible client pointing at xAI."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or _require_api_key()
        self.base_url = (base_url or os.environ.get("XAI_BASE_URL") or DEFAULT_BASE_URL).rstrip(
            "/"
        )
        self.model = model or DEFAULT_MODEL
        self.chat = _ChatNamespace(self)
        self.batch = _BatchNamespace(self.chat.completions)


class ArkBatchClientShim(XAIOpenAIClient):
    """
    Name-compatible shim for code that does:
        client = ArkBatchClient(...)
        client.batch.chat.completions.create(...)
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Ignore Ark-specific endpoint ids; model comes from XAI_MODEL.
        kwargs.pop("batch_model", None)
        kwargs.pop("BATCH_MODEL", None)
        super().__init__(*args, **kwargs)


def smoke_ping(prompt: str = "Reply with exactly: PONG") -> str:
    """Minimal live check; costs a few tokens."""
    client = XAIOpenAIClient()
    resp = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=16,
    )
    return resp.choices[0].message.content or ""


def retrying_create(client: XAIOpenAIClient, retries: int = 5, **kwargs: Any) -> Any:
    last: Optional[Exception] = None
    for i in range(retries):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:  # noqa: BLE001 — surface vendor transient errors
            last = e
            time.sleep(min(2**i, 20))
    assert last is not None
    raise last


if __name__ == "__main__":
    print("model=", DEFAULT_MODEL)
    print("base_url=", os.environ.get("XAI_BASE_URL", DEFAULT_BASE_URL))
    if not (os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY")):
        print("XAI_API_KEY not set — adapter loaded, live ping skipped")
    else:
        print(smoke_ping())
