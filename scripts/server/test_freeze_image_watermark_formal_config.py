from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from PIL import Image

from protection.supporting.image_watermark.experiments.manifest import (
    build_manifest_from_config,
    dataset_roots_from_config,
    deterministic_split,
    load_manifest,
    manifest_lock_path,
    validate_manifest_lock,
    write_manifest,
)
from protection.supporting.image_watermark.experiments.paper_benchmark import (
    SOURCE_TREE_IDENTITY_VERSION,
    _source_tree_identity_scope,
)
from scripts.server import (
    analyze_image_watermark_threshold_calibration as analyzer_module,
)
from scripts.server import freeze_image_watermark_formal_config as freeze_module
from scripts.server.analyze_image_watermark_threshold_calibration import (
    CONSTRAINTS,
    REPORT_SCHEMA_VERSION,
)
from scripts.server.build_image_watermark_threshold_calibration import (
    ATTACK_ARTIFACT_RETENTION,
    EVALUATION_SEEDS,
    FROZEN_THRESHOLDS,
    REQUIRED_ATTACK_RUNTIME,
    RUN_CLASS,
    build_threshold_calibration_bundle,
    candidate_id,
    sha256_file,
)
from scripts.server.freeze_image_watermark_formal_config import (
    FORMAL_RUN_CLASS,
    FORMAL_SELECTION_SCHEMA_VERSION,
    FormalFreezeError,
    _expected_constraint_names,
    freeze_formal_config,
    validate_frozen_formal_config,
)
from scripts.server.image_watermark_preregistration import write_preregistration_claim
from scripts.server.test_image_watermark_threshold_calibration import (
    _build_bundle as _build_real_analyzer_bundle,
)
from scripts.server.test_image_watermark_threshold_calibration import (
    _fake_candidate_runs as _write_real_candidate_runs,
)


