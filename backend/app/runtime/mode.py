from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from backend.app.protection.tpcs.nemo_guardrails_adapter import (
    NeMoGuardrailsAdapter,
)

VALID_RUNTIME_MODES = {"mock", "llm", "guarded_llm"}
PLACEHOLDER_KEYS = {"", "your_mimo_api_key_here", "your_openai_api_key_here"}
DEFAULT_GUARDRAILS_CONFIG = (
    Path(__file__).resolve().parents[3] / "protection" / "tpcs_guardrails"
)
GuardrailAdapter = NeMoGuardrailsAdapter


@dataclass(frozen=True, slots=True)
class RuntimeStatus:
    runtime_mode: str
    llm_provider: str
    api_key_loaded: bool
    nemo_guardrails_enabled: bool
    fallback_reason: str
    agent_call_mode: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_runtime_status(env_file: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    _load_env_file(env_file)

    requested_mode = os.environ.get("COGNIGUARD_RUNTIME_MODE", "").strip().lower()
    api_key_loaded = _has_mimo_key()
    guardrails_requested = requested_mode == "guarded_llm" or _truthy(
        os.environ.get("COGNIGUARD_NEMO_GUARDRAILS_ENABLED")
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
            fallback_reason
            or "MIMO_API_KEY is not configured; using deterministic fallback."
        )
    elif requested_mode == "guarded_llm" or (not requested_mode and guardrails_requested):
        runtime_mode = "guarded_llm"
        nemo_enabled = True
        agent_call_mode = "real_llm"
    else:
        runtime_mode = "llm"
        nemo_enabled = False
        agent_call_mode = "real_llm"

    return RuntimeStatus(
        runtime_mode=runtime_mode,
        llm_provider="Xiaomi MiMo",
        api_key_loaded=api_key_loaded,
        nemo_guardrails_enabled=nemo_enabled,
        fallback_reason=fallback_reason,
        agent_call_mode=agent_call_mode,
    ).to_dict()


def build_runtime_llm_client(
    env_file: str | os.PathLike[str] | None = None,
) -> Any | None:
    status = get_runtime_status(env_file=env_file)
    if status["agent_call_mode"] != "real_llm":
        return None
    from backend.app.agents.mimo_client import build_default_llm_client

    return build_default_llm_client(env_file=env_file)


def build_student_runtime_llm_client(
    env_file: str | os.PathLike[str] | None = None,
) -> Any | None:
    status = get_runtime_status(env_file=env_file)
    if status["agent_call_mode"] != "real_llm":
        return None
    from backend.app.agents.mimo_client import build_student_llm_client

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
