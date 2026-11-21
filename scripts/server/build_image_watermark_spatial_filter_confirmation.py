#!/usr/bin/env python3
"""Build the fresh 600-image v3 spatial-filter confirmation bundle."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from protection.supporting.image_watermark.experiments.manifest import (
    dataset_roots_from_config,
    load_manifest,
    manifest_lock_path,
    manifest_path_from_config,
    validate_manifest_lock,
    write_manifest,
)
from scripts.server.analyze_image_watermark_spatial_filter import (
    CALIBRATION_REPORT_SCHEMA_VERSION,
    analyze_bundle,
)
from scripts.server.build_image_watermark_threshold_calibration import (
    _selected_attacks,
    manifest_text,
    normalize_base_url,
)
from scripts.server.image_watermark_preregistration import (
    build_preregistration_contract,
    claim_path_for_config,
    generate_preregistration_nonce,
    write_preregistration_claim,
)
from scripts.server.image_watermark_redevelopment_protocol import (
    ATTACK_ARTIFACT_RETENTION,
    ATTACK_CONDITIONS,
    CALIBRATION_CONTRACT_KEY,
    CALIBRATION_RUN_CLASS,
    CALIBRATION_SCHEMA_VERSION,
    CONFIRMATION_CONTRACT_KEY,
    CONFIRMATION_DATASET_QUOTAS,
    CONFIRMATION_RUN_CLASS,
    CONFIRMATION_SCHEMA_VERSION,
    CONSTRAINTS,
    DATASET_ORDER,
    EVALUATION_SEEDS,
    FORMAL_TEST_ROWS_CONSUMED,
    PROTOCOL_ID,
    REQUIRED_ATTACK_RUNTIME,
    SELECTION_SPLIT,
    SPATIAL_FILTER_CANDIDATES,
    STATISTICAL_UNITS,
    candidate_id,
    canonical_sha256,
    load_locked_assignment,
    required_capabilities,
    sha256_file,
)


EXPECTED_SAMPLES = 600
EXPECTED_ROWS = EXPECTED_SAMPLES * len(EVALUATION_SEEDS) * len(ATTACK_CONDITIONS)
MINIMUM_DOMAINS = 34
class SpatialFilterConfirmationBuildError(RuntimeError):
    """Raised when a frozen input cannot prove the v3 confirmation contract."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the preregistered v3 spatial-filter confirmation bundle."
    )
    parser.add_argument("--source", required=True, help="Frozen formal YAML.")
    parser.add_argument("--assignment", required=True, help="Locked v3 assignment JSONL.")
    parser.add_argument(
        "--assignment-lock", required=True, help="Locked v3 assignment lock JSON."
    )
    parser.add_argument("--calibration-config", required=True)
    parser.add_argument("--calibration-manifest", required=True)
    parser.add_argument("--calibration-run-root", required=True)
    parser.add_argument("--calibration-report", required=True)
    parser.add_argument("--output", required=True, help="Fresh confirmation YAML.")
    parser.add_argument("--manifest-output", required=True, help="Fresh 600-row JSONL.")
    parser.add_argument("--base-url", required=True, help="Exact local API origin.")
    return parser.parse_args()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_mapping(path: Path, *, yaml_file: bool, label: str) -> dict[str, Any]:
    try:
        if yaml_file:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise SpatialFilterConfirmationBuildError(f"Invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise SpatialFilterConfirmationBuildError(f"{label} must be a mapping.")
    return payload


def _validate_calibration(
    *,
    source_config: Path,
    source_manifest: Path,
    assignment_path: Path,
    assignment_lock_path: Path,
    calibration_config: Path,
    calibration_manifest: Path,
    calibration_run_root: Path,
    calibration_report: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Reproduce the complete calibration analysis and return its sole winner."""

    payload = _read_mapping(
        calibration_config, yaml_file=True, label="spatial-filter calibration config"
    )
    experiment = payload.get("experiment") or {}
    contract = payload.get(CALIBRATION_CONTRACT_KEY) or {}
    configured_manifest = manifest_path_from_config(calibration_config, environ={})
    configured_output = Path(str(experiment.get("output_root") or "")).resolve()
    if (
        not isinstance(experiment, dict)
        or experiment.get("run_class") != CALIBRATION_RUN_CLASS
        or not isinstance(contract, dict)
        or contract.get("schema_version") != CALIBRATION_SCHEMA_VERSION
        or configured_manifest.resolve() != calibration_manifest
        or configured_output != (calibration_run_root / "candidate-runs").resolve()
        or Path(str(contract.get("source_formal_config") or "")).resolve()
        != source_config
        or contract.get("source_formal_config_sha256") != sha256_file(source_config)
        or Path(str(contract.get("source_formal_manifest") or "")).resolve()
        != source_manifest
        or contract.get("source_formal_manifest_sha256") != sha256_file(source_manifest)
        or Path(str(contract.get("redevelopment_assignment") or "")).resolve()
        != assignment_path
        or contract.get("redevelopment_assignment_sha256")
        != sha256_file(assignment_path)
        or Path(str(contract.get("redevelopment_assignment_lock") or "")).resolve()
        != assignment_lock_path
        or contract.get("redevelopment_assignment_lock_sha256")
        != sha256_file(assignment_lock_path)
        or contract.get("expected_samples") != 300
        or contract.get("expected_rows_per_candidate")
        != 300 * len(EVALUATION_SEEDS) * len(ATTACK_CONDITIONS)
        or contract.get("evaluation_seeds") != list(EVALUATION_SEEDS)
        or contract.get("attack_conditions") != list(ATTACK_CONDITIONS)
        or contract.get("candidate_area_ratios") != list(SPATIAL_FILTER_CANDIDATES)
        or contract.get("constraints") != CONSTRAINTS
        or contract.get("statistical_units") != STATISTICAL_UNITS
        or contract.get("formal_test_rows_consumed") != FORMAL_TEST_ROWS_CONSUMED
    ):
        raise SpatialFilterConfirmationBuildError(
            "Calibration bundle does not match the frozen v3 source/assignment contract."
        )

    roots = dataset_roots_from_config(calibration_config, environ={})
    calibration_rows = load_manifest(
        calibration_manifest,
        dataset_roots=roots,
        require_files=True,
        verify_hashes=True,
    )
    calibration_lock = validate_manifest_lock(
        calibration_manifest,
        calibration_rows,
        config_path=calibration_config,
        dataset_roots=roots,
    )
    if (
        len(calibration_rows) != 300
        or any(row.split != SELECTION_SPLIT for row in calibration_rows)
        or sha256_file(calibration_manifest) != contract.get("selected_manifest_sha256")
    ):
        raise SpatialFilterConfirmationBuildError(
            "Calibration manifest is incomplete or differs from its frozen binding."
        )

    saved_report = _read_mapping(
        calibration_report, yaml_file=False, label="spatial-filter calibration report"
    )
    declared_payload_sha = saved_report.get("report_payload_sha256")
    report_payload = dict(saved_report)
    report_payload.pop("report_payload_sha256", None)
    if (
        saved_report.get("schema_version") != CALIBRATION_REPORT_SCHEMA_VERSION
        or saved_report.get("status") != "winner_selected"
        or saved_report.get("calibration_passed") is not True
        or saved_report.get("confirmation_performed") is not False
        or saved_report.get("formal_test_rows_consumed") != 0
        or declared_payload_sha != canonical_sha256(report_payload)
        or saved_report.get("config_sha256") != sha256_file(calibration_config)
        or Path(str(saved_report.get("run_root") or "")).resolve()
        != calibration_run_root
    ):
        raise SpatialFilterConfirmationBuildError(
            "Calibration report is not an authenticated winner_selected result."
        )
    reproduced = analyze_bundle(calibration_config, run_root=calibration_run_root)
    if reproduced != saved_report:
        raise SpatialFilterConfirmationBuildError(
            "Saved calibration report differs from independent full-evidence replay."
        )

    selected = saved_report.get("selected_candidate")
    if not isinstance(selected, dict):
        raise SpatialFilterConfirmationBuildError(
            "Calibration report has no sole selected candidate."
        )
    ratio = selected.get("localization_min_component_area_ratio")
    if type(ratio) is not float or ratio not in SPATIAL_FILTER_CANDIDATES:
        raise SpatialFilterConfirmationBuildError(
            "Calibration selected ratio is outside the preregistered grid."
        )
    expected_required = required_capabilities(ratio)
    expected_selected = {
        "candidate_id": candidate_id(ratio),
        "localization_min_component_area_ratio": ratio,
        "required_capabilities": expected_required,
    }
    if selected != expected_selected:
        raise SpatialFilterConfirmationBuildError(
            "Calibration winner identity/capabilities are inconsistent."
        )
    return expected_selected, saved_report, contract, calibration_lock


def build_confirmation_bundle(
    source_config: Path,
    *,
    assignment_path: Path,
    assignment_lock_path: Path,
    calibration_config: Path,
    calibration_manifest: Path,
    calibration_run_root: Path,
    calibration_report: Path,
    output_config: Path,
    output_manifest: Path,
    base_url: str,
    preregistration_nonce: str | None = None,
) -> tuple[dict[str, Any], list[Any]]:
    source_config = source_config.expanduser().resolve()
    assignment_path = assignment_path.expanduser().resolve()
    assignment_lock_path = assignment_lock_path.expanduser().resolve()
    calibration_config = calibration_config.expanduser().resolve()
    calibration_manifest = calibration_manifest.expanduser().resolve()
    calibration_run_root = calibration_run_root.expanduser().resolve()
    calibration_report = calibration_report.expanduser().resolve()
    output_config = output_config.expanduser().resolve()
    output_manifest = output_manifest.expanduser().resolve()
    frozen_inputs = (
        source_config,
        assignment_path,
        assignment_lock_path,
        calibration_config,
        calibration_manifest,
        manifest_lock_path(calibration_manifest),
        calibration_report,
    )
    if output_config.parent != output_manifest.parent or output_config == output_manifest:
        raise SpatialFilterConfirmationBuildError(
            "Confirmation YAML and manifest must share one fresh directory."
        )
    initial_hashes = {path: sha256_file(path) for path in frozen_inputs}
    source = _read_mapping(source_config, yaml_file=True, label="frozen formal config")
    source_experiment = source.get("experiment") or {}
    if (
        not isinstance(source_experiment, dict)
        or source_experiment.get("strict_paper_mode") is not True
        or source_experiment.get("fail_fast") is not True
        or source_experiment.get("split") != "test"
        or source_experiment.get("traditional_attack_artifact_retention")
        != ATTACK_ARTIFACT_RETENTION
        or source_experiment.get("required_attack_runtime") != REQUIRED_ATTACK_RUNTIME
    ):
        raise SpatialFilterConfirmationBuildError(
            "Source config is not the reviewed frozen formal benchmark."
        )

    source_manifest = manifest_path_from_config(source_config, environ={}).resolve()
    for path in (source_manifest, manifest_lock_path(source_manifest)):
        initial_hashes[path] = sha256_file(path)
    roots = dataset_roots_from_config(source_config, environ={})
    source_rows = load_manifest(
        source_manifest,
        dataset_roots=roots,
        require_files=True,
        verify_hashes=True,
    )
    source_lock = validate_manifest_lock(
        source_manifest,
        source_rows,
        config_path=source_config,
        dataset_roots=roots,
    )
    assignment_rows, assignment_lock = load_locked_assignment(
        assignment_path, assignment_lock_path
    )
    if (
        assignment_lock.get("source_formal_config_sha256") != sha256_file(source_config)
        or assignment_lock.get("source_formal_manifest_sha256")
        != sha256_file(source_manifest)
    ):
        raise SpatialFilterConfirmationBuildError(
            "v3 assignment does not bind this source config/manifest."
        )

    winner, calibration_result, calibration_contract, calibration_lock = (
        _validate_calibration(
            source_config=source_config,
            source_manifest=source_manifest,
            assignment_path=assignment_path,
            assignment_lock_path=assignment_lock_path,
            calibration_config=calibration_config,
            calibration_manifest=calibration_manifest,
            calibration_run_root=calibration_run_root,
            calibration_report=calibration_report,
        )
    )
    calibration_ids = {
        str(row.get("sample_id") or "")
        for row in assignment_rows
        if row.get("redevelopment_role") == "calibration"
    }
    selected_assignment = [
        row
        for row in assignment_rows
        if row.get("redevelopment_role") == "confirmation"
    ]
    if len(selected_assignment) != EXPECTED_SAMPLES:
        raise SpatialFilterConfirmationBuildError(
            "v3 assignment does not contain exactly 600 confirmation rows."
        )
    source_by_id = {row.sample_id: row for row in source_rows}
    selected = []
    for assigned in selected_assignment:
        row = source_by_id.get(str(assigned.get("sample_id") or ""))
        if (
            row is None
            or row.sample_id in calibration_ids
            or row.split != "train"
            or assigned.get("formal_split") != "train"
            or assigned.get("history_touched") is not False
            or assigned.get("sha256") != row.sha256
            or assigned.get("source_family") != row.source_family
            or assigned.get("source_dataset") != row.source_dataset
            or assigned.get("domain") != row.domain
        ):
            raise SpatialFilterConfirmationBuildError(
                "Confirmation assignment identity/history validation failed."
            )
        selected.append(replace(row, split=SELECTION_SPLIT))
    selected.sort(key=lambda row: (row.source_dataset, row.sample_id))
    dataset_counts = Counter(row.source_dataset for row in selected)
    selected_domains = sorted({row.domain for row in selected})
    if dict(dataset_counts) != CONFIRMATION_DATASET_QUOTAS:
        raise SpatialFilterConfirmationBuildError(
            "Confirmation source quotas differ from 238/162/119/81."
        )
    if len(selected_domains) < MINIMUM_DOMAINS:
        raise SpatialFilterConfirmationBuildError(
            "Confirmation does not cover the required 34 raw domains."
        )
    for field in ("sample_id", "source_family", "sha256"):
        if len({getattr(row, field) for row in selected}) != EXPECTED_SAMPLES:
            raise SpatialFilterConfirmationBuildError(
                f"Confirmation selected duplicate {field} values."
            )

    datasets = [
        copy.deepcopy(row)
        for row in (source.get("datasets") or [])
        if isinstance(row, dict)
        and row.get("enabled", True)
        and row.get("name") in DATASET_ORDER
    ]
    if {str(row.get("name")) for row in datasets} != set(DATASET_ORDER):
        raise SpatialFilterConfirmationBuildError(
            "Confirmation must retain the four formal source datasets."
        )
    for dataset in datasets:
        name = str(dataset["name"])
        dataset["root"] = str(roots[name])
        dataset["enabled"] = True
        dataset["required_samples"] = CONFIRMATION_DATASET_QUOTAS[name]
        dataset["max_samples"] = CONFIRMATION_DATASET_QUOTAS[name]

    methods = [
        copy.deepcopy(row)
        for row in (source.get("methods") or [])
        if isinstance(row, dict)
        and row.get("id") == "editguard_wrapper"
        and row.get("enabled", True)
    ]
    if len(methods) != 1:
        raise SpatialFilterConfirmationBuildError(
            "Confirmation requires exactly one editguard_wrapper method."
        )
    selected_required = copy.deepcopy(winner["required_capabilities"])
    methods[0]["enabled"] = True
    methods[0]["base_url"] = normalize_base_url(base_url)
    methods[0]["required_capabilities"] = copy.deepcopy(selected_required)
    attacks = _selected_attacks(source)
    selected_text = manifest_text(selected)
    attacks_path = (
        Path(__file__).resolve().parents[2]
        / 'protection' / 'image_watermark'
        / "experiments"
        / "attacks.py"
    ).resolve()
    nonce = preregistration_nonce or generate_preregistration_nonce()
    run_relative_path = f"confirmation-run/{winner['candidate_id']}"
    candidate_root = (output_config.parent / run_relative_path).resolve()

    config = copy.deepcopy(source)
    config["experiment"] = {
        "name": "cogniguard_v3_spatial_filter_confirmation",
        "strict_paper_mode": True,
        "fail_fast": True,
        "run_class": CONFIRMATION_RUN_CLASS,
        "paper_eligible": False,
        "development_only": True,
        "split": SELECTION_SPLIT,
        "seeds": list(EVALUATION_SEEDS),
        "max_samples": EXPECTED_SAMPLES,
        "api_timeout_seconds": int(source_experiment.get("api_timeout_seconds", 900)),
        "bootstrap_iterations": 2000,
        "bootstrap_seed": EVALUATION_SEEDS[0],
        "traditional_attack_artifact_retention": ATTACK_ARTIFACT_RETENTION,
        "required_attack_runtime": copy.deepcopy(REQUIRED_ATTACK_RUNTIME),
        "output_root": str(candidate_root),
    }
    config["manifest"] = {
        "path": str(output_manifest),
        "verify_hashes": True,
        "require_lock": True,
    }
    config["data_requirements"] = {
        "expected_total_samples": EXPECTED_SAMPLES,
        "minimum_selected_samples": EXPECTED_SAMPLES,
        "minimum_test_samples": EXPECTED_SAMPLES,
        "minimum_datasets": 4,
        "minimum_domains": MINIMUM_DOMAINS,
        "require_nonempty_source_family": True,
        "require_unique_source_family": True,
        "expected_unique_source_families": EXPECTED_SAMPLES,
        "require_deterministic_splits": False,
        "required_evaluation_split": SELECTION_SPLIT,
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
    config[CONFIRMATION_CONTRACT_KEY] = {
        "schema_version": CONFIRMATION_SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "run_class": CONFIRMATION_RUN_CLASS,
        "development_only": True,
        "paper_eligible": False,
        "selection_split": SELECTION_SPLIT,
        "source_formal_config": str(source_config),
        "source_formal_config_sha256": sha256_file(source_config),
        "source_formal_manifest": str(source_manifest),
        "source_formal_manifest_sha256": sha256_file(source_manifest),
        "source_formal_manifest_lock": source_lock,
        "redevelopment_assignment": str(assignment_path),
        "redevelopment_assignment_sha256": sha256_file(assignment_path),
        "redevelopment_assignment_lock": str(assignment_lock_path),
        "redevelopment_assignment_lock_sha256": sha256_file(assignment_lock_path),
        "selection_role": "confirmation",
        "expected_samples": EXPECTED_SAMPLES,
        "expected_rows": EXPECTED_ROWS,
        "evaluation_seeds": list(EVALUATION_SEEDS),
        "attack_conditions": list(ATTACK_CONDITIONS),
        "selected_manifest_sha256": hashlib.sha256(
            selected_text.encode("utf-8")
        ).hexdigest(),
        "selected_dataset_counts": dict(dataset_counts),
        "selected_domains": selected_domains,
        "selected_unique_sha256": EXPECTED_SAMPLES,
        "selected_unique_source_families": EXPECTED_SAMPLES,
        "candidate_count": 1,
        "selected_candidate": {
            **copy.deepcopy(winner),
            "run_relative_path": run_relative_path,
        },
        "selected_required_capabilities": copy.deepcopy(selected_required),
        "parameter_search_allowed": False,
        "fallback_candidate_allowed": False,
        "fallback_on_confirmation_failure_allowed": False,
        "decision_output": "pass_or_fail_only_no_parameter_selection",
        "constraints": copy.deepcopy(CONSTRAINTS),
        "statistical_units": copy.deepcopy(STATISTICAL_UNITS),
        "source_calibration_config": str(calibration_config),
        "source_calibration_config_sha256": sha256_file(calibration_config),
        "source_calibration_manifest": str(calibration_manifest),
        "source_calibration_manifest_sha256": sha256_file(calibration_manifest),
        "source_calibration_manifest_lock_path": str(
            manifest_lock_path(calibration_manifest)
        ),
        "source_calibration_manifest_lock_sha256": sha256_file(
            manifest_lock_path(calibration_manifest)
        ),
        "source_calibration_manifest_lock": calibration_lock,
        "source_calibration_report": str(calibration_report),
        "source_calibration_report_sha256": sha256_file(calibration_report),
        "source_calibration_report_payload_sha256": calibration_result[
            "report_payload_sha256"
        ],
        "source_calibration_run_root": str(calibration_run_root),
        "source_calibration_schema_version": calibration_result["schema_version"],
        "source_calibration_status": "winner_selected",
        "source_calibration_passed": True,
        "source_calibration_selected_candidate": copy.deepcopy(winner),
        "source_calibration_contract_sha256": canonical_sha256(calibration_contract),
        "source_calibration_environment_identity_sha256": calibration_result[
            "immutable_environment_identity_sha256"
        ],
        "source_calibration_source_tree_sha256": calibration_result[
            "source_tree_sha256"
        ],
        "formal_test_rows_consumed": FORMAL_TEST_ROWS_CONSUMED,
        "formal_config_mutation_allowed": False,
        "formal_config_update_performed": False,
        "traditional_attack_artifact_retention": ATTACK_ARTIFACT_RETENTION,
        "required_attack_runtime": copy.deepcopy(REQUIRED_ATTACK_RUNTIME),
        "traditional_attack_implementation": {
            "path": str(attacks_path),
            "sha256": sha256_file(attacks_path),
        },
        "preregistration_claim": build_preregistration_contract(
            config_path=output_config,
            nonce=nonce,
            expected_candidate_run_relative_paths=[run_relative_path],
        ),
    }
    if any(sha256_file(path) != digest for path, digest in initial_hashes.items()):
        raise SpatialFilterConfirmationBuildError(
            "A frozen formal/assignment/calibration input changed during construction."
        )
    return config, selected


def main() -> int:
    args = parse_args()
    output = Path(args.output).expanduser().resolve()
    manifest_output = Path(args.manifest_output).expanduser().resolve()
    lock_output = manifest_lock_path(manifest_output)
    claim_output = claim_path_for_config(output)
    candidate_root = output.parent / "confirmation-run"
    if any(
        os.path.lexists(path)
        for path in (output, manifest_output, lock_output, claim_output, candidate_root)
    ):
        raise FileExistsError("Refusing to overwrite a v3 confirmation bundle.")
    config, rows = build_confirmation_bundle(
        Path(args.source),
        assignment_path=Path(args.assignment),
        assignment_lock_path=Path(args.assignment_lock),
        calibration_config=Path(args.calibration_config),
        calibration_manifest=Path(args.calibration_manifest),
        calibration_run_root=Path(args.calibration_run_root),
        calibration_report=Path(args.calibration_report),
        output_config=output,
        output_manifest=manifest_output,
        base_url=args.base_url,
    )
    _atomic_write(output, yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    source_lock = config[CONFIRMATION_CONTRACT_KEY]["source_formal_manifest_lock"]
    written = write_manifest(
        rows,
        manifest_output,
        environ={},
        config_path=output,
        upstream_dataset_locks=source_lock.get("upstream_dataset_locks") or {},
    )
    if sha256_file(written) != config[CONFIRMATION_CONTRACT_KEY][
        "selected_manifest_sha256"
    ]:
        raise RuntimeError("Written confirmation manifest differs from preregistration.")
    roots = dataset_roots_from_config(output, environ={})
    confirmation_lock = validate_manifest_lock(
        written,
        rows,
        config_path=output,
        dataset_roots=roots,
    )
    claim = write_preregistration_claim(
        output, expected_run_class=CONFIRMATION_RUN_CLASS
    )
    print(
        json.dumps(
            {
                "status": "created",
                "config": str(output),
                "manifest": str(written),
                "manifest_lock": str(lock_output),
                "manifest_lock_sha256": confirmation_lock["lock_sha256"],
                "preregistration_claim": claim["source_claim_path"],
                "samples": len(rows),
                "expected_rows": EXPECTED_ROWS,
                "candidate": config[CONFIRMATION_CONTRACT_KEY]["selected_candidate"],
                "formal_test_rows_consumed": FORMAL_TEST_ROWS_CONSUMED,
                "fallback_candidate_allowed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
