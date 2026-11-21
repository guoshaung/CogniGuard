#!/usr/bin/env python3
"""Derive a small, explicitly non-paper pilot config from the frozen config."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any

import yaml


TRADITIONAL_ATTACKS: dict[str, dict[str, Any] | None] = {
    "clean": None,
    "jpeg": {"quality": 70},
    "resize": {"scale": 0.75},
    "gaussian_noise": {"sigma": 5.0},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a reduced, strict-real-pipeline pilot benchmark YAML."
    )
    parser.add_argument("--source", required=True, help="Frozen formal benchmark YAML.")
    parser.add_argument("--output", required=True, help="Run-local pilot YAML to create.")
    parser.add_argument("--max-samples", type=int, default=8)
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args()


def resolve_path(value: str, base: Path) -> Path:
    path = Path(os.path.expandvars(value)).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def manifest_sources(manifest_path: Path) -> set[str]:
    sources: set[str] = set()
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid manifest JSON at line {line_number}: {exc}") from exc
            source = str(row.get("source_dataset") or "").strip()
            if not source:
                raise ValueError(f"Manifest line {line_number} has no source_dataset.")
            sources.add(source)
    if not sources:
        raise ValueError("Pilot manifest is empty.")
    return sources


def select_grid(spec: dict[str, Any], desired: dict[str, Any] | None) -> dict[str, Any]:
    selected = copy.deepcopy(spec)
    grid = selected.get("grid") or []
    if desired is None or not grid:
        return selected
    exact = [row for row in grid if all(row.get(key) == value for key, value in desired.items())]
    selected["grid"] = [copy.deepcopy(exact[0] if exact else grid[0])]
    return selected


def build_pilot_config(
    source_config: Path,
    *,
    output_path: Path,
    max_samples: int,
    seed: int | None,
) -> dict[str, Any]:
    if max_samples < 1:
        raise ValueError("max_samples must be positive.")
    payload = yaml.safe_load(source_config.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("Source benchmark YAML root must be a mapping.")
    config = copy.deepcopy(payload)
    base = source_config.parent

    manifest_cfg = config.get("manifest")
    if not isinstance(manifest_cfg, dict) or not manifest_cfg.get("path"):
        raise ValueError("Source config must define manifest.path.")
    manifest_path = resolve_path(str(manifest_cfg["path"]), base)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Pilot manifest not found: {manifest_path}")
    manifest_cfg["path"] = str(manifest_path)
    sources = manifest_sources(manifest_path)

    selected_datasets: list[dict[str, Any]] = []
    selected_names: set[str] = set()
    for dataset in config.get("datasets") or []:
        if not isinstance(dataset, dict) or not dataset.get("enabled", True):
            continue
        name = str(dataset.get("name") or "").strip()
        if name not in sources:
            continue
        root = resolve_path(str(dataset.get("root") or ""), base)
        if not root.is_dir():
            raise FileNotFoundError(f"Pilot dataset root not found for {name}: {root}")
        selected = copy.deepcopy(dataset)
        selected["root"] = str(root)
        selected["enabled"] = True
        selected_datasets.append(selected)
        selected_names.add(name)
    missing_sources = sorted(sources - selected_names)
    if missing_sources:
        raise ValueError(f"Manifest sources have no available enabled dataset root: {missing_sources}")
    config["datasets"] = selected_datasets

    experiment = config.setdefault("experiment", {})
    configured_seeds = experiment.get("seeds") or []
    chosen_seed = int(seed if seed is not None else configured_seeds[0] if configured_seeds else 20260802)
    experiment["name"] = f"{experiment.get('name', 'cogniguard_image_watermark')}_pilot"
    experiment["strict_paper_mode"] = True
    experiment["fail_fast"] = True
    experiment["run_class"] = "pilot_not_for_paper"
    experiment["paper_eligible"] = False
    experiment["seeds"] = [chosen_seed]
    experiment["max_samples"] = int(max_samples)
    experiment["bootstrap_iterations"] = min(int(experiment.get("bootstrap_iterations", 500)), 500)
    experiment["output_root"] = str((output_path.parent / "benchmark").resolve())
    config["data_requirements"] = {
        "minimum_test_samples": 1,
        "minimum_datasets": 1,
        "minimum_domains": 1,
    }

    methods = [
        copy.deepcopy(method)
        for method in config.get("methods") or []
        if isinstance(method, dict) and method.get("id") == "editguard_wrapper"
    ]
    if len(methods) != 1:
        raise ValueError("Pilot requires exactly one editguard_wrapper method.")
    methods[0]["enabled"] = True
    config["methods"] = methods

    attacks = config.get("attacks") or {}
    traditional_by_name = {
        str(spec.get("name")): spec
        for spec in attacks.get("traditional") or []
        if isinstance(spec, dict)
    }
    selected_traditional: list[dict[str, Any]] = []
    for name, desired in TRADITIONAL_ATTACKS.items():
        if name not in traditional_by_name:
            raise ValueError(f"Source config has no required pilot attack: {name}")
        selected_traditional.append(select_grid(traditional_by_name[name], desired))

    aigc = attacks.get("aigc") or {}
    inpainting = [
        spec
        for spec in aigc.get("specs") or []
        if isinstance(spec, dict) and spec.get("name") == "inpainting"
    ]
    if len(inpainting) != 1:
        raise ValueError("Source config must contain exactly one AIGC inpainting specification.")
    selected_aigc = select_grid(inpainting[0], None)
    if selected_aigc.get("grid"):
        selected_aigc["grid"] = [copy.deepcopy(selected_aigc["grid"][0])]
    config["attacks"] = {
        "traditional": selected_traditional,
        "aigc": {"enabled": True, "specs": [selected_aigc]},
    }
    config["pilot"] = {
        "run_class": "pilot_not_for_paper",
        "paper_eligible": False,
        "derived_from": str(source_config),
        "manifest_sources": sorted(sources),
        "max_samples": int(max_samples),
        "seed": chosen_seed,
    }
    return config


def main() -> int:
    args = parse_args()
    source = Path(args.source).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    config = build_pilot_config(
        source,
        output_path=output,
        max_samples=args.max_samples,
        seed=args.seed,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "created",
                "run_class": "pilot_not_for_paper",
                "config": str(output),
                "max_samples": config["experiment"]["max_samples"],
                "seed": config["experiment"]["seeds"][0],
                "dataset_names": [row["name"] for row in config["datasets"]],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
