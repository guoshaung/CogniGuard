#!/usr/bin/env python3
"""Validate that readiness evidence belongs to the API process just launched."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class ApiInstanceValidationError(RuntimeError):
    """Raised when health evidence does not match the run-local API identity."""


_FORBIDDEN_SECRET_KEYS = {
    "registry_secret",
    "registry_secret_value",
    "registry_hmac_key",
    "sce_locguard_registry_secret",
}


def _mapping_contains_forbidden_secret_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in _FORBIDDEN_SECRET_KEYS:
                return True
            if _mapping_contains_forbidden_secret_key(child):
                return True
    elif isinstance(value, list):
        return any(_mapping_contains_forbidden_secret_key(child) for child in value)
    return False


def validate_api_instance_health(
    health: Mapping[str, Any], *, expected_nonce: str, expected_job_root: Path
) -> dict[str, str]:
    """Return normalized public evidence or fail closed on any identity drift."""

    if re.fullmatch(r"[0-9a-f]{64}", expected_nonce) is None:
        raise ApiInstanceValidationError(
            "Expected API run-instance nonce is not 256-bit lowercase hex."
        )
    expected_root = expected_job_root.expanduser().resolve()
    if not expected_root.is_absolute():
        raise ApiInstanceValidationError("Expected API job root must be absolute.")
    failures: list[str] = []
    if health.get("status") != "ok" or health.get("service") != "sce-locguard":
        failures.append("static health identity")
    if health.get("run_instance_nonce") != expected_nonce:
        failures.append("run_instance_nonce")
    if health.get("api_job_root") != str(expected_root):
        failures.append("api_job_root")
    if _mapping_contains_forbidden_secret_key(health):
        failures.append("raw registry secret field")
    if failures:
        raise ApiInstanceValidationError(
            "API instance attestation mismatch: " + ", ".join(failures)
        )
    return {
        "status": "ready",
        "run_instance_nonce": expected_nonce,
        "api_job_root": str(expected_root),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate run-local SCE-LocGuard health evidence."
    )
    parser.add_argument("--health-json", type=Path, required=True)
    parser.add_argument("--expected-nonce", required=True)
    parser.add_argument("--expected-job-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = json.loads(args.health_json.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ApiInstanceValidationError("Health JSON root must be an object.")
        validate_api_instance_health(
            payload,
            expected_nonce=args.expected_nonce,
            expected_job_root=args.expected_job_root,
        )
    except (OSError, json.JSONDecodeError, ApiInstanceValidationError) as exc:
        raise SystemExit(str(exc)) from exc
    print("API instance attestation: ready")


if __name__ == "__main__":
    main()
