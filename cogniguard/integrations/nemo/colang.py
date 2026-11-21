"""Preparation metadata for a future, explicitly implemented Colang bridge.

No NeMo import, YAML runtime parsing, action registration or generation occurs.
Keeping configuration files is not evidence that their flows are executing.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from core.paths import CG_GUARDRAILS_DIR

_ACTIONS = (
    {
        "name": "sanitize_retrieved_prompt_injection",
        "hook": "retrieval",
        "policy_owner": "C2-RAG",
        "legacy_symbol": "protection.supporting.cg_guardrails.actions.sanitize_retrieved_prompt_injection",
    },
    {
        "name": "block_original_teacher_resource_retrieval",
        "hook": "retrieval",
        "policy_owner": "C2-RAG",
        "legacy_symbol": "protection.supporting.cg_guardrails.actions.block_original_teacher_resource_retrieval",
    },
    {
        "name": "block_raw_profile_or_multimodal_output",
        "hook": "output",
        "policy_owner": "MM-FOPD + CGC",
        "legacy_symbol": "protection.supporting.cg_guardrails.actions.block_raw_profile_or_multimodal_output",
    },
    {
        "name": "block_copyrighted_original_output",
        "hook": "output",
        "policy_owner": "C2-RAG + CGC",
        "legacy_symbol": "protection.supporting.cg_guardrails.actions.block_copyrighted_original_output",
    },
)
_HOOKS = (
    {
        "name": "input",
        "policy_owner": "MM-FOPD + CGC",
        "purpose": "trusted scope and profile minimization",
    },
    {
        "name": "retrieval",
        "policy_owner": "C2-RAG",
        "purpose": "retrieval evidence and controlled resource release",
    },
    {
        "name": "dialog",
        "policy_owner": "LangGraph + CGC",
        "purpose": "application dialogue and session transitions",
    },
    {
        "name": "execution",
        "policy_owner": "CGC",
        "purpose": "capabilities, action validation and budgets",
    },
    {
        "name": "output",
        "policy_owner": "MM-FOPD + C2-RAG + HSW-ST + CGC",
        "purpose": "final content policy, watermark and provenance",
    },
)


class ColangExecutionDisabled(RuntimeError):
    """Native Colang execution has not been implemented or enabled."""


class ColangInterface:
    """A disabled, inspectable boundary; enabled=True is rejected, not executed.

    Hook/action metadata describes intended ownership and retained configuration,
    not registration in an active NeMo runtime. CogniGuard remains the policy
    owner. A future bridge needs new implementation and version validation.
    """

    __slots__ = ("_config_path",)

    def __init__(self, config_path: str | Path | None = None, *, enabled: bool = False):
        if enabled is not False:
            raise ColangExecutionDisabled(
                "Colang execution is unavailable; enabled=True cannot activate it"
            )
        path = (
            Path(config_path).expanduser()
            if config_path is not None
            else CG_GUARDRAILS_DIR
        )
        self._config_path = path.resolve()

    @property
    def enabled(self) -> bool:
        return False

    @property
    def config_path(self) -> Path:
        return self._config_path

    @property
    def actions(self) -> list[dict[str, Any]]:
        return [
            {**deepcopy(action), "status": "metadata_only", "colang_execution_enabled": False}
            for action in _ACTIONS
        ]

    @property
    def hooks(self) -> list[dict[str, Any]]:
        return [
            {**deepcopy(hook), "status": "application_owned", "colang_execution_enabled": False}
            for hook in _HOOKS
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "interface_version": "cogniguard-colang-disabled-v1",
            "status": "disabled",
            "enabled": False,
            "can_execute": False,
            "native_runtime_loaded": False,
            "native_version_verified": False,
            "policy_owner": "CogniGuard",
            "config_path": str(self.config_path),
            "config_exists": self.config_path.is_dir(),
            "actions": self.actions,
            "hooks": self.hooks,
        }

    def prepare(self) -> dict[str, Any]:
        """List candidate files without importing, parsing or executing them."""
        files = []
        if self.config_path.is_dir():
            files = [
                str(path)
                for path in sorted(self.config_path.iterdir())
                if path.is_file() and path.suffix in {".yml", ".yaml", ".co", ".py"}
            ]
        return {
            **self.describe(),
            "preparation": "metadata_only",
            "config_files": files,
            "configuration_parsed": False,
            "actions_registered": False,
            "future_activation_requires": [
                "implement a native bridge",
                "explicitly configure native execution",
                "verify the supported NeMo and Colang versions",
                "preserve CogniGuard domain ownership and final delivery checks",
            ],
        }

    def execute(self, *args, **kwargs):
        raise ColangExecutionDisabled(
            "Colang execution is disabled; no native NeMo runtime is loaded"
        )

    def generate(self, *args, **kwargs):
        raise ColangExecutionDisabled("Colang generation is disabled; no model call was made")