DATASET_NAMES = ("synthetic_v2", "open_images", "nasa", "met")
SOURCE_SAMPLES_PER_DATASET = 33
SOURCE_TOTAL_SAMPLES = len(DATASET_NAMES) * SOURCE_SAMPLES_PER_DATASET
SPLIT_SEED = 20260802
TRAIN_RATIO = 0.70
DEV_RATIO = 0.10
FIXTURE_SOURCE_TREE_SHA256 = "c" * 64
FIXTURE_SOURCE_TREE_FILE_COUNT = 37


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _replace_immutable_identity(
    report: dict[str, Any], identity: dict[str, Any]
) -> None:
    report["immutable_environment_identity"] = identity
    report["immutable_environment_identity_sha256"] = hashlib.sha256(
        json.dumps(
            identity,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


@pytest.fixture
def mock_full_analyzer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests may isolate post-analysis freeze mechanics from GPU artifacts."""

    def read_stored_report(
        _config_path: Path, *, run_root: Path | None = None
    ) -> dict[str, Any]:
        if run_root is None:
            raise AssertionError("Freeze must provide the calibration run root.")
        return json.loads(
            (Path(run_root) / "threshold_selection.json").read_text(encoding="utf-8")
        )

    monkeypatch.setattr(
        freeze_module,
        "analyze_threshold_calibration",
        read_stored_report,
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


def _formal_fixture(tmp_path: Path) -> tuple[Path, Path]:
    datasets: list[dict[str, Any]] = []
    image_index = 0
    for dataset_name in DATASET_NAMES:
        root = tmp_path / "datasets" / dataset_name
        images = root / "images"
        images.mkdir(parents=True)
        metadata_rows: list[dict[str, Any]] = []
        requested_splits = ["dev"] * 31 + ["train", "test"]
        for local_index, split in enumerate(requested_splits):
            relative_path = f"images/image_{local_index:03d}.png"
            image_path = root / relative_path
            image = Image.new(
                "RGB",
                (3, 3),
                (
                    image_index % 256,
                    (image_index // 256) % 256,
                    (image_index * 37 + 11) % 256,
                ),
            )
            image.putpixel(
                (local_index % 3, (local_index // 3) % 3),
                ((image_index * 19) % 256, 255, local_index),
            )
            image.save(image_path)
            metadata_rows.append(
                {
                    "relative_path": relative_path,
                    "split": split,
                    "source_family": _source_family_for_split(
                        dataset_name, local_index, split
                    ),
                    "domain": f"domain:{dataset_name}",
                    "license_id": "CC0-1.0",
                    "license_url": (
                        "https://creativecommons.org/publicdomain/zero/1.0/"
                    ),
                    "provenance": f"fixture:{dataset_name}:{local_index}",
                }
            )
            image_index += 1
        (root / "metadata.jsonl").write_text(
            "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                for row in metadata_rows
            ),
            encoding="utf-8",
        )
        datasets.append(
            {
                "name": dataset_name,
                "enabled": True,
                "root": str(root),
                "glob": "**/*.png",
                "metadata_jsonl": "metadata.jsonl",
                "require_sidecar_metadata": True,
                "max_samples": SOURCE_SAMPLES_PER_DATASET,
                "required_samples": SOURCE_SAMPLES_PER_DATASET,
                "compute_sha256": True,
                "license_id": "CC0-1.0",
                "license_url": ("https://creativecommons.org/publicdomain/zero/1.0/"),
                "provenance": f"fixture:{dataset_name}",
            }
        )

    manifest_path = tmp_path / "source" / "paper_formal_fixture_v2.jsonl"
    config = {
        "experiment": {
            "name": "formal_fixture_v2",
            "strict_paper_mode": True,
            "fail_fast": True,
            "split": "test",
            "seeds": list(EVALUATION_SEEDS),
            "max_samples": 0,
            "api_timeout_seconds": 900,
            "traditional_attack_artifact_retention": ATTACK_ARTIFACT_RETENTION,
            "required_attack_runtime": dict(REQUIRED_ATTACK_RUNTIME),
            "output_root": str(tmp_path / "formal-results"),
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
            "expected_total_samples": SOURCE_TOTAL_SAMPLES,
            "minimum_test_samples": len(DATASET_NAMES),
            "minimum_datasets": len(DATASET_NAMES),
            "minimum_domains": len(DATASET_NAMES),
            "require_nonempty_source_family": True,
            "require_unique_source_family": True,
            "expected_unique_source_families": SOURCE_TOTAL_SAMPLES,
            "require_deterministic_splits": True,
            "required_evaluation_split": "test",
            "require_max_samples_zero": True,
        },
        "metrics": {
            "require_reference_ssim": True,
            "lpips": {"enabled": True, "required": True},
        },
        "datasets": datasets,
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
            "aigc": {"enabled": False, "specs": []},
        },
    }
    config_path = tmp_path / "source" / "paper_benchmark.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    rows, report = build_manifest_from_config(config_path, environ={})
    write_manifest(
        rows,
        manifest_path,
        environ={},
        config_path=config_path,
        upstream_dataset_locks=report.get("upstream_dataset_locks") or {},
    )
    return config_path, manifest_path


def _selection_report_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    source_config, source_manifest = _formal_fixture(tmp_path)
    calibration_dir = tmp_path / "calibration"
    calibration_config = calibration_dir / "threshold_calibration.yaml"
    calibration_manifest = calibration_dir / "threshold_calibration_dev_117.jsonl"
    config, selected = build_threshold_calibration_bundle(
        source_config,
        output_config=calibration_config,
        output_manifest=calibration_manifest,
        base_url="http://127.0.0.1:18010",
    )
    calibration_dir.mkdir(parents=True, exist_ok=True)
    calibration_config.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    upstream = (
        config["threshold_calibration"]["source_formal_manifest_lock"].get(
            "upstream_dataset_locks"
        )
        or {}
    )
    write_manifest(
        selected,
        calibration_manifest,
        environ={},
        config_path=calibration_config,
        upstream_dataset_locks=upstream,
    )
    preregistration_evidence = write_preregistration_claim(
        calibration_config,
        expected_run_class=RUN_CLASS,
    )

    source_roots = dataset_roots_from_config(source_config, environ={})
    source_rows = load_manifest(
        source_manifest,
        dataset_roots=source_roots,
        require_files=True,
        verify_hashes=True,
    )
    source_lock = validate_manifest_lock(
        source_manifest,
        source_rows,
        config_path=source_config,
        dataset_roots=source_roots,
    )
    calibration_roots = dataset_roots_from_config(calibration_config, environ={})
    selected_rows = load_manifest(
        calibration_manifest,
        dataset_roots=calibration_roots,
        require_files=True,
        verify_hashes=True,
    )
    selected_lock = validate_manifest_lock(
        calibration_manifest,
        selected_rows,
        config_path=calibration_config,
        dataset_roots=calibration_roots,
    )

    constraint_names = sorted(_expected_constraint_names())
    candidates: list[dict[str, Any]] = []
    eligible_ids: list[str] = []
    for threshold in FROZEN_THRESHOLDS:
        passed = threshold >= 0.28
        checks = [
            {"name": name, "passed": passed or index > 0}
            for index, name in enumerate(constraint_names)
        ]
        row = {
            "candidate_id": candidate_id(threshold),
            "recovery_threshold": threshold,
            "development_only": True,
            "paper_eligible": False,
            "evaluation_seeds": list(EVALUATION_SEEDS),
            "constraint_checks": checks,
            "all_constraints_passed": passed,
        }
        candidates.append(row)
        if passed:
            eligible_ids.append(row["candidate_id"])

    contract = config["threshold_calibration"]
    immutable_environment_identity = {
        "fixture": True,
        "source_tree_identity_version": SOURCE_TREE_IDENTITY_VERSION,
        "source_tree_scope": _source_tree_identity_scope(),
        "source_tree_sha256": FIXTURE_SOURCE_TREE_SHA256,
        "source_tree_file_count": FIXTURE_SOURCE_TREE_FILE_COUNT,
        "fixed_capabilities": {
            "attack_model_id": "stable-diffusion-v1-5/stable-diffusion-inpainting",
            "attack_model_revision": "1" * 40,
            "deterministic_mode_enabled": True,
        },
    }
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "winner_selected",
        "run_class": RUN_CLASS,
        "development_only": True,
        "paper_eligible": False,
        "selection_split": "dev",
        "excluded_splits": ["train", "test"],
        "formal_test_rows_consumed": 0,
        "formal_config_update_performed": False,
        "formal_config_must_remain_unchanged_until_freeze": True,
        "config": str(calibration_config.resolve()),
        "config_sha256": sha256_file(calibration_config),
        "preregistration_claim": preregistration_evidence,
        "selected_manifest": str(calibration_manifest.resolve()),
        "selected_manifest_sha256": sha256_file(calibration_manifest),
        "selected_manifest_lock": selected_lock,
        "selected_samples": 117,
        "selection_seed": contract["selection_seed"],
        "evaluation_seeds": list(EVALUATION_SEEDS),
        "unique_image_sha256": 117,
        "unique_source_families": 117,
        "selected_dataset_counts": contract["selected_dataset_counts"],
        "selected_domains": contract["selected_domains"],
        "formal_split_assignment_audit": contract["formal_split_assignment_audit"],
        "cross_candidate_attack_inputs_identical": True,
        "cross_candidate_environment_identity_identical": True,
        "immutable_environment_identity_sha256": hashlib.sha256(
            json.dumps(
                immutable_environment_identity,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "immutable_environment_identity": immutable_environment_identity,
        "attack_input_hash_map_sha256": "b" * 64,
        "candidate_metrics": candidates,
        "eligible_candidate_ids": eligible_ids,
        "winner_rule": contract["winner_rule"],
        "winner": {
            "candidate_id": candidate_id(0.28),
            "recovery_threshold": 0.28,
            "selection_reason": (
                "smallest candidate satisfying every frozen completeness, "
                "clean-FPR, and erasing-IoU constraint"
            ),
        },
        "constraints": CONSTRAINTS,
        "formal_inputs": {
            "config": str(source_config.resolve()),
            "config_sha256": sha256_file(source_config),
            "manifest": str(source_manifest.resolve()),
            "manifest_sha256": sha256_file(source_manifest),
            "manifest_lock": source_lock,
        },
    }
    report_path = calibration_dir / "threshold_selection.json"
    _write_json(report_path, report)
    (calibration_dir / "candidate-runs").mkdir()
    return source_config, source_manifest, report_path


def test_freeze_creates_new_config_byte_equal_manifest_and_bound_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_full_analyzer: None,
) -> None:
    source_config, source_manifest, selection_report = _selection_report_fixture(
        tmp_path
    )
    output_config = tmp_path / "selected" / "paper_benchmark_selected_v1.yaml"
    output_manifest = tmp_path / "selected-manifests" / "paper_formal_selected_v1.jsonl"
    monkeypatch.setenv(
        "COGNIGUARD_WATERMARK_DATASET_MANIFEST", str(tmp_path / "wrong.jsonl")
    )
    monkeypatch.setenv(
        "COGNIGUARD_DATASET_ROOTS_JSON", json.dumps({"synthetic_v2": "wrong"})
    )

    result = freeze_formal_config(
        source_config,
        selection_report=selection_report,
        output_config=output_config,
        output_manifest=output_manifest,
        expected_formal_samples=SOURCE_TOTAL_SAMPLES,
    )

    assert result["status"] == "created"
    assert result["samples"] == SOURCE_TOTAL_SAMPLES
    assert result["test_samples"] == len(DATASET_NAMES)
    assert result["generic_input_overrides_ignored"] is True
    assert output_manifest.read_bytes() == source_manifest.read_bytes()

    payload = yaml.safe_load(output_config.read_text(encoding="utf-8"))
    assert payload["experiment"]["run_class"] == FORMAL_RUN_CLASS
    assert payload["experiment"]["paper_eligible"] is True
    assert payload["experiment"]["development_only"] is False
    selection = payload["formal_selection"]
    assert selection["schema_version"] == FORMAL_SELECTION_SCHEMA_VERSION
    assert selection["selection_split"] == "dev"
    assert selection["formal_test_rows_consumed"] == 0
    assert selection["winner_candidate_id"] == candidate_id(0.28)
    assert (
        selection["calibration_source_tree_identity_version"]
        == SOURCE_TREE_IDENTITY_VERSION
    )
    assert selection["calibration_source_tree_scope"] == _source_tree_identity_scope()
    assert selection["calibration_source_tree_sha256"] == FIXTURE_SOURCE_TREE_SHA256
    assert (
        selection["calibration_source_tree_file_count"]
        == FIXTURE_SOURCE_TREE_FILE_COUNT
    )
    required = selection["selected_parameters"]
    assert type(required["recovery_threshold"]) is float
    assert type(required["tamper_area_threshold"]) is float
    assert type(required["registry_hamming_radius"]) is int
    assert type(required["localization_postprocessing"]) is str
    assert type(required["localization_mask_rule_version"]) is str
    assert type(required["localization_residual_channels"]) is int
    assert type(required["localization_channel_aggregation"]) is str
    assert type(required["localization_channel_vote_min"]) is int
    assert type(required["localization_residual_threshold_rule"]) is str
    editguard = next(
        method for method in payload["methods"] if method["id"] == "editguard_wrapper"
    )
    assert editguard["required_capabilities"] == required
    assert required == {
        "recovery_threshold": 0.28,
        "tamper_area_threshold": 0.001,
        "registry_hamming_radius": 1,
        "localization_postprocessing": "none",
        "localization_mask_rule_version": "editguard_residual_channel_vote_v2",
        "localization_residual_channels": 3,
        "localization_channel_aggregation": "k_of_3",
        "localization_channel_vote_min": 1,
            "localization_residual_threshold_rule": (
                "abs_gt_recovery_threshold_per_channel"
            ),
            "attack_model_id": "stable-diffusion-v1-5/stable-diffusion-inpainting",
            "attack_model_revision": "1" * 40,
            "deterministic_mode_enabled": True,
        }

    selected_roots = dataset_roots_from_config(output_config, environ={})
    selected_rows = load_manifest(
        output_manifest,
        dataset_roots=selected_roots,
        require_files=True,
        verify_hashes=True,
    )
    selected_lock = validate_manifest_lock(
        output_manifest,
        selected_rows,
        config_path=output_config,
        dataset_roots=selected_roots,
    )
    source_roots = dataset_roots_from_config(source_config, environ={})
    source_rows = load_manifest(
        source_manifest,
        dataset_roots=source_roots,
        require_files=True,
        verify_hashes=True,
    )
    source_lock = validate_manifest_lock(
        source_manifest,
        source_rows,
        config_path=source_config,
        dataset_roots=source_roots,
    )
    for field in (
        "manifest_sha256",
        "total_samples",
        "dataset_counts",
        "split_counts",
        "unique_sha256_count",
        "unique_source_family_count",
        "assignment_sha256",
        "upstream_dataset_locks",
    ):
        assert selected_lock[field] == source_lock[field]
    assert selected_lock["manifest_filename"] == output_manifest.name
    assert selected_lock["config_sha256"] == sha256_file(output_config)
    assert selected_lock["config_sha256"] != source_lock["config_sha256"]
    assert (
        validate_frozen_formal_config(
            output_config,
            expected_formal_samples=SOURCE_TOTAL_SAMPLES,
        )
        == required
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda report: report.update(
                {"status": "no_candidate_satisfies_constraints"}
            ),
            "winner_selected",
        ),
        (
            lambda report: report.update({"formal_test_rows_consumed": 1}),
            "dev-only/test-unconsumed",
        ),
        (
            lambda report: report["eligible_candidate_ids"].pop(0),
            "eligible_candidate_ids",
        ),
        (
            lambda report: report["winner"].update(
                {
                    "candidate_id": candidate_id(0.30),
                    "recovery_threshold": 0.30,
                }
            ),
            "smallest eligible",
        ),
        (
            lambda report: report["candidate_metrics"][4].update(
                {"all_constraints_passed": False}
            ),
            "all_constraints_passed is inconsistent",
        ),
        (
            lambda report: report["formal_inputs"].update({"config_sha256": "0" * 64}),
            "Source formal config SHA-256",
        ),
        (
            lambda report: report["selected_manifest_lock"].update(
                {"manifest_sha256": "1" * 64}
            ),
            "dev manifest evidence differs",
        ),
        (
            lambda report: report.update(
                {"immutable_environment_identity_sha256": "0" * 64}
            ),
            "does not authenticate immutable_environment_identity",
        ),
        (
            lambda report: _replace_immutable_identity(
                report,
                {
                    **report["immutable_environment_identity"],
                    "source_tree_identity_version": "obsolete-version",
                },
            ),
            "source_tree_identity_version",
        ),
        (
            lambda report: _replace_immutable_identity(
                report,
                {
                    **report["immutable_environment_identity"],
                    "source_tree_scope": {"include_globs": []},
                },
            ),
            "source_tree_scope differs",
        ),
        (
            lambda report: _replace_immutable_identity(
                report,
                {
                    **report["immutable_environment_identity"],
                    "source_tree_sha256": "invalid",
                },
            ),
            "source_tree_sha256",
        ),
        (
            lambda report: _replace_immutable_identity(
                report,
                {
                    **report["immutable_environment_identity"],
                    "source_tree_file_count": True,
                },
            ),
            "source_tree_file_count must be a positive integer",
        ),
    ],
)
def test_freeze_rejects_invalid_selection_and_source_evidence(
    tmp_path: Path,
    mutation: Any,
    message: str,
    mock_full_analyzer: None,
) -> None:
    source_config, _, report_path = _selection_report_fixture(tmp_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    mutation(report)
    _write_json(report_path, report)
    output_config = tmp_path / "selected" / "paper_selected.yaml"
    output_manifest = tmp_path / "selected" / "paper_selected.jsonl"

    with pytest.raises(FormalFreezeError, match=message):
        freeze_formal_config(
            source_config,
            selection_report=report_path,
            output_config=output_config,
            output_manifest=output_manifest,
            expected_formal_samples=SOURCE_TOTAL_SAMPLES,
        )
    assert not output_config.exists()
    assert not output_manifest.exists()
    assert not manifest_lock_path(output_manifest).exists()


def test_validate_frozen_rejects_tampered_calibration_source_tree_binding(
    tmp_path: Path,
    mock_full_analyzer: None,
) -> None:
    source_config, _, report_path = _selection_report_fixture(tmp_path)
    output_config = tmp_path / "selected" / "paper_selected.yaml"
    output_manifest = tmp_path / "selected" / "paper_selected.jsonl"
    freeze_formal_config(
        source_config,
        selection_report=report_path,
        output_config=output_config,
        output_manifest=output_manifest,
        expected_formal_samples=SOURCE_TOTAL_SAMPLES,
    )
    selected = yaml.safe_load(output_config.read_text(encoding="utf-8"))
    selected["formal_selection"]["calibration_source_tree_sha256"] = "0" * 64
    output_config.write_text(
        yaml.safe_dump(selected, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(
        FormalFreezeError,
        match="source-tree identity differs from the threshold-selection report",
    ):
        validate_frozen_formal_config(
            output_config,
            expected_formal_samples=SOURCE_TOTAL_SAMPLES,
        )


def test_freeze_refuses_overwrite_without_touching_existing_file(
    tmp_path: Path,
) -> None:
    source_config, _, report_path = _selection_report_fixture(tmp_path)
    output_config = tmp_path / "selected" / "paper_selected.yaml"
    output_manifest = tmp_path / "selected" / "paper_selected.jsonl"
    output_config.parent.mkdir(parents=True)
    output_config.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        freeze_formal_config(
            source_config,
            selection_report=report_path,
            output_config=output_config,
            output_manifest=output_manifest,
            expected_formal_samples=SOURCE_TOTAL_SAMPLES,
        )
    assert output_config.read_text(encoding="utf-8") == "sentinel\n"
    assert not output_manifest.exists()


def test_freeze_requires_all_candidate_run_artifacts_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_config, _, report_path = _selection_report_fixture(tmp_path)
    monkeypatch.setattr(
        analyzer_module.importlib.metadata,
        "version",
        lambda package: REQUIRED_ATTACK_RUNTIME[package],
    )

    with pytest.raises(
        FormalFreezeError,
        match="failed independent threshold reanalysis.*Candidate run directory is missing",
    ):
        freeze_formal_config(
            source_config,
            selection_report=report_path,
            output_config=tmp_path / "selected" / "paper_selected.yaml",
            output_manifest=tmp_path / "selected" / "paper_selected.jsonl",
            expected_formal_samples=SOURCE_TOTAL_SAMPLES,
        )


def test_full_reanalysis_rejects_internally_consistent_forged_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analyzer_module, "EXPECTED_SERVICE_IMAGE_SHAPE", (8, 8))
    config_path, manifest_path, config, selected = _build_real_analyzer_bundle(tmp_path)
    run_root = tmp_path / "calibration"
    _write_real_candidate_runs(run_root, config_path, manifest_path, config, selected)

    real_version = analyzer_module.importlib.metadata.version

    def frozen_version(package: str) -> str:
        if package in REQUIRED_ATTACK_RUNTIME:
            return REQUIRED_ATTACK_RUNTIME[package]
        return real_version(package)

    monkeypatch.setattr(
        analyzer_module.importlib.metadata,
        "version",
        frozen_version,
    )
    canonical = analyzer_module.analyze_threshold_calibration(
        config_path,
        run_root=run_root,
    )

    forged = copy.deepcopy(canonical)
    formerly_winning = next(
        row
        for row in forged["candidate_metrics"]
        if row["candidate_id"] == candidate_id(0.28)
    )
    formerly_winning["constraint_checks"][0]["passed"] = False
    formerly_winning["all_constraints_passed"] = False
    forged["eligible_candidate_ids"].remove(candidate_id(0.28))
    forged["winner"] = {
        "candidate_id": candidate_id(0.30),
        "recovery_threshold": 0.30,
        "selection_reason": canonical["winner"]["selection_reason"],
    }
    report_path = run_root / "threshold_selection.json"
    _write_json(report_path, forged)
    source_config = Path(config["threshold_calibration"]["source_formal_config"])
    output_config = tmp_path / "selected" / "paper_selected.yaml"
    output_manifest = tmp_path / "selected" / "paper_selected.jsonl"

    with pytest.raises(
        FormalFreezeError,
        match="differs from independent candidate-run reanalysis",
    ):
        freeze_formal_config(
            source_config,
            selection_report=report_path,
            output_config=output_config,
            output_manifest=output_manifest,
            expected_formal_samples=SOURCE_TOTAL_SAMPLES,
        )
    assert not output_config.exists()
    assert not output_manifest.exists()
    assert not manifest_lock_path(output_manifest).exists()


def test_freeze_rejects_reconstructed_manifest_byte_drift_and_cleans_outputs(
    tmp_path: Path,
    mock_full_analyzer: None,
) -> None:
    source_config, _, report_path = _selection_report_fixture(tmp_path)
    metadata_path = tmp_path / "datasets" / DATASET_NAMES[0] / "metadata.jsonl"
    metadata_rows = [
        json.loads(line)
        for line in metadata_path.read_text(encoding="utf-8").splitlines()
    ]
    metadata_rows[0]["domain"] = "domain:changed-after-calibration"
    metadata_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in metadata_rows),
        encoding="utf-8",
    )
    output_config = tmp_path / "selected" / "paper_selected.yaml"
    output_manifest = tmp_path / "selected" / "paper_selected.jsonl"

    with pytest.raises(FormalFreezeError, match="not byte-equivalent"):
        freeze_formal_config(
            source_config,
            selection_report=report_path,
            output_config=output_config,
            output_manifest=output_manifest,
            expected_formal_samples=SOURCE_TOTAL_SAMPLES,
        )
    assert not output_config.exists()
    assert not output_manifest.exists()
    assert not manifest_lock_path(output_manifest).exists()
