from __future__ import annotations

from pathlib import Path

import pytest

from scripts.server.validate_image_watermark_api_instance import (
    ApiInstanceValidationError,
    validate_api_instance_health,
)


NONCE = "ab" * 32


def _health(job_root: Path) -> dict[str, object]:
    return {
        "status": "ok",
        "service": "sce-locguard",
        "run_instance_nonce": NONCE,
        "api_job_root": str(job_root.resolve()),
        "constraints": {"verification_mode": "blind"},
    }


def test_api_instance_health_requires_exact_nonce_and_job_root(tmp_path: Path) -> None:
    job_root = tmp_path / "run" / "api_jobs"
    expected = validate_api_instance_health(
        _health(job_root), expected_nonce=NONCE, expected_job_root=job_root
    )
    assert expected["status"] == "ready"

    wrong_nonce = _health(job_root)
    wrong_nonce["run_instance_nonce"] = "cd" * 32
    with pytest.raises(ApiInstanceValidationError, match="run_instance_nonce"):
        validate_api_instance_health(
            wrong_nonce, expected_nonce=NONCE, expected_job_root=job_root
        )

    with pytest.raises(ApiInstanceValidationError, match="api_job_root"):
        validate_api_instance_health(
            _health(tmp_path / "old-run" / "api_jobs"),
            expected_nonce=NONCE,
            expected_job_root=job_root,
        )


def test_api_instance_health_rejects_raw_secret_fields(tmp_path: Path) -> None:
    health = _health(tmp_path / "api_jobs")
    health["nested"] = {"registry_secret": "must-not-appear"}
    with pytest.raises(ApiInstanceValidationError, match="raw registry secret"):
        validate_api_instance_health(
            health,
            expected_nonce=NONCE,
            expected_job_root=tmp_path / "api_jobs",
        )
