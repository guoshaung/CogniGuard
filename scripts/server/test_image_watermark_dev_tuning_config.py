from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from scripts.server import preflight_image_watermark as preflight
from scripts.server.build_image_watermark_dev_tuning_config import (
    EXPECTED_SAMPLES,
    RUN_CLASS,
    build_dev_tuning_bundle,
    manifest_text,
)


DOMAINS = [
    "presentation_slide",
    "chemistry_diagram",
    "fractions",
    "geometry",
    "practice_worksheet",
    "function_plot",
    "physics_diagram",
    "statistics",
    "flowchart",
]


def _source_bundle(tmp_path: Path, *, dev_samples: int = EXPECTED_SAMPLES) -> Path:
    dataset_root = tmp_path / "synthetic"
    dataset_root.mkdir()
    manifest = tmp_path / "paper_core.jsonl"
    rows = []
    for split, sample_count in (("dev", dev_samples), ("test", 8)):
        for index in range(sample_count):
            image_bytes = f"synthetic-image-test-fixture|{split}|{index}".encode()
            relative_path = f"{split}-{index:03d}.png"
            (dataset_root / relative_path).write_bytes(image_bytes)
            rows.append(
                {
                    "sample_id": f"synthetic:{relative_path}",
                    "relative_path": relative_path,
                    "split": split,
                    "source_dataset": "cogniguard_edufig_v2",
                    "source_family": f"synthetic-family:{split}:{index:03d}",
                    "domain": DOMAINS[index % len(DOMAINS)],
                    "license_id": "CC0-1.0",
                    "provenance": "programmatic:test",
                    "sha256": hashlib.sha256(image_bytes).hexdigest(),
                }
            )
    manifest.write_text(manifest_text(rows), encoding="utf-8")
    config = {
        "experiment": {
            "name": "formal_source",
            "split": "test",
            "seeds": [20260802, 20260803],
            "api_timeout_seconds": 900,
        },
        "manifest": {"path": str(manifest), "verify_hashes": True},
        "metrics": {"lpips": {"enabled": True, "required": True}},
        "datasets": [
            {
                "name": "cogniguard_edufig_v2",
                "enabled": True,
                "root": str(dataset_root),
            },
            {
                "name": "future_external",
                "enabled": True,
                "root": str(tmp_path / "missing-future-root"),
            },
        ],
        "methods": [
            {
                "id": "editguard_wrapper",
                "kind": "sce_locguard_api",
                "base_url": "http://127.0.0.1:8010",
                "enabled": True,
            },
            {
                "id": "future_method",
                "kind": "sce_locguard_api",
                "base_url": "http://127.0.0.1:8110",
                "enabled": False,
            },
        ],
        "attacks": {
            "traditional": [
                {"name": "clean", "family": "clean"},
                {
                    "name": "jpeg",
                    "family": "compression",
                    "grid": [
                        {"quality": 90},
                        {"quality": 70},
                        {"quality": 50},
                    ],
                },
                {
                    "name": "resize",
                    "family": "geometry",
                    "grid": [{"scale": 0.5}, {"scale": 0.75}],
                },
                {
                    "name": "gaussian_noise",
                    "family": "degradation",
                    "grid": [
                        {"sigma": 2.0},
                        {"sigma": 5.0},
                        {"sigma": 10.0},
                    ],
                },
            ],
            "aigc": {
                "enabled": True,
                "specs": [{"name": "inpainting", "requires_aigc": True}],
            },
        },
    }
    source = tmp_path / "paper_benchmark.yaml"
    source.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return source


