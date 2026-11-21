#!/usr/bin/env python3
"""Strictly analyze the sole preregistered 2-of-3 dev confirmation run."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from PIL import Image

from protection.supporting.image_watermark.experiments.attacks import expand_attack_specs
from protection.supporting.image_watermark.experiments.localization_artifacts import (
    LocalizationArtifactError,
    canonical_sha256 as localization_evidence_sha256,
    validate_verify_localization_artifacts,
)
from protection.supporting.image_watermark.experiments.manifest import (
    ImageSample,
    dataset_roots_from_config,
    load_manifest,
    manifest_path_from_config,
    validate_manifest_lock,
)
from protection.supporting.image_watermark.experiments.paper_benchmark import _source_tree_identity
from scripts.server.analyze_image_watermark_threshold_calibration import (
    EXPECTED_SERVICE_IMAGE_SHAPE,
    ThresholdCalibrationError,
    _binary_metric,
    _constraint,
    _independently_validate_candidate_artifacts,
    _mean,
    _metric_summary,
    _read_json,
    _read_jsonl,
    _unit_interval,
    _validate_current_attack_runtime,
    _immutable_environment_identity,
)
from scripts.server.build_image_watermark_channel_vote_confirmation import (
    CANDIDATE_ID,
    CONFIRMATION_MINIMUM_DOMAINS,
    EXPECTED_CONFIRMATION_SAMPLES,
    EXPECTED_FORMAL_SPLIT_COUNTS,
    EXPECTED_ROWS,
    FORMAL_TEST_ROWS_CONSUMED,
    FROZEN_CHANNEL_VOTE_MIN,
    FROZEN_RECOVERY_THRESHOLD,
    FROZEN_REQUIRED_CAPABILITIES,
    RUNTIME_REQUIRED_CAPABILITY_FIELDS,
    RUN_CLASS,
    RUN_RELATIVE_PATH,
    SCHEMA_VERSION,
    SELECTION_RULE,
    SELECTION_SPLIT,
    _assignment_sha256,
    _select_confirmation_complement,
    _validate_calibration_evidence,
    _validate_formal_bundle,
    sha256_file,
)
from scripts.server.build_image_watermark_threshold_calibration import (
    ATTACK_ARTIFACT_RETENTION,
    ATTACK_CONDITIONS,
    CONSTRAINTS,
    EVALUATION_SEEDS,
    ERASING_RATIOS,
    REQUIRED_ATTACK_RUNTIME,
)
from scripts.server.image_watermark_preregistration import (
    RUN_COPY_FILENAME,
    PreregistrationError,
    validate_preregistration_claim,
    validate_preregistration_contract,
)


REPORT_SCHEMA_VERSION = "cogniguard_image_channel_vote_confirmation_report_v2"
_DYNAMIC_CAPABILITY_FIELDS = {
    "registry_codebook_records",
    "registry_codebook_min_distance",
}


class ChannelVoteConfirmationError(RuntimeError):
    """Raised when confirmation evidence violates the preregistration."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze the single preregistered 216-row channel-vote run."
    )
    parser.add_argument("--config", required=True, help="Confirmation YAML.")
    parser.add_argument(
        "--run-root",
        default=None,
        help="Bundle root containing confirmation-run/; defaults to config directory.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Fresh JSON report; defaults to RUN_ROOT/channel_vote_confirmation_report.json.",
    )
    return parser.parse_args()


def _strict_scalar_matches(observed: Any, expected: Any) -> bool:
    if isinstance(expected, bool):
        return type(observed) is bool and observed is expected
    if isinstance(expected, int):
        return type(observed) is int and observed == expected
    if isinstance(expected, float):
        return (
            type(observed) is float
            and math.isfinite(observed)
            and math.isclose(
                observed, expected, rel_tol=0.0, abs_tol=1e-12
            )
        )
    if isinstance(expected, str):
        return type(observed) is str and observed == expected
    return False


