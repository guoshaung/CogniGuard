#!/usr/bin/env python3
"""Fail-closed analyzer for v3 spatial-filter calibration and confirmation."""

from __future__ import annotations

import argparse
import json
import math
import os
import stat
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from protection.supporting.image_watermark.experiments.attacks import expand_attack_specs
from protection.supporting.image_watermark.experiments.localization_artifacts import (
    LOCALIZATION_ARTIFACT_EVIDENCE_SCHEMA_VERSION_V2,
    LocalizationArtifactError,
    canonical_sha256,
    validate_verify_localization_artifacts,
)
from protection.supporting.image_watermark.experiments.manifest import (
    dataset_roots_from_config,
    load_manifest,
    manifest_lock_path,
    manifest_path_from_config,
    validate_manifest_lock,
)
from protection.supporting.image_watermark.experiments.paper_benchmark import validate_required_capabilities
from scripts.server.image_watermark_preregistration import (
    RUN_COPY_FILENAME,
    validate_preregistration_claim,
)
from scripts.server.image_watermark_spatial_filter_attack_evidence import (
    SpatialFilterAttackEvidenceError,
    validate_spatial_filter_attack_evidence,
)
from scripts.server.image_watermark_redevelopment_protocol import (
    ATTACK_CONDITIONS,
    CALIBRATION_CONTRACT_KEY,
    CALIBRATION_DATASET_QUOTAS,
    CALIBRATION_RUN_CLASS,
    CALIBRATION_SCHEMA_VERSION,
    CONFIRMATION_CONTRACT_KEY,
    CONFIRMATION_DATASET_QUOTAS,
    CONFIRMATION_RUN_CLASS,
    CONFIRMATION_SCHEMA_VERSION,
    CONSTRAINTS,
    EVALUATION_SEEDS,
    FORMAL_TEST_ROWS_CONSUMED,
    FROZEN_FIXED_CAPABILITIES,
    PROTOCOL_ID,
    REQUIRED_ATTACK_RUNTIME,
    SELECTION_SPLIT,
    SPATIAL_FILTER_CANDIDATES,
    STATISTICAL_UNITS,
    candidate_id,
    candidate_runs,
    load_locked_assignment,
    required_capabilities,
    sha256_file,
)


CALIBRATION_REPORT_SCHEMA_VERSION = (
    "cogniguard_image_spatial_filter_selection_report_v3"
)
CONFIRMATION_REPORT_SCHEMA_VERSION = (
    "cogniguard_image_spatial_filter_confirmation_report_v3"
)
EXPECTED_EVIDENCE_ROW_FIELDS = (
    "localization_artifact_evidence",
    "localization_artifact_evidence_sha256",
    "raw_localization_votes_sha256",
    "predicted_mask_sha256",
    "localization_replay_identity_sha256",
)


class SpatialFilterAnalysisError(RuntimeError):
    """Raised when v3 evidence is incomplete, mutable, or contradictory."""


def _link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def _require_real_directory(path: Path, *, label: str) -> Path:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise SpatialFilterAnalysisError(f"{label} is unavailable: {path}") from exc
    if _link_like(path) or not stat.S_ISDIR(metadata.st_mode):
        raise SpatialFilterAnalysisError(
            f"{label} must be a real, non-symlink directory: {path}"
        )
    return path.resolve(strict=True)


def _require_real_file(path: Path, *, label: str) -> Path:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise SpatialFilterAnalysisError(f"{label} is unavailable: {path}") from exc
    if _link_like(path) or not stat.S_ISREG(metadata.st_mode):
        raise SpatialFilterAnalysisError(
            f"{label} must be a regular, non-symlink file: {path}"
        )
    return path.resolve(strict=True)


def _file_matches_sha256(path: Path, expected: object) -> bool:
    return (
        isinstance(expected, str)
        and len(expected) == 64
        and path.is_file()
        and sha256_file(path) == expected
    )


