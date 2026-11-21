#!/usr/bin/env python3
"""Build an isolated synthetic-dev watermark tuning bundle.

The generated manifest contains only the frozen CogniGuard-EduFig development
split. Train and test records never enter the run-local manifest, so a tuning
run cannot accidentally consume the pilot/formal test split.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml


RUN_CLASS = "dev_tuning"
SOURCE_DATASET = "cogniguard_edufig_v2"
SOURCE_SPLIT = "dev"
EXPECTED_SAMPLES = 117
EXPECTED_DOMAINS = 9
DEFAULT_SEED = 20260802
SUBSET_POLICY = "sha256(seed|dev-tuning-subset-v2|sample_id), first N"
DEFAULT_ATTACK_PROFILE = "baseline"
BASELINE_ATTACKS: tuple[tuple[str, tuple[dict[str, Any], ...] | None], ...] = (
    ("clean", None),
    ("jpeg", ({"quality": 70},)),
    ("gaussian_noise", ({"sigma": 5.0},)),
    ("resize", ({"scale": 0.75},)),
)
SELECTION_GRID_ATTACKS: tuple[
    tuple[str, tuple[dict[str, Any], ...] | None], ...
] = (
    ("clean", None),
    ("jpeg", ({"quality": 90}, {"quality": 70}, {"quality": 50})),
    (
        "gaussian_noise",
        ({"sigma": 2.0}, {"sigma": 5.0}, {"sigma": 10.0}),
    ),
)
ATTACK_PROFILES = {
    "baseline": BASELINE_ATTACKS,
    "selection-grid": SELECTION_GRID_ATTACKS,
}
ATTACK_CONDITIONS = {
    "baseline": (
        "clean",
        "jpeg_quality_70",
        "gaussian_noise_sigma_5.0",
        "resize_scale_0.75",
    ),
    "selection-grid": (
        "clean",
        "jpeg_quality_90",
        "jpeg_quality_70",
        "jpeg_quality_50",
        "gaussian_noise_sigma_2.0",
        "gaussian_noise_sigma_5.0",
        "gaussian_noise_sigma_10.0",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a run-local, development-only watermark tuning config."
    )
    parser.add_argument("--source", required=True, help="Frozen formal benchmark YAML.")
    parser.add_argument("--output", required=True, help="Run-local dev-tuning YAML.")
    parser.add_argument(
        "--manifest-output", required=True, help="Run-local dev-only JSONL manifest."
    )
    parser.add_argument(
        "--source-manifest",
        default=None,
        help="Optional source manifest override; otherwise use source YAML manifest.path.",
    )
    parser.add_argument("--expected-samples", type=int, default=EXPECTED_SAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--attack-profile",
        choices=tuple(ATTACK_PROFILES),
        default=DEFAULT_ATTACK_PROFILE,
        help="Frozen traditional-attack profile for this dev-only run.",
    )
    return parser.parse_args()


def resolve_path(value: str, base: Path) -> Path:
    path = Path(os.path.expandvars(value)).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid source manifest JSON at line {line_number}: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise ValueError(f"Source manifest line {line_number} is not an object.")
            rows.append(row)
    if not rows:
        raise ValueError("Source manifest is empty.")
    return rows


def manifest_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )


def select_attack(
    source: dict[str, Any], desired_grid: tuple[dict[str, Any], ...] | None
) -> dict[str, Any]:
    selected = copy.deepcopy(source)
    grid = list(selected.get("grid") or [])
    if desired_grid is None:
        if grid:
            raise ValueError(f"Clean attack unexpectedly defines a grid: {grid}")
        selected.pop("grid", None)
        return selected
    if not desired_grid:
        raise ValueError(f"Attack {source.get('name')!r} has an empty desired grid.")
    selected_grid: list[dict[str, Any]] = []
    for desired in desired_grid:
        exact = [row for row in grid if isinstance(row, dict) and row == desired]
        if len(exact) != 1:
            raise ValueError(
                f"Attack {source.get('name')!r} must contain exactly one grid row "
                f"{desired!r}."
            )
        selected_grid.append(copy.deepcopy(exact[0]))
    selected["grid"] = selected_grid
    return selected


def build_dev_tuning_bundle(
    source_config: Path,
    *,
    output_config: Path,
    output_manifest: Path,
    source_manifest_override: Path | None = None,
    expected_samples: int = EXPECTED_SAMPLES,
    seed: int = DEFAULT_SEED,
    attack_profile: str = DEFAULT_ATTACK_PROFILE,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if expected_samples != EXPECTED_SAMPLES:
        raise ValueError(
            f"This frozen dev-tuning protocol requires exactly {EXPECTED_SAMPLES} samples."
        )
    if seed < 0:
        raise ValueError("Seed must be non-negative.")
    if attack_profile not in ATTACK_PROFILES:
        allowed = ", ".join(sorted(ATTACK_PROFILES))
        raise ValueError(
            f"Unknown dev-tuning attack profile {attack_profile!r}; expected one of: "
            f"{allowed}."
        )
    attack_specs = ATTACK_PROFILES[attack_profile]
    attack_conditions = ATTACK_CONDITIONS[attack_profile]
    source_config = source_config.expanduser().resolve()
    payload = yaml.safe_load(source_config.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("Source benchmark YAML root must be a mapping.")
    base = source_config.parent

    manifest_cfg = payload.get("manifest")
    if not isinstance(manifest_cfg, dict) or not manifest_cfg.get("path"):
        raise ValueError("Source config must define manifest.path.")
    source_manifest = (
        source_manifest_override.expanduser().resolve()
        if source_manifest_override is not None
        else resolve_path(str(manifest_cfg["path"]), base)
    )
    if not source_manifest.is_file():
        raise FileNotFoundError(f"Source manifest not found: {source_manifest}")
    all_rows = read_manifest(source_manifest)
    eligible_rows = sorted(
        (
            copy.deepcopy(row)
            for row in all_rows
            if row.get("source_dataset") == SOURCE_DATASET
            and row.get("split") == SOURCE_SPLIT
        ),
        key=lambda row: str(row.get("sample_id") or ""),
    )
    if len(eligible_rows) < expected_samples:
        raise ValueError(
            f"Expected at least {expected_samples} {SOURCE_DATASET}/{SOURCE_SPLIT} rows; "
            f"found {len(eligible_rows)}."
        )
    selected_rows = sorted(
        eligible_rows,
        key=lambda row: hashlib.sha256(
            (
                f"{seed}|dev-tuning-subset-v2|"
                f"{str(row.get('sample_id') or '')}"
            ).encode("utf-8")
        ).hexdigest(),
    )[:expected_samples]
    selected_rows.sort(key=lambda row: str(row.get("sample_id") or ""))
    sample_ids = [str(row.get("sample_id") or "") for row in selected_rows]
    if any(not sample_id for sample_id in sample_ids) or len(set(sample_ids)) != len(sample_ids):
        raise ValueError("Selected dev rows must have unique, non-empty sample_id values.")
    test_ids = {
        str(row.get("sample_id") or "")
        for row in all_rows
        if row.get("split") == "test"
    }
    if set(sample_ids) & test_ids:
        raise ValueError("Development and test sample_id sets overlap.")
    domains = {str(row.get("domain") or "") for row in selected_rows}
    if "" in domains or len(domains) != EXPECTED_DOMAINS:
        raise ValueError(
            f"Expected exactly {EXPECTED_DOMAINS} non-empty dev domains; found {len(domains)}."
        )

    datasets = [
        copy.deepcopy(dataset)
        for dataset in payload.get("datasets") or []
        if isinstance(dataset, dict)
        and dataset.get("enabled", True)
        and dataset.get("name") == SOURCE_DATASET
    ]
    if len(datasets) != 1:
        raise ValueError(f"Source config must enable exactly one {SOURCE_DATASET} dataset.")
    dataset_root = resolve_path(str(datasets[0].get("root") or ""), base)
    if not dataset_root.is_dir():
        raise FileNotFoundError(f"Synthetic dataset root not found: {dataset_root}")
    datasets[0]["root"] = str(dataset_root)
    datasets[0]["enabled"] = True

    methods = [
        copy.deepcopy(method)
        for method in payload.get("methods") or []
        if isinstance(method, dict) and method.get("id") == "editguard_wrapper"
    ]
    if len(methods) != 1:
        raise ValueError("Dev tuning requires exactly one editguard_wrapper method.")
    methods[0]["enabled"] = True

    attacks = payload.get("attacks") or {}
    traditional_by_name: dict[str, list[dict[str, Any]]] = {}
    for spec in attacks.get("traditional") or []:
        if isinstance(spec, dict):
            traditional_by_name.setdefault(str(spec.get("name")), []).append(spec)
    selected_attacks: list[dict[str, Any]] = []
    for name, desired_grid in attack_specs:
        matches = traditional_by_name.get(name, [])
        if len(matches) != 1:
            raise ValueError(f"Source config has no unique required attack: {name}")
        selected_attacks.append(select_attack(matches[0], desired_grid))
    selected_condition_count = sum(
        len(attack.get("grid") or []) or 1 for attack in selected_attacks
    )
    if selected_condition_count != len(attack_conditions):
        raise ValueError(
            f"Attack profile {attack_profile!r} expands to {selected_condition_count} "
            f"conditions, but declares {len(attack_conditions)} canonical conditions."
        )

    output_config = output_config.expanduser().resolve()
    output_manifest = output_manifest.expanduser().resolve()
    selected_manifest_text = manifest_text(selected_rows)
    config = copy.deepcopy(payload)
    config["experiment"] = {
        "name": "cogniguard_image_watermark_synthetic_dev_tuning",
        "strict_paper_mode": True,
        "fail_fast": True,
        "run_class": RUN_CLASS,
        "paper_eligible": False,
        "split": SOURCE_SPLIT,
        "seeds": [int(seed)],
        "max_samples": expected_samples,
        "api_timeout_seconds": int(
            (payload.get("experiment") or {}).get("api_timeout_seconds", 900)
        ),
        "bootstrap_iterations": 2000,
        "bootstrap_seed": int(seed),
        "output_root": str((output_config.parent / "benchmark").resolve()),
    }
    config["manifest"] = {"path": str(output_manifest), "verify_hashes": True}
    config["data_requirements"] = {
        "minimum_selected_samples": expected_samples,
        "minimum_test_samples": expected_samples,
        "minimum_datasets": 1,
        "minimum_domains": EXPECTED_DOMAINS,
    }
    config["metrics"] = {
        "require_reference_ssim": True,
        "lpips": {"enabled": False, "required": False},
    }
    config["datasets"] = datasets
    config["methods"] = methods
    config["attacks"] = {
        "traditional": selected_attacks,
        "aigc": {"enabled": False, "specs": []},
    }
    config["dev_tuning"] = {
        "run_class": RUN_CLASS,
        "attack_profile": attack_profile,
        "paper_eligible": False,
        "tuning_only": True,
        "source_dataset": SOURCE_DATASET,
        "source_split": SOURCE_SPLIT,
        "eligible_source_dev_samples": len(eligible_rows),
        "expected_samples": expected_samples,
        "selection_policy": SUBSET_POLICY,
        "expected_rows": expected_samples * len(attack_conditions),
        "test_samples_consumed": 0,
        "golden_test_consumed": False,
        "pilot_outputs_reused": False,
        "excluded_splits": ["train", "test"],
        "decoder_mode": "identity_single_view",
        "multi_view_enabled": False,
        "registry_hamming_radii_evaluated": [1],
        "source_manifest": str(source_manifest),
        "source_manifest_sha256": sha256_file(source_manifest),
        "selected_manifest_sha256": hashlib.sha256(
            selected_manifest_text.encode("utf-8")
        ).hexdigest(),
        "selected_sample_ids_sha256": hashlib.sha256(
            "\n".join(sample_ids).encode("utf-8")
        ).hexdigest(),
        "attack_conditions": list(attack_conditions),
        "aigc_enabled": False,
        "lpips_enabled": False,
        "frozen_service_parameters": {
            "recovery_threshold": 0.28,
            "tamper_area_threshold": 0.001,
            "registry_hamming_radius": 1,
        },
    }
    return config, selected_rows


def main() -> int:
    args = parse_args()
    source = Path(args.source).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    manifest_output = Path(args.manifest_output).expanduser().resolve()
    source_manifest = (
        Path(args.source_manifest).expanduser().resolve()
        if args.source_manifest
        else None
    )
    if output.exists() or manifest_output.exists():
        raise FileExistsError("Refusing to overwrite an existing dev-tuning bundle.")
    config, selected_rows = build_dev_tuning_bundle(
        source,
        output_config=output,
        output_manifest=manifest_output,
        source_manifest_override=source_manifest,
        expected_samples=args.expected_samples,
        seed=args.seed,
        attack_profile=args.attack_profile,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(manifest_text(selected_rows), encoding="utf-8")
    output.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "created",
                "run_class": RUN_CLASS,
                "paper_eligible": False,
                "config": str(output),
                "manifest": str(manifest_output),
                "samples": len(selected_rows),
                "split": SOURCE_SPLIT,
                "dataset": SOURCE_DATASET,
                "attack_profile": config["dev_tuning"]["attack_profile"],
                "expected_rows": config["dev_tuning"]["expected_rows"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
