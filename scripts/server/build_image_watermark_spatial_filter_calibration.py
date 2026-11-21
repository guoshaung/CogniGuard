#!/usr/bin/env python3
"""Build the fresh 300-image v3 spatial-filter calibration bundle."""

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
    CALIBRATION_DATASET_QUOTAS,
    CALIBRATION_RUN_CLASS,
    CALIBRATION_SCHEMA_VERSION,
    CONSTRAINTS,
    DATASET_ORDER,
    EVALUATION_SEEDS,
    FORMAL_TEST_ROWS_CONSUMED,
    FROZEN_FIXED_CAPABILITIES,
    PROTOCOL_ID,
    REQUIRED_ATTACK_RUNTIME,
    SELECTION_SPLIT,
    SPATIAL_FILTER_CANDIDATES,
    STATISTICAL_UNITS,
    candidate_runs,
    load_locked_assignment,
    sha256_file,
)


EXPECTED_SAMPLES = 300
EXPECTED_ROWS_PER_CANDIDATE = EXPECTED_SAMPLES * len(EVALUATION_SEEDS) * len(
    ATTACK_CONDITIONS
)
MINIMUM_DOMAINS = 34


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the preregistered v3 spatial-filter calibration bundle."
    )
    parser.add_argument("--source", required=True, help="Frozen formal YAML.")
    parser.add_argument("--assignment", required=True, help="Locked v3 assignment JSONL.")
    parser.add_argument(
        "--assignment-lock", required=True, help="Locked v3 assignment lock JSON."
    )
    parser.add_argument("--output", required=True, help="Fresh calibration YAML.")
    parser.add_argument("--manifest-output", required=True, help="Fresh 300-row JSONL.")
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


