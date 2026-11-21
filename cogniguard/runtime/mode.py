from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cogniguard.protection.cg.nemo_guardrails_adapter import (
    NeMoGuardrailsAdapter,
)

VALID_RUNTIME_MODES = {"mock", "llm", "guarded_llm"}
PLACEHOLDER_KEYS = {"", "your_mimo_api_key_here", "your_openai_api_key_here"}
DEFAULT_GUARDRAILS_CONFIG = (
    Path(__file__).resolve().parents[2] / "protection" / "supporting" / "cg_guardrails"
)
GuardrailAdapter = NeMoGuardrailsAdapter


@dataclass(frozen=True, slots=True)
class RuntimeOptions:
    runtime_mode: str
    guardrails_enabled: bool


_request_runtime: ContextVar[RuntimeOptions | None] = ContextVar(
    "cogniguard_request_runtime", default=None
)


@contextmanager
def runtime_options(runtime_mode: str, guardrails_enabled: bool) -> Iterator[None]:
    """Apply per-request settings without changing the process environment."""
    token = _request_runtime.set(RuntimeOptions(runtime_mode, guardrails_enabled))
    try:
        yield
    finally:
        _request_runtime.reset(token)


@dataclass(frozen=True, slots=True)
class RuntimeStatus:
    runtime_mode: str
    llm_provider: str
    api_key_loaded: bool
    nemo_guardrails_enabled: bool
    fallback_reason: str
    agent_call_mode: str
    guardrail_backend: str
    nemo_runtime_available: bool
    nemo_native_configured: bool
    nemo_semantic_configured: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_runtime_status(env_file: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    _load_env_file(env_file)

    request_options = _request_runtime.get()
    requested_mode = (
        (
            request_options.runtime_mode
            if request_options is not None
            else os.environ.get("COGNIGUARD_RUNTIME_MODE", "")
        )
        .strip()
        .lower()
    )
    api_key_loaded = _has_mimo_key()
    guardrails_requested = requested_mode == "guarded_llm" or (
        request_options.guardrails_enabled
        if request_options is not None
        else _truthy(os.environ.get("COGNIGUARD_NEMO_GUARDRAILS_ENABLED"))
    )

    fallback_reason = ""
    if requested_mode and requested_mode not in VALID_RUNTIME_MODES:
        fallback_reason = (
            f"Unsupported COGNIGUARD_RUNTIME_MODE={requested_mode!r}; "
            "using the safest available mode."
        )
        requested_mode = ""

    if requested_mode == "mock":
        runtime_mode = "mock"
        nemo_enabled = False
        agent_call_mode = "deterministic_fallback"
        fallback_reason = fallback_reason or "Mock mode requested explicitly."
    elif not api_key_loaded:
        runtime_mode = "mock"
        nemo_enabled = False
        agent_call_mode = "deterministic_fallback"
        fallback_reason = (
            fallback_reason or "MIMO_API_KEY is not configured; using deterministic fallback."
        )
    elif requested_mode == "guarded_llm" or (not requested_mode and guardrails_requested):
        runtime_mode = "guarded_llm"
        nemo_enabled = True
        agent_call_mode = "real_llm"
    else:
        runtime_mode = "llm"
        nemo_enabled = False
        agent_call_mode = "real_llm"

    nemo_runtime_available = _nemo_guardrails_available()
    # build_guardrail_adapter always constructs CG's deterministic adapter.
    # Package availability alone does not mean an LLMRails runtime is executing.
    guardrail_backend = "cg_deterministic_adapter" if nemo_enabled else "disabled"

    return RuntimeStatus(
        runtime_mode=runtime_mode,
        llm_provider="Xiaomi MiMo",
        api_key_loaded=api_key_loaded,
        nemo_guardrails_enabled=nemo_enabled,
        fallback_reason=fallback_reason,
        agent_call_mode=agent_call_mode,
        guardrail_backend=guardrail_backend,
        nemo_runtime_available=nemo_runtime_available,
        nemo_native_configured=os.environ.get("COGNIGUARD_NEMO_NATIVE", "off").strip().lower()
        == "on",
        nemo_semantic_configured=os.environ.get("COGNIGUARD_NEMO_SEMANTIC", "off").strip().lower()
        == "on",
    ).to_dict()


def build_runtime_llm_client(
    env_file: str | os.PathLike[str] | None = None,
) -> Any | None:
    status = get_runtime_status(env_file=env_file)
    if status["agent_call_mode"] != "real_llm":
        return None
    from cogniguard.providers.mimo import build_default_llm_client

    return build_default_llm_client(env_file=env_file)


def build_student_runtime_llm_client(
    env_file: str | os.PathLike[str] | None = None,
) -> Any | None:
    status = get_runtime_status(env_file=env_file)
    if status["agent_call_mode"] != "real_llm":
        return None
    from cogniguard.providers.mimo import build_student_llm_client

    return build_student_llm_client(env_file=env_file)


def build_guardrail_adapter(
    env_file: str | os.PathLike[str] | None = None,
) -> NeMoGuardrailsAdapter | None:
    status = get_runtime_status(env_file=env_file)
    if not status["nemo_guardrails_enabled"]:
        return None
    config_path = os.environ.get(
        "COGNIGUARD_NEMO_CONFIG_PATH",
        str(DEFAULT_GUARDRAILS_CONFIG),
    )
    return NeMoGuardrailsAdapter(config_path=config_path, enabled=True)


def _has_mimo_key() -> bool:
    key = os.environ.get("MIMO_API_KEY", "").strip()
    return key.lower() not in PLACEHOLDER_KEYS


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _nemo_guardrails_available() -> bool:
    try:
        import nemoguardrails  # noqa: F401
    except Exception:
        return False
    return True


def _load_env_file(env_file: str | os.PathLike[str] | None = None) -> None:
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
    for directory in [cwd, *cwd.parents]:
        path = directory / ".env"
        if path.exists():
            return path
    return None
