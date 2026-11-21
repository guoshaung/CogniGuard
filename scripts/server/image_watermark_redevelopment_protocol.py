"""Frozen constants and execution gates for the post-failure v3 protocol."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from protection.supporting.image_watermark.experiments.localization_artifacts import (
    LocalizationArtifactError,
    _validated_required_capabilities,
)


PROTOCOL_ID = "cogniguard-image-watermark-redevelopment-v1"
SPLIT_SEED = "388e1c31e9618f3587237c6dc1319846ec8e0d3af2ee7750344ddc921848767b"
HISTORY_AUDIT_CUTOFF_UTC = "2026-08-03T11:55:30Z"
ASSIGNMENT_SCHEMA_VERSION = "cogniguard_image_redevelopment_assignment_v1"
CALIBRATION_SCHEMA_VERSION = "cogniguard_image_spatial_filter_calibration_v3"
CONFIRMATION_SCHEMA_VERSION = "cogniguard_image_spatial_filter_confirmation_v3"
CALIBRATION_RUN_CLASS = "spatial_filter_calibration_development_only"
CONFIRMATION_RUN_CLASS = "spatial_filter_confirmation_development_only"
CALIBRATION_CONTRACT_KEY = "spatial_filter_calibration"
CONFIRMATION_CONTRACT_KEY = "spatial_filter_confirmation"
SELECTION_SPLIT = "dev"
FORMAL_TEST_ROWS_CONSUMED = 0
EXPECTED_FORMAL_SAMPLES = 3000
EXPECTED_FORMAL_SPLITS = {"train": 2109, "dev": 333, "test": 558}
EXPECTED_ROLE_COUNTS = {
    "tuning": 1209,
    "calibration": 300,
    "confirmation": 600,
    "legacy_observed_dev": 333,
    "formal_test_sealed": 558,
}
DATASET_ORDER = (
    "cogniguard_edufig_v2",
    "met_open_access_cc0",
    "open_images_v7_license_audited",
    "nasa_images_policy_audited",
)
CALIBRATION_DATASET_QUOTAS = {
    "cogniguard_edufig_v2": 119,
    "met_open_access_cc0": 81,
    "open_images_v7_license_audited": 60,
    "nasa_images_policy_audited": 40,
}
CONFIRMATION_DATASET_QUOTAS = {
    "cogniguard_edufig_v2": 238,
    "met_open_access_cc0": 162,
    "open_images_v7_license_audited": 119,
    "nasa_images_policy_audited": 81,
}
EVALUATION_SEEDS = (20260802, 20260803, 20260804)
ERASING_RATIOS = (0.05, 0.15, 0.25)
ATTACK_CONDITIONS = (
    "clean",
    "erasing__area_ratio-0.05",
    "erasing__area_ratio-0.15",
    "erasing__area_ratio-0.25",
)
SPATIAL_FILTER_CANDIDATES = (0.005, 0.01, 0.02)
FROZEN_RECOVERY_THRESHOLD = 0.34
FROZEN_FIXED_CAPABILITIES: dict[str, Any] = {
    "recovery_threshold": FROZEN_RECOVERY_THRESHOLD,
    "tamper_area_threshold": 0.001,
    "registry_hamming_radius": 1,
    "localization_postprocessing": "connected_component_min_area_ratio_v1",
    "localization_mask_rule_version": "editguard_residual_channel_vote_cc8_v3",
    "localization_residual_channels": 3,
    "localization_channel_aggregation": "k_of_3",
    "localization_channel_vote_min": 1,
    "localization_residual_threshold_rule": (
        "abs_gt_recovery_threshold_per_channel"
    ),
    "localization_component_connectivity": 8,
    "localization_component_area_rounding": "ceil_height_times_width",
}
CONSTRAINTS = {
    "clean_mean_mask_fpr_max": 1e-4,
    "clean_p99_mask_fpr_max": 5e-4,
    "clean_max_mask_fpr_max": 1e-3,
    "each_erasing_mean_mask_iou_min": 0.90,
    "each_erasing_p10_mask_iou_min": 0.75,
    "each_erasing_iou_at_least_0_75_rate_min": 0.95,
}
STATISTICAL_UNITS = {
    "primary": "source_sample_mean_across_three_seeds",
    "required_secondary_gate": "all_source_seed_rows",
}
REQUIRED_ATTACK_RUNTIME = {"numpy": "1.26.4", "Pillow": "10.4.0"}
ATTACK_ARTIFACT_RETENTION = "hash_only"


class RedevelopmentProtocolError(RuntimeError):
    """Raised when a v3 development artifact violates the frozen protocol."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def load_locked_assignment(
    assignment_path: str | Path,
    lock_path: str | Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    assignment = Path(assignment_path).expanduser().resolve()
    lock_file = Path(lock_path).expanduser().resolve()
    try:
        lock = json.loads(lock_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RedevelopmentProtocolError("Invalid redevelopment assignment lock.") from exc
    if not isinstance(lock, dict):
        raise RedevelopmentProtocolError("Redevelopment assignment lock is not an object.")
    declared_lock_payload = lock.get("lock_payload_sha256")
    lock_payload = dict(lock)
    lock_payload.pop("lock_payload_sha256", None)
    if (
        lock.get("schema_version") != ASSIGNMENT_SCHEMA_VERSION
        or lock.get("protocol_id") != PROTOCOL_ID
        or lock.get("split_seed") != SPLIT_SEED
        or lock.get("formal_test_rows_consumed") != 0
        or lock.get("role_counts") != EXPECTED_ROLE_COUNTS
        or lock.get("assignment_path") != str(assignment)
        or lock.get("assignment_file_sha256") != sha256_file(assignment)
        or lock.get("assignment_sha256") != sha256_file(assignment)
        or declared_lock_payload != canonical_sha256(lock_payload)
    ):
        raise RedevelopmentProtocolError(
            "Redevelopment assignment lock authentication failed."
        )
    rows: list[dict[str, Any]] = []
    try:
        with assignment.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise TypeError(f"row {line_number} is not an object")
                rows.append(row)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise RedevelopmentProtocolError(
            "Redevelopment assignment JSONL is malformed."
        ) from exc
    if len(rows) != EXPECTED_FORMAL_SAMPLES:
        raise RedevelopmentProtocolError("Redevelopment assignment must contain 3000 rows.")
    for field in ("sample_id", "source_family", "sha256"):
        if len({row.get(field) for row in rows}) != len(rows):
            raise RedevelopmentProtocolError(
                f"Redevelopment assignment has duplicate {field}."
            )
    observed_roles: dict[str, int] = {}
    for row in rows:
        role = str(row.get("redevelopment_role") or "")
        observed_roles[role] = observed_roles.get(role, 0) + 1
    if observed_roles != EXPECTED_ROLE_COUNTS:
        raise RedevelopmentProtocolError(
            "Redevelopment assignment role counts differ from its lock."
        )
    return rows, lock


def candidate_id(area_ratio: float) -> str:
    rendered = f"{area_ratio:.8f}".rstrip("0").rstrip(".").replace(".", "p")
    return f"cc8_min_component_area_ratio_{rendered}"


def required_capabilities(area_ratio: float) -> dict[str, Any]:
    if (
        type(area_ratio) is not float
        or not math.isfinite(area_ratio)
        or area_ratio not in SPATIAL_FILTER_CANDIDATES
    ):
        raise RedevelopmentProtocolError(
            "Spatial-filter area ratio is outside the frozen candidate grid."
        )
    required = {
        **copy.deepcopy(FROZEN_FIXED_CAPABILITIES),
        "localization_min_component_area_ratio": area_ratio,
    }
    try:
        _validated_required_capabilities(required)
    except LocalizationArtifactError as exc:
        raise RedevelopmentProtocolError(
            f"Internal v3 localization contract is invalid: {exc}"
        ) from exc
    return required


def candidate_runs() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": candidate_id(area_ratio),
            "localization_min_component_area_ratio": area_ratio,
        }
        for area_ratio in SPATIAL_FILTER_CANDIDATES
    ]


