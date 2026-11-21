from __future__ import annotations

import hashlib
import importlib.metadata
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml
from PIL import Image

from scripts.server import analyze_image_watermark_threshold_calibration as threshold_analyzer
from protection.supporting.image_watermark.experiments.attacks import (
    AttackSpec,
    apply_traditional_attack,
    truth_mask_from_half_open_bbox,
)
from protection.supporting.image_watermark.experiments.manifest import (
    ImageSample,
    dataset_roots_from_config,
    deterministic_split,
    load_manifest,
    manifest_lock_path,
    validate_manifest_lock,
    write_manifest,
)
from protection.supporting.image_watermark.experiments.metrics import mask_metrics
from protection.supporting.image_watermark.experiments.paper_benchmark import (
    SOURCE_TREE_IDENTITY_VERSION,
    PaperBenchmarkRunner,
    _source_tree_identity_scope,
)
from scripts.server.analyze_image_watermark_threshold_calibration import (
    RAW_LOCALIZATION_VOTE_ENCODING,
    RAW_LOCALIZATION_VOTE_FILENAME,
    ThresholdCalibrationError,
    _independently_validate_candidate_artifacts,
    _validate_current_attack_runtime,
    analyze_threshold_calibration,
)
from scripts.server.build_image_watermark_threshold_calibration import (
    ATTACK_ARTIFACT_RETENTION,
    EVALUATION_SEEDS,
    EXPECTED_SAMPLES,
    FIXED_PARAMETERS,
    FROZEN_THRESHOLDS,
    LOCALIZATION_MASK_CONTRACT,
    REQUIRED_ATTACK_RUNTIME,
    RUN_CLASS,
    SUBSET_POLICY,
    build_threshold_calibration_bundle,
    candidate_id,
    main as build_threshold_calibration_main,
    normalize_thresholds,
    sha256_file,
)
from scripts.server.image_watermark_preregistration import (
    copy_preregistration_claim_to_run,
    write_preregistration_claim,
)


DATASET_NAMES = ("synthetic_v2", "open_images", "nasa", "met")
SPLIT_SEED = 20260802
TRAIN_RATIO = 0.70
DEV_RATIO = 0.10
TEST_BASE_URL = "http://127.0.0.1:18010"
_RAW_VOTE_PNG_CACHE: dict[tuple[tuple[int, int], bytes], bytes] = {}
PRODUCTION_EXPECTED_SERVICE_IMAGE_SHAPE = (
    threshold_analyzer.EXPECTED_SERVICE_IMAGE_SHAPE
)


@pytest.fixture(autouse=True)
def _frozen_analyzer_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    real_version = importlib.metadata.version

    def frozen_version(distribution: str) -> str:
        if distribution in REQUIRED_ATTACK_RUNTIME:
            return REQUIRED_ATTACK_RUNTIME[distribution]
        return real_version(distribution)

    monkeypatch.setattr(importlib.metadata, "version", frozen_version)
    # Full 12,636-artifact fixtures use 8x8 masks to keep the unit suite bounded;
    # production analysis remains frozen to 512x512 and is asserted separately.
    monkeypatch.setattr(threshold_analyzer, "EXPECTED_SERVICE_IMAGE_SHAPE", (8, 8))


def test_production_service_shape_is_frozen_to_512_square() -> None:
    assert PRODUCTION_EXPECTED_SERVICE_IMAGE_SHAPE == (512, 512)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _directory_symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Directory symlinks are unavailable for this test: {exc}")


def _write_raw_localization_votes(
    path: Path,
    predicted: Image.Image,
    *,
    localization_channel_vote_min: int = 1,
) -> dict[str, Any]:
    predicted_array = np.asarray(predicted.convert("L"), dtype=np.uint8) >= 128
    raw_votes = np.zeros(predicted_array.shape, dtype=np.uint16)
    foreground = np.argwhere(predicted_array)
    eligible_values = [
        value
        for value in (255, 510, 765)
        if value >= 255 * localization_channel_vote_min
    ]
    for index, (y, x) in enumerate(foreground):
        raw_votes[int(y), int(x)] = eligible_values[index % len(eligible_values)]
    path.parent.mkdir(parents=True, exist_ok=True)
    cache_key = (raw_votes.shape, raw_votes.tobytes())
    encoded = _RAW_VOTE_PNG_CACHE.get(cache_key)
    if encoded is None:
        buffer = io.BytesIO()
        image = Image.fromarray(raw_votes)
        assert image.mode == "I;16"
        image.save(buffer, format="PNG", compress_level=6)
        encoded = buffer.getvalue()
        _RAW_VOTE_PNG_CACHE[cache_key] = encoded
    path.write_bytes(encoded)
    histogram = {
        str(value): int(np.count_nonzero(raw_votes == value))
        for value in (0, 255, 510, 765)
    }
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "dtype": "uint16",
        "shape": [int(raw_votes.shape[0]), int(raw_votes.shape[1])],
        "encoding": RAW_LOCALIZATION_VOTE_ENCODING,
        "histogram": histogram,
    }


def _rewrite_locked_manifest(
    config_path: Path,
    manifest_path: Path,
    rows: list[dict[str, Any]] | list[ImageSample],
) -> None:
    manifest_path.unlink()
    manifest_lock_path(manifest_path).unlink()
    write_manifest(
        [
            row if isinstance(row, ImageSample) else ImageSample.from_dict(row)
            for row in rows
        ],
        manifest_path,
        environ={},
        config_path=config_path,
        upstream_dataset_locks={},
    )


def _source_family_for_split(
    dataset_name: str, local_index: int, target_split: str
) -> str:
    for nonce in range(100_000):
        family = f"family:{dataset_name}:{local_index}:{target_split}:{nonce}"
        if (
            deterministic_split(
                family,
                seed=SPLIT_SEED,
                train_ratio=TRAIN_RATIO,
                dev_ratio=DEV_RATIO,
            )
            == target_split
        ):
            return family
    raise AssertionError(f"Unable to construct deterministic {target_split} family")