def test_builder_isolates_exact_dev_split_and_attack_grid(tmp_path: Path) -> None:
    source = _source_bundle(tmp_path)
    output_config = tmp_path / "run" / "dev_tuning.yaml"
    output_manifest = tmp_path / "run" / "synthetic_dev_117.jsonl"

    config, rows = build_dev_tuning_bundle(
        source,
        output_config=output_config,
        output_manifest=output_manifest,
    )

    assert len(rows) == 117
    assert {row["split"] for row in rows} == {"dev"}
    assert {row["source_dataset"] for row in rows} == {"cogniguard_edufig_v2"}
    assert all("test-" not in row["sample_id"] for row in rows)
    assert config["experiment"]["run_class"] == RUN_CLASS
    assert config["experiment"]["paper_eligible"] is False
    assert config["experiment"]["split"] == "dev"
    assert config["experiment"]["seeds"] == [20260802]
    assert config["experiment"]["max_samples"] == 117
    assert config["manifest"]["path"] == str(output_manifest.resolve())
    assert [dataset["name"] for dataset in config["datasets"]] == [
        "cogniguard_edufig_v2"
    ]
    assert [method["id"] for method in config["methods"]] == ["editguard_wrapper"]
    assert config["metrics"]["lpips"] == {"enabled": False, "required": False}
    assert config["attacks"]["aigc"] == {"enabled": False, "specs": []}
    assert config["attacks"]["traditional"] == [
        {"name": "clean", "family": "clean"},
        {"name": "jpeg", "family": "compression", "grid": [{"quality": 70}]},
        {
            "name": "gaussian_noise",
            "family": "degradation",
            "grid": [{"sigma": 5.0}],
        },
        {"name": "resize", "family": "geometry", "grid": [{"scale": 0.75}]},
    ]
    assert config["dev_tuning"]["expected_rows"] == 468
    assert config["dev_tuning"]["attack_profile"] == "baseline"
    assert config["dev_tuning"]["attack_conditions"] == [
        "clean",
        "jpeg_quality_70",
        "gaussian_noise_sigma_5.0",
        "resize_scale_0.75",
    ]
    assert config["dev_tuning"]["test_samples_consumed"] == 0
    assert config["dev_tuning"]["golden_test_consumed"] is False
    assert config["dev_tuning"]["pilot_outputs_reused"] is False
    assert config["dev_tuning"]["decoder_mode"] == "identity_single_view"
    assert config["dev_tuning"]["multi_view_enabled"] is False
    assert config["dev_tuning"]["registry_hamming_radii_evaluated"] == [1]
    assert config["dev_tuning"]["selected_manifest_sha256"]
    assert config["dev_tuning"]["source_manifest_sha256"]


def test_builder_creates_strict_selection_grid_without_resize(tmp_path: Path) -> None:
    source = _source_bundle(tmp_path)
    output_config = tmp_path / "run" / "dev_tuning.yaml"
    output_manifest = tmp_path / "run" / "synthetic_dev_117.jsonl"

    config, rows = build_dev_tuning_bundle(
        source,
        output_config=output_config,
        output_manifest=output_manifest,
        attack_profile="selection-grid",
    )

    assert len(rows) == 117
    assert {row["split"] for row in rows} == {"dev"}
    assert all("test-" not in row["sample_id"] for row in rows)
    assert config["experiment"]["seeds"] == [20260802]
    assert config["experiment"]["max_samples"] == 117
    assert [method["id"] for method in config["methods"]] == ["editguard_wrapper"]
    assert config["metrics"]["lpips"] == {"enabled": False, "required": False}
    assert config["attacks"]["aigc"] == {"enabled": False, "specs": []}
    assert config["attacks"]["traditional"] == [
        {"name": "clean", "family": "clean"},
        {
            "name": "jpeg",
            "family": "compression",
            "grid": [{"quality": 90}, {"quality": 70}, {"quality": 50}],
        },
        {
            "name": "gaussian_noise",
            "family": "degradation",
            "grid": [{"sigma": 2.0}, {"sigma": 5.0}, {"sigma": 10.0}],
        },
    ]
    tuning = config["dev_tuning"]
    assert tuning["attack_profile"] == "selection-grid"
    assert tuning["expected_rows"] == 819
    assert tuning["attack_conditions"] == [
        "clean",
        "jpeg_quality_90",
        "jpeg_quality_70",
        "jpeg_quality_50",
        "gaussian_noise_sigma_2.0",
        "gaussian_noise_sigma_5.0",
        "gaussian_noise_sigma_10.0",
    ]
    assert tuning["test_samples_consumed"] == 0
    assert tuning["golden_test_consumed"] is False
    assert tuning["pilot_outputs_reused"] is False
    assert tuning["excluded_splits"] == ["train", "test"]


