from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts.server import analyze_image_watermark_spatial_filter as analyzer
from scripts.server.image_watermark_redevelopment_protocol import (
    CALIBRATION_RUN_CLASS,
    CONFIRMATION_RUN_CLASS,
    SPATIAL_FILTER_CANDIDATES,
    STATISTICAL_UNITS,
    candidate_id,
    required_capabilities,
)


def _candidate_report(area_ratio: float, *, passed: bool) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id(area_ratio),
        "localization_min_component_area_ratio": area_ratio,
        "required_capabilities": required_capabilities(area_ratio),
        "all_constraints_satisfied": passed,
        "authenticated_attack_input_identity_sha256": "a" * 64,
        "environment_identity_sha256": "e" * 64,
        "environment_identity": {
            "source_tree_sha256": "s" * 64,
            "source_tree_file_count": 42,
        },
    }


def test_calibration_selects_smallest_candidate_that_passes_both_units(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "calibration.yaml"
    config_path.write_text("fixture: true\n", encoding="utf-8")
    contract = {
        "statistical_units": STATISTICAL_UNITS,
        "winner_rule": "smallest_candidate_satisfying_all_constraints",
    }
    monkeypatch.setattr(
        analyzer,
        "_validate_config_and_manifest",
        lambda *_args, **_kwargs: ({}, contract, [object()] * 300, CALIBRATION_RUN_CLASS),
    )

    def fake_validate_candidate(**kwargs: Any) -> dict[str, Any]:
        ratio = kwargs["area_ratio"]
        return _candidate_report(ratio, passed=ratio in {0.01, 0.02})

    monkeypatch.setattr(analyzer, "_validate_candidate", fake_validate_candidate)

    report = analyzer.analyze_bundle(config_path, run_root=tmp_path)

    assert report["status"] == "winner_selected"
    assert report["calibration_passed"] is True
    assert report["selected_candidate"][
        "localization_min_component_area_ratio"
    ] == 0.01
    assert report["formal_test_rows_consumed"] == 0
    assert len(report["candidate_reports"]) == len(SPATIAL_FILTER_CANDIDATES)


def test_confirmation_failure_never_falls_back_or_authorizes_formal_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "confirmation.yaml"
    config_path.write_text("fixture: true\n", encoding="utf-8")
    candidate_root = tmp_path / "confirmation-run" / candidate_id(0.005)
    config = {"experiment": {"output_root": str(candidate_root)}}
    contract = {
        "statistical_units": STATISTICAL_UNITS,
        "selected_required_capabilities": required_capabilities(0.005),
    }
    monkeypatch.setattr(
        analyzer,
        "_validate_config_and_manifest",
        lambda *_args, **_kwargs: (
            config,
            contract,
            [object()] * 600,
            CONFIRMATION_RUN_CLASS,
        ),
    )
    monkeypatch.setattr(
        analyzer,
        "_validate_candidate",
        lambda **_kwargs: _candidate_report(0.005, passed=False),
    )
    monkeypatch.setattr(
        analyzer,
        "_validate_confirmation_lineage",
        lambda _contract: {
            "calibration_source_tree_sha256": "s" * 64,
            "calibration_winner": {
                "candidate_id": candidate_id(0.005),
            },
        },
    )

    report = analyzer.analyze_bundle(config_path, run_root=tmp_path)

    assert report["status"] == "confirmation_failed"
    assert report["confirmation_passed"] is False
    assert report["formal_execution_authorized"] is False
    assert report["fallback_candidate_allowed"] is False
    assert report["formal_test_rows_consumed"] == 0


def test_constraints_require_clean_and_each_erasing_condition() -> None:
    by_attack = {
        "clean": [0.0, 0.0001],
        "erasing__area_ratio-0.05": [0.9, 0.9],
        "erasing__area_ratio-0.15": [0.95, 0.95],
        "erasing__area_ratio-0.25": [0.96, 0.96],
    }
    summary = analyzer._metric_summary(by_attack)
    constraints = analyzer._constraint_results(summary)

    assert all(constraints.values())
    summary["erasing"]["0.15"]["p10_mask_iou"] = 0.74
    constraints = analyzer._constraint_results(summary)
    assert constraints["erasing_0.15_p10_mask_iou"] is False