def _formal_fixture(tmp_path: Path) -> tuple[Path, Path, list[ImageSample]]:
    rows: list[ImageSample] = []
    index = 0
    roots: dict[str, Path] = {}
    for dataset_index, dataset_name in enumerate(DATASET_NAMES):
        root = tmp_path / "datasets" / dataset_name
        roots[dataset_name] = root
        (root / "images").mkdir(parents=True)
        splits = ["dev"] * 31 + ["train", "test"]
        for local_index, split in enumerate(splits):
            image_path = root / "images" / f"image_{local_index:03d}.png"
            image = Image.new(
                "RGB",
                (8, 8),
                (
                    index % 256,
                    (index * 17 + dataset_index) % 256,
                    (index * 53 + local_index) % 256,
                ),
            )
            image.putpixel((index % 8, (index // 8) % 8), (255, index % 256, 0))
            image.save(image_path)
            rows.append(
                ImageSample(
                    sample_id=f"{dataset_name}_{local_index:03d}",
                    relative_path=f"images/{image_path.name}",
                    split=split,
                    source_dataset=dataset_name,
                    domain=f"domain_{index % 6}",
                    license_id="CC0-1.0",
                    license_url="https://creativecommons.org/publicdomain/zero/1.0/",
                    provenance=f"test:{dataset_name}:{local_index}",
                    source_family=_source_family_for_split(
                        dataset_name, local_index, split
                    ),
                    sha256=sha256_file(image_path),
                    width=8,
                    height=8,
                )
            )
            index += 1

    manifest_path = tmp_path / "paper_formal_132_v2.jsonl"
    config = {
        "experiment": {
            "name": "formal_v2_fixture",
            "strict_paper_mode": True,
            "fail_fast": True,
            "split": "test",
            "seeds": [20260802, 20260803, 20260804],
            "api_timeout_seconds": 900,
            "traditional_attack_artifact_retention": ATTACK_ARTIFACT_RETENTION,
            "required_attack_runtime": dict(REQUIRED_ATTACK_RUNTIME),
        },
        "split": {
            "seed": SPLIT_SEED,
            "train_ratio": TRAIN_RATIO,
            "dev_ratio": DEV_RATIO,
        },
        "manifest": {
            "path": str(manifest_path),
            "verify_hashes": True,
            "require_lock": True,
        },
        "data_requirements": {
            "expected_total_samples": len(rows),
            "minimum_test_samples": 4,
            "minimum_datasets": 4,
            "minimum_domains": 4,
        },
        "metrics": {
            "require_reference_ssim": True,
            "lpips": {"enabled": True, "required": True},
        },
        "datasets": [
            {
                "name": name,
                "enabled": True,
                "root": str(roots[name]),
                "required_samples": 33,
                "max_samples": 33,
            }
            for name in DATASET_NAMES
        ],
        "methods": [
            {
                "id": "editguard_wrapper",
                "kind": "sce_locguard_api",
                "base_url": "http://127.0.0.1:8010",
                "enabled": True,
            }
        ],
        "attacks": {
            "traditional": [
                {"name": "clean", "family": "clean"},
                {
                    "name": "erasing",
                    "family": "removal",
                    "grid": [
                        {"area_ratio": 0.05},
                        {"area_ratio": 0.15},
                        {"area_ratio": 0.25},
                    ],
                },
            ],
            "aigc": {"enabled": True, "specs": [{"name": "inpaint"}]},
        },
    }
    config_path = tmp_path / "paper_benchmark.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    write_manifest(
        rows,
        manifest_path,
        environ={},
        config_path=config_path,
        upstream_dataset_locks={},
    )
    return config_path, manifest_path, rows


def _build_bundle(
    tmp_path: Path,
) -> tuple[Path, Path, dict[str, Any], list[ImageSample]]:
    formal_config, _, _ = _formal_fixture(tmp_path)
    config_path = tmp_path / "calibration" / "threshold_calibration.yaml"
    manifest_path = tmp_path / "calibration" / "threshold_calibration_dev_117.jsonl"
    config, selected = build_threshold_calibration_bundle(
        formal_config,
        output_config=config_path,
        output_manifest=manifest_path,
        base_url=TEST_BASE_URL,
    )
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    write_manifest(
        selected,
        manifest_path,
        environ={},
        config_path=config_path,
        upstream_dataset_locks=config["threshold_calibration"][
            "source_formal_manifest_lock"
        ].get("upstream_dataset_locks")
        or {},
    )
    write_preregistration_claim(
        config_path,
        expected_run_class=RUN_CLASS,
    )
    return config_path, manifest_path, config, selected


def _fake_candidate_runs(
    run_root: Path,
    config_path: Path,
    manifest_path: Path,
    config: dict[str, Any],
    selected: list[ImageSample],
) -> None:
    sample_ids = sorted(row.sample_id for row in selected)
    selected_ids_sha256 = hashlib.sha256("\n".join(sample_ids).encode()).hexdigest()
    roots = dataset_roots_from_config(config_path, environ={})
    locked_rows = load_manifest(
        manifest_path,
        dataset_roots=roots,
        require_files=True,
        verify_hashes=True,
    )
    manifest_lock_audit = validate_manifest_lock(
        manifest_path,
        locked_rows,
        config_path=config_path,
        dataset_roots=roots,
    )
    attack_contract = config["threshold_calibration"][
        "traditional_attack_implementation"
    ]
    for candidate in config["threshold_calibration"]["candidate_runs"]:
        threshold = float(candidate["recovery_threshold"])
        run_dir = run_root / "candidate-runs" / candidate["candidate_id"]
        benchmark_dir = run_dir / "benchmark"
        benchmark_dir.mkdir(parents=True)
        preregistration_evidence = copy_preregistration_claim_to_run(
            config_path,
            source_claim_path=Path(
                config["threshold_calibration"]["preregistration_claim"][
                    "claim_path"
                ]
            ),
            destination_run=run_dir,
            expected_run_class=RUN_CLASS,
            expected_nonce=config["threshold_calibration"][
                "preregistration_claim"
            ]["nonce"],
        )
        (run_dir / "run-class.txt").write_text(RUN_CLASS + "\n", encoding="utf-8")
        _write_json(run_dir / "preflight.json", {"status": "ready"})
        capabilities = {
            "recovery_threshold": threshold,
            "tamper_area_threshold": 0.001,
            "registry_hamming_radius": 1,
            "localization_postprocessing": "none",
            "deterministic_mode_enabled": True,
            "attack_model_id": "stable-diffusion-v1-5/stable-diffusion-inpainting",
            "attack_model_revision": "1" * 40,
            **LOCALIZATION_MASK_CONTRACT,
        }
        _write_json(run_dir / "capabilities.json", capabilities)
        _write_json(
            benchmark_dir / "environment.json",
            {
                "schema_version": "cogniguard_image_benchmark_environment_v1",
                "python": "3.12-test",
                "platform": "test-platform",
                "config_path": str(config_path),
                "config_sha256": sha256_file(config_path),
                "manifest_path": str(manifest_path),
                "manifest_sha256": sha256_file(manifest_path),
                "resolved_dataset_roots": {
                    name: str(path.resolve()) for name, path in sorted(roots.items())
                },
                "strict_paper_mode": True,
                "run_class": RUN_CLASS,
                "paper_eligible": False,
                "evaluation_split": "dev",
                "dataset_manifest_override_used": False,
                "dataset_roots_override_used": False,
                "registry_secret_recorded": False,
                "methods": [{"id": "editguard_wrapper", "kind": "sce_locguard_api"}],
                "capabilities": {"editguard_wrapper": capabilities},
                "capabilities_contract": {"editguard_wrapper": capabilities},
                "packages": dict(REQUIRED_ATTACK_RUNTIME),
                "gpu": {"cuda_available": True, "devices": ["test-gpu"]},
                "checkpoints": {"clean.pth": {"sha256": "a" * 64}},
                "git_commit": "test-commit",
                "git_status_sha256": "b" * 64,
                "source_tree_sha256": "c" * 64,
                "source_tree_file_count": 42,
                "source_tree_identity_version": SOURCE_TREE_IDENTITY_VERSION,
                "source_tree_scope": _source_tree_identity_scope(),
                "input_manifest_audit": {
                    "total_samples": EXPECTED_SAMPLES,
                    "selected_samples": EXPECTED_SAMPLES,
                    "selected_split": "dev",
                    "selected_sample_ids_sha256": selected_ids_sha256,
                },
                "manifest_lock": manifest_lock_audit,
                "preregistration_claim": preregistration_evidence,
                "traditional_attack_runtime": {
                    "implementation_path": attack_contract["path"],
                    "implementation_sha256": attack_contract["sha256"],
                    "required_packages": dict(REQUIRED_ATTACK_RUNTIME),
                    "observed_packages": dict(REQUIRED_ATTACK_RUNTIME),
                    "artifact_retention": ATTACK_ARTIFACT_RETENTION,
                },
                "deterministic_runtime_identity": {"fixture": "deterministic-v1"},
                "asset_manifest_identity": {"fixture": "assets-v1"},
                "aigc_attack_runtime_identity": {"fixture": "aigc-v1"},
                "registry_secret_identity_fingerprint": "9" * 64,
            },
        )
        result_rows: list[dict[str, Any]] = []
        for sample in selected:
            for seed in EVALUATION_SEEDS:
                embed_key = hashlib.sha256(
                    f"{candidate['candidate_id']}|{sample.sample_id}|{seed}|embed".encode()
                ).hexdigest()[:16]
                watermarked_path = (
                    benchmark_dir
                    / "api_jobs"
                    / "editguard_wrapper"
                    / f"embed_{embed_key}"
                    / "embed"
                    / "watermarked.png"
                )
                watermarked_path.parent.mkdir(parents=True, exist_ok=True)
                with Image.open(sample.image_path) as source_image:
                    watermarked = source_image.convert("RGB").copy()
                watermarked.save(watermarked_path)

                for attack_id in (
                    "clean",
                    "erasing__area_ratio-0.05",
                    "erasing__area_ratio-0.15",
                    "erasing__area_ratio-0.25",
                ):
                    is_clean = attack_id == "clean"
                    if is_clean:
                        attacked_sha256 = sha256_file(watermarked_path)
                        attacked_size_bytes = watermarked_path.stat().st_size
                        truth = Image.new("L", watermarked.size, 0)
                        attack_params: dict[str, float] = {}
                        truth_bbox = None
                    else:
                        ratio = float(attack_id.rsplit("-", 1)[1])
                        attack_params = {"area_ratio": ratio}
                        attacked, attack_metadata = apply_traditional_attack(
                            watermarked,
                            AttackSpec(
                                name="erasing",
                                family="removal",
                                params={
                                    "area_ratio": ratio,
                                    "expanded_name": attack_id,
                                },
                            ),
                            seed=seed,
                        )
                        buffer = io.BytesIO()
                        attacked.save(buffer, format="PNG")
                        attacked_bytes = buffer.getvalue()
                        attacked_sha256 = hashlib.sha256(attacked_bytes).hexdigest()
                        attacked_size_bytes = len(attacked_bytes)
                        truth_bbox = attack_metadata["truth_bbox"]
                        truth = truth_mask_from_half_open_bbox(
                            watermarked.size, truth_bbox
                        )

                    if is_clean:
                        predicted = Image.new("L", watermarked.size, 0)
                        if threshold < 0.24:
                            predicted.putpixel((0, 0), 255)
                    elif threshold < 0.28:
                        predicted = Image.new("L", watermarked.size, 0)
                    else:
                        predicted = truth.copy()
                    verify_key = hashlib.sha256(
                        (
                            f"{candidate['candidate_id']}|{sample.sample_id}|"
                            f"{seed}|{attack_id}|verify"
                        ).encode()
                    ).hexdigest()[:20]
                    verify_job_id = f"verify_{verify_key}"
                    predicted_path = (
                        benchmark_dir
                        / "api_jobs"
                        / verify_job_id
                        / "verify"
                        / "predicted_mask.png"
                    )
                    predicted_path.parent.mkdir(parents=True, exist_ok=True)
                    predicted.save(predicted_path)
                    raw_vote_artifact = _write_raw_localization_votes(
                        predicted_path.with_name(RAW_LOCALIZATION_VOTE_FILENAME),
                        predicted,
                        localization_channel_vote_min=1,
                    )
                    predicted_area_ratio = float(
                        (np.asarray(predicted, dtype=np.uint8) >= 128).mean()
                    )
                    attack_regime = (
                        "global_rerendering_or_watermark_laundering"
                        if predicted_area_ratio > 0.80
                        else (
                            "localized_tamper_candidate"
                            if predicted_area_ratio > 0.001
                            else "no_tamper_detected"
                        )
                    )
                    input_reference = {
                        "suffix": ".png",
                        "size_bytes": attacked_size_bytes,
                        "sha256": attacked_sha256,
                    }
                    verify_report_path = predicted_path.with_name(
                        "verify_report.json"
                    )
                    _write_json(
                        verify_report_path,
                        {
                            "job_id": verify_job_id,
                            "job_type": "verify",
                            "request": {
                                "image_reference": input_reference,
                                "seed": seed,
                                "strict": True,
                                "return_overlay": False,
                                "return_recovered_bits": True,
                            },
                            "input_image": input_reference,
                            "recovery_threshold": threshold,
                            "tamper_area_threshold": 0.001,
                            "localization_postprocessing": "none",
                            **LOCALIZATION_MASK_CONTRACT,
                            "resolved_raw_vote_threshold": 255,
                            "predicted_mask_area_ratio": predicted_area_ratio,
                            "raw_localization_votes_artifact": raw_vote_artifact,
                            "response": {
                                "job_id": verify_job_id,
                                "status": "ok",
                                "implementation_level": "real_pipeline",
                                "predicted_mask_path": str(predicted_path.resolve()),
                                "report_json_path": str(verify_report_path.resolve()),
                                "recovery_threshold": threshold,
                                "tamper_area_threshold": 0.001,
                                **LOCALIZATION_MASK_CONTRACT,
                                "predicted_mask_area_ratio": predicted_area_ratio,
                                "attack_regime": attack_regime,
                                "raw_localization_votes_path": raw_vote_artifact[
                                    "path"
                                ],
                                "raw_localization_votes_sha256": raw_vote_artifact[
                                    "sha256"
                                ],
                                "raw_localization_votes_histogram": raw_vote_artifact[
                                    "histogram"
                                ],
                                "raw_localization_votes_dtype": raw_vote_artifact[
                                    "dtype"
                                ],
                                "raw_localization_votes_shape": raw_vote_artifact[
                                    "shape"
                                ],
                                "raw_localization_votes_encoding": raw_vote_artifact[
                                    "encoding"
                                ],
                                "seed": seed,
                            },
                        },
                    )
                    scores = mask_metrics(predicted, truth)
                    predicted_array = np.asarray(predicted, dtype=np.uint8) >= 128
                    result = {
                        "row_key": (
                            f"editguard_wrapper|{sample.sample_id}|{seed}|{attack_id}"
                        ),
                        "sample_id": sample.sample_id,
                        "image_sha256": sample.sha256,
                        "source_dataset": sample.source_dataset,
                        "status": "ok",
                        "pipeline_success": 1.0,
                        "implementation_level": "real_pipeline",
                        "method_id": "editguard_wrapper",
                        "run_class": RUN_CLASS,
                        "paper_eligible": False,
                        "split": "dev",
                        "seed": seed,
                        "verify_job_id": verify_job_id,
                        "attack_id": attack_id,
                        "attack_params": attack_params,
                        "attack_truth_bbox": truth_bbox,
                        "traditional_attack_artifact_retention": (
                            ATTACK_ARTIFACT_RETENTION
                        ),
                        "attacked_image_sha256": attacked_sha256,
                        "attacked_image_retained": is_clean,
                        "attacked_image_path": (
                            str(watermarked_path.resolve()) if is_clean else None
                        ),
                        "mask_fpr": scores["fpr"],
                        "predicted_mask_nonempty": float(predicted_array.any()),
                        "image_tamper_detected": float(
                            predicted_area_ratio > 0.001
                        ),
                        "predicted_tamper_area_ratio": float(predicted_array.mean()),
                        "source_registry_match": 1.0,
                    }
                    if not is_clean:
                        result.update(
                            {
                                "mask_iou": scores["iou"],
                                "mask_dice": scores["dice"],
                                "mask_precision": scores["precision"],
                                "mask_recall": scores["recall"],
                            }
                        )
                    result_rows.append(result)
        _write_jsonl(benchmark_dir / "raw_results.jsonl", result_rows)


def test_builder_selects_exact_deterministic_dev_subset_and_copies_runtime(
    tmp_path: Path,
) -> None:
    formal_config, formal_manifest, formal_rows = _formal_fixture(tmp_path)
    formal_sha256 = sha256_file(formal_config)
    kwargs = {
        "output_config": tmp_path / "first.yaml",
        "output_manifest": tmp_path / "first.jsonl",
        "base_url": TEST_BASE_URL,
    }
    first_config, first_rows = build_threshold_calibration_bundle(
        formal_config, **kwargs
    )
    second_config, second_rows = build_threshold_calibration_bundle(
        formal_config,
        output_config=tmp_path / "second.yaml",
        output_manifest=tmp_path / "second.jsonl",
        base_url=TEST_BASE_URL,
    )

    assert len(first_rows) == EXPECTED_SAMPLES
    assert {row.split for row in first_rows} == {"dev"}
    assert len({row.sha256 for row in first_rows}) == EXPECTED_SAMPLES
    assert len({row.source_family for row in first_rows}) == EXPECTED_SAMPLES
    assert {row.source_dataset for row in first_rows} == set(DATASET_NAMES)
    assert [row.sample_id for row in first_rows] == [
        row.sample_id for row in second_rows
    ]
    assert first_config["threshold_calibration"]["candidate_thresholds"] == list(
        FROZEN_THRESHOLDS
    )
    assert first_config["experiment"]["seeds"] == list(EVALUATION_SEEDS)
    assert first_config["threshold_calibration"]["evaluation_seeds"] == list(
        EVALUATION_SEEDS
    )
    assert first_config["threshold_calibration"]["expected_rows_per_candidate"] == (
        EXPECTED_SAMPLES * 4 * len(EVALUATION_SEEDS)
    )
    assert (
        first_config["threshold_calibration"]["fixed_parameters"]
        == FIXED_PARAMETERS
    )
    split_audit = first_config["threshold_calibration"]["formal_split_assignment_audit"]
    assert split_audit["rows"] == 132
    assert split_audit["split_counts"] == {"dev": 124, "test": 4, "train": 4}
    assert (
        first_config["experiment"]["traditional_attack_artifact_retention"]
        == ATTACK_ARTIFACT_RETENTION
    )
    assert (
        first_config["experiment"]["required_attack_runtime"] == REQUIRED_ATTACK_RUNTIME
    )
    assert (
        first_config["threshold_calibration"]["required_attack_runtime"]
        == REQUIRED_ATTACK_RUNTIME
    )
    attack_implementation = first_config["threshold_calibration"][
        "traditional_attack_implementation"
    ]
    assert (
        sha256_file(Path(attack_implementation["path"]))
        == attack_implementation["sha256"]
    )
    assert first_config["data_requirements"]["expected_total_samples"] == 117
    assert (
        sum(dataset["required_samples"] for dataset in first_config["datasets"]) == 117
    )
    assert first_config["attacks"]["aigc"]["enabled"] is False
    assert first_config["methods"] == [
        {
            "id": "editguard_wrapper",
            "kind": "sce_locguard_api",
            "base_url": TEST_BASE_URL,
            "enabled": True,
            "required_capabilities": FIXED_PARAMETERS,
        }
    ]
    assert first_config["threshold_calibration"]["selection_policy"] == SUBSET_POLICY
    assert "threshold-calibration-v2-family-representative" in SUBSET_POLICY
    assert "threshold-calibration-v2-subset" in SUBSET_POLICY
    assert first_config["manifest"]["require_lock"] is True
    formal_roots = dataset_roots_from_config(formal_config, environ={})
    expected_formal_lock = validate_manifest_lock(
        formal_manifest,
        load_manifest(
            formal_manifest,
            dataset_roots=formal_roots,
            require_files=True,
            verify_hashes=True,
        ),
        config_path=formal_config,
        dataset_roots=formal_roots,
    )
    assert (
        first_config["threshold_calibration"]["source_formal_manifest_lock"]
        == expected_formal_lock
    )
    assert len(formal_rows) == 132
    assert sha256_file(formal_config) == formal_sha256
    assert (
        first_config["threshold_calibration"]["formal_config_update_performed"] is False
    )
    assert (
        second_config["threshold_calibration"]["selected_sample_ids_sha256"]
        == (first_config["threshold_calibration"]["selected_sample_ids_sha256"])
    )


def test_builder_rejects_missing_candidate_and_runtime_drift(tmp_path: Path) -> None:
    formal_config, _, _ = _formal_fixture(tmp_path)
    with pytest.raises(ValueError, match="exactly equal"):
        normalize_thresholds(FROZEN_THRESHOLDS[:-1])
    with pytest.raises(ValueError, match="exactly equal"):
        normalize_thresholds((*FROZEN_THRESHOLDS, 0.38))

    payload = yaml.safe_load(formal_config.read_text(encoding="utf-8"))
    payload["experiment"]["required_attack_runtime"]["Pillow"] = "0.0-wrong"
    formal_config.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="required_attack_runtime"):
        build_threshold_calibration_bundle(
            formal_config,
            output_config=tmp_path / "calibration.yaml",
            output_manifest=tmp_path / "calibration.jsonl",
            base_url=TEST_BASE_URL,
        )


def test_builder_rejects_output_collision_and_invalid_api_origin(
    tmp_path: Path,
) -> None:
    missing_source = tmp_path / "unused-source.yaml"
    shared_output = tmp_path / "same-output"
    with pytest.raises(ValueError, match="must be different paths"):
        build_threshold_calibration_bundle(
            missing_source,
            output_config=shared_output,
            output_manifest=shared_output,
            base_url=TEST_BASE_URL,
        )
    with pytest.raises(ValueError, match=r"absolute http\(s\) origin"):
        build_threshold_calibration_bundle(
            missing_source,
            output_config=tmp_path / "calibration.yaml",
            output_manifest=tmp_path / "calibration.jsonl",
            base_url="http://127.0.0.1:18010/api",
        )


def test_builder_ignores_generic_manifest_and_root_environment_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    formal_config, formal_manifest, _ = _formal_fixture(tmp_path)
    monkeypatch.setenv(
        "COGNIGUARD_WATERMARK_DATASET_MANIFEST", str(tmp_path / "wrong.jsonl")
    )
    monkeypatch.setenv(
        "COGNIGUARD_DATASET_ROOTS_JSON", json.dumps({"synthetic_v2": "wrong"})
    )

    config, _ = build_threshold_calibration_bundle(
        formal_config,
        output_config=tmp_path / "calibration.yaml",
        output_manifest=tmp_path / "calibration.jsonl",
        base_url=TEST_BASE_URL,
    )

    assert config["threshold_calibration"]["source_formal_manifest"] == str(
        formal_manifest.resolve()
    )


def test_builder_fails_closed_on_hash_and_source_family(tmp_path: Path) -> None:
    formal_config, manifest_path, rows = _formal_fixture(tmp_path)
    first_image = tmp_path / "datasets" / rows[0].source_dataset / rows[0].relative_path
    first_image.write_bytes(first_image.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="sha256 mismatch"):
        build_threshold_calibration_bundle(
            formal_config,
            output_config=tmp_path / "hash.yaml",
            output_manifest=tmp_path / "hash.jsonl",
            base_url=TEST_BASE_URL,
        )

    formal_config, manifest_path, _ = _formal_fixture(tmp_path / "family_case")
    manifest_rows = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
    ]
    shared_dev_family = _source_family_for_split("shared", 0, "dev")
    for row in manifest_rows:
        if row["split"] == "dev":
            row["source_family"] = shared_dev_family
    _rewrite_locked_manifest(formal_config, manifest_path, manifest_rows)
    with pytest.raises(ValueError, match="independent source families"):
        build_threshold_calibration_bundle(
            formal_config,
            output_config=tmp_path / "family.yaml",
            output_manifest=tmp_path / "family.jsonl",
            base_url=TEST_BASE_URL,
        )


