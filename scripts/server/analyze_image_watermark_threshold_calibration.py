#!/usr/bin/env python3
"""Validate and select a v2 recovery threshold from development-only runs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import math
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import yaml
from PIL import Image

from protection.supporting.image_watermark.experiments.attacks import (
    AttackSpec,
    apply_traditional_attack,
    truth_mask_from_half_open_bbox,
)
from protection.supporting.image_watermark.experiments.manifest import (
    ImageSample,
    dataset_roots_from_config,
    load_manifest,
    manifest_path_from_config,
    validate_manifest_lock,
)
from protection.supporting.image_watermark.experiments.localization_artifacts import (
    RAW_LOCALIZATION_VOTE_ENCODING,
    RAW_LOCALIZATION_VOTE_FILENAME,
    LocalizationArtifactError,
    validate_verify_localization_artifacts,
)
from protection.supporting.image_watermark.experiments.metrics import mask_metrics
from scripts.server.build_image_watermark_threshold_calibration import (
    ATTACK_CONDITIONS,
    ATTACK_ARTIFACT_RETENTION,
    CONSTRAINTS,
    EVALUATION_SEEDS,
    ERASING_RATIOS,
    EXPECTED_SAMPLES,
    FIXED_PARAMETERS,
    FROZEN_THRESHOLDS,
    LOCALIZATION_MASK_CONTRACT,
    DEFAULT_SEED,
    REQUIRED_ATTACK_RUNTIME,
    RUN_CLASS,
    SCHEMA_VERSION,
    SELECTION_SPLIT,
    audit_formal_split_assignments,
    candidate_id,
    sha256_file,
)
from scripts.server.image_watermark_preregistration import (
    RUN_COPY_FILENAME,
    PreregistrationError,
    validate_preregistration_claim,
    validate_preregistration_contract,
)


REPORT_SCHEMA_VERSION = "cogniguard_image_threshold_selection_v2"
EXPECTED_ATTACK_IDS = (*ATTACK_CONDITIONS,)
EXPECTED_FIXED_PARAMETERS = dict(FIXED_PARAMETERS)
LOCALIZATION_CONTRACT_FIELDS = tuple(LOCALIZATION_MASK_CONTRACT)
RAW_LOCALIZATION_VOTE_VALUES = (0, 255, 510, 765)
EXPECTED_SERVICE_IMAGE_SHAPE = (512, 512)
EXPECTED_ATTACK_MODEL_ID = "stable-diffusion-v1-5/stable-diffusion-inpainting"
LOCALIZATION_ARTIFACT_EVIDENCE_SCHEMA_VERSION = (
    "cogniguard_localization_artifact_evidence_v1"
)
SUPPORTED_VERIFY_IMAGE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


class ThresholdCalibrationError(RuntimeError):
    """Raised when a calibration artifact violates the frozen protocol."""


def _validate_current_attack_runtime(
    required: dict[str, str],
) -> dict[str, str]:
    """Bind recomputation to the same pinned image/array runtime as generation."""

    if required != REQUIRED_ATTACK_RUNTIME:
        raise ThresholdCalibrationError(
            "Analyzer attack-runtime contract differs from the frozen protocol."
        )
    observed: dict[str, str] = {}
    for distribution, expected in required.items():
        try:
            observed[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ThresholdCalibrationError(
                f"Analyzer runtime package is missing: {distribution}=={expected}"
            ) from exc
    if observed != required:
        raise ThresholdCalibrationError(
            f"Analyzer runtime is not frozen: required={required}, observed={observed}."
        )
    return observed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze completed development-only threshold candidate runs."
    )
    parser.add_argument("--config", required=True, help="Calibration YAML.")
    parser.add_argument(
        "--run-root",
        default=None,
        help="Run root containing candidate-runs/; defaults to the config directory.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Fresh JSON report path; defaults to RUN_ROOT/threshold_selection.json.",
    )
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ThresholdCalibrationError(f"Required JSON artifact is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ThresholdCalibrationError(
            f"Invalid JSON artifact: {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ThresholdCalibrationError(f"JSON artifact is not an object: {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ThresholdCalibrationError(f"Required JSONL artifact is missing: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ThresholdCalibrationError(
                    f"Invalid JSON at {path}:{line_number}: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise ThresholdCalibrationError(
                    f"JSONL row is not an object at {path}:{line_number}."
                )
            rows.append(row)
    return rows


def _finite_float(row: dict[str, Any], field: str) -> float:
    value = row.get(field)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise ThresholdCalibrationError(
            f"Calibration row has no finite {field}: {row.get('row_key')}"
        )
    return float(value)


def _unit_interval(row: dict[str, Any], field: str) -> float:
    value = _finite_float(row, field)
    if not 0.0 <= value <= 1.0:
        raise ThresholdCalibrationError(
            f"Calibration row {field} is outside [0, 1]: {row.get('row_key')}"
        )
    return value


def _binary_metric(row: dict[str, Any], field: str) -> float:
    value = _unit_interval(row, field)
    if value not in {0.0, 1.0}:
        raise ThresholdCalibrationError(
            f"Calibration row {field} is not binary: {row.get('row_key')}"
        )
    return value


def _mean(rows: Iterable[dict[str, Any]], field: str) -> float:
    values = [_unit_interval(row, field) for row in rows]
    if not values:
        raise ThresholdCalibrationError(f"Cannot aggregate empty metric: {field}")
    return float(np.mean(np.asarray(values, dtype=np.float64)))


def _metric_summary(rows: list[dict[str, Any]], field: str) -> dict[str, float]:
    values = np.asarray([_unit_interval(row, field) for row in rows], dtype=np.float64)
    return {
        "mean": float(np.mean(values)),
        "p01": float(np.quantile(values, 0.01, method="linear")),
        "p10": float(np.quantile(values, 0.10, method="linear")),
        "median": float(np.median(values)),
        "p99": float(np.quantile(values, 0.99, method="linear")),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def _constraint(
    *, name: str, observed: float, operator: str, limit: float
) -> dict[str, Any]:
    if operator == "<=":
        passed = observed <= limit
    elif operator == ">=":
        passed = observed >= limit
    else:
        raise ValueError(f"Unsupported constraint operator: {operator}")
    return {
        "name": name,
        "observed": observed,
        "operator": operator,
        "limit": limit,
        "passed": bool(passed),
    }


def _validate_calibration_config(
    config_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ThresholdCalibrationError("Calibration YAML root must be a mapping.")
    experiment = payload.get("experiment") or {}
    contract = payload.get("threshold_calibration") or {}
    if (
        not isinstance(experiment, dict)
        or not isinstance(contract, dict)
        or experiment.get("run_class") != RUN_CLASS
        or experiment.get("strict_paper_mode") is not True
        or experiment.get("fail_fast") is not True
        or experiment.get("development_only") is not True
        or experiment.get("paper_eligible") is not False
        or experiment.get("split") != SELECTION_SPLIT
        or experiment.get("max_samples") != EXPECTED_SAMPLES
        or contract.get("schema_version") != SCHEMA_VERSION
        or contract.get("development_only") is not True
        or contract.get("paper_eligible") is not False
        or contract.get("selection_split") != SELECTION_SPLIT
        or contract.get("formal_test_rows_consumed") != 0
        or contract.get("formal_config_update_performed") is not False
        or contract.get("formal_config_mutation_allowed") is not False
        or contract.get("expected_samples") != EXPECTED_SAMPLES
        or contract.get("selection_seed") != DEFAULT_SEED
        or contract.get("expected_rows_per_candidate")
        != EXPECTED_SAMPLES * len(EXPECTED_ATTACK_IDS) * len(EVALUATION_SEEDS)
        or contract.get("selected_unique_sha256") != EXPECTED_SAMPLES
        or contract.get("selected_unique_source_families") != EXPECTED_SAMPLES
    ):
        raise ThresholdCalibrationError(
            "YAML is not a frozen development-only threshold-calibration config."
        )
    if set(contract.get("excluded_splits") or []) != {"train", "test"}:
        raise ThresholdCalibrationError(
            "Calibration config does not exclude train/test."
        )
    if contract.get("attack_conditions") != list(EXPECTED_ATTACK_IDS):
        raise ThresholdCalibrationError("Calibration attack conditions are not frozen.")
    candidate_runs = contract.get("candidate_runs") or []
    if not isinstance(candidate_runs, list) or not all(
        isinstance(row, dict) for row in candidate_runs
    ):
        raise ThresholdCalibrationError("Calibration candidate runs are malformed.")
    try:
        candidate_thresholds = [
            float(row["recovery_threshold"]) for row in candidate_runs
        ]
        declared_thresholds = [
            float(value) for value in contract.get("candidate_thresholds") or []
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ThresholdCalibrationError(
            "Calibration candidate thresholds are malformed."
        ) from exc
    if (
        not candidate_thresholds
        or any(
            not math.isfinite(value) or not 0.0 < value < 1.0
            for value in candidate_thresholds
        )
        or candidate_thresholds != list(FROZEN_THRESHOLDS)
        or declared_thresholds != candidate_thresholds
        or any(
            row.get("candidate_id") != candidate_id(threshold)
            for row, threshold in zip(candidate_runs, candidate_thresholds, strict=True)
        )
    ):
        raise ThresholdCalibrationError(
            "Calibration candidate grid differs from the frozen declarations."
        )
    if (
        experiment.get("traditional_attack_artifact_retention")
        != ATTACK_ARTIFACT_RETENTION
        or contract.get("traditional_attack_artifact_retention")
        != ATTACK_ARTIFACT_RETENTION
    ):
        raise ThresholdCalibrationError(
            "Calibration did not preserve the frozen attack-artifact retention policy."
        )
    if (
        experiment.get("required_attack_runtime") != REQUIRED_ATTACK_RUNTIME
        or contract.get("required_attack_runtime") != REQUIRED_ATTACK_RUNTIME
    ):
        raise ThresholdCalibrationError(
            "Calibration did not preserve the frozen attack runtime."
        )
    if contract.get("fixed_parameters") != EXPECTED_FIXED_PARAMETERS:
        raise ThresholdCalibrationError(
            "Calibration changed a fixed non-calibrated service parameter."
        )
    frozen_inputs = (
        (
            "formal config",
            contract.get("source_formal_config"),
            contract.get("source_formal_config_sha256"),
        ),
        (
            "formal manifest",
            contract.get("source_formal_manifest"),
            contract.get("source_formal_manifest_sha256"),
        ),
    )
    for label, raw_path, expected_sha256 in frozen_inputs:
        path = Path(str(raw_path or "")).resolve()
        if not raw_path or not path.is_file() or expected_sha256 != sha256_file(path):
            raise ThresholdCalibrationError(
                f"Frozen source {label} is missing or changed: {path}"
            )
    if contract.get("evaluation_seeds") != list(EVALUATION_SEEDS):
        raise ThresholdCalibrationError(
            "Calibration evaluation seeds differ from the frozen protocol."
        )

    formal_config = Path(str(contract.get("source_formal_config") or "")).resolve()
    formal_manifest = Path(str(contract.get("source_formal_manifest") or "")).resolve()
    try:
        formal_payload = yaml.safe_load(formal_config.read_text(encoding="utf-8")) or {}
        if not isinstance(formal_payload, dict):
            raise ValueError("Frozen formal config root must be a mapping.")
        formal_rows = load_manifest(
            formal_manifest,
            dataset_roots=dataset_roots_from_config(formal_config, environ={}),
            require_files=True,
            verify_hashes=True,
        )
        formal_roots = dataset_roots_from_config(formal_config, environ={})
        formal_lock_audit = validate_manifest_lock(
            formal_manifest,
            formal_rows,
            config_path=formal_config,
            dataset_roots=formal_roots,
        )
        formal_split_audit = audit_formal_split_assignments(
            formal_rows, split_config=dict(formal_payload.get("split") or {})
        )
    except (OSError, TypeError, ValueError) as exc:
        raise ThresholdCalibrationError(
            f"Frozen formal split assignments failed independent validation: {exc}"
        ) from exc
    if formal_split_audit != contract.get("formal_split_assignment_audit"):
        raise ThresholdCalibrationError(
            "Frozen formal split-assignment digest differs from the calibration bundle."
        )
    if formal_lock_audit != contract.get("source_formal_manifest_lock"):
        raise ThresholdCalibrationError(
            "Frozen formal manifest-lock evidence differs from the calibration bundle."
        )
    requirements = payload.get("data_requirements") or {}
    manifest = payload.get("manifest") or {}
    if (
        not isinstance(requirements, dict)
        or requirements.get("expected_total_samples") != EXPECTED_SAMPLES
        or requirements.get("minimum_selected_samples") != EXPECTED_SAMPLES
        or not isinstance(manifest, dict)
        or manifest.get("verify_hashes") is not True
        or manifest.get("require_lock") is not True
    ):
        raise ThresholdCalibrationError(
            "Calibration data requirements are not exact or hash verification is disabled."
        )
    implementation = contract.get("traditional_attack_implementation") or {}
    expected_attacks_path = (
        Path(__file__).resolve().parents[2]
        / 'protection' / 'image_watermark'
        / "experiments"
        / "attacks.py"
    ).resolve()
    if (
        not isinstance(implementation, dict)
        or Path(str(implementation.get("path") or "")).resolve()
        != expected_attacks_path
        or not expected_attacks_path.is_file()
        or implementation.get("sha256") != sha256_file(expected_attacks_path)
    ):
        raise ThresholdCalibrationError(
            "Shared attacks.py path or SHA-256 differs from the frozen bundle."
        )
    try:
        validate_preregistration_contract(
            contract.get("preregistration_claim") or {},
            config_path=config_path,
        )
    except PreregistrationError as exc:
        raise ThresholdCalibrationError(
            f"Calibration preregistration contract is invalid: {exc}"
        ) from exc
    return payload, contract


def _validate_selected_manifest(
    config_path: Path,
    contract: dict[str, Any],
) -> tuple[list[ImageSample], Path, dict[str, Any]]:
    manifest_path = manifest_path_from_config(config_path, environ={})
    roots = dataset_roots_from_config(config_path, environ={})
    try:
        rows = load_manifest(
            manifest_path,
            dataset_roots=roots,
            require_files=True,
            verify_hashes=True,
        )
        manifest_lock_audit = validate_manifest_lock(
            manifest_path,
            rows,
            config_path=config_path,
            dataset_roots=roots,
        )
    except (OSError, ValueError) as exc:
        raise ThresholdCalibrationError(
            f"Selected dev manifest failed strict validation: {exc}"
        ) from exc
    if len(rows) != EXPECTED_SAMPLES:
        raise ThresholdCalibrationError(
            f"Selected dev manifest has {len(rows)} rows; expected {EXPECTED_SAMPLES}."
        )
    if {row.split for row in rows} != {SELECTION_SPLIT}:
        raise ThresholdCalibrationError("Selected manifest contains non-dev rows.")
    if len({row.sha256 for row in rows}) != EXPECTED_SAMPLES:
        raise ThresholdCalibrationError(
            "Selected manifest content hashes are not unique."
        )
    if len({row.source_family for row in rows}) != EXPECTED_SAMPLES:
        raise ThresholdCalibrationError(
            "Selected manifest source families are not unique."
        )
    if sha256_file(manifest_path) != contract.get("selected_manifest_sha256"):
        raise ThresholdCalibrationError(
            "Selected manifest SHA-256 does not match YAML."
        )
    canonical = sorted(rows, key=lambda row: (row.source_dataset, row.sample_id))
    if [row.sample_id for row in rows] != [row.sample_id for row in canonical]:
        raise ThresholdCalibrationError("Selected manifest order is not canonical.")
    actual_ids_sha = hashlib.sha256(
        "\n".join(sorted(row.sample_id for row in rows)).encode("utf-8")
    ).hexdigest()
    if actual_ids_sha != contract.get("selected_sample_ids_sha256"):
        raise ThresholdCalibrationError("Selected sample-id hash does not match YAML.")
    dataset_counts: dict[str, int] = {}
    for row in rows:
        dataset_counts[row.source_dataset] = (
            dataset_counts.get(row.source_dataset, 0) + 1
        )
    if dataset_counts != contract.get("selected_dataset_counts"):
        raise ThresholdCalibrationError("Selected dataset counts do not match YAML.")
    if sorted(dataset_counts) != contract.get("selected_datasets"):
        raise ThresholdCalibrationError("Selected dataset names do not match YAML.")
    if sorted({row.domain for row in rows}) != contract.get("selected_domains"):
        raise ThresholdCalibrationError("Selected domains do not match YAML.")
    return rows, manifest_path, manifest_lock_audit


def _validate_run_rows(
    rows: list[dict[str, Any]],
    *,
    samples_by_id: dict[str, ImageSample],
    evaluation_seeds: tuple[int, ...],
) -> dict[str, list[dict[str, Any]]]:
    sample_ids = set(samples_by_id)
    expected_rows = EXPECTED_SAMPLES * len(EXPECTED_ATTACK_IDS) * len(evaluation_seeds)
    if len(rows) != expected_rows:
        raise ThresholdCalibrationError(
            f"Candidate has {len(rows)} result rows; expected {expected_rows}."
        )
    row_keys = [str(row.get("row_key") or "") for row in rows]
    if any(not key for key in row_keys) or len(set(row_keys)) != len(row_keys):
        raise ThresholdCalibrationError(
            "Candidate row_key values are missing or duplicated."
        )
    if any(
        row.get("status") != "ok"
        or row.get("pipeline_success") != 1.0
        or row.get("implementation_level") != "real_pipeline"
        or row.get("run_class") != RUN_CLASS
        or row.get("paper_eligible") is not False
        or row.get("split") != SELECTION_SPLIT
        or row.get("method_id") != "editguard_wrapper"
        or row.get("traditional_attack_artifact_retention") != ATTACK_ARTIFACT_RETENTION
        or isinstance(row.get("seed"), bool)
        or not isinstance(row.get("seed"), int)
        or int(row["seed"]) not in evaluation_seeds
        for row in rows
    ):
        raise ThresholdCalibrationError(
            "Candidate contains failed, non-real, non-dev, or misclassified rows."
        )
    if {str(row.get("sample_id") or "") for row in rows} != sample_ids:
        raise ThresholdCalibrationError(
            "Candidate sample set differs from dev manifest."
        )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    combinations: set[tuple[str, int, str]] = set()
    verify_job_ids: set[str] = set()
    for row in rows:
        attack_id = str(row.get("attack_id") or "")
        sample_id = str(row.get("sample_id") or "")
        seed = int(row["seed"])
        expected_row_key = f"editguard_wrapper|{sample_id}|{seed}|{attack_id}"
        if row.get("row_key") != expected_row_key:
            raise ThresholdCalibrationError(
                "Candidate row_key differs from the frozen benchmark key: "
                f"observed={row.get('row_key')!r}, expected={expected_row_key!r}"
            )
        sample = samples_by_id[sample_id]
        if (
            row.get("image_sha256") != sample.sha256
            or row.get("source_dataset") != sample.source_dataset
        ):
            raise ThresholdCalibrationError(
                "Candidate row source identity differs from the dev manifest: "
                f"{row.get('row_key')}"
            )
        if attack_id not in EXPECTED_ATTACK_IDS:
            raise ThresholdCalibrationError(f"Unexpected attack id: {attack_id}")
        verify_job_id = str(row.get("verify_job_id") or "")
        if (
            not re.fullmatch(r"verify_[A-Za-z0-9._-]+", verify_job_id)
            or verify_job_id in verify_job_ids
        ):
            raise ThresholdCalibrationError(
                f"Candidate row has invalid or duplicate verify_job_id: {row.get('row_key')}"
            )
        verify_job_ids.add(verify_job_id)
        attacked_sha256 = str(row.get("attacked_image_sha256") or "")
        if len(attacked_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in attacked_sha256
        ):
            raise ThresholdCalibrationError(
                f"Candidate row has no valid attacked-image SHA-256: {row.get('row_key')}"
            )
        if attack_id != "clean" and (
            row.get("attacked_image_retained") is not False
            or row.get("attacked_image_path") is not None
        ):
            raise ThresholdCalibrationError(
                f"Erasing artifact was retained despite hash_only policy: {row.get('row_key')}"
            )
        for metric in (
            "mask_fpr",
            "predicted_tamper_area_ratio",
            "source_registry_match",
        ):
            _unit_interval(row, metric)
        _binary_metric(row, "predicted_mask_nonempty")
        _binary_metric(row, "image_tamper_detected")
        if attack_id != "clean":
            for metric in ("mask_iou", "mask_dice", "mask_precision", "mask_recall"):
                _unit_interval(row, metric)
        combination = (sample_id, seed, attack_id)
        if combination in combinations:
            raise ThresholdCalibrationError(
                f"Duplicate sample/seed/attack result: {sample_id}/{seed}/{attack_id}"
            )
        combinations.add(combination)
        grouped[attack_id].append(row)
    expected_combinations = {
        (sample_id, seed, attack_id)
        for sample_id in sample_ids
        for seed in evaluation_seeds
        for attack_id in EXPECTED_ATTACK_IDS
    }
    if combinations != expected_combinations or any(
        len(grouped[attack_id]) != EXPECTED_SAMPLES * len(evaluation_seeds)
        for attack_id in EXPECTED_ATTACK_IDS
    ):
        raise ThresholdCalibrationError("A candidate attack cell is incomplete.")
    return grouped


_DYNAMIC_CAPABILITY_FIELDS = {
    "recovery_threshold",
    "registry_codebook_records",
    "registry_codebook_min_distance",
}
_IMMUTABLE_ENVIRONMENT_FIELDS = (
    "schema_version",
    "python",
    "platform",
    "packages",
    "gpu",
    "checkpoints",
    "git_commit",
    "git_status_sha256",
    "source_tree_sha256",
    "source_tree_file_count",
    "source_tree_identity_version",
    "source_tree_scope",
    "config_path",
    "config_sha256",
    "manifest_path",
    "manifest_sha256",
    "resolved_dataset_roots",
    "dataset_manifest_override_used",
    "dataset_roots_override_used",
    "registry_secret_recorded",
    "methods",
    "strict_paper_mode",
    "run_class",
    "paper_eligible",
    "evaluation_split",
    "input_manifest_audit",
    "manifest_lock",
    "traditional_attack_runtime",
    "deterministic_runtime_identity",
    "asset_manifest_identity",
    "aigc_attack_runtime_identity",
    "registry_secret_identity_fingerprint",
)


def _fixed_capabilities(capabilities: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in sorted(capabilities.items())
        if key not in _DYNAMIC_CAPABILITY_FIELDS
    }


def _immutable_environment_identity(
    environment: dict[str, Any], *, startup_capabilities: dict[str, Any]
) -> dict[str, Any]:
    missing = [
        field for field in _IMMUTABLE_ENVIRONMENT_FIELDS if field not in environment
    ]
    if missing:
        raise ThresholdCalibrationError(
            "Candidate environment omits immutable identity fields: "
            + ", ".join(missing)
        )
    fingerprint = environment.get("registry_secret_identity_fingerprint")
    if type(fingerprint) is not str or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
        raise ThresholdCalibrationError(
            "Candidate environment has no valid registry-secret identity fingerprint."
        )
    for field in (
        "deterministic_runtime_identity",
        "asset_manifest_identity",
        "aigc_attack_runtime_identity",
    ):
        if not isinstance(environment.get(field), dict) or not environment[field]:
            raise ThresholdCalibrationError(
                f"Candidate environment {field} must be a non-empty mapping."
            )
    forbidden_secret_fields = {
        "registry_secret",
        "registry_secret_value",
        "registry_hmac_key",
        "sce_locguard_registry_secret",
    }
    leaked_fields = sorted(forbidden_secret_fields.intersection(environment))
    if leaked_fields:
        raise ThresholdCalibrationError(
            "Candidate environment leaked a raw registry secret field: "
            + ", ".join(leaked_fields)
        )
    all_capabilities = environment.get("capabilities")
    declared_contract = environment.get("capabilities_contract")
    if not isinstance(all_capabilities, dict) or not isinstance(
        declared_contract, dict
    ):
        raise ThresholdCalibrationError(
            "Candidate environment omits capabilities/capabilities_contract."
        )
    if set(all_capabilities) != {"editguard_wrapper"}:
        raise ThresholdCalibrationError(
            "Candidate environment capabilities do not match the single frozen method."
        )
    benchmark_capabilities = all_capabilities.get("editguard_wrapper")
    if not isinstance(benchmark_capabilities, dict):
        raise ThresholdCalibrationError(
            "Candidate environment has no editguard_wrapper capabilities."
        )
    expected_contract = {
        "editguard_wrapper": {
            key: value
            for key, value in sorted(benchmark_capabilities.items())
            if key
            not in {"registry_codebook_records", "registry_codebook_min_distance"}
        }
    }
    if declared_contract != expected_contract:
        raise ThresholdCalibrationError(
            "Candidate capabilities_contract differs from the benchmark capabilities."
        )
    fixed = _fixed_capabilities(benchmark_capabilities)
    if fixed != _fixed_capabilities(startup_capabilities):
        raise ThresholdCalibrationError(
            "Startup and benchmark fixed capabilities differ within one candidate."
        )
    identity = {field: environment[field] for field in _IMMUTABLE_ENVIRONMENT_FIELDS}
    identity["fixed_capabilities"] = fixed
    return identity


def _resolve_within(path: Path, root: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ThresholdCalibrationError(
            f"{label} escapes its candidate run directory: {resolved}"
        ) from exc
    return resolved


def _require_file_within(path: Path, root: Path, *, label: str) -> Path:
    resolved = _resolve_within(path, root, label=label)
    if not resolved.is_file():
        raise ThresholdCalibrationError(f"{label} is missing: {resolved}")
    return resolved


def _validate_candidate_runs_root(
    payload: Mapping[str, Any], *, run_root: Path
) -> Path:
    """Bind YAML output to the bundle's real, non-symlink candidate directory."""

    run_root = run_root.expanduser().resolve()
    expected = run_root / "candidate-runs"
    experiment = payload.get("experiment") or {}
    declared_raw = (
        experiment.get("output_root") if isinstance(experiment, Mapping) else None
    )
    if type(declared_raw) is not str or not declared_raw.strip():
        raise ThresholdCalibrationError(
            "Calibration experiment.output_root must be an absolute path."
        )
    declared_path = Path(declared_raw).expanduser()
    declared = Path(os.path.abspath(os.fspath(declared_path)))
    if not declared_path.is_absolute() or declared != expected:
        raise ThresholdCalibrationError(
            "Calibration experiment.output_root must equal "
            f"RUN_ROOT/candidate-runs exactly: expected {expected}, got {declared_raw!r}."
        )
    if expected.is_symlink():
        raise ThresholdCalibrationError(
            f"Calibration candidate-runs directory must not be a symlink: {expected}"
        )
    if expected.exists() and not expected.is_dir():
        raise ThresholdCalibrationError(
            f"Calibration candidate-runs path is not a directory: {expected}"
        )
    return expected


