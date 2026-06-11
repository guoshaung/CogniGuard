from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


DEFAULT_MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
DEFAULT_MIMO_MODEL = "mimo-v2.5-pro"
DEFAULT_STUDENT_MIMO_MODEL = "mimo-v2-flash"


class MiMoClientError(RuntimeError):
    """Raised when Xiaomi MiMo returns an unusable response."""


@dataclass(slots=True)
class MiMoChatClient:
    """Minimal OpenAI-compatible Xiaomi MiMo chat client.

    The API key is intentionally provided at runtime and should come from an
    environment variable or secret manager, never from committed source code.
    """

    api_key: str
    base_url: str = DEFAULT_MIMO_BASE_URL
    model: str = DEFAULT_MIMO_MODEL
    timeout_seconds: float = 60.0
    temperature: float = 0.2
    max_tokens: int = 700

    def __post_init__(self) -> None:
        self.base_url = normalize_mimo_base_url(self.base_url)

    def chat(
        self,
        system_prompt: str,
        payload: dict[str, Any],
        on_text_delta: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        user_content = (
            "Return one valid JSON object only. Do not include markdown fences.\n"
            f"Payload:\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
        )
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": self.temperature,
            "max_completion_tokens": self.max_tokens,
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
        }
        content = self._post_chat_completions(body, on_text_delta=on_text_delta)
        parsed = _parse_json_content(content)
        if parsed is None:
            raise MiMoClientError("Xiaomi MiMo response did not contain valid JSON.")
        return parsed

    def _post_chat_completions(
        self,
        body: dict[str, Any],
        on_text_delta: Callable[[str], None] | None = None,
    ) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        request_body = dict(body)
        if on_text_delta is not None:
            request_body["stream"] = True
        data = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url=url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                if on_text_delta is not None:
                    return _read_streamed_chat_response(response, on_text_delta)
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MiMoClientError(
                f"Xiaomi MiMo HTTP {exc.code}: {_trim_secret_detail(detail)}"
            ) from exc
        except urllib.error.URLError as exc:
            raise MiMoClientError(
                f"Xiaomi MiMo connection error: {exc.reason}"
            ) from exc

        parsed = json.loads(response_body)
        try:
            return parsed["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise MiMoClientError(
                "Unexpected Xiaomi MiMo chat response schema."
            ) from exc


def _read_streamed_chat_response(
    response: Any,
    on_text_delta: Callable[[str], None],
) -> str:
    chunks: list[str] = []
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line or not line.startswith("data:"):
            continue

        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            break

        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue

        choices = event.get("choices") or []
        if not choices:
            continue

        delta = choices[0].get("delta") or {}
        text = delta.get("content") or delta.get("reasoning_content") or ""
        if not text:
            continue

        chunks.append(text)
        try:
            on_text_delta(text)
        except Exception:
            pass

    return "".join(chunks)


def build_default_llm_client(
    env_file: str | os.PathLike[str] | None = None,
    *,
    model_env_var: str = "MIMO_MODEL",
    default_model: str = DEFAULT_MIMO_MODEL,
    max_tokens_env_var: str = "MIMO_MAX_TOKENS",
    default_max_tokens: int = 700,
) -> MiMoChatClient | None:
    _load_env_file(env_file)
    api_key = os.environ.get("MIMO_API_KEY", "").strip()
    if not api_key:
        return None

    base_url = os.environ.get("MIMO_BASE_URL", DEFAULT_MIMO_BASE_URL).strip()
    model = os.environ.get(model_env_var, default_model).strip()
    timeout = _safe_float(os.environ.get("MIMO_TIMEOUT_SECONDS"), 60.0)
    temperature = _safe_float(os.environ.get("MIMO_TEMPERATURE"), 0.2)
    max_tokens = _safe_int(
        os.environ.get(max_tokens_env_var),
        default_max_tokens,
    )

    return MiMoChatClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def build_student_llm_client(
    env_file: str | os.PathLike[str] | None = None,
) -> MiMoChatClient | None:
    return build_default_llm_client(
        env_file=env_file,
        model_env_var="MIMO_STUDENT_MODEL",
        default_model=DEFAULT_STUDENT_MIMO_MODEL,
        max_tokens_env_var="MIMO_STUDENT_MAX_TOKENS",
        default_max_tokens=420,
    )


def normalize_mimo_base_url(raw_url: str) -> str:
    url = (raw_url or DEFAULT_MIMO_BASE_URL).strip().rstrip("/")
    if url == "https://api.xiaomimimo.com":
        return DEFAULT_MIMO_BASE_URL
    return url


def _load_env_file(env_file: str | os.PathLike[str] | None) -> None:
    path = Path(env_file) if env_file is not None else _find_local_env_file()
    if path is None or not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _find_local_env_file() -> Path | None:
    cwd = Path.cwd().resolve()
    candidates = [cwd, *cwd.parents]
    for directory in candidates:
        path = directory / ".env"
        if path.exists():
            return path
    return None


def _parse_json_content(content: str) -> dict[str, Any] | None:
    text = (content or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _trim_secret_detail(detail: str) -> str:
    text = " ".join((detail or "").split())
    if len(text) <= 500:
        return text
    return f"{text[:497]}..."


def _safe_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default


def _safe_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default
