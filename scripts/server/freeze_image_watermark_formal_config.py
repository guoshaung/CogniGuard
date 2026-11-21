#!/usr/bin/env python3
"""Freeze a validated dev-only threshold winner into fresh formal inputs.

This is deliberately a one-way, fail-closed publication step.  It never edits
the formal config/manifest/lock used as calibration inputs.  Instead it creates
a new config, reconstructs the complete manifest from the configured datasets,
requires the reconstructed JSONL bytes to equal the calibration source
manifest, and writes a new adjacent lock bound to the new config.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Mapping

import yaml

from protection.supporting.image_watermark.experiments.manifest import (
    build_manifest_from_config,
    dataset_roots_from_config,
    load_manifest,
    manifest_assignment_sha256,
    manifest_lock_path,
    manifest_path_from_config,
    validate_manifest_lock,
    write_manifest,
)
from protection.supporting.image_watermark.experiments.paper_benchmark import (
    SOURCE_TREE_IDENTITY_VERSION,
    _source_tree_identity_scope,
)
from scripts.server.analyze_image_watermark_threshold_calibration import (
    CONSTRAINTS,
    EXPECTED_FIXED_PARAMETERS,
    REPORT_SCHEMA_VERSION,
    ThresholdCalibrationError,
    _validate_calibration_config,
    _validate_selected_manifest,
    analyze_threshold_calibration,
)
from scripts.server.build_image_watermark_threshold_calibration import (
    ERASING_RATIOS,
    EVALUATION_SEEDS,
    EXPECTED_SAMPLES,
    FROZEN_THRESHOLDS,
    RUN_CLASS,
    SELECTION_SPLIT,
    candidate_id,
    manifest_text,
    sha256_file,
)
from scripts.server.image_watermark_preregistration import (
    PreregistrationError,
    validate_preregistration_claim,
)


FORMAL_SELECTION_SCHEMA_VERSION = "cogniguard_image_formal_selection_v2"
EXPECTED_FORMAL_SAMPLES = 3000
FORMAL_RUN_CLASS = "formal_paper_candidate"
FORMAL_METHOD_ID = "editguard_wrapper"
FLOAT_ABS_TOLERANCE = 1e-12
THRESHOLD_LOCALIZATION_CAPABILITIES = {
    "localization_mask_rule_version": "editguard_residual_channel_vote_v2",
    "localization_residual_channels": 3,
    "localization_channel_aggregation": "k_of_3",
    "localization_channel_vote_min": 1,
    "localization_residual_threshold_rule": ("abs_gt_recovery_threshold_per_channel"),
}


class FormalFreezeError(RuntimeError):
    """Raised when calibration evidence cannot be frozen safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a fresh formal config and byte-equivalent full manifest from "
            "a validated development-only threshold-selection report."
        )
    )
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--selection-report", type=Path, required=True)
    parser.add_argument("--output-config", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    return parser.parse_args()


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FormalFreezeError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise FormalFreezeError(f"{label} must be a JSON object: {path}")
    return payload


def _read_yaml(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise FormalFreezeError(f"{label} is not valid YAML: {path}") from exc
    if not isinstance(payload, dict):
        raise FormalFreezeError(f"{label} must be a YAML mapping: {path}")
    return payload


def _finite_number(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FormalFreezeError(f"{label} must be a finite numeric value.")
    result = float(value)
    if not math.isfinite(result):
        raise FormalFreezeError(f"{label} must be a finite numeric value.")
    return result


def _require_sha256(value: Any, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise FormalFreezeError(f"{label} must be a lowercase hexadecimal SHA-256.")
    return value


def _calibration_source_tree_identity(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract and authenticate the calibration run's recorded source tree."""

    immutable_identity = report.get("immutable_environment_identity")
    if not isinstance(immutable_identity, Mapping):
        raise FormalFreezeError(
            "Selection report immutable_environment_identity must be a mapping."
        )
    declared_identity_sha256 = _require_sha256(
        report.get("immutable_environment_identity_sha256"),
        label="immutable_environment_identity_sha256",
    )
    canonical_identity = json.dumps(
        dict(immutable_identity),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    observed_identity_sha256 = hashlib.sha256(canonical_identity).hexdigest()
    if observed_identity_sha256 != declared_identity_sha256:
        raise FormalFreezeError(
            "Selection report immutable_environment_identity_sha256 does not "
            "authenticate immutable_environment_identity."
        )

    identity_version = immutable_identity.get("source_tree_identity_version")
    if identity_version != SOURCE_TREE_IDENTITY_VERSION:
        raise FormalFreezeError(
            "immutable_environment_identity.source_tree_identity_version is "
            f"not {SOURCE_TREE_IDENTITY_VERSION!r}."
        )
    source_tree_scope = immutable_identity.get("source_tree_scope")
    expected_scope = _source_tree_identity_scope()
    if source_tree_scope != expected_scope:
        raise FormalFreezeError(
            "immutable_environment_identity.source_tree_scope differs from the "
            "required formal source-tree scope."
        )
    source_tree_sha256 = _require_sha256(
        immutable_identity.get("source_tree_sha256"),
        label="immutable_environment_identity.source_tree_sha256",
    )
    source_tree_file_count = immutable_identity.get("source_tree_file_count")
    if type(source_tree_file_count) is not int or source_tree_file_count <= 0:
        raise FormalFreezeError(
            "immutable_environment_identity.source_tree_file_count must be a "
            "positive integer."
        )
    return {
        "identity_version": identity_version,
        "scope": source_tree_scope,
        "sha256": source_tree_sha256,
        "file_count": source_tree_file_count,
    }


def _same_float(left: Any, right: Any) -> bool:
    try:
        left_value = _finite_number(left, label="left comparison value")
        right_value = _finite_number(right, label="right comparison value")
    except FormalFreezeError:
        return False
    return math.isclose(
        left_value,
        right_value,
        rel_tol=0.0,
        abs_tol=FLOAT_ABS_TOLERANCE,
    )


def _expected_constraint_names() -> set[str]:
    names = {
        "clean_mean_mask_fpr",
        "clean_p99_mask_fpr",
        "clean_max_mask_fpr",
    }
    for ratio in ERASING_RATIOS:
        names.update(
            {
                f"erasing_{ratio:.2f}_mean_mask_iou",
                f"erasing_{ratio:.2f}_p10_mask_iou",
                f"erasing_{ratio:.2f}_iou_at_least_0_75_rate",
            }
        )
    return names


def _validate_candidate_metrics(
    report: Mapping[str, Any],
) -> tuple[dict[str, Any], float]:
    candidate_rows = report.get("candidate_metrics")
    if not isinstance(candidate_rows, list) or not all(
        isinstance(row, dict) for row in candidate_rows
    ):
        raise FormalFreezeError("Selection report candidate_metrics are malformed.")
    if len(candidate_rows) != len(FROZEN_THRESHOLDS):
        raise FormalFreezeError(
            "Selection report must contain the exact frozen nine-candidate grid."
        )

    expected_names = _expected_constraint_names()
    seen_ids: set[str] = set()
    passed_ids: list[str] = []
    candidates_by_id: dict[str, dict[str, Any]] = {}
    for row, expected_threshold in zip(candidate_rows, FROZEN_THRESHOLDS, strict=True):
        threshold = _finite_number(
            row.get("recovery_threshold"), label="Candidate recovery_threshold"
        )
        expected_id = candidate_id(expected_threshold)
        observed_id = row.get("candidate_id")
        if not _same_float(threshold, expected_threshold) or observed_id != expected_id:
            raise FormalFreezeError(
                "Selection report candidate grid/order differs from the frozen protocol."
            )
        if observed_id in seen_ids:
            raise FormalFreezeError(
                "Selection report contains duplicate candidate IDs."
            )
        seen_ids.add(str(observed_id))

        checks = row.get("constraint_checks")
        if not isinstance(checks, list) or not all(
            isinstance(check, dict) for check in checks
        ):
            raise FormalFreezeError(
                f"Candidate {observed_id} constraint_checks are malformed."
            )
        check_names = [str(check.get("name") or "") for check in checks]
        if (
            len(check_names) != len(expected_names)
            or set(check_names) != expected_names
        ):
            raise FormalFreezeError(
                f"Candidate {observed_id} does not contain the exact frozen constraints."
            )
        if any(type(check.get("passed")) is not bool for check in checks):
            raise FormalFreezeError(
                f"Candidate {observed_id} constraint pass values must be booleans."
            )
        computed_passed = all(bool(check["passed"]) for check in checks)
        if type(row.get("all_constraints_passed")) is not bool or (
            row["all_constraints_passed"] is not computed_passed
        ):
            raise FormalFreezeError(
                f"Candidate {observed_id} all_constraints_passed is inconsistent."
            )
        if (
            row.get("development_only") is not True
            or row.get("paper_eligible") is not False
        ):
            raise FormalFreezeError(
                f"Candidate {observed_id} is not marked development-only/non-paper."
            )
        if row.get("evaluation_seeds") != list(EVALUATION_SEEDS):
            raise FormalFreezeError(
                f"Candidate {observed_id} evaluation seeds differ from the frozen protocol."
            )
        if computed_passed:
            passed_ids.append(str(observed_id))
        candidates_by_id[str(observed_id)] = row

    eligible_ids = report.get("eligible_candidate_ids")
    if eligible_ids != passed_ids:
        raise FormalFreezeError(
            "Selection report eligible_candidate_ids differ from passing candidates."
        )
    if not passed_ids:
        raise FormalFreezeError("Selection report has no eligible threshold candidate.")

    winner = report.get("winner")
    if not isinstance(winner, dict):
        raise FormalFreezeError("Selection report winner is missing or malformed.")
    winner_id = str(winner.get("candidate_id") or "")
    winner_threshold = _finite_number(
        winner.get("recovery_threshold"), label="Winner recovery_threshold"
    )
    expected_winner_id = passed_ids[0]
    expected_winner = candidates_by_id[expected_winner_id]
    if (
        winner_id != expected_winner_id
        or not _same_float(winner_threshold, expected_winner.get("recovery_threshold"))
        or expected_winner.get("all_constraints_passed") is not True
    ):
        raise FormalFreezeError(
            "Winner is not the smallest eligible candidate with all constraints passed."
        )
    if not 0.0 < winner_threshold < 1.0:
        raise FormalFreezeError("Winner recovery_threshold must be in (0, 1).")
    return expected_winner, winner_threshold


def _validate_report_protocol(
    report: Mapping[str, Any],
) -> tuple[dict[str, Any], float]:
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise FormalFreezeError("Unsupported threshold-selection report schema.")
    if report.get("status") != "winner_selected":
        raise FormalFreezeError("Selection report status must be winner_selected.")
    if (
        report.get("run_class") != RUN_CLASS
        or report.get("development_only") is not True
        or report.get("paper_eligible") is not False
        or report.get("selection_split") != SELECTION_SPLIT
        or report.get("excluded_splits") != ["train", "test"]
        or report.get("formal_test_rows_consumed") != 0
        or report.get("formal_config_update_performed") is not False
        or report.get("formal_config_must_remain_unchanged_until_freeze") is not True
    ):
        raise FormalFreezeError(
            "Selection report is not the frozen dev-only/test-unconsumed protocol."
        )
    if report.get("evaluation_seeds") != list(EVALUATION_SEEDS):
        raise FormalFreezeError("Selection report evaluation seeds are not frozen.")
    if report.get("constraints") != CONSTRAINTS:
        raise FormalFreezeError(
            "Selection report constraints differ from the protocol."
        )
    if (
        report.get("cross_candidate_attack_inputs_identical") is not True
        or report.get("cross_candidate_environment_identity_identical") is not True
    ):
        raise FormalFreezeError(
            "Selection report does not prove identical candidate inputs/environments."
        )
    _calibration_source_tree_identity(report)
    _require_sha256(
        report.get("attack_input_hash_map_sha256"),
        label="attack_input_hash_map_sha256",
    )
    return _validate_candidate_metrics(report)


def _assert_candidate_runs_reproduce_report(
    report: Mapping[str, Any],
    *,
    calibration_config: Path,
    selection_report: Path,
) -> None:
    run_root = selection_report.parent.resolve()
    if calibration_config.parent.resolve() != run_root:
        raise FormalFreezeError(
            "Selection report and calibration config must share one immutable run root."
        )
    candidate_root = run_root / "candidate-runs"
    if not candidate_root.is_dir():
        raise FormalFreezeError(
            f"Calibration candidate-runs directory is missing: {candidate_root}"
        )
    try:
        recomputed = analyze_threshold_calibration(
            calibration_config,
            run_root=run_root,
        )
    except (OSError, ThresholdCalibrationError, TypeError, ValueError) as exc:
        raise FormalFreezeError(
            f"Candidate runs failed independent threshold reanalysis: {exc}"
        ) from exc
    reported_canonical = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    recomputed_canonical = json.dumps(
        recomputed,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if reported_canonical != recomputed_canonical:
        raise FormalFreezeError(
            "Threshold-selection report differs from independent candidate-run "
            "reanalysis."
        )


def _resolve_report_file(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise FormalFreezeError(f"Selection report {label} path is missing.")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FormalFreezeError(f"Selection report {label} is missing: {path}")
    return path


def _validate_calibration_evidence(
    report: Mapping[str, Any], source_config: Path
) -> tuple[dict[str, Any], dict[str, Any], Path, Path, dict[str, Any]]:
    calibration_config = _resolve_report_file(report.get("config"), label="config")
    if sha256_file(calibration_config) != report.get("config_sha256"):
        raise FormalFreezeError("Calibration config SHA-256 differs from the report.")
    try:
        preregistration_evidence = validate_preregistration_claim(
            calibration_config,
            expected_run_class=RUN_CLASS,
        )
    except PreregistrationError as exc:
        raise FormalFreezeError(
            f"Calibration preregistration evidence is invalid: {exc}"
        ) from exc
    if report.get("preregistration_claim") != preregistration_evidence:
        raise FormalFreezeError(
            "Selection report preregistration claim differs from the frozen bundle."
        )
    try:
        calibration_payload, calibration_contract = _validate_calibration_config(
            calibration_config
        )
        selected_rows, selected_manifest, selected_lock_audit = (
            _validate_selected_manifest(calibration_config, calibration_contract)
        )
    except (OSError, ThresholdCalibrationError, TypeError, ValueError) as exc:
        raise FormalFreezeError(
            f"Calibration bundle failed strict revalidation: {exc}"
        ) from exc

    if (
        str(selected_manifest) != report.get("selected_manifest")
        or sha256_file(selected_manifest) != report.get("selected_manifest_sha256")
        or selected_lock_audit != report.get("selected_manifest_lock")
        or len(selected_rows) != EXPECTED_SAMPLES
        or report.get("selected_samples") != EXPECTED_SAMPLES
        or report.get("unique_image_sha256") != EXPECTED_SAMPLES
        or report.get("unique_source_families") != EXPECTED_SAMPLES
    ):
        raise FormalFreezeError(
            "Selection report dev manifest evidence differs from the calibration bundle."
        )
    if report.get("formal_split_assignment_audit") != calibration_contract.get(
        "formal_split_assignment_audit"
    ):
        raise FormalFreezeError(
            "Selection report formal split audit differs from the calibration bundle."
        )
    for report_field, contract_field in (
        ("selection_seed", "selection_seed"),
        ("selected_dataset_counts", "selected_dataset_counts"),
        ("selected_domains", "selected_domains"),
        ("winner_rule", "winner_rule"),
    ):
        if report.get(report_field) != calibration_contract.get(contract_field):
            raise FormalFreezeError(
                f"Selection report {report_field} differs from the calibration bundle."
            )

    formal_inputs = report.get("formal_inputs")
    if not isinstance(formal_inputs, dict):
        raise FormalFreezeError("Selection report formal_inputs are missing.")
    reported_source_config = _resolve_report_file(
        formal_inputs.get("config"), label="source formal config"
    )
    if reported_source_config != source_config:
        raise FormalFreezeError(
            "--source-config is not the formal config bound by the selection report."
        )
    source_config_sha256 = sha256_file(source_config)
    if source_config_sha256 != formal_inputs.get("config_sha256"):
        raise FormalFreezeError("Source formal config SHA-256 differs from the report.")

    source_manifest = manifest_path_from_config(source_config, environ={})
    reported_source_manifest = _resolve_report_file(
        formal_inputs.get("manifest"), label="source formal manifest"
    )
    if source_manifest != reported_source_manifest or sha256_file(
        source_manifest
    ) != formal_inputs.get("manifest_sha256"):
        raise FormalFreezeError(
            "Source formal manifest SHA-256/path differs from the report."
        )
    source_roots = dataset_roots_from_config(source_config, environ={})
    try:
        source_rows = load_manifest(
            source_manifest,
            dataset_roots=source_roots,
            require_files=True,
            verify_hashes=True,
        )
        source_lock_audit = validate_manifest_lock(
            source_manifest,
            source_rows,
            config_path=source_config,
            dataset_roots=source_roots,
        )
    except (OSError, ValueError) as exc:
        raise FormalFreezeError(
            f"Source formal manifest/lock failed strict validation: {exc}"
        ) from exc
    if source_lock_audit != formal_inputs.get("manifest_lock"):
        raise FormalFreezeError(
            "Source formal manifest lock differs from the selection report."
        )
    if source_lock_audit != calibration_contract.get("source_formal_manifest_lock"):
        raise FormalFreezeError(
            "Source formal manifest lock differs from the calibration contract."
        )
    return (
        calibration_payload,
        calibration_contract,
        calibration_config,
        source_manifest,
        source_lock_audit,
    )


def _validate_source_formal_config(
    source_payload: Mapping[str, Any], *, expected_formal_samples: int
) -> None:
    experiment = source_payload.get("experiment")
    manifest = source_payload.get("manifest")
    requirements = source_payload.get("data_requirements")
    if (
        not isinstance(experiment, dict)
        or experiment.get("strict_paper_mode") is not True
        or experiment.get("fail_fast") is not True
        or experiment.get("split") != "test"
        or int(experiment.get("max_samples", 0) or 0) != 0
        or not isinstance(manifest, dict)
        or manifest.get("verify_hashes") is not True
        or manifest.get("require_lock") is not True
        or not isinstance(requirements, dict)
        or requirements.get("expected_total_samples") != expected_formal_samples
        or requirements.get("required_evaluation_split") != "test"
        or requirements.get("require_max_samples_zero") is not True
    ):
        raise FormalFreezeError(
            "Source config is not the exact locked strict formal-test configuration."
        )
    if "formal_selection" in source_payload:
        raise FormalFreezeError("Source config is already a selected formal config.")


def _relative_reference(target: Path, *, base: Path) -> str:
    try:
        return Path(os.path.relpath(target, start=base)).as_posix()
    except ValueError:
        return str(target)


def _rebase_config_paths(
    payload: dict[str, Any], *, source_config: Path, output_config: Path
) -> None:
    source_base = source_config.parent
    output_base = output_config.parent
    experiment = payload.get("experiment")
    if isinstance(experiment, dict) and experiment.get("output_root"):
        original_output = Path(str(experiment["output_root"]))
        if not original_output.is_absolute():
            original_output = source_base / original_output
        experiment["output_root"] = _relative_reference(
            original_output.expanduser().resolve(), base=output_base
        )
    for dataset in payload.get("datasets") or []:
        if not isinstance(dataset, dict) or not dataset.get("root"):
            continue
        original_root = Path(str(dataset["root"]))
        if not original_root.is_absolute():
            original_root = source_base / original_root
        dataset["root"] = _relative_reference(
            original_root.expanduser().resolve(), base=output_base
        )


def _required_capabilities(
    winner_threshold: float, selection_report: Mapping[str, Any]
) -> dict[str, Any]:
    tamper_threshold = _finite_number(
        EXPECTED_FIXED_PARAMETERS.get("tamper_area_threshold"),
        label="Frozen tamper_area_threshold",
    )
    registry_radius = EXPECTED_FIXED_PARAMETERS.get("registry_hamming_radius")
    postprocessing = EXPECTED_FIXED_PARAMETERS.get("localization_postprocessing")
    if type(registry_radius) is not int or registry_radius < 0:
        raise FormalFreezeError(
            "Frozen registry_hamming_radius must be a non-negative integer."
        )
    if not isinstance(postprocessing, str) or not postprocessing:
        raise FormalFreezeError(
            "Frozen localization_postprocessing must be a non-empty string."
        )
    for name, expected in THRESHOLD_LOCALIZATION_CAPABILITIES.items():
        observed = EXPECTED_FIXED_PARAMETERS.get(name)
        if type(observed) is not type(expected) or observed != expected:
            raise FormalFreezeError(
                f"Frozen threshold-calibration capability {name!r} must be "
                f"exactly {expected!r}; observed {observed!r}."
            )
    identity = selection_report.get("immutable_environment_identity")
    fixed_capabilities = (
        identity.get("fixed_capabilities") if isinstance(identity, Mapping) else None
    )
    if not isinstance(fixed_capabilities, Mapping):
        raise FormalFreezeError(
            "Calibration report has no authenticated fixed-capability identity."
        )
    attack_model_id = fixed_capabilities.get("attack_model_id")
    attack_model_revision = fixed_capabilities.get("attack_model_revision")
    deterministic_mode_enabled = fixed_capabilities.get(
        "deterministic_mode_enabled"
    )
    if attack_model_id != "stable-diffusion-v1-5/stable-diffusion-inpainting":
        raise FormalFreezeError("Calibration attack_model_id is not frozen.")
    if (
        type(attack_model_revision) is not str
        or re.fullmatch(r"[0-9a-f]{40}", attack_model_revision) is None
    ):
        raise FormalFreezeError(
            "Calibration attack_model_revision must be an exact 40-character commit."
        )
    if deterministic_mode_enabled is not True:
        raise FormalFreezeError(
            "Calibration deterministic_mode_enabled must be exactly true."
        )
    return {
        "recovery_threshold": float(winner_threshold),
        "tamper_area_threshold": float(tamper_threshold),
        "registry_hamming_radius": registry_radius,
        "localization_postprocessing": postprocessing,
        **copy.deepcopy(THRESHOLD_LOCALIZATION_CAPABILITIES),
        "attack_model_id": attack_model_id,
        "attack_model_revision": attack_model_revision,
        "deterministic_mode_enabled": deterministic_mode_enabled,
    }


def _build_selected_config(
    source_payload: Mapping[str, Any],
    *,
    source_config: Path,
    source_manifest: Path,
    source_lock_audit: Mapping[str, Any],
    selection_report: Path,
    selection_report_sha256: str,
    selection_report_payload: Mapping[str, Any],
    output_config: Path,
    output_manifest: Path,
    winner_threshold: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    selected = copy.deepcopy(dict(source_payload))
    _rebase_config_paths(
        selected, source_config=source_config, output_config=output_config
    )
    experiment = selected.setdefault("experiment", {})
    experiment["run_class"] = FORMAL_RUN_CLASS
    experiment["paper_eligible"] = True
    experiment["development_only"] = False
    selected.setdefault("manifest", {})["path"] = _relative_reference(
        output_manifest, base=output_config.parent
    )

    enabled_editguard = [
        method
        for method in selected.get("methods") or []
        if isinstance(method, dict)
        and method.get("enabled", True)
        and method.get("id") == FORMAL_METHOD_ID
    ]
    if len(enabled_editguard) != 1:
        raise FormalFreezeError(
            "Source config must contain exactly one enabled editguard_wrapper method."
        )
    if "required_capabilities" in enabled_editguard[0]:
        raise FormalFreezeError(
            "Source editguard_wrapper already declares required_capabilities."
        )
    required_capabilities = _required_capabilities(
        winner_threshold, selection_report_payload
    )
    enabled_editguard[0]["required_capabilities"] = copy.deepcopy(required_capabilities)

    formal_inputs = dict(selection_report_payload["formal_inputs"])
    selected_lock = dict(selection_report_payload["selected_manifest_lock"])
    calibration_source_tree = _calibration_source_tree_identity(
        selection_report_payload
    )
    selected["formal_selection"] = {
        "schema_version": FORMAL_SELECTION_SCHEMA_VERSION,
        "status": "frozen",
        "method_id": FORMAL_METHOD_ID,
        "selection_source": "development_only_threshold_calibration",
        "selection_split": SELECTION_SPLIT,
        "excluded_splits": ["train", "test"],
        "formal_test_rows_consumed": 0,
        "selection_report": _relative_reference(
            selection_report, base=output_config.parent
        ),
        "selection_report_sha256": selection_report_sha256,
        "selection_report_schema_version": REPORT_SCHEMA_VERSION,
        "calibration_config": _relative_reference(
            Path(str(selection_report_payload["config"])).resolve(),
            base=output_config.parent,
        ),
        "calibration_config_sha256": selection_report_payload["config_sha256"],
        "calibration_selected_manifest_sha256": selection_report_payload[
            "selected_manifest_sha256"
        ],
        "calibration_selected_manifest_lock_sha256": selected_lock["lock_sha256"],
        "calibration_preregistration": {
            "schema_version": selection_report_payload[
                "preregistration_claim"
            ]["schema_version"],
            "nonce": selection_report_payload["preregistration_claim"]["nonce"],
            "claim": _relative_reference(
                Path(
                    str(
                        selection_report_payload["preregistration_claim"][
                            "source_claim_path"
                        ]
                    )
                ).resolve(),
                base=output_config.parent,
            ),
            "claim_sha256": selection_report_payload[
                "preregistration_claim"
            ]["source_claim_sha256"],
            "config_sha256": selection_report_payload[
                "preregistration_claim"
            ]["config_sha256"],
            "manifest_sha256": selection_report_payload[
                "preregistration_claim"
            ]["manifest_sha256"],
            "manifest_lock_sha256": selection_report_payload[
                "preregistration_claim"
            ]["manifest_lock_sha256"],
            "claim_committed_before_candidate_execution": True,
            "external_append_only_anchor_present": False,
            "evidence_limitation": selection_report_payload[
                "preregistration_claim"
            ]["evidence_limitation"],
        },
        "winner_candidate_id": selection_report_payload["winner"]["candidate_id"],
        "winner_rule": selection_report_payload["winner_rule"],
        "selected_parameters": copy.deepcopy(required_capabilities),
        "source_formal_config": _relative_reference(
            source_config, base=output_config.parent
        ),
        "source_formal_config_sha256": formal_inputs["config_sha256"],
        "source_formal_manifest": _relative_reference(
            source_manifest, base=output_config.parent
        ),
        "source_formal_manifest_sha256": formal_inputs["manifest_sha256"],
        "source_formal_manifest_lock": _relative_reference(
            Path(str(source_lock_audit["lock_path"])).resolve(),
            base=output_config.parent,
        ),
        "source_formal_manifest_lock_sha256": source_lock_audit["lock_sha256"],
        "source_assignment_sha256": source_lock_audit["assignment_sha256"],
        "immutable_environment_identity_sha256": selection_report_payload[
            "immutable_environment_identity_sha256"
        ],
        "calibration_source_tree_identity_version": calibration_source_tree[
            "identity_version"
        ],
        "calibration_source_tree_scope": copy.deepcopy(
            calibration_source_tree["scope"]
        ),
        "calibration_source_tree_sha256": calibration_source_tree["sha256"],
        "calibration_source_tree_file_count": calibration_source_tree["file_count"],
        "attack_input_hash_map_sha256": selection_report_payload[
            "attack_input_hash_map_sha256"
        ],
    }
    return selected, required_capabilities


def _assert_selection_evidence_unchanged(
    report: Mapping[str, Any],
    *,
    selection_report: Path,
    selection_report_sha256: str,
) -> None:
    if sha256_file(selection_report) != selection_report_sha256:
        raise FormalFreezeError("Selection report changed during formal freeze.")
    calibration_config = Path(str(report.get("config") or "")).resolve()
    if not calibration_config.is_file() or sha256_file(
        calibration_config
    ) != report.get("config_sha256"):
        raise FormalFreezeError("Calibration config changed during formal freeze.")
    selected_manifest = Path(str(report.get("selected_manifest") or "")).resolve()
    if not selected_manifest.is_file() or sha256_file(selected_manifest) != report.get(
        "selected_manifest_sha256"
    ):
        raise FormalFreezeError(
            "Calibration selected manifest changed during formal freeze."
        )
    selected_lock = report.get("selected_manifest_lock")
    if not isinstance(selected_lock, Mapping):
        raise FormalFreezeError(
            "Calibration selected manifest lock evidence is missing."
        )
    selected_lock_path = Path(str(selected_lock.get("lock_path") or "")).resolve()
    if not selected_lock_path.is_file() or sha256_file(
        selected_lock_path
    ) != selected_lock.get("lock_sha256"):
        raise FormalFreezeError(
            "Calibration selected manifest lock changed during formal freeze."
        )


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if temporary.exists():
        raise FileExistsError(f"Temporary output already exists: {temporary}")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing output: {path}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _assert_fresh_outputs(output_config: Path, output_manifest: Path) -> None:
    output_lock = manifest_lock_path(output_manifest)
    collisions = [
        path for path in (output_config, output_manifest, output_lock) if path.exists()
    ]
    if collisions:
        raise FileExistsError(
            "Refusing to overwrite selected formal outputs: "
            + ", ".join(str(path) for path in collisions)
        )
    if output_config == output_manifest or output_config == output_lock:
        raise FormalFreezeError(
            "Selected config, manifest, and lock paths must differ."
        )


def _assert_lock_invariants(
    source_lock: Mapping[str, Any],
    selected_lock: Mapping[str, Any],
    *,
    output_config: Path,
    output_manifest: Path,
) -> None:
    invariant_fields = (
        "manifest_sha256",
        "total_samples",
        "dataset_counts",
        "split_counts",
        "unique_sha256_count",
        "unique_source_family_count",
        "assignment_sha256",
        "upstream_dataset_locks",
    )
    mismatches = {
        field: {
            "source": source_lock.get(field),
            "selected": selected_lock.get(field),
        }
        for field in invariant_fields
        if source_lock.get(field) != selected_lock.get(field)
    }
    if mismatches:
        raise FormalFreezeError(
            f"Selected formal manifest lock changed frozen data evidence: {mismatches}"
        )
    if selected_lock.get("manifest_filename") != output_manifest.name:
        raise FormalFreezeError("Selected lock manifest_filename is incorrect.")
    if selected_lock.get("config_sha256") != sha256_file(output_config):
        raise FormalFreezeError("Selected lock does not bind the selected config.")


def _resolve_selected_reference(
    selected_config: Path,
    value: Any,
    *,
    label: str,
) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise FormalFreezeError(f"Selected formal {label} path is missing.")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = selected_config.parent / path
    path = path.resolve()
    if not path.is_file():
        raise FormalFreezeError(f"Selected formal {label} is missing: {path}")
    return path


def validate_frozen_formal_config(
    selected_config: Path,
    *,
    expected_formal_samples: int = EXPECTED_FORMAL_SAMPLES,
) -> dict[str, Any]:
    """Revalidate a published formal freeze and its complete evidence chain."""

    selected_config = selected_config.expanduser().resolve()
    if expected_formal_samples <= 0:
        raise ValueError("expected_formal_samples must be positive.")
    selected_payload = _read_yaml(selected_config, label="Selected formal config")
    selection = selected_payload.get("formal_selection")
    if not isinstance(selection, dict):
        raise FormalFreezeError("Selected config formal_selection is missing.")
    if (
        selection.get("schema_version") != FORMAL_SELECTION_SCHEMA_VERSION
        or selection.get("status") != "frozen"
        or selection.get("method_id") != FORMAL_METHOD_ID
        or selection.get("selection_source") != "development_only_threshold_calibration"
        or selection.get("selection_split") != SELECTION_SPLIT
        or selection.get("excluded_splits") != ["train", "test"]
        or type(selection.get("formal_test_rows_consumed")) is not int
        or selection.get("formal_test_rows_consumed") != 0
        or selection.get("selection_report_schema_version") != REPORT_SCHEMA_VERSION
    ):
        raise FormalFreezeError(
            "Selected config does not contain the exact frozen formal-selection contract."
        )

    selection_report = _resolve_selected_reference(
        selected_config,
        selection.get("selection_report"),
        label="threshold-selection report",
    )
    selection_report_sha256 = _require_sha256(
        selection.get("selection_report_sha256"),
        label="selection_report_sha256",
    )
    if sha256_file(selection_report) != selection_report_sha256:
        raise FormalFreezeError("Selected threshold-selection report SHA-256 differs.")
    report = _read_json(selection_report, label="Threshold-selection report")
    calibration_source_tree = _calibration_source_tree_identity(report)
    if (
        selection.get("calibration_source_tree_identity_version")
        != calibration_source_tree["identity_version"]
        or selection.get("calibration_source_tree_scope")
        != calibration_source_tree["scope"]
    ):
        raise FormalFreezeError(
            "Selected calibration source-tree version/scope differs from the "
            "threshold-selection report."
        )
    selected_source_tree_sha256 = _require_sha256(
        selection.get("calibration_source_tree_sha256"),
        label="calibration_source_tree_sha256",
    )
    selected_source_tree_file_count = selection.get(
        "calibration_source_tree_file_count"
    )
    if (
        type(selected_source_tree_file_count) is not int
        or selected_source_tree_file_count <= 0
    ):
        raise FormalFreezeError(
            "calibration_source_tree_file_count must be a positive integer."
        )
    if (
        selected_source_tree_sha256 != calibration_source_tree["sha256"]
        or selected_source_tree_file_count != calibration_source_tree["file_count"]
    ):
        raise FormalFreezeError(
            "Selected calibration source-tree identity differs from the "
            "threshold-selection report."
        )

    source_config = _resolve_selected_reference(
        selected_config,
        selection.get("source_formal_config"),
        label="source formal config",
    )
    if sha256_file(source_config) != _require_sha256(
        selection.get("source_formal_config_sha256"),
        label="source_formal_config_sha256",
    ):
        raise FormalFreezeError("Selected source formal config SHA-256 differs.")
    (
        _,
        calibration_contract,
        calibration_config,
        source_manifest,
        source_lock_audit,
    ) = _validate_calibration_evidence(report, source_config)
    _assert_candidate_runs_reproduce_report(
        report,
        calibration_config=calibration_config,
        selection_report=selection_report,
    )
    _, winner_threshold = _validate_report_protocol(report)
    if calibration_config != _resolve_selected_reference(
        selected_config,
        selection.get("calibration_config"),
        label="calibration config",
    ) or sha256_file(calibration_config) != _require_sha256(
        selection.get("calibration_config_sha256"),
        label="calibration_config_sha256",
    ):
        raise FormalFreezeError("Selected calibration config evidence differs.")

    source_payload = _read_yaml(source_config, label="Source formal config")
    _validate_source_formal_config(
        source_payload, expected_formal_samples=expected_formal_samples
    )
    selected_manifest = manifest_path_from_config(selected_config, environ={})
    selected_roots = dataset_roots_from_config(selected_config, environ={})
    try:
        selected_rows = load_manifest(
            selected_manifest,
            dataset_roots=selected_roots,
            require_files=True,
            verify_hashes=True,
        )
        selected_lock_audit = validate_manifest_lock(
            selected_manifest,
            selected_rows,
            config_path=selected_config,
            dataset_roots=selected_roots,
        )
    except (OSError, ValueError) as exc:
        raise FormalFreezeError(
            f"Selected formal manifest/lock failed strict validation: {exc}"
        ) from exc
    if len(selected_rows) != expected_formal_samples:
        raise FormalFreezeError(
            f"Selected formal manifest has {len(selected_rows)} rows; "
            f"expected exactly {expected_formal_samples}."
        )
    if selected_manifest.read_bytes() != source_manifest.read_bytes():
        raise FormalFreezeError(
            "Selected formal manifest is not byte-equivalent to its source manifest."
        )
    _assert_lock_invariants(
        source_lock_audit,
        selected_lock_audit,
        output_config=selected_config,
        output_manifest=selected_manifest,
    )

    expected_payload, required_capabilities = _build_selected_config(
        source_payload,
        source_config=source_config,
        source_manifest=source_manifest,
        source_lock_audit=source_lock_audit,
        selection_report=selection_report,
        selection_report_sha256=selection_report_sha256,
        selection_report_payload=report,
        output_config=selected_config,
        output_manifest=selected_manifest,
        winner_threshold=winner_threshold,
    )
    selected_canonical = json.dumps(
        selected_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    expected_canonical = json.dumps(
        expected_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if selected_canonical != expected_canonical:
        raise FormalFreezeError(
            "Selected formal config differs from the deterministic freeze product."
        )
    if calibration_contract.get("source_formal_manifest_lock") != source_lock_audit:
        raise FormalFreezeError(
            "Calibration source lock differs from selected formal evidence."
        )
    _assert_selection_evidence_unchanged(
        report,
        selection_report=selection_report,
        selection_report_sha256=selection_report_sha256,
    )
    return required_capabilities


def freeze_formal_config(
    source_config: Path,
    *,
    selection_report: Path,
    output_config: Path,
    output_manifest: Path,
    expected_formal_samples: int = EXPECTED_FORMAL_SAMPLES,
) -> dict[str, Any]:
    source_config = source_config.expanduser().resolve()
    selection_report = selection_report.expanduser().resolve()
    output_config = output_config.expanduser().resolve()
    output_manifest = output_manifest.expanduser().resolve()
    if expected_formal_samples <= 0:
        raise ValueError("expected_formal_samples must be positive.")
    if not source_config.is_file():
        raise FileNotFoundError(f"Source formal config is missing: {source_config}")
    if not selection_report.is_file():
        raise FileNotFoundError(
            f"Threshold-selection report is missing: {selection_report}"
        )
    source_manifest_candidate = manifest_path_from_config(source_config, environ={})
    source_lock_candidate = manifest_lock_path(source_manifest_candidate)
    protected_inputs = {
        source_config,
        selection_report,
        source_manifest_candidate,
        source_lock_candidate,
    }
    output_lock_candidate = manifest_lock_path(output_manifest)
    if (
        output_config in protected_inputs
        or output_manifest in protected_inputs
        or output_lock_candidate in protected_inputs
    ):
        raise FormalFreezeError(
            "Selected outputs must not overwrite calibration/source evidence."
        )
    _assert_fresh_outputs(output_config, output_manifest)

    selection_report_sha256 = sha256_file(selection_report)
    report = _read_json(selection_report, label="Threshold-selection report")
    calibration_source_tree = _calibration_source_tree_identity(report)
    if sha256_file(selection_report) != selection_report_sha256:
        raise FormalFreezeError("Selection report changed while it was read.")
    (
        _,
        calibration_contract,
        calibration_config,
        source_manifest,
        source_lock_audit,
    ) = _validate_calibration_evidence(report, source_config)
    _assert_candidate_runs_reproduce_report(
        report,
        calibration_config=calibration_config,
        selection_report=selection_report,
    )
    if sha256_file(selection_report) != selection_report_sha256:
        raise FormalFreezeError("Selection report changed during full reanalysis.")
    _, winner_threshold = _validate_report_protocol(report)
    source_payload = _read_yaml(source_config, label="Source formal config")
    _validate_source_formal_config(
        source_payload, expected_formal_samples=expected_formal_samples
    )

    source_roots = dataset_roots_from_config(source_config, environ={})
    source_rows = load_manifest(
        source_manifest,
        dataset_roots=source_roots,
        require_files=True,
        verify_hashes=True,
    )
    if len(source_rows) != expected_formal_samples:
        raise FormalFreezeError(
            f"Source formal manifest has {len(source_rows)} rows; "
            f"expected exactly {expected_formal_samples}."
        )
    if source_lock_audit.get("total_samples") != expected_formal_samples:
        raise FormalFreezeError("Source formal lock sample count is not exact.")

    selected_payload, required_capabilities = _build_selected_config(
        source_payload,
        source_config=source_config,
        source_manifest=source_manifest,
        source_lock_audit=source_lock_audit,
        selection_report=selection_report,
        selection_report_sha256=selection_report_sha256,
        selection_report_payload=report,
        output_config=output_config,
        output_manifest=output_manifest,
        winner_threshold=winner_threshold,
    )
    selected_text = yaml.safe_dump(
        selected_payload, allow_unicode=True, sort_keys=False
    )

    output_config.parent.mkdir(parents=True, exist_ok=True)
    preparation_config = output_config.with_name(
        f".{output_config.name}.{os.getpid()}.prepare"
    )
    if preparation_config.exists():
        raise FileExistsError(
            f"Temporary selected config already exists: {preparation_config}"
        )
    created_outputs: list[Path] = []
    try:
        _atomic_write_text(preparation_config, selected_text)
        rebuilt_rows, rebuilt_report = build_manifest_from_config(
            preparation_config,
            allow_missing_sources=False,
            environ={},
        )
        if len(rebuilt_rows) != expected_formal_samples:
            raise FormalFreezeError(
                f"Rebuilt formal manifest has {len(rebuilt_rows)} rows; "
                f"expected exactly {expected_formal_samples}."
            )
        rebuilt_bytes = manifest_text(rebuilt_rows).encode("utf-8")
        source_bytes = source_manifest.read_bytes()
        if rebuilt_bytes != source_bytes:
            raise FormalFreezeError(
                "Rebuilt selected formal manifest is not byte-equivalent to the "
                "calibration source manifest."
            )
        if manifest_assignment_sha256(rebuilt_rows) != source_lock_audit.get(
            "assignment_sha256"
        ):
            raise FormalFreezeError(
                "Rebuilt selected manifest assignment differs from the source lock."
            )
        rebuilt_upstream = rebuilt_report.get("upstream_dataset_locks") or {}
        source_upstream = source_lock_audit.get("upstream_dataset_locks") or {}
        if rebuilt_upstream != source_upstream:
            raise FormalFreezeError(
                "Upstream dataset locks changed between calibration and formal freeze."
            )
        if sha256_file(source_config) != report["formal_inputs"]["config_sha256"]:
            raise FormalFreezeError("Source config changed during formal freeze.")
        if sha256_file(source_manifest) != report["formal_inputs"]["manifest_sha256"]:
            raise FormalFreezeError("Source manifest changed during formal freeze.")
        source_lock_path = Path(str(source_lock_audit["lock_path"])).resolve()
        if sha256_file(source_lock_path) != source_lock_audit["lock_sha256"]:
            raise FormalFreezeError(
                "Source manifest lock changed during formal freeze."
            )
        if calibration_contract.get("source_formal_manifest_lock") != source_lock_audit:
            raise FormalFreezeError(
                "Calibration contract source lock changed during formal freeze."
            )
        _assert_selection_evidence_unchanged(
            report,
            selection_report=selection_report,
            selection_report_sha256=selection_report_sha256,
        )

        _assert_fresh_outputs(output_config, output_manifest)
        os.replace(preparation_config, output_config)
        created_outputs.append(output_config)
        created_outputs.extend([output_manifest, manifest_lock_path(output_manifest)])
        write_manifest(
            rebuilt_rows,
            output_manifest,
            environ={},
            config_path=output_config,
            upstream_dataset_locks=rebuilt_upstream,
        )
        selected_roots = dataset_roots_from_config(output_config, environ={})
        selected_rows = load_manifest(
            output_manifest,
            dataset_roots=selected_roots,
            require_files=True,
            verify_hashes=True,
        )
        selected_lock_audit = validate_manifest_lock(
            output_manifest,
            selected_rows,
            config_path=output_config,
            dataset_roots=selected_roots,
        )
        if output_manifest.read_bytes() != source_bytes:
            raise FormalFreezeError(
                "Published selected manifest bytes differ from the source manifest."
            )
        _assert_lock_invariants(
            source_lock_audit,
            selected_lock_audit,
            output_config=output_config,
            output_manifest=output_manifest,
        )
    except Exception:
        preparation_config.unlink(missing_ok=True)
        for path in reversed(created_outputs):
            path.unlink(missing_ok=True)
        raise
    finally:
        preparation_config.unlink(missing_ok=True)

    return {
        "status": "created",
        "schema_version": FORMAL_SELECTION_SCHEMA_VERSION,
        "source_config": str(source_config),
        "source_config_sha256": sha256_file(source_config),
        "selection_report": str(selection_report),
        "selection_report_sha256": selection_report_sha256,
        "selected_config": str(output_config),
        "selected_config_sha256": sha256_file(output_config),
        "selected_manifest": str(output_manifest),
        "selected_manifest_sha256": sha256_file(output_manifest),
        "selected_manifest_lock": str(manifest_lock_path(output_manifest)),
        "selected_manifest_lock_sha256": sha256_file(
            manifest_lock_path(output_manifest)
        ),
        "samples": expected_formal_samples,
        "test_samples": int(source_lock_audit["split_counts"].get("test", 0)),
        "assignment_sha256": source_lock_audit["assignment_sha256"],
        "winner_candidate_id": report["winner"]["candidate_id"],
        "required_capabilities": required_capabilities,
        "calibration_source_tree_identity_version": calibration_source_tree[
            "identity_version"
        ],
        "calibration_source_tree_scope": calibration_source_tree["scope"],
        "calibration_source_tree_sha256": calibration_source_tree["sha256"],
        "calibration_source_tree_file_count": calibration_source_tree["file_count"],
        "generic_input_overrides_ignored": True,
    }


def main() -> int:
    args = parse_args()
    result = freeze_formal_config(
        args.source_config,
        selection_report=args.selection_report,
        output_config=args.output_config,
        output_manifest=args.output_manifest,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