def test_builder_rejects_tampered_source_formal_manifest_lock(tmp_path: Path) -> None:
    formal_config, manifest_path, _ = _formal_fixture(tmp_path)
    lock_path = manifest_lock_path(manifest_path)
    lock_payload = json.loads(lock_path.read_text(encoding="utf-8"))
    lock_payload["manifest_sha256"] = "0" * 64
    _write_json(lock_path, lock_payload)

    with pytest.raises(ValueError, match="Manifest lock evidence mismatch"):
        build_threshold_calibration_bundle(
            formal_config,
            output_config=tmp_path / "calibration.yaml",
            output_manifest=tmp_path / "calibration.jsonl",
            base_url=TEST_BASE_URL,
        )


def test_builder_main_writes_config_then_bound_manifest_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    formal_config, _, _ = _formal_fixture(tmp_path)
    config_path = tmp_path / "created" / "threshold_calibration.yaml"
    manifest_path = tmp_path / "created" / "threshold_calibration_dev_117.jsonl"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_image_watermark_threshold_calibration.py",
            "--source",
            str(formal_config),
            "--output",
            str(config_path),
            "--manifest-output",
            str(manifest_path),
            "--base-url",
            TEST_BASE_URL,
        ],
    )

    assert build_threshold_calibration_main() == 0
    created = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert created["manifest"]["require_lock"] is True
    preregistration = created["threshold_calibration"]["preregistration_claim"]
    assert len(preregistration["nonce"]) == 64
    assert Path(preregistration["claim_path"]).is_file()
    assert not (config_path.parent / "candidate-runs").exists()
    roots = dataset_roots_from_config(config_path, environ={})
    rows = load_manifest(
        manifest_path,
        dataset_roots=roots,
        require_files=True,
        verify_hashes=True,
    )
    lock_audit = validate_manifest_lock(
        manifest_path,
        rows,
        config_path=config_path,
        dataset_roots=roots,
    )
    assert lock_audit["config_sha256"] == sha256_file(config_path)
    assert (
        lock_audit["upstream_dataset_locks"]
        == created["threshold_calibration"]["source_formal_manifest_lock"][
            "upstream_dataset_locks"
        ]
    )