def test_builder_rejects_unknown_attack_profile(tmp_path: Path) -> None:
    source = _source_bundle(tmp_path)

    with pytest.raises(ValueError, match="Unknown dev-tuning attack profile"):
        build_dev_tuning_bundle(
            source,
            output_config=tmp_path / "run" / "dev_tuning.yaml",
            output_manifest=tmp_path / "run" / "synthetic_dev_117.jsonl",
            attack_profile="formal-test",
        )


def test_run_script_forwards_fail_closed_attack_profile() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (
        project_root / "scripts/server/run_image_watermark_dev_tuning.sh"
    ).read_text(encoding="utf-8")

    assert (
        'DEV_TUNING_ATTACK_PROFILE="${DEV_TUNING_ATTACK_PROFILE:-baseline}"' in script
    )
    assert '--attack-profile "${DEV_TUNING_ATTACK_PROFILE}"' in script
    assert "selection-grid)" in script
    assert "DEV_TUNING_SOURCE_CONFIG:-" in script
    assert "DEV_TUNING_EXPECTED_ROWS=819" in script


def test_builder_rejects_too_few_dev_samples(tmp_path: Path) -> None:
    source = _source_bundle(tmp_path, dev_samples=116)

    with pytest.raises(ValueError, match="Expected at least 117"):
        build_dev_tuning_bundle(
            source,
            output_config=tmp_path / "run" / "dev_tuning.yaml",
            output_manifest=tmp_path / "run" / "synthetic_dev_117.jsonl",
        )


def test_builder_deterministically_subsets_an_expanded_dev_split(tmp_path: Path) -> None:
    source = _source_bundle(tmp_path, dev_samples=122)

    first_config, first_rows = build_dev_tuning_bundle(
        source,
        output_config=tmp_path / "first" / "dev_tuning.yaml",
        output_manifest=tmp_path / "first" / "synthetic_dev_117.jsonl",
    )
    second_config, second_rows = build_dev_tuning_bundle(
        source,
        output_config=tmp_path / "second" / "dev_tuning.yaml",
        output_manifest=tmp_path / "second" / "synthetic_dev_117.jsonl",
    )

    assert len(first_rows) == 117
    assert first_rows == second_rows
    assert first_config["dev_tuning"]["eligible_source_dev_samples"] == 122
    assert first_config["dev_tuning"]["selection_policy"] == (
        "sha256(seed|dev-tuning-subset-v2|sample_id), first N"
    )
    assert (
        first_config["dev_tuning"]["selected_sample_ids_sha256"]
        == second_config["dev_tuning"]["selected_sample_ids_sha256"]
    )
    assert len({row["domain"] for row in first_rows}) == len(DOMAINS)


def test_builder_rejects_non_frozen_expected_sample_override(tmp_path: Path) -> None:
    source = _source_bundle(tmp_path)

    with pytest.raises(ValueError, match="requires exactly 117"):
        build_dev_tuning_bundle(
            source,
            output_config=tmp_path / "run" / "dev_tuning.yaml",
            output_manifest=tmp_path / "run" / "synthetic_dev_117.jsonl",
            expected_samples=8,
        )


def test_manifest_serialization_is_deterministic(tmp_path: Path) -> None:
    source = _source_bundle(tmp_path)
    config, rows = build_dev_tuning_bundle(
        source,
        output_config=tmp_path / "run" / "dev_tuning.yaml",
        output_manifest=tmp_path / "run" / "synthetic_dev_117.jsonl",
    )

    serialized = manifest_text(rows)
    assert (
        hashlib_sha256(serialized) == config["dev_tuning"]["selected_manifest_sha256"]
    )
    parsed = [json.loads(line) for line in serialized.splitlines()]
    assert [row["sample_id"] for row in parsed] == sorted(
        row["sample_id"] for row in parsed
    )


