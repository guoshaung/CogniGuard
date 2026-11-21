"""One case execution path for GET, POST, and NDJSON transports."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Callable

from cogniguard.runtime.mode import runtime_options

from .. import dependencies
from .history import append_log
from .watermarks import register_watermark_session


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    raise ValueError("enable_nemo must be a boolean")


def execute_case(
    case_index: int,
    *,
    episode_id: str | None = None,
    runtime_mode: str = "guarded_llm",
    enable_nemo: bool = True,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    with runtime_options(runtime_mode, enable_nemo):
        if dependencies.run_demo is None:
            return {
                "error": "cogniguard.applications.education.case_study not importable",
                "case_index": case_index,
                "runtime_status": {
                    "runtime_mode": "mock",
                    "agent_call_mode": "deterministic_fallback",
                    "nemo_guardrails_enabled": False,
                },
            }
        kwargs: dict[str, Any] = {
            "data_root": dependencies.PROJECT_ROOT / "data",
            "case_index": case_index,
            "episode_id": episode_id,
        }
        if event_sink is not None:
            kwargs["event_sink"] = event_sink
        result = dependencies.run_demo(**kwargs)
        # run_demo owns all descriptive content inside its delivery gateway.
        # Do not append unchecked dataset strings after its final validation.
        result["runtime_status"] = dependencies.get_runtime_status()
        register_watermark_session(result)
        context_card = result.get("generated_context_card", {})
        resource_log = result.get("protection_logs", {}).get("c2_rag", {})
        protection = result.get("protection") or {}
        budgets = protection.get("budgets") or {}

        def measured(value):
            return (
                value
                if isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                else None
            )

        append_log(
            {
                "type": "normal",
                "timestamp": datetime.now().isoformat(),
                "case_index": case_index,
                "episode_id": episode_id,
                "disclosure_score": measured(context_card.get("disclosure_score")),
                "copyright_leakage_rate": measured(resource_log.get("copyright_leakage_rate")),
                "copyright_exposure_cost": measured(resource_log.get("exposure_cost")),
                "privacy_budget_used": measured((budgets.get("privacy") or {}).get("used")),
                "copyright_budget_used": measured((budgets.get("copyright") or {}).get("used")),
                "watermark_bound": (
                    (result.get("text_watermark") or {}).get("watermark_verified") is True
                    and ((result.get("protection") or {}).get("watermark_verification") or {}).get(
                        "valid"
                    )
                    is True
                ),
            }
        )
        return result