def _resolve_candidate_run_directory(
    *, run_root: Path, candidate_runs_root: Path, candidate_name: str
) -> Path:
    """Resolve a candidate without allowing either directory level to redirect."""

    run_root = run_root.expanduser().resolve()
    if candidate_runs_root.is_symlink():
        raise ThresholdCalibrationError(
            "Calibration candidate-runs directory must not be a symlink: "
            f"{candidate_runs_root}"
        )
    candidate_path = candidate_runs_root / candidate_name
    if candidate_path.is_symlink():
        raise ThresholdCalibrationError(
            f"Candidate run directory must not be a symlink: {candidate_path}"
        )
    try:
        resolved = candidate_path.resolve(strict=True)
    except OSError as exc:
        raise ThresholdCalibrationError(
            f"Candidate run directory is missing: {candidate_path}"
        ) from exc
    try:
        resolved.relative_to(run_root)
    except ValueError as exc:
        raise ThresholdCalibrationError(
            f"Candidate run directory escapes the calibration run root: {resolved}"
        ) from exc
    if not resolved.is_dir():
        raise ThresholdCalibrationError(
            f"Candidate run directory is missing: {resolved}"
        )
    return resolved


def _png_sha256(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def _assert_metric_matches(
    row: dict[str, Any], field: str, expected: float, *, atol: float = 1e-12
) -> None:
    observed = _unit_interval(row, field)
    if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=atol):
        raise ThresholdCalibrationError(
            f"Candidate metric {field} differs from retained predicted mask: "
            f"{row.get('row_key')} observed={observed} expected={expected}"
        )


