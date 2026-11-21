#!/usr/bin/env python3
"""Freeze an authenticated v3 spatial-filter winner for the sealed formal test."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

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
    FORMAL_ATTACK_MODEL_ID,
    SOURCE_TREE_IDENTITY_VERSION,
    _source_tree_identity,
    _source_tree_identity_scope,
    validate_required_capabilities,
)
from scripts.server.analyze_image_watermark_spatial_filter import (
    CALIBRATION_REPORT_SCHEMA_VERSION,
    CONFIRMATION_REPORT_SCHEMA_VERSION,
    analyze_bundle,
)
from scripts.server.build_image_watermark_threshold_calibration import manifest_text
from scripts.server.image_watermark_redevelopment_protocol import (
    ATTACK_ARTIFACT_RETENTION,
    CALIBRATION_CONTRACT_KEY,
    CALIBRATION_RUN_CLASS,
    CONFIRMATION_CONTRACT_KEY,
    CONFIRMATION_RUN_CLASS,
    EXPECTED_FORMAL_SPLITS,
    FORMAL_TEST_ROWS_CONSUMED,
    REQUIRED_ATTACK_RUNTIME,
    candidate_id,
    canonical_sha256,
    load_locked_assignment,
    required_capabilities,
    sha256_file,
)


FORMAL_SELECTION_SCHEMA_VERSION = (
    "cogniguard_image_spatial_filter_formal_selection_v1"
)
FORMAL_SELECTION_SOURCE = "development_only_spatial_filter_confirmation"
FORMAL_RUN_CLASS = "formal_paper_candidate"
FORMAL_METHOD_ID = "editguard_wrapper"
EXPECTED_FORMAL_SAMPLES = 3000
RUNTIME_CAPABILITY_NAMES = (
    "attack_model_id",
    "attack_model_revision",
    "deterministic_mode_enabled",
)
ATTACK_MODEL_REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
RUNTIME_EVIDENCE_SCHEMA_VERSION = (
    "cogniguard_spatial_filter_formal_runtime_evidence_v1"
)


class SpatialFilterFormalFreezeError(RuntimeError):
    """Raised when v3 development evidence cannot authorize formal execution."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--assignment", type=Path, required=True)
    parser.add_argument("--assignment-lock", type=Path, required=True)
    parser.add_argument("--calibration-config", type=Path, required=True)
    parser.add_argument("--calibration-manifest", type=Path, required=True)
    parser.add_argument("--calibration-report", type=Path, required=True)
    parser.add_argument("--calibration-run-root", type=Path, required=True)
    parser.add_argument("--confirmation-config", type=Path, required=True)
    parser.add_argument("--confirmation-manifest", type=Path, required=True)
    parser.add_argument("--confirmation-report", type=Path, required=True)
    parser.add_argument("--confirmation-run-root", type=Path, required=True)
    parser.add_argument("--output-config", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    return parser.parse_args()


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpatialFilterFormalFreezeError(f"Invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise SpatialFilterFormalFreezeError(f"{label} must be a JSON object.")
    return payload


def _read_yaml(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise SpatialFilterFormalFreezeError(f"Invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise SpatialFilterFormalFreezeError(f"{label} must be a YAML mapping.")
    return payload


def _resolve_file(value: object, *, label: str, base: Path | None = None) -> Path:
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip():
        raise SpatialFilterFormalFreezeError(f"{label} path is missing.")
    path = Path(value).expanduser()
    if not path.is_absolute() and base is not None:
        path = base / path
    # Check the directory entry before resolving so a symlink cannot be
    # canonicalized into an apparently regular target and bypass the freeze
    # evidence boundary.
    if path.is_symlink():
        raise SpatialFilterFormalFreezeError(
            f"{label} must be a regular non-symlink file: {path}"
        )
    path = path.resolve()
    if not path.is_file():
        raise SpatialFilterFormalFreezeError(
            f"{label} must be a regular non-symlink file: {path}"
        )
    return path


def _resolve_directory(
    value: object, *, label: str, base: Path | None = None
) -> Path:
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip():
        raise SpatialFilterFormalFreezeError(f"{label} path is missing.")
    path = Path(value).expanduser()
    if not path.is_absolute() and base is not None:
        path = base / path
    if path.is_symlink():
        raise SpatialFilterFormalFreezeError(
            f"{label} must be a real non-symlink directory: {path}"
        )
    path = path.resolve()
    if not path.is_dir():
        raise SpatialFilterFormalFreezeError(
            f"{label} must be a real non-symlink directory: {path}"
        )
    return path


def _relative_reference(target: Path, *, base: Path) -> str:
    try:
        return Path(os.path.relpath(target, start=base)).as_posix()
    except ValueError:
        return str(target)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if os.path.lexists(temporary):
        raise FileExistsError(f"Temporary output already exists: {temporary}")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if os.path.lexists(path):
            raise FileExistsError(f"Refusing to overwrite existing output: {path}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _assert_fresh_outputs(output_config: Path, output_manifest: Path) -> None:
    output_lock = manifest_lock_path(output_manifest)
    if len({output_config, output_manifest, output_lock}) != 3:
        raise SpatialFilterFormalFreezeError(
            "Selected config, manifest, and lock paths must differ."
        )
    collisions = [
        path
        for path in (output_config, output_manifest, output_lock)
        if os.path.lexists(path)
    ]
    if collisions:
        raise FileExistsError(
            "Refusing to overwrite spatial-filter formal outputs: "
            + ", ".join(str(path) for path in collisions)
        )


def _bound_file(
    path: Path,
    expected_path: object,
    expected_sha256: object,
    *,
    label: str,
) -> None:
    if (
        _resolve_file(expected_path, label=label) != path
        or not isinstance(expected_sha256, str)
        or sha256_file(path) != expected_sha256
    ):
        raise SpatialFilterFormalFreezeError(f"{label} path/SHA binding differs.")


def _authenticated_saved_report(
    report_path: Path,
    *,
    config_path: Path,
    run_root: Path,
    expected_schema: str,
    label: str,
) -> dict[str, Any]:
    saved = _read_json(report_path, label=label)
    payload = dict(saved)
    declared = payload.pop("report_payload_sha256", None)
    if (
        saved.get("schema_version") != expected_schema
        or declared != canonical_sha256(payload)
        or saved.get("config_sha256") != sha256_file(config_path)
        or Path(str(saved.get("run_root") or "")).resolve() != run_root
        or saved.get("formal_test_rows_consumed") != FORMAL_TEST_ROWS_CONSUMED
    ):
        raise SpatialFilterFormalFreezeError(f"{label} authentication failed.")
    return saved


def _validate_formal_source(
    source_config: Path,
    *,
    expected_formal_samples: int,
) -> tuple[dict[str, Any], Path, list[Any], dict[str, Any]]:
    payload = _read_yaml(source_config, label="source formal config")
    experiment = payload.get("experiment") or {}
    manifest_cfg = payload.get("manifest") or {}
    requirements = payload.get("data_requirements") or {}
    methods = [
        row
        for row in (payload.get("methods") or [])
        if isinstance(row, Mapping)
        and row.get("enabled", True)
        and row.get("id") == FORMAL_METHOD_ID
    ]
    if (
        not isinstance(experiment, Mapping)
        or experiment.get("strict_paper_mode") is not True
        or experiment.get("fail_fast") is not True
        or experiment.get("split") != "test"
        or experiment.get("traditional_attack_artifact_retention")
        != ATTACK_ARTIFACT_RETENTION
        or experiment.get("required_attack_runtime") != REQUIRED_ATTACK_RUNTIME
        or not isinstance(manifest_cfg, Mapping)
        or manifest_cfg.get("verify_hashes") is not True
        or manifest_cfg.get("require_lock") is not True
        or not isinstance(requirements, Mapping)
        or requirements.get("expected_total_samples") != expected_formal_samples
        or len(methods) != 1
        or "required_capabilities" in methods[0]
        or "formal_selection" in payload
    ):
        raise SpatialFilterFormalFreezeError(
            "Source must be the unselected strict formal benchmark."
        )
    manifest = manifest_path_from_config(source_config, environ={}).resolve()
    roots = dataset_roots_from_config(source_config, environ={})
    rows = load_manifest(
        manifest,
        dataset_roots=roots,
        require_files=True,
        verify_hashes=True,
    )
    lock = validate_manifest_lock(
        manifest,
        rows,
        config_path=source_config,
        dataset_roots=roots,
    )
    if (
        len(rows) != expected_formal_samples
        or len({row.sample_id for row in rows}) != expected_formal_samples
        or len({row.source_family for row in rows}) != expected_formal_samples
        or len({row.sha256 for row in rows}) != expected_formal_samples
    ):
        raise SpatialFilterFormalFreezeError(
            "Source formal manifest count/independence is invalid."
        )
    split_counts = dict(Counter(row.split for row in rows))
    if expected_formal_samples == EXPECTED_FORMAL_SAMPLES:
        if split_counts != EXPECTED_FORMAL_SPLITS:
            raise SpatialFilterFormalFreezeError(
                "Source formal split must remain 2109/333/558."
            )
    elif not split_counts.get("test"):
        raise SpatialFilterFormalFreezeError("Fixture formal manifest has no test row.")
    return payload, manifest, rows, lock


def _load_runtime_evidence(
    confirmation_report: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    candidate_reports = confirmation_report.get("candidate_reports")
    if (
        not isinstance(candidate_reports, list)
        or len(candidate_reports) != 1
        or not isinstance(candidate_reports[0], Mapping)
    ):
        raise SpatialFilterFormalFreezeError(
            "Confirmation report must contain exactly one candidate report."
        )
    candidate = dict(candidate_reports[0])
    environment = candidate.get("environment_identity")
    if (
        not isinstance(environment, Mapping)
        or candidate.get("environment_identity_sha256")
        != canonical_sha256(dict(environment))
    ):
        raise SpatialFilterFormalFreezeError(
            "Confirmation environment identity is unauthenticated."
        )
    capabilities_path = _resolve_file(
        candidate.get("capabilities_path"), label="confirmation capabilities"
    )
    if sha256_file(capabilities_path) != candidate.get("capabilities_sha256"):
        raise SpatialFilterFormalFreezeError(
            "Confirmation capabilities file differs from its report SHA."
        )
    capabilities = _read_json(
        capabilities_path, label="confirmation capabilities"
    )
    ratio = candidate.get("localization_min_component_area_ratio")
    algorithm = required_capabilities(ratio)
    validate_required_capabilities(
        {"id": FORMAL_METHOD_ID, "required_capabilities": algorithm},
        capabilities,
        require_declaration=True,
    )
    runtime = {name: capabilities.get(name) for name in RUNTIME_CAPABILITY_NAMES}
    if (
        runtime.get("attack_model_id") != FORMAL_ATTACK_MODEL_ID
        or type(runtime.get("attack_model_revision")) is not str
        or ATTACK_MODEL_REVISION_PATTERN.fullmatch(
            str(runtime.get("attack_model_revision"))
        )
        is None
        or runtime.get("deterministic_mode_enabled") is not True
        or capabilities.get("service_singleton") is not True
    ):
        raise SpatialFilterFormalFreezeError(
            "Confirmation runtime capabilities are incomplete or unaudited."
        )
    required = {**algorithm, **runtime}
    evidence = {
        "schema_version": RUNTIME_EVIDENCE_SCHEMA_VERSION,
        "confirmation_environment": copy.deepcopy(dict(environment)),
        "confirmation_environment_sha256": candidate[
            "environment_identity_sha256"
        ],
        "confirmation_capabilities": copy.deepcopy(capabilities),
        "confirmation_capabilities_path": str(capabilities_path),
        "confirmation_capabilities_sha256": candidate["capabilities_sha256"],
        "selected_required_capabilities": copy.deepcopy(required),
        "service_singleton": True,
    }
    return required, evidence, candidate


def _source_tree_from_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    environment = candidate.get("environment_identity") or {}
    identity = {
        "identity_version": environment.get("source_tree_identity_version"),
        "scope": copy.deepcopy(environment.get("source_tree_scope")),
        "sha256": environment.get("source_tree_sha256"),
        "file_count": environment.get("source_tree_file_count"),
    }
    if (
        identity["identity_version"] != SOURCE_TREE_IDENTITY_VERSION
        or identity["scope"] != _source_tree_identity_scope()
        or not isinstance(identity["sha256"], str)
        or re.fullmatch(r"[0-9a-f]{64}", identity["sha256"]) is None
        or type(identity["file_count"]) is not int
        or identity["file_count"] <= 0
    ):
        raise SpatialFilterFormalFreezeError(
            "Development source-tree identity is incomplete."
        )
    return identity


def _replay_chain(
    *,
    source_config: Path,
    assignment: Path,
    assignment_lock: Path,
    calibration_config: Path,
    calibration_manifest: Path,
    calibration_report: Path,
    calibration_run_root: Path,
    confirmation_config: Path,
    confirmation_manifest: Path,
    confirmation_report: Path,
    confirmation_run_root: Path,
    expected_formal_samples: int,
    require_current_source_tree: bool,
) -> dict[str, Any]:
    source_payload, source_manifest, source_rows, source_lock = (
        _validate_formal_source(
            source_config, expected_formal_samples=expected_formal_samples
        )
    )
    assignments, assignment_lock_payload = load_locked_assignment(
        assignment, assignment_lock
    )
    if (
        assignment_lock_payload.get("source_formal_config_sha256")
        != sha256_file(source_config)
        or assignment_lock_payload.get("source_formal_manifest_sha256")
        != sha256_file(source_manifest)
        or len(assignments) != EXPECTED_FORMAL_SAMPLES
    ):
        raise SpatialFilterFormalFreezeError(
            "Redevelopment assignment does not bind the formal source."
        )

    calibration_payload = _read_yaml(
        calibration_config, label="calibration config"
    )
    calibration_contract = calibration_payload.get(CALIBRATION_CONTRACT_KEY) or {}
    if (
        not isinstance(calibration_contract, Mapping)
        or (calibration_payload.get("experiment") or {}).get("run_class")
        != CALIBRATION_RUN_CLASS
        or calibration_config.parent != calibration_run_root
        or manifest_path_from_config(calibration_config, environ={}).resolve()
        != calibration_manifest
    ):
        raise SpatialFilterFormalFreezeError("Calibration path/run contract is invalid.")
    for actual, path_field, sha_field, label in (
        (source_config, "source_formal_config", "source_formal_config_sha256", "source formal config"),
        (source_manifest, "source_formal_manifest", "source_formal_manifest_sha256", "source formal manifest"),
        (assignment, "redevelopment_assignment", "redevelopment_assignment_sha256", "assignment"),
        (assignment_lock, "redevelopment_assignment_lock", "redevelopment_assignment_lock_sha256", "assignment lock"),
    ):
        _bound_file(
            actual,
            calibration_contract.get(path_field),
            calibration_contract.get(sha_field),
            label=f"Calibration {label}",
        )
    saved_calibration = _authenticated_saved_report(
        calibration_report,
        config_path=calibration_config,
        run_root=calibration_run_root,
        expected_schema=CALIBRATION_REPORT_SCHEMA_VERSION,
        label="calibration report",
    )
    reproduced_calibration = analyze_bundle(
        calibration_config, run_root=calibration_run_root
    )
    if reproduced_calibration != saved_calibration:
        raise SpatialFilterFormalFreezeError(
            "Calibration report differs from independent analyze_bundle replay."
        )
    if (
        saved_calibration.get("status") != "winner_selected"
        or saved_calibration.get("calibration_passed") is not True
        or saved_calibration.get("confirmation_performed") is not False
    ):
        raise SpatialFilterFormalFreezeError(
            "Calibration did not select an eligible winner."
        )

    confirmation_payload = _read_yaml(
        confirmation_config, label="confirmation config"
    )
    confirmation_contract = confirmation_payload.get(CONFIRMATION_CONTRACT_KEY) or {}
    if (
        not isinstance(confirmation_contract, Mapping)
        or (confirmation_payload.get("experiment") or {}).get("run_class")
        != CONFIRMATION_RUN_CLASS
        or confirmation_config.parent != confirmation_run_root
        or manifest_path_from_config(confirmation_config, environ={}).resolve()
        != confirmation_manifest
    ):
        raise SpatialFilterFormalFreezeError("Confirmation path/run contract is invalid.")
    confirmation_bindings = (
        (source_config, "source_formal_config", "source_formal_config_sha256", "source formal config"),
        (source_manifest, "source_formal_manifest", "source_formal_manifest_sha256", "source formal manifest"),
        (assignment, "redevelopment_assignment", "redevelopment_assignment_sha256", "assignment"),
        (assignment_lock, "redevelopment_assignment_lock", "redevelopment_assignment_lock_sha256", "assignment lock"),
        (calibration_config, "source_calibration_config", "source_calibration_config_sha256", "calibration config"),
        (calibration_manifest, "source_calibration_manifest", "source_calibration_manifest_sha256", "calibration manifest"),
        (manifest_lock_path(calibration_manifest), "source_calibration_manifest_lock_path", "source_calibration_manifest_lock_sha256", "calibration manifest lock"),
        (calibration_report, "source_calibration_report", "source_calibration_report_sha256", "calibration report"),
    )
    for actual, path_field, sha_field, label in confirmation_bindings:
        _bound_file(
            actual,
            confirmation_contract.get(path_field),
            confirmation_contract.get(sha_field),
            label=f"Confirmation {label}",
        )
    if (
        Path(
            str(confirmation_contract.get("source_calibration_run_root") or "")
        ).resolve()
        != calibration_run_root
    ):
        raise SpatialFilterFormalFreezeError(
            "Confirmation calibration run-root binding differs."
        )
    saved_confirmation = _authenticated_saved_report(
        confirmation_report,
        config_path=confirmation_config,
        run_root=confirmation_run_root,
        expected_schema=CONFIRMATION_REPORT_SCHEMA_VERSION,
        label="confirmation report",
    )
    # This replay independently validates the confirmation and recursively replays
    # its calibration lineage.  The explicit calibration replay above is retained
    # so the freeze does not rely only on the nested call.
    reproduced_confirmation = analyze_bundle(
        confirmation_config, run_root=confirmation_run_root
    )
    if reproduced_confirmation != saved_confirmation:
        raise SpatialFilterFormalFreezeError(
            "Confirmation report differs from independent analyze_bundle replay."
        )
    if (
        saved_confirmation.get("status") != "confirmation_passed"
        or saved_confirmation.get("confirmation_passed") is not True
        or saved_confirmation.get("formal_execution_authorized") is not True
        or saved_confirmation.get("fallback_candidate_allowed") is not False
        or saved_confirmation.get("formal_test_rows_consumed") != 0
    ):
        raise SpatialFilterFormalFreezeError(
            "Confirmation did not authorize formal execution."
        )

    required, runtime_evidence, confirmation_candidate = _load_runtime_evidence(
        saved_confirmation
    )
    selected = saved_confirmation.get("selected_candidate")
    ratio = required.get("localization_min_component_area_ratio")
    expected_selected = {
        "candidate_id": candidate_id(ratio),
        "localization_min_component_area_ratio": ratio,
        "required_capabilities": required_capabilities(ratio),
    }
    if (
        selected != expected_selected
        or saved_calibration.get("selected_candidate") != expected_selected
        or confirmation_contract.get("selected_required_capabilities")
        != expected_selected["required_capabilities"]
    ):
        raise SpatialFilterFormalFreezeError(
            "Confirmation winner differs from its calibration lineage."
        )

    calibration_reports = saved_calibration.get("candidate_reports") or []
    matching_calibration = [
        row
        for row in calibration_reports
        if isinstance(row, Mapping)
        and row.get("candidate_id") == expected_selected["candidate_id"]
    ]
    if len(matching_calibration) != 1:
        raise SpatialFilterFormalFreezeError(
            "Calibration winner runtime/source-tree evidence is missing."
        )
    source_tree = _source_tree_from_candidate(confirmation_candidate)
    if _source_tree_from_candidate(matching_calibration[0]) != source_tree:
        raise SpatialFilterFormalFreezeError(
            "Calibration and confirmation source-tree identities differ."
        )
    if require_current_source_tree:
        current_tree = _source_tree_identity(Path(__file__).resolve().parents[2])
        if current_tree != source_tree:
            raise SpatialFilterFormalFreezeError(
                "Current source tree differs from development evidence."
            )

    for manifest, config in (
        (calibration_manifest, calibration_config),
        (confirmation_manifest, confirmation_config),
    ):
        roots = dataset_roots_from_config(config, environ={})
        rows = load_manifest(
            manifest, dataset_roots=roots, require_files=True, verify_hashes=True
        )
        validate_manifest_lock(
            manifest, rows, config_path=config, dataset_roots=roots
        )

    input_paths = (
        source_config,
        source_manifest,
        manifest_lock_path(source_manifest),
        assignment,
        assignment_lock,
        calibration_config,
        calibration_manifest,
        manifest_lock_path(calibration_manifest),
        calibration_report,
        confirmation_config,
        confirmation_manifest,
        manifest_lock_path(confirmation_manifest),
        confirmation_report,
    )
    return {
        "source_payload": source_payload,
        "source_manifest": source_manifest,
        "source_rows": source_rows,
        "source_lock": source_lock,
        "assignment": assignment,
        "assignment_lock": assignment_lock,
        "assignment_lock_payload": assignment_lock_payload,
        "calibration_config": calibration_config,
        "calibration_manifest": calibration_manifest,
        "calibration_report_path": calibration_report,
        "calibration_report": saved_calibration,
        "calibration_run_root": calibration_run_root,
        "confirmation_config": confirmation_config,
        "confirmation_manifest": confirmation_manifest,
        "confirmation_report_path": confirmation_report,
        "confirmation_report": saved_confirmation,
        "confirmation_run_root": confirmation_run_root,
        "required_capabilities": required,
        "runtime_evidence": runtime_evidence,
        "runtime_evidence_sha256": canonical_sha256(runtime_evidence),
        "source_tree": source_tree,
        "input_hashes": {str(path): sha256_file(path) for path in input_paths},
    }


def _rebase_config_paths(
    payload: dict[str, Any], *, source_config: Path, output_config: Path
) -> None:
    source_base = source_config.parent
    output_base = output_config.parent
    experiment = payload.get("experiment")
    if isinstance(experiment, dict) and experiment.get("output_root"):
        output = Path(str(experiment["output_root"])).expanduser()
        if not output.is_absolute():
            output = source_base / output
        experiment["output_root"] = _relative_reference(
            output.resolve(), base=output_base
        )
    for dataset in payload.get("datasets") or []:
        if not isinstance(dataset, dict) or not dataset.get("root"):
            continue
        root = Path(str(dataset["root"])).expanduser()
        if not root.is_absolute():
            root = source_base / root
        dataset["root"] = _relative_reference(root.resolve(), base=output_base)


def _artifact_binding(path: Path, *, base: Path) -> dict[str, Any]:
    return {
        "path": _relative_reference(path, base=base),
        "sha256": sha256_file(path),
    }


def _build_selected_payload(
    *,
    source_config: Path,
    output_config: Path,
    output_manifest: Path,
    chain: Mapping[str, Any],
) -> dict[str, Any]:
    selected = copy.deepcopy(dict(chain["source_payload"]))
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
    if len(methods) != 1 or "required_capabilities" in methods[0]:
        raise SpatialFilterFormalFreezeError(
            "Source must enable one unselected editguard_wrapper method."
        )
    methods[0]["required_capabilities"] = copy.deepcopy(
        chain["required_capabilities"]
    )
    source_tree = chain["source_tree"]
    source_lock = chain["source_lock"]
    runtime_evidence = chain["runtime_evidence"]
    selected_candidate = chain["confirmation_report"]["selected_candidate"]
    base = output_config.parent
    selected["formal_selection"] = {
        "schema_version": FORMAL_SELECTION_SCHEMA_VERSION,
        "status": "frozen",
        "method_id": FORMAL_METHOD_ID,
        "selection_source": FORMAL_SELECTION_SOURCE,
        "selection_split": "redevelopment_train_heldout_as_dev",
        "development_roles": ["calibration", "confirmation"],
        "formal_test_rows_consumed": FORMAL_TEST_ROWS_CONSUMED,
        "formal_test_split_sealed_until_execution": True,
        "selected_parameters": copy.deepcopy(chain["required_capabilities"]),
        "selected_candidate": copy.deepcopy(selected_candidate),
        "fallback_candidate_allowed": False,
        "decision_rule": (
            "publish the smallest calibration candidate satisfying every source-cluster "
            "and row-level gate only when the sole fresh confirmation also satisfies "
            "every gate; no fallback"
        ),
        "source_tree_identity": copy.deepcopy(source_tree),
        "calibration_source_tree_identity_version": source_tree["identity_version"],
        "calibration_source_tree_scope": copy.deepcopy(source_tree["scope"]),
        "calibration_source_tree_sha256": source_tree["sha256"],
        "calibration_source_tree_file_count": source_tree["file_count"],
        "spatial_filter_runtime_evidence": copy.deepcopy(runtime_evidence),
        "spatial_filter_runtime_evidence_sha256": chain[
            "runtime_evidence_sha256"
        ],
        "source_formal": {
            "config": _relative_reference(source_config, base=base),
            "config_sha256": sha256_file(source_config),
            "manifest": _relative_reference(chain["source_manifest"], base=base),
            "manifest_sha256": sha256_file(chain["source_manifest"]),
            "manifest_lock": _relative_reference(
                manifest_lock_path(chain["source_manifest"]), base=base
            ),
            "manifest_lock_sha256": source_lock["lock_sha256"],
            "assignment_sha256": source_lock["assignment_sha256"],
            "split_counts": copy.deepcopy(source_lock["split_counts"]),
        },
        "redevelopment_assignment": {
            **_artifact_binding(chain["assignment"], base=base),
            "lock": _relative_reference(chain["assignment_lock"], base=base),
            "lock_sha256": sha256_file(chain["assignment_lock"]),
        },
        "calibration": {
            "config": _artifact_binding(chain["calibration_config"], base=base),
            "manifest": _artifact_binding(chain["calibration_manifest"], base=base),
            "manifest_lock": _artifact_binding(
                manifest_lock_path(chain["calibration_manifest"]), base=base
            ),
            "report": _artifact_binding(chain["calibration_report_path"], base=base),
            "report_payload_sha256": chain["calibration_report"][
                "report_payload_sha256"
            ],
            "run_root": _relative_reference(chain["calibration_run_root"], base=base),
            "outcome": "winner_selected",
        },
        "confirmation": {
            "config": _artifact_binding(chain["confirmation_config"], base=base),
            "manifest": _artifact_binding(chain["confirmation_manifest"], base=base),
            "manifest_lock": _artifact_binding(
                manifest_lock_path(chain["confirmation_manifest"]), base=base
            ),
            "report": _artifact_binding(chain["confirmation_report_path"], base=base),
            "report_payload_sha256": chain["confirmation_report"][
                "report_payload_sha256"
            ],
            "run_root": _relative_reference(chain["confirmation_run_root"], base=base),
            "outcome": "confirmation_passed",
            "formal_execution_authorized": True,
        },
    }
    return selected


def _selection_paths(
    config_path: Path, selection: Mapping[str, Any]
) -> dict[str, Path]:
    base = config_path.parent
    source = selection.get("source_formal") or {}
    assignment = selection.get("redevelopment_assignment") or {}
    calibration = selection.get("calibration") or {}
    confirmation = selection.get("confirmation") or {}
    if not all(
        isinstance(row, Mapping)
        for row in (source, assignment, calibration, confirmation)
    ):
        raise SpatialFilterFormalFreezeError(
            "Selected formal artifact bindings are incomplete."
        )

    def artifact(container: Mapping[str, Any], key: str, label: str) -> Path:
        value = container.get(key)
        if isinstance(value, Mapping):
            path_value = value.get("path")
            expected_sha = value.get("sha256")
        else:
            path_value = value
            expected_sha = (
                container.get("sha256")
                if key == "path"
                else container.get(f"{key}_sha256")
            )
        path = _resolve_file(path_value, label=label, base=base)
        if sha256_file(path) != expected_sha:
            raise SpatialFilterFormalFreezeError(f"{label} SHA binding differs.")
        return path

    paths = {
        "source_config": artifact(source, "config", "source formal config"),
        "source_manifest": artifact(source, "manifest", "source formal manifest"),
        "source_lock": artifact(source, "manifest_lock", "source formal manifest lock"),
        "assignment": artifact(assignment, "path", "redevelopment assignment"),
        "assignment_lock": artifact(assignment, "lock", "redevelopment assignment lock"),
        "calibration_config": artifact(calibration, "config", "calibration config"),
        "calibration_manifest": artifact(calibration, "manifest", "calibration manifest"),
        "calibration_lock": artifact(calibration, "manifest_lock", "calibration manifest lock"),
        "calibration_report": artifact(calibration, "report", "calibration report"),
        "confirmation_config": artifact(confirmation, "config", "confirmation config"),
        "confirmation_manifest": artifact(confirmation, "manifest", "confirmation manifest"),
        "confirmation_lock": artifact(confirmation, "manifest_lock", "confirmation manifest lock"),
        "confirmation_report": artifact(confirmation, "report", "confirmation report"),
    }
    for key, manifest_key in (
        ("source_lock", "source_manifest"),
        ("calibration_lock", "calibration_manifest"),
        ("confirmation_lock", "confirmation_manifest"),
    ):
        if paths[key] != manifest_lock_path(paths[manifest_key]):
            raise SpatialFilterFormalFreezeError(
                f"{key} is not adjacent to its selected manifest."
            )
    for phase in ("calibration", "confirmation"):
        container = selection[phase]
        run_root = _resolve_directory(
            container.get("run_root"), label=f"{phase} run root", base=base
        )
        paths[f"{phase}_run_root"] = run_root
    return paths


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
        raise SpatialFilterFormalFreezeError(
            f"Selected lock changed frozen formal data evidence: {mismatches}."
        )
    if (
        selected_lock.get("manifest_filename") != output_manifest.name
        or selected_lock.get("config_sha256") != sha256_file(output_config)
    ):
        raise SpatialFilterFormalFreezeError(
            "Selected manifest lock does not bind the selected config/manifest."
        )


def validate_frozen_spatial_filter_formal_config(
    selected_config: Path,
    *,
    expected_formal_samples: int = EXPECTED_FORMAL_SAMPLES,
) -> dict[str, Any]:
    selected_config = _resolve_file(
        selected_config, label="selected spatial-filter formal config"
    )
    selected_payload = _read_yaml(selected_config, label="selected formal config")
    selection = selected_payload.get("formal_selection") or {}
    if (
        not isinstance(selection, Mapping)
        or selection.get("schema_version") != FORMAL_SELECTION_SCHEMA_VERSION
        or selection.get("selection_source") != FORMAL_SELECTION_SOURCE
        or selection.get("status") != "frozen"
        or selection.get("method_id") != FORMAL_METHOD_ID
        or selection.get("formal_test_rows_consumed") != 0
        or selection.get("formal_test_split_sealed_until_execution") is not True
        or selection.get("fallback_candidate_allowed") is not False
    ):
        raise SpatialFilterFormalFreezeError(
            "Selected config has no supported v3 spatial-filter formal selection."
        )
    paths = _selection_paths(selected_config, selection)
    chain = _replay_chain(
        source_config=paths["source_config"],
        assignment=paths["assignment"],
        assignment_lock=paths["assignment_lock"],
        calibration_config=paths["calibration_config"],
        calibration_manifest=paths["calibration_manifest"],
        calibration_report=paths["calibration_report"],
        calibration_run_root=paths["calibration_run_root"],
        confirmation_config=paths["confirmation_config"],
        confirmation_manifest=paths["confirmation_manifest"],
        confirmation_report=paths["confirmation_report"],
        confirmation_run_root=paths["confirmation_run_root"],
        expected_formal_samples=expected_formal_samples,
        require_current_source_tree=False,
    )
    if paths["source_manifest"] != chain["source_manifest"]:
        raise SpatialFilterFormalFreezeError(
            "Selected source formal manifest reference differs from source config."
        )
    expected = _build_selected_payload(
        source_config=paths["source_config"],
        output_config=selected_config,
        output_manifest=manifest_path_from_config(selected_config, environ={}).resolve(),
        chain=chain,
    )
    if selected_payload != expected:
        raise SpatialFilterFormalFreezeError(
            "Selected YAML differs from the deterministic v3 freeze product."
        )
    selected_manifest = manifest_path_from_config(selected_config, environ={}).resolve()
    roots = dataset_roots_from_config(selected_config, environ={})
    rows = load_manifest(
        selected_manifest,
        dataset_roots=roots,
        require_files=True,
        verify_hashes=True,
    )
    selected_lock = validate_manifest_lock(
        selected_manifest,
        rows,
        config_path=selected_config,
        dataset_roots=roots,
    )
    if (
        len(rows) != expected_formal_samples
        or selected_manifest.read_bytes() != chain["source_manifest"].read_bytes()
    ):
        raise SpatialFilterFormalFreezeError(
            "Selected formal manifest is not byte-identical to the sealed source."
        )
    _assert_lock_invariants(
        chain["source_lock"],
        selected_lock,
        output_config=selected_config,
        output_manifest=selected_manifest,
    )
    return copy.deepcopy(chain["required_capabilities"])


def freeze_spatial_filter_formal_config(
    source_config: Path,
    *,
    assignment: Path,
    assignment_lock: Path,
    calibration_config: Path,
    calibration_manifest: Path,
    calibration_report: Path,
    calibration_run_root: Path,
    confirmation_config: Path,
    confirmation_manifest: Path,
    confirmation_report: Path,
    confirmation_run_root: Path,
    output_config: Path,
    output_manifest: Path,
    expected_formal_samples: int = EXPECTED_FORMAL_SAMPLES,
) -> dict[str, Any]:
    resolved = {
        "source_config": source_config.expanduser().resolve(),
        "assignment": assignment.expanduser().resolve(),
        "assignment_lock": assignment_lock.expanduser().resolve(),
        "calibration_config": calibration_config.expanduser().resolve(),
        "calibration_manifest": calibration_manifest.expanduser().resolve(),
        "calibration_report": calibration_report.expanduser().resolve(),
        "calibration_run_root": calibration_run_root.expanduser().resolve(),
        "confirmation_config": confirmation_config.expanduser().resolve(),
        "confirmation_manifest": confirmation_manifest.expanduser().resolve(),
        "confirmation_report": confirmation_report.expanduser().resolve(),
        "confirmation_run_root": confirmation_run_root.expanduser().resolve(),
    }
    output_config = output_config.expanduser().resolve()
    output_manifest = output_manifest.expanduser().resolve()
    _assert_fresh_outputs(output_config, output_manifest)
    protected = set(resolved.values()) | {
        manifest_lock_path(resolved["calibration_manifest"]),
        manifest_lock_path(resolved["confirmation_manifest"]),
    }
    if output_config in protected or output_manifest in protected:
        raise SpatialFilterFormalFreezeError(
            "Formal outputs must not overwrite development/source evidence."
        )
    chain = _replay_chain(
        **resolved,
        expected_formal_samples=expected_formal_samples,
        require_current_source_tree=True,
    )
    selected_payload = _build_selected_payload(
        source_config=resolved["source_config"],
        output_config=output_config,
        output_manifest=output_manifest,
        chain=chain,
    )
    initial_hashes = dict(chain["input_hashes"])
    created: list[Path] = []
    try:
        rebuilt_rows, _report = build_manifest_from_config(
            resolved["source_config"], environ={}
        )
        source_bytes = chain["source_manifest"].read_bytes()
        if (
            len(rebuilt_rows) != expected_formal_samples
            or manifest_text(rebuilt_rows).encode("utf-8") != source_bytes
            or manifest_assignment_sha256(rebuilt_rows)
            != chain["source_lock"].get("assignment_sha256")
        ):
            raise SpatialFilterFormalFreezeError(
                "Rebuilt formal manifest differs from the sealed 3000-row source."
            )
        if any(
            sha256_file(Path(path)) != digest
            for path, digest in initial_hashes.items()
        ):
            raise SpatialFilterFormalFreezeError(
                "A source/development artifact changed during formal freeze."
            )
        _assert_fresh_outputs(output_config, output_manifest)
        _atomic_write(
            output_config,
            yaml.safe_dump(selected_payload, allow_unicode=True, sort_keys=False),
        )
        created.append(output_config)
        created.extend([output_manifest, manifest_lock_path(output_manifest)])
        write_manifest(
            rebuilt_rows,
            output_manifest,
            environ={},
            config_path=output_config,
            upstream_dataset_locks=(
                chain["source_lock"].get("upstream_dataset_locks") or {}
            ),
        )
        roots = dataset_roots_from_config(output_config, environ={})
        selected_rows = load_manifest(
            output_manifest,
            dataset_roots=roots,
            require_files=True,
            verify_hashes=True,
        )
        selected_lock = validate_manifest_lock(
            output_manifest,
            selected_rows,
            config_path=output_config,
            dataset_roots=roots,
        )
        if (
            output_manifest.read_bytes() != source_bytes
            or Counter(row.split for row in selected_rows)
            != Counter(row.split for row in chain["source_rows"])
        ):
            raise SpatialFilterFormalFreezeError(
                "Published formal manifest/test split changed during freeze."
            )
        _assert_lock_invariants(
            chain["source_lock"],
            selected_lock,
            output_config=output_config,
            output_manifest=output_manifest,
        )
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return {
        "status": "frozen",
        "schema_version": FORMAL_SELECTION_SCHEMA_VERSION,
        "selection_source": FORMAL_SELECTION_SOURCE,
        "selected_config": str(output_config),
        "selected_config_sha256": sha256_file(output_config),
        "selected_manifest": str(output_manifest),
        "selected_manifest_sha256": sha256_file(output_manifest),
        "selected_manifest_lock": str(manifest_lock_path(output_manifest)),
        "selected_manifest_lock_sha256": sha256_file(
            manifest_lock_path(output_manifest)
        ),
        "selected_parameters": copy.deepcopy(chain["required_capabilities"]),
        "formal_test_rows_consumed": 0,
        "formal_test_samples": Counter(row.split for row in chain["source_rows"])[
            "test"
        ],
    }


def main() -> int:
    args = parse_args()
    result = freeze_spatial_filter_formal_config(
        args.source_config,
        assignment=args.assignment,
        assignment_lock=args.assignment_lock,
        calibration_config=args.calibration_config,
        calibration_manifest=args.calibration_manifest,
        calibration_report=args.calibration_report,
        calibration_run_root=args.calibration_run_root,
        confirmation_config=args.confirmation_config,
        confirmation_manifest=args.confirmation_manifest,
        confirmation_report=args.confirmation_report,
        confirmation_run_root=args.confirmation_run_root,
        output_config=args.output_config,
        output_manifest=args.output_manifest,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