def build_calibration_bundle(
    source_config: Path,
    *,
    assignment_path: Path,
    assignment_lock_path: Path,
    output_config: Path,
    output_manifest: Path,
    base_url: str,
    preregistration_nonce: str | None = None,
) -> tuple[dict[str, Any], list[Any]]:
    source_config = source_config.expanduser().resolve()
    assignment_path = assignment_path.expanduser().resolve()
    assignment_lock_path = assignment_lock_path.expanduser().resolve()
    output_config = output_config.expanduser().resolve()
    output_manifest = output_manifest.expanduser().resolve()
    if output_config.parent != output_manifest.parent or output_config == output_manifest:
        raise ValueError("Calibration YAML and manifest must share one fresh directory.")
    try:
        source = yaml.safe_load(source_config.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("Unable to read frozen formal YAML.") from exc
    if not isinstance(source, dict):
        raise ValueError("Frozen formal YAML root is not a mapping.")
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
        raise ValueError("Source config is not the reviewed frozen formal benchmark.")

    source_manifest = manifest_path_from_config(source_config, environ={})
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
        raise ValueError("v3 assignment does not bind this source config/manifest.")
    source_by_id = {row.sample_id: row for row in source_rows}
    selected_assignment = [
        row
        for row in assignment_rows
        if row.get("redevelopment_role") == "calibration"
    ]
    if len(selected_assignment) != EXPECTED_SAMPLES:
        raise ValueError("v3 assignment does not contain exactly 300 calibration rows.")
    selected = []
    for assigned in selected_assignment:
        row = source_by_id.get(str(assigned.get("sample_id") or ""))
        if (
            row is None
            or row.split != "train"
            or assigned.get("formal_split") != "train"
            or assigned.get("history_touched") is not False
            or assigned.get("sha256") != row.sha256
            or assigned.get("source_family") != row.source_family
            or assigned.get("source_dataset") != row.source_dataset
            or assigned.get("domain") != row.domain
        ):
            raise ValueError("Calibration assignment identity/history validation failed.")
        selected.append(replace(row, split=SELECTION_SPLIT))
    selected.sort(key=lambda row: (row.source_dataset, row.sample_id))
    dataset_counts = Counter(row.source_dataset for row in selected)
    if dict(dataset_counts) != CALIBRATION_DATASET_QUOTAS:
        raise ValueError("Calibration source quotas differ from the locked assignment.")
    if len({row.domain for row in selected}) < MINIMUM_DOMAINS:
        raise ValueError("Calibration does not cover the required 34 raw domains.")
    for field in ("sample_id", "source_family", "sha256"):
        if len({getattr(row, field) for row in selected}) != EXPECTED_SAMPLES:
            raise ValueError(f"Calibration selected duplicate {field} values.")

    enabled_source_datasets = [
        copy.deepcopy(row)
        for row in (source.get("datasets") or [])
        if isinstance(row, dict)
        and row.get("enabled", True)
        and row.get("name") in DATASET_ORDER
    ]
    if {str(row.get("name")) for row in enabled_source_datasets} != set(DATASET_ORDER):
        raise ValueError("Calibration must retain the four formal source datasets.")
    for dataset in enabled_source_datasets:
        name = str(dataset["name"])
        dataset["root"] = str(roots[name])
        dataset["enabled"] = True
        dataset["required_samples"] = CALIBRATION_DATASET_QUOTAS[name]
        dataset["max_samples"] = CALIBRATION_DATASET_QUOTAS[name]

    methods = [
        copy.deepcopy(row)
        for row in (source.get("methods") or [])
        if isinstance(row, dict)
        and row.get("id") == "editguard_wrapper"
        and row.get("enabled", True)
    ]
    if len(methods) != 1:
        raise ValueError("Calibration requires exactly one editguard_wrapper method.")
    methods[0]["enabled"] = True
    methods[0]["base_url"] = normalize_base_url(base_url)
    methods[0]["required_capabilities"] = copy.deepcopy(
        FROZEN_FIXED_CAPABILITIES
    )
    attacks = _selected_attacks(source)
    selected_text = manifest_text(selected)
    attacks_path = (
        Path(__file__).resolve().parents[2]
        / 'protection' / 'image_watermark'
        / "experiments"
        / "attacks.py"
    ).resolve()
    nonce = preregistration_nonce or generate_preregistration_nonce()
    config = copy.deepcopy(source)
    config["experiment"] = {
        "name": "cogniguard_v3_spatial_filter_calibration",
        "strict_paper_mode": True,
        "fail_fast": True,
        "run_class": CALIBRATION_RUN_CLASS,
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
        "output_root": str((output_config.parent / "candidate-runs").resolve()),
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
    config["datasets"] = enabled_source_datasets
    config["methods"] = methods
    config["attacks"] = {
        "traditional": attacks,
        "aigc": {"enabled": False, "specs": []},
    }
    config[CALIBRATION_CONTRACT_KEY] = {
        "schema_version": CALIBRATION_SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "run_class": CALIBRATION_RUN_CLASS,
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
        "redevelopment_assignment_lock_sha256": sha256_file(
            assignment_lock_path
        ),
        "selection_role": "calibration",
        "expected_samples": EXPECTED_SAMPLES,
        "expected_rows_per_candidate": EXPECTED_ROWS_PER_CANDIDATE,
        "evaluation_seeds": list(EVALUATION_SEEDS),
        "selected_manifest_sha256": hashlib.sha256(
            selected_text.encode("utf-8")
        ).hexdigest(),
        "selected_dataset_counts": dict(dataset_counts),
        "selected_domains": sorted({row.domain for row in selected}),
        "selected_unique_sha256": EXPECTED_SAMPLES,
        "selected_unique_source_families": EXPECTED_SAMPLES,
        "candidate_area_ratios": list(SPATIAL_FILTER_CANDIDATES),
        "candidate_runs": candidate_runs(),
        "fixed_capabilities": copy.deepcopy(FROZEN_FIXED_CAPABILITIES),
        "attack_conditions": list(ATTACK_CONDITIONS),
        "constraints": copy.deepcopy(CONSTRAINTS),
        "statistical_units": copy.deepcopy(STATISTICAL_UNITS),
        "winner_rule": (
            "among complete candidates satisfying every source-cluster and row-level "
            "clean-FPR/erasing-IoU constraint, select the smallest frozen component "
            "area ratio; no fallback after confirmation"
        ),
        "exploratory_legacy_evidence_only": True,
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
            expected_candidate_run_relative_paths=[
                f"candidate-runs/{row['candidate_id']}" for row in candidate_runs()
            ],
        ),
    }
    return config, selected


def main() -> int:
    args = parse_args()
    output = Path(args.output).expanduser().resolve()
    manifest_output = Path(args.manifest_output).expanduser().resolve()
    lock_output = manifest_lock_path(manifest_output)
    claim_output = claim_path_for_config(output)
    candidate_root = output.parent / "candidate-runs"
    if any(
        os.path.lexists(path)
        for path in (output, manifest_output, lock_output, claim_output, candidate_root)
    ):
        raise FileExistsError("Refusing to overwrite a v3 calibration bundle.")
    config, rows = build_calibration_bundle(
        Path(args.source),
        assignment_path=Path(args.assignment),
        assignment_lock_path=Path(args.assignment_lock),
        output_config=output,
        output_manifest=manifest_output,
        base_url=args.base_url,
    )
    _atomic_write(output, yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    source_lock = config[CALIBRATION_CONTRACT_KEY]["source_formal_manifest_lock"]
    written = write_manifest(
        rows,
        manifest_output,
        environ={},
        config_path=output,
        upstream_dataset_locks=source_lock.get("upstream_dataset_locks") or {},
    )
    if sha256_file(written) != config[CALIBRATION_CONTRACT_KEY][
        "selected_manifest_sha256"
    ]:
        raise RuntimeError("Written calibration manifest differs from preregistration.")
    roots = dataset_roots_from_config(output, environ={})
    calibration_lock = validate_manifest_lock(
        written,
        rows,
        config_path=output,
        dataset_roots=roots,
    )
    claim = write_preregistration_claim(
        output, expected_run_class=CALIBRATION_RUN_CLASS
    )
    print(
        json.dumps(
            {
                "status": "created",
                "config": str(output),
                "manifest": str(written),
                "manifest_lock": str(lock_output),
                "manifest_lock_sha256": calibration_lock["lock_sha256"],
                "preregistration_claim": claim["source_claim_path"],
                "samples": len(rows),
                "candidate_area_ratios": list(SPATIAL_FILTER_CANDIDATES),
                "expected_rows_per_candidate": EXPECTED_ROWS_PER_CANDIDATE,
                "formal_test_rows_consumed": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