def test_preflight_applies_minimum_to_configured_dev_split(tmp_path: Path) -> None:
    source = _source_bundle(tmp_path)
    output_config = tmp_path / "run" / "dev_tuning.yaml"
    output_manifest = tmp_path / "run" / "synthetic_dev_117.jsonl"
    config, rows = build_dev_tuning_bundle(
        source,
        output_config=output_config,
        output_manifest=output_manifest,
    )
    output_config.parent.mkdir(parents=True)
    output_manifest.write_text(manifest_text(rows), encoding="utf-8")
    output_config.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    args = preflight.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "--benchmark-config",
            str(output_config),
            "--min-dataset-samples",
            "117",
            "--min-test-samples",
            "117",
            "--min-source-datasets",
            "1",
            "--min-content-domains",
            "9",
        ]
    )
    report = preflight.CheckReport()

    preflight.check_dataset(args, tmp_path, None, report)

    manifest_check = next(
        row for row in report.checks if row["name"] == "dataset.manifest"
    )
    assert manifest_check["status"] == "pass"
    assert manifest_check["details"]["benchmark_split"] == "dev"
    assert manifest_check["details"]["split_counts"] == {"dev": 117}
    assert manifest_check["details"]["unique_sha256_count"] == 117
    assert manifest_check["details"]["duplicate_sha256_content_rows"] == 0


def test_preflight_rejects_duplicate_content_sha256(tmp_path: Path) -> None:
    source = _source_bundle(tmp_path)
    output_config = tmp_path / "run" / "dev_tuning.yaml"
    output_manifest = tmp_path / "run" / "synthetic_dev_117.jsonl"
    config, rows = build_dev_tuning_bundle(
        source,
        output_config=output_config,
        output_manifest=output_manifest,
    )
    rows[1]["sha256"] = rows[0]["sha256"]
    output_config.parent.mkdir(parents=True)
    output_manifest.write_text(manifest_text(rows), encoding="utf-8")
    output_config.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    args = preflight.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "--benchmark-config",
            str(output_config),
            "--min-dataset-samples",
            "117",
            "--min-test-samples",
            "117",
            "--min-source-datasets",
            "1",
            "--min-content-domains",
            "9",
        ]
    )
    report = preflight.CheckReport()

    preflight.check_dataset(args, tmp_path, None, report)

    manifest_check = next(
        row for row in report.checks if row["name"] == "dataset.manifest"
    )
    assert manifest_check["status"] == "error"
    assert manifest_check["details"]["duplicate_sha256_content_rows"] == 1
    assert any(
        "duplicate SHA-256 content rows: 1" in message
        for message in manifest_check["details"]["errors"]
    )


def test_next_round_candidate_matrix_is_disabled_and_dev_only() -> None:
    project_root = Path(__file__).resolve().parents[2]
    payload = yaml.safe_load(
        (
            project_root
            / 'protection' / 'image_watermark'
            / "configs"
            / "image_watermark_dev_tuning_candidates.yaml"
        ).read_text(encoding="utf-8")
    )

    assert payload["run_class"] == "dev_tuning_candidates_not_executed"
    assert payload["enabled"] is False
    assert payload["selection_split"] == "dev"
    assert "golden_test" in payload["forbidden_inputs"]
    assert payload["baseline"] == {
        "decoder_mode": "identity_single_view",
        "registry_hamming_radius": 1,
    }
    assert all(candidate["enabled"] is False for candidate in payload["candidates"])
    assert {
        candidate["registry_hamming_radius"] for candidate in payload["candidates"]
    } == {1, 2, 3, 4}


def hashlib_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
