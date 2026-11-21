from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.server.audit_image_watermark_attack_runtime import (
    AttackRuntimeAuditError,
    compare_reports,
    emit_report,
)


def _config(path: Path) -> Path:
    path.write_text(
        yaml.safe_dump(
            {
                "experiment": {},
                "attacks": {
                    "traditional": [
                        {"name": "clean", "family": "clean"},
                        {
                            "name": "gaussian_noise",
                            "family": "degradation",
                            "grid": [{"sigma": 2.0}, {"sigma": 5.0}],
                        },
                        {
                            "name": "erasing",
                            "family": "removal",
                            "grid": [{"area_ratio": 0.15}],
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_emit_is_deterministic_and_records_runtime(tmp_path: Path) -> None:
    config = _config(tmp_path / "config.yaml")
    first = emit_report(config, seed=17, label="first")
    second = emit_report(config, seed=17, label="second")

    assert first["schema_version"].endswith(".v1")
    assert first["attack_count"] == 4
    assert first["attacks"] == second["attacks"]
    assert first["attack_implementation_sha256"] == second["attack_implementation_sha256"]
    assert all(len(row["pixel_sha256"]) == 64 for row in first["attacks"])
    assert all(len(row["png_sha256"]) == 64 for row in first["attacks"])


def test_compare_accepts_identical_reports_and_rejects_drift(tmp_path: Path) -> None:
    config = _config(tmp_path / "config.yaml")
    reports = []
    for label in ("main", "trustmark", "wam"):
        payload = emit_report(config, seed=17, label=label)
        path = tmp_path / f"{label}.json"
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        reports.append(path)

    consensus = compare_reports(reports)
    assert consensus["status"] == "identical"
    assert consensus["labels"] == ["main", "trustmark", "wam"]

    drift = json.loads(reports[-1].read_text(encoding="utf-8"))
    drift["attacks"][0]["pixel_sha256"] = "0" * 64
    reports[-1].write_text(json.dumps(drift), encoding="utf-8")
    with pytest.raises(AttackRuntimeAuditError, match="not byte-identical"):
        compare_reports(reports)


def test_emit_rejects_required_version_mismatch(tmp_path: Path) -> None:
    config = _config(tmp_path / "config.yaml")
    payload = yaml.safe_load(config.read_text(encoding="utf-8"))
    payload["experiment"]["required_attack_runtime"] = {
        "Pillow": "0.0-impossible"
    }
    config.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(AttackRuntimeAuditError, match="does not match"):
        emit_report(config, seed=17, label="invalid")
