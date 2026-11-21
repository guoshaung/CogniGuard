"""Persist and summarize dashboard run history."""

from __future__ import annotations

import json
import math
from typing import Any

from core.paths import OUTPUTS_DIR


def append_log(entry: dict[str, Any]) -> None:
    """Helper to persist a run or attack log to run_history.json."""
    history_file = OUTPUTS_DIR / "run_history.json"
    history = []
    if history_file.exists():
        try:
            with history_file.open("r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            pass
    history.append(entry)
    history_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with history_file.open("w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def build_history_metrics() -> dict[str, Any]:
    history_file = OUTPUTS_DIR / "run_history.json"
    if not history_file.exists():
        return {
            "history_exists": False,
            "total_runs": 0,
            "total_agent_calls": 0,
            "total_attacks": 0,
            "blocked_attacks": 0,
            "sanitized_attacks": 0,
            "degraded_attacks": 0,
            "successful_attacks": 0,
            "attack_success_rate": 0.0,
            "defense_success_rate": 0.0,
            "privacy_leakage_rate": 0.0,
            "copyright_leakage_rate": 0.0,
            "unauthorized_agent_access_rate": 0.0,
            "audit_coverage_rate": 0.0,
            "nemo_block_count": 0,
            "nemo_sanitize_count": 0,
            "cg_block_count": 0,
            "cg_degrade_count": 0,
        }

    try:
        with history_file.open("r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        history = []

    normal_runs = [r for r in history if r.get("type") == "normal"]
    attack_runs = [r for r in history if r.get("type") == "attack"]
    if not normal_runs and not attack_runs:
        return {
            "history_exists": False,
            "total_runs": 0,
            "total_agent_calls": 0,
            "total_attacks": 0,
            "blocked_attacks": 0,
            "sanitized_attacks": 0,
            "degraded_attacks": 0,
            "successful_attacks": 0,
            "attack_success_rate": 0.0,
            "defense_success_rate": 0.0,
            "privacy_leakage_rate": 0.0,
            "copyright_leakage_rate": 0.0,
            "unauthorized_agent_access_rate": 0.0,
            "audit_coverage_rate": 0.0,
            "nemo_block_count": 0,
            "nemo_sanitize_count": 0,
            "cg_block_count": 0,
            "cg_degrade_count": 0,
        }

    total_runs = len(normal_runs)
    total_attacks = len(attack_runs)
    blocked_attacks = sum(
        1
        for r in attack_runs
        if "Blocked" in r.get("result", "")
        or "Refused" in r.get("result", "")
        or "Intercepted" in r.get("result", "")
    )
    sanitized_attacks = sum(1 for r in attack_runs if "Sanitized" in r.get("result", ""))
    degraded_attacks = sum(1 for r in attack_runs if "Degraded" in r.get("result", ""))

    successful_attacks = sum(
        1
        for r in attack_runs
        if r.get("result") == "Success"
        or (
            "Blocked" not in r.get("result", "")
            and "Refused" not in r.get("result", "")
            and "Sanitized" not in r.get("result", "")
            and "Degraded" not in r.get("result", "")
            and "Intercepted" not in r.get("result", "")
        )
    )

    attack_success_rate = (successful_attacks / total_attacks) if total_attacks > 0 else 0.0
    defended_attacks = sum(
        1
        for r in attack_runs
        if any(
            decision in r.get("result", "")
            for decision in ("Blocked", "Refused", "Intercepted", "Sanitized", "Degraded")
        )
    )
    defense_success_rate = (
        defended_attacks / total_attacks if total_attacks > 0 else (1.0 if total_runs > 0 else 0.0)
    )

    def observed_mean(key):
        values = [
            row[key]
            for row in normal_runs
            if isinstance(row.get(key), (int, float))
            and not isinstance(row.get(key), bool)
            and math.isfinite(row[key])
        ]
        return (sum(values) / len(values), len(values)) if values else (None, 0)

    privacy_leakage_rate, privacy_observations = observed_mean("disclosure_score")
    copyright_leakage_rate, copyright_observations = observed_mean("copyright_leakage_rate")

    unauthorized_attempts = sum(1 for r in attack_runs if r.get("attack_case_id") == "atk_005")
    unauthorized_successes = sum(
        1
        for r in attack_runs
        if r.get("attack_case_id") == "atk_005" and r.get("result") == "Success"
    )
    unauthorized_agent_access_rate = (
        (unauthorized_successes / unauthorized_attempts) if unauthorized_attempts > 0 else 0.0
    )

    audit_coverage_rate = (
        sum(1 for r in normal_runs if r.get("watermark_bound", False)) / total_runs
        if total_runs
        else 0.0
    )

    return {
        "history_exists": True,
        "total_runs": total_runs,
        "total_agent_calls": total_runs * 4,
        "total_attacks": total_attacks,
        "blocked_attacks": blocked_attacks,
        "sanitized_attacks": sanitized_attacks,
        "degraded_attacks": degraded_attacks,
        "successful_attacks": successful_attacks,
        "attack_success_rate": attack_success_rate,
        "defense_success_rate": defense_success_rate,
        "privacy_leakage_rate": privacy_leakage_rate,
        "copyright_leakage_rate": copyright_leakage_rate,
        "privacy_metric_kind": "disclosure_score_proxy",
        "privacy_metric_observations": privacy_observations,
        "copyright_metric_observations": copyright_observations,
        "unauthorized_agent_access_rate": unauthorized_agent_access_rate,
        "audit_coverage_rate": audit_coverage_rate,
        "nemo_block_count": sum(
            1 for r in attack_runs if r.get("attack_case_id") in ("atk_001", "atk_002")
        ),
        "nemo_sanitize_count": sum(1 for r in attack_runs if r.get("attack_case_id") == "atk_003"),
        "cg_block_count": sum(
            1 for r in attack_runs if r.get("attack_case_id") in ("atk_004", "atk_005", "atk_007")
        ),
        "cg_degrade_count": sum(1 for r in attack_runs if r.get("attack_case_id") == "atk_006"),
    }
