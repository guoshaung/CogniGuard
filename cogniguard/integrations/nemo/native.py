"""Optional, fail-closed NeMo input/output checks at the application boundary.

The domain protections remain independent owners of authorization and release.
NeMo is imported only when this explicitly configured integration is constructed.
"""

from __future__ import annotations

import asyncio
import atexit
import os
from pathlib import Path
from threading import RLock, Thread
from urllib.parse import urlsplit
from urllib.request import getproxies, proxy_bypass

from core.paths import PROJECT_ROOT


class NativeNeMoUnavailable(RuntimeError):
    """The explicitly required native guardrail could not be executed."""


class NativeNeMoGuard:
    """Run configured NeMo checks without passing policy or secrets to a remote model."""

    def __init__(
        self,
        config_path: str | Path | None = None,
        *,
        config_content: str | None = None,
        timeout_seconds: float = 30,
    ):
        path = Path(config_path or PROJECT_ROOT / "configs" / "nemo" / "base")
        try:
            from nemoguardrails import Guardrails, RailsConfig

            config = (
                RailsConfig.from_content(yaml_content=config_content)
                if config_content is not None
                else RailsConfig.from_path(str(path))
            )
            if not config.rails.input.flows or not config.rails.output.flows:
                raise ValueError("Both input and output rails must be configured")
            self._rails = Guardrails(config, require_iorails=True)
        except Exception as exc:
            raise NativeNeMoUnavailable("Native NeMo guardrails could not be initialized") from exc
        self._lock = RLock()
        self._timeout_seconds = timeout_seconds
        self._loop = asyncio.new_event_loop()
        self._thread = Thread(target=self._loop.run_forever, name="cogniguard-nemo", daemon=True)
        self._thread.start()
        self._closed = False
        try:
            asyncio.run_coroutine_threadsafe(self._rails.startup(), self._loop).result(timeout=30)
        except Exception as exc:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5)
            raise NativeNeMoUnavailable("Native NeMo guardrail startup failed") from exc
        atexit.register(self.close)

    def close(self) -> None:
        """Release NeMo clients and the dedicated event loop at service shutdown."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                asyncio.run_coroutine_threadsafe(self._rails.shutdown(), self._loop).result(
                    timeout=10
                )
            finally:
                self._loop.call_soon_threadsafe(self._loop.stop)
                self._thread.join(timeout=10)
                if not self._thread.is_alive():
                    self._loop.close()

    def _check(self, text: str, role: str) -> bool:
        try:
            with self._lock:
                if self._closed:
                    raise RuntimeError("Native NeMo guard is closed")
                pending = asyncio.run_coroutine_threadsafe(
                    self._rails.check_async(messages=[{"role": role, "content": text}]),
                    self._loop,
                )
                try:
                    result = pending.result(timeout=self._timeout_seconds)
                except Exception:
                    pending.cancel()
                    raise
            status = getattr(result.status, "value", result.status)
            if status == "passed":
                return True
            if status in {"blocked", "modified"}:
                # Modified content is not silently accepted: domain provenance
                # must be rebound after any transformation.
                return False
            raise ValueError("Unexpected NeMo result status")
        except Exception as exc:
            raise NativeNeMoUnavailable("Native NeMo guardrail check failed") from exc

    def check_input(self, text: str) -> bool:
        return self._check(text, "user")

    def check_output(self, text: str) -> bool:
        return self._check(text, "assistant")


def configured_native_guard() -> NativeNeMoGuard | None:
    """Only trusted process configuration may activate this optional backend."""
    mode = os.environ.get("COGNIGUARD_NEMO_NATIVE", "off").strip().lower()
    if mode == "off":
        return None
    if mode != "on":
        raise NativeNeMoUnavailable("COGNIGUARD_NEMO_NATIVE must be 'on' or 'off'")
    return NativeNeMoGuard(os.environ.get("COGNIGUARD_NEMO_BASE_CONFIG") or None)


def configured_semantic_guard() -> NativeNeMoGuard | None:
    """Enable local-only NeMo self-checks when explicitly requested by the server."""
    mode = os.environ.get("COGNIGUARD_NEMO_SEMANTIC", "off").strip().lower()
    if mode == "off":
        return None
    if mode != "on":
        raise NativeNeMoUnavailable("COGNIGUARD_NEMO_SEMANTIC must be 'on' or 'off'")
    endpoint = os.environ.get("COGNIGUARD_NEMO_SEMANTIC_URL", "http://127.0.0.1:11434/v1")
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path != "/v1"
    ):
        raise NativeNeMoUnavailable("Semantic guard requires an HTTP 127.0.0.1 /v1 endpoint")
    proxies = getproxies()
    if any(proxies.get(key) for key in ("http", "all")) and not proxy_bypass("127.0.0.1"):
        raise NativeNeMoUnavailable("Local semantic endpoint must bypass configured proxies")
    model = os.environ.get("COGNIGUARD_NEMO_SEMANTIC_MODEL", "").strip()
    if not model:
        raise NativeNeMoUnavailable("COGNIGUARD_NEMO_SEMANTIC_MODEL must identify a local model")
    try:
        import yaml

        path = PROJECT_ROOT / "configs" / "nemo" / "semantic" / "config.yml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["models"][0]["parameters"]["base_url"] = endpoint
        data["models"][0]["model"] = model
        os.environ.setdefault("COGNIGUARD_LOCAL_MODEL_KEY", "local-only")
        return NativeNeMoGuard(
            config_content=yaml.safe_dump(data, allow_unicode=True), timeout_seconds=130
        )
    except NativeNeMoUnavailable:
        raise
    except Exception as exc:
        raise NativeNeMoUnavailable("Local semantic guard configuration failed") from exc
