#!/usr/bin/env python3
"""Build a fail-closed, development-only localization-threshold bundle."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

import yaml

from protection.supporting.image_watermark.experiments.attacks import expand_attack_specs
from protection.supporting.image_watermark.experiments.manifest import (
    ImageSample,
    dataset_roots_from_config,
    deterministic_split,
    load_manifest,
    manifest_lock_path,
    manifest_path_from_config,
    validate_manifest_lock,
    write_manifest,
)
from scripts.server.image_watermark_preregistration import (
    build_preregistration_contract,
    claim_path_for_config,
    generate_preregistration_nonce,
    write_preregistration_claim,
)


SCHEMA_VERSION = "cogniguard_image_threshold_calibration_v2"
RUN_CLASS = "threshold_calibration_development_only"
SELECTION_SPLIT = "dev"
EXPECTED_SAMPLES = 117
DEFAULT_SEED = 20260802
FROZEN_THRESHOLDS = (0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.32, 0.34, 0.36)
EVALUATION_SEEDS = (20260802, 20260803, 20260804)
ERASING_RATIOS = (0.05, 0.15, 0.25)
ATTACK_CONDITIONS = (
    "clean",
    "erasing__area_ratio-0.05",
    "erasing__area_ratio-0.15",
    "erasing__area_ratio-0.25",
)
SUBSET_POLICY = (
    "stage 1: within each dev source_family select the row minimizing "
    "sha256(seed|threshold-calibration-v2-family-representative|source_family|"
    "sample_id|sha256); stage 2: rank those representatives by "
    "sha256(seed|threshold-calibration-v2-subset|source_family|sample_id|sha256), "
    "take the first 117, then sort output by (source_dataset, sample_id)"
)
CONSTRAINTS = {
    "clean_mean_mask_fpr_max": 1e-4,
    "clean_p99_mask_fpr_max": 5e-4,
    "clean_max_mask_fpr_max": 1e-3,
    "each_erasing_mean_mask_iou_min": 0.90,
    "each_erasing_p10_mask_iou_min": 0.75,
    "each_erasing_iou_at_least_0_75_rate_min": 0.95,
}
ATTACK_ARTIFACT_RETENTION = "hash_only"
REQUIRED_ATTACK_RUNTIME = {
    "numpy": "1.26.4",
    "Pillow": "10.4.0",
}
LOCALIZATION_MASK_CONTRACT = {
    "localization_mask_rule_version": "editguard_residual_channel_vote_v2",
    "localization_residual_channels": 3,
    "localization_channel_aggregation": "k_of_3",
    "localization_channel_vote_min": 1,
    "localization_residual_threshold_rule": (
        "abs_gt_recovery_threshold_per_channel"
    ),
}
FIXED_PARAMETERS = {
    "tamper_area_threshold": 0.001,
    "registry_hamming_radius": 1,
    "localization_postprocessing": "none",
    **LOCALIZATION_MASK_CONTRACT,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an isolated v2 dev threshold-calibration bundle."
    )
    parser.add_argument("--source", required=True, help="Frozen formal benchmark YAML.")
    parser.add_argument("--output", required=True, help="Fresh calibration YAML path.")
    parser.add_argument(
        "--manifest-output", required=True, help="Fresh dev-only JSONL path."
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Exact image-watermark API base URL used by every candidate run.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--expected-samples", type=int, default=EXPECTED_SAMPLES)
    parser.add_argument(
        "--threshold",
        type=float,
        action="append",
        dest="thresholds",
        help="Candidate threshold; repeat to add candidates. Defaults to the frozen grid.",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def candidate_id(threshold: float) -> str:
    rendered = f"{threshold:.8f}".rstrip("0").rstrip(".").replace(".", "p")
    return f"recovery_threshold_{rendered}"


def normalize_base_url(value: str) -> str:
    base_url = str(value).strip()
    parsed = urlsplit(base_url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"Invalid image-watermark API base URL: {base_url!r}") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or port is None
        or not 1 <= port <= 65535
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Image-watermark API base URL must be an absolute http(s) origin "
            f"with an explicit port and no credentials, path, query, or fragment: {base_url!r}"
        )
    return base_url


def normalize_thresholds(values: Iterable[float] | None) -> tuple[float, ...]:
    raw = (
        FROZEN_THRESHOLDS if values is None else tuple(float(value) for value in values)
    )
    normalized: list[float] = []
    for value in raw:
        if not math.isfinite(value) or not 0.0 < value < 1.0:
            raise ValueError(
                f"Recovery thresholds must be finite values in (0, 1): {value}"
            )
        rounded = round(value, 12)
        if rounded not in normalized:
            normalized.append(rounded)
    frozen = tuple(FROZEN_THRESHOLDS)
    observed = tuple(sorted(normalized))
    if observed != frozen:
        raise ValueError(
            "Threshold grid must exactly equal the frozen candidates: "
            f"expected={list(frozen)}, observed={list(observed)}"
        )
    return observed


def audit_formal_split_assignments(
    rows: Iterable[ImageSample], *, split_config: dict[str, Any]
) -> dict[str, Any]:
    """Recompute every formal split from source_family and freeze an audit digest."""

    try:
        split_seed = int(split_config["seed"])
        train_ratio = float(split_config["train_ratio"])
        dev_ratio = float(split_config["dev_ratio"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "Formal config split must define integer seed and numeric train/dev ratios."
        ) from exc
    materialized = list(rows)
    if not materialized:
        raise ValueError("Formal split audit requires a non-empty manifest.")
    if any(not row.source_family for row in materialized):
        raise ValueError(
            "Every formal manifest row must have a non-empty source_family."
        )

    assignments: list[tuple[str, str, str, str]] = []
    mismatches: list[dict[str, str]] = []
    split_counts: dict[str, int] = {}
    for row in materialized:
        expected = deterministic_split(
            row.source_family,
            seed=split_seed,
            train_ratio=train_ratio,
            dev_ratio=dev_ratio,
        )
        assignments.append(
            (row.source_dataset, row.sample_id, row.source_family, expected)
        )
        split_counts[expected] = split_counts.get(expected, 0) + 1
        if row.split != expected:
            mismatches.append(
                {
                    "sample_id": row.sample_id,
                    "source_family": row.source_family,
                    "declared": row.split,
                    "expected": expected,
                }
            )
    if mismatches:
        raise ValueError(
            "Formal manifest split assignments do not match deterministic source-family "
            f"splitting; first mismatches={mismatches[:5]}"
        )
    digest_text = "".join("\t".join(values) + "\n" for values in sorted(assignments))
    return {
        "seed": split_seed,
        "train_ratio": train_ratio,
        "dev_ratio": dev_ratio,
        "rows": len(materialized),
        "source_families": len({row.source_family for row in materialized}),
        "split_counts": dict(sorted(split_counts.items())),
        "assignment_sha256": hashlib.sha256(digest_text.encode("utf-8")).hexdigest(),
    }


def manifest_text(rows: Iterable[ImageSample]) -> str:
    ordered = sorted(rows, key=lambda row: (row.source_dataset, row.sample_id))
    return "".join(
        json.dumps(
            row.to_dict(include_runtime_path=False),
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
        for row in ordered
    )


def _selection_key(sample: ImageSample, *, seed: int, label: str) -> str:
    material = "|".join(
        (
            str(seed),
            label,
            sample.source_family,
            sample.sample_id,
            sample.sha256,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _select_unique_dev_rows(
    rows: list[ImageSample], *, seed: int, expected_samples: int
) -> tuple[list[ImageSample], dict[str, int]]:
    eligible = [row for row in rows if row.split == SELECTION_SPLIT]
    if any(not row.sha256 for row in eligible):
        raise ValueError("Every eligible dev row must have a verified SHA-256 value.")
    if any(not row.source_family for row in eligible):
        raise ValueError("Every eligible dev row must have a non-empty source_family.")

    by_family: dict[str, list[ImageSample]] = {}
    for row in eligible:
        by_family.setdefault(row.source_family, []).append(row)
    representatives = [
        min(
            family_rows,
            key=lambda row: _selection_key(
                row, seed=seed, label="threshold-calibration-v2-family-representative"
            ),
        )
        for family_rows in by_family.values()
    ]
    if len(representatives) < expected_samples:
        raise ValueError(
            f"Formal dev split has only {len(representatives)} independent source families; "
            f"{expected_samples} are required."
        )
    selected = sorted(
        representatives,
        key=lambda row: _selection_key(
            row, seed=seed, label="threshold-calibration-v2-subset"
        ),
    )[:expected_samples]
    selected.sort(key=lambda row: (row.source_dataset, row.sample_id))
    if len({row.sample_id for row in selected}) != expected_samples:
        raise ValueError(
            "Selected calibration rows do not have unique sample_id values."
        )
    if len({row.sha256 for row in selected}) != expected_samples:
        raise ValueError("Selected calibration rows do not have unique image content.")
    if len({row.source_family for row in selected}) != expected_samples:
        raise ValueError(
            "Selected calibration rows do not have unique source_family values."
        )
    if {row.split for row in selected} != {SELECTION_SPLIT}:
        raise ValueError("Threshold calibration selected a non-development row.")
    return selected, {
        "eligible_dev_rows": len(eligible),
        "eligible_unique_sha256": len({row.sha256 for row in eligible}),
        "eligible_source_families": len(by_family),
    }


def _selected_attacks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    traditional = (payload.get("attacks") or {}).get("traditional") or []
    by_name: dict[str, list[dict[str, Any]]] = {}
    for row in traditional:
        if isinstance(row, dict):
            by_name.setdefault(str(row.get("name") or ""), []).append(row)
    if len(by_name.get("clean", [])) != 1 or len(by_name.get("erasing", [])) != 1:
        raise ValueError(
            "Formal config must define exactly one clean and one erasing attack."
        )
    clean = copy.deepcopy(by_name["clean"][0])
    clean.pop("grid", None)
    erasing = copy.deepcopy(by_name["erasing"][0])
    source_grid = list(erasing.get("grid") or [])
    selected_grid: list[dict[str, Any]] = []
    for ratio in ERASING_RATIOS:
        matches = [
            copy.deepcopy(row)
            for row in source_grid
            if isinstance(row, dict)
            and set(row) == {"area_ratio"}
            and math.isclose(
                float(row["area_ratio"]), ratio, rel_tol=0.0, abs_tol=1e-12
            )
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Formal erasing grid must contain exactly one area_ratio={ratio}."
            )
        selected_grid.append(matches[0])
    erasing["grid"] = selected_grid
    attacks = [clean, erasing]
    expanded = expand_attack_specs(attacks)
    observed = [str(spec.params.get("expanded_name") or spec.name) for spec in expanded]
    expected = list(ATTACK_CONDITIONS)
    if observed != expected:
        raise ValueError(f"Unexpected calibration attack expansion: {observed}")
    return attacks


def build_threshold_calibration_bundle(
    source_config: Path,
    *,
    output_config: Path,
    output_manifest: Path,
    base_url: str,
    expected_samples: int = EXPECTED_SAMPLES,
    seed: int = DEFAULT_SEED,
    thresholds: Iterable[float] | None = None,
    preregistration_nonce: str | None = None,
) -> tuple[dict[str, Any], list[ImageSample]]:
    if expected_samples != EXPECTED_SAMPLES:
        raise ValueError(
            f"The frozen threshold protocol requires exactly {EXPECTED_SAMPLES} samples."
        )
    if seed != DEFAULT_SEED:
        raise ValueError(
            f"The frozen threshold protocol requires selection seed {DEFAULT_SEED}."
        )
    candidates = normalize_thresholds(thresholds)
    preregistration_nonce = (
        generate_preregistration_nonce()
        if preregistration_nonce is None
        else preregistration_nonce
    )
    source_config = source_config.expanduser().resolve()
    output_config = output_config.expanduser().resolve()
    output_manifest = output_manifest.expanduser().resolve()
    if output_config == output_manifest:
        raise ValueError(
            "Calibration output config and manifest must be different paths."
        )
    if output_config.parent != output_manifest.parent:
        raise ValueError(
            "Calibration output config and manifest must share one bundle directory."
        )
    frozen_base_url = normalize_base_url(base_url)
    source_config_sha256 = sha256_file(source_config)
    payload = yaml.safe_load(source_config.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("Formal benchmark YAML root must be a mapping.")
    experiment = payload.get("experiment") or {}
    manifest_cfg = payload.get("manifest") or {}
    if (
        not isinstance(experiment, dict)
        or experiment.get("split") != "test"
        or experiment.get("strict_paper_mode") is not True
        or experiment.get("fail_fast") is not True
    ):
        raise ValueError("Source config must be the strict formal test configuration.")
    if (
        not isinstance(manifest_cfg, dict)
        or manifest_cfg.get("verify_hashes") is not True
        or manifest_cfg.get("require_lock") is not True
    ):
        raise ValueError(
            "Formal manifest hash verification and immutable lock are required."
        )
    attack_artifact_retention = experiment.get("traditional_attack_artifact_retention")
    if attack_artifact_retention != ATTACK_ARTIFACT_RETENTION:
        raise ValueError(
            "Formal config must freeze traditional_attack_artifact_retention="
            f"{ATTACK_ARTIFACT_RETENTION!r}."
        )
    required_attack_runtime = experiment.get("required_attack_runtime")
    if required_attack_runtime != REQUIRED_ATTACK_RUNTIME:
        raise ValueError(
            "Formal config required_attack_runtime must exactly match the frozen "
            f"attack runtime: {REQUIRED_ATTACK_RUNTIME}."
        )

    # Calibration must be bound to the manifest and roots declared by the
    # reviewed formal YAML.  Machine-level environment overrides are ignored.
    source_manifest = manifest_path_from_config(source_config, environ={})
    source_manifest_sha256 = sha256_file(source_manifest)
    roots = dataset_roots_from_config(source_config, environ={})
    rows = load_manifest(
        source_manifest,
        dataset_roots=roots,
        require_files=True,
        verify_hashes=True,
    )
    source_manifest_lock_audit = validate_manifest_lock(
        source_manifest,
        rows,
        config_path=source_config,
        dataset_roots=roots,
    )
    if sha256_file(source_manifest) != source_manifest_sha256:
        raise RuntimeError("Formal manifest changed while its rows were verified.")
    expected_total = int(
        ((payload.get("data_requirements") or {}).get("expected_total_samples") or 0)
    )
    if expected_total and len(rows) != expected_total:
        raise ValueError(
            f"Formal manifest has {len(rows)} rows; expected exactly {expected_total}."
        )
    split_assignment_audit = audit_formal_split_assignments(
        rows, split_config=dict(payload.get("split") or {})
    )

    enabled_source_datasets = [
        row
        for row in (payload.get("datasets") or [])
        if isinstance(row, dict) and row.get("enabled", True)
    ]
    enabled_names = {str(row.get("name") or "") for row in enabled_source_datasets}
    if not enabled_names or "" in enabled_names:
        raise ValueError("Formal config must define named enabled datasets.")
    source_dataset_counts: dict[str, int] = {}
    for row in rows:
        source_dataset_counts[row.source_dataset] = (
            source_dataset_counts.get(row.source_dataset, 0) + 1
        )
    unexpected_source_datasets = sorted(set(source_dataset_counts) - enabled_names)
    if unexpected_source_datasets:
        raise ValueError(
            "Formal manifest contains rows outside enabled datasets: "
            + ", ".join(unexpected_source_datasets)
        )
    expected_source_counts = {
        str(row["name"]): int(row["required_samples"])
        for row in enabled_source_datasets
        if row.get("required_samples") is not None
    }
    mismatched_source_counts = {
        name: {"expected": expected, "observed": source_dataset_counts.get(name, 0)}
        for name, expected in sorted(expected_source_counts.items())
        if source_dataset_counts.get(name, 0) != expected
    }
    if mismatched_source_counts:
        raise ValueError(
            "Formal manifest exact dataset quotas do not match: "
            f"{mismatched_source_counts}."
        )
    selected, eligible_audit = _select_unique_dev_rows(
        rows, seed=seed, expected_samples=expected_samples
    )

    enabled_datasets = [copy.deepcopy(row) for row in enabled_source_datasets]
    selected_names = {row.source_dataset for row in selected}
    if not enabled_names or selected_names != enabled_names:
        raise ValueError(
            "The 117-row dev subset must cover every enabled formal dataset: "
            f"selected={sorted(selected_names)}, enabled={sorted(enabled_names)}"
        )
    minimum_domains = int(
        ((payload.get("data_requirements") or {}).get("minimum_domains") or 1)
    )
    selected_domains = {row.domain for row in selected}
    if len(selected_domains) < minimum_domains:
        raise ValueError(
            f"Selected dev subset has {len(selected_domains)} domains; "
            f"minimum is {minimum_domains}."
        )
    selected_dataset_counts: dict[str, int] = {}
    for row in selected:
        selected_dataset_counts[row.source_dataset] = (
            selected_dataset_counts.get(row.source_dataset, 0) + 1
        )
    for dataset in enabled_datasets:
        name = str(dataset.get("name") or "")
        root = roots.get(name)
        if root is None or not root.is_dir():
            raise FileNotFoundError(f"Resolved dataset root is unavailable: {name}")
        dataset["root"] = str(root)
        dataset["enabled"] = True
        dataset["required_samples"] = selected_dataset_counts[name]
        dataset["max_samples"] = selected_dataset_counts[name]

    methods = [
        copy.deepcopy(row)
        for row in (payload.get("methods") or [])
        if isinstance(row, dict)
        and row.get("id") == "editguard_wrapper"
        and row.get("enabled", True)
    ]
    if len(methods) != 1:
        raise ValueError("Calibration requires exactly one editguard_wrapper method.")
    methods[0]["enabled"] = True
    methods[0]["base_url"] = frozen_base_url
    # The recovery threshold is the only candidate-varying capability and is
    # checked by the runner.  Replace any source-formal declaration so a stale
    # formal k value cannot leak into this frozen k=1 development protocol.
    methods[0]["required_capabilities"] = copy.deepcopy(FIXED_PARAMETERS)
    attacks = _selected_attacks(payload)
    selected_text = manifest_text(selected)
    sample_ids = sorted(row.sample_id for row in selected)
    attacks_path = (
        Path(__file__).resolve().parents[2]
        / 'protection' / 'image_watermark'
        / "experiments"
        / "attacks.py"
    ).resolve()
    if not attacks_path.is_file():
        raise FileNotFoundError(
            f"Shared attack implementation is missing: {attacks_path}"
        )
    attacks_sha256 = sha256_file(attacks_path)

    config = copy.deepcopy(payload)
    config["experiment"] = {
        "name": "cogniguard_v2_recovery_threshold_calibration",
        "strict_paper_mode": True,
        "fail_fast": True,
        "run_class": RUN_CLASS,
        "paper_eligible": False,
        "development_only": True,
        "split": SELECTION_SPLIT,
        "seeds": list(EVALUATION_SEEDS),
        "max_samples": expected_samples,
        "api_timeout_seconds": int(experiment.get("api_timeout_seconds", 900)),
        "bootstrap_iterations": 2000,
        "bootstrap_seed": int(seed),
        "traditional_attack_artifact_retention": attack_artifact_retention,
        "required_attack_runtime": copy.deepcopy(required_attack_runtime),
        "output_root": str((output_config.parent / "candidate-runs").resolve()),
    }
    config["manifest"] = {
        "path": str(output_manifest),
        "verify_hashes": True,
        "require_lock": True,
    }
    config["data_requirements"] = {
        "expected_total_samples": expected_samples,
        "minimum_selected_samples": expected_samples,
        "minimum_test_samples": expected_samples,
        "minimum_datasets": len(enabled_names),
        "minimum_domains": minimum_domains,
        "require_nonempty_source_family": True,
        "require_unique_source_family": True,
        "expected_unique_source_families": expected_samples,
        "require_deterministic_splits": True,
    }
    config["metrics"] = {
        "require_reference_ssim": True,
        "lpips": {"enabled": False, "required": False},
    }
    config["datasets"] = enabled_datasets
    config["methods"] = methods
    config["attacks"] = {
        "traditional": attacks,
        "aigc": {"enabled": False, "specs": []},
    }
    config["threshold_calibration"] = {
        "schema_version": SCHEMA_VERSION,
        "run_class": RUN_CLASS,
        "development_only": True,
        "paper_eligible": False,
        "selection_split": SELECTION_SPLIT,
        "excluded_splits": ["train", "test"],
        "formal_test_rows_consumed": 0,
        "formal_config_mutation_allowed": False,
        "formal_config_update_performed": False,
        "source_formal_config": str(source_config),
        "source_formal_config_sha256": source_config_sha256,
        "source_formal_manifest": str(source_manifest),
        "source_formal_manifest_sha256": source_manifest_sha256,
        "source_formal_manifest_lock": source_manifest_lock_audit,
        "selected_manifest_sha256": hashlib.sha256(
            selected_text.encode("utf-8")
        ).hexdigest(),
        "selected_sample_ids_sha256": hashlib.sha256(
            "\n".join(sample_ids).encode("utf-8")
        ).hexdigest(),
        "selection_seed": int(seed),
        "evaluation_seeds": list(EVALUATION_SEEDS),
        "selection_policy": SUBSET_POLICY,
        "expected_samples": expected_samples,
        "expected_rows_per_candidate": (
            expected_samples * len(ATTACK_CONDITIONS) * len(EVALUATION_SEEDS)
        ),
        "eligible_audit": eligible_audit,
        "formal_split_assignment_audit": split_assignment_audit,
        "selected_unique_sha256": expected_samples,
        "selected_unique_source_families": expected_samples,
        "selected_dataset_counts": dict(sorted(selected_dataset_counts.items())),
        "selected_datasets": sorted(selected_names),
        "selected_domains": sorted(selected_domains),
        "candidate_thresholds": list(candidates),
        "candidate_runs": [
            {"candidate_id": candidate_id(value), "recovery_threshold": value}
            for value in candidates
        ],
        "preregistration_claim": build_preregistration_contract(
            config_path=output_config,
            nonce=preregistration_nonce,
            expected_candidate_run_relative_paths=[
                f"candidate-runs/{candidate_id(value)}" for value in candidates
            ],
        ),
        "fixed_parameters": copy.deepcopy(FIXED_PARAMETERS),
        "traditional_attack_artifact_retention": attack_artifact_retention,
        "required_attack_runtime": copy.deepcopy(required_attack_runtime),
        "traditional_attack_implementation": {
            "path": str(attacks_path),
            "sha256": attacks_sha256,
        },
        "attack_conditions": list(ATTACK_CONDITIONS),
        "constraints": CONSTRAINTS,
        "winner_rule": (
            "smallest recovery_threshold satisfying every completeness, clean-FPR, "
            "and per-erasing-IoU constraint"
        ),
    }
    if sha256_file(source_config) != source_config_sha256:
        raise RuntimeError(
            "Formal config changed while the calibration bundle was built."
        )
    if sha256_file(source_manifest) != source_manifest_sha256:
        raise RuntimeError(
            "Formal manifest changed while the calibration bundle was built."
        )
    source_lock_path = Path(source_manifest_lock_audit["lock_path"]).resolve()
    if sha256_file(source_lock_path) != source_manifest_lock_audit["lock_sha256"]:
        raise RuntimeError(
            "Formal manifest lock changed while the calibration bundle was built."
        )
    return config, selected


def main() -> int:
    args = parse_args()
    source = Path(args.source).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    manifest_output = Path(args.manifest_output).expanduser().resolve()
    output_manifest_lock = manifest_lock_path(manifest_output)
    claim_output = claim_path_for_config(output)
    candidate_runs_root = output.parent / "candidate-runs"
    if any(
        os.path.lexists(path)
        for path in (
            output,
            manifest_output,
            output_manifest_lock,
            claim_output,
            candidate_runs_root,
        )
    ):
        raise FileExistsError("Refusing to overwrite an existing calibration bundle.")
    source_sha256 = sha256_file(source)
    config, rows = build_threshold_calibration_bundle(
        source,
        output_config=output,
        output_manifest=manifest_output,
        base_url=args.base_url,
        expected_samples=args.expected_samples,
        seed=args.seed,
        thresholds=args.thresholds,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(
        output,
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
    )
    source_lock_audit = config["threshold_calibration"]["source_formal_manifest_lock"]
    written_manifest = write_manifest(
        rows,
        manifest_output,
        environ={},
        config_path=output,
        upstream_dataset_locks=source_lock_audit.get("upstream_dataset_locks") or {},
    )
    if (
        sha256_file(written_manifest)
        != config["threshold_calibration"]["selected_manifest_sha256"]
    ):
        raise RuntimeError(
            "Written dev manifest does not match the selected-manifest hash."
        )
    calibration_lock_audit = validate_manifest_lock(
        written_manifest,
        rows,
        config_path=output,
        dataset_roots=dataset_roots_from_config(output, environ={}),
    )
    if sha256_file(source) != source_sha256:
        raise RuntimeError(
            "Formal config changed while calibration outputs were written."
        )
    frozen_manifest = Path(
        config["threshold_calibration"]["source_formal_manifest"]
    ).resolve()
    if (
        sha256_file(frozen_manifest)
        != config["threshold_calibration"]["source_formal_manifest_sha256"]
    ):
        raise RuntimeError(
            "Formal manifest changed while calibration outputs were written."
        )
    frozen_lock = Path(source_lock_audit["lock_path"]).resolve()
    if sha256_file(frozen_lock) != source_lock_audit["lock_sha256"]:
        raise RuntimeError(
            "Formal manifest lock changed while calibration outputs were written."
        )
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
                "config": str(output),
                "manifest": str(manifest_output),
                "manifest_lock": str(output_manifest_lock),
                "manifest_lock_sha256": calibration_lock_audit["lock_sha256"],
                "preregistration_claim": preregistration_evidence["source_claim_path"],
                "preregistration_claim_sha256": preregistration_evidence[
                    "source_claim_sha256"
                ],
                "preregistration_nonce": preregistration_evidence["nonce"],
                "samples": len(rows),
                "candidate_thresholds": config["threshold_calibration"][
                    "candidate_thresholds"
                ],
                "traditional_attack_implementation_sha256": config[
                    "threshold_calibration"
                ]["traditional_attack_implementation"]["sha256"],
                "required_attack_runtime": config["threshold_calibration"][
                    "required_attack_runtime"
                ],
                "traditional_attack_artifact_retention": config[
                    "threshold_calibration"
                ]["traditional_attack_artifact_retention"],
                "formal_config_update_performed": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
