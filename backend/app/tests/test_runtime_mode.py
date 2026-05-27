from __future__ import annotations

from pathlib import Path

from backend.app.protection.tpcs.nemo_guardrails_adapter import (
    NeMoGuardrailsAdapter,
)
from backend.app.runtime.mode import build_guardrail_adapter, get_runtime_status


def test_runtime_status_mock_without_api_key(
    monkeypatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("COGNIGUARD_RUNTIME_MODE", raising=False)
    monkeypatch.delenv("COGNIGUARD_NEMO_GUARDRAILS_ENABLED", raising=False)

    status = get_runtime_status(env_file=env_file)

    assert status["runtime_mode"] == "mock"
    assert status["llm_provider"] == "MiniMax"
    assert status["api_key_loaded"] is False
    assert status["nemo_guardrails_enabled"] is False
    assert status["agent_call_mode"] == "deterministic_fallback"
    assert "MINIMAX_API_KEY" in status["fallback_reason"]


def test_runtime_status_llm_with_api_key(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-test-runtime-key")
    monkeypatch.setenv("COGNIGUARD_RUNTIME_MODE", "llm")
    monkeypatch.delenv("COGNIGUARD_NEMO_GUARDRAILS_ENABLED", raising=False)

    status = get_runtime_status(env_file=env_file)

    assert status["runtime_mode"] == "llm"
    assert status["api_key_loaded"] is True
    assert status["nemo_guardrails_enabled"] is False
    assert status["agent_call_mode"] == "real_llm"


def test_runtime_status_guarded_llm_uses_tpcs_guardrails(
    monkeypatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-test-runtime-key")
    monkeypatch.setenv("COGNIGUARD_RUNTIME_MODE", "guarded_llm")

    status = get_runtime_status(env_file=env_file)

    assert status["runtime_mode"] == "guarded_llm"
    assert status["nemo_guardrails_enabled"] is True
    assert status["agent_call_mode"] == "real_llm"


def test_guarded_runtime_builds_nemo_adapter(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-test-runtime-key")
    monkeypatch.setenv("COGNIGUARD_RUNTIME_MODE", "guarded_llm")

    adapter = build_guardrail_adapter(env_file=env_file)

    assert isinstance(adapter, NeMoGuardrailsAdapter)
    assert adapter.enabled is True
    assert adapter.config_exists is True