def test_analyzer_rejects_current_attack_runtime_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        importlib.metadata,
        "version",
        lambda distribution: (
            "0.0-wrong"
            if distribution == "numpy"
            else REQUIRED_ATTACK_RUNTIME[distribution]
        ),
    )
    with pytest.raises(ThresholdCalibrationError, match="runtime is not frozen"):
        _validate_current_attack_runtime(dict(REQUIRED_ATTACK_RUNTIME))


def test_analyzer_requires_the_committed_source_preregistration_claim(
    tmp_path: Path,
) -> None:
    config_path, _, config, _ = _build_bundle(tmp_path)
    claim_path = Path(
        config["threshold_calibration"]["preregistration_claim"]["claim_path"]
    )
    claim_path.unlink()

    with pytest.raises(
        ThresholdCalibrationError,
        match="source preregistration claim is invalid",
    ):
        analyze_threshold_calibration(config_path, run_root=config_path.parent)


@pytest.mark.parametrize(
    ("field", "observed", "expected"),
    [
        ("recovery_threshold", 1, 1.0),
        ("tamper_area_threshold", True, 0.001),
        ("registry_hamming_radius", 1.0, 1),
    ],
)
def test_threshold_capability_gate_rejects_scalar_type_coercion(
    field: str, observed: Any, expected: Any
) -> None:
    with pytest.raises(ThresholdCalibrationError, match="wrong type/value"):
        threshold_analyzer._assert_exact_capability(
            {field: observed}, field, expected, label="fixture"
        )