def _require_no_link_components(path: Path, root: Path, *, label: str) -> Path:
    lexical = Path(os.path.abspath(os.fspath(path.expanduser())))
    try:
        relative = lexical.relative_to(root)
    except ValueError as exc:
        raise SpatialFilterAnalysisError(f"{label} escapes v3 run root: {path}") from exc
    current = root
    for component in relative.parts:
        current = current / component
        try:
            current.lstat()
        except OSError as exc:
            raise SpatialFilterAnalysisError(
                f"{label} component is unavailable: {current}"
            ) from exc
        if _link_like(current):
            raise SpatialFilterAnalysisError(
                f"{label} traverses a symlink or junction: {current}"
            )
    return lexical


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze one complete v3 bundle.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpatialFilterAnalysisError(f"Invalid JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise SpatialFilterAnalysisError(f"JSON artifact is not an object: {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise TypeError(f"row {line_number} is not an object")
                rows.append(row)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise SpatialFilterAnalysisError(f"Invalid JSONL artifact: {path}") from exc
    return rows


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _close(a: object, b: float) -> bool:
    return (
        type(a) is float
        and math.isfinite(a)
        and math.isclose(a, b, rel_tol=0.0, abs_tol=1e-12)
    )


def _percentile(values: list[float], value: float) -> float:
    if not values:
        raise SpatialFilterAnalysisError("Cannot aggregate an empty metric group.")
    return float(np.percentile(np.asarray(values, dtype=np.float64), value))


def _metric_summary(by_attack: Mapping[str, list[float]]) -> dict[str, Any]:
    clean = list(by_attack.get("clean") or [])
    summary: dict[str, Any] = {
        "clean": {
            "n": len(clean),
            "mean_mask_fpr": float(np.mean(clean)),
            "p99_mask_fpr": _percentile(clean, 99),
            "max_mask_fpr": float(np.max(clean)),
        },
        "erasing": {},
    }
    for ratio in (0.05, 0.15, 0.25):
        attack_id = f"erasing__area_ratio-{ratio:.2f}"
        values = list(by_attack.get(attack_id) or [])
        summary["erasing"][f"{ratio:.2f}"] = {
            "n": len(values),
            "mean_mask_iou": float(np.mean(values)),
            "p10_mask_iou": _percentile(values, 10),
            "mask_iou_at_least_0_75_rate": float(
                np.mean(np.asarray(values, dtype=np.float64) >= 0.75)
            ),
        }
    return summary


def _constraint_results(summary: Mapping[str, Any]) -> dict[str, bool]:
    clean = summary["clean"]
    results = {
        "clean_mean_mask_fpr": clean["mean_mask_fpr"]
        <= CONSTRAINTS["clean_mean_mask_fpr_max"],
        "clean_p99_mask_fpr": clean["p99_mask_fpr"]
        <= CONSTRAINTS["clean_p99_mask_fpr_max"],
        "clean_max_mask_fpr": clean["max_mask_fpr"]
        <= CONSTRAINTS["clean_max_mask_fpr_max"],
    }
    for ratio, metrics in summary["erasing"].items():
        results[f"erasing_{ratio}_mean_mask_iou"] = (
            metrics["mean_mask_iou"]
            >= CONSTRAINTS["each_erasing_mean_mask_iou_min"]
        )
        results[f"erasing_{ratio}_p10_mask_iou"] = (
            metrics["p10_mask_iou"]
            >= CONSTRAINTS["each_erasing_p10_mask_iou_min"]
        )
        results[f"erasing_{ratio}_iou_at_least_0_75_rate"] = (
            metrics["mask_iou_at_least_0_75_rate"]
            >= CONSTRAINTS["each_erasing_iou_at_least_0_75_rate_min"]
        )
    return results


def _environment_identity(environment: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "python",
        "platform",
        "gpu",
        "packages",
        "checkpoints",
        "deterministic_runtime_identity",
        "asset_manifest_identity",
        "aigc_attack_runtime_identity",
        "traditional_attack_runtime",
        "registry_secret_identity_fingerprint",
        "source_tree_identity_version",
        "source_tree_file_count",
        "source_tree_scope",
        "source_tree_sha256",
        "config_sha256",
        "manifest_sha256",
    )
    identity = {field: environment.get(field) for field in fields}
    if any(value is None for value in identity.values()):
        missing = [field for field, value in identity.items() if value is None]
        raise SpatialFilterAnalysisError(
            "Candidate environment identity is incomplete: " + ", ".join(missing)
        )
    return identity


def _bound_file(
    contract: Mapping[str, Any],
    *,
    path_field: str,
    sha_field: str,
    label: str,
) -> Path:
    value = contract.get(path_field)
    if not isinstance(value, str) or not value:
        raise SpatialFilterAnalysisError(f"{label} path is missing.")
    path = Path(value).expanduser().resolve()
    if not path.is_file() or sha256_file(path) != contract.get(sha_field):
        raise SpatialFilterAnalysisError(f"{label} differs from its frozen SHA-256.")
    return path


def _validate_attack_config(config: Mapping[str, Any]) -> None:
    attacks = config.get("attacks") or {}
    traditional = attacks.get("traditional") if isinstance(attacks, Mapping) else None
    aigc = attacks.get("aigc") if isinstance(attacks, Mapping) else None
    if not isinstance(traditional, list) or aigc != {"enabled": False, "specs": []}:
        raise SpatialFilterAnalysisError("v3 attack configuration is not exact.")
    try:
        expanded = expand_attack_specs(traditional)
    except (TypeError, ValueError) as exc:
        raise SpatialFilterAnalysisError("v3 traditional attacks are malformed.") from exc
    observed = []
    for spec in expanded:
        attack_id = str(spec.params.get("expanded_name") or spec.name)
        params = {key: value for key, value in spec.params.items() if key != "expanded_name"}
        observed.append((attack_id, spec.name, spec.family, params, spec.requires_aigc))
    expected = [
        ("clean", "clean", "clean", {}, False),
        *[
            (
                f"erasing__area_ratio-{ratio:.2f}",
                "erasing",
                "removal",
                {"area_ratio": ratio},
                False,
            )
            for ratio in (0.05, 0.15, 0.25)
        ],
    ]
    if observed != expected:
        raise SpatialFilterAnalysisError(
            f"v3 expanded attacks differ from the frozen four conditions: {observed!r}."
        )


def _validate_common_frozen_contract(
    config_path: Path,
    run_root: Path,
    config: Mapping[str, Any],
    contract: Mapping[str, Any],
    *,
    run_class: str,
    role: str,
    expected_samples: int,
) -> None:
    experiment = config.get("experiment") or {}
    expected_rows = expected_samples * len(EVALUATION_SEEDS) * len(ATTACK_CONDITIONS)
    if (
        not isinstance(experiment, Mapping)
        or config_path.parent != run_root
        or experiment.get("strict_paper_mode") is not True
        or experiment.get("fail_fast") is not True
        or experiment.get("run_class") != run_class
        or experiment.get("paper_eligible") is not False
        or experiment.get("development_only") is not True
        or experiment.get("split") != SELECTION_SPLIT
        or experiment.get("seeds") != list(EVALUATION_SEEDS)
        or experiment.get("max_samples") != expected_samples
        or experiment.get("traditional_attack_artifact_retention") != "hash_only"
        or experiment.get("required_attack_runtime") != REQUIRED_ATTACK_RUNTIME
        or contract.get("protocol_id") != PROTOCOL_ID
        or contract.get("development_only") is not True
        or contract.get("paper_eligible") is not False
        or contract.get("selection_split") != SELECTION_SPLIT
        or contract.get("selection_role") != role
        or contract.get("evaluation_seeds") != list(EVALUATION_SEEDS)
        or contract.get("attack_conditions") != list(ATTACK_CONDITIONS)
        or contract.get("constraints") != CONSTRAINTS
        or contract.get("statistical_units") != STATISTICAL_UNITS
        or contract.get("formal_test_rows_consumed")
        != FORMAL_TEST_ROWS_CONSUMED
        or contract.get("formal_config_mutation_allowed") is not False
        or contract.get("formal_config_update_performed") is not False
        or contract.get("traditional_attack_artifact_retention") != "hash_only"
        or contract.get("required_attack_runtime") != REQUIRED_ATTACK_RUNTIME
    ):
        raise SpatialFilterAnalysisError("v3 frozen protocol contract is incomplete.")
    expected_rows_field = (
        "expected_rows_per_candidate"
        if run_class == CALIBRATION_RUN_CLASS
        else "expected_rows"
    )
    if contract.get(expected_rows_field) != expected_rows:
        raise SpatialFilterAnalysisError("v3 expected row count is not frozen.")
    _validate_attack_config(config)
    formal_config = _bound_file(
        contract,
        path_field="source_formal_config",
        sha_field="source_formal_config_sha256",
        label="Source formal config",
    )
    formal_manifest = _bound_file(
        contract,
        path_field="source_formal_manifest",
        sha_field="source_formal_manifest_sha256",
        label="Source formal manifest",
    )
    formal_lock = contract.get("source_formal_manifest_lock")
    if (
        not isinstance(formal_lock, Mapping)
        or formal_lock.get("manifest_sha256") != sha256_file(formal_manifest)
        or formal_lock.get("config_sha256") != sha256_file(formal_config)
        or not _file_matches_sha256(
            manifest_lock_path(formal_manifest), formal_lock.get("lock_sha256")
        )
    ):
        raise SpatialFilterAnalysisError("Source formal manifest lock binding changed.")
    implementation = contract.get("traditional_attack_implementation")
    if not isinstance(implementation, Mapping):
        raise SpatialFilterAnalysisError("Traditional attack implementation is unbound.")
    implementation_path = Path(str(implementation.get("path") or "")).resolve()
    if (
        not implementation_path.is_file()
        or sha256_file(implementation_path) != implementation.get("sha256")
    ):
        raise SpatialFilterAnalysisError("Traditional attack implementation changed.")

    methods = [
        row
        for row in (config.get("methods") or [])
        if isinstance(row, Mapping) and row.get("enabled", True)
    ]
    if (
        len(methods) != 1
        or methods[0].get("id") != "editguard_wrapper"
        or methods[0].get("kind", "sce_locguard_api") != "sce_locguard_api"
    ):
        raise SpatialFilterAnalysisError("v3 requires one editguard_wrapper method.")

    quotas = (
        CALIBRATION_DATASET_QUOTAS
        if run_class == CALIBRATION_RUN_CLASS
        else CONFIRMATION_DATASET_QUOTAS
    )
    if contract.get("selected_dataset_counts") != quotas:
        raise SpatialFilterAnalysisError("v3 source quotas differ from the frozen split.")
    if run_class == CALIBRATION_RUN_CLASS:
        expected_root = run_root / "candidate-runs"
        if (
            Path(str(experiment.get("output_root") or "")).resolve()
            != expected_root.resolve()
            or contract.get("candidate_runs") != candidate_runs()
            or contract.get("candidate_area_ratios")
            != list(SPATIAL_FILTER_CANDIDATES)
            or contract.get("fixed_capabilities") != FROZEN_FIXED_CAPABILITIES
            or methods[0].get("required_capabilities")
            != FROZEN_FIXED_CAPABILITIES
        ):
            raise SpatialFilterAnalysisError("Calibration candidate grid/root changed.")
    else:
        selected = contract.get("selected_candidate")
        selected_required = contract.get("selected_required_capabilities")
        if not isinstance(selected, Mapping) or not isinstance(
            selected_required, Mapping
        ):
            raise SpatialFilterAnalysisError("Confirmation selected candidate is missing.")
        ratio = selected.get("localization_min_component_area_ratio")
        expected_required = required_capabilities(ratio)
        expected_run_relative = f"confirmation-run/{candidate_id(ratio)}"
        expected_root = run_root / expected_run_relative
        if (
            contract.get("candidate_count") != 1
            or selected.get("candidate_id") != candidate_id(ratio)
            or selected.get("run_relative_path") != expected_run_relative
            or selected.get("required_capabilities") != expected_required
            or dict(selected_required) != expected_required
            or methods[0].get("required_capabilities") != expected_required
            or Path(str(experiment.get("output_root") or "")).resolve()
            != expected_root.resolve()
            or contract.get("parameter_search_allowed") is not False
            or contract.get("fallback_candidate_allowed") is not False
            or contract.get("fallback_on_confirmation_failure_allowed") is not False
            or contract.get("decision_output")
            != "pass_or_fail_only_no_parameter_selection"
        ):
            raise SpatialFilterAnalysisError(
                "Confirmation sole-candidate/no-fallback contract changed."
            )


def _validate_config_and_manifest(
    config_path: Path,
    *,
    run_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[Any], str]:
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise SpatialFilterAnalysisError("Invalid v3 YAML.") from exc
    if not isinstance(config, dict):
        raise SpatialFilterAnalysisError("v3 YAML root is not a mapping.")
    experiment = config.get("experiment") or {}
    run_class = str(experiment.get("run_class") or "")
    if run_class == CALIBRATION_RUN_CLASS:
        key = CALIBRATION_CONTRACT_KEY
        schema = CALIBRATION_SCHEMA_VERSION
        role = "calibration"
        expected_samples = 300
    elif run_class == CONFIRMATION_RUN_CLASS:
        key = CONFIRMATION_CONTRACT_KEY
        schema = CONFIRMATION_SCHEMA_VERSION
        role = "confirmation"
        expected_samples = 600
    else:
        raise SpatialFilterAnalysisError(f"Unsupported v3 run class: {run_class!r}")
    contract = config.get(key) or {}
    if (
        not isinstance(contract, dict)
        or contract.get("schema_version") != schema
        or contract.get("run_class") != run_class
        or contract.get("selection_role") != role
        or contract.get("expected_samples") != expected_samples
        or contract.get("formal_test_rows_consumed") != 0
    ):
        raise SpatialFilterAnalysisError("v3 config contract markers are invalid.")
    _validate_common_frozen_contract(
        config_path,
        run_root,
        config,
        contract,
        run_class=run_class,
        role=role,
        expected_samples=expected_samples,
    )
    manifest_path = manifest_path_from_config(config_path, environ={})
    if manifest_path.parent != run_root:
        raise SpatialFilterAnalysisError("v3 selected manifest escapes its run root.")
    roots = dataset_roots_from_config(config_path, environ={})
    samples = load_manifest(
        manifest_path,
        dataset_roots=roots,
        require_files=True,
        verify_hashes=True,
    )
    validate_manifest_lock(
        manifest_path,
        samples,
        config_path=config_path,
        dataset_roots=roots,
    )
    selected = [row for row in samples if row.split == "dev"]
    if len(samples) != expected_samples or len(selected) != expected_samples:
        raise SpatialFilterAnalysisError("v3 manifest sample count/split is invalid.")
    if sha256_file(manifest_path) != contract.get("selected_manifest_sha256"):
        raise SpatialFilterAnalysisError("v3 manifest differs from its frozen hash.")
    if (
        Counter(row.source_dataset for row in selected)
        != Counter(contract.get("selected_dataset_counts") or {})
        or sorted({row.domain for row in selected})
        != contract.get("selected_domains")
        or len({row.sha256 for row in selected}) != expected_samples
        or len({row.source_family for row in selected}) != expected_samples
    ):
        raise SpatialFilterAnalysisError(
            "v3 selected manifest quotas/domains/independence changed."
        )
    assignment_path = Path(contract["redevelopment_assignment"]).resolve()
    assignment_lock_path = Path(contract["redevelopment_assignment_lock"]).resolve()
    if (
        sha256_file(assignment_path)
        != contract.get("redevelopment_assignment_sha256")
        or sha256_file(assignment_lock_path)
        != contract.get("redevelopment_assignment_lock_sha256")
    ):
        raise SpatialFilterAnalysisError("v3 assignment files changed after build.")
    assignments, _lock = load_locked_assignment(
        assignment_path, assignment_lock_path
    )
    expected_identity = {
        (
            str(row["sample_id"]),
            str(row["source_family"]),
            str(row["sha256"]),
        )
        for row in assignments
        if row.get("redevelopment_role") == role
        and row.get("history_touched") is False
        and row.get("formal_split") == "train"
    }
    observed_identity = {
        (row.sample_id, row.source_family, row.sha256) for row in selected
    }
    if observed_identity != expected_identity:
        raise SpatialFilterAnalysisError(
            "v3 selected manifest differs from its untouched assignment role."
        )
    return config, contract, selected, run_class


def _validate_confirmation_lineage(
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    calibration_config = _bound_file(
        contract,
        path_field="source_calibration_config",
        sha_field="source_calibration_config_sha256",
        label="Source calibration config",
    )
    calibration_manifest = _bound_file(
        contract,
        path_field="source_calibration_manifest",
        sha_field="source_calibration_manifest_sha256",
        label="Source calibration manifest",
    )
    calibration_lock = _bound_file(
        contract,
        path_field="source_calibration_manifest_lock_path",
        sha_field="source_calibration_manifest_lock_sha256",
        label="Source calibration manifest lock",
    )
    calibration_report_path = _bound_file(
        contract,
        path_field="source_calibration_report",
        sha_field="source_calibration_report_sha256",
        label="Source calibration report",
    )
    calibration_run_root = _require_real_directory(
        Path(str(contract.get("source_calibration_run_root") or "")),
        label="Source calibration run root",
    )
    if (
        calibration_manifest != manifest_path_from_config(
            calibration_config, environ={}
        )
        or calibration_lock != manifest_lock_path(calibration_manifest)
        or calibration_config.parent != calibration_run_root
    ):
        raise SpatialFilterAnalysisError(
            "Confirmation calibration path lineage is inconsistent."
        )
    saved = _read_json(calibration_report_path)
    declared_payload_sha = saved.get("report_payload_sha256")
    payload_without_sha = dict(saved)
    payload_without_sha.pop("report_payload_sha256", None)
    if (
        saved.get("schema_version") != CALIBRATION_REPORT_SCHEMA_VERSION
        or saved.get("status") != "winner_selected"
        or saved.get("calibration_passed") is not True
        or saved.get("confirmation_performed") is not False
        or saved.get("formal_test_rows_consumed") != 0
        or declared_payload_sha != canonical_sha256(payload_without_sha)
        or declared_payload_sha
        != contract.get("source_calibration_report_payload_sha256")
        or saved.get("config_sha256") != sha256_file(calibration_config)
        or Path(str(saved.get("run_root") or "")).resolve()
        != calibration_run_root
    ):
        raise SpatialFilterAnalysisError(
            "Confirmation source calibration report is unauthenticated."
        )
    try:
        calibration_config_payload = yaml.safe_load(
            calibration_config.read_text(encoding="utf-8")
        ) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise SpatialFilterAnalysisError(
            "Confirmation source calibration config is invalid."
        ) from exc
    calibration_contract = (
        calibration_config_payload.get(CALIBRATION_CONTRACT_KEY)
        if isinstance(calibration_config_payload, Mapping)
        else None
    )
    if (
        not isinstance(calibration_contract, Mapping)
        or canonical_sha256(dict(calibration_contract))
        != contract.get("source_calibration_contract_sha256")
    ):
        raise SpatialFilterAnalysisError(
            "Confirmation source calibration contract changed."
        )
    reproduced = analyze_bundle(
        calibration_config,
        run_root=calibration_run_root,
    )
    if reproduced != saved:
        raise SpatialFilterAnalysisError(
            "Confirmation source calibration differs from full independent replay."
        )
    winner = saved.get("selected_candidate")
    confirmation_selected = contract.get("selected_candidate")
    if not isinstance(winner, Mapping) or not isinstance(
        confirmation_selected, Mapping
    ):
        raise SpatialFilterAnalysisError("Confirmation winner lineage is missing.")
    ratio = winner.get("localization_min_component_area_ratio")
    expected_winner = {
        "candidate_id": candidate_id(ratio),
        "localization_min_component_area_ratio": ratio,
        "required_capabilities": required_capabilities(ratio),
    }
    expected_confirmation = {
        **expected_winner,
        "run_relative_path": f"confirmation-run/{candidate_id(ratio)}",
    }
    if (
        dict(winner) != expected_winner
        or dict(confirmation_selected) != expected_confirmation
        or contract.get("selected_required_capabilities")
        != expected_winner["required_capabilities"]
        or contract.get("source_calibration_selected_candidate")
        != expected_winner
        or contract.get("source_calibration_schema_version")
        != CALIBRATION_REPORT_SCHEMA_VERSION
        or contract.get("source_calibration_status") != "winner_selected"
        or contract.get("source_calibration_passed") is not True
        or contract.get("source_calibration_environment_identity_sha256")
        != saved.get("immutable_environment_identity_sha256")
        or contract.get("source_calibration_source_tree_sha256")
        != saved.get("source_tree_sha256")
    ):
        raise SpatialFilterAnalysisError(
            "Confirmation candidate is not the authenticated calibration winner."
        )
    return {
        "calibration_report": str(calibration_report_path),
        "calibration_report_sha256": sha256_file(calibration_report_path),
        "calibration_report_payload_sha256": declared_payload_sha,
        "calibration_source_tree_sha256": saved["source_tree_sha256"],
        "calibration_winner": expected_winner,
    }


def _validate_candidate(
    *,
    config_path: Path,
    candidate_root: Path,
    selected: list[Any],
    run_class: str,
    area_ratio: float,
) -> dict[str, Any]:
    candidate_root = _require_no_link_components(
        candidate_root,
        config_path.parent,
        label="Candidate root",
    )
    candidate_root = _require_real_directory(candidate_root, label="Candidate root")
    benchmark_root = _require_real_directory(
        candidate_root / "benchmark", label="Candidate benchmark root"
    )
    raw_path = benchmark_root / "raw_results.jsonl"
    summary_path = benchmark_root / "summary.json"
    environment_path = benchmark_root / "environment.json"
    capabilities_path = candidate_root / "capabilities.json"
    for path, label in (
        (raw_path, "Candidate raw results"),
        (summary_path, "Candidate summary"),
        (environment_path, "Candidate environment"),
        (capabilities_path, "Candidate capabilities"),
    ):
        _require_real_file(path, label=label)
    run_class_path = _require_real_file(
        candidate_root / "run-class.txt", label="Candidate run-class marker"
    )
    try:
        observed_run_class = run_class_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise SpatialFilterAnalysisError("Candidate run-class marker is unreadable.") from exc
    if observed_run_class != run_class:
        raise SpatialFilterAnalysisError("Candidate run-class marker differs.")
    preflight = _read_json(
        _require_real_file(
            candidate_root / "preflight.json", label="Candidate preflight report"
        )
    )
    preflight_summary = preflight.get("summary") or {}
    preflight_contract = preflight.get("deployment_contract") or {}
    if (
        preflight.get("schema_version") != 1
        or preflight.get("status") not in {"ready", "ready_with_warnings"}
        or not isinstance(preflight_summary, Mapping)
        or preflight_summary.get("errors") != []
        or not isinstance(preflight_contract, Mapping)
        or Path(str(preflight_contract.get("output_root") or "")).resolve()
        != (candidate_root / "api_jobs").resolve()
        or preflight_contract.get("uvicorn_workers") != 1
        or preflight_contract.get("secret_value_recorded") is not False
    ):
        raise SpatialFilterAnalysisError("Candidate preflight attestation is invalid.")
    required = required_capabilities(area_ratio)
    capabilities = _read_json(capabilities_path)
    validate_required_capabilities(
        {"id": "editguard_wrapper", "required_capabilities": required},
        capabilities,
        require_declaration=True,
    )
    source_claim = validate_preregistration_claim(
        config_path,
        claim_path=Path(
            (yaml.safe_load(config_path.read_text(encoding="utf-8")) or {})[
                CALIBRATION_CONTRACT_KEY
                if run_class == CALIBRATION_RUN_CLASS
                else CONFIRMATION_CONTRACT_KEY
            ]["preregistration_claim"]["claim_path"]
        ),
        expected_run_class=run_class,
        expected_candidate_run=candidate_root,
    )
    run_claim = validate_preregistration_claim(
        config_path,
        claim_path=candidate_root / RUN_COPY_FILENAME,
        expected_run_class=run_class,
        expected_nonce=source_claim["nonce"],
        expected_candidate_run=candidate_root,
    )
    if source_claim["source_claim_sha256"] != run_claim["source_claim_sha256"]:
        raise SpatialFilterAnalysisError("Candidate preregistration copies differ.")

    rows = _read_jsonl(raw_path)
    expected_rows = len(selected) * len(EVALUATION_SEEDS) * len(ATTACK_CONDITIONS)
    if len(rows) != expected_rows:
        raise SpatialFilterAnalysisError(
            f"Candidate rows are incomplete: {len(rows)} != {expected_rows}."
        )
    sample_by_id = {row.sample_id: row for row in selected}
    attack_validation = validate_spatial_filter_attack_evidence(
        rows,
        benchmark_root=benchmark_root.resolve(),
        sample_by_id=sample_by_id,
        expected_seeds=EVALUATION_SEEDS,
        expected_attack_ids=ATTACK_CONDITIONS,
    )
    expected_keys = {
        (sample.sample_id, seed, attack_id)
        for sample in selected
        for seed in EVALUATION_SEEDS
        for attack_id in ATTACK_CONDITIONS
    }
    observed_keys: set[tuple[str, int, str]] = set()
    row_metrics: dict[str, list[float]] = defaultdict(list)
    cluster_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    evidence_rows = 0
    for row in rows:
        sample_id = str(row.get("sample_id") or "")
        attack_id = str(row.get("attack_id") or "")
        seed = row.get("seed")
        key = (sample_id, seed, attack_id)
        sample = sample_by_id.get(sample_id)
        if (
            type(seed) is not int
            or key in observed_keys
            or key not in expected_keys
            or sample is None
            or row.get("row_key")
            != "|".join(("editguard_wrapper", sample_id, str(seed), attack_id))
            or row.get("method_id") != "editguard_wrapper"
            or row.get("run_class") != run_class
            or row.get("paper_eligible") is not False
            or row.get("split") != "dev"
            or row.get("status") != "ok"
            or not _close(row.get("pipeline_success"), 1.0)
            or row.get("image_sha256") != sample.sha256
            or row.get("source_dataset") != sample.source_dataset
            or row.get("domain") != sample.domain
            or row.get("implementation_level") != "real_pipeline"
            or any(field not in row for field in EXPECTED_EVIDENCE_ROW_FIELDS)
        ):
            raise SpatialFilterAnalysisError(
                f"Candidate row identity/status is invalid: {row.get('row_key')!r}"
            )
        observed_keys.add(key)
        evidence = row["localization_artifact_evidence"]
        if (
            not isinstance(evidence, dict)
            or evidence.get("schema_version")
            != LOCALIZATION_ARTIFACT_EVIDENCE_SCHEMA_VERSION_V2
            or row["localization_artifact_evidence_sha256"]
            != evidence.get("canonical_evidence_sha256")
            or canonical_sha256(
                {k: v for k, v in evidence.items() if k != "canonical_evidence_sha256"}
            )
            != evidence.get("canonical_evidence_sha256")
        ):
            raise SpatialFilterAnalysisError("Row localization evidence is unauthenticated.")
        report_path = Path(str(evidence.get("verify_report_path") or "")).resolve()
        try:
            report_path.relative_to(benchmark_root.resolve())
        except ValueError as exc:
            raise SpatialFilterAnalysisError(
                "Row verify report escapes its candidate benchmark root."
            ) from exc
        report = _read_json(report_path)
        response = report.get("response")
        input_reference = report.get("input_image")
        if not isinstance(response, dict) or not isinstance(input_reference, dict):
            raise SpatialFilterAnalysisError("Verify report identity evidence is missing.")
        validation = validate_verify_localization_artifacts(
            response=response,
            artifact_run_root=benchmark_root.resolve(),
            required_capabilities=required,
            expected_input_sha256=str(row.get("attacked_image_sha256") or ""),
            expected_seed=seed,
            expected_image_shape=(sample.height, sample.width),
            expected_input_suffix=str(input_reference.get("suffix") or ""),
            expected_input_size_bytes=input_reference.get("size_bytes"),
        )
        if validation.evidence != evidence:
            raise SpatialFilterAnalysisError(
                "Row localization evidence differs from independent replay."
            )
        if (
            row["raw_localization_votes_sha256"] != evidence["raw_vote_sha256"]
            or row["predicted_mask_sha256"] != evidence["predicted_mask_sha256"]
            or row["localization_replay_identity_sha256"]
            != evidence["replay_identity_sha256"]
        ):
            raise SpatialFilterAnalysisError("Row evidence SHA bindings differ.")
        predicted = validation.predicted_mask
        if attack_id == "clean":
            if row.get("attack_truth_bbox") is not None:
                raise SpatialFilterAnalysisError("Clean row unexpectedly has attack truth.")
            value = float(predicted.mean())
            if not _close(row.get("mask_fpr"), value):
                raise SpatialFilterAnalysisError("Clean mask_fpr differs from replay.")
        else:
            bbox = attack_validation.authenticated_attack_map[key][
                "attack_truth_bbox"
            ]
            if (
                not isinstance(bbox, list)
                or len(bbox) != 4
                or any(type(value) is not int for value in bbox)
            ):
                raise SpatialFilterAnalysisError("Erasing row has invalid truth bbox.")
            x0, y0, x1, y1 = bbox
            if not (
                0 <= x0 < x1 <= predicted.shape[1]
                and 0 <= y0 < y1 <= predicted.shape[0]
            ):
                raise SpatialFilterAnalysisError(
                    "Erasing truth bbox escapes the attacked image."
                )
            truth = np.zeros(predicted.shape, dtype=np.bool_)
            truth[y0:y1, x0:x1] = True
            intersection = int(np.logical_and(predicted, truth).sum())
            union = int(np.logical_or(predicted, truth).sum())
            value = float(intersection / union) if union else 1.0
            if not _close(row.get("mask_iou"), value):
                raise SpatialFilterAnalysisError("Erasing mask_iou differs from replay.")
        row_metrics[attack_id].append(value)
        cluster_values[(sample_id, attack_id)].append(value)
        evidence_rows += 1
    if observed_keys != expected_keys:
        raise SpatialFilterAnalysisError("Candidate cross-product rows are incomplete.")
    cluster_metrics: dict[str, list[float]] = defaultdict(list)
    for (sample_id, attack_id), values in cluster_values.items():
        if len(values) != len(EVALUATION_SEEDS):
            raise SpatialFilterAnalysisError(
                f"Source cluster is incomplete: {sample_id}, {attack_id}."
            )
        cluster_metrics[attack_id].append(float(np.mean(values)))
    row_summary = _metric_summary(row_metrics)
    cluster_summary = _metric_summary(cluster_metrics)
    row_constraints = _constraint_results(row_summary)
    cluster_constraints = _constraint_results(cluster_summary)
    all_pass = all(row_constraints.values()) and all(cluster_constraints.values())
    environment = _read_json(environment_path)
    summary = _read_json(summary_path)
    manifest_path = manifest_path_from_config(config_path, environ={})
    environment_capabilities = environment.get("capabilities") or {}
    dynamic_capability_fields = {
        "registry_codebook_records",
        "registry_codebook_min_distance",
    }
    expected_capabilities_contract = {
        "editguard_wrapper": {
            key: value
            for key, value in sorted(capabilities.items())
            if key not in dynamic_capability_fields
        }
    }
    traditional_runtime = environment.get("traditional_attack_runtime") or {}
    environment_manifest_lock = environment.get("manifest_lock") or {}
    if (
        environment.get("strict_paper_mode") is not True
        or environment.get("run_class") != run_class
        or environment.get("paper_eligible") is not False
        or environment.get("evaluation_split") != SELECTION_SPLIT
        or environment.get("dataset_manifest_override_used") is not False
        or environment.get("dataset_roots_override_used") is not False
        or environment.get("config_sha256") != sha256_file(config_path)
        or environment.get("manifest_sha256") != sha256_file(manifest_path)
        or environment.get("preregistration_claim") != run_claim
        or environment_capabilities.get("editguard_wrapper") != capabilities
        or environment.get("capabilities_contract")
        != expected_capabilities_contract
        or environment.get("methods")
        != [{"id": "editguard_wrapper", "kind": "sce_locguard_api"}]
        or not isinstance(traditional_runtime, Mapping)
        or traditional_runtime.get("required_packages") != REQUIRED_ATTACK_RUNTIME
        or traditional_runtime.get("artifact_retention") != "hash_only"
        or not _file_matches_sha256(
            Path(str(traditional_runtime.get("implementation_path") or "")),
            traditional_runtime.get("implementation_sha256"),
        )
        or not isinstance(environment_manifest_lock, Mapping)
        or not _file_matches_sha256(
            manifest_lock_path(manifest_path),
            environment_manifest_lock.get("lock_sha256"),
        )
    ):
        raise SpatialFilterAnalysisError(
            "Candidate environment/config/capability attestation is invalid."
        )
    if (
        summary.get("expected_rows") != expected_rows
        or summary.get("observed_rows") != expected_rows
        or summary.get("run_class") != run_class
        or summary.get("paper_eligible") is not False
    ):
        raise SpatialFilterAnalysisError("Benchmark summary completeness is invalid.")
    return {
        "candidate_id": candidate_id(area_ratio),
        "localization_min_component_area_ratio": area_ratio,
        "required_capabilities": required,
        "expected_rows": expected_rows,
        "observed_rows": len(rows),
        "localization_evidence_rows": evidence_rows,
        "authenticated_attack_input_rows": len(
            attack_validation.authenticated_attack_map
        ),
        "authenticated_attack_input_identity_sha256": (
            attack_validation.canonical_identity_sha256
        ),
        "row_level_metrics": row_summary,
        "source_cluster_metrics": cluster_summary,
        "row_level_constraints": row_constraints,
        "source_cluster_constraints": cluster_constraints,
        "constraints_passed": sum(row_constraints.values())
        + sum(cluster_constraints.values()),
        "constraints_total": len(row_constraints) + len(cluster_constraints),
        "all_constraints_satisfied": all_pass,
        "environment_identity": _environment_identity(environment),
        "environment_identity_sha256": canonical_sha256(
            _environment_identity(environment)
        ),
        "raw_results_path": str(raw_path),
        "raw_results_sha256": sha256_file(raw_path),
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "capabilities_path": str(capabilities_path),
        "capabilities_sha256": sha256_file(capabilities_path),
        "preregistration_claim_sha256": source_claim["source_claim_sha256"],
    }


def analyze_bundle(config_path: Path, *, run_root: Path) -> dict[str, Any]:
    raw_config_path = Path(os.path.abspath(os.fspath(config_path.expanduser())))
    raw_run_root = Path(os.path.abspath(os.fspath(run_root.expanduser())))
    config_path = _require_real_file(raw_config_path, label="v3 config")
    run_root = _require_real_directory(raw_run_root, label="v3 run root")
    config, contract, selected, run_class = _validate_config_and_manifest(
        config_path, run_root=run_root
    )
    confirmation_lineage = (
        _validate_confirmation_lineage(contract)
        if run_class == CONFIRMATION_RUN_CLASS
        else None
    )
    if run_class == CALIBRATION_RUN_CLASS:
        candidates = [
            (
                run_root / "candidate-runs" / candidate_id(ratio),
                ratio,
            )
            for ratio in SPATIAL_FILTER_CANDIDATES
        ]
    else:
        required = contract.get("selected_required_capabilities") or {}
        ratio = required.get("localization_min_component_area_ratio")
        if type(ratio) is not float:
            raise SpatialFilterAnalysisError("Confirmation selected ratio is invalid.")
        candidates = [
            (
                Path(config["experiment"]["output_root"]).expanduser(),
                ratio,
            )
        ]
    reports = [
        _validate_candidate(
            config_path=config_path,
            candidate_root=root,
            selected=selected,
            run_class=run_class,
            area_ratio=ratio,
        )
        for root, ratio in candidates
    ]
    environment_hashes = {row["environment_identity_sha256"] for row in reports}
    if len(environment_hashes) != 1:
        raise SpatialFilterAnalysisError(
            "Candidate immutable environment/source-tree identities differ."
        )
    attack_input_hashes = {
        row["authenticated_attack_input_identity_sha256"] for row in reports
    }
    if len(attack_input_hashes) != 1:
        raise SpatialFilterAnalysisError(
            "Candidate clean/erasing inputs or truth boxes are not byte-identical."
        )
    base: dict[str, Any] = {
        "run_class": run_class,
        "development_only": True,
        "paper_eligible": False,
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "run_root": str(run_root),
        "expected_samples": len(selected),
        "formal_test_rows_consumed": 0,
        "constraints": CONSTRAINTS,
        "statistical_units": contract["statistical_units"],
        "candidate_reports": reports,
        "immutable_environment_identity_sha256": next(iter(environment_hashes)),
        "authenticated_attack_input_identity_sha256": next(
            iter(attack_input_hashes)
        ),
        "cross_candidate_attack_inputs_identical": True,
        "source_tree_sha256": reports[0]["environment_identity"][
            "source_tree_sha256"
        ],
        "source_tree_file_count": reports[0]["environment_identity"][
            "source_tree_file_count"
        ],
    }
    if confirmation_lineage is not None:
        if (
            reports[0]["environment_identity"]["source_tree_sha256"]
            != confirmation_lineage["calibration_source_tree_sha256"]
        ):
            raise SpatialFilterAnalysisError(
                "Confirmation source tree differs from authenticated calibration."
            )
        base["calibration_lineage"] = confirmation_lineage
    if run_class == CALIBRATION_RUN_CLASS:
        eligible = [row for row in reports if row["all_constraints_satisfied"]]
        eligible.sort(key=lambda row: row["localization_min_component_area_ratio"])
        winner = eligible[0] if eligible else None
        base.update(
            {
                "schema_version": CALIBRATION_REPORT_SCHEMA_VERSION,
                "status": (
                    "winner_selected"
                    if winner is not None
                    else "no_candidate_satisfies_constraints"
                ),
                "selection_rule": contract["winner_rule"],
                "selected_candidate": (
                    {
                        "candidate_id": winner["candidate_id"],
                        "localization_min_component_area_ratio": winner[
                            "localization_min_component_area_ratio"
                        ],
                        "required_capabilities": winner["required_capabilities"],
                    }
                    if winner is not None
                    else None
                ),
                "calibration_passed": winner is not None,
                "confirmation_performed": False,
            }
        )
    else:
        passed = reports[0]["all_constraints_satisfied"]
        base.update(
            {
                "schema_version": CONFIRMATION_REPORT_SCHEMA_VERSION,
                "status": "confirmation_passed" if passed else "confirmation_failed",
                "selected_candidate": {
                    "candidate_id": reports[0]["candidate_id"],
                    "localization_min_component_area_ratio": reports[0][
                        "localization_min_component_area_ratio"
                    ],
                    "required_capabilities": reports[0]["required_capabilities"],
                },
                "confirmation_passed": passed,
                "formal_execution_authorized": passed,
                "fallback_candidate_allowed": False,
            }
        )
    base["report_payload_sha256"] = canonical_sha256(base)
    return base


def main() -> int:
    args = parse_args()
    output = Path(args.output).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite v3 analysis report: {output}")
    report = analyze_bundle(Path(args.config), run_root=Path(args.run_root))
    _atomic_write_json(output, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": str(output),
                "report_sha256": sha256_file(output),
                "formal_test_rows_consumed": 0,
                "selected_candidate": report.get("selected_candidate"),
            },
            sort_keys=True,
        )
    )
    passed = bool(
        report.get("calibration_passed") or report.get("confirmation_passed")
    )
    return 0 if passed else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        LocalizationArtifactError,
        SpatialFilterAnalysisError,
        SpatialFilterAttackEvidenceError,
    ) as exc:
        raise SystemExit(f"spatial-filter analysis failed closed: {exc}") from exc