def _reported_float(payload: dict[str, Any], field: str, *, label: str) -> float:
    value = payload.get(field)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise ThresholdCalibrationError(f"{label} has no finite {field}.")
    return float(value)


def _expected_attack_regime(area_ratio: float, tamper_area_threshold: float) -> str:
    if area_ratio > 0.80:
        return "global_rerendering_or_watermark_laundering"
    if area_ratio > tamper_area_threshold:
        return "localized_tamper_candidate"
    return "no_tamper_detected"


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _binary_mask_replay_identity(mask: np.ndarray) -> str:
    binary = np.ascontiguousarray(mask, dtype=np.uint8)
    if binary.ndim != 2 or not bool(np.isin(binary, [0, 1]).all()):
        raise ThresholdCalibrationError(
            "Cannot bind a non-binary localization-mask replay."
        )
    digest = hashlib.sha256()
    digest.update(b"cogniguard.localization-mask-replay.v1\x00")
    digest.update(
        json.dumps(
            {"shape": [int(binary.shape[0]), int(binary.shape[1])]},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    )
    digest.update(b"\x00")
    digest.update(binary.tobytes(order="C"))
    return digest.hexdigest()


def _expected_localization_contract(
    *,
    localization_channel_vote_min: int,
    declared_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if (
        isinstance(localization_channel_vote_min, bool)
        or not isinstance(localization_channel_vote_min, int)
        or not 1 <= localization_channel_vote_min <= 3
    ):
        raise ThresholdCalibrationError(
            "localization_channel_vote_min must be an integer from 1 to 3."
        )
    expected = dict(LOCALIZATION_MASK_CONTRACT)
    expected["localization_channel_vote_min"] = localization_channel_vote_min
    if declared_contract is None:
        return expected
    if not isinstance(declared_contract, Mapping):
        raise ThresholdCalibrationError(
            "Expected localization contract must be a mapping."
        )
    declared = {
        field: declared_contract.get(field) for field in LOCALIZATION_CONTRACT_FIELDS
    }
    if declared != expected:
        raise ThresholdCalibrationError(
            "Expected localization contract differs from the supported residual-channel "
            f"vote protocol: expected={expected}, declared={declared}."
        )
    return declared


def _assert_localization_contract(
    payload: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    label: str,
) -> None:
    legacy_fields = {
        "localization_rule_version",
        "localization_channel_count",
        "localization_channel_vote_rule",
        "localization_threshold_rule",
        "localization_channel_vote",
    }
    observed_legacy = sorted(legacy_fields.intersection(payload))
    mismatches: list[str] = []
    for field in LOCALIZATION_CONTRACT_FIELDS:
        observed = payload.get(field)
        wanted = expected[field]
        if type(observed) is not type(wanted) or observed != wanted:
            mismatches.append(f"{field}={observed!r}")
    if observed_legacy or mismatches:
        details = []
        if mismatches:
            details.append("mismatch=" + ",".join(mismatches))
        if observed_legacy:
            details.append("legacy=" + ",".join(observed_legacy))
        raise ThresholdCalibrationError(
            f"{label} localization contract is invalid: " + "; ".join(details)
        )


def _assert_exact_capability(
    payload: Mapping[str, Any], field: str, expected: Any, *, label: str
) -> None:
    observed = payload.get(field)
    if type(observed) is not type(expected):
        raise ThresholdCalibrationError(
            f"{label} capability {field} has wrong type/value: "
            f"expected={expected!r}, observed={observed!r}."
        )
    if isinstance(expected, float):
        if not math.isfinite(observed) or not math.isclose(
            observed, expected, rel_tol=0.0, abs_tol=1e-12
        ):
            raise ThresholdCalibrationError(
                f"{label} capability {field} differs: "
                f"expected={expected!r}, observed={observed!r}."
            )
    elif observed != expected:
        raise ThresholdCalibrationError(
            f"{label} capability {field} differs: "
            f"expected={expected!r}, observed={observed!r}."
        )


def _assert_attack_runtime_capabilities(
    payload: Mapping[str, Any], *, label: str
) -> None:
    _assert_exact_capability(
        payload, "attack_model_id", EXPECTED_ATTACK_MODEL_ID, label=label
    )
    _assert_exact_capability(
        payload, "deterministic_mode_enabled", True, label=label
    )
    revision = payload.get("attack_model_revision")
    if type(revision) is not str or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ThresholdCalibrationError(
            f"{label} attack_model_revision must be an exact 40-character lowercase "
            f"commit hash; observed={revision!r}."
        )


def _png_ihdr(path: Path) -> dict[str, int]:
    header = path.read_bytes()[:33]
    if len(header) != 33 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ThresholdCalibrationError(
            f"Raw localization vote artifact is not a PNG: {path}"
        )
    if int.from_bytes(header[8:12], "big") != 13 or header[12:16] != b"IHDR":
        raise ThresholdCalibrationError(
            f"Raw localization vote artifact has no canonical IHDR: {path}"
        )
    ihdr = header[16:29]
    return {
        "width": int.from_bytes(ihdr[0:4], "big"),
        "height": int.from_bytes(ihdr[4:8], "big"),
        "bit_depth": int(ihdr[8]),
        "color_type": int(ihdr[9]),
        "compression": int(ihdr[10]),
        "filter": int(ihdr[11]),
        "interlace": int(ihdr[12]),
    }


def _predicted_mask_for_row(
    row: dict[str, Any],
    *,
    run_dir: Path,
    recovery_threshold: float,
    localization_channel_vote_min: int,
    expected_localization_contract: Mapping[str, Any],
    expected_image_shape: tuple[int, int],
    localization_evidence: dict[str, dict[str, Any]] | None = None,
) -> Image.Image:
    verify_job_id = str(row["verify_job_id"])
    verify_dir = run_dir / "benchmark" / "api_jobs" / verify_job_id / "verify"
    report_path = _require_file_within(
        verify_dir / "verify_report.json",
        run_dir,
        label="Verify report",
    )
    report = _read_json(report_path)
    response = report.get("response")
    request = report.get("request")
    input_image = report.get("input_image")
    if (
        report.get("job_id") != verify_job_id
        or report.get("job_type") != "verify"
        or not isinstance(response, dict)
        or response.get("job_id") != verify_job_id
        or response.get("status") != "ok"
        or response.get("implementation_level") != "real_pipeline"
        or not isinstance(request, dict)
        or not isinstance(input_image, dict)
        or input_image.get("sha256") != row.get("attacked_image_sha256")
        or request.get("image_reference") != input_image
    ):
        raise ThresholdCalibrationError(
            "Verify report identity, implementation, or input-image SHA-256 differs "
            f"from its calibration row: {row.get('row_key')}"
        )
    shared_required_capabilities = {
        "recovery_threshold": recovery_threshold,
        "tamper_area_threshold": float(
            EXPECTED_FIXED_PARAMETERS["tamper_area_threshold"]
        ),
        "localization_postprocessing": EXPECTED_FIXED_PARAMETERS[
            "localization_postprocessing"
        ],
        **dict(expected_localization_contract),
    }
    try:
        shared_validation = validate_verify_localization_artifacts(
            response=response,
            artifact_run_root=run_dir / "benchmark",
            required_capabilities=shared_required_capabilities,
            expected_input_sha256=str(row.get("attacked_image_sha256") or ""),
            expected_seed=row.get("seed"),
            expected_image_shape=expected_image_shape,
        )
    except LocalizationArtifactError as exc:
        raise ThresholdCalibrationError(
            "Shared localization artifact validation failed for "
            f"{row.get('row_key')}: {exc}"
        ) from exc
    input_size = input_image.get("size_bytes")
    if (
        input_image.get("suffix") not in SUPPORTED_VERIFY_IMAGE_SUFFIXES
        or isinstance(input_size, bool)
        or not isinstance(input_size, int)
        or input_size <= 0
    ):
        raise ThresholdCalibrationError(
            f"Verify report input_image reference is malformed: {row.get('row_key')}"
        )
    row_seed = row.get("seed")
    if (
        isinstance(row_seed, bool)
        or not isinstance(row_seed, int)
        or request.get("seed") != row_seed
        or isinstance(response.get("seed"), bool)
        or response.get("seed") != row_seed
    ):
        raise ThresholdCalibrationError(
            f"Verify report seed differs from its calibration row: {row.get('row_key')}"
        )
    if not math.isclose(
        _reported_float(report, "recovery_threshold", label="Verify report"),
        recovery_threshold,
        rel_tol=0.0,
        abs_tol=1e-12,
    ) or not math.isclose(
        _reported_float(response, "recovery_threshold", label="Verify report response"),
        recovery_threshold,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ThresholdCalibrationError(
            "Verify report recovery_threshold differs from its candidate: "
            f"{row.get('row_key')}"
        )
    if (
        not math.isclose(
            _reported_float(report, "tamper_area_threshold", label="Verify report"),
            float(EXPECTED_FIXED_PARAMETERS["tamper_area_threshold"]),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        or not math.isclose(
            _reported_float(
                response,
                "tamper_area_threshold",
                label="Verify report response",
            ),
            float(EXPECTED_FIXED_PARAMETERS["tamper_area_threshold"]),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        or report.get("localization_postprocessing")
        != EXPECTED_FIXED_PARAMETERS["localization_postprocessing"]
    ):
        raise ThresholdCalibrationError(
            "Verify report changed a fixed localization parameter: "
            f"{row.get('row_key')}"
        )
    _assert_localization_contract(
        report,
        expected_localization_contract,
        label="Verify report",
    )
    _assert_localization_contract(
        response,
        expected_localization_contract,
        label="Verify report response",
    )
    resolved_raw_vote_threshold = 255 * localization_channel_vote_min
    if (
        isinstance(report.get("resolved_raw_vote_threshold"), bool)
        or type(report.get("resolved_raw_vote_threshold")) is not int
        or report.get("resolved_raw_vote_threshold")
        != resolved_raw_vote_threshold
    ):
        raise ThresholdCalibrationError(
            "Verify report resolved_raw_vote_threshold differs from its "
            f"localization contract: {row.get('row_key')}"
        )

    predicted_path = _require_file_within(
        verify_dir / "predicted_mask.png",
        run_dir,
        label="Predicted mask",
    )
    reported_predicted_path = _require_file_within(
        Path(str(response.get("predicted_mask_path") or "")),
        run_dir,
        label="Verify-report predicted mask",
    )
    if reported_predicted_path != predicted_path:
        raise ThresholdCalibrationError(
            "Verify report predicted_mask_path does not identify the retained mask: "
            f"{row.get('row_key')}"
        )
    with Image.open(predicted_path) as image:
        if image.mode != "L":
            raise ThresholdCalibrationError(
                f"Retained predicted mask is not 8-bit grayscale: {row.get('row_key')}"
            )
        predicted_array = np.asarray(image).copy()
    if predicted_array.ndim != 2 or not bool(
        np.isin(predicted_array, np.asarray([0, 255], dtype=np.uint8)).all()
    ):
        raise ThresholdCalibrationError(
            f"Retained predicted mask is not binary: {row.get('row_key')}"
        )
    if predicted_array.shape != expected_image_shape:
        raise ThresholdCalibrationError(
            "Retained predicted mask dimensions differ from the attacked input: "
            f"{row.get('row_key')} expected={expected_image_shape}, "
            f"observed={predicted_array.shape}."
        )

    raw_artifact = report.get("raw_localization_votes_artifact")
    expected_artifact_fields = {
        "path",
        "sha256",
        "dtype",
        "shape",
        "encoding",
        "histogram",
    }
    if not isinstance(raw_artifact, dict) or set(raw_artifact) != expected_artifact_fields:
        raise ThresholdCalibrationError(
            f"Verify report raw-vote artifact metadata is malformed: {row.get('row_key')}"
        )
    raw_path = _require_file_within(
        verify_dir / RAW_LOCALIZATION_VOTE_FILENAME,
        run_dir,
        label="Raw localization vote artifact",
    )
    reported_raw_path = _require_file_within(
        Path(str(raw_artifact.get("path") or "")),
        run_dir,
        label="Verify-report raw localization vote artifact",
    )
    response_raw_path = _require_file_within(
        Path(str(response.get("raw_localization_votes_path") or "")),
        run_dir,
        label="Verify-response raw localization vote artifact",
    )
    if raw_path != reported_raw_path or raw_path != response_raw_path:
        raise ThresholdCalibrationError(
            "Verify report raw-vote paths do not identify the retained artifact: "
            f"{row.get('row_key')}"
        )
    raw_sha256 = sha256_file(raw_path)
    if (
        raw_artifact.get("sha256") != raw_sha256
        or response.get("raw_localization_votes_sha256") != raw_sha256
    ):
        raise ThresholdCalibrationError(
            f"Raw localization vote SHA-256 differs from its report: {row.get('row_key')}"
        )

    ihdr = _png_ihdr(raw_path)
    if (
        ihdr["bit_depth"] != 16
        or ihdr["color_type"] != 0
        or ihdr["compression"] != 0
        or ihdr["filter"] != 0
        or ihdr["interlace"] != 0
    ):
        raise ThresholdCalibrationError(
            f"Raw localization vote PNG is not non-interlaced 16-bit grayscale: {row.get('row_key')}"
        )
    expected_shape = [int(expected_image_shape[0]), int(expected_image_shape[1])]
    if (
        [ihdr["height"], ihdr["width"]] != expected_shape
        or raw_artifact.get("shape") != expected_shape
        or response.get("raw_localization_votes_shape") != expected_shape
        or raw_artifact.get("dtype") != "uint16"
        or response.get("raw_localization_votes_dtype") != "uint16"
        or raw_artifact.get("encoding") != RAW_LOCALIZATION_VOTE_ENCODING
        or response.get("raw_localization_votes_encoding")
        != RAW_LOCALIZATION_VOTE_ENCODING
    ):
        raise ThresholdCalibrationError(
            f"Raw localization vote dtype, shape, or encoding is invalid: {row.get('row_key')}"
        )
    with Image.open(raw_path) as image:
        raw_votes = np.asarray(image).copy()
    if (
        raw_votes.ndim != 2
        or raw_votes.shape != predicted_array.shape
        or raw_votes.dtype == np.dtype("uint8")
        or not np.issubdtype(raw_votes.dtype, np.integer)
    ):
        raise ThresholdCalibrationError(
            f"Decoded raw localization votes are not a 16-bit 2D map: {row.get('row_key')}"
        )
    if not bool(
        np.isin(
            raw_votes,
            np.asarray(RAW_LOCALIZATION_VOTE_VALUES, dtype=np.uint16),
        ).all()
    ):
        raise ThresholdCalibrationError(
            f"Raw localization votes contain a value outside the four-value domain: {row.get('row_key')}"
        )
    histogram = {
        str(value): int(np.count_nonzero(raw_votes == value))
        for value in RAW_LOCALIZATION_VOTE_VALUES
    }
    if (
        raw_artifact.get("histogram") != histogram
        or response.get("raw_localization_votes_histogram") != histogram
        or sum(histogram.values()) != raw_votes.size
    ):
        raise ThresholdCalibrationError(
            f"Raw localization vote histogram differs from the retained PNG: {row.get('row_key')}"
        )

    reconstructed = raw_votes >= resolved_raw_vote_threshold
    retained_binary = predicted_array == 255
    if not np.array_equal(reconstructed, retained_binary):
        raise ThresholdCalibrationError(
            "Predicted mask differs from independent raw-vote reconstruction: "
            f"{row.get('row_key')}"
        )
    if not np.array_equal(reconstructed, shared_validation.predicted_mask):
        raise ThresholdCalibrationError(
            "Threshold analyzer replay differs from the shared localization "
            f"validator: {row.get('row_key')}"
        )
    reconstructed_area = float(reconstructed.mean())
    if (
        not math.isclose(
            _reported_float(
                report,
                "predicted_mask_area_ratio",
                label="Verify report",
            ),
            reconstructed_area,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        or not math.isclose(
            _reported_float(
                response,
                "predicted_mask_area_ratio",
                label="Verify report response",
            ),
            reconstructed_area,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    ):
        raise ThresholdCalibrationError(
            "Verify report mask area differs from independent raw-vote reconstruction: "
            f"{row.get('row_key')}"
        )
    tamper_area_threshold = float(EXPECTED_FIXED_PARAMETERS["tamper_area_threshold"])
    expected_attack_regime = _expected_attack_regime(
        reconstructed_area, tamper_area_threshold
    )
    if response.get("attack_regime") != expected_attack_regime:
        raise ThresholdCalibrationError(
            "Verify response attack_regime differs from the independent tamper "
            f"decision: {row.get('row_key')} expected={expected_attack_regime!r}, "
            f"observed={response.get('attack_regime')!r}."
        )
    if localization_evidence is not None:
        row_key = str(row.get("row_key") or "")
        if not row_key or row_key in localization_evidence:
            raise ThresholdCalibrationError(
                f"Localization evidence row key is missing or duplicated: {row_key!r}."
            )
        replay_identity = _binary_mask_replay_identity(reconstructed)
        retained_identity = _binary_mask_replay_identity(retained_binary)
        if replay_identity != retained_identity:
            raise ThresholdCalibrationError(
                f"Retained-mask replay identity mismatch: {row_key}."
            )
        shared_evidence = shared_validation.evidence
        localization_evidence[row_key] = {
            "row_key": row_key,
            "raw_vote_path": shared_evidence["raw_vote_path"],
            "raw_vote_sha256": shared_evidence["raw_vote_sha256"],
            "raw_vote_shape": shared_evidence["raw_vote_shape"],
            "raw_vote_histogram": shared_evidence["raw_vote_histogram"],
            "raw_vote_encoding": shared_evidence["raw_vote_encoding"],
            "predicted_mask_path": shared_evidence["predicted_mask_path"],
            "predicted_mask_sha256": shared_evidence["predicted_mask_sha256"],
            "replay_identity_sha256": shared_evidence["replay_identity_sha256"],
            "resolved_raw_vote_threshold": shared_evidence[
                "resolved_raw_vote_threshold"
            ],
        }
    return Image.fromarray(shared_validation.predicted_mask.astype(np.uint8) * 255)


def _independently_validate_candidate_artifacts(
    rows: list[dict[str, Any]],
    *,
    run_dir: Path,
    recovery_threshold: float,
    localization_channel_vote_min: int = 1,
    localization_contract: Mapping[str, Any] | None = None,
    required_image_shape: tuple[int, int] | None = None,
    localization_evidence: dict[str, dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Rehash clean files, replay erasing, and recompute mask metrics."""

    expected_localization_contract = _expected_localization_contract(
        localization_channel_vote_min=localization_channel_vote_min,
        declared_contract=localization_contract,
    )
    expected_image_shape = (
        EXPECTED_SERVICE_IMAGE_SHAPE
        if required_image_shape is None
        else required_image_shape
    )
    if (
        len(expected_image_shape) != 2
        or any(type(value) is not int or value <= 0 for value in expected_image_shape)
    ):
        raise ThresholdCalibrationError("Required service image shape is invalid.")

    by_key = {
        (str(row["sample_id"]), int(row["seed"]), str(row["attack_id"])): row
        for row in rows
    }
    sample_seed_pairs = sorted(
        {(str(row["sample_id"]), int(row["seed"])) for row in rows}
    )
    attack_hashes: dict[str, str] = {}
    for sample_id, seed in sample_seed_pairs:
        clean = by_key[(sample_id, seed, "clean")]
        clean_raw_path = clean.get("attacked_image_path")
        if clean.get("attacked_image_retained") is not True or not isinstance(
            clean_raw_path, str
        ):
            raise ThresholdCalibrationError(
                f"Clean watermarked artifact was not retained: {clean.get('row_key')}"
            )
        clean_path = _require_file_within(
            Path(clean_raw_path), run_dir, label="Clean watermarked image"
        )
        clean_sha256 = sha256_file(clean_path)
        if clean_sha256 != clean.get("attacked_image_sha256"):
            raise ThresholdCalibrationError(
                f"Clean watermarked SHA-256 differs from its file: {clean.get('row_key')}"
            )
        if clean.get("attack_truth_bbox") is not None:
            raise ThresholdCalibrationError(
                f"Clean row unexpectedly declares an attack truth box: {clean.get('row_key')}"
            )
        with Image.open(clean_path) as image:
            watermarked = image.convert("RGB").copy()
        observed_image_shape = (watermarked.height, watermarked.width)
        if observed_image_shape != expected_image_shape:
            raise ThresholdCalibrationError(
                "Clean watermarked/attacked input dimensions differ from the frozen "
                f"service dimensions: {clean.get('row_key')} "
                f"expected={expected_image_shape}, observed={observed_image_shape}."
            )

        for attack_id in EXPECTED_ATTACK_IDS:
            row = by_key[(sample_id, seed, attack_id)]
            if attack_id == "clean":
                expected_sha256 = clean_sha256
                truth = Image.new("L", watermarked.size, 0)
            else:
                ratio = float(attack_id.rsplit("-", 1)[1])
                if row.get("attack_params") != {"area_ratio": ratio}:
                    raise ThresholdCalibrationError(
                        f"Erasing parameters differ from the frozen attack: {row.get('row_key')}"
                    )
                attacked, metadata = apply_traditional_attack(
                    watermarked,
                    AttackSpec(
                        name="erasing",
                        family="removal",
                        params={"area_ratio": ratio, "expanded_name": attack_id},
                    ),
                    seed=seed,
                )
                expected_sha256 = _png_sha256(attacked)
                expected_bbox = metadata.get("truth_bbox")
                if row.get("attack_truth_bbox") != expected_bbox:
                    raise ThresholdCalibrationError(
                        f"Erasing truth box differs from deterministic replay: {row.get('row_key')}"
                    )
                truth = truth_mask_from_half_open_bbox(watermarked.size, expected_bbox)
            if row.get("attacked_image_sha256") != expected_sha256:
                raise ThresholdCalibrationError(
                    f"Attacked-image SHA-256 differs from deterministic replay: {row.get('row_key')}"
                )
            attack_hashes[f"{sample_id}|{seed}|{attack_id}"] = expected_sha256

            predicted = _predicted_mask_for_row(
                row,
                run_dir=run_dir,
                recovery_threshold=recovery_threshold,
                localization_channel_vote_min=localization_channel_vote_min,
                expected_localization_contract=expected_localization_contract,
                expected_image_shape=expected_image_shape,
                localization_evidence=localization_evidence,
            )
            recomputed = mask_metrics(predicted, truth)
            _assert_metric_matches(row, "mask_fpr", recomputed["fpr"])
            if attack_id != "clean":
                for field in ("iou", "dice", "precision", "recall"):
                    _assert_metric_matches(row, f"mask_{field}", recomputed[field])
            predicted_array = np.asarray(predicted, dtype=np.uint8) >= 128
            expected_area = float(predicted_array.mean())
            expected_nonempty = float(bool(predicted_array.any()))
            expected_detected = float(
                expected_area
                > float(EXPECTED_FIXED_PARAMETERS["tamper_area_threshold"])
            )
            _assert_metric_matches(row, "predicted_tamper_area_ratio", expected_area)
            _assert_metric_matches(row, "predicted_mask_nonempty", expected_nonempty)
            if _binary_metric(row, "image_tamper_detected") != expected_detected:
                raise ThresholdCalibrationError(
                    "Candidate image_tamper_detected differs from the service area-threshold "
                    "decision: "
                    f"{row.get('row_key')}"
                )
    if localization_evidence is not None:
        expected_raw_paths = {
            Path(row["raw_vote_path"]).resolve()
            for row in localization_evidence.values()
        }
        expected_predicted_paths = {
            Path(row["predicted_mask_path"]).resolve()
            for row in localization_evidence.values()
        }
        api_jobs_root = run_dir / "benchmark" / "api_jobs"
        discovered_raw_paths = {
            path.resolve()
            for path in api_jobs_root.rglob("raw_localization_channel_votes*")
            if path.is_file()
        }
        discovered_predicted_paths = {
            path.resolve()
            for path in api_jobs_root.rglob("predicted_mask*")
            if path.is_file()
        }
        if discovered_raw_paths != expected_raw_paths:
            raise ThresholdCalibrationError(
                "Raw localization vote artifact set has missing, extra, or alternate files."
            )
        if discovered_predicted_paths != expected_predicted_paths:
            raise ThresholdCalibrationError(
                "Predicted-mask artifact set has missing, extra, or alternate files."
            )
    return attack_hashes


def _analyze_candidate(
    candidate: dict[str, Any],
    *,
    run_root: Path,
    candidate_runs_root: Path,
    samples_by_id: dict[str, ImageSample],
    evaluation_seeds: tuple[int, ...],
    fixed: dict[str, Any],
    required_attack_runtime: dict[str, str],
    attacks_path: Path,
    attacks_sha256: str,
    config_path: Path,
    manifest_path: Path,
    manifest_lock_audit: dict[str, Any],
    preregistration_nonce: str,
) -> dict[str, Any]:
    sample_ids = set(samples_by_id)
    threshold = float(candidate["recovery_threshold"])
    expected_id = candidate_id(threshold)
    if candidate.get("candidate_id") != expected_id:
        raise ThresholdCalibrationError(f"Candidate id/threshold mismatch: {candidate}")
    run_dir = _resolve_candidate_run_directory(
        run_root=run_root,
        candidate_runs_root=candidate_runs_root,
        candidate_name=expected_id,
    )
    try:
        preregistration_evidence = validate_preregistration_claim(
            config_path,
            claim_path=run_dir / RUN_COPY_FILENAME,
            expected_run_class=RUN_CLASS,
            expected_nonce=preregistration_nonce,
            expected_candidate_run=run_dir,
        )
    except PreregistrationError as exc:
        raise ThresholdCalibrationError(
            f"Candidate preregistration evidence is invalid ({expected_id}): {exc}"
        ) from exc
    run_class_path = run_dir / "run-class.txt"
    if (
        not run_class_path.is_file()
        or run_class_path.read_text(encoding="utf-8").strip() != RUN_CLASS
    ):
        raise ThresholdCalibrationError(f"Candidate run class is invalid: {run_dir}")
    preflight = _read_json(run_dir / "preflight.json")
    if preflight.get("status") not in {"ready", "ready_with_warnings"}:
        raise ThresholdCalibrationError(f"Candidate preflight failed: {run_dir}")
    capabilities = _read_json(run_dir / "capabilities.json")
    expected_localization_contract = _expected_localization_contract(
        localization_channel_vote_min=1,
        declared_contract=fixed,
    )
    _assert_localization_contract(
        capabilities,
        expected_localization_contract,
        label=f"Candidate API capabilities ({expected_id})",
    )
    _assert_exact_capability(
        capabilities,
        "recovery_threshold",
        threshold,
        label=f"Candidate API ({expected_id})",
    )
    for capability_name in (
        "tamper_area_threshold",
        "registry_hamming_radius",
        "localization_postprocessing",
    ):
        _assert_exact_capability(
            capabilities,
            capability_name,
            fixed[capability_name],
            label=f"Candidate API ({expected_id})",
        )
    _assert_attack_runtime_capabilities(
        capabilities, label=f"Candidate API ({expected_id})"
    )
    environment = _read_json(run_dir / "benchmark" / "environment.json")
    if (
        environment.get("config_sha256") != sha256_file(config_path)
        or environment.get("manifest_sha256") != sha256_file(manifest_path)
        or Path(str(environment.get("config_path") or "")).resolve() != config_path
        or Path(str(environment.get("manifest_path") or "")).resolve() != manifest_path
        or environment.get("strict_paper_mode") is not True
        or environment.get("run_class") != RUN_CLASS
        or environment.get("paper_eligible") is not False
        or environment.get("evaluation_split") != SELECTION_SPLIT
        or environment.get("dataset_manifest_override_used") is not False
        or environment.get("dataset_roots_override_used") is not False
        or environment.get("manifest_lock") != manifest_lock_audit
        or environment.get("preregistration_claim") != preregistration_evidence
    ):
        raise ThresholdCalibrationError(
            f"Candidate benchmark environment is not bound to the calibration bundle: {expected_id}"
        )
    benchmark_capabilities = (environment.get("capabilities") or {}).get(
        "editguard_wrapper"
    ) or {}
    if isinstance(benchmark_capabilities, dict):
        _assert_localization_contract(
            benchmark_capabilities,
            expected_localization_contract,
            label=f"Benchmark API capabilities ({expected_id})",
        )
    if environment.get("methods") != [
        {"id": "editguard_wrapper", "kind": "sce_locguard_api"}
    ] or not isinstance(benchmark_capabilities, dict):
        raise ThresholdCalibrationError(
            f"Benchmark API capabilities differ from the candidate: {expected_id}"
        )
    _assert_exact_capability(
        benchmark_capabilities,
        "recovery_threshold",
        threshold,
        label=f"Benchmark API ({expected_id})",
    )
    for capability_name in (
        "tamper_area_threshold",
        "registry_hamming_radius",
        "localization_postprocessing",
    ):
        _assert_exact_capability(
            benchmark_capabilities,
            capability_name,
            fixed[capability_name],
            label=f"Benchmark API ({expected_id})",
        )
    _assert_attack_runtime_capabilities(
        benchmark_capabilities, label=f"Benchmark API ({expected_id})"
    )
    immutable_environment_identity = _immutable_environment_identity(
        environment, startup_capabilities=capabilities
    )
    immutable_environment_identity_sha256 = hashlib.sha256(
        json.dumps(
            immutable_environment_identity,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    manifest_audit = environment.get("input_manifest_audit") or {}
    expected_sample_ids_sha256 = hashlib.sha256(
        "\n".join(sorted(sample_ids)).encode("utf-8")
    ).hexdigest()
    if (
        not isinstance(manifest_audit, dict)
        or manifest_audit.get("total_samples") != EXPECTED_SAMPLES
        or manifest_audit.get("selected_samples") != EXPECTED_SAMPLES
        or manifest_audit.get("selected_split") != SELECTION_SPLIT
        or manifest_audit.get("selected_sample_ids_sha256")
        != expected_sample_ids_sha256
    ):
        raise ThresholdCalibrationError(
            f"Candidate input-manifest audit is incomplete: {expected_id}"
        )
    packages = environment.get("packages") or {}
    attack_runtime = environment.get("traditional_attack_runtime") or {}
    observed_packages = attack_runtime.get("observed_packages") or {}
    if (
        not isinstance(packages, dict)
        or not isinstance(attack_runtime, dict)
        or attack_runtime.get("artifact_retention") != ATTACK_ARTIFACT_RETENTION
        or attack_runtime.get("required_packages") != required_attack_runtime
        or observed_packages != required_attack_runtime
        or any(
            packages.get(name) != version
            for name, version in required_attack_runtime.items()
        )
        or Path(str(attack_runtime.get("implementation_path") or "")).resolve()
        != attacks_path
        or attack_runtime.get("implementation_sha256") != attacks_sha256
    ):
        raise ThresholdCalibrationError(
            f"Candidate attack implementation/runtime is not frozen: {expected_id}"
        )
    rows = _read_jsonl(run_dir / "benchmark" / "raw_results.jsonl")
    grouped = _validate_run_rows(
        rows,
        samples_by_id=samples_by_id,
        evaluation_seeds=evaluation_seeds,
    )
    retained_attack_pngs = sorted((run_dir / "benchmark" / "attacks").rglob("*.png"))
    if retained_attack_pngs:
        raise ThresholdCalibrationError(
            f"Candidate retained {len(retained_attack_pngs)} traditional attack PNGs "
            f"despite hash_only policy: {expected_id}"
        )
    localization_artifact_rows: dict[str, dict[str, Any]] = {}
    attack_input_hashes = _independently_validate_candidate_artifacts(
        rows,
        run_dir=run_dir,
        recovery_threshold=threshold,
        localization_channel_vote_min=1,
        localization_contract=fixed,
        localization_evidence=localization_artifact_rows,
    )
    attack_input_hash_map_sha256 = hashlib.sha256(
        json.dumps(attack_input_hashes, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    if len(localization_artifact_rows) != len(rows):
        raise ThresholdCalibrationError(
            f"Candidate localization evidence is incomplete: {expected_id}."
        )
    localization_artifact_evidence_sha256 = _canonical_sha256(
        localization_artifact_rows
    )

    clean = grouped["clean"]
    clean_fpr = _metric_summary(clean, "mask_fpr")
    condition_metrics: list[dict[str, Any]] = [
        {
            "attack_id": "clean",
            "rows": len(clean),
            "mask_fpr": clean_fpr,
            "image_tamper_false_positive_rate": _mean(clean, "image_tamper_detected"),
            "predicted_tamper_area_ratio": _metric_summary(
                clean, "predicted_tamper_area_ratio"
            ),
            "source_registry_match_rate": _mean(clean, "source_registry_match"),
        }
    ]
    erasing_mean_iou: dict[str, float] = {}
    erasing_p10_iou: dict[str, float] = {}
    erasing_success_rate: dict[str, float] = {}
    for ratio in ERASING_RATIOS:
        attack_id = f"erasing__area_ratio-{ratio}"
        attack_rows = grouped[attack_id]
        iou_summary = _metric_summary(attack_rows, "mask_iou")
        mean_iou = iou_summary["mean"]
        p10_iou = iou_summary["p10"]
        success_rate = float(
            np.mean(
                np.asarray(
                    [_unit_interval(row, "mask_iou") >= 0.75 for row in attack_rows],
                    dtype=np.float64,
                )
            )
        )
        erasing_mean_iou[f"{ratio:.2f}"] = mean_iou
        erasing_p10_iou[f"{ratio:.2f}"] = p10_iou
        erasing_success_rate[f"{ratio:.2f}"] = success_rate
        condition_metrics.append(
            {
                "attack_id": attack_id,
                "area_ratio": ratio,
                "rows": len(attack_rows),
                "mask_iou": iou_summary,
                "mask_iou_at_least_0_75_rate": success_rate,
                "mask_dice": _metric_summary(attack_rows, "mask_dice"),
                "mask_precision": _metric_summary(attack_rows, "mask_precision"),
                "mask_recall": _metric_summary(attack_rows, "mask_recall"),
                "image_tamper_detection_rate": _mean(
                    attack_rows, "image_tamper_detected"
                ),
                "source_registry_match_rate": _mean(
                    attack_rows, "source_registry_match"
                ),
            }
        )

    checks = [
        _constraint(
            name="clean_mean_mask_fpr",
            observed=clean_fpr["mean"],
            operator="<=",
            limit=float(CONSTRAINTS["clean_mean_mask_fpr_max"]),
        ),
        _constraint(
            name="clean_p99_mask_fpr",
            observed=clean_fpr["p99"],
            operator="<=",
            limit=float(CONSTRAINTS["clean_p99_mask_fpr_max"]),
        ),
        _constraint(
            name="clean_max_mask_fpr",
            observed=clean_fpr["max"],
            operator="<=",
            limit=float(CONSTRAINTS["clean_max_mask_fpr_max"]),
        ),
    ]
    checks.extend(
        _constraint(
            name=f"erasing_{ratio:.2f}_mean_mask_iou",
            observed=erasing_mean_iou[f"{ratio:.2f}"],
            operator=">=",
            limit=float(CONSTRAINTS["each_erasing_mean_mask_iou_min"]),
        )
        for ratio in ERASING_RATIOS
    )
    checks.extend(
        _constraint(
            name=f"erasing_{ratio:.2f}_p10_mask_iou",
            observed=erasing_p10_iou[f"{ratio:.2f}"],
            operator=">=",
            limit=float(CONSTRAINTS["each_erasing_p10_mask_iou_min"]),
        )
        for ratio in ERASING_RATIOS
    )
    checks.extend(
        _constraint(
            name=f"erasing_{ratio:.2f}_iou_at_least_0_75_rate",
            observed=erasing_success_rate[f"{ratio:.2f}"],
            operator=">=",
            limit=float(CONSTRAINTS["each_erasing_iou_at_least_0_75_rate_min"]),
        )
        for ratio in ERASING_RATIOS
    )
    eligible = all(check["passed"] for check in checks)
    return {
        "candidate_id": expected_id,
        "recovery_threshold": threshold,
        "run_dir": str(run_dir),
        "development_only": True,
        "paper_eligible": False,
        "preregistration_claim": preregistration_evidence,
        "rows": len(rows),
        "unique_samples": len(sample_ids),
        "evaluation_seeds": list(evaluation_seeds),
        "retained_traditional_attack_pngs": 0,
        "attack_input_hash_map_sha256": attack_input_hash_map_sha256,
        "localization_artifact_evidence": {
            "schema_version": LOCALIZATION_ARTIFACT_EVIDENCE_SCHEMA_VERSION,
            "count": len(localization_artifact_rows),
            "rows": localization_artifact_rows,
            "evidence_sha256": localization_artifact_evidence_sha256,
        },
        "localization_artifact_evidence_count": len(localization_artifact_rows),
        "localization_artifact_evidence_sha256": (
            localization_artifact_evidence_sha256
        ),
        "traditional_attack_runtime": {
            "implementation_path": str(attacks_path),
            "implementation_sha256": attacks_sha256,
            "required_packages": dict(required_attack_runtime),
            "observed_packages": dict(observed_packages),
            "artifact_retention": ATTACK_ARTIFACT_RETENTION,
        },
        "condition_metrics": condition_metrics,
        "selection_metrics": {
            "clean_mean_mask_fpr": clean_fpr["mean"],
            "clean_p99_mask_fpr": clean_fpr["p99"],
            "clean_max_mask_fpr": clean_fpr["max"],
            "erasing_mean_mask_iou_by_ratio": erasing_mean_iou,
            "erasing_p10_mask_iou_by_ratio": erasing_p10_iou,
            "erasing_iou_at_least_0_75_rate_by_ratio": erasing_success_rate,
            "erasing_equal_weight_macro_mean_iou": float(
                np.mean(list(erasing_mean_iou.values()))
            ),
        },
        "constraint_checks": checks,
        "all_constraints_passed": eligible,
        "capabilities_sha256": sha256_file(run_dir / "capabilities.json"),
        "preflight_sha256": sha256_file(run_dir / "preflight.json"),
        "environment_sha256": sha256_file(run_dir / "benchmark" / "environment.json"),
        "immutable_environment_identity_sha256": (
            immutable_environment_identity_sha256
        ),
        "immutable_environment_identity": immutable_environment_identity,
        "raw_results_sha256": sha256_file(run_dir / "benchmark" / "raw_results.jsonl"),
    }


def analyze_threshold_calibration(
    config_path: Path,
    *,
    run_root: Path | None = None,
) -> dict[str, Any]:
    config_path = config_path.expanduser().resolve()
    run_root = (
        run_root.expanduser().resolve()
        if run_root is not None
        else config_path.parent.resolve()
    )
    payload, contract = _validate_calibration_config(config_path)
    try:
        preregistration_evidence = validate_preregistration_claim(
            config_path,
            expected_run_class=RUN_CLASS,
        )
    except PreregistrationError as exc:
        raise ThresholdCalibrationError(
            f"Calibration source preregistration claim is invalid: {exc}"
        ) from exc
    candidate_runs_root = _validate_candidate_runs_root(payload, run_root=run_root)
    rows, manifest_path, manifest_lock_audit = _validate_selected_manifest(
        config_path, contract
    )
    samples_by_id = {row.sample_id: row for row in rows}
    seed_values = list((payload.get("experiment") or {}).get("seeds") or [])
    if seed_values != list(EVALUATION_SEEDS):
        raise ThresholdCalibrationError(
            "Calibration must use the three frozen evaluation seeds."
        )
    evaluation_seeds = tuple(int(value) for value in seed_values)
    candidates = list(contract.get("candidate_runs") or [])
    thresholds = [float(row.get("recovery_threshold")) for row in candidates]
    if thresholds != list(FROZEN_THRESHOLDS):
        raise ThresholdCalibrationError(
            "Candidate thresholds differ from the exact frozen nine-point grid."
        )
    if [
        float(value) for value in contract.get("candidate_thresholds") or []
    ] != thresholds:
        raise ThresholdCalibrationError(
            "Candidate threshold list differs from candidate-run declarations."
        )
    if contract.get("constraints") != CONSTRAINTS:
        raise ThresholdCalibrationError(
            "Calibration constraints differ from the frozen protocol."
        )
    fixed = dict(contract.get("fixed_parameters") or {})
    attack_implementation = dict(
        contract.get("traditional_attack_implementation") or {}
    )
    attacks_path = Path(str(attack_implementation["path"])).resolve()
    attacks_sha256 = str(attack_implementation["sha256"])
    required_attack_runtime = dict(contract.get("required_attack_runtime") or {})
    analyzer_attack_runtime = _validate_current_attack_runtime(required_attack_runtime)
    analyzed = [
        _analyze_candidate(
            candidate,
            run_root=run_root,
            candidate_runs_root=candidate_runs_root,
            samples_by_id=samples_by_id,
            evaluation_seeds=evaluation_seeds,
            fixed=fixed,
            required_attack_runtime=required_attack_runtime,
            attacks_path=attacks_path,
            attacks_sha256=attacks_sha256,
            config_path=config_path,
            manifest_path=manifest_path,
            manifest_lock_audit=manifest_lock_audit,
            preregistration_nonce=preregistration_evidence["nonce"],
        )
        for candidate in candidates
    ]
    immutable_environment_identity_sha256 = {
        row["immutable_environment_identity_sha256"] for row in analyzed
    }
    if len(immutable_environment_identity_sha256) != 1:
        raise ThresholdCalibrationError(
            "Candidate immutable environment identities differ; refusing code/model/runtime drift."
        )
    attack_input_hash_map_sha256 = {
        row["attack_input_hash_map_sha256"] for row in analyzed
    }
    if len(attack_input_hash_map_sha256) != 1:
        raise ThresholdCalibrationError(
            "Candidate runs did not use byte-identical watermarked/attacked inputs."
        )
    candidate_preregistration_hashes = {
        row["preregistration_claim"]["claim_sha256"] for row in analyzed
    }
    if candidate_preregistration_hashes != {
        preregistration_evidence["source_claim_sha256"]
    }:
        raise ThresholdCalibrationError(
            "Candidate runs do not share the frozen source preregistration claim."
        )
    eligible = sorted(
        (row for row in analyzed if row["all_constraints_passed"]),
        key=lambda row: float(row["recovery_threshold"]),
    )
    winner = (
        {
            "candidate_id": eligible[0]["candidate_id"],
            "recovery_threshold": eligible[0]["recovery_threshold"],
            "selection_reason": (
                "smallest candidate satisfying every frozen completeness, "
                "clean-FPR, and erasing-IoU constraint"
            ),
        }
        if eligible
        else None
    )

    formal_config = Path(str(contract.get("source_formal_config") or "")).resolve()
    formal_manifest = Path(str(contract.get("source_formal_manifest") or "")).resolve()
    if sha256_file(formal_config) != contract.get("source_formal_config_sha256"):
        raise ThresholdCalibrationError("Formal config changed during calibration.")
    if sha256_file(formal_manifest) != contract.get("source_formal_manifest_sha256"):
        raise ThresholdCalibrationError("Formal manifest changed during calibration.")
    formal_lock_audit = contract.get("source_formal_manifest_lock") or {}
    formal_lock_path = Path(str(formal_lock_audit.get("lock_path") or "")).resolve()
    if not formal_lock_path.is_file() or sha256_file(
        formal_lock_path
    ) != formal_lock_audit.get("lock_sha256"):
        raise ThresholdCalibrationError(
            "Formal manifest lock changed during calibration."
        )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "winner_selected" if winner else "no_candidate_satisfies_constraints",
        "run_class": RUN_CLASS,
        "development_only": True,
        "paper_eligible": False,
        "selection_split": SELECTION_SPLIT,
        "excluded_splits": ["train", "test"],
        "formal_test_rows_consumed": 0,
        "formal_config_update_performed": False,
        "formal_config_must_remain_unchanged_until_freeze": True,
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "preregistration_claim": preregistration_evidence,
        "selected_manifest": str(manifest_path),
        "selected_manifest_sha256": sha256_file(manifest_path),
        "selected_manifest_lock": manifest_lock_audit,
        "selected_samples": len(rows),
        "selection_seed": contract.get("selection_seed"),
        "evaluation_seeds": list(evaluation_seeds),
        "unique_image_sha256": len({row.sha256 for row in rows}),
        "unique_source_families": len({row.source_family for row in rows}),
        "selected_dataset_counts": contract.get("selected_dataset_counts"),
        "selected_domains": contract.get("selected_domains"),
        "formal_split_assignment_audit": contract.get("formal_split_assignment_audit"),
        "cross_candidate_attack_inputs_identical": True,
        "cross_candidate_environment_identity_identical": True,
        "immutable_environment_identity_sha256": next(
            iter(immutable_environment_identity_sha256)
        ),
        "immutable_environment_identity": analyzed[0]["immutable_environment_identity"],
        "attack_input_hash_map_sha256": next(iter(attack_input_hash_map_sha256)),
        "candidate_metrics": analyzed,
        "eligible_candidate_ids": [row["candidate_id"] for row in eligible],
        "winner_rule": contract.get("winner_rule"),
        "winner": winner,
        "constraints": contract.get("constraints"),
        "traditional_attack_runtime": {
            "implementation_path": str(attacks_path),
            "implementation_sha256": attacks_sha256,
            "required_packages": required_attack_runtime,
            "analyzer_packages": analyzer_attack_runtime,
            "observed_packages_by_candidate": {
                row["candidate_id"]: row["traditional_attack_runtime"][
                    "observed_packages"
                ]
                for row in analyzed
            },
            "artifact_retention": ATTACK_ARTIFACT_RETENTION,
        },
        "formal_inputs": {
            "config": str(formal_config),
            "config_sha256": sha256_file(formal_config),
            "manifest": str(formal_manifest),
            "manifest_sha256": sha256_file(formal_manifest),
            "manifest_lock": formal_lock_audit,
        },
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    run_root = (
        Path(args.run_root).expanduser().resolve()
        if args.run_root
        else config_path.parent.resolve()
    )
    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else run_root / "threshold_selection.json"
    )
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite selection report: {output}")
    report = analyze_threshold_calibration(config_path, run_root=run_root)
    _atomic_write_json(output, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["winner"] is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