def _validated_domain_coverage(
    payload: dict[str, Any],
    contract: dict[str, Any],
    *,
    source_formal_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate declared confirmation coverage and, when available, its source floor."""

    requirements = payload.get("data_requirements") or {}
    selected_domains = contract.get("selected_domains")
    source_minimum = contract.get("source_formal_minimum_domains")
    confirmation_minimum = contract.get("confirmation_minimum_domains")
    effective_minimum = contract.get("effective_minimum_domains")
    selected_count = contract.get("selected_domain_count")
    if not isinstance(selected_domains, list) or any(
        type(domain) is not str or not domain.strip() for domain in selected_domains
    ):
        raise ChannelVoteConfirmationError(
            "Confirmation domain-coverage contract is malformed or inconsistent."
        )
    if (
        not isinstance(requirements, dict)
        or type(source_minimum) is not int
        or source_minimum < 1
        or type(confirmation_minimum) is not int
        or confirmation_minimum != CONFIRMATION_MINIMUM_DOMAINS
        or type(effective_minimum) is not int
        or effective_minimum != max(source_minimum, CONFIRMATION_MINIMUM_DOMAINS)
        or requirements.get("minimum_domains") != effective_minimum
        or type(selected_count) is not int
        or selected_domains != sorted(set(selected_domains))
        or selected_count != len(selected_domains)
        or selected_count < effective_minimum
    ):
        raise ChannelVoteConfirmationError(
            "Confirmation domain-coverage contract is malformed or inconsistent."
        )
    if source_formal_payload is not None:
        source_requirements = source_formal_payload.get("data_requirements") or {}
        if (
            not isinstance(source_requirements, dict)
            or source_requirements.get("minimum_domains") != source_minimum
        ):
            raise ChannelVoteConfirmationError(
                "Confirmation source-domain floor differs from the frozen formal config."
            )
    return {
        "source_formal_minimum_domains": source_minimum,
        "confirmation_minimum_domains": confirmation_minimum,
        "effective_minimum_domains": effective_minimum,
        "selected_domain_count": selected_count,
        "selected_domains": copy.deepcopy(selected_domains),
    }


def _validate_observed_domain_coverage(
    rows: list[ImageSample],
    contract: dict[str, Any],
) -> list[str]:
    """Replay the declared domain evidence from the locked selected manifest."""

    observed_domains = sorted({row.domain for row in rows})
    effective_minimum = contract.get("effective_minimum_domains")
    if (
        type(effective_minimum) is not int
        or observed_domains != contract.get("selected_domains")
        or len(observed_domains) != contract.get("selected_domain_count")
        or len(observed_domains) < effective_minimum
    ):
        raise ChannelVoteConfirmationError(
            "Confirmation manifest domain coverage differs from the frozen contract."
        )
    return observed_domains


def _validate_required_capabilities(
    observed: dict[str, Any],
    *,
    label: str,
    expected: dict[str, Any],
) -> None:
    if not isinstance(observed, dict):
        raise ChannelVoteConfirmationError(f"{label} capabilities are not a mapping.")
    mismatches = {
        name: {"expected": wanted, "observed": observed.get(name)}
        for name, wanted in expected.items()
        if name not in observed
        or not _strict_scalar_matches(observed.get(name), wanted)
    }
    if mismatches:
        raise ChannelVoteConfirmationError(
            f"{label} required capabilities mismatch: {mismatches}."
        )


def _validated_required_capabilities(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ChannelVoteConfirmationError(
            "Confirmation required_capabilities are not a mapping."
        )
    expected_keys = set(FROZEN_REQUIRED_CAPABILITIES).union(
        RUNTIME_REQUIRED_CAPABILITY_FIELDS
    )
    if set(raw) != expected_keys:
        raise ChannelVoteConfirmationError(
            "Confirmation required_capabilities have a missing or extra field."
        )
    for name, expected in FROZEN_REQUIRED_CAPABILITIES.items():
        if not _strict_scalar_matches(raw.get(name), expected):
            raise ChannelVoteConfirmationError(
                f"Confirmation required capability {name} differs from the protocol."
            )
    if raw.get("attack_model_id") != (
        "stable-diffusion-v1-5/stable-diffusion-inpainting"
    ):
        raise ChannelVoteConfirmationError(
            "Confirmation attack_model_id differs from the frozen model."
        )
    revision = raw.get("attack_model_revision")
    if type(revision) is not str or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ChannelVoteConfirmationError(
            "Confirmation attack_model_revision is not an exact 40-character commit."
        )
    if raw.get("deterministic_mode_enabled") is not True:
        raise ChannelVoteConfirmationError(
            "Confirmation deterministic_mode_enabled must be exactly true."
        )
    return copy.deepcopy(raw)


def _validate_frozen_parameters(
    contract: dict[str, Any],
    method: dict[str, Any],
) -> dict[str, Any]:
    candidate = contract.get("candidate")
    if not isinstance(candidate, dict):
        raise ChannelVoteConfirmationError("Confirmation candidate is malformed.")
    required_capabilities = _validated_required_capabilities(
        contract.get("required_capabilities")
    )
    expected_candidate = {
        "candidate_id": CANDIDATE_ID,
        **copy.deepcopy(required_capabilities),
        "run_relative_path": RUN_RELATIVE_PATH,
    }
    if candidate != expected_candidate:
        raise ChannelVoteConfirmationError(
            "Confirmation candidate parameters differ from the sole preregistered setting."
        )
    if method.get("required_capabilities") != required_capabilities:
        raise ChannelVoteConfirmationError(
            "Method required_capabilities differ from the frozen 0.34/2-of-3 setting."
        )
    if (
        contract.get("candidate_count") != 1
        or contract.get("parameter_search_allowed") is not False
        or contract.get("posthoc_parameter_change_allowed") is not False
        or contract.get("fallback_candidate_allowed") is not False
        or contract.get("selection_rule") != SELECTION_RULE
        or contract.get("decision_output")
        != "pass_or_fail_only_no_parameter_selection"
    ):
        raise ChannelVoteConfirmationError(
            "Confirmation YAML permits a grid, fallback, or post-hoc parameter change."
        )
    return required_capabilities


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ChannelVoteConfirmationError(f"Confirmation config is missing: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ChannelVoteConfirmationError(
            f"Confirmation config cannot be parsed: {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ChannelVoteConfirmationError(
            "Confirmation YAML root must be a mapping."
        )
    return payload


def _validate_confirmation_output_root(
    config_path: Path, experiment: dict[str, Any]
) -> Path:
    """Bind offline analysis to the sole preregistered candidate directory."""

    resolved_config = config_path.expanduser().resolve()
    expected = (resolved_config.parent / RUN_RELATIVE_PATH).resolve()
    raw_value = experiment.get("output_root")
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ChannelVoteConfirmationError(
            "Confirmation experiment.output_root must be the absolute frozen candidate path."
        )
    declared = Path(raw_value).expanduser()
    if not declared.is_absolute() or declared != expected:
        raise ChannelVoteConfirmationError(
            "Confirmation experiment.output_root differs from the sole preregistered "
            f"candidate directory: expected={expected}, observed={declared}."
        )
    return expected


def _validate_confirmation_config(
    config_path: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[ImageSample],
    list[ImageSample],
    dict[str, Any],
]:
    payload = _read_yaml_mapping(config_path)
    experiment = payload.get("experiment") or {}
    contract = payload.get("channel_vote_confirmation") or {}
    manifest = payload.get("manifest") or {}
    requirements = payload.get("data_requirements") or {}
    if (
        not isinstance(experiment, dict)
        or not isinstance(contract, dict)
        or experiment.get("run_class") != RUN_CLASS
        or experiment.get("strict_paper_mode") is not True
        or experiment.get("fail_fast") is not True
        or experiment.get("development_only") is not True
        or experiment.get("paper_eligible") is not False
        or experiment.get("split") != SELECTION_SPLIT
        or experiment.get("max_samples") != EXPECTED_CONFIRMATION_SAMPLES
        or experiment.get("seeds") != list(EVALUATION_SEEDS)
        or experiment.get("traditional_attack_artifact_retention")
        != ATTACK_ARTIFACT_RETENTION
        or experiment.get("required_attack_runtime") != REQUIRED_ATTACK_RUNTIME
        or contract.get("schema_version") != SCHEMA_VERSION
        or contract.get("run_class") != RUN_CLASS
        or contract.get("development_only") is not True
        or contract.get("paper_eligible") is not False
        or contract.get("selection_split") != SELECTION_SPLIT
        or contract.get("formal_test_rows_consumed")
        != FORMAL_TEST_ROWS_CONSUMED
        or contract.get("formal_config_mutation_allowed") is not False
        or contract.get("formal_config_update_performed") is not False
        or contract.get("preregistered_before_candidate_execution") is not True
        or contract.get("preexisting_candidate_artifacts") != 0
        or contract.get("expected_samples") != EXPECTED_CONFIRMATION_SAMPLES
        or contract.get("expected_rows") != EXPECTED_ROWS
        or contract.get("evaluation_seeds") != list(EVALUATION_SEEDS)
        or contract.get("attack_conditions") != list(ATTACK_CONDITIONS)
        or contract.get("constraints") != CONSTRAINTS
        or contract.get("traditional_attack_artifact_retention")
        != ATTACK_ARTIFACT_RETENTION
        or contract.get("required_attack_runtime") != REQUIRED_ATTACK_RUNTIME
        or not isinstance(manifest, dict)
        or manifest.get("verify_hashes") is not True
        or manifest.get("require_lock") is not True
        or not isinstance(requirements, dict)
        or requirements.get("expected_total_samples")
        != EXPECTED_CONFIRMATION_SAMPLES
        or requirements.get("minimum_selected_samples")
        != EXPECTED_CONFIRMATION_SAMPLES
    ):
        raise ChannelVoteConfirmationError(
            "YAML is not the exact frozen, development-only 216-row confirmation config."
        )
    if set(contract.get("excluded_splits") or []) != {"train", "test"}:
        raise ChannelVoteConfirmationError(
            "Confirmation does not explicitly exclude train and test."
        )
    declared_domain_coverage = _validated_domain_coverage(payload, contract)
    _validate_confirmation_output_root(config_path, experiment)
    methods = [
        row
        for row in (payload.get("methods") or [])
        if isinstance(row, dict) and row.get("enabled", True)
    ]
    if (
        len(methods) != 1
        or methods[0].get("id") != "editguard_wrapper"
        or methods[0].get("kind", "sce_locguard_api") != "sce_locguard_api"
    ):
        raise ChannelVoteConfirmationError(
            "Confirmation must enable only editguard_wrapper."
        )
    declared_required_capabilities = _validate_frozen_parameters(
        contract, methods[0]
    )

    traditional = (payload.get("attacks") or {}).get("traditional") or []
    try:
        observed_attacks = [
            str(spec.params.get("expanded_name") or spec.name)
            for spec in expand_attack_specs(traditional)
        ]
    except (TypeError, ValueError) as exc:
        raise ChannelVoteConfirmationError(
            f"Confirmation attacks are malformed: {exc}"
        ) from exc
    if observed_attacks != list(ATTACK_CONDITIONS) or (
        (payload.get("attacks") or {}).get("aigc")
        != {"enabled": False, "specs": []}
    ):
        raise ChannelVoteConfirmationError(
            "Confirmation attack cells differ from clean plus frozen erasing ratios."
        )

    formal_config = Path(str(contract.get("source_formal_config") or "")).resolve()
    formal_manifest_recorded = Path(
        str(contract.get("source_formal_manifest") or "")
    ).resolve()
    calibration_config = Path(
        str(contract.get("source_calibration_config") or "")
    ).resolve()
    calibration_manifest = Path(
        str(contract.get("source_calibration_manifest") or "")
    ).resolve()
    calibration_report = Path(
        str(contract.get("source_calibration_report") or "")
    ).resolve()
    calibration_run_root = Path(
        str(contract.get("source_calibration_run_root") or "")
    ).resolve()
    for label, path, expected_sha256 in (
        ("formal config", formal_config, contract.get("source_formal_config_sha256")),
        (
            "formal manifest",
            formal_manifest_recorded,
            contract.get("source_formal_manifest_sha256"),
        ),
        (
            "calibration config",
            calibration_config,
            contract.get("source_calibration_config_sha256"),
        ),
        (
            "calibration manifest",
            calibration_manifest,
            contract.get("source_calibration_manifest_sha256"),
        ),
        (
            "calibration report",
            calibration_report,
            contract.get("source_calibration_report_sha256"),
        ),
    ):
        if not path.is_file() or sha256_file(path) != expected_sha256:
            raise ChannelVoteConfirmationError(
                f"Frozen source {label} is missing or changed: {path}."
            )

    try:
        (
            formal_payload,
            formal_manifest,
            formal_rows,
            _,
            formal_lock_audit,
            split_audit,
        ) = _validate_formal_bundle(formal_config)
        (
            _,
            calibration_rows,
            calibration_lock_audit,
            selection_rationale,
            calibration_run_evidence,
            calibration_run_evidence_sha256,
            calibration_required_capabilities,
        ) = _validate_calibration_evidence(
            formal_config=formal_config,
            formal_manifest=formal_manifest,
            formal_lock_audit=formal_lock_audit,
            calibration_config=calibration_config,
            calibration_manifest=calibration_manifest,
            calibration_run_root=calibration_run_root,
            calibration_report=calibration_report,
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        if isinstance(exc, ChannelVoteConfirmationError):
            raise
        raise ChannelVoteConfirmationError(
            f"Frozen formal/calibration evidence failed revalidation: {exc}"
        ) from exc
    if (
        _validated_domain_coverage(
            payload,
            contract,
            source_formal_payload=formal_payload,
        )
        != declared_domain_coverage
    ):
        raise ChannelVoteConfirmationError(
            "Confirmation domain coverage changed during source revalidation."
        )
    if formal_manifest.resolve() != formal_manifest_recorded:
        raise ChannelVoteConfirmationError(
            "Recorded formal manifest path differs from the formal YAML."
        )
    if (
        formal_lock_audit != contract.get("source_formal_manifest_lock")
        or split_audit != contract.get("formal_split_assignment_audit")
        or calibration_lock_audit
        != contract.get("source_calibration_manifest_lock")
        or selection_rationale
        != contract.get("source_calibration_selection_rationale")
        or calibration_run_evidence
        != contract.get("source_calibration_run_evidence")
        or calibration_run_evidence_sha256
        != contract.get("source_calibration_run_evidence_sha256")
        or calibration_required_capabilities != declared_required_capabilities
    ):
        raise ChannelVoteConfirmationError(
            "Recorded source locks, assignment, report rationale, or run hashes changed."
        )

    expected_complement = _select_confirmation_complement(
        formal_rows, calibration_rows
    )
    calibration_ids_sha256 = hashlib.sha256(
        "\n".join(sorted(row.sample_id for row in calibration_rows)).encode("utf-8")
    ).hexdigest()
    if (
        contract.get("calibration_rows_excluded") != len(calibration_rows)
        or contract.get("calibration_sample_ids_sha256")
        != calibration_ids_sha256
        or contract.get("eligible_formal_dev_rows")
        != EXPECTED_FORMAL_SPLIT_COUNTS[SELECTION_SPLIT]
    ):
        raise ChannelVoteConfirmationError(
            "Calibration exclusion or formal-dev cardinality evidence changed."
        )

    source_tree_contract = contract.get("source_tree_identity") or {}
    project_root = Path(str(source_tree_contract.get("project_root") or "")).resolve()
    if project_root != Path(__file__).resolve().parents[2]:
        raise ChannelVoteConfirmationError(
            "Preregistered project root differs from the analyzer project root."
        )
    current_source_tree = _source_tree_identity(project_root)
    if source_tree_contract != {
        "project_root": str(project_root),
        "identity_version": current_source_tree["identity_version"],
        "scope": current_source_tree["scope"],
        "sha256": current_source_tree["sha256"],
        "file_count": current_source_tree["file_count"],
    }:
        raise ChannelVoteConfirmationError(
            "Current service source tree differs from the preregistered identity."
        )
    implementation = contract.get("traditional_attack_implementation") or {}
    attacks_path = (
        project_root / 'protection' / 'image_watermark' / "experiments" / "attacks.py"
    ).resolve()
    if (
        not isinstance(implementation, dict)
        or Path(str(implementation.get("path") or "")).resolve() != attacks_path
        or not attacks_path.is_file()
        or implementation.get("sha256") != sha256_file(attacks_path)
    ):
        raise ChannelVoteConfirmationError(
            "Shared attack implementation differs from the preregistration."
        )
    try:
        validate_preregistration_contract(
            contract.get("preregistration_claim") or {},
            config_path=config_path,
        )
    except PreregistrationError as exc:
        raise ChannelVoteConfirmationError(
            f"Confirmation preregistration contract is invalid: {exc}"
        ) from exc
    return payload, contract, expected_complement, calibration_rows, {
        "formal_lock": formal_lock_audit,
        "calibration_lock": calibration_lock_audit,
        "source_tree": current_source_tree,
        "domain_coverage": declared_domain_coverage,
    }


def _validate_selected_manifest(
    config_path: Path,
    contract: dict[str, Any],
    *,
    expected_rows: list[ImageSample],
) -> tuple[list[ImageSample], Path, dict[str, Any]]:
    manifest_path = manifest_path_from_config(config_path, environ={}).resolve()
    roots = dataset_roots_from_config(config_path, environ={})
    try:
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
    except (OSError, TypeError, ValueError) as exc:
        raise ChannelVoteConfirmationError(
            f"Confirmation manifest/lock validation failed: {exc}"
        ) from exc
    if len(rows) != EXPECTED_CONFIRMATION_SAMPLES or {
        row.split for row in rows
    } != {SELECTION_SPLIT}:
        raise ChannelVoteConfirmationError(
            "Confirmation manifest is not exactly 216 development rows."
        )
    canonical = sorted(rows, key=lambda row: (row.source_dataset, row.sample_id))
    if [row.sample_id for row in rows] != [row.sample_id for row in canonical]:
        raise ChannelVoteConfirmationError(
            "Confirmation manifest order is not canonical."
        )
    if [row.to_dict(include_runtime_path=False) for row in rows] != [
        row.to_dict(include_runtime_path=False) for row in expected_rows
    ]:
        raise ChannelVoteConfirmationError(
            "Confirmation manifest is not the exact formal-dev complement."
        )
    selected_ids_sha256 = hashlib.sha256(
        "\n".join(sorted(row.sample_id for row in rows)).encode("utf-8")
    ).hexdigest()
    dataset_counts: dict[str, int] = {}
    for row in rows:
        dataset_counts[row.source_dataset] = dataset_counts.get(row.source_dataset, 0) + 1
    _validate_observed_domain_coverage(rows, contract)
    if (
        sha256_file(manifest_path) != contract.get("selected_manifest_sha256")
        or selected_ids_sha256 != contract.get("selected_sample_ids_sha256")
        or _assignment_sha256(rows)
        != contract.get("confirmation_assignment_sha256")
        or len({row.sha256 for row in rows})
        != contract.get("selected_unique_sha256")
        or len({row.source_family for row in rows})
        != contract.get("selected_unique_source_families")
        or dict(sorted(dataset_counts.items()))
        != contract.get("selected_dataset_counts")
        or sorted(dataset_counts) != contract.get("selected_datasets")
    ):
        raise ChannelVoteConfirmationError(
            "Confirmation manifest hash, assignment, uniqueness, or coverage changed."
        )
    return rows, manifest_path, lock_audit


def _validate_run_rows(
    rows: list[dict[str, Any]],
    *,
    samples_by_id: dict[str, ImageSample],
    evaluation_seeds: tuple[int, ...] = EVALUATION_SEEDS,
) -> dict[str, list[dict[str, Any]]]:
    sample_ids = set(samples_by_id)
    if len(sample_ids) != EXPECTED_CONFIRMATION_SAMPLES:
        raise ChannelVoteConfirmationError(
            f"Analyzer received {len(sample_ids)} samples; expected 216."
        )
    if len(rows) != EXPECTED_ROWS:
        raise ChannelVoteConfirmationError(
            f"Confirmation has {len(rows)} result rows; expected {EXPECTED_ROWS}."
        )
    row_keys = [str(row.get("row_key") or "") for row in rows]
    if any(not key for key in row_keys) or len(set(row_keys)) != len(row_keys):
        raise ChannelVoteConfirmationError(
            "Confirmation row_key values are missing or duplicated."
        )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    combinations: set[tuple[str, int, str]] = set()
    verify_job_ids: set[str] = set()
    for row in rows:
        sample_id = str(row.get("sample_id") or "")
        attack_id = str(row.get("attack_id") or "")
        seed = row.get("seed")
        if (
            row.get("status") != "ok"
            or row.get("pipeline_success") != 1.0
            or row.get("implementation_level") != "real_pipeline"
            or row.get("run_class") != RUN_CLASS
            or row.get("paper_eligible") is not False
            or row.get("split") != SELECTION_SPLIT
            or row.get("method_id") != "editguard_wrapper"
            or row.get("traditional_attack_artifact_retention")
            != ATTACK_ARTIFACT_RETENTION
            or isinstance(seed, bool)
            or not isinstance(seed, int)
            or seed not in evaluation_seeds
            or sample_id not in samples_by_id
            or attack_id not in ATTACK_CONDITIONS
        ):
            raise ChannelVoteConfirmationError(
                "Confirmation contains failed, non-real, non-dev, or misclassified rows."
            )
        expected_key = f"editguard_wrapper|{sample_id}|{seed}|{attack_id}"
        if row.get("row_key") != expected_key:
            raise ChannelVoteConfirmationError(
                f"Confirmation row_key differs from the benchmark key: {expected_key}."
            )
        sample = samples_by_id[sample_id]
        if (
            row.get("image_sha256") != sample.sha256
            or row.get("source_dataset") != sample.source_dataset
        ):
            raise ChannelVoteConfirmationError(
                f"Confirmation source identity differs for {expected_key}."
            )
        verify_job_id = str(row.get("verify_job_id") or "")
        if (
            not re.fullmatch(r"verify_[A-Za-z0-9._-]+", verify_job_id)
            or verify_job_id in verify_job_ids
        ):
            raise ChannelVoteConfirmationError(
                f"Invalid or duplicate verify_job_id for {expected_key}."
            )
        verify_job_ids.add(verify_job_id)
        attacked_sha256 = str(row.get("attacked_image_sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", attacked_sha256):
            raise ChannelVoteConfirmationError(
                f"Missing attacked-image SHA-256 for {expected_key}."
            )
        if attack_id == "clean":
            if row.get("attack_truth_bbox") is not None:
                raise ChannelVoteConfirmationError(
                    f"Clean row declares a truth box: {expected_key}."
                )
        elif (
            row.get("attacked_image_retained") is not False
            or row.get("attacked_image_path") is not None
        ):
            raise ChannelVoteConfirmationError(
                f"Erasing artifact was retained despite hash_only: {expected_key}."
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
            raise ChannelVoteConfirmationError(
                f"Duplicate sample/seed/attack cell: {combination}."
            )
        combinations.add(combination)
        grouped[attack_id].append(row)
    expected_combinations = {
        (sample_id, seed, attack_id)
        for sample_id in sample_ids
        for seed in evaluation_seeds
        for attack_id in ATTACK_CONDITIONS
    }
    if combinations != expected_combinations or any(
        len(grouped[attack_id])
        != EXPECTED_CONFIRMATION_SAMPLES * len(evaluation_seeds)
        for attack_id in ATTACK_CONDITIONS
    ):
        raise ChannelVoteConfirmationError(
            "A confirmation sample/seed/attack cell is missing or duplicated."
        )
    return grouped


def _finite_protocol_value(value: Any, *, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise ChannelVoteConfirmationError(f"{label} is not finite.")
    return float(value)


def _evaluate_protocol_constraints(
    *,
    clean_mean: float,
    clean_p99: float,
    clean_max: float,
    erasing_mean_by_ratio: dict[str, float],
    erasing_p10_by_ratio: dict[str, float],
    erasing_success_rate_by_ratio: dict[str, float],
) -> tuple[list[dict[str, Any]], bool]:
    """Evaluate exact inclusive boundaries; exposed for focused boundary tests."""

    clean_mean = _finite_protocol_value(clean_mean, label="clean mean FPR")
    clean_p99 = _finite_protocol_value(clean_p99, label="clean p99 FPR")
    clean_max = _finite_protocol_value(clean_max, label="clean max FPR")
    ratio_keys = {f"{ratio:.2f}" for ratio in ERASING_RATIOS}
    for label, values in (
        ("erasing mean IoU", erasing_mean_by_ratio),
        ("erasing p10 IoU", erasing_p10_by_ratio),
        ("erasing IoU success rate", erasing_success_rate_by_ratio),
    ):
        if set(values) != ratio_keys:
            raise ChannelVoteConfirmationError(
                f"{label} ratios differ from the frozen cells."
            )
        for key, value in values.items():
            normalized = _finite_protocol_value(value, label=f"{label} {key}")
            if not 0.0 <= normalized <= 1.0:
                raise ChannelVoteConfirmationError(
                    f"{label} {key} is outside [0, 1]."
                )
    checks = [
        _constraint(
            name="clean_mean_mask_fpr",
            observed=clean_mean,
            operator="<=",
            limit=float(CONSTRAINTS["clean_mean_mask_fpr_max"]),
        ),
        _constraint(
            name="clean_p99_mask_fpr",
            observed=clean_p99,
            operator="<=",
            limit=float(CONSTRAINTS["clean_p99_mask_fpr_max"]),
        ),
        _constraint(
            name="clean_max_mask_fpr",
            observed=clean_max,
            operator="<=",
            limit=float(CONSTRAINTS["clean_max_mask_fpr_max"]),
        ),
    ]
    checks.extend(
        _constraint(
            name=f"erasing_{ratio:.2f}_mean_mask_iou",
            observed=float(erasing_mean_by_ratio[f"{ratio:.2f}"]),
            operator=">=",
            limit=float(CONSTRAINTS["each_erasing_mean_mask_iou_min"]),
        )
        for ratio in ERASING_RATIOS
    )
    checks.extend(
        _constraint(
            name=f"erasing_{ratio:.2f}_p10_mask_iou",
            observed=float(erasing_p10_by_ratio[f"{ratio:.2f}"]),
            operator=">=",
            limit=float(CONSTRAINTS["each_erasing_p10_mask_iou_min"]),
        )
        for ratio in ERASING_RATIOS
    )
    checks.extend(
        _constraint(
            name=f"erasing_{ratio:.2f}_iou_at_least_0_75_rate",
            observed=float(erasing_success_rate_by_ratio[f"{ratio:.2f}"]),
            operator=">=",
            limit=float(CONSTRAINTS["each_erasing_iou_at_least_0_75_rate_min"]),
        )
        for ratio in ERASING_RATIOS
    )
    return checks, all(bool(check["passed"]) for check in checks)


def _hash_calibration_files_still_bound(contract: dict[str, Any]) -> None:
    evidence = contract.get("source_calibration_run_evidence") or {}
    if not isinstance(evidence, dict):
        raise ChannelVoteConfirmationError("Calibration run evidence is malformed.")
    file_map = {
        "capabilities_sha256": Path("capabilities.json"),
        "preflight_sha256": Path("preflight.json"),
        "environment_sha256": Path("benchmark/environment.json"),
        "raw_results_sha256": Path("benchmark/raw_results.jsonl"),
    }
    for candidate_id, candidate in evidence.items():
        if not isinstance(candidate, dict):
            raise ChannelVoteConfirmationError(
                f"Calibration run evidence is malformed: {candidate_id}."
            )
        run_dir = Path(str(candidate.get("run_dir") or "")).resolve()
        for field, relative in file_map.items():
            path = (run_dir / relative).resolve()
            if not path.is_file() or sha256_file(path) != candidate.get(field):
                raise ChannelVoteConfirmationError(
                    f"Calibration source artifact changed after reanalysis: {path}."
                )


def _require_file_within(path: Path, root: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ChannelVoteConfirmationError(
            f"{label} escapes the confirmation run directory: {resolved}."
        ) from exc
    if not resolved.is_file():
        raise ChannelVoteConfirmationError(f"{label} is missing: {resolved}.")
    return resolved


def _read_strict_uint16_vote_png(path: Path) -> np.ndarray:
    """Read a true 16-bit grayscale PNG without an 8-bit conversion path."""

    raw_bytes = path.read_bytes()
    if (
        len(raw_bytes) < 33
        or raw_bytes[:8] != b"\x89PNG\r\n\x1a\n"
        or raw_bytes[12:16] != b"IHDR"
        or int.from_bytes(raw_bytes[8:12], "big") != 13
        or raw_bytes[24] != 16
        or raw_bytes[25] != 0
    ):
        raise ChannelVoteConfirmationError(
            f"Raw localization votes are not a 16-bit grayscale PNG: {path}."
        )
    with Image.open(path) as image:
        if image.format != "PNG" or image.mode not in {"I;16", "I;16B", "I"}:
            raise ChannelVoteConfirmationError(
                f"Raw vote PNG has an unsafe Pillow mode: {image.mode!r}."
            )
        native = np.asarray(image).copy()
    if native.ndim != 2 or native.dtype == np.dtype("uint8") or native.dtype.itemsize < 2:
        raise ChannelVoteConfirmationError(
            f"Raw vote PNG was decoded through an 8-bit or non-planar representation: "
            f"shape={native.shape}, dtype={native.dtype}."
        )
    if not np.issubdtype(native.dtype, np.integer):
        raise ChannelVoteConfirmationError(
            f"Raw vote PNG did not decode to integer samples: {native.dtype}."
        )
    if native.size and (int(native.min()) < 0 or int(native.max()) > 65535):
        raise ChannelVoteConfirmationError(
            "Raw vote PNG samples exceed uint16 and would overflow."
        )
    votes = native.astype(np.uint16, copy=False)
    allowed = np.asarray([0, 255, 510, 765], dtype=np.uint16)
    if votes.size == 0 or not bool(np.isin(votes, allowed).all()):
        unexpected = sorted(
            int(value) for value in np.unique(votes) if int(value) not in {0, 255, 510, 765}
        )
        raise ChannelVoteConfirmationError(
            f"Raw vote PNG contains values outside {{0,255,510,765}}: {unexpected[:10]}."
        )
    return votes


def _validate_raw_vote_artifacts(
    rows: list[dict[str, Any]],
    *,
    run_dir: Path,
    required_image_shape: tuple[int, int] = EXPECTED_SERVICE_IMAGE_SHAPE,
) -> tuple[dict[str, Any], str]:
    """Validate every verify row through the shared localization replay gate."""

    expected_paths: set[Path] = set()
    expected_predicted_paths: set[Path] = set()
    evidence: dict[str, Any] = {}
    artifact_run_root = run_dir / "benchmark"
    api_jobs_root = artifact_run_root / "api_jobs"
    for row in rows:
        row_key = str(row["row_key"])
        verify_job_id = str(row["verify_job_id"])
        verify_dir = api_jobs_root / verify_job_id / "verify"
        report_path = _require_file_within(
            verify_dir / "verify_report.json",
            run_dir,
            label="Verify report",
        )
        report = _read_json(report_path)
        response = report.get("response")
        if not isinstance(response, dict):
            raise ChannelVoteConfirmationError(
                f"Verify response evidence is missing: {row_key}."
            )
        if response.get("job_id") != verify_job_id:
            raise ChannelVoteConfirmationError(
                f"Verify response job id differs from the result row: {row_key}."
            )
        try:
            validated = validate_verify_localization_artifacts(
                response=response,
                artifact_run_root=artifact_run_root,
                required_capabilities=FROZEN_REQUIRED_CAPABILITIES,
                expected_input_sha256=row.get("attacked_image_sha256"),
                expected_seed=row.get("seed"),
                expected_image_shape=required_image_shape,
            )
        except (LocalizationArtifactError, OSError) as exc:
            raise ChannelVoteConfirmationError(
                f"Shared localization artifact validation failed for {row_key}: {exc}"
            ) from exc

        shared_evidence = copy.deepcopy(validated.evidence)
        if row.get("localization_artifact_evidence") != shared_evidence:
            raise ChannelVoteConfirmationError(
                f"Raw-results localization evidence differs from shared replay: {row_key}."
            )
        row_bindings = {
            "localization_artifact_evidence_sha256": shared_evidence[
                "canonical_evidence_sha256"
            ],
            "raw_localization_votes_sha256": shared_evidence["raw_vote_sha256"],
            "predicted_mask_sha256": shared_evidence["predicted_mask_sha256"],
            "localization_replay_identity_sha256": shared_evidence[
                "replay_identity_sha256"
            ],
        }
        if any(row.get(field) != value for field, value in row_bindings.items()):
            raise ChannelVoteConfirmationError(
                f"Raw-results localization hashes differ from shared replay: {row_key}."
            )

        fixed_vote_path = Path(shared_evidence["raw_vote_path"]).resolve()
        if fixed_vote_path in expected_paths:
            raise ChannelVoteConfirmationError(
                f"Multiple result rows reuse one raw-vote artifact: {fixed_vote_path}."
            )
        expected_paths.add(fixed_vote_path)
        predicted_path = Path(shared_evidence["predicted_mask_path"]).resolve()
        if predicted_path in expected_predicted_paths:
            raise ChannelVoteConfirmationError(
                f"Multiple result rows reuse one predicted-mask artifact: {predicted_path}."
            )
        expected_predicted_paths.add(predicted_path)
        evidence[row_key] = shared_evidence
    discovered_paths = {
        path.resolve()
        for path in api_jobs_root.rglob("raw_localization_channel_votes*")
        if path.is_file()
    }
    if discovered_paths != expected_paths:
        raise ChannelVoteConfirmationError(
            "Raw localization vote artifact set has missing, extra, or alternate files."
        )
    discovered_predicted_paths = {
        path.resolve()
        for path in api_jobs_root.rglob("predicted_mask*")
        if path.is_file()
    }
    if discovered_predicted_paths != expected_predicted_paths:
        raise ChannelVoteConfirmationError(
            "Predicted-mask artifact set has missing, extra, or alternate files."
        )
    evidence_sha256 = localization_evidence_sha256(evidence)
    return evidence, evidence_sha256


def _resolve_confirmation_run_directory(run_root: Path) -> Path:
    """Resolve the sole candidate without accepting symlinked run directories."""

    run_root = run_root.expanduser().resolve()
    confirmation_runs_root = run_root / "confirmation-run"
    if confirmation_runs_root.is_symlink():
        raise ChannelVoteConfirmationError(
            "Confirmation-run directory must not be a symlink: "
            f"{confirmation_runs_root}."
        )
    candidate_path = run_root / RUN_RELATIVE_PATH
    if candidate_path.is_symlink():
        raise ChannelVoteConfirmationError(
            f"Confirmation candidate directory must not be a symlink: {candidate_path}."
        )
    try:
        resolved = candidate_path.resolve(strict=True)
    except OSError as exc:
        raise ChannelVoteConfirmationError(
            f"Confirmation run directory is missing: {candidate_path}."
        ) from exc
    try:
        resolved.relative_to(run_root)
    except ValueError as exc:
        raise ChannelVoteConfirmationError(
            f"Confirmation run path escapes its bundle root: {resolved}."
        ) from exc
    if not resolved.is_dir():
        raise ChannelVoteConfirmationError(
            f"Confirmation run directory is missing: {resolved}."
        )
    return resolved


def analyze_channel_vote_confirmation(
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
    initial_config_sha256 = sha256_file(config_path)
    payload, contract, expected_rows, _, source_audits = (
        _validate_confirmation_config(config_path)
    )
    try:
        source_preregistration_evidence = validate_preregistration_claim(
            config_path,
            expected_run_class=RUN_CLASS,
        )
    except PreregistrationError as exc:
        raise ChannelVoteConfirmationError(
            f"Confirmation source preregistration claim is invalid: {exc}"
        ) from exc
    required_capabilities = _validated_required_capabilities(
        contract.get("required_capabilities")
    )
    rows, manifest_path, manifest_lock_audit = _validate_selected_manifest(
        config_path, contract, expected_rows=expected_rows
    )
    initial_manifest_sha256 = sha256_file(manifest_path)
    samples_by_id = {row.sample_id: row for row in rows}
    run_dir = _resolve_confirmation_run_directory(run_root)
    try:
        preregistration_evidence = validate_preregistration_claim(
            config_path,
            claim_path=run_dir / RUN_COPY_FILENAME,
            expected_run_class=RUN_CLASS,
            expected_nonce=source_preregistration_evidence["nonce"],
            expected_candidate_run=run_dir,
        )
    except PreregistrationError as exc:
        raise ChannelVoteConfirmationError(
            f"Confirmation candidate preregistration claim is invalid: {exc}"
        ) from exc
    run_class_path = run_dir / "run-class.txt"
    if (
        not run_class_path.is_file()
        or run_class_path.read_text(encoding="utf-8").strip() != RUN_CLASS
    ):
        raise ChannelVoteConfirmationError(
            f"Confirmation run class is invalid: {run_dir}."
        )
    preflight = _read_json(run_dir / "preflight.json")
    if preflight.get("status") not in {"ready", "ready_with_warnings"}:
        raise ChannelVoteConfirmationError(
            f"Confirmation preflight did not pass: {run_dir}."
        )
    startup_capabilities = _read_json(run_dir / "capabilities.json")
    _validate_required_capabilities(
        startup_capabilities,
        label="Startup",
        expected=required_capabilities,
    )
    environment = _read_json(run_dir / "benchmark" / "environment.json")
    if (
        environment.get("config_sha256") != initial_config_sha256
        or environment.get("manifest_sha256") != initial_manifest_sha256
        or Path(str(environment.get("config_path") or "")).resolve() != config_path
        or Path(str(environment.get("manifest_path") or "")).resolve()
        != manifest_path
        or environment.get("strict_paper_mode") is not True
        or environment.get("run_class") != RUN_CLASS
        or environment.get("paper_eligible") is not False
        or environment.get("evaluation_split") != SELECTION_SPLIT
        or environment.get("dataset_manifest_override_used") is not False
        or environment.get("dataset_roots_override_used") is not False
        or environment.get("manifest_lock") != manifest_lock_audit
        or environment.get("preregistration_claim") != preregistration_evidence
        or environment.get("methods")
        != [{"id": "editguard_wrapper", "kind": "sce_locguard_api"}]
    ):
        raise ChannelVoteConfirmationError(
            "Benchmark environment is not bound to the confirmation bundle."
        )
    source_tree = contract["source_tree_identity"]
    if (
        environment.get("source_tree_sha256") != source_tree["sha256"]
        or environment.get("source_tree_file_count") != source_tree["file_count"]
        or environment.get("source_tree_identity_version")
        != source_tree["identity_version"]
        or environment.get("source_tree_scope") != source_tree["scope"]
    ):
        raise ChannelVoteConfirmationError(
            "Benchmark ran a different service source tree than preregistered."
        )
    all_capabilities = environment.get("capabilities") or {}
    if not isinstance(all_capabilities, dict) or set(all_capabilities) != {
        "editguard_wrapper"
    }:
        raise ChannelVoteConfirmationError(
            "Benchmark capabilities do not identify only editguard_wrapper."
        )
    benchmark_capabilities = all_capabilities.get("editguard_wrapper")
    _validate_required_capabilities(
        benchmark_capabilities,
        label="Benchmark",
        expected=required_capabilities,
    )
    try:
        immutable_identity = _immutable_environment_identity(
            environment, startup_capabilities=startup_capabilities
        )
    except ThresholdCalibrationError as exc:
        raise ChannelVoteConfirmationError(
            f"Confirmation environment identity is invalid: {exc}"
        ) from exc
    identity_sha256 = hashlib.sha256(
        json.dumps(
            immutable_identity,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    manifest_audit = environment.get("input_manifest_audit") or {}
    expected_ids_sha256 = hashlib.sha256(
        "\n".join(sorted(samples_by_id)).encode("utf-8")
    ).hexdigest()
    if (
        not isinstance(manifest_audit, dict)
        or manifest_audit.get("total_samples") != EXPECTED_CONFIRMATION_SAMPLES
        or manifest_audit.get("selected_samples") != EXPECTED_CONFIRMATION_SAMPLES
        or manifest_audit.get("selected_split") != SELECTION_SPLIT
        or manifest_audit.get("selected_sample_ids_sha256")
        != expected_ids_sha256
    ):
        raise ChannelVoteConfirmationError(
            "Benchmark input-manifest audit is incomplete or changed."
        )
    implementation = contract["traditional_attack_implementation"]
    attacks_path = Path(str(implementation["path"])).resolve()
    runtime = environment.get("traditional_attack_runtime") or {}
    packages = environment.get("packages") or {}
    observed_packages = runtime.get("observed_packages") or {}
    if (
        not isinstance(runtime, dict)
        or not isinstance(packages, dict)
        or runtime.get("artifact_retention") != ATTACK_ARTIFACT_RETENTION
        or runtime.get("required_packages") != REQUIRED_ATTACK_RUNTIME
        or observed_packages != REQUIRED_ATTACK_RUNTIME
        or any(
            packages.get(name) != version
            for name, version in REQUIRED_ATTACK_RUNTIME.items()
        )
        or Path(str(runtime.get("implementation_path") or "")).resolve()
        != attacks_path
        or runtime.get("implementation_sha256") != implementation["sha256"]
    ):
        raise ChannelVoteConfirmationError(
            "Benchmark attack implementation/runtime differs from the protocol."
        )
    try:
        analyzer_runtime = _validate_current_attack_runtime(REQUIRED_ATTACK_RUNTIME)
    except ThresholdCalibrationError as exc:
        raise ChannelVoteConfirmationError(str(exc)) from exc
    raw_path = run_dir / "benchmark" / "raw_results.jsonl"
    raw_rows = _read_jsonl(raw_path)
    try:
        grouped = _validate_run_rows(raw_rows, samples_by_id=samples_by_id)
    except ThresholdCalibrationError as exc:
        raise ChannelVoteConfirmationError(str(exc)) from exc
    retained_attack_pngs = sorted((run_dir / "benchmark" / "attacks").rglob("*.png"))
    if retained_attack_pngs:
        raise ChannelVoteConfirmationError(
            f"Confirmation retained {len(retained_attack_pngs)} erasing PNGs under hash_only."
        )
    raw_vote_evidence, raw_vote_evidence_sha256 = _validate_raw_vote_artifacts(
        raw_rows,
        run_dir=run_dir,
    )
    try:
        attack_input_hashes = _independently_validate_candidate_artifacts(
            raw_rows,
            run_dir=run_dir,
            recovery_threshold=FROZEN_RECOVERY_THRESHOLD,
            localization_channel_vote_min=FROZEN_CHANNEL_VOTE_MIN,
            localization_contract=FROZEN_REQUIRED_CAPABILITIES,
        )
    except ThresholdCalibrationError as exc:
        raise ChannelVoteConfirmationError(
            f"Confirmation artifact replay failed: {exc}"
        ) from exc
    attack_hash_map_sha256 = hashlib.sha256(
        json.dumps(
            attack_input_hashes, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()

    clean = grouped["clean"]
    clean_fpr = _metric_summary(clean, "mask_fpr")
    condition_metrics: list[dict[str, Any]] = [
        {
            "attack_id": "clean",
            "rows": len(clean),
            "mask_fpr": clean_fpr,
            "image_tamper_false_positive_rate": _mean(
                clean, "image_tamper_detected"
            ),
            "predicted_tamper_area_ratio": _metric_summary(
                clean, "predicted_tamper_area_ratio"
            ),
            "source_registry_match_rate": _mean(clean, "source_registry_match"),
        }
    ]
    erasing_mean: dict[str, float] = {}
    erasing_p10: dict[str, float] = {}
    erasing_success: dict[str, float] = {}
    for ratio in ERASING_RATIOS:
        attack_id = f"erasing__area_ratio-{ratio}"
        attack_rows = grouped[attack_id]
        iou = _metric_summary(attack_rows, "mask_iou")
        ratio_key = f"{ratio:.2f}"
        erasing_mean[ratio_key] = iou["mean"]
        erasing_p10[ratio_key] = iou["p10"]
        erasing_success[ratio_key] = float(
            np.mean(
                np.asarray(
                    [_unit_interval(row, "mask_iou") >= 0.75 for row in attack_rows],
                    dtype=np.float64,
                )
            )
        )
        condition_metrics.append(
            {
                "attack_id": attack_id,
                "area_ratio": ratio,
                "rows": len(attack_rows),
                "mask_iou": iou,
                "mask_iou_at_least_0_75_rate": erasing_success[ratio_key],
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
    checks, passed = _evaluate_protocol_constraints(
        clean_mean=clean_fpr["mean"],
        clean_p99=clean_fpr["p99"],
        clean_max=clean_fpr["max"],
        erasing_mean_by_ratio=erasing_mean,
        erasing_p10_by_ratio=erasing_p10,
        erasing_success_rate_by_ratio=erasing_success,
    )

    if sha256_file(config_path) != initial_config_sha256:
        raise ChannelVoteConfirmationError(
            "Confirmation config changed during analysis."
        )
    if sha256_file(manifest_path) != initial_manifest_sha256:
        raise ChannelVoteConfirmationError(
            "Confirmation manifest changed during analysis."
        )
    current_tree = _source_tree_identity(Path(source_tree["project_root"]))
    if current_tree != {
        "identity_version": source_tree["identity_version"],
        "scope": source_tree["scope"],
        "sha256": source_tree["sha256"],
        "file_count": source_tree["file_count"],
    }:
        raise ChannelVoteConfirmationError(
            "Service source tree changed during analysis."
        )
    _hash_calibration_files_still_bound(contract)

    selection_metrics = {
        "clean_mean_mask_fpr": clean_fpr["mean"],
        "clean_p99_mask_fpr": clean_fpr["p99"],
        "clean_max_mask_fpr": clean_fpr["max"],
        "erasing_mean_mask_iou_by_ratio": erasing_mean,
        "erasing_p10_mask_iou_by_ratio": erasing_p10,
        "erasing_iou_at_least_0_75_rate_by_ratio": erasing_success,
        "erasing_equal_weight_macro_mean_iou": float(
            np.mean(list(erasing_mean.values()))
        ),
    }
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "confirmation_passed" if passed else "confirmation_failed",
        "confirmation_passed": passed,
        "run_class": RUN_CLASS,
        "development_only": True,
        "paper_eligible": False,
        "selection_split": SELECTION_SPLIT,
        "excluded_splits": ["train", "test"],
        "formal_test_rows_consumed": FORMAL_TEST_ROWS_CONSUMED,
        "parameter_selection_performed": False,
        "fallback_candidate_considered": False,
        "decision": "pass" if passed else "fail",
        "selection_rule": SELECTION_RULE,
        "candidate": copy.deepcopy(contract["candidate"]),
        "config": str(config_path),
        "config_sha256": initial_config_sha256,
        "preregistration_claim": source_preregistration_evidence,
        "candidate_preregistration_claim": preregistration_evidence,
        "manifest": str(manifest_path),
        "manifest_sha256": initial_manifest_sha256,
        "manifest_lock": manifest_lock_audit,
        "domain_coverage": copy.deepcopy(source_audits["domain_coverage"]),
        "run_dir": str(run_dir),
        "rows": len(raw_rows),
        "samples": len(rows),
        "unique_image_sha256": len({row.sha256 for row in rows}),
        "unique_source_families": len({row.source_family for row in rows}),
        "evaluation_seeds": list(EVALUATION_SEEDS),
        "condition_metrics": condition_metrics,
        "selection_metrics": selection_metrics,
        "constraint_checks": checks,
        "constraints": copy.deepcopy(CONSTRAINTS),
        "all_constraints_passed": passed,
        "retained_traditional_attack_pngs": 0,
        "attack_input_hash_map_sha256": attack_hash_map_sha256,
        "raw_localization_vote_artifacts": {
            "count": len(raw_vote_evidence),
            "threshold": 510,
            "dtype": "uint16",
            "encoding": "lossless_png_16bit_grayscale_I;16",
            "allowed_values": [0, 255, 510, 765],
            "evidence_sha256": raw_vote_evidence_sha256,
        },
        "capabilities_sha256": sha256_file(run_dir / "capabilities.json"),
        "preflight_sha256": sha256_file(run_dir / "preflight.json"),
        "environment_sha256": sha256_file(
            run_dir / "benchmark" / "environment.json"
        ),
        "raw_results_sha256": sha256_file(raw_path),
        "immutable_environment_identity": immutable_identity,
        "immutable_environment_identity_sha256": identity_sha256,
        "required_capabilities": copy.deepcopy(required_capabilities),
        "traditional_attack_runtime": {
            "implementation_path": str(attacks_path),
            "implementation_sha256": implementation["sha256"],
            "required_packages": copy.deepcopy(REQUIRED_ATTACK_RUNTIME),
            "observed_packages": copy.deepcopy(observed_packages),
            "analyzer_packages": analyzer_runtime,
            "artifact_retention": ATTACK_ARTIFACT_RETENTION,
        },
        "source_evidence": {
            "formal_manifest_lock": source_audits["formal_lock"],
            "calibration_manifest_lock": source_audits["calibration_lock"],
            "calibration_report_sha256": contract[
                "source_calibration_report_sha256"
            ],
            "calibration_run_evidence_sha256": contract[
                "source_calibration_run_evidence_sha256"
            ],
            "formal_split_assignment_audit": contract[
                "formal_split_assignment_audit"
            ],
            "source_tree_identity": copy.deepcopy(contract["source_tree_identity"]),
        },
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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
        else run_root / "channel_vote_confirmation_report.json"
    )
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite confirmation report: {output}")
    report = analyze_channel_vote_confirmation(config_path, run_root=run_root)
    _atomic_write_json(output, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["confirmation_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
