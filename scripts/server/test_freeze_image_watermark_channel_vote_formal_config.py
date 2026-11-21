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
from protection.supporting.image_watermark.experiments.paper_benchmark import _source_tree_identity
from scripts.server import (
    freeze_image_watermark_channel_vote_formal_config as freeze_module,
)
from scripts.server.analyze_image_watermark_channel_vote_confirmation import (
    REPORT_SCHEMA_VERSION as CONFIRMATION_REPORT_SCHEMA_VERSION,
    ChannelVoteConfirmationError,
)
from scripts.server.analyze_image_watermark_threshold_calibration import (
    REPORT_SCHEMA_VERSION as CALIBRATION_REPORT_SCHEMA_VERSION,
)
from scripts.server.build_image_watermark_channel_vote_confirmation import (
    CONFIRMATION_MINIMUM_DOMAINS,
    CANDIDATE_ID,
    EXPECTED_CONFIRMATION_SAMPLES,
    EXPECTED_ROWS as EXPECTED_CONFIRMATION_ROWS,
    FROZEN_REQUIRED_CAPABILITIES,
    RUN_CLASS as CONFIRMATION_RUN_CLASS,
    RUN_RELATIVE_PATH,
    SCHEMA_VERSION as CONFIRMATION_CONFIG_SCHEMA_VERSION,
    SELECTION_RULE,
    _assignment_sha256,
    _selection_rationale_from_report,
)
from scripts.server.build_image_watermark_threshold_calibration import (
    ATTACK_ARTIFACT_RETENTION,
    CONSTRAINTS,
    EVALUATION_SEEDS,
    FROZEN_THRESHOLDS,
    REQUIRED_ATTACK_RUNTIME,
    RUN_CLASS as CALIBRATION_RUN_CLASS,
    audit_formal_split_assignments,
    candidate_id,
    sha256_file,
)
from scripts.server.image_watermark_preregistration import (
    build_preregistration_contract,
    copy_preregistration_claim_to_run,
    write_preregistration_claim,
)
from scripts.server.freeze_image_watermark_channel_vote_formal_config import (
    FORMAL_SELECTION_SCHEMA_VERSION,
    ChannelVoteFormalFreezeError,
    _candidate_run_evidence,
    freeze_channel_vote_formal_config,
    validate_frozen_channel_vote_formal_config,
)


SPLIT_SEED = 20260802
TRAIN_RATIO = 0.70
DEV_RATIO = 0.10
FIXTURE_FORMAL_SAMPLES = 335
TEST_REQUIRED_CAPABILITIES = {
    **FROZEN_REQUIRED_CAPABILITIES,
    "attack_model_id": "stable-diffusion-v1-5/stable-diffusion-inpainting",
    "attack_model_revision": "1" * 40,
    "deterministic_mode_enabled": True,
}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _family_for_split(index: int, split: str) -> str:
    for nonce in range(100_000):
        family = f"fixture-family:{index}:{split}:{nonce}"
        if (
            deterministic_split(
                family,
                seed=SPLIT_SEED,
                train_ratio=TRAIN_RATIO,
                dev_ratio=DEV_RATIO,
            )
            == split
        ):
            return family
    raise AssertionError(f"Unable to create {split} family")