def _resolve_path(value: object, base: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise RedevelopmentProtocolError("Required protocol path is missing.")
    raw = Path(os.path.expandvars(value)).expanduser()
    return raw.resolve() if raw.is_absolute() else (base / raw).resolve()


def _enabled_editguard_method(config: Mapping[str, Any]) -> dict[str, Any]:
    methods = [
        dict(row)
        for row in (config.get("methods") or [])
        if isinstance(row, Mapping) and row.get("enabled", True)
    ]
    if (
        len(methods) != 1
        or methods[0].get("id") != "editguard_wrapper"
        or methods[0].get("kind", "sce_locguard_api") != "sce_locguard_api"
    ):
        raise RedevelopmentProtocolError(
            "v3 runs must enable exactly one editguard_wrapper API method."
        )
    return methods[0]


def resolve_development_required_capabilities(
    config_path: str | Path,
    output_dir: str | Path,
    *,
    run_class: str,
) -> dict[str, Any]:
    """Resolve one v3 candidate from its preregistered output path."""

    path = Path(config_path).expanduser().resolve()
    output = Path(output_dir).expanduser().resolve()
    try:
        config = yaml.safe_load(
            os.path.expandvars(path.read_text(encoding="utf-8"))
        ) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise RedevelopmentProtocolError(f"Unable to read v3 config: {exc}") from exc
    if not isinstance(config, dict):
        raise RedevelopmentProtocolError("v3 config root must be a mapping.")
    experiment = config.get("experiment") or {}
    if (
        not isinstance(experiment, Mapping)
        or experiment.get("run_class") != run_class
        or experiment.get("strict_paper_mode") is not True
        or experiment.get("fail_fast") is not True
        or experiment.get("development_only") is not True
        or experiment.get("paper_eligible") is not False
        or experiment.get("split") != SELECTION_SPLIT
    ):
        raise RedevelopmentProtocolError("v3 experiment markers are not exact.")
    method = _enabled_editguard_method(config)

    if run_class == CALIBRATION_RUN_CLASS:
        contract = config.get(CALIBRATION_CONTRACT_KEY) or {}
        if (
            not isinstance(contract, Mapping)
            or contract.get("schema_version") != CALIBRATION_SCHEMA_VERSION
            or contract.get("run_class") != CALIBRATION_RUN_CLASS
            or contract.get("candidate_runs") != candidate_runs()
            or contract.get("candidate_area_ratios")
            != list(SPATIAL_FILTER_CANDIDATES)
            or contract.get("fixed_capabilities") != FROZEN_FIXED_CAPABILITIES
            or contract.get("expected_samples") != 300
            or contract.get("formal_test_rows_consumed")
            != FORMAL_TEST_ROWS_CONSUMED
            or contract.get("formal_config_mutation_allowed") is not False
            or contract.get("formal_config_update_performed") is not False
        ):
            raise RedevelopmentProtocolError(
                "Spatial-filter calibration contract is not frozen v3."
            )
        expected_root = _resolve_path(
            experiment.get("output_root"), path.parent
        )
        matches = [
            row
            for row in candidate_runs()
            if (
                expected_root / str(row["candidate_id"]) / "benchmark"
            ).resolve()
            == output
        ]
        if len(matches) != 1:
            raise RedevelopmentProtocolError(
                "Calibration output does not bind exactly one v3 candidate."
            )
        if method.get("required_capabilities") != FROZEN_FIXED_CAPABILITIES:
            raise RedevelopmentProtocolError(
                "Calibration method capabilities differ from frozen v3 fields."
            )
        ratio = matches[0]["localization_min_component_area_ratio"]
        return required_capabilities(ratio)

    if run_class == CONFIRMATION_RUN_CLASS:
        contract = config.get(CONFIRMATION_CONTRACT_KEY) or {}
        selected = contract.get("selected_required_capabilities")
        expected_output = (
            _resolve_path(experiment.get("output_root"), path.parent) / "benchmark"
        ).resolve()
        if (
            not isinstance(contract, Mapping)
            or contract.get("schema_version") != CONFIRMATION_SCHEMA_VERSION
            or contract.get("run_class") != CONFIRMATION_RUN_CLASS
            or contract.get("expected_samples") != 600
            or contract.get("formal_test_rows_consumed")
            != FORMAL_TEST_ROWS_CONSUMED
            or contract.get("formal_config_mutation_allowed") is not False
            or contract.get("formal_config_update_performed") is not False
            or output != expected_output
            or not isinstance(selected, Mapping)
        ):
            raise RedevelopmentProtocolError(
                "Spatial-filter confirmation contract is not frozen v3."
            )
        ratio = selected.get("localization_min_component_area_ratio")
        required = required_capabilities(ratio)
        if dict(selected) != required or method.get("required_capabilities") != required:
            raise RedevelopmentProtocolError(
                "Confirmation method differs from its sole selected candidate."
            )
        return required

    raise RedevelopmentProtocolError(f"Unsupported v3 run class: {run_class!r}.")


__all__ = [
    "ASSIGNMENT_SCHEMA_VERSION",
    "ATTACK_ARTIFACT_RETENTION",
    "ATTACK_CONDITIONS",
    "CALIBRATION_CONTRACT_KEY",
    "CALIBRATION_DATASET_QUOTAS",
    "CALIBRATION_RUN_CLASS",
    "CALIBRATION_SCHEMA_VERSION",
    "CONFIRMATION_CONTRACT_KEY",
    "CONFIRMATION_DATASET_QUOTAS",
    "CONFIRMATION_RUN_CLASS",
    "CONFIRMATION_SCHEMA_VERSION",
    "CONSTRAINTS",
    "DATASET_ORDER",
    "ERASING_RATIOS",
    "EVALUATION_SEEDS",
    "EXPECTED_FORMAL_SAMPLES",
    "EXPECTED_FORMAL_SPLITS",
    "EXPECTED_ROLE_COUNTS",
    "FORMAL_TEST_ROWS_CONSUMED",
    "FROZEN_FIXED_CAPABILITIES",
    "HISTORY_AUDIT_CUTOFF_UTC",
    "PROTOCOL_ID",
    "REQUIRED_ATTACK_RUNTIME",
    "RedevelopmentProtocolError",
    "SELECTION_SPLIT",
    "SPATIAL_FILTER_CANDIDATES",
    "SPLIT_SEED",
    "STATISTICAL_UNITS",
    "candidate_id",
    "candidate_runs",
    "required_capabilities",
    "resolve_development_required_capabilities",
    "canonical_sha256",
    "load_locked_assignment",
    "sha256_file",
]