def test_independent_raw_vote_replay_accepts_parameterized_k2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(threshold_analyzer, "EXPECTED_ATTACK_IDS", ("clean",))
    shared_calls: list[dict[str, Any]] = []
    shared_validator = threshold_analyzer.validate_verify_localization_artifacts

    def validate_with_shared_authority(**kwargs: Any):
        shared_calls.append(kwargs)
        return shared_validator(**kwargs)

    monkeypatch.setattr(
        threshold_analyzer,
        "validate_verify_localization_artifacts",
        validate_with_shared_authority,
    )
    run_dir = tmp_path / "candidate"
    benchmark_dir = run_dir / "benchmark"
    clean_path = benchmark_dir / "clean.png"
    clean_path.parent.mkdir(parents=True)
    watermarked = Image.new("RGB", (8, 8), "white")
    watermarked.save(clean_path)
    clean_sha256 = sha256_file(clean_path)
    seed = 7
    verify_job_id = "verify_k2_contract"
    verify_dir = benchmark_dir / "api_jobs" / verify_job_id / "verify"
    verify_dir.mkdir(parents=True)
    predicted = Image.new("L", watermarked.size, 0)
    predicted_path = verify_dir / "predicted_mask.png"
    predicted.save(predicted_path)

    raw_votes = np.zeros((8, 8), dtype=np.uint16)
    raw_votes[0, 0] = 255
    raw_path = verify_dir / RAW_LOCALIZATION_VOTE_FILENAME
    Image.fromarray(raw_votes).save(raw_path, format="PNG", compress_level=6)
    histogram = {
        str(value): int(np.count_nonzero(raw_votes == value))
        for value in (0, 255, 510, 765)
    }
    artifact = {
        "path": str(raw_path.resolve()),
        "sha256": sha256_file(raw_path),
        "dtype": "uint16",
        "shape": [8, 8],
        "encoding": RAW_LOCALIZATION_VOTE_ENCODING,
        "histogram": histogram,
    }
    contract = dict(LOCALIZATION_MASK_CONTRACT)
    contract["localization_channel_vote_min"] = 2
    input_reference = {
        "suffix": ".png",
        "size_bytes": clean_path.stat().st_size,
        "sha256": clean_sha256,
    }
    verify_report_path = verify_dir / "verify_report.json"
    _write_json(
        verify_report_path,
        {
            "job_id": verify_job_id,
            "job_type": "verify",
            "request": {
                "image_reference": input_reference,
                "seed": seed,
                "strict": True,
                "return_overlay": False,
                "return_recovered_bits": True,
            },
            "input_image": input_reference,
            "recovery_threshold": 0.28,
            "tamper_area_threshold": 0.001,
            "localization_postprocessing": "none",
            **contract,
            "resolved_raw_vote_threshold": 510,
            "predicted_mask_area_ratio": 0.0,
            "raw_localization_votes_artifact": artifact,
            "response": {
                "job_id": verify_job_id,
                "status": "ok",
                "implementation_level": "real_pipeline",
                "predicted_mask_path": str(predicted_path.resolve()),
                "report_json_path": str(verify_report_path.resolve()),
                "recovery_threshold": 0.28,
                "tamper_area_threshold": 0.001,
                **contract,
                "predicted_mask_area_ratio": 0.0,
                "attack_regime": "no_tamper_detected",
                "raw_localization_votes_path": artifact["path"],
                "raw_localization_votes_sha256": artifact["sha256"],
                "raw_localization_votes_histogram": histogram,
                "raw_localization_votes_dtype": "uint16",
                "raw_localization_votes_shape": [8, 8],
                "raw_localization_votes_encoding": RAW_LOCALIZATION_VOTE_ENCODING,
                "seed": seed,
            },
        },
    )
    row = {
        "row_key": "editguard_wrapper|sample|7|clean",
        "sample_id": "sample",
        "seed": seed,
        "attack_id": "clean",
        "verify_job_id": verify_job_id,
        "attacked_image_path": str(clean_path.resolve()),
        "attacked_image_retained": True,
        "attacked_image_sha256": clean_sha256,
        "attack_truth_bbox": None,
        "mask_fpr": 0.0,
        "predicted_tamper_area_ratio": 0.0,
        "predicted_mask_nonempty": 0.0,
        "image_tamper_detected": 0.0,
    }

    localization_evidence: dict[str, dict[str, Any]] = {}
    hashes = _independently_validate_candidate_artifacts(
        [row],
        run_dir=run_dir,
        recovery_threshold=0.28,
        localization_channel_vote_min=2,
        localization_contract=contract,
        required_image_shape=(8, 8),
        localization_evidence=localization_evidence,
    )

    assert hashes == {"sample|7|clean": clean_sha256}
    assert len(shared_calls) == 1
    assert shared_calls[0]["required_capabilities"][
        "localization_channel_vote_min"
    ] == 2
    assert localization_evidence[row["row_key"]]["raw_vote_sha256"] == artifact[
        "sha256"
    ]

    orphan = benchmark_dir / "api_jobs" / "orphan" / "raw_localization_channel_votes.extra"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"orphan")
    with pytest.raises(ThresholdCalibrationError, match="missing, extra, or alternate"):
        _independently_validate_candidate_artifacts(
            [row],
            run_dir=run_dir,
            recovery_threshold=0.28,
            localization_channel_vote_min=2,
            localization_contract=contract,
            required_image_shape=(8, 8),
            localization_evidence={},
        )


