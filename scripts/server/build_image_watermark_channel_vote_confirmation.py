#!/usr/bin/env python3
"""Build the preregistered, development-only 2-of-3 confirmation bundle.

This protocol is deliberately not another parameter search.  It evaluates one
fixed service configuration on the 216 formal-development rows that were not
used by the preceding 117-row threshold calibration.  The formal test split is
never selected or consumed.
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
from typing import Any, Iterable

import yaml

from protection.supporting.image_watermark.experiments.manifest import (
    ImageSample,
    dataset_roots_from_config,
    load_manifest,
    manifest_lock_path,
    manifest_path_from_config,
    validate_manifest_lock,
    write_manifest,
)
from protection.supporting.image_watermark.experiments.paper_benchmark import _source_tree_identity
from scripts.server.analyze_image_watermark_threshold_calibration import (
    EXPECTED_ATTACK_MODEL_ID,
    ThresholdCalibrationError,
    _validate_calibration_config,
    _validate_selected_manifest,
    analyze_threshold_calibration,
)
from scripts.server.build_image_watermark_threshold_calibration import (
    ATTACK_ARTIFACT_RETENTION,
    ATTACK_CONDITIONS,
    CONSTRAINTS,
    EVALUATION_SEEDS,
    EXPECTED_SAMPLES as CALIBRATION_SAMPLES,
    REQUIRED_ATTACK_RUNTIME,
    audit_formal_split_assignments,
    normalize_base_url,
    sha256_file,
    _selected_attacks,
)
from scripts.server.image_watermark_preregistration import (
    build_preregistration_contract,
    claim_path_for_config,
    generate_preregistration_nonce,
    write_preregistration_claim,
)


SCHEMA_VERSION = "cogniguard_image_channel_vote_confirmation_v2"
RUN_CLASS = "channel_vote_confirmation_development_only"
SELECTION_SPLIT = "dev"
EXPECTED_FORMAL_SAMPLES = 3000
EXPECTED_FORMAL_SPLIT_COUNTS = {"dev": 333, "test": 558, "train": 2109}
EXPECTED_CONFIRMATION_SAMPLES = 216
EXPECTED_ROWS = (
    EXPECTED_CONFIRMATION_SAMPLES * len(EVALUATION_SEEDS) * len(ATTACK_CONDITIONS)
)
FORMAL_TEST_ROWS_CONSUMED = 0
CONFIRMATION_MINIMUM_DOMAINS = 9
FROZEN_RECOVERY_THRESHOLD = 0.34
FROZEN_CHANNEL_VOTE_MIN = 2
CANDIDATE_ID = "recovery_threshold_0p34__channel_vote_2of3"
RUN_RELATIVE_PATH = f"confirmation-run/{CANDIDATE_ID}"
FAILED_CALIBRATION_CONSTRAINT = "clean_max_mask_fpr"
TIED_RECOVERY_THRESHOLD = 0.36
TIED_CANDIDATE_ID = "recovery_threshold_0p36"
TIED_FAILED_CALIBRATION_CONSTRAINT = "erasing_0.05_mean_mask_iou"
PROTOCOL_AMENDMENT_ID = "channel_vote_mechanism_eligibility_after_117"
PROTOCOL_AMENDMENT_VERSION = "cogniguard_channel_vote_protocol_amendment_v1"
EXPECTED_MAX_CONSTRAINTS_PASSED = 11

FROZEN_REQUIRED_CAPABILITIES: dict[str, Any] = {
    "recovery_threshold": FROZEN_RECOVERY_THRESHOLD,
    "tamper_area_threshold": 0.001,
    "registry_hamming_radius": 1,
    "localization_mask_rule_version": "editguard_residual_channel_vote_v2",
    "localization_residual_channels": 3,
    "localization_channel_aggregation": "k_of_3",
    "localization_channel_vote_min": FROZEN_CHANNEL_VOTE_MIN,
    "localization_residual_threshold_rule": (
        "abs_gt_recovery_threshold_per_channel"
    ),
    "localization_postprocessing": "none",
}
RUNTIME_REQUIRED_CAPABILITY_FIELDS = (
    "attack_model_id",
    "attack_model_revision",
    "deterministic_mode_enabled",
)

SELECTION_RULE = (
    "Apply cogniguard_channel_vote_protocol_amendment_v1, disclosed as post-hoc "
    "to the 117-row calibration and frozen before the 216-row confirmation: require "
    "the exact 11-of-12 pass-count tie between recovery thresholds 0.34 and 0.36, "
    "with 0.34 failing only clean_max_mask_fpr and 0.36 failing only "
    "erasing_0.05_mean_mask_iou; treat only 0.34 as mechanism-eligible for the "
    "predeclared 2-of-3 clean-false-positive intervention; evaluate that sole "
    "candidate once on the disjoint 216-row dev complement; report pass/fail against "
    "every frozen constraint; do not search, rank, replace, or fall back to another "
    "parameter setting."
)


class ChannelVoteConfirmationBuildError(RuntimeError):
    """Raised when an input cannot prove the frozen confirmation protocol."""


def _confirmation_domain_coverage(
    source_formal_minimum_domains: Any,
    selected_domains: Iterable[str],
) -> dict[str, Any]:
    """Freeze the stronger confirmation-domain floor and its observed coverage."""

    if (
        type(source_formal_minimum_domains) is not int
        or source_formal_minimum_domains < 1
    ):
        raise ChannelVoteConfirmationBuildError(
            "Formal data_requirements.minimum_domains must be a positive integer."
        )
    materialized_domains = list(selected_domains)
    if not materialized_domains or any(
        type(domain) is not str or not domain.strip() for domain in materialized_domains
    ):
        raise ChannelVoteConfirmationBuildError(
            "Confirmation domains must be non-empty strings."
        )
    normalized_domains = sorted(set(materialized_domains))
    effective_minimum_domains = max(
        source_formal_minimum_domains,
        CONFIRMATION_MINIMUM_DOMAINS,
    )
    selected_domain_count = len(normalized_domains)
    if selected_domain_count < effective_minimum_domains:
        raise ChannelVoteConfirmationBuildError(
            f"Confirmation complement has {selected_domain_count} domains; "
            f"effective minimum is {effective_minimum_domains}."
        )
    return {
        "source_formal_minimum_domains": source_formal_minimum_domains,
        "confirmation_minimum_domains": CONFIRMATION_MINIMUM_DOMAINS,
        "effective_minimum_domains": effective_minimum_domains,
        "selected_domain_count": selected_domain_count,
        "selected_domains": normalized_domains,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the preregistered 216-row 2-of-3 confirmation bundle."
    )
    parser.add_argument("--source", required=True, help="Frozen 3000-row formal YAML.")
    parser.add_argument(
        "--calibration-config", required=True, help="117-row threshold YAML."
    )
    parser.add_argument(
        "--calibration-manifest", required=True, help="Locked 117-row JSONL."
    )
    parser.add_argument(
        "--calibration-run-root",
        required=True,
        help="Threshold bundle root containing candidate-runs/.",
    )
    parser.add_argument(
        "--calibration-report",
        required=True,
        help="Saved threshold-selection JSON to independently reproduce.",
    )
    parser.add_argument("--output", required=True, help="Fresh confirmation YAML.")
    parser.add_argument(
        "--manifest-output", required=True, help="Fresh 216-row JSONL."
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Exact image-watermark API origin, including an explicit port.",
    )
    return parser.parse_args()


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_mapping(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ChannelVoteConfirmationBuildError(f"{label} is missing: {path}")
    try:
        if path.suffix.lower() in {".yaml", ".yml"}:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ChannelVoteConfirmationBuildError(
            f"{label} cannot be parsed: {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ChannelVoteConfirmationBuildError(f"{label} must be a mapping: {path}")
    return payload


def _canonical_sha256(payload: Any) -> str:
    material = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _manifest_text(rows: Iterable[ImageSample]) -> str:
    return "".join(
        json.dumps(
            row.to_dict(include_runtime_path=False),
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
        for row in sorted(rows, key=lambda item: (item.source_dataset, item.sample_id))
    )


def _assignment_sha256(rows: Iterable[ImageSample]) -> str:
    material = "".join(
        "\t".join(
            (
                row.source_dataset,
                row.sample_id,
                row.source_family,
                row.sha256,
                row.split,
            )
        )
        + "\n"
        for row in sorted(rows, key=lambda item: (item.source_dataset, item.sample_id))
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _sample_identity(sample: ImageSample) -> tuple[str, ...]:
    return (
        sample.sample_id,
        sample.source_dataset,
        sample.relative_path,
        sample.sha256,
        sample.source_family,
        sample.split,
        sample.domain,
        sample.license_id,
        sample.license_url,
        sample.provenance,
        str(sample.width),
        str(sample.height),
    )


def _load_locked_manifest(
    config_path: Path,
    manifest_path: Path,
) -> tuple[list[ImageSample], dict[str, Path], dict[str, Any]]:
    """Load, hash-check, and lock-check a manifest without environment overrides."""

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
        raise ChannelVoteConfirmationBuildError(
            f"Locked manifest validation failed for {manifest_path}: {exc}"
        ) from exc
    return rows, roots, lock_audit


def _validate_formal_bundle(
    source_config: Path,
) -> tuple[dict[str, Any], Path, list[ImageSample], dict[str, Path], dict[str, Any], dict[str, Any]]:
    payload = _read_mapping(source_config, label="Formal config")
    experiment = payload.get("experiment") or {}
    manifest_cfg = payload.get("manifest") or {}
    requirements = payload.get("data_requirements") or {}
    if (
        not isinstance(experiment, dict)
        or experiment.get("split") != "test"
        or experiment.get("strict_paper_mode") is not True
        or experiment.get("fail_fast") is not True
        or experiment.get("traditional_attack_artifact_retention")
        != ATTACK_ARTIFACT_RETENTION
        or experiment.get("required_attack_runtime") != REQUIRED_ATTACK_RUNTIME
        or not isinstance(manifest_cfg, dict)
        or manifest_cfg.get("verify_hashes") is not True
        or manifest_cfg.get("require_lock") is not True
        or not isinstance(requirements, dict)
        or int(requirements.get("expected_total_samples") or 0)
        != EXPECTED_FORMAL_SAMPLES
    ):
        raise ChannelVoteConfirmationBuildError(
            "Source must be the strict, locked 3000-row formal test configuration."
        )
    source_manifest = manifest_path_from_config(source_config, environ={}).resolve()
    rows, roots, lock_audit = _load_locked_manifest(source_config, source_manifest)
    if len(rows) != EXPECTED_FORMAL_SAMPLES:
        raise ChannelVoteConfirmationBuildError(
            f"Formal manifest has {len(rows)} rows; expected {EXPECTED_FORMAL_SAMPLES}."
        )
    if len({row.sample_id for row in rows}) != EXPECTED_FORMAL_SAMPLES:
        raise ChannelVoteConfirmationBuildError("Formal sample_id values are not unique.")
    if len({row.sha256 for row in rows}) != EXPECTED_FORMAL_SAMPLES:
        raise ChannelVoteConfirmationBuildError("Formal image hashes are not unique.")
    if len({row.source_family for row in rows}) != EXPECTED_FORMAL_SAMPLES:
        raise ChannelVoteConfirmationBuildError(
            "Formal source_family values are not unique."
        )
    try:
        split_audit = audit_formal_split_assignments(
            rows, split_config=dict(payload.get("split") or {})
        )
    except (TypeError, ValueError) as exc:
        raise ChannelVoteConfirmationBuildError(
            f"Formal deterministic split audit failed: {exc}"
        ) from exc
    if split_audit.get("split_counts") != EXPECTED_FORMAL_SPLIT_COUNTS:
        raise ChannelVoteConfirmationBuildError(
            "Formal split counts differ from the frozen 2109/333/558 assignment: "
            f"{split_audit.get('split_counts')}."
        )

    enabled = [
        row
        for row in (payload.get("datasets") or [])
        if isinstance(row, dict) and row.get("enabled", True)
    ]
    enabled_names = {str(row.get("name") or "") for row in enabled}
    if not enabled_names or "" in enabled_names:
        raise ChannelVoteConfirmationBuildError(
            "Formal config has no complete enabled-dataset declaration."
        )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.source_dataset] = counts.get(row.source_dataset, 0) + 1
    expected_counts = {
        str(row["name"]): int(row["required_samples"])
        for row in enabled
        if row.get("required_samples") is not None
    }
    if set(counts) != enabled_names or counts != expected_counts:
        raise ChannelVoteConfirmationBuildError(
            f"Formal dataset quotas are not exact: expected={expected_counts}, observed={counts}."
        )
    return payload, source_manifest, rows, roots, lock_audit, split_audit


def _candidate_constraint_map(candidate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = candidate.get("constraint_checks")
    if not isinstance(checks, list) or not all(isinstance(row, dict) for row in checks):
        raise ChannelVoteConfirmationBuildError(
            "Calibration candidate has malformed constraint evidence."
        )
    result: dict[str, dict[str, Any]] = {}
    for row in checks:
        name = str(row.get("name") or "")
        if not name or name in result or not isinstance(row.get("passed"), bool):
            raise ChannelVoteConfirmationBuildError(
                "Calibration candidate constraint names/pass flags are malformed."
            )
        result[name] = row
    return result


def _selection_rationale_from_report(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("status") != "no_candidate_satisfies_constraints" or report.get(
        "winner"
    ) is not None:
        raise ChannelVoteConfirmationBuildError(
            "The source threshold calibration must have no eligible winner."
        )
    candidates = report.get("candidate_metrics")
    if not isinstance(candidates, list) or len(candidates) != 9:
        raise ChannelVoteConfirmationBuildError(
            "The source threshold report must contain all nine frozen candidates."
        )
    target_rows = [
        row
        for row in candidates
        if isinstance(row, dict)
        and math.isclose(
            float(row.get("recovery_threshold", math.nan)),
            FROZEN_RECOVERY_THRESHOLD,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    ]
    if len(target_rows) != 1:
        raise ChannelVoteConfirmationBuildError(
            "Threshold 0.34 is not represented exactly once in the calibration report."
        )
    target = target_rows[0]
    target_checks = _candidate_constraint_map(target)
    failed = sorted(name for name, row in target_checks.items() if not row["passed"])
    passed_count = sum(bool(row["passed"]) for row in target_checks.values())
    if (
        len(target_checks) != 12
        or passed_count != 11
        or failed != [FAILED_CALIBRATION_CONSTRAINT]
        or target.get("all_constraints_passed") is not False
    ):
        raise ChannelVoteConfirmationBuildError(
            "Threshold 0.34 must be the 11/12 candidate whose sole failure is "
            "clean_max_mask_fpr."
        )
    tied_rows = [
        row
        for row in candidates
        if isinstance(row, dict)
        and math.isclose(
            float(row.get("recovery_threshold", math.nan)),
            TIED_RECOVERY_THRESHOLD,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    ]
    if len(tied_rows) != 1:
        raise ChannelVoteConfirmationBuildError(
            "Threshold 0.36 is not represented exactly once in the calibration report."
        )
    tied = tied_rows[0]
    tied_checks = _candidate_constraint_map(tied)
    tied_failed = sorted(
        name for name, row in tied_checks.items() if not row["passed"]
    )
    tied_passed_count = sum(bool(row["passed"]) for row in tied_checks.values())
    if (
        len(tied_checks) != 12
        or tied_passed_count != EXPECTED_MAX_CONSTRAINTS_PASSED
        or tied_failed != [TIED_FAILED_CALIBRATION_CONSTRAINT]
        or tied.get("all_constraints_passed") is not False
    ):
        raise ChannelVoteConfirmationBuildError(
            "Threshold 0.36 must be the tied 11/12 candidate whose sole failure is "
            "erasing_0.05_mean_mask_iou; it is not eligible for the clean-FPR "
            "channel-vote intervention."
        )

    pass_counts: dict[str, int] = {}
    failure_sets: dict[str, list[str]] = {}
    expected_constraint_names = set(target_checks)
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ChannelVoteConfirmationBuildError(
                "Calibration candidate evidence is malformed."
            )
        candidate_name = str(candidate.get("candidate_id") or "")
        if not candidate_name or candidate_name in pass_counts:
            raise ChannelVoteConfirmationBuildError(
                "Calibration candidate ids are missing or duplicated."
            )
        candidate_checks = _candidate_constraint_map(candidate)
        if (
            len(candidate_checks) != 12
            or set(candidate_checks) != expected_constraint_names
            or candidate.get("all_constraints_passed") is not False
        ):
            raise ChannelVoteConfirmationBuildError(
                "Every calibration candidate must expose the same twelve failed-or-"
                "passed constraints and no all-pass winner."
            )
        pass_counts[candidate_name] = sum(
            bool(row["passed"]) for row in candidate_checks.values()
        )
        failure_sets[candidate_name] = sorted(
            name for name, row in candidate_checks.items() if not row["passed"]
        )
    maximum_pass_count = max(pass_counts.values())
    pass_count_tie_candidate_ids = sorted(
        name for name, count in pass_counts.items() if count == maximum_pass_count
    )
    expected_tie_candidate_ids = sorted(
        [CANDIDATE_ID.split("__", 1)[0], TIED_CANDIDATE_ID]
    )
    if (
        maximum_pass_count != EXPECTED_MAX_CONSTRAINTS_PASSED
        or pass_count_tie_candidate_ids != expected_tie_candidate_ids
        or any(
            count > 10
            for name, count in pass_counts.items()
            if name not in expected_tie_candidate_ids
        )
    ):
        raise ChannelVoteConfirmationBuildError(
            "Calibration pass-count tie does not match the amended mechanism-"
            "eligibility contract: expected only thresholds 0.34 and 0.36 at 11/12 "
            f"and every other candidate at no more than 10/12; observed "
            f"leaders={pass_count_tie_candidate_ids}, counts={pass_counts}."
        )
    metrics = target.get("selection_metrics")
    if not isinstance(metrics, dict):
        raise ChannelVoteConfirmationBuildError(
            "Threshold 0.34 selection metrics are missing."
        )
    return {
        "source_candidate_id": target.get("candidate_id"),
        "source_recovery_threshold": FROZEN_RECOVERY_THRESHOLD,
        "constraints_passed": passed_count,
        "constraints_total": len(target_checks),
        "sole_failed_constraint": FAILED_CALIBRATION_CONSTRAINT,
        "selection_metrics": copy.deepcopy(metrics),
        "constraint_checks": copy.deepcopy(target.get("constraint_checks")),
        "pass_count_tie": True,
        "maximum_constraints_passed": maximum_pass_count,
        "pass_count_tie_candidate_ids": pass_count_tie_candidate_ids,
        "candidate_pass_counts": dict(sorted(pass_counts.items())),
        "candidate_failure_sets": {
            name: failure_sets[name] for name in sorted(failure_sets)
        },
        "protocol_amendment_id": PROTOCOL_AMENDMENT_ID,
        "protocol_amendment_version": PROTOCOL_AMENDMENT_VERSION,
        "posthoc_to_117": True,
        "preregistered_before_216": True,
        "mechanism_eligibility": {
            "eligible_candidate_ids": [CANDIDATE_ID.split("__", 1)[0]],
            "ineligible_tied_candidate_ids": [TIED_CANDIDATE_ID],
            "intervention": "increase_channel_vote_min_from_1_to_2",
            "targeted_failure_class": "isolated_single_channel_clean_false_positive",
            "non_targeted_failure_class": "erasing_localization_mean_iou",
            "selected_candidate_changed_by_amendment": False,
        },
        "reason": (
            "The one-channel threshold calibration had no all-pass candidate. "
            "Thresholds 0.34 and 0.36 tied at 11 of 12 frozen constraints.  Threshold "
            "0.34 failed only clean maximum FPR, whereas threshold 0.36 failed only "
            "5-percent erasing mean IoU.  This versioned amendment is explicitly "
            "post-hoc to the 117-row calibration and preregistered before any inference "
            "on the disjoint 216-row complement.  The 2-of-3 rule directly targets "
            "isolated single-channel clean false positives, so 0.34 is the sole "
            "mechanism-eligible confirmation candidate; increasing the vote minimum "
            "does not target the erasing-localization failure at 0.36."
        ),
    }


def _calibration_run_evidence(report: dict[str, Any]) -> tuple[dict[str, Any], str]:
    candidates = report.get("candidate_metrics") or []
    evidence: dict[str, Any] = {}
    required_hash_fields = (
        "capabilities_sha256",
        "preflight_sha256",
        "environment_sha256",
        "raw_results_sha256",
        "attack_input_hash_map_sha256",
        "immutable_environment_identity_sha256",
        "localization_artifact_evidence_sha256",
    )
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id") or "")
        if not candidate_id or candidate_id in evidence:
            raise ChannelVoteConfirmationBuildError(
                "Calibration run evidence has a missing or duplicate candidate id."
            )
        hashes = {name: candidate.get(name) for name in required_hash_fields}
        if any(
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in hashes.values()
        ):
            raise ChannelVoteConfirmationBuildError(
                f"Calibration candidate hash evidence is malformed: {candidate_id}."
            )
        localization_evidence = candidate.get("localization_artifact_evidence")
        localization_rows = (
            localization_evidence.get("rows")
            if isinstance(localization_evidence, dict)
            else None
        )
        localization_count = candidate.get("localization_artifact_evidence_count")
        if (
            not isinstance(localization_evidence, dict)
            or localization_evidence.get("schema_version")
            != "cogniguard_localization_artifact_evidence_v1"
            or not isinstance(localization_rows, dict)
            or type(localization_count) is not int
            or localization_count != candidate.get("rows")
            or localization_evidence.get("count") != localization_count
            or len(localization_rows) != localization_count
            or localization_evidence.get("evidence_sha256")
            != hashes["localization_artifact_evidence_sha256"]
            or _canonical_sha256(localization_rows)
            != hashes["localization_artifact_evidence_sha256"]
        ):
            raise ChannelVoteConfirmationBuildError(
                "Calibration candidate localization-artifact evidence is malformed "
                f"or unauthenticated: {candidate_id}."
            )
        evidence[candidate_id] = {
            "run_dir": candidate.get("run_dir"),
            "rows": candidate.get("rows"),
            "localization_artifact_evidence_count": localization_count,
            **hashes,
        }
    return evidence, _canonical_sha256(evidence)


def _required_capabilities_from_calibration_report(
    report: dict[str, Any],
) -> dict[str, Any]:
    identity = report.get("immutable_environment_identity")
    fixed = identity.get("fixed_capabilities") if isinstance(identity, dict) else None
    if not isinstance(fixed, dict):
        raise ChannelVoteConfirmationBuildError(
            "Calibration report has no authenticated fixed-capability identity."
        )
    model_id = fixed.get("attack_model_id")
    revision = fixed.get("attack_model_revision")
    deterministic = fixed.get("deterministic_mode_enabled")
    if model_id != EXPECTED_ATTACK_MODEL_ID:
        raise ChannelVoteConfirmationBuildError(
            f"Calibration attack_model_id is not frozen: {model_id!r}."
        )
    if type(revision) is not str or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ChannelVoteConfirmationBuildError(
            "Calibration attack_model_revision must be an exact 40-character "
            "lowercase commit hash."
        )
    if deterministic is not True:
        raise ChannelVoteConfirmationBuildError(
            "Calibration deterministic_mode_enabled must be exactly true."
        )
    return {
        **copy.deepcopy(FROZEN_REQUIRED_CAPABILITIES),
        "attack_model_id": model_id,
        "attack_model_revision": revision,
        "deterministic_mode_enabled": deterministic,
    }


def _validate_calibration_evidence(
    *,
    formal_config: Path,
    formal_manifest: Path,
    formal_lock_audit: dict[str, Any],
    calibration_config: Path,
    calibration_manifest: Path,
    calibration_run_root: Path,
    calibration_report: Path,
) -> tuple[
    dict[str, Any],
    list[ImageSample],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    str,
    dict[str, Any],
]:
    """Re-run the full threshold analyzer and prove every source binding."""

    try:
        calibration_payload, calibration_contract = _validate_calibration_config(
            calibration_config
        )
        calibration_rows, declared_manifest, calibration_lock_audit = (
            _validate_selected_manifest(calibration_config, calibration_contract)
        )
        recomputed_report = analyze_threshold_calibration(
            calibration_config, run_root=calibration_run_root
        )
    except (OSError, TypeError, ValueError, ThresholdCalibrationError) as exc:
        raise ChannelVoteConfirmationBuildError(
            f"Threshold calibration cannot be independently reproduced: {exc}"
        ) from exc
    if declared_manifest.resolve() != calibration_manifest.resolve():
        raise ChannelVoteConfirmationBuildError(
            "The supplied calibration manifest differs from the one locked by its YAML."
        )
    saved_report = _read_mapping(calibration_report, label="Calibration report")
    if saved_report != recomputed_report:
        raise ChannelVoteConfirmationBuildError(
            "Saved calibration report differs from a fresh full-evidence analysis."
        )
    if (
        Path(str(calibration_contract.get("source_formal_config") or "")).resolve()
        != formal_config.resolve()
        or Path(
            str(calibration_contract.get("source_formal_manifest") or "")
        ).resolve()
        != formal_manifest.resolve()
        or calibration_contract.get("source_formal_config_sha256")
        != sha256_file(formal_config)
        or calibration_contract.get("source_formal_manifest_sha256")
        != sha256_file(formal_manifest)
        or calibration_contract.get("source_formal_manifest_lock")
        != formal_lock_audit
    ):
        raise ChannelVoteConfirmationBuildError(
            "Calibration inputs are not bound to the supplied frozen formal bundle."
        )
    if len(calibration_rows) != CALIBRATION_SAMPLES or {
        row.split for row in calibration_rows
    } != {SELECTION_SPLIT}:
        raise ChannelVoteConfirmationBuildError(
            "Calibration manifest is not the exact 117-row dev selection."
        )
    rationale = _selection_rationale_from_report(recomputed_report)
    run_evidence, run_evidence_sha256 = _calibration_run_evidence(recomputed_report)
    required_capabilities = _required_capabilities_from_calibration_report(
        recomputed_report
    )
    return (
        calibration_payload,
        calibration_rows,
        calibration_lock_audit,
        rationale,
        run_evidence,
        run_evidence_sha256,
        required_capabilities,
    )


def _select_confirmation_complement(
    formal_rows: Iterable[ImageSample],
    calibration_rows: Iterable[ImageSample],
) -> list[ImageSample]:
    """Return the exact 333-dev minus 117-calibration complement."""

    formal = list(formal_rows)
    calibration = list(calibration_rows)
    dev = [row for row in formal if row.split == SELECTION_SPLIT]
    if len(dev) != EXPECTED_FORMAL_SPLIT_COUNTS[SELECTION_SPLIT]:
        raise ChannelVoteConfirmationBuildError(
            f"Formal dev split has {len(dev)} rows; expected 333."
        )
    formal_by_id = {row.sample_id: row for row in formal}
    if len(formal_by_id) != len(formal):
        raise ChannelVoteConfirmationBuildError("Formal sample ids are not unique.")
    calibration_ids: set[str] = set()
    for row in calibration:
        formal_row = formal_by_id.get(row.sample_id)
        if (
            formal_row is None
            or row.split != SELECTION_SPLIT
            or formal_row.split != SELECTION_SPLIT
            or _sample_identity(row) != _sample_identity(formal_row)
            or row.sample_id in calibration_ids
        ):
            raise ChannelVoteConfirmationBuildError(
                "Calibration manifest is not an identity-preserving subset of formal dev: "
                f"{row.sample_id}."
            )
        calibration_ids.add(row.sample_id)
    if len(calibration_ids) != CALIBRATION_SAMPLES:
        raise ChannelVoteConfirmationBuildError(
            f"Calibration selection has {len(calibration_ids)} rows; expected 117."
        )
    complement = sorted(
        (row for row in dev if row.sample_id not in calibration_ids),
        key=lambda item: (item.source_dataset, item.sample_id),
    )
    if len(complement) != EXPECTED_CONFIRMATION_SAMPLES:
        raise ChannelVoteConfirmationBuildError(
            f"Dev complement has {len(complement)} rows; expected 216."
        )
    if (
        {row.split for row in complement} != {SELECTION_SPLIT}
        or len({row.sample_id for row in complement}) != EXPECTED_CONFIRMATION_SAMPLES
        or len({row.sha256 for row in complement}) != EXPECTED_CONFIRMATION_SAMPLES
        or len({row.source_family for row in complement})
        != EXPECTED_CONFIRMATION_SAMPLES
        or {row.sample_id for row in complement}.intersection(calibration_ids)
    ):
        raise ChannelVoteConfirmationBuildError(
            "Confirmation complement is not unique, development-only, and disjoint."
        )
    return complement


def _assert_contract_sources_unchanged(contract: dict[str, Any]) -> None:
    for label, path_field, hash_field in (
        ("formal config", "source_formal_config", "source_formal_config_sha256"),
        (
            "formal manifest",
            "source_formal_manifest",
            "source_formal_manifest_sha256",
        ),
        (
            "calibration config",
            "source_calibration_config",
            "source_calibration_config_sha256",
        ),
        (
            "calibration manifest",
            "source_calibration_manifest",
            "source_calibration_manifest_sha256",
        ),
        (
            "calibration report",
            "source_calibration_report",
            "source_calibration_report_sha256",
        ),
    ):
        path = Path(str(contract.get(path_field) or "")).resolve()
        if not path.is_file() or sha256_file(path) != contract.get(hash_field):
            raise ChannelVoteConfirmationBuildError(
                f"Frozen {label} changed while the confirmation bundle was built: {path}."
            )
    for label, lock_field in (
        ("formal manifest lock", "source_formal_manifest_lock"),
        ("calibration manifest lock", "source_calibration_manifest_lock"),
    ):
        lock = contract.get(lock_field) or {}
        path = Path(str(lock.get("lock_path") or "")).resolve()
        if not path.is_file() or sha256_file(path) != lock.get("lock_sha256"):
            raise ChannelVoteConfirmationBuildError(
                f"Frozen {label} changed while the confirmation bundle was built: {path}."
            )
    evidence = contract.get("source_calibration_run_evidence") or {}
    artifact_fields = {
        "capabilities_sha256": Path("capabilities.json"),
        "preflight_sha256": Path("preflight.json"),
        "environment_sha256": Path("benchmark/environment.json"),
        "raw_results_sha256": Path("benchmark/raw_results.jsonl"),
    }
    if not isinstance(evidence, dict):
        raise ChannelVoteConfirmationBuildError(
            "Frozen calibration run evidence is malformed."
        )
    for candidate_id, candidate in evidence.items():
        if not isinstance(candidate, dict):
            raise ChannelVoteConfirmationBuildError(
                f"Frozen calibration run evidence is malformed: {candidate_id}."
            )
        run_dir = Path(str(candidate.get("run_dir") or "")).resolve()
        for hash_field, relative_path in artifact_fields.items():
            path = (run_dir / relative_path).resolve()
            if not path.is_file() or sha256_file(path) != candidate.get(hash_field):
                raise ChannelVoteConfirmationBuildError(
                    "Frozen calibration candidate artifact changed while building: "
                    f"{path}."
                )
    source_tree = contract.get("source_tree_identity") or {}
    project_root = Path(str(source_tree.get("project_root") or "")).resolve()
    current_tree = _source_tree_identity(project_root)
    if source_tree != {
        "project_root": str(project_root),
        "identity_version": current_tree["identity_version"],
        "scope": current_tree["scope"],
        "sha256": current_tree["sha256"],
        "file_count": current_tree["file_count"],
    }:
        raise ChannelVoteConfirmationBuildError(
            "Service source tree changed while the confirmation bundle was built."
        )


def build_channel_vote_confirmation_bundle(
    source_config: Path,
    *,
    calibration_config: Path,
    calibration_manifest: Path,
    calibration_run_root: Path,
    calibration_report: Path,
    output_config: Path,
    output_manifest: Path,
    base_url: str,
    preregistration_nonce: str | None = None,
) -> tuple[dict[str, Any], list[ImageSample]]:
    source_config = source_config.expanduser().resolve()
    calibration_config = calibration_config.expanduser().resolve()
    calibration_manifest = calibration_manifest.expanduser().resolve()
    calibration_run_root = calibration_run_root.expanduser().resolve()
    calibration_report = calibration_report.expanduser().resolve()
    output_config = output_config.expanduser().resolve()
    output_manifest = output_manifest.expanduser().resolve()
    if len({output_config, output_manifest}) != 2:
        raise ChannelVoteConfirmationBuildError(
            "Confirmation config and manifest paths must differ."
        )
    if output_config.parent != output_manifest.parent:
        raise ChannelVoteConfirmationBuildError(
            "Confirmation config and manifest must share one bundle directory."
        )
    preregistration_nonce = (
        generate_preregistration_nonce()
        if preregistration_nonce is None
        else preregistration_nonce
    )
    if output_config in {
        source_config,
        calibration_config,
        calibration_manifest,
        calibration_report,
    } or output_manifest in {
        source_config,
        calibration_config,
        calibration_manifest,
        calibration_report,
    }:
        raise ChannelVoteConfirmationBuildError(
            "Confirmation outputs must not overwrite any frozen input."
        )
    candidate_run_path = (output_config.parent / RUN_RELATIVE_PATH).resolve()
    if candidate_run_path.exists():
        raise ChannelVoteConfirmationBuildError(
            "Refusing to preregister after a candidate run path already exists: "
            f"{candidate_run_path}."
        )
    initial_input_hashes = {
        source_config: sha256_file(source_config),
        calibration_config: sha256_file(calibration_config),
        calibration_manifest: sha256_file(calibration_manifest),
        calibration_report: sha256_file(calibration_report),
    }
    frozen_base_url = normalize_base_url(base_url)
    (
        formal_payload,
        formal_manifest,
        formal_rows,
        formal_roots,
        formal_lock_audit,
        split_audit,
    ) = _validate_formal_bundle(source_config)
    (
        _,
        calibration_rows,
        calibration_lock_audit,
        selection_rationale,
        calibration_run_evidence,
        calibration_run_evidence_sha256,
        required_capabilities,
    ) = _validate_calibration_evidence(
        formal_config=source_config,
        formal_manifest=formal_manifest,
        formal_lock_audit=formal_lock_audit,
        calibration_config=calibration_config,
        calibration_manifest=calibration_manifest,
        calibration_run_root=calibration_run_root,
        calibration_report=calibration_report,
    )
    selected = _select_confirmation_complement(formal_rows, calibration_rows)

    formal_enabled_datasets = [
        copy.deepcopy(row)
        for row in (formal_payload.get("datasets") or [])
        if isinstance(row, dict) and row.get("enabled", True)
    ]
    selected_counts: dict[str, int] = {}
    for row in selected:
        selected_counts[row.source_dataset] = selected_counts.get(row.source_dataset, 0) + 1
    enabled_names = {str(row.get("name") or "") for row in formal_enabled_datasets}
    if set(selected_counts) != enabled_names:
        raise ChannelVoteConfirmationBuildError(
            "The 216-row complement must retain every enabled formal dataset: "
            f"selected={sorted(selected_counts)}, enabled={sorted(enabled_names)}."
        )
    datasets: list[dict[str, Any]] = []
    for dataset in formal_enabled_datasets:
        name = str(dataset.get("name") or "")
        root = formal_roots.get(name)
        if root is None or not root.is_dir():
            raise ChannelVoteConfirmationBuildError(
                f"Formal dataset root is unavailable: {name}."
            )
        dataset["root"] = str(root)
        dataset["enabled"] = True
        dataset["required_samples"] = selected_counts[name]
        dataset["max_samples"] = selected_counts[name]
        datasets.append(dataset)

    methods = [
        copy.deepcopy(row)
        for row in (formal_payload.get("methods") or [])
        if isinstance(row, dict)
        and row.get("id") == "editguard_wrapper"
        and row.get("enabled", True)
    ]
    if len(methods) != 1:
        raise ChannelVoteConfirmationBuildError(
            "Confirmation requires exactly one enabled editguard_wrapper method."
        )
    methods[0]["enabled"] = True
    methods[0]["base_url"] = frozen_base_url
    methods[0]["required_capabilities"] = copy.deepcopy(required_capabilities)
    attacks = _selected_attacks(formal_payload)
    attack_path = (
        Path(__file__).resolve().parents[2]
        / 'protection' / 'image_watermark'
        / "experiments"
        / "attacks.py"
    ).resolve()
    if not attack_path.is_file():
        raise ChannelVoteConfirmationBuildError(
            f"Shared attack implementation is missing: {attack_path}."
        )
    project_root = Path(__file__).resolve().parents[2]
    source_tree = _source_tree_identity(project_root)
    selected_text = _manifest_text(selected)
    selected_ids = sorted(row.sample_id for row in selected)
    calibration_ids = sorted(row.sample_id for row in calibration_rows)
    selected_domains = sorted({row.domain for row in selected})
    formal_requirements = formal_payload.get("data_requirements") or {}
    domain_coverage = _confirmation_domain_coverage(
        formal_requirements.get("minimum_domains"),
        selected_domains,
    )

    config = copy.deepcopy(formal_payload)
    formal_experiment = formal_payload.get("experiment") or {}
    config["experiment"] = {
        "name": "cogniguard_v2_channel_vote_confirmation",
        "strict_paper_mode": True,
        "fail_fast": True,
        "run_class": RUN_CLASS,
        "paper_eligible": False,
        "development_only": True,
        "split": SELECTION_SPLIT,
        "seeds": list(EVALUATION_SEEDS),
        "max_samples": EXPECTED_CONFIRMATION_SAMPLES,
        "api_timeout_seconds": int(formal_experiment.get("api_timeout_seconds", 900)),
        "bootstrap_iterations": 2000,
        "bootstrap_seed": int(EVALUATION_SEEDS[0]),
        "traditional_attack_artifact_retention": ATTACK_ARTIFACT_RETENTION,
        "required_attack_runtime": copy.deepcopy(REQUIRED_ATTACK_RUNTIME),
        "output_root": str((output_config.parent / RUN_RELATIVE_PATH).resolve()),
    }
    config["manifest"] = {
        "path": str(output_manifest),
        "verify_hashes": True,
        "require_lock": True,
    }
    config["data_requirements"] = {
        "expected_total_samples": EXPECTED_CONFIRMATION_SAMPLES,
        "minimum_selected_samples": EXPECTED_CONFIRMATION_SAMPLES,
        "minimum_test_samples": EXPECTED_CONFIRMATION_SAMPLES,
        "minimum_datasets": len(enabled_names),
        "minimum_domains": domain_coverage["effective_minimum_domains"],
        "require_nonempty_source_family": True,
        "require_unique_source_family": True,
        "expected_unique_source_families": EXPECTED_CONFIRMATION_SAMPLES,
        "require_deterministic_splits": True,
    }
    config["metrics"] = {
        "require_reference_ssim": True,
        "lpips": {"enabled": False, "required": False},
    }
    config["datasets"] = datasets
    config["methods"] = methods
    config["attacks"] = {
        "traditional": attacks,
        "aigc": {"enabled": False, "specs": []},
    }
    config["channel_vote_confirmation"] = {
        "schema_version": SCHEMA_VERSION,
        "run_class": RUN_CLASS,
        "development_only": True,
        "paper_eligible": False,
        "selection_split": SELECTION_SPLIT,
        "excluded_splits": ["train", "test"],
        "formal_test_rows_consumed": FORMAL_TEST_ROWS_CONSUMED,
        "formal_config_mutation_allowed": False,
        "formal_config_update_performed": False,
        "parameter_search_allowed": False,
        "posthoc_parameter_change_allowed": False,
        "fallback_candidate_allowed": False,
        "preregistered_before_candidate_execution": True,
        "preexisting_candidate_artifacts": 0,
        "candidate_count": 1,
        "candidate": {
            "candidate_id": CANDIDATE_ID,
            **copy.deepcopy(required_capabilities),
            "run_relative_path": RUN_RELATIVE_PATH,
        },
        "preregistration_claim": build_preregistration_contract(
            config_path=output_config,
            nonce=preregistration_nonce,
            expected_candidate_run_relative_paths=[RUN_RELATIVE_PATH],
        ),
        "required_capabilities": copy.deepcopy(required_capabilities),
        "selection_rule": SELECTION_RULE,
        "decision_output": "pass_or_fail_only_no_parameter_selection",
        "source_formal_config": str(source_config),
        "source_formal_config_sha256": sha256_file(source_config),
        "source_formal_manifest": str(formal_manifest),
        "source_formal_manifest_sha256": sha256_file(formal_manifest),
        "source_formal_manifest_lock": copy.deepcopy(formal_lock_audit),
        "formal_split_assignment_audit": copy.deepcopy(split_audit),
        "source_calibration_config": str(calibration_config),
        "source_calibration_config_sha256": sha256_file(calibration_config),
        "source_calibration_manifest": str(calibration_manifest),
        "source_calibration_manifest_sha256": sha256_file(calibration_manifest),
        "source_calibration_manifest_lock": copy.deepcopy(calibration_lock_audit),
        "source_calibration_report": str(calibration_report),
        "source_calibration_report_sha256": sha256_file(calibration_report),
        "source_calibration_run_root": str(calibration_run_root),
        "source_calibration_run_evidence": calibration_run_evidence,
        "source_calibration_run_evidence_sha256": calibration_run_evidence_sha256,
        "source_calibration_selection_rationale": selection_rationale,
        "source_tree_identity": {
            "project_root": str(project_root),
            "identity_version": source_tree["identity_version"],
            "scope": copy.deepcopy(source_tree["scope"]),
            "sha256": source_tree["sha256"],
            "file_count": source_tree["file_count"],
        },
        "calibration_rows_excluded": CALIBRATION_SAMPLES,
        "calibration_sample_ids_sha256": hashlib.sha256(
            "\n".join(calibration_ids).encode("utf-8")
        ).hexdigest(),
        "eligible_formal_dev_rows": EXPECTED_FORMAL_SPLIT_COUNTS[SELECTION_SPLIT],
        "expected_samples": EXPECTED_CONFIRMATION_SAMPLES,
        "expected_rows": EXPECTED_ROWS,
        "evaluation_seeds": list(EVALUATION_SEEDS),
        "attack_conditions": list(ATTACK_CONDITIONS),
        "selected_manifest_sha256": hashlib.sha256(
            selected_text.encode("utf-8")
        ).hexdigest(),
        "selected_sample_ids_sha256": hashlib.sha256(
            "\n".join(selected_ids).encode("utf-8")
        ).hexdigest(),
        "confirmation_assignment_sha256": _assignment_sha256(selected),
        "selected_unique_sha256": EXPECTED_CONFIRMATION_SAMPLES,
        "selected_unique_source_families": EXPECTED_CONFIRMATION_SAMPLES,
        "selected_dataset_counts": dict(sorted(selected_counts.items())),
        "selected_datasets": sorted(selected_counts),
        **copy.deepcopy(domain_coverage),
        "traditional_attack_artifact_retention": ATTACK_ARTIFACT_RETENTION,
        "required_attack_runtime": copy.deepcopy(REQUIRED_ATTACK_RUNTIME),
        "traditional_attack_implementation": {
            "path": str(attack_path),
            "sha256": sha256_file(attack_path),
        },
        "constraints": copy.deepcopy(CONSTRAINTS),
    }
    if any(sha256_file(path) != digest for path, digest in initial_input_hashes.items()):
        raise ChannelVoteConfirmationBuildError(
            "A frozen formal/calibration input changed during bundle construction."
        )
    _assert_contract_sources_unchanged(config["channel_vote_confirmation"])
    return config, selected


def main() -> int:
    args = parse_args()
    output = Path(args.output).expanduser().resolve()
    manifest_output = Path(args.manifest_output).expanduser().resolve()
    output_lock = manifest_lock_path(manifest_output)
    claim_output = claim_path_for_config(output)
    candidate_runs_root = output.parent / "confirmation-run"
    if any(
        os.path.lexists(path)
        for path in (
            output,
            manifest_output,
            output_lock,
            claim_output,
            candidate_runs_root,
        )
    ):
        raise FileExistsError(
            "Refusing to overwrite an existing channel-vote confirmation bundle."
        )
    config, rows = build_channel_vote_confirmation_bundle(
        Path(args.source),
        calibration_config=Path(args.calibration_config),
        calibration_manifest=Path(args.calibration_manifest),
        calibration_run_root=Path(args.calibration_run_root),
        calibration_report=Path(args.calibration_report),
        output_config=output,
        output_manifest=manifest_output,
        base_url=args.base_url,
    )
    _atomic_write_text(output, yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    source_lock = config["channel_vote_confirmation"]["source_formal_manifest_lock"]
    written_manifest = write_manifest(
        rows,
        manifest_output,
        environ={},
        config_path=output,
        upstream_dataset_locks=source_lock.get("upstream_dataset_locks") or {},
    )
    if sha256_file(written_manifest) != config["channel_vote_confirmation"][
        "selected_manifest_sha256"
    ]:
        raise RuntimeError("Written confirmation manifest differs from its frozen hash.")
    locked_rows, _, lock_audit = _load_locked_manifest(output, written_manifest)
    if len(locked_rows) != EXPECTED_CONFIRMATION_SAMPLES:
        raise RuntimeError("Written confirmation manifest is incomplete.")
    _assert_contract_sources_unchanged(config["channel_vote_confirmation"])
    preregistration_evidence = write_preregistration_claim(
        output,
        expected_run_class=RUN_CLASS,
    )
    print(
        json.dumps(
            {
                "status": "created",
                "schema_version": SCHEMA_VERSION,
                "run_class": RUN_CLASS,
                "development_only": True,
                "paper_eligible": False,
                "formal_test_rows_consumed": FORMAL_TEST_ROWS_CONSUMED,
                "config": str(output),
                "manifest": str(written_manifest),
                "manifest_lock": str(output_lock),
                "manifest_lock_sha256": lock_audit["lock_sha256"],
                "preregistration_claim": preregistration_evidence[
                    "source_claim_path"
                ],
                "preregistration_claim_sha256": preregistration_evidence[
                    "source_claim_sha256"
                ],
                "preregistration_nonce": preregistration_evidence["nonce"],
                "samples": len(locked_rows),
                "expected_rows": EXPECTED_ROWS,
                "candidate": config["channel_vote_confirmation"]["candidate"],
                "selection_rule": SELECTION_RULE,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