def _formal_fixture(tmp_path: Path) -> tuple[Path, Path, list[Any], dict[str, Any]]:
    root = tmp_path / "dataset"
    images = root / "images"
    images.mkdir(parents=True)
    metadata: list[dict[str, Any]] = []
    requested_splits = ["dev"] * 333 + ["train", "test"]
    for index, split in enumerate(requested_splits):
        relative = f"images/image_{index:04d}.png"
        image_path = root / relative
        image = Image.new(
            "RGB",
            (4, 4),
            (index % 256, (index // 256) % 256, (index * 37) % 256),
        )
        image.putpixel(
            (index % 4, (index // 4) % 4),
            ((index * 19) % 256, 255, (index * 7) % 256),
        )
        image.save(image_path)
        metadata.append(
            {
                "relative_path": relative,
                "split": split,
                "source_family": _family_for_split(index, split),
                "domain": f"domain:{index % 12}",
                "license_id": "CC0-1.0",
                "license_url": (
                    "https://creativecommons.org/publicdomain/zero/1.0/"
                ),
                "provenance": f"fixture:{index}",
            }
        )
    metadata_path = root / "metadata.jsonl"
    metadata_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in metadata),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "source" / "paper_formal.jsonl"
    config = {
        "experiment": {
            "name": "formal_fixture",
            "strict_paper_mode": True,
            "fail_fast": True,
            "split": "test",
            "seeds": list(EVALUATION_SEEDS),
            "max_samples": 0,
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
            "expected_total_samples": FIXTURE_FORMAL_SAMPLES,
            "minimum_test_samples": 1,
            "minimum_datasets": 1,
            "minimum_domains": 1,
            "require_nonempty_source_family": True,
            "require_unique_source_family": True,
            "expected_unique_source_families": FIXTURE_FORMAL_SAMPLES,
            "require_deterministic_splits": True,
            "required_evaluation_split": "test",
            "require_max_samples_zero": True,
        },
        "metrics": {
            "require_reference_ssim": True,
            "lpips": {"enabled": True, "required": True},
        },
        "datasets": [
            {
                "name": "fixture",
                "enabled": True,
                "root": str(root),
                "glob": "**/*.png",
                "metadata_jsonl": "metadata.jsonl",
                "require_sidecar_metadata": True,
                "max_samples": FIXTURE_FORMAL_SAMPLES,
                "required_samples": FIXTURE_FORMAL_SAMPLES,
                "compute_sha256": True,
                "license_id": "CC0-1.0",
                "license_url": (
                    "https://creativecommons.org/publicdomain/zero/1.0/"
                ),
                "provenance": "fixture",
            }
        ],
        "methods": [
            {
                "id": "editguard_wrapper",
                "kind": "sce_locguard_api",
                "base_url": "http://127.0.0.1:18010",
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
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    rows, build_report = build_manifest_from_config(config_path, environ={})
    write_manifest(
        rows,
        manifest_path,
        environ={},
        config_path=config_path,
        upstream_dataset_locks=build_report.get("upstream_dataset_locks") or {},
    )
    roots = dataset_roots_from_config(config_path, environ={})
    locked_rows = load_manifest(
        manifest_path,
        dataset_roots=roots,
        require_files=True,
        verify_hashes=True,
    )
    lock = validate_manifest_lock(
        manifest_path,
        locked_rows,
        config_path=config_path,
        dataset_roots=roots,
    )
    return config_path, manifest_path, locked_rows, lock


def _constraint_names() -> list[str]:
    return [
        "clean_mean_mask_fpr",
        "clean_p99_mask_fpr",
        "clean_max_mask_fpr",
        "erasing_0.05_mean_mask_iou",
        "erasing_0.15_mean_mask_iou",
        "erasing_0.25_mean_mask_iou",
        "erasing_0.05_p10_mask_iou",
        "erasing_0.15_p10_mask_iou",
        "erasing_0.25_p10_mask_iou",
        "erasing_0.05_iou_at_least_0_75_rate",
        "erasing_0.15_iou_at_least_0_75_rate",
        "erasing_0.25_iou_at_least_0_75_rate",
    ]


def _immutable_identity(
    *,
    source_tree: dict[str, Any],
    roots: dict[str, str],
    vote_min: int,
    config_path: Path,
    manifest_path: Path,
) -> tuple[dict[str, Any], str]:
    fixed_capabilities = {
        key: value
        for key, value in FROZEN_REQUIRED_CAPABILITIES.items()
        if key != "recovery_threshold"
    }
    fixed_capabilities["localization_channel_vote_min"] = vote_min
    fixed_capabilities.update(
        {
            "attack_model_id": TEST_REQUIRED_CAPABILITIES["attack_model_id"],
            "attack_model_revision": TEST_REQUIRED_CAPABILITIES[
                "attack_model_revision"
            ],
            "deterministic_mode_enabled": True,
        }
    )
    identity = {
        "schema_version": "cogniguard_image_benchmark_environment_v1",
        "python": "3.12-fixture",
        "platform": "fixture-platform",
        "packages": {"numpy": "1.26.4", "Pillow": "10.4.0"},
        "gpu": {"cuda_available": True, "devices": ["fixture-gpu"]},
        "checkpoints": {"clean.pth": {"sha256": "a" * 64}},
        "git_commit": "fixture-commit",
        "git_status_sha256": "b" * 64,
        "source_tree_identity_version": source_tree["identity_version"],
        "source_tree_scope": copy.deepcopy(source_tree["scope"]),
        "source_tree_sha256": source_tree["sha256"],
        "source_tree_file_count": source_tree["file_count"],
        "config_path": str(config_path),
        "config_sha256": sha256_file(config_path),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "resolved_dataset_roots": roots,
        "dataset_manifest_override_used": False,
        "dataset_roots_override_used": False,
        "registry_secret_recorded": False,
        "methods": [{"id": "editguard_wrapper", "kind": "sce_locguard_api"}],
        "strict_paper_mode": True,
        "run_class": f"fixture-vote-{vote_min}",
        "paper_eligible": False,
        "evaluation_split": "dev",
        "input_manifest_audit": {"fixture_vote_min": vote_min},
        "manifest_lock": {"fixture_vote_min": vote_min},
        "traditional_attack_runtime": {
            "implementation_path": "fixture-attacks.py",
            "implementation_sha256": "c" * 64,
            "required_packages": dict(REQUIRED_ATTACK_RUNTIME),
            "observed_packages": dict(REQUIRED_ATTACK_RUNTIME),
            "artifact_retention": ATTACK_ARTIFACT_RETENTION,
        },
        "deterministic_runtime_identity": {"fixture": "deterministic-v1"},
        "asset_manifest_identity": {"fixture": "assets-v1"},
        "aigc_attack_runtime_identity": {"fixture": "aigc-v1"},
        "registry_secret_identity_fingerprint": "9" * 64,
        "fixed_capabilities": fixed_capabilities,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return identity, digest


def _write_subset_bundle(
    *,
    tmp_path: Path,
    name: str,
    source_config: Path,
    rows: list[Any],
) -> tuple[Path, Path, dict[str, Any]]:
    source_payload = yaml.safe_load(source_config.read_text(encoding="utf-8"))
    config_path = tmp_path / name / f"{name}.yaml"
    manifest_path = tmp_path / name / f"{name}.jsonl"
    config = {
        "manifest": {
            "path": str(manifest_path),
            "verify_hashes": True,
            "require_lock": True,
        },
        "datasets": copy.deepcopy(source_payload["datasets"]),
    }
    config_path.parent.mkdir(parents=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    write_manifest(
        rows,
        manifest_path,
        environ={},
        config_path=config_path,
        upstream_dataset_locks={},
    )
    roots = dataset_roots_from_config(config_path, environ={})
    locked_rows = load_manifest(
        manifest_path,
        dataset_roots=roots,
        require_files=True,
        verify_hashes=True,
    )
    lock = validate_manifest_lock(
        manifest_path,
        locked_rows,
        config_path=config_path,
        dataset_roots=roots,
    )
    return config_path, manifest_path, lock


def _chain_fixture(tmp_path: Path) -> dict[str, Any]:
    source_config, source_manifest, source_rows, source_lock = _formal_fixture(tmp_path)
    dev_rows = [row for row in source_rows if row.split == "dev"]
    calibration_rows = dev_rows[:117]
    confirmation_rows = dev_rows[117:]
    assert len(confirmation_rows) == EXPECTED_CONFIRMATION_SAMPLES
    calibration_config, calibration_manifest, calibration_lock = _write_subset_bundle(
        tmp_path=tmp_path,
        name="calibration",
        source_config=source_config,
        rows=calibration_rows,
    )
    calibration_payload = yaml.safe_load(
        calibration_config.read_text(encoding="utf-8")
    )
    calibration_payload["experiment"] = {"run_class": CALIBRATION_RUN_CLASS}
    calibration_payload["threshold_calibration"] = {
        "preregistration_claim": build_preregistration_contract(
            config_path=calibration_config,
            nonce="11" * 32,
            expected_candidate_run_relative_paths=[
                f"candidate-runs/{candidate_id(threshold)}"
                for threshold in FROZEN_THRESHOLDS
            ],
        )
    }
    calibration_config.write_text(
        yaml.safe_dump(calibration_payload, sort_keys=False), encoding="utf-8"
    )
    calibration_manifest.unlink()
    manifest_lock_path(calibration_manifest).unlink()
    write_manifest(
        calibration_rows,
        calibration_manifest,
        environ={},
        config_path=calibration_config,
        upstream_dataset_locks={},
    )
    calibration_roots = dataset_roots_from_config(calibration_config, environ={})
    calibration_locked_rows = load_manifest(
        calibration_manifest,
        dataset_roots=calibration_roots,
        require_files=True,
        verify_hashes=True,
    )
    calibration_lock = validate_manifest_lock(
        calibration_manifest,
        calibration_locked_rows,
        config_path=calibration_config,
        dataset_roots=calibration_roots,
    )
    calibration_preregistration = write_preregistration_claim(
        calibration_config,
        expected_run_class=CALIBRATION_RUN_CLASS,
    )
    split_audit = audit_formal_split_assignments(
        source_rows,
        split_config={
            "seed": SPLIT_SEED,
            "train_ratio": TRAIN_RATIO,
            "dev_ratio": DEV_RATIO,
        },
    )
    project_root = Path(__file__).resolve().parents[2]
    source_tree = _source_tree_identity(project_root)
    roots = {
        name: str(path.resolve())
        for name, path in dataset_roots_from_config(source_config, environ={}).items()
    }
    calibration_identity, calibration_identity_sha256 = _immutable_identity(
        source_tree=source_tree,
        roots=roots,
        vote_min=1,
        config_path=calibration_config,
        manifest_path=calibration_manifest,
    )
    candidates: list[dict[str, Any]] = []
    for threshold in FROZEN_THRESHOLDS:
        checks = [
            {
                "name": name,
                "passed": index < (12 if threshold in {0.34, 0.36} else 10),
            }
            for index, name in enumerate(_constraint_names())
        ]
        if threshold == 0.34:
            checks[2]["passed"] = False
        elif threshold == 0.36:
            checks[3]["passed"] = False
        candidate_name = candidate_id(threshold)
        localization_rows = {
            f"{candidate_name}|row-{index:04d}": {
                "row_key": f"{candidate_name}|row-{index:04d}",
                "raw_vote_sha256": hashlib.sha256(
                    f"vote:{candidate_name}:{index}".encode()
                ).hexdigest(),
            }
            for index in range(1404)
        }
        localization_evidence_sha256 = freeze_module._canonical_sha256(
            localization_rows
        )
        candidates.append(
            {
                "candidate_id": candidate_name,
                "recovery_threshold": threshold,
                "run_dir": str(
                    tmp_path / "calibration" / "candidate-runs" / candidate_name
                ),
                "rows": 1404,
                "constraint_checks": checks,
                "all_constraints_passed": False,
                "selection_metrics": {
                    "clean_mean_mask_fpr": 2.5192e-05,
                    "clean_p99_mask_fpr": 4.406e-04,
                    "clean_max_mask_fpr": 0.002571,
                    "erasing_mean_mask_iou_by_ratio": {
                        "0.05": 0.900784,
                        "0.15": 0.954158,
                        "0.25": 0.967894,
                    },
                },
                "capabilities_sha256": hashlib.sha256(
                    f"cap:{threshold}".encode()
                ).hexdigest(),
                "preflight_sha256": hashlib.sha256(
                    f"pre:{threshold}".encode()
                ).hexdigest(),
                "environment_sha256": hashlib.sha256(
                    f"env:{threshold}".encode()
                ).hexdigest(),
                "raw_results_sha256": hashlib.sha256(
                    f"raw:{threshold}".encode()
                ).hexdigest(),
                "attack_input_hash_map_sha256": hashlib.sha256(
                    f"attack:{threshold}".encode()
                ).hexdigest(),
                "immutable_environment_identity_sha256": hashlib.sha256(
                    f"identity:{threshold}".encode()
                ).hexdigest(),
                "localization_artifact_evidence": {
                    "schema_version": "cogniguard_localization_artifact_evidence_v1",
                    "count": 1404,
                    "rows": localization_rows,
                    "evidence_sha256": localization_evidence_sha256,
                },
                "localization_artifact_evidence_count": 1404,
                "localization_artifact_evidence_sha256": (
                    localization_evidence_sha256
                ),
            }
        )
    calibration_report = {
        "schema_version": CALIBRATION_REPORT_SCHEMA_VERSION,
        "status": "no_candidate_satisfies_constraints",
        "run_class": "threshold_calibration_development_only",
        "development_only": True,
        "paper_eligible": False,
        "selection_split": "dev",
        "excluded_splits": ["train", "test"],
        "formal_test_rows_consumed": 0,
        "formal_config_update_performed": False,
        "evaluation_seeds": list(EVALUATION_SEEDS),
        "constraints": CONSTRAINTS,
        "config": str(calibration_config.resolve()),
        "config_sha256": sha256_file(calibration_config),
        "preregistration_claim": calibration_preregistration,
        "selected_manifest": str(calibration_manifest.resolve()),
        "selected_manifest_sha256": sha256_file(calibration_manifest),
        "selected_manifest_lock": calibration_lock,
        "selected_samples": 117,
        "unique_image_sha256": 117,
        "unique_source_families": 117,
        "formal_split_assignment_audit": split_audit,
        "candidate_metrics": candidates,
        "eligible_candidate_ids": [],
        "winner": None,
        "immutable_environment_identity": calibration_identity,
        "immutable_environment_identity_sha256": calibration_identity_sha256,
        "formal_inputs": {
            "config": str(source_config.resolve()),
            "config_sha256": sha256_file(source_config),
            "manifest": str(source_manifest.resolve()),
            "manifest_sha256": sha256_file(source_manifest),
            "manifest_lock": source_lock,
        },
    }
    calibration_report_path = tmp_path / "calibration" / "threshold_selection.json"
    _write_json(calibration_report_path, calibration_report)
    calibration_run_root = calibration_report_path.parent
    (calibration_run_root / "candidate-runs").mkdir(exist_ok=True)
    calibration_evidence, calibration_evidence_sha256 = _candidate_run_evidence(
        calibration_report
    )
    calibration_rationale = _selection_rationale_from_report(calibration_report)

    confirmation_config, confirmation_manifest, _ = _write_subset_bundle(
        tmp_path=tmp_path,
        name="confirmation",
        source_config=source_config,
        rows=confirmation_rows,
    )
    confirmation_payload = yaml.safe_load(
        confirmation_config.read_text(encoding="utf-8")
    )
    source_formal_payload = yaml.safe_load(source_config.read_text(encoding="utf-8"))
    source_formal_minimum_domains = source_formal_payload["data_requirements"][
        "minimum_domains"
    ]
    selected_domains = sorted({row.domain for row in confirmation_rows})
    effective_minimum_domains = max(
        source_formal_minimum_domains,
        CONFIRMATION_MINIMUM_DOMAINS,
    )
    confirmation_payload["experiment"] = {"run_class": CONFIRMATION_RUN_CLASS}
    confirmation_payload["data_requirements"] = {
        "minimum_domains": effective_minimum_domains
    }
    confirmation_payload["channel_vote_confirmation"] = {
        "schema_version": CONFIRMATION_CONFIG_SCHEMA_VERSION,
        "preregistration_claim": build_preregistration_contract(
            config_path=confirmation_config,
            nonce="22" * 32,
            expected_candidate_run_relative_paths=[RUN_RELATIVE_PATH],
        ),
        "source_formal_config": str(source_config.resolve()),
        "source_formal_config_sha256": sha256_file(source_config),
        "source_formal_manifest": str(source_manifest.resolve()),
        "source_formal_manifest_sha256": sha256_file(source_manifest),
        "source_formal_manifest_lock": source_lock,
        "formal_split_assignment_audit": split_audit,
        "source_calibration_config": str(calibration_config.resolve()),
        "source_calibration_config_sha256": sha256_file(calibration_config),
        "source_calibration_manifest": str(calibration_manifest.resolve()),
        "source_calibration_manifest_sha256": sha256_file(calibration_manifest),
        "source_calibration_manifest_lock": calibration_lock,
        "source_calibration_report": str(calibration_report_path.resolve()),
        "source_calibration_report_sha256": sha256_file(calibration_report_path),
        "source_calibration_run_root": str(calibration_run_root.resolve()),
        "source_calibration_run_evidence": calibration_evidence,
        "source_calibration_run_evidence_sha256": calibration_evidence_sha256,
        "source_calibration_selection_rationale": calibration_rationale,
        "confirmation_assignment_sha256": _assignment_sha256(confirmation_rows),
        "calibration_rows_excluded": 117,
        "calibration_sample_ids_sha256": hashlib.sha256(
            "\n".join(sorted(row.sample_id for row in calibration_rows)).encode()
        ).hexdigest(),
        "source_formal_minimum_domains": source_formal_minimum_domains,
        "confirmation_minimum_domains": CONFIRMATION_MINIMUM_DOMAINS,
        "effective_minimum_domains": effective_minimum_domains,
        "selected_domain_count": len(selected_domains),
        "selected_domains": selected_domains,
        "source_tree_identity": {
            "project_root": str(project_root),
            **copy.deepcopy(source_tree),
        },
    }
    confirmation_config.write_text(
        yaml.safe_dump(confirmation_payload, sort_keys=False), encoding="utf-8"
    )
    # Rebind the adjacent lock because the config hash changed when the contract was added.
    confirmation_manifest.unlink()
    manifest_lock_path(confirmation_manifest).unlink()
    write_manifest(
        confirmation_rows,
        confirmation_manifest,
        environ={},
        config_path=confirmation_config,
        upstream_dataset_locks={},
    )
    confirmation_roots = dataset_roots_from_config(confirmation_config, environ={})
    confirmation_locked_rows = load_manifest(
        confirmation_manifest,
        dataset_roots=confirmation_roots,
        require_files=True,
        verify_hashes=True,
    )
    confirmation_lock = validate_manifest_lock(
        confirmation_manifest,
        confirmation_locked_rows,
        config_path=confirmation_config,
        dataset_roots=confirmation_roots,
    )
    confirmation_preregistration = write_preregistration_claim(
        confirmation_config,
        expected_run_class=CONFIRMATION_RUN_CLASS,
    )
    confirmation_identity, confirmation_identity_sha256 = _immutable_identity(
        source_tree=source_tree,
        roots=roots,
        vote_min=2,
        config_path=confirmation_config,
        manifest_path=confirmation_manifest,
    )
    confirmation_run_root = confirmation_config.parent
    confirmation_run_dir = confirmation_run_root / RUN_RELATIVE_PATH
    confirmation_run_dir.mkdir(parents=True)
    candidate_preregistration = copy_preregistration_claim_to_run(
        confirmation_config,
        source_claim_path=Path(confirmation_preregistration["source_claim_path"]),
        destination_run=confirmation_run_dir,
        expected_run_class=CONFIRMATION_RUN_CLASS,
        expected_nonce=confirmation_preregistration["nonce"],
    )
    raw_sentinel = confirmation_run_dir / "raw-vote-sentinel.bin"
    raw_sentinel.write_bytes(b"frozen raw localization votes")
    raw_vote_evidence_sha256 = sha256_file(raw_sentinel)
    confirmation_report = {
        "schema_version": CONFIRMATION_REPORT_SCHEMA_VERSION,
        "status": "confirmation_passed",
        "confirmation_passed": True,
        "all_constraints_passed": True,
        "development_only": True,
        "paper_eligible": False,
        "selection_split": "dev",
        "excluded_splits": ["train", "test"],
        "formal_test_rows_consumed": 0,
        "parameter_selection_performed": False,
        "fallback_candidate_considered": False,
        "decision": "pass",
        "selection_rule": SELECTION_RULE,
        "candidate": {
            "candidate_id": CANDIDATE_ID,
            **copy.deepcopy(TEST_REQUIRED_CAPABILITIES),
            "run_relative_path": RUN_RELATIVE_PATH,
        },
        "required_capabilities": copy.deepcopy(TEST_REQUIRED_CAPABILITIES),
        "samples": EXPECTED_CONFIRMATION_SAMPLES,
        "rows": EXPECTED_CONFIRMATION_ROWS,
        "evaluation_seeds": list(EVALUATION_SEEDS),
        "constraints": CONSTRAINTS,
        "constraint_checks": [
            {"name": name, "passed": True} for name in _constraint_names()
        ],
        "config": str(confirmation_config.resolve()),
        "config_sha256": sha256_file(confirmation_config),
        "preregistration_claim": confirmation_preregistration,
        "candidate_preregistration_claim": candidate_preregistration,
        "manifest": str(confirmation_manifest.resolve()),
        "manifest_sha256": sha256_file(confirmation_manifest),
        "manifest_lock": confirmation_lock,
        "domain_coverage": {
            "source_formal_minimum_domains": source_formal_minimum_domains,
            "confirmation_minimum_domains": CONFIRMATION_MINIMUM_DOMAINS,
            "effective_minimum_domains": effective_minimum_domains,
            "selected_domain_count": len(selected_domains),
            "selected_domains": selected_domains,
        },
        "run_dir": str(confirmation_run_dir.resolve()),
        "capabilities_sha256": "1" * 64,
        "preflight_sha256": "2" * 64,
        "environment_sha256": "3" * 64,
        "raw_results_sha256": "4" * 64,
        "attack_input_hash_map_sha256": "5" * 64,
        "immutable_environment_identity": confirmation_identity,
        "immutable_environment_identity_sha256": confirmation_identity_sha256,
        "raw_localization_vote_artifacts": {
            "count": EXPECTED_CONFIRMATION_ROWS,
            "threshold": 510,
            "dtype": "uint16",
            "encoding": "lossless_png_16bit_grayscale_I;16",
            "allowed_values": [0, 255, 510, 765],
            "evidence_sha256": raw_vote_evidence_sha256,
        },
        "source_evidence": {
            "formal_manifest_lock": source_lock,
            "calibration_manifest_lock": calibration_lock,
            "calibration_report_sha256": sha256_file(calibration_report_path),
            "calibration_run_evidence_sha256": calibration_evidence_sha256,
            "formal_split_assignment_audit": split_audit,
            "source_tree_identity": {
                "project_root": str(project_root),
                **copy.deepcopy(source_tree),
            },
        },
    }
    confirmation_report_path = (
        confirmation_run_root / "channel_vote_confirmation_report.json"
    )
    _write_json(confirmation_report_path, confirmation_report)
    return {
        "source_config": source_config,
        "source_manifest": source_manifest,
        "source_lock": source_lock,
        "calibration_report_path": calibration_report_path,
        "calibration_run_root": calibration_run_root,
        "calibration_canonical": calibration_report,
        "confirmation_report_path": confirmation_report_path,
        "confirmation_run_root": confirmation_run_root,
        "confirmation_canonical": confirmation_report,
        "raw_sentinel": raw_sentinel,
        "raw_sentinel_sha256": raw_vote_evidence_sha256,
        "source_tree": source_tree,
    }


def _install_full_reanalysis_mocks(
    monkeypatch: pytest.MonkeyPatch,
    fixture: dict[str, Any],
) -> dict[str, int]:
    calls = {"calibration": 0, "confirmation": 0}

    def analyze_calibration(
        config_path: Path, *, run_root: Path | None = None
    ) -> dict[str, Any]:
        calls["calibration"] += 1
        assert run_root == fixture["calibration_run_root"]
        assert config_path == Path(fixture["calibration_canonical"]["config"])
        return copy.deepcopy(fixture["calibration_canonical"])

    def analyze_confirmation(
        config_path: Path, *, run_root: Path | None = None
    ) -> dict[str, Any]:
        calls["confirmation"] += 1
        assert run_root == fixture["confirmation_run_root"]
        assert config_path == Path(fixture["confirmation_canonical"]["config"])
        return copy.deepcopy(fixture["confirmation_canonical"])

    monkeypatch.setattr(freeze_module, "analyze_threshold_calibration", analyze_calibration)
    monkeypatch.setattr(
        freeze_module, "analyze_channel_vote_confirmation", analyze_confirmation
    )
    monkeypatch.setattr(
        freeze_module,
        "_source_tree_identity",
        lambda _project_root: copy.deepcopy(fixture["source_tree"]),
    )
    return calls


def _freeze(
    fixture: dict[str, Any],
    tmp_path: Path,
) -> tuple[dict[str, Any], Path, Path]:
    output_config = tmp_path / "selected" / "paper_channel_vote_selected.yaml"
    output_manifest = tmp_path / "selected" / "paper_channel_vote_selected.jsonl"
    result = freeze_channel_vote_formal_config(
        fixture["source_config"],
        calibration_report=fixture["calibration_report_path"],
        calibration_run_root=fixture["calibration_run_root"],
        confirmation_report=fixture["confirmation_report_path"],
        confirmation_run_root=fixture["confirmation_run_root"],
        output_config=output_config,
        output_manifest=output_manifest,
        expected_formal_samples=FIXTURE_FORMAL_SAMPLES,
    )
    return result, output_config, output_manifest


def test_calibration_raw_vote_evidence_is_canonically_bound(tmp_path: Path) -> None:
    fixture = _chain_fixture(tmp_path)
    report = copy.deepcopy(fixture["calibration_canonical"])

    evidence, evidence_sha256 = _candidate_run_evidence(report)

    assert len(evidence) == len(FROZEN_THRESHOLDS)
    assert len(evidence_sha256) == 64
    first_candidate = report["candidate_metrics"][0]
    first_rows = first_candidate["localization_artifact_evidence"]["rows"]
    first_row = first_rows[next(iter(first_rows))]
    first_row["raw_vote_sha256"] = "f" * 64
    with pytest.raises(ChannelVoteFormalFreezeError, match="unauthenticated"):
        _candidate_run_evidence(report)


def test_success_chain_freezes_byte_equal_manifest_and_replays_both_analyzers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _chain_fixture(tmp_path)
    calls = _install_full_reanalysis_mocks(monkeypatch, fixture)

    result, output_config, output_manifest = _freeze(fixture, tmp_path)

    assert calls == {"calibration": 2, "confirmation": 2}
    assert result["status"] == "created"
    assert output_manifest.read_bytes() == fixture["source_manifest"].read_bytes()
    selected = yaml.safe_load(output_config.read_text(encoding="utf-8"))
    selection = selected["formal_selection"]
    assert selection["schema_version"] == FORMAL_SELECTION_SCHEMA_VERSION
    assert selection["selection_source"] == "development_only_channel_vote_confirmation"
    assert selection["formal_test_rows_consumed"] == 0
    assert selection["selected_parameters"] == TEST_REQUIRED_CAPABILITIES
    assert selection["confirmation"]["domain_coverage"] == fixture[
        "confirmation_canonical"
    ]["domain_coverage"]
    assert (
        selection["calibration_source_tree_identity_version"]
        == fixture["source_tree"]["identity_version"]
    )
    assert selection["calibration_source_tree_scope"] == fixture["source_tree"]["scope"]
    method = next(row for row in selected["methods"] if row["id"] == "editguard_wrapper")
    assert method["required_capabilities"] == TEST_REQUIRED_CAPABILITIES
    assert validate_frozen_channel_vote_formal_config(
        output_config,
        expected_formal_samples=FIXTURE_FORMAL_SAMPLES,
    ) == TEST_REQUIRED_CAPABILITIES
    assert calls == {"calibration": 3, "confirmation": 3}


def test_forged_pass_report_is_rejected_by_canonical_full_reanalysis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _chain_fixture(tmp_path)
    _install_full_reanalysis_mocks(monkeypatch, fixture)
    forged = copy.deepcopy(fixture["confirmation_canonical"])
    forged["constraint_checks"][0]["observed"] = 0.0
    _write_json(fixture["confirmation_report_path"], forged)

    with pytest.raises(
        ChannelVoteFormalFreezeError,
        match="differs from complete raw-artifact reanalysis",
    ):
        _freeze(fixture, tmp_path)


def test_changed_raw_artifact_is_rejected_during_required_reanalysis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _chain_fixture(tmp_path)
    calls = _install_full_reanalysis_mocks(monkeypatch, fixture)

    def analyze_confirmation(
        config_path: Path, *, run_root: Path | None = None
    ) -> dict[str, Any]:
        calls["confirmation"] += 1
        if sha256_file(fixture["raw_sentinel"]) != fixture["raw_sentinel_sha256"]:
            raise ChannelVoteConfirmationError(
                "raw localization vote artifact SHA-256 changed"
            )
        return copy.deepcopy(fixture["confirmation_canonical"])

    monkeypatch.setattr(
        freeze_module, "analyze_channel_vote_confirmation", analyze_confirmation
    )
    fixture["raw_sentinel"].write_bytes(b"tampered raw localization votes")

    with pytest.raises(
        ChannelVoteFormalFreezeError,
        match="raw localization vote artifact SHA-256 changed",
    ):
        _freeze(fixture, tmp_path)


def test_run_local_preregistration_claim_tamper_blocks_formal_freeze(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _chain_fixture(tmp_path)
    _install_full_reanalysis_mocks(monkeypatch, fixture)
    run_claim = (
        fixture["confirmation_run_root"]
        / RUN_RELATIVE_PATH
        / "preregistration-claim.json"
    )
    run_claim.chmod(0o644)
    claim = json.loads(run_claim.read_text(encoding="utf-8"))
    claim["nonce"] = "ff" * 32
    run_claim.write_text(json.dumps(claim, sort_keys=True), encoding="utf-8")

    with pytest.raises(
        ChannelVoteFormalFreezeError,
        match="preregistration evidence is invalid",
    ):
        _freeze(fixture, tmp_path)


def test_source_tree_identity_drift_between_runs_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _chain_fixture(tmp_path)
    changed = copy.deepcopy(fixture["confirmation_canonical"])
    changed["immutable_environment_identity"]["source_tree_sha256"] = "0" * 64
    changed["immutable_environment_identity_sha256"] = hashlib.sha256(
        json.dumps(
            changed["immutable_environment_identity"],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    fixture["confirmation_canonical"] = changed
    _write_json(fixture["confirmation_report_path"], changed)
    _install_full_reanalysis_mocks(monkeypatch, fixture)

    with pytest.raises(
        ChannelVoteFormalFreezeError,
        match="source-tree identities are not identical",
    ):
        _freeze(fixture, tmp_path)


def test_non_source_runtime_invariant_drift_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _chain_fixture(tmp_path)
    changed = copy.deepcopy(fixture["confirmation_canonical"])
    changed["immutable_environment_identity"]["packages"]["numpy"] = "9.9.9"
    changed["immutable_environment_identity_sha256"] = hashlib.sha256(
        json.dumps(
            changed["immutable_environment_identity"],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    fixture["confirmation_canonical"] = changed
    _write_json(fixture["confirmation_report_path"], changed)
    _install_full_reanalysis_mocks(monkeypatch, fixture)

    with pytest.raises(
        ChannelVoteFormalFreezeError,
        match="immutable runtime invariants drifted",
    ):
        _freeze(fixture, tmp_path)


def test_output_collision_refuses_overwrite_before_analysis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _chain_fixture(tmp_path)
    calls = _install_full_reanalysis_mocks(monkeypatch, fixture)
    output_config = tmp_path / "selected" / "paper_channel_vote_selected.yaml"
    output_manifest = tmp_path / "selected" / "paper_channel_vote_selected.jsonl"
    output_config.parent.mkdir(parents=True)
    output_config.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        freeze_channel_vote_formal_config(
            fixture["source_config"],
            calibration_report=fixture["calibration_report_path"],
            calibration_run_root=fixture["calibration_run_root"],
            confirmation_report=fixture["confirmation_report_path"],
            confirmation_run_root=fixture["confirmation_run_root"],
            output_config=output_config,
            output_manifest=output_manifest,
            expected_formal_samples=FIXTURE_FORMAL_SAMPLES,
        )
    assert output_config.read_text(encoding="utf-8") == "sentinel\n"
    assert calls == {"calibration": 0, "confirmation": 0}


def test_validator_rejects_capability_drift_even_if_both_declarations_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _chain_fixture(tmp_path)
    _install_full_reanalysis_mocks(monkeypatch, fixture)
    _, output_config, _ = _freeze(fixture, tmp_path)
    selected = yaml.safe_load(output_config.read_text(encoding="utf-8"))
    selected["formal_selection"]["selected_parameters"][
        "localization_channel_vote_min"
    ] = 1
    method = next(row for row in selected["methods"] if row["id"] == "editguard_wrapper")
    method["required_capabilities"]["localization_channel_vote_min"] = 1
    output_config.write_text(yaml.safe_dump(selected, sort_keys=False), encoding="utf-8")

    with pytest.raises(
        ChannelVoteFormalFreezeError,
        match="differs from the deterministic confirmation freeze product",
    ):
        validate_frozen_channel_vote_formal_config(
            output_config,
            expected_formal_samples=FIXTURE_FORMAL_SAMPLES,
        )


def test_validator_rejects_selected_domain_coverage_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _chain_fixture(tmp_path)
    _install_full_reanalysis_mocks(monkeypatch, fixture)
    _, output_config, _ = _freeze(fixture, tmp_path)
    selected = yaml.safe_load(output_config.read_text(encoding="utf-8"))
    selected["formal_selection"]["confirmation"]["domain_coverage"][
        "selected_domain_count"
    ] -= 1
    output_config.write_text(
        yaml.safe_dump(selected, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(
        ChannelVoteFormalFreezeError,
        match="differs from the deterministic confirmation freeze product",
    ):
        validate_frozen_channel_vote_formal_config(
            output_config,
            expected_formal_samples=FIXTURE_FORMAL_SAMPLES,
        )