def test_builder_recomputes_every_formal_source_family_split(tmp_path: Path) -> None:
    formal_config, manifest_path, _ = _formal_fixture(tmp_path)
    manifest_rows = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
    ]
    manifest_rows[0]["split"] = "test"
    _rewrite_locked_manifest(formal_config, manifest_path, manifest_rows)

    with pytest.raises(ValueError, match="split assignments"):
        build_threshold_calibration_bundle(
            formal_config,
            output_config=tmp_path / "split.yaml",
            output_manifest=tmp_path / "split.jsonl",
            base_url=TEST_BASE_URL,
        )


def test_analyzer_reports_metrics_constraints_runtime_and_smallest_winner(
    tmp_path: Path,
) -> None:
    config_path, manifest_path, config, selected = _build_bundle(tmp_path)
    runner_output = (
        Path(config["experiment"]["output_root"])
        / candidate_id(FROZEN_THRESHOLDS[0])
        / "benchmark"
    )
    selected_by_runner, methods = PaperBenchmarkRunner(
        config_path, output_dir=runner_output
    ).validate_inputs()
    assert len(selected_by_runner) == EXPECTED_SAMPLES
    assert [method["id"] for method in methods] == ["editguard_wrapper"]
    _fake_candidate_runs(
        tmp_path / "calibration", config_path, manifest_path, config, selected
    )

    report = analyze_threshold_calibration(
        config_path, run_root=tmp_path / "calibration"
    )

    assert report["status"] == "winner_selected"
    assert report["winner"] == {
        "candidate_id": candidate_id(0.28),
        "recovery_threshold": 0.28,
        "selection_reason": (
            "smallest candidate satisfying every frozen completeness, "
            "clean-FPR, and erasing-IoU constraint"
        ),
    }
    by_threshold = {
        row["recovery_threshold"]: row for row in report["candidate_metrics"]
    }
    assert by_threshold[0.20]["all_constraints_passed"] is False
    assert by_threshold[0.22]["all_constraints_passed"] is False
    assert by_threshold[0.24]["all_constraints_passed"] is False
    assert by_threshold[0.26]["all_constraints_passed"] is False
    assert by_threshold[0.28]["all_constraints_passed"] is True
    assert by_threshold[0.30]["all_constraints_passed"] is True
    assert by_threshold[0.28]["evaluation_seeds"] == list(EVALUATION_SEEDS)
    assert by_threshold[0.28]["rows"] == EXPECTED_SAMPLES * 4 * len(EVALUATION_SEEDS)
    assert by_threshold[0.28]["immutable_environment_identity"][
        "source_tree_identity_version"
    ] == SOURCE_TREE_IDENTITY_VERSION
    assert by_threshold[0.28]["immutable_environment_identity"][
        "source_tree_scope"
    ] == _source_tree_identity_scope()
    assert len(by_threshold[0.28]["condition_metrics"]) == 4
    assert len(by_threshold[0.28]["constraint_checks"]) == 12
    localization_evidence = by_threshold[0.28]["localization_artifact_evidence"]
    assert localization_evidence["count"] == by_threshold[0.28]["rows"]
    assert len(localization_evidence["rows"]) == by_threshold[0.28]["rows"]
    assert localization_evidence["evidence_sha256"] == threshold_analyzer._canonical_sha256(
        localization_evidence["rows"]
    )
    assert (
        by_threshold[0.28]["localization_artifact_evidence_sha256"]
        == localization_evidence["evidence_sha256"]
    )
    assert (
        report["traditional_attack_runtime"]["required_packages"]
        == REQUIRED_ATTACK_RUNTIME
    )
    assert set(
        report["traditional_attack_runtime"]["observed_packages_by_candidate"]
    ) == {candidate_id(value) for value in FROZEN_THRESHOLDS}
    assert report["formal_test_rows_consumed"] == 0
    assert report["formal_config_update_performed"] is False
    assert report["cross_candidate_attack_inputs_identical"] is True
    assert report["cross_candidate_environment_identity_identical"] is True
    assert report["selected_manifest_lock"]["lock_path"] == str(
        manifest_lock_path(manifest_path)
    )
    assert (
        report["traditional_attack_runtime"]["analyzer_packages"]
        == REQUIRED_ATTACK_RUNTIME
    )
    assert report["evaluation_seeds"] == list(EVALUATION_SEEDS)

    drift_id = candidate_id(0.22)
    drift_environment_path = (
        tmp_path
        / "calibration"
        / "candidate-runs"
        / drift_id
        / "benchmark"
        / "environment.json"
    )
    drift_environment = json.loads(drift_environment_path.read_text(encoding="utf-8"))
    drift_environment["checkpoints"]["clean.pth"]["sha256"] = "d" * 64
    _write_json(drift_environment_path, drift_environment)
    with pytest.raises(
        ThresholdCalibrationError, match="immutable environment identities differ"
    ):
        analyze_threshold_calibration(config_path, run_root=tmp_path / "calibration")


def test_analyzer_rejects_non_frozen_grid_and_evaluation_seeds(tmp_path: Path) -> None:
    config_path, manifest_path, config, selected = _build_bundle(tmp_path)
    config["threshold_calibration"]["candidate_thresholds"].append(0.38)
    config["threshold_calibration"]["candidate_runs"].append(
        {"candidate_id": candidate_id(0.38), "recovery_threshold": 0.38}
    )
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    with pytest.raises(ThresholdCalibrationError, match="candidate grid"):
        analyze_threshold_calibration(config_path)

    config, _ = build_threshold_calibration_bundle(
        Path(config["threshold_calibration"]["source_formal_config"]),
        output_config=config_path,
        output_manifest=Path(config["manifest"]["path"]),
        base_url=TEST_BASE_URL,
    )
    config["experiment"]["seeds"] = list(EVALUATION_SEEDS[:-1])
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    _rewrite_locked_manifest(config_path, manifest_path, selected)
    claim_path = Path(
        config["threshold_calibration"]["preregistration_claim"]["claim_path"]
    )
    claim_path.unlink()
    write_preregistration_claim(config_path, expected_run_class=RUN_CLASS)
    with pytest.raises(
        ThresholdCalibrationError, match="three frozen evaluation seeds"
    ):
        analyze_threshold_calibration(config_path)


def test_analyzer_binds_yaml_output_root_and_candidate_containment(
    tmp_path: Path,
) -> None:
    run_root = (tmp_path / "calibration").resolve()
    candidate_runs_root = run_root / "candidate-runs"
    candidate_runs_root.mkdir(parents=True)
    payload = {"experiment": {"output_root": str(candidate_runs_root)}}

    assert (
        threshold_analyzer._validate_candidate_runs_root(
            payload, run_root=run_root
        )
        == candidate_runs_root
    )

    payload["experiment"]["output_root"] = str(tmp_path / "wrong-root")
    with pytest.raises(ThresholdCalibrationError, match="must equal"):
        threshold_analyzer._validate_candidate_runs_root(payload, run_root=run_root)

    outside = tmp_path / "outside-candidate"
    outside.mkdir()
    with pytest.raises(ThresholdCalibrationError, match="escapes"):
        threshold_analyzer._resolve_candidate_run_directory(
            run_root=run_root,
            candidate_runs_root=candidate_runs_root,
            candidate_name="../../outside-candidate",
        )


