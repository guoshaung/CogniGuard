#!/usr/bin/env python3
"""Freeze a passed 2-of-3 dev confirmation into fresh formal-test inputs.

The freeze never trusts either saved analysis report.  Every invocation first
replays the complete nine-point threshold analysis and the complete disjoint
216-row channel-vote confirmation, then requires canonical whole-object equality
with both saved reports.  The formal test manifest is reproduced byte-for-byte
and receives a fresh adjacent lock bound to the newly selected config.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
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
    _source_tree_identity,
    _source_tree_identity_scope,
)
from scripts.server.analyze_image_watermark_channel_vote_confirmation import (
    REPORT_SCHEMA_VERSION as CONFIRMATION_REPORT_SCHEMA_VERSION,
    ChannelVoteConfirmationError,
    _validated_required_capabilities,
    analyze_channel_vote_confirmation,
)
from scripts.server.analyze_image_watermark_threshold_calibration import (
    REPORT_SCHEMA_VERSION as CALIBRATION_REPORT_SCHEMA_VERSION,
    ThresholdCalibrationError,
    analyze_threshold_calibration,
)
from scripts.server.build_image_watermark_channel_vote_confirmation import (
    CANDIDATE_ID,
    CONFIRMATION_MINIMUM_DOMAINS,
    EXPECTED_CONFIRMATION_SAMPLES,
    EXPECTED_ROWS as EXPECTED_CONFIRMATION_ROWS,
    FORMAL_TEST_ROWS_CONSUMED,
    RUN_CLASS as CONFIRMATION_RUN_CLASS,
    RUN_RELATIVE_PATH,
    SCHEMA_VERSION as CONFIRMATION_CONFIG_SCHEMA_VERSION,
    SELECTION_RULE,
    ChannelVoteConfirmationBuildError,
    _selection_rationale_from_report,
)
from scripts.server.build_image_watermark_threshold_calibration import (
    CONSTRAINTS,
    EVALUATION_SEEDS,
    FROZEN_THRESHOLDS,
    RUN_CLASS as CALIBRATION_RUN_CLASS,
    candidate_id,
    manifest_text,
    sha256_file,
)
from scripts.server.image_watermark_preregistration import (
    RUN_COPY_FILENAME,
    PreregistrationError,
    validate_preregistration_claim,
)


FORMAL_SELECTION_SCHEMA_VERSION = (
    "cogniguard_image_channel_vote_formal_selection_v1"
)
FORMAL_RUN_CLASS = "formal_paper_candidate"
FORMAL_METHOD_ID = "editguard_wrapper"
EXPECTED_FORMAL_SAMPLES = 3000
FLOAT_ABS_TOLERANCE = 1e-12


class ChannelVoteFormalFreezeError(RuntimeError):
    """Raised when the calibration-confirmation chain cannot be frozen safely."""


def _validate_report_preregistration(
    report: Mapping[str, Any],
    *,
    config_path: Path,
    run_class: str,
    candidate_run: Path | None = None,
) -> dict[str, Any]:
    try:
        source_evidence = validate_preregistration_claim(
            config_path,
            expected_run_class=run_class,
        )
        if report.get("preregistration_claim") != source_evidence:
            raise PreregistrationError(
                "report source claim differs from the frozen bundle"
            )
        if candidate_run is not None:
            candidate_evidence = validate_preregistration_claim(
                config_path,
                claim_path=candidate_run / RUN_COPY_FILENAME,
                expected_run_class=run_class,
                expected_nonce=source_evidence["nonce"],
                expected_candidate_run=candidate_run,
            )
            if report.get("candidate_preregistration_claim") != candidate_evidence:
                raise PreregistrationError(
                    "report candidate claim differs from the run-local copy"
                )
    except PreregistrationError as exc:
        raise ChannelVoteFormalFreezeError(
            f"{run_class} preregistration evidence is invalid: {exc}"
        ) from exc
    return source_evidence


def _portable_preregistration_evidence(
    evidence: Mapping[str, Any], *, base: Path
) -> dict[str, Any]:
    return {
        "schema_version": evidence["schema_version"],
        "nonce": evidence["nonce"],
        "claim": _relative_reference(
            Path(str(evidence["source_claim_path"])).resolve(), base=base
        ),
        "claim_sha256": evidence["source_claim_sha256"],
        "config_sha256": evidence["config_sha256"],
        "manifest_sha256": evidence["manifest_sha256"],
        "manifest_lock_sha256": evidence["manifest_lock_sha256"],
        "claim_committed_before_candidate_execution": True,
        "external_append_only_anchor_present": False,
        "evidence_limitation": evidence["evidence_limitation"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze a fully replayed threshold-calibration plus 2-of-3 confirmation "
            "chain into fresh formal inputs."
        )
    )
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--calibration-report", type=Path, required=True)
    parser.add_argument("--calibration-run-root", type=Path, required=True)
    parser.add_argument("--confirmation-report", type=Path, required=True)
    parser.add_argument("--confirmation-run-root", type=Path, required=True)
    parser.add_argument("--output-config", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument(
        "--expected-formal-samples", type=int, default=EXPECTED_FORMAL_SAMPLES
    )
    return parser.parse_args()


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ChannelVoteFormalFreezeError(f"{label} is missing: {path}.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChannelVoteFormalFreezeError(
            f"{label} is not valid JSON: {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ChannelVoteFormalFreezeError(f"{label} must be a JSON object: {path}.")
    return payload


def _read_yaml(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ChannelVoteFormalFreezeError(f"{label} is missing: {path}.")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ChannelVoteFormalFreezeError(
            f"{label} is not valid YAML: {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ChannelVoteFormalFreezeError(f"{label} must be a YAML mapping: {path}.")
    return payload


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _require_sha256(value: Any, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ChannelVoteFormalFreezeError(
            f"{label} must be a lowercase hexadecimal SHA-256."
        )
    return value


def _resolve_file(value: Any, *, label: str, base: Path | None = None) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ChannelVoteFormalFreezeError(f"{label} path is missing.")
    path = Path(value).expanduser()
    if not path.is_absolute() and base is not None:
        path = base / path
    path = path.resolve()
    if not path.is_file():
        raise ChannelVoteFormalFreezeError(f"{label} is missing: {path}.")
    return path


def _resolve_directory(value: Any, *, label: str, base: Path | None = None) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ChannelVoteFormalFreezeError(f"{label} path is missing.")
    path = Path(value).expanduser()
    if not path.is_absolute() and base is not None:
        path = base / path
    path = path.resolve()
    if not path.is_dir():
        raise ChannelVoteFormalFreezeError(f"{label} is missing: {path}.")
    return path


def _relative_reference(target: Path, *, base: Path) -> str:
    try:
        return Path(os.path.relpath(target, start=base)).as_posix()
    except ValueError:
        return str(target)


def _extract_source_tree_identity(
    report: Mapping[str, Any], *, label: str
) -> dict[str, Any]:
    immutable = report.get("immutable_environment_identity")
    if not isinstance(immutable, Mapping):
        raise ChannelVoteFormalFreezeError(
            f"{label} immutable_environment_identity must be a mapping."
        )
    declared_identity_sha256 = _require_sha256(
        report.get("immutable_environment_identity_sha256"),
        label=f"{label} immutable_environment_identity_sha256",
    )
    if _canonical_sha256(dict(immutable)) != declared_identity_sha256:
        raise ChannelVoteFormalFreezeError(
            f"{label} immutable identity SHA-256 does not authenticate its payload."
        )
    identity = {
        "identity_version": immutable.get("source_tree_identity_version"),
        "scope": copy.deepcopy(immutable.get("source_tree_scope")),
        "sha256": immutable.get("source_tree_sha256"),
        "file_count": immutable.get("source_tree_file_count"),
    }
    if identity["identity_version"] != SOURCE_TREE_IDENTITY_VERSION:
        raise ChannelVoteFormalFreezeError(
            f"{label} source-tree identity is not v2."
        )
    if identity["scope"] != _source_tree_identity_scope():
        raise ChannelVoteFormalFreezeError(
            f"{label} source-tree scope differs from the complete v2 scope."
        )
    _require_sha256(identity["sha256"], label=f"{label} source-tree SHA-256")
    if type(identity["file_count"]) is not int or identity["file_count"] <= 0:
        raise ChannelVoteFormalFreezeError(
            f"{label} source-tree file_count must be a positive integer."
        )
    return identity


def _candidate_run_evidence(report: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    candidates = report.get("candidate_metrics")
    if not isinstance(candidates, list) or len(candidates) != len(FROZEN_THRESHOLDS):
        raise ChannelVoteFormalFreezeError(
            "Calibration report does not contain all nine candidate runs."
        )
    fields = (
        "capabilities_sha256",
        "preflight_sha256",
        "environment_sha256",
        "raw_results_sha256",
        "attack_input_hash_map_sha256",
        "immutable_environment_identity_sha256",
        "localization_artifact_evidence_sha256",
    )
    evidence: dict[str, Any] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ChannelVoteFormalFreezeError(
                "Calibration candidate run evidence is malformed."
            )
        candidate_name = str(candidate.get("candidate_id") or "")
        if not candidate_name or candidate_name in evidence:
            raise ChannelVoteFormalFreezeError(
                "Calibration candidate ids are missing or duplicated."
            )
        hashes = {
            field: _require_sha256(
                candidate.get(field), label=f"{candidate_name} {field}"
            )
            for field in fields
        }
        localization_evidence = candidate.get("localization_artifact_evidence")
        localization_rows = (
            localization_evidence.get("rows")
            if isinstance(localization_evidence, Mapping)
            else None
        )
        localization_count = candidate.get("localization_artifact_evidence_count")
        if (
            not isinstance(localization_evidence, Mapping)
            or localization_evidence.get("schema_version")
            != "cogniguard_localization_artifact_evidence_v1"
            or not isinstance(localization_rows, Mapping)
            or type(localization_count) is not int
            or localization_count != candidate.get("rows")
            or localization_evidence.get("count") != localization_count
            or len(localization_rows) != localization_count
            or localization_evidence.get("evidence_sha256")
            != hashes["localization_artifact_evidence_sha256"]
            or _canonical_sha256(dict(localization_rows))
            != hashes["localization_artifact_evidence_sha256"]
        ):
            raise ChannelVoteFormalFreezeError(
                "Calibration candidate localization-artifact evidence is malformed "
                f"or unauthenticated: {candidate_name}."
            )
        evidence[candidate_name] = {
            "run_dir": candidate.get("run_dir"),
            "rows": candidate.get("rows"),
            "localization_artifact_evidence_count": localization_count,
            **hashes,
        }
    return evidence, _canonical_sha256(evidence)


def _confirmation_run_evidence(
    report: Mapping[str, Any]
) -> tuple[dict[str, Any], str]:
    hash_fields = (
        "capabilities_sha256",
        "preflight_sha256",
        "environment_sha256",
        "raw_results_sha256",
        "attack_input_hash_map_sha256",
        "immutable_environment_identity_sha256",
    )
    evidence: dict[str, Any] = {
        "run_dir": report.get("run_dir"),
        "rows": report.get("rows"),
        "samples": report.get("samples"),
    }
    for field in hash_fields:
        evidence[field] = _require_sha256(
            report.get(field), label=f"Confirmation {field}"
        )
    raw_votes = report.get("raw_localization_vote_artifacts")
    if (
        not isinstance(raw_votes, Mapping)
        or raw_votes.get("count") != EXPECTED_CONFIRMATION_ROWS
        or raw_votes.get("threshold") != 510
        or raw_votes.get("dtype") != "uint16"
        or raw_votes.get("encoding") != "lossless_png_16bit_grayscale_I;16"
        or raw_votes.get("allowed_values") != [0, 255, 510, 765]
    ):
        raise ChannelVoteFormalFreezeError(
            "Confirmation raw localization-vote evidence is incomplete."
        )
    evidence["raw_localization_vote_artifacts"] = copy.deepcopy(dict(raw_votes))
    _require_sha256(
        raw_votes.get("evidence_sha256"),
        label="Confirmation raw localization-vote evidence",
    )
    return evidence, _canonical_sha256(evidence)


def _validate_cross_run_invariants(
    calibration_report: Mapping[str, Any],
    confirmation_report: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    calibration_identity = calibration_report.get("immutable_environment_identity")
    confirmation_identity = confirmation_report.get("immutable_environment_identity")
    if not isinstance(calibration_identity, Mapping) or not isinstance(
        confirmation_identity, Mapping
    ):
        raise ChannelVoteFormalFreezeError(
            "Calibration/confirmation immutable environment identities are missing."
        )
    common_fields = (
        "python",
        "platform",
        "packages",
        "gpu",
        "checkpoints",
        "git_commit",
        "git_status_sha256",
        "source_tree_identity_version",
        "source_tree_scope",
        "source_tree_sha256",
        "source_tree_file_count",
        "resolved_dataset_roots",
        "dataset_manifest_override_used",
        "dataset_roots_override_used",
        "registry_secret_recorded",
        "methods",
        "strict_paper_mode",
        "paper_eligible",
        "evaluation_split",
        "traditional_attack_runtime",
        "deterministic_runtime_identity",
        "asset_manifest_identity",
        "aigc_attack_runtime_identity",
        "registry_secret_identity_fingerprint",
    )
    missing = [
        field
        for field in common_fields
        if field not in calibration_identity or field not in confirmation_identity
    ]
    if missing:
        raise ChannelVoteFormalFreezeError(
            "Cross-run immutable identity omits required fields: " + ", ".join(missing)
        )
    mismatches = {
        field: {
            "calibration": calibration_identity[field],
            "confirmation": confirmation_identity[field],
        }
        for field in common_fields
        if calibration_identity[field] != confirmation_identity[field]
    }
    if mismatches:
        raise ChannelVoteFormalFreezeError(
            f"Calibration/confirmation immutable runtime invariants drifted: {mismatches}."
        )
    if (
        calibration_identity.get("registry_secret_recorded") is not False
        or calibration_identity.get("dataset_manifest_override_used") is not False
        or calibration_identity.get("dataset_roots_override_used") is not False
    ):
        raise ChannelVoteFormalFreezeError(
            "Cross-run evidence used an input override or recorded registry secret."
        )
    calibration_caps = calibration_identity.get("fixed_capabilities")
    confirmation_caps = confirmation_identity.get("fixed_capabilities")
    if not isinstance(calibration_caps, Mapping) or not isinstance(
        confirmation_caps, Mapping
    ):
        raise ChannelVoteFormalFreezeError(
            "Cross-run fixed service capabilities are missing."
        )
    expected_variable = {"localization_channel_vote_min"}
    calibration_stable_caps = {
        key: value
        for key, value in calibration_caps.items()
        if key not in expected_variable
    }
    confirmation_stable_caps = {
        key: value
        for key, value in confirmation_caps.items()
        if key not in expected_variable
    }
    if calibration_stable_caps != confirmation_stable_caps:
        raise ChannelVoteFormalFreezeError(
            "Fixed service capabilities drifted beyond localization_channel_vote_min."
        )
    if (
        calibration_caps.get("localization_channel_vote_min") != 1
        or confirmation_caps.get("localization_channel_vote_min") != 2
    ):
        raise ChannelVoteFormalFreezeError(
            "Calibration/confirmation channel vote minima are not the expected 1 then 2."
        )
    evidence = {
        "common_environment": {
            field: copy.deepcopy(calibration_identity[field]) for field in common_fields
        },
        "stable_fixed_capabilities": copy.deepcopy(calibration_stable_caps),
        "expected_capability_difference": {
            "field": "localization_channel_vote_min",
            "calibration": 1,
            "confirmation": 2,
        },
        "excluded_expected_identity_differences": [
            "config_path",
            "config_sha256",
            "manifest_path",
            "manifest_sha256",
            "run_class",
            "input_manifest_audit",
            "manifest_lock",
        ],
    }
    return evidence, _canonical_sha256(evidence)


def _validate_calibration_protocol(report: Mapping[str, Any]) -> dict[str, Any]:
    if (
        report.get("schema_version") != CALIBRATION_REPORT_SCHEMA_VERSION
        or report.get("status") != "no_candidate_satisfies_constraints"
        or report.get("winner") is not None
        or report.get("eligible_candidate_ids") != []
        or report.get("development_only") is not True
        or report.get("paper_eligible") is not False
        or report.get("selection_split") != "dev"
        or report.get("excluded_splits") != ["train", "test"]
        or report.get("formal_test_rows_consumed") != FORMAL_TEST_ROWS_CONSUMED
        or report.get("formal_config_update_performed") is not False
        or report.get("evaluation_seeds") != list(EVALUATION_SEEDS)
        or report.get("constraints") != CONSTRAINTS
    ):
        raise ChannelVoteFormalFreezeError(
            "Calibration report is not the frozen no-winner, dev-only protocol."
        )
    try:
        rationale = _selection_rationale_from_report(dict(report))
    except (ChannelVoteConfirmationBuildError, TypeError, ValueError) as exc:
        raise ChannelVoteFormalFreezeError(
            "Calibration does not prove the amended 0.34/0.36 tie profile and "
            f"mechanism-eligibility rationale: {exc}"
        ) from exc
    if (
        rationale.get("source_candidate_id") != candidate_id(0.34)
        or rationale.get("constraints_passed") != 11
        or rationale.get("constraints_total") != 12
        or rationale.get("sole_failed_constraint") != "clean_max_mask_fpr"
    ):
        raise ChannelVoteFormalFreezeError(
            "Calibration 0.34 rationale differs from the preregistration."
        )
    return rationale


def _validate_confirmation_protocol(
    report: Mapping[str, Any],
    *,
    confirmation_config: Path,
    confirmation_run_root: Path,
) -> dict[str, Any]:
    try:
        required_capabilities = _validated_required_capabilities(
            report.get("required_capabilities")
        )
    except ChannelVoteConfirmationError as exc:
        raise ChannelVoteFormalFreezeError(str(exc)) from exc
    domain_coverage = report.get("domain_coverage")
    if not isinstance(domain_coverage, Mapping):
        raise ChannelVoteFormalFreezeError(
            "Confirmation report has no authenticated domain-coverage evidence."
        )
    source_minimum = domain_coverage.get("source_formal_minimum_domains")
    confirmation_minimum = domain_coverage.get("confirmation_minimum_domains")
    effective_minimum = domain_coverage.get("effective_minimum_domains")
    selected_count = domain_coverage.get("selected_domain_count")
    selected_domains = domain_coverage.get("selected_domains")
    if (
        set(domain_coverage)
        != {
            "source_formal_minimum_domains",
            "confirmation_minimum_domains",
            "effective_minimum_domains",
            "selected_domain_count",
            "selected_domains",
        }
        or type(source_minimum) is not int
        or source_minimum < 1
        or type(confirmation_minimum) is not int
        or confirmation_minimum != CONFIRMATION_MINIMUM_DOMAINS
        or type(effective_minimum) is not int
        or effective_minimum != max(source_minimum, CONFIRMATION_MINIMUM_DOMAINS)
        or type(selected_count) is not int
        or not isinstance(selected_domains, list)
        or any(
            type(domain) is not str or not domain.strip()
            for domain in selected_domains
        )
        or selected_domains != sorted(set(selected_domains))
        or selected_count != len(selected_domains)
        or selected_count < effective_minimum
    ):
        raise ChannelVoteFormalFreezeError(
            "Confirmation report domain-coverage evidence is inconsistent."
        )
    if (
        report.get("schema_version") != CONFIRMATION_REPORT_SCHEMA_VERSION
        or report.get("status") != "confirmation_passed"
        or report.get("confirmation_passed") is not True
        or report.get("all_constraints_passed") is not True
        or report.get("development_only") is not True
        or report.get("paper_eligible") is not False
        or report.get("selection_split") != "dev"
        or report.get("excluded_splits") != ["train", "test"]
        or report.get("formal_test_rows_consumed") != FORMAL_TEST_ROWS_CONSUMED
        or report.get("parameter_selection_performed") is not False
        or report.get("fallback_candidate_considered") is not False
        or report.get("decision") != "pass"
        or report.get("selection_rule") != SELECTION_RULE
        or report.get("samples") != EXPECTED_CONFIRMATION_SAMPLES
        or report.get("rows") != EXPECTED_CONFIRMATION_ROWS
        or report.get("evaluation_seeds") != list(EVALUATION_SEEDS)
        or report.get("constraints") != CONSTRAINTS
    ):
        raise ChannelVoteFormalFreezeError(
            "Confirmation report is not the passed, test-unconsumed, sole-candidate protocol."
        )
    expected_candidate = {
        "candidate_id": CANDIDATE_ID,
        **copy.deepcopy(required_capabilities),
        "run_relative_path": RUN_RELATIVE_PATH,
    }
    if report.get("candidate") != expected_candidate:
        raise ChannelVoteFormalFreezeError(
            "Confirmation report candidate differs from fixed tau=0.34, k=2."
        )
    checks = report.get("constraint_checks")
    if (
        not isinstance(checks, list)
        or len(checks) != 12
        or not all(isinstance(row, Mapping) and row.get("passed") is True for row in checks)
    ):
        raise ChannelVoteFormalFreezeError(
            "Confirmation report does not pass all twelve frozen constraints."
        )
    if Path(str(report.get("config") or "")).resolve() != confirmation_config:
        raise ChannelVoteFormalFreezeError(
            "Confirmation report config path differs from the replayed config."
        )
    if sha256_file(confirmation_config) != report.get("config_sha256"):
        raise ChannelVoteFormalFreezeError(
            "Confirmation config SHA-256 differs from its report."
        )
    expected_run_dir = (confirmation_run_root / RUN_RELATIVE_PATH).resolve()
    if Path(str(report.get("run_dir") or "")).resolve() != expected_run_dir:
        raise ChannelVoteFormalFreezeError(
            "Confirmation report run directory differs from the supplied run root."
        )
    return expected_candidate


def _rerun_saved_reports(
    *,
    calibration_report: Path,
    calibration_run_root: Path,
    confirmation_report: Path,
    confirmation_run_root: Path,
) -> dict[str, Any]:
    calibration_report_sha256 = sha256_file(calibration_report)
    confirmation_report_sha256 = sha256_file(confirmation_report)
    stored_calibration = _read_json(
        calibration_report, label="Threshold-calibration report"
    )
    stored_confirmation = _read_json(
        confirmation_report, label="Channel-vote confirmation report"
    )
    calibration_config = _resolve_file(
        stored_calibration.get("config"), label="Calibration config"
    )
    confirmation_config = _resolve_file(
        stored_confirmation.get("config"), label="Confirmation config"
    )
    if not calibration_run_root.is_dir():
        raise ChannelVoteFormalFreezeError(
            f"Calibration run root is missing: {calibration_run_root}."
        )
    if not confirmation_run_root.is_dir():
        raise ChannelVoteFormalFreezeError(
            f"Confirmation run root is missing: {confirmation_run_root}."
        )
    try:
        recomputed_calibration = analyze_threshold_calibration(
            calibration_config,
            run_root=calibration_run_root,
        )
    except (OSError, ThresholdCalibrationError, TypeError, ValueError) as exc:
        raise ChannelVoteFormalFreezeError(
            f"Calibration candidate runs failed complete independent reanalysis: {exc}"
        ) from exc
    if _canonical_json(stored_calibration) != _canonical_json(recomputed_calibration):
        raise ChannelVoteFormalFreezeError(
            "Saved calibration report differs from complete candidate-run reanalysis."
        )
    try:
        recomputed_confirmation = analyze_channel_vote_confirmation(
            confirmation_config,
            run_root=confirmation_run_root,
        )
    except (OSError, ChannelVoteConfirmationError, TypeError, ValueError) as exc:
        raise ChannelVoteFormalFreezeError(
            f"Confirmation run failed complete independent reanalysis: {exc}"
        ) from exc
    if _canonical_json(stored_confirmation) != _canonical_json(
        recomputed_confirmation
    ):
        raise ChannelVoteFormalFreezeError(
            "Saved confirmation report differs from complete raw-artifact reanalysis."
        )
    if (
        sha256_file(calibration_report) != calibration_report_sha256
        or sha256_file(confirmation_report) != confirmation_report_sha256
    ):
        raise ChannelVoteFormalFreezeError(
            "An analysis report changed during complete reanalysis."
        )
    calibration_rationale = _validate_calibration_protocol(stored_calibration)
    confirmation_candidate = _validate_confirmation_protocol(
        stored_confirmation,
        confirmation_config=confirmation_config,
        confirmation_run_root=confirmation_run_root,
    )
    calibration_preregistration = _validate_report_preregistration(
        stored_calibration,
        config_path=calibration_config,
        run_class=CALIBRATION_RUN_CLASS,
    )
    confirmation_preregistration = _validate_report_preregistration(
        stored_confirmation,
        config_path=confirmation_config,
        run_class=CONFIRMATION_RUN_CLASS,
        candidate_run=(confirmation_run_root / RUN_RELATIVE_PATH).resolve(),
    )
    return {
        "calibration_report": stored_calibration,
        "calibration_report_path": calibration_report,
        "calibration_report_sha256": calibration_report_sha256,
        "calibration_config": calibration_config,
        "calibration_rationale": calibration_rationale,
        "calibration_preregistration": calibration_preregistration,
        "confirmation_report": stored_confirmation,
        "confirmation_report_path": confirmation_report,
        "confirmation_report_sha256": confirmation_report_sha256,
        "confirmation_config": confirmation_config,
        "confirmation_candidate": confirmation_candidate,
        "confirmation_preregistration": confirmation_preregistration,
    }


def _validate_source_formal_bundle(
    source_config: Path, *, expected_formal_samples: int
) -> tuple[dict[str, Any], Path, list[Any], dict[str, Any]]:
    source_payload = _read_yaml(source_config, label="Source formal config")
    experiment = source_payload.get("experiment")
    manifest = source_payload.get("manifest")
    requirements = source_payload.get("data_requirements")
    if (
        not isinstance(experiment, Mapping)
        or experiment.get("strict_paper_mode") is not True
        or experiment.get("fail_fast") is not True
        or experiment.get("split") != "test"
        or int(experiment.get("max_samples", 0) or 0) != 0
        or not isinstance(manifest, Mapping)
        or manifest.get("verify_hashes") is not True
        or manifest.get("require_lock") is not True
        or not isinstance(requirements, Mapping)
        or requirements.get("expected_total_samples") != expected_formal_samples
        or requirements.get("required_evaluation_split") != "test"
        or requirements.get("require_max_samples_zero") is not True
        or "formal_selection" in source_payload
    ):
        raise ChannelVoteFormalFreezeError(
            "Source config is not the exact unselected, locked formal-test configuration."
        )
    source_manifest = manifest_path_from_config(source_config, environ={}).resolve()
    roots = dataset_roots_from_config(source_config, environ={})
    try:
        rows = load_manifest(
            source_manifest,
            dataset_roots=roots,
            require_files=True,
            verify_hashes=True,
        )
        lock_audit = validate_manifest_lock(
            source_manifest,
            rows,
            config_path=source_config,
            dataset_roots=roots,
        )
    except (OSError, TypeError, ValueError) as exc:
        raise ChannelVoteFormalFreezeError(
            f"Source formal manifest/lock failed strict validation: {exc}"
        ) from exc
    if len(rows) != expected_formal_samples or lock_audit.get(
        "total_samples"
    ) != expected_formal_samples:
        raise ChannelVoteFormalFreezeError(
            f"Source formal data has {len(rows)} rows; expected {expected_formal_samples}."
        )
    return source_payload, source_manifest, rows, lock_audit


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


def _build_selected_payload(
    source_payload: Mapping[str, Any],
    *,
    source_config: Path,
    source_manifest: Path,
    source_lock: Mapping[str, Any],
    output_config: Path,
    output_manifest: Path,
    chain: Mapping[str, Any],
) -> dict[str, Any]:
    selected = copy.deepcopy(dict(source_payload))
    confirmation_report = chain["confirmation_report"]
    try:
        required_capabilities = _validated_required_capabilities(
            confirmation_report.get("required_capabilities")
        )
    except ChannelVoteConfirmationError as exc:
        raise ChannelVoteFormalFreezeError(str(exc)) from exc
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
    methods = [
        row
        for row in (selected.get("methods") or [])
        if isinstance(row, dict)
        and row.get("enabled", True)
        and row.get("id") == FORMAL_METHOD_ID
    ]
    if len(methods) != 1:
        raise ChannelVoteFormalFreezeError(
            "Source config must enable exactly one editguard_wrapper method."
        )
    if "required_capabilities" in methods[0]:
        raise ChannelVoteFormalFreezeError(
            "Source editguard_wrapper already declares required_capabilities."
        )
    methods[0]["required_capabilities"] = copy.deepcopy(required_capabilities)

    calibration_report = chain["calibration_report"]
    confirmation_contract = chain["confirmation_contract"]
    calibration_run_evidence, calibration_run_evidence_sha256 = (
        _candidate_run_evidence(calibration_report)
    )
    confirmation_run_evidence, confirmation_run_evidence_sha256 = (
        _confirmation_run_evidence(confirmation_report)
    )
    calibration_selected_lock = calibration_report["selected_manifest_lock"]
    confirmation_lock = confirmation_report["manifest_lock"]
    selected["formal_selection"] = {
        "schema_version": FORMAL_SELECTION_SCHEMA_VERSION,
        "status": "frozen",
        "method_id": FORMAL_METHOD_ID,
        "selection_source": "development_only_channel_vote_confirmation",
        "selection_split": "dev",
        "excluded_splits": ["train", "test"],
        "formal_test_rows_consumed": FORMAL_TEST_ROWS_CONSUMED,
        "formal_parameter_selection_performed": False,
        "selected_parameters": copy.deepcopy(required_capabilities),
        "decision_rule": (
            "publish the sole preregistered tau=0.34,k=2 candidate only after all "
            "twelve confirmation constraints pass on the disjoint 216-row dev complement"
        ),
        "source_tree_identity": copy.deepcopy(chain["source_tree_identity"]),
        "calibration_source_tree_identity_version": chain[
            "source_tree_identity"
        ]["identity_version"],
        "calibration_source_tree_scope": copy.deepcopy(
            chain["source_tree_identity"]["scope"]
        ),
        "calibration_source_tree_sha256": chain["source_tree_identity"]["sha256"],
        "calibration_source_tree_file_count": chain["source_tree_identity"][
            "file_count"
        ],
        "cross_run_invariant_evidence": copy.deepcopy(
            chain["cross_run_invariant_evidence"]
        ),
        "cross_run_invariant_evidence_sha256": chain[
            "cross_run_invariant_evidence_sha256"
        ],
        "source_formal": {
            "config": _relative_reference(source_config, base=output_config.parent),
            "config_sha256": sha256_file(source_config),
            "manifest": _relative_reference(
                source_manifest, base=output_config.parent
            ),
            "manifest_sha256": sha256_file(source_manifest),
            "manifest_lock": _relative_reference(
                Path(str(source_lock["lock_path"])).resolve(),
                base=output_config.parent,
            ),
            "manifest_lock_sha256": source_lock["lock_sha256"],
            "assignment_sha256": source_lock["assignment_sha256"],
            "formal_split_assignment_audit": copy.deepcopy(
                chain["formal_split_assignment_audit"]
            ),
        },
        "calibration": {
            "config": _relative_reference(
                chain["calibration_config"], base=output_config.parent
            ),
            "config_sha256": calibration_report["config_sha256"],
            "report": _relative_reference(
                chain["calibration_report_path"], base=output_config.parent
            ),
            "report_sha256": chain["calibration_report_sha256"],
            "report_schema_version": CALIBRATION_REPORT_SCHEMA_VERSION,
            "run_root": _relative_reference(
                chain["calibration_run_root"], base=output_config.parent
            ),
            "run_evidence": calibration_run_evidence,
            "run_evidence_sha256": calibration_run_evidence_sha256,
            "preregistration": _portable_preregistration_evidence(
                chain["calibration_preregistration"], base=output_config.parent
            ),
            "selected_manifest": _relative_reference(
                Path(str(calibration_report["selected_manifest"])).resolve(),
                base=output_config.parent,
            ),
            "selected_manifest_sha256": calibration_report[
                "selected_manifest_sha256"
            ],
            "selected_manifest_lock": _relative_reference(
                Path(str(calibration_selected_lock["lock_path"])).resolve(),
                base=output_config.parent,
            ),
            "selected_manifest_lock_sha256": calibration_selected_lock[
                "lock_sha256"
            ],
            "outcome": "no_candidate_satisfies_constraints",
            "tau_0p34_rationale": copy.deepcopy(chain["calibration_rationale"]),
        },
        "confirmation": {
            "config": _relative_reference(
                chain["confirmation_config"], base=output_config.parent
            ),
            "config_sha256": confirmation_report["config_sha256"],
            "config_schema_version": CONFIRMATION_CONFIG_SCHEMA_VERSION,
            "report": _relative_reference(
                chain["confirmation_report_path"], base=output_config.parent
            ),
            "report_sha256": chain["confirmation_report_sha256"],
            "report_schema_version": CONFIRMATION_REPORT_SCHEMA_VERSION,
            "run_root": _relative_reference(
                chain["confirmation_run_root"], base=output_config.parent
            ),
            "run_evidence": confirmation_run_evidence,
            "run_evidence_sha256": confirmation_run_evidence_sha256,
            "preregistration": _portable_preregistration_evidence(
                chain["confirmation_preregistration"], base=output_config.parent
            ),
            "selected_manifest": _relative_reference(
                Path(str(confirmation_report["manifest"])).resolve(),
                base=output_config.parent,
            ),
            "selected_manifest_sha256": confirmation_report["manifest_sha256"],
            "selected_manifest_lock": _relative_reference(
                Path(str(confirmation_lock["lock_path"])).resolve(),
                base=output_config.parent,
            ),
            "selected_manifest_lock_sha256": confirmation_lock["lock_sha256"],
            "complement_samples": EXPECTED_CONFIRMATION_SAMPLES,
            "complement_assignment_sha256": confirmation_contract[
                "confirmation_assignment_sha256"
            ],
            "calibration_rows_excluded": confirmation_contract[
                "calibration_rows_excluded"
            ],
            "calibration_sample_ids_sha256": confirmation_contract[
                "calibration_sample_ids_sha256"
            ],
            "domain_coverage": copy.deepcopy(
                confirmation_report["domain_coverage"]
            ),
            "raw_localization_vote_evidence_sha256": confirmation_report[
                "raw_localization_vote_artifacts"
            ]["evidence_sha256"],
            "outcome": "confirmation_passed",
        },
    }
    return selected


def _prepare_chain(
    source_config: Path,
    *,
    calibration_report: Path,
    calibration_run_root: Path,
    confirmation_report: Path,
    confirmation_run_root: Path,
    output_config: Path,
    output_manifest: Path,
    expected_formal_samples: int,
) -> dict[str, Any]:
    if expected_formal_samples <= 0:
        raise ValueError("expected_formal_samples must be positive.")
    source_payload, source_manifest, source_rows, source_lock = (
        _validate_source_formal_bundle(
            source_config, expected_formal_samples=expected_formal_samples
        )
    )
    chain = _rerun_saved_reports(
        calibration_report=calibration_report,
        calibration_run_root=calibration_run_root,
        confirmation_report=confirmation_report,
        confirmation_run_root=confirmation_run_root,
    )
    calibration_payload = chain["calibration_report"]
    confirmation_payload = chain["confirmation_report"]
    confirmation_config_payload = _read_yaml(
        chain["confirmation_config"], label="Confirmation config"
    )
    confirmation_contract = confirmation_config_payload.get(
        "channel_vote_confirmation"
    )
    if not isinstance(confirmation_contract, Mapping):
        raise ChannelVoteFormalFreezeError(
            "Confirmation config has no channel_vote_confirmation contract."
        )
    domain_fields = (
        "source_formal_minimum_domains",
        "confirmation_minimum_domains",
        "effective_minimum_domains",
        "selected_domain_count",
        "selected_domains",
    )
    contract_domain_coverage = {
        field: copy.deepcopy(confirmation_contract.get(field))
        for field in domain_fields
    }
    if (
        confirmation_payload.get("domain_coverage") != contract_domain_coverage
        or (confirmation_config_payload.get("data_requirements") or {}).get(
            "minimum_domains"
        )
        != contract_domain_coverage["effective_minimum_domains"]
        or (source_payload.get("data_requirements") or {}).get("minimum_domains")
        != contract_domain_coverage["source_formal_minimum_domains"]
    ):
        raise ChannelVoteFormalFreezeError(
            "Confirmation domain coverage is not bound across source, config, and report."
        )
    calibration_formal = calibration_payload.get("formal_inputs")
    if not isinstance(calibration_formal, Mapping):
        raise ChannelVoteFormalFreezeError(
            "Calibration report formal_inputs are missing."
        )
    if (
        Path(str(calibration_formal.get("config") or "")).resolve()
        != source_config
        or calibration_formal.get("config_sha256") != sha256_file(source_config)
        or Path(str(calibration_formal.get("manifest") or "")).resolve()
        != source_manifest
        or calibration_formal.get("manifest_sha256")
        != sha256_file(source_manifest)
        or calibration_formal.get("manifest_lock") != source_lock
    ):
        raise ChannelVoteFormalFreezeError(
            "Calibration report is not bound to the supplied formal source."
        )
    if (
        Path(str(confirmation_contract.get("source_formal_config") or "")).resolve()
        != source_config
        or confirmation_contract.get("source_formal_config_sha256")
        != sha256_file(source_config)
        or Path(
            str(confirmation_contract.get("source_formal_manifest") or "")
        ).resolve()
        != source_manifest
        or confirmation_contract.get("source_formal_manifest_sha256")
        != sha256_file(source_manifest)
        or confirmation_contract.get("source_formal_manifest_lock") != source_lock
    ):
        raise ChannelVoteFormalFreezeError(
            "Confirmation config is not bound to the same formal source."
        )
    if (
        Path(
            str(confirmation_contract.get("source_calibration_config") or "")
        ).resolve()
        != chain["calibration_config"]
        or confirmation_contract.get("source_calibration_config_sha256")
        != calibration_payload.get("config_sha256")
        or Path(
            str(confirmation_contract.get("source_calibration_manifest") or "")
        ).resolve()
        != Path(str(calibration_payload.get("selected_manifest") or "")).resolve()
        or confirmation_contract.get("source_calibration_manifest_sha256")
        != calibration_payload.get("selected_manifest_sha256")
        or confirmation_contract.get("source_calibration_manifest_lock")
        != calibration_payload.get("selected_manifest_lock")
        or Path(
            str(confirmation_contract.get("source_calibration_report") or "")
        ).resolve()
        != calibration_report
        or confirmation_contract.get("source_calibration_report_sha256")
        != chain["calibration_report_sha256"]
        or Path(
            str(confirmation_contract.get("source_calibration_run_root") or "")
        ).resolve()
        != calibration_run_root
    ):
        raise ChannelVoteFormalFreezeError(
            "Confirmation did not consume this exact calibration report/run root."
        )
    expected_calibration_evidence, expected_calibration_evidence_sha256 = (
        _candidate_run_evidence(calibration_payload)
    )
    if (
        confirmation_contract.get("source_calibration_run_evidence")
        != expected_calibration_evidence
        or confirmation_contract.get("source_calibration_run_evidence_sha256")
        != expected_calibration_evidence_sha256
        or confirmation_contract.get("source_calibration_selection_rationale")
        != chain["calibration_rationale"]
    ):
        raise ChannelVoteFormalFreezeError(
            "Confirmation calibration run hashes/rationale differ from full reanalysis."
        )
    formal_split_audit = calibration_payload.get("formal_split_assignment_audit")
    if (
        not isinstance(formal_split_audit, Mapping)
        or confirmation_contract.get("formal_split_assignment_audit")
        != formal_split_audit
    ):
        raise ChannelVoteFormalFreezeError(
            "Calibration and confirmation formal split assignments differ."
        )
    calibration_tree = _extract_source_tree_identity(
        calibration_payload, label="Calibration"
    )
    confirmation_tree = _extract_source_tree_identity(
        confirmation_payload, label="Confirmation"
    )
    if confirmation_tree != calibration_tree:
        raise ChannelVoteFormalFreezeError(
            "Calibration and confirmation source-tree identities are not identical."
        )
    current_tree = _source_tree_identity(Path(__file__).resolve().parents[2])
    if current_tree != calibration_tree:
        raise ChannelVoteFormalFreezeError(
            "Current complete v2 source tree differs from the analyzed runs."
        )
    expected_confirmation_tree_contract = {
        "project_root": str(Path(__file__).resolve().parents[2]),
        **copy.deepcopy(calibration_tree),
    }
    if confirmation_contract.get("source_tree_identity") != (
        expected_confirmation_tree_contract
    ):
        raise ChannelVoteFormalFreezeError(
            "Confirmation config does not bind the complete analyzed v2 source tree."
        )
    cross_run_invariants, cross_run_invariants_sha256 = (
        _validate_cross_run_invariants(calibration_payload, confirmation_payload)
    )
    confirmation_source_evidence = confirmation_payload.get("source_evidence")
    if (
        not isinstance(confirmation_source_evidence, Mapping)
        or confirmation_source_evidence.get("formal_manifest_lock") != source_lock
        or confirmation_source_evidence.get("calibration_manifest_lock")
        != calibration_payload.get("selected_manifest_lock")
        or confirmation_source_evidence.get("calibration_report_sha256")
        != chain["calibration_report_sha256"]
        or confirmation_source_evidence.get("calibration_run_evidence_sha256")
        != expected_calibration_evidence_sha256
        or confirmation_source_evidence.get("formal_split_assignment_audit")
        != formal_split_audit
        or confirmation_source_evidence.get("source_tree_identity")
        != expected_confirmation_tree_contract
    ):
        raise ChannelVoteFormalFreezeError(
            "Confirmation report source evidence differs from the common formal source."
        )
    chain.update(
        {
            "source_payload": source_payload,
            "source_manifest": source_manifest,
            "source_rows": source_rows,
            "source_lock": source_lock,
            "source_tree_identity": calibration_tree,
            "formal_split_assignment_audit": copy.deepcopy(dict(formal_split_audit)),
            "confirmation_contract": dict(confirmation_contract),
            "cross_run_invariant_evidence": cross_run_invariants,
            "cross_run_invariant_evidence_sha256": (
                cross_run_invariants_sha256
            ),
            "calibration_run_root": calibration_run_root,
            "confirmation_run_root": confirmation_run_root,
        }
    )
    selected_payload = _build_selected_payload(
        source_payload,
        source_config=source_config,
        source_manifest=source_manifest,
        source_lock=source_lock,
        output_config=output_config,
        output_manifest=output_manifest,
        chain=chain,
    )
    chain["selected_payload"] = selected_payload
    return chain


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
            "Refusing to overwrite channel-vote formal outputs: "
            + ", ".join(str(path) for path in collisions)
        )
    if len({output_config, output_manifest, output_lock}) != 3:
        raise ChannelVoteFormalFreezeError(
            "Selected config, manifest, and lock paths must differ."
        )


def _assert_lock_invariants(
    source_lock: Mapping[str, Any],
    selected_lock: Mapping[str, Any],
    *,
    output_config: Path,
    output_manifest: Path,
) -> None:
    fields = (
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
        field: {"source": source_lock.get(field), "selected": selected_lock.get(field)}
        for field in fields
        if source_lock.get(field) != selected_lock.get(field)
    }
    if mismatches:
        raise ChannelVoteFormalFreezeError(
            f"Selected lock changed frozen formal data evidence: {mismatches}."
        )
    if selected_lock.get("manifest_filename") != output_manifest.name:
        raise ChannelVoteFormalFreezeError(
            "Selected lock manifest_filename is incorrect."
        )
    if selected_lock.get("config_sha256") != sha256_file(output_config):
        raise ChannelVoteFormalFreezeError(
            "Selected lock does not bind the selected config."
        )


def _validate_selected_manifest(
    selected_config: Path,
    *,
    source_manifest: Path,
    source_lock: Mapping[str, Any],
    expected_formal_samples: int,
) -> tuple[Path, dict[str, Any]]:
    selected_manifest = manifest_path_from_config(selected_config, environ={}).resolve()
    roots = dataset_roots_from_config(selected_config, environ={})
    try:
        rows = load_manifest(
            selected_manifest,
            dataset_roots=roots,
            require_files=True,
            verify_hashes=True,
        )
        lock_audit = validate_manifest_lock(
            selected_manifest,
            rows,
            config_path=selected_config,
            dataset_roots=roots,
        )
    except (OSError, TypeError, ValueError) as exc:
        raise ChannelVoteFormalFreezeError(
            f"Selected formal manifest/lock failed strict validation: {exc}"
        ) from exc
    if len(rows) != expected_formal_samples:
        raise ChannelVoteFormalFreezeError(
            f"Selected formal manifest has {len(rows)} rows; expected {expected_formal_samples}."
        )
    if selected_manifest.read_bytes() != source_manifest.read_bytes():
        raise ChannelVoteFormalFreezeError(
            "Selected formal manifest is not byte-equivalent to the source manifest."
        )
    _assert_lock_invariants(
        source_lock,
        lock_audit,
        output_config=selected_config,
        output_manifest=selected_manifest,
    )
    return selected_manifest, lock_audit


def validate_frozen_channel_vote_formal_config(
    selected_config: Path,
    *,
    expected_formal_samples: int = EXPECTED_FORMAL_SAMPLES,
) -> dict[str, Any]:
    selected_config = selected_config.expanduser().resolve()
    selected_payload = _read_yaml(selected_config, label="Selected formal config")
    selection = selected_payload.get("formal_selection")
    if not isinstance(selection, Mapping) or selection.get(
        "schema_version"
    ) != FORMAL_SELECTION_SCHEMA_VERSION:
        raise ChannelVoteFormalFreezeError(
            "Selected config has no supported channel-vote formal_selection."
        )
    source_section = selection.get("source_formal")
    calibration_section = selection.get("calibration")
    confirmation_section = selection.get("confirmation")
    if not all(
        isinstance(section, Mapping)
        for section in (source_section, calibration_section, confirmation_section)
    ):
        raise ChannelVoteFormalFreezeError(
            "Selected config formal evidence sections are incomplete."
        )
    source_config = _resolve_file(
        source_section.get("config"),
        label="Selected source formal config",
        base=selected_config.parent,
    )
    calibration_report = _resolve_file(
        calibration_section.get("report"),
        label="Selected calibration report",
        base=selected_config.parent,
    )
    calibration_run_root = _resolve_directory(
        calibration_section.get("run_root"),
        label="Selected calibration run root",
        base=selected_config.parent,
    )
    confirmation_report = _resolve_file(
        confirmation_section.get("report"),
        label="Selected confirmation report",
        base=selected_config.parent,
    )
    confirmation_run_root = _resolve_directory(
        confirmation_section.get("run_root"),
        label="Selected confirmation run root",
        base=selected_config.parent,
    )
    selected_manifest = manifest_path_from_config(selected_config, environ={}).resolve()
    chain = _prepare_chain(
        source_config,
        calibration_report=calibration_report,
        calibration_run_root=calibration_run_root,
        confirmation_report=confirmation_report,
        confirmation_run_root=confirmation_run_root,
        output_config=selected_config,
        output_manifest=selected_manifest,
        expected_formal_samples=expected_formal_samples,
    )
    if _canonical_json(selected_payload) != _canonical_json(chain["selected_payload"]):
        raise ChannelVoteFormalFreezeError(
            "Selected formal config differs from the deterministic confirmation freeze product."
        )
    _validate_selected_manifest(
        selected_config,
        source_manifest=chain["source_manifest"],
        source_lock=chain["source_lock"],
        expected_formal_samples=expected_formal_samples,
    )
    try:
        return _validated_required_capabilities(
            (selected_payload.get("formal_selection") or {}).get(
                "selected_parameters"
            )
        )
    except ChannelVoteConfirmationError as exc:
        raise ChannelVoteFormalFreezeError(str(exc)) from exc


def freeze_channel_vote_formal_config(
    source_config: Path,
    *,
    calibration_report: Path,
    calibration_run_root: Path,
    confirmation_report: Path,
    confirmation_run_root: Path,
    output_config: Path,
    output_manifest: Path,
    expected_formal_samples: int = EXPECTED_FORMAL_SAMPLES,
) -> dict[str, Any]:
    source_config = source_config.expanduser().resolve()
    calibration_report = calibration_report.expanduser().resolve()
    calibration_run_root = calibration_run_root.expanduser().resolve()
    confirmation_report = confirmation_report.expanduser().resolve()
    confirmation_run_root = confirmation_run_root.expanduser().resolve()
    output_config = output_config.expanduser().resolve()
    output_manifest = output_manifest.expanduser().resolve()
    _assert_fresh_outputs(output_config, output_manifest)
    chain = _prepare_chain(
        source_config,
        calibration_report=calibration_report,
        calibration_run_root=calibration_run_root,
        confirmation_report=confirmation_report,
        confirmation_run_root=confirmation_run_root,
        output_config=output_config,
        output_manifest=output_manifest,
        expected_formal_samples=expected_formal_samples,
    )
    selected_text = yaml.safe_dump(
        chain["selected_payload"], allow_unicode=True, sort_keys=False
    )
    output_config.parent.mkdir(parents=True, exist_ok=True)
    preparation_config = output_config.with_name(
        f".{output_config.name}.{os.getpid()}.prepare"
    )
    if preparation_config.exists():
        raise FileExistsError(
            f"Temporary selected config already exists: {preparation_config}"
        )
    created: list[Path] = []
    try:
        _atomic_write_text(preparation_config, selected_text)
        rebuilt_rows, rebuilt_report = build_manifest_from_config(
            preparation_config,
            allow_missing_sources=False,
            environ={},
        )
        if len(rebuilt_rows) != expected_formal_samples:
            raise ChannelVoteFormalFreezeError(
                f"Rebuilt formal manifest has {len(rebuilt_rows)} rows; "
                f"expected {expected_formal_samples}."
            )
        source_bytes = chain["source_manifest"].read_bytes()
        if manifest_text(rebuilt_rows).encode("utf-8") != source_bytes:
            raise ChannelVoteFormalFreezeError(
                "Rebuilt formal manifest is not byte-equivalent to the analyzed source."
            )
        if manifest_assignment_sha256(rebuilt_rows) != chain["source_lock"].get(
            "assignment_sha256"
        ):
            raise ChannelVoteFormalFreezeError(
                "Rebuilt formal assignment differs from the source lock."
            )
        rebuilt_upstream = rebuilt_report.get("upstream_dataset_locks") or {}
        if rebuilt_upstream != (
            chain["source_lock"].get("upstream_dataset_locks") or {}
        ):
            raise ChannelVoteFormalFreezeError(
                "Upstream dataset locks changed during formal reconstruction."
            )
        if (
            sha256_file(calibration_report) != chain["calibration_report_sha256"]
            or sha256_file(confirmation_report)
            != chain["confirmation_report_sha256"]
            or sha256_file(source_config)
            != chain["calibration_report"]["formal_inputs"]["config_sha256"]
            or sha256_file(chain["source_manifest"])
            != chain["calibration_report"]["formal_inputs"]["manifest_sha256"]
        ):
            raise ChannelVoteFormalFreezeError(
                "A frozen report or formal source changed during reconstruction."
            )
        source_lock_path = Path(str(chain["source_lock"]["lock_path"])).resolve()
        if sha256_file(source_lock_path) != chain["source_lock"]["lock_sha256"]:
            raise ChannelVoteFormalFreezeError(
                "Source formal manifest lock changed during reconstruction."
            )
        _assert_fresh_outputs(output_config, output_manifest)
        os.replace(preparation_config, output_config)
        created.append(output_config)
        created.extend([output_manifest, manifest_lock_path(output_manifest)])
        write_manifest(
            rebuilt_rows,
            output_manifest,
            environ={},
            config_path=output_config,
            upstream_dataset_locks=rebuilt_upstream,
        )
        _validate_selected_manifest(
            output_config,
            source_manifest=chain["source_manifest"],
            source_lock=chain["source_lock"],
            expected_formal_samples=expected_formal_samples,
        )
        # The public validator deterministically rebuilds the payload and, by
        # design, performs both complete analyses again before publication ends.
        validated_capabilities = validate_frozen_channel_vote_formal_config(
            output_config,
            expected_formal_samples=expected_formal_samples,
        )
        if validated_capabilities != chain["confirmation_report"].get(
            "required_capabilities"
        ):
            raise ChannelVoteFormalFreezeError(
                "Published formal capabilities differ after deterministic validation."
            )
    except Exception:
        preparation_config.unlink(missing_ok=True)
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    finally:
        preparation_config.unlink(missing_ok=True)

    return {
        "status": "created",
        "schema_version": FORMAL_SELECTION_SCHEMA_VERSION,
        "source_config": str(source_config),
        "source_config_sha256": sha256_file(source_config),
        "calibration_report": str(calibration_report),
        "calibration_report_sha256": chain["calibration_report_sha256"],
        "confirmation_report": str(confirmation_report),
        "confirmation_report_sha256": chain["confirmation_report_sha256"],
        "selected_config": str(output_config),
        "selected_config_sha256": sha256_file(output_config),
        "selected_manifest": str(output_manifest),
        "selected_manifest_sha256": sha256_file(output_manifest),
        "selected_manifest_lock": str(manifest_lock_path(output_manifest)),
        "selected_manifest_lock_sha256": sha256_file(
            manifest_lock_path(output_manifest)
        ),
        "samples": expected_formal_samples,
        "test_samples": int(chain["source_lock"]["split_counts"].get("test", 0)),
        "assignment_sha256": chain["source_lock"]["assignment_sha256"],
        "formal_test_rows_consumed": FORMAL_TEST_ROWS_CONSUMED,
        "required_capabilities": copy.deepcopy(
            chain["confirmation_report"]["required_capabilities"]
        ),
        "source_tree_identity": copy.deepcopy(chain["source_tree_identity"]),
        "generic_input_overrides_ignored": True,
    }


def main() -> int:
    args = parse_args()
    result = freeze_channel_vote_formal_config(
        args.source_config,
        calibration_report=args.calibration_report,
        calibration_run_root=args.calibration_run_root,
        confirmation_report=args.confirmation_report,
        confirmation_run_root=args.confirmation_run_root,
        output_config=args.output_config,
        output_manifest=args.output_manifest,
        expected_formal_samples=args.expected_formal_samples,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