def test_analyzer_rejects_symlinked_candidate_run_directories(tmp_path: Path) -> None:
    run_root = (tmp_path / "calibration").resolve()
    run_root.mkdir()
    outside_runs = tmp_path / "outside-runs"
    outside_runs.mkdir()
    candidate_runs_root = run_root / "candidate-runs"
    _directory_symlink_or_skip(candidate_runs_root, outside_runs)
    payload = {"experiment": {"output_root": str(candidate_runs_root)}}
    with pytest.raises(ThresholdCalibrationError, match="must not be a symlink"):
        threshold_analyzer._validate_candidate_runs_root(payload, run_root=run_root)

    candidate_runs_root.unlink()
    candidate_runs_root.mkdir()
    outside_candidate = tmp_path / "outside-candidate"
    outside_candidate.mkdir()
    candidate_path = candidate_runs_root / "candidate"
    _directory_symlink_or_skip(candidate_path, outside_candidate)
    with pytest.raises(ThresholdCalibrationError, match="must not be a symlink"):
        threshold_analyzer._resolve_candidate_run_directory(
            run_root=run_root,
            candidate_runs_root=candidate_runs_root,
            candidate_name="candidate",
        )


def test_analyzer_rejects_runtime_drift_and_non_dev_rows(tmp_path: Path) -> None:
    config_path, manifest_path, config, selected = _build_bundle(tmp_path)
    run_root = tmp_path / "calibration"
    _fake_candidate_runs(run_root, config_path, manifest_path, config, selected)
    first_id = candidate_id(0.20)
    capabilities_path = run_root / "candidate-runs" / first_id / "capabilities.json"
    original_capabilities = json.loads(capabilities_path.read_text(encoding="utf-8"))
    tampered_capabilities = dict(original_capabilities)
    tampered_capabilities["localization_channel_vote_min"] = 2
    _write_json(capabilities_path, tampered_capabilities)
    with pytest.raises(ThresholdCalibrationError, match="localization contract is invalid"):
        analyze_threshold_calibration(config_path, run_root=run_root)
    _write_json(capabilities_path, original_capabilities)

    environment_path = (
        run_root / "candidate-runs" / first_id / "benchmark" / "environment.json"
    )
    environment = json.loads(environment_path.read_text(encoding="utf-8"))
    environment["packages"]["Pillow"] = "0.0-wrong"
    _write_json(environment_path, environment)
    with pytest.raises(ThresholdCalibrationError, match="runtime is not frozen"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    environment["packages"]["Pillow"] = REQUIRED_ATTACK_RUNTIME["Pillow"]
    _write_json(environment_path, environment)
    raw_path = (
        run_root / "candidate-runs" / first_id / "benchmark" / "raw_results.jsonl"
    )
    raw_rows = [json.loads(line) for line in raw_path.read_text().splitlines()]
    original_clean_path = raw_rows[0]["attacked_image_path"]
    raw_rows[0]["attacked_image_path"] = selected[0].image_path
    _write_jsonl(raw_path, raw_rows)
    with pytest.raises(ThresholdCalibrationError, match="escapes"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    raw_rows[0]["attacked_image_path"] = original_clean_path
    raw_rows[0]["split"] = "test"
    _write_jsonl(raw_path, raw_rows)
    with pytest.raises(ThresholdCalibrationError, match="non-dev"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    raw_rows[0]["split"] = "dev"
    original_row_key = raw_rows[0]["row_key"]
    raw_rows[0]["row_key"] = "wrong|row|key"
    _write_jsonl(raw_path, raw_rows)
    with pytest.raises(ThresholdCalibrationError, match="row_key differs"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    raw_rows[0]["row_key"] = original_row_key
    original_attacked_sha256 = raw_rows[0]["attacked_image_sha256"]
    raw_rows[0]["attacked_image_sha256"] = "b" * 64
    _write_jsonl(raw_path, raw_rows)
    with pytest.raises(ThresholdCalibrationError, match="differs from its file"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    raw_rows[0]["attacked_image_sha256"] = original_attacked_sha256
    original_erasing_sha256 = raw_rows[1]["attacked_image_sha256"]
    raw_rows[1]["attacked_image_sha256"] = "c" * 64
    _write_jsonl(raw_path, raw_rows)
    with pytest.raises(ThresholdCalibrationError, match="deterministic replay"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    raw_rows[1]["attacked_image_sha256"] = original_erasing_sha256
    raw_rows[0]["mask_fpr"] = -0.1
    _write_jsonl(raw_path, raw_rows)
    with pytest.raises(ThresholdCalibrationError, match=r"outside \[0, 1\]"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    raw_rows[0]["mask_fpr"] = True
    _write_jsonl(raw_path, raw_rows)
    with pytest.raises(ThresholdCalibrationError, match="no finite mask_fpr"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    raw_rows[0]["mask_fpr"] = 1.0 / 64.0
    _write_jsonl(raw_path, raw_rows)
    verify_report_path = (
        run_root
        / "candidate-runs"
        / first_id
        / "benchmark"
        / "api_jobs"
        / raw_rows[0]["verify_job_id"]
        / "verify"
        / "verify_report.json"
    )
    original_verify_report = json.loads(verify_report_path.read_text(encoding="utf-8"))
    verify_report_path.unlink()
    with pytest.raises(ThresholdCalibrationError, match="Verify report is missing"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    _write_json(verify_report_path, original_verify_report)
    tampered_verify_report = json.loads(verify_report_path.read_text(encoding="utf-8"))
    tampered_verify_report["input_image"]["sha256"] = "e" * 64
    _write_json(verify_report_path, tampered_verify_report)
    with pytest.raises(ThresholdCalibrationError, match="input-image SHA-256 differs"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    _write_json(verify_report_path, original_verify_report)
    tampered_verify_report = json.loads(verify_report_path.read_text(encoding="utf-8"))
    tampered_verify_report["response"]["seed"] += 1
    _write_json(verify_report_path, tampered_verify_report)
    with pytest.raises(ThresholdCalibrationError, match="seed differs"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    _write_json(verify_report_path, original_verify_report)
    tampered_verify_report = json.loads(verify_report_path.read_text(encoding="utf-8"))
    tampered_verify_report["response"]["localization_channel_vote_min"] = 2
    _write_json(verify_report_path, tampered_verify_report)
    with pytest.raises(ThresholdCalibrationError, match="localization contract is invalid"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    _write_json(verify_report_path, original_verify_report)
    tampered_verify_report = json.loads(verify_report_path.read_text(encoding="utf-8"))
    tampered_verify_report["raw_localization_votes_artifact"]["histogram"]["0"] -= 1
    _write_json(verify_report_path, tampered_verify_report)
    with pytest.raises(ThresholdCalibrationError, match="histogram differs"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    _write_json(verify_report_path, original_verify_report)
    raw_vote_path = verify_report_path.with_name(RAW_LOCALIZATION_VOTE_FILENAME)
    original_raw_vote_bytes = raw_vote_path.read_bytes()
    with Image.open(raw_vote_path) as raw_vote_image:
        raw_vote_array = np.asarray(raw_vote_image).astype(np.uint16)
    Image.fromarray(raw_vote_array.astype(np.uint8)).save(raw_vote_path)
    tampered_verify_report = json.loads(verify_report_path.read_text(encoding="utf-8"))
    tampered_raw_sha256 = sha256_file(raw_vote_path)
    tampered_verify_report["raw_localization_votes_artifact"][
        "sha256"
    ] = tampered_raw_sha256
    tampered_verify_report["response"][
        "raw_localization_votes_sha256"
    ] = tampered_raw_sha256
    _write_json(verify_report_path, tampered_verify_report)
    with pytest.raises(ThresholdCalibrationError, match="not non-interlaced 16-bit"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    raw_vote_path.write_bytes(original_raw_vote_bytes)
    _write_json(verify_report_path, original_verify_report)
    with Image.open(raw_vote_path) as raw_vote_image:
        raw_vote_array = np.asarray(raw_vote_image).astype(np.uint16)
    raw_vote_array[1, 1] = 255
    Image.fromarray(raw_vote_array).save(raw_vote_path, format="PNG", compress_level=6)
    tampered_verify_report = json.loads(verify_report_path.read_text(encoding="utf-8"))
    tampered_raw_sha256 = sha256_file(raw_vote_path)
    tampered_histogram = {
        str(value): int(np.count_nonzero(raw_vote_array == value))
        for value in (0, 255, 510, 765)
    }
    tampered_verify_report["raw_localization_votes_artifact"].update(
        {"sha256": tampered_raw_sha256, "histogram": tampered_histogram}
    )
    tampered_verify_report["response"].update(
        {
            "raw_localization_votes_sha256": tampered_raw_sha256,
            "raw_localization_votes_histogram": tampered_histogram,
        }
    )
    _write_json(verify_report_path, tampered_verify_report)
    with pytest.raises(
        ThresholdCalibrationError,
        match="differs from independent raw-vote reconstruction",
    ):
        analyze_threshold_calibration(config_path, run_root=run_root)

    raw_vote_path.write_bytes(original_raw_vote_bytes)
    _write_json(verify_report_path, original_verify_report)
    tampered_verify_report = json.loads(verify_report_path.read_text(encoding="utf-8"))
    tampered_verify_report["tamper_area_threshold"] = 0.002
    _write_json(verify_report_path, tampered_verify_report)
    with pytest.raises(ThresholdCalibrationError, match="fixed localization parameter"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    _write_json(verify_report_path, original_verify_report)
    tampered_verify_report = json.loads(verify_report_path.read_text(encoding="utf-8"))
    tampered_verify_report["response"]["predicted_mask_path"] = str(
        (tmp_path / "outside.png").resolve()
    )
    _write_json(verify_report_path, tampered_verify_report)
    with pytest.raises(ThresholdCalibrationError, match="escapes"):
        analyze_threshold_calibration(config_path, run_root=run_root)

    _write_json(verify_report_path, original_verify_report)
    predicted_path = (
        run_root
        / "candidate-runs"
        / first_id
        / "benchmark"
        / "api_jobs"
        / raw_rows[0]["verify_job_id"]
        / "verify"
        / "predicted_mask.png"
    )
    predicted = Image.open(predicted_path).convert("L")
    predicted.putpixel((1, 1), 255)
    predicted.save(predicted_path)
    with pytest.raises(
        ThresholdCalibrationError,
        match="differs from independent raw-vote reconstruction",
    ):
        analyze_threshold_calibration(config_path, run_root=run_root)


def test_threshold_shell_entrypoints_are_syntax_valid_and_isolated() -> None:
    project_root = Path(__file__).resolve().parents[2]
    runner = (
        project_root
        / "scripts"
        / "server"
        / "run_image_watermark_threshold_calibration.sh"
    )
    sbatch = project_root / "scripts" / "server" / "image_watermark_benchmark.sbatch"
    subprocess.run(
        ["bash", "-n", "scripts/server/run_image_watermark_threshold_calibration.sh"],
        check=True,
        cwd=project_root,
    )
    subprocess.run(
        ["bash", "-n", "scripts/server/image_watermark_benchmark.sbatch"],
        check=True,
        cwd=project_root,
    )
    runner_text = runner.read_text(encoding="utf-8")
    sbatch_text = sbatch.read_text(encoding="utf-8")
    for threshold in (
        "0.20",
        "0.22",
        "0.24",
        "0.26",
        "0.28",
        "0.30",
        "0.32",
        "0.34",
        "0.36",
    ):
        assert f"--threshold {threshold}" in runner_text
    assert "-ne 9" in runner_text
    assert "--source-manifest" not in runner_text
    assert "unset COGNIGUARD_WATERMARK_DATASET_MANIFEST" in runner_text
    assert "unset COGNIGUARD_DATASET_ROOTS_JSON" in runner_text
    assert "unset COGNIGUARD_WATERMARK_BENCHMARK_CONFIG" in runner_text
    assert "unset COGNIGUARD_WATERMARK_ASSET_MANIFEST" not in runner_text
    assert 'EXPLICIT_FORMAL_CONFIG="${FORMAL_BENCHMARK_CONFIG-}"' in runner_text
    assert 'FORMAL_CONFIG="${EXPLICIT_FORMAL_CONFIG}"' in runner_text
    assert "must explicitly name the reviewed formal YAML" in runner_text
    assert "${COGNIGUARD_WATERMARK_BENCHMARK_CONFIG:-" not in runner_text
    assert "Refusing to overwrite threshold-calibration output" in runner_text
    assert 'if ! mkdir -- "${RUN_ROOT}"; then' in runner_text
    assert 'if [[ -e "${RUN_ROOT}" ]]' not in runner_text
    assert 'mkdir -p -- "${RUN_ROOT}"' not in runner_text
    assert runner_text.count('mkdir -- "${RUN_ROOT}"') == 1
    assert "THRESHOLD_CALIBRATION_MODE=1" in runner_text
    assert "SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN=1" in runner_text
    assert "BENCHMARK_RESUME=0" in runner_text
    assert "COGNIGUARD_PREREGISTRATION_CLAIM_PATH" in runner_text
    assert "COGNIGUARD_PREREGISTRATION_NONCE" in runner_text
    assert 'mkdir -- "${RUN_ROOT}/candidate-runs"' in runner_text
    assert 'export PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"' in runner_text
    assert 'API_HOST="${WATERMARK_API_HOST:-127.0.0.1}"' in runner_text
    assert 'API_PORT="${WATERMARK_API_PORT:-8010}"' in runner_text
    assert '--base-url "${CALIBRATION_BASE_URL}"' in runner_text
    assert 'WATERMARK_API_HOST="${API_HOST}"' in runner_text
    assert 'WATERMARK_API_PORT="${API_PORT}"' in runner_text
    assert "$(${PYTHON_BIN}" not in runner_text
    assert runner_text.count('$("${PYTHON_BIN}" -c') == 2
    assert 'RUN_CLASS="threshold_calibration_development_only"' in sbatch_text
    assert "CALIBRATION_EXPECTED_RECOVERY_THRESHOLD" in sbatch_text
    assert "threshold-calibration config gate: ready" in sbatch_text
    assert "threshold-calibration API URL gate:" in sbatch_text
    assert "refusing secure-environment drift" in sbatch_text
    assert "localization_mask_rule_version" in sbatch_text
    assert "localization_residual_channels" in sbatch_text
    assert "localization_channel_aggregation" in sbatch_text
    assert "localization_channel_vote_min" in sbatch_text
    assert "localization_residual_threshold_rule" in sbatch_text
    assert "attack_model_revision" in sbatch_text
    assert "stable-diffusion-v1-5/stable-diffusion-inpainting" in sbatch_text
    assert "unset COGNIGUARD_WATERMARK_DATASET_MANIFEST" in sbatch_text
    assert "unset COGNIGUARD_DATASET_ROOTS_JSON" in sbatch_text
    assert "scripts.server.image_watermark_preregistration validate" in sbatch_text
    assert "scripts.server.image_watermark_preregistration copy" in sbatch_text
    assert 'if ! mkdir -- "${RUN_DIR}"; then' in sbatch_text


def test_threshold_runner_rejects_implicit_formal_config() -> None:
    project_root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment.pop("FORMAL_BENCHMARK_CONFIG", None)
    environment.pop("SERVER_ENV_FILE", None)
    environment.update(
        {
            "COGNIGUARD_WATERMARK_BENCHMARK_CONFIG": "poison.yaml",
            "COGNIGUARD_WATERMARK_DATASET_MANIFEST": "poison.jsonl",
            "COGNIGUARD_DATASET_ROOTS_JSON": '{"poison":"root"}',
            "COGNIGUARD_WATERMARK_ASSET_MANIFEST": "poison-assets.json",
        }
    )

    completed = subprocess.run(
        ["bash", "scripts/server/run_image_watermark_threshold_calibration.sh"],
        cwd=project_root,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "must explicitly name the reviewed formal YAML" in completed.stderr
