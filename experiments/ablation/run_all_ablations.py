from __future__ import annotations

import argparse
import copy
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_ROOT = PROJECT_ROOT / "protection" / "audit_trace"
DEFAULT_CONFIG = AUDIT_ROOT / "configs" / "config.yaml"
DEFAULT_RESULTS = PROJECT_ROOT / "experiments" / "results" / "ablation"
ABLATION_MODES = ("full", "no_watermark", "kgw_only", "protect_only")


def build_ablation_config(
    base_config: dict[str, Any],
    ablation: str,
    output_dir: Path,
) -> dict[str, Any]:
    config = copy.deepcopy(base_config)
    config.setdefault("experiment", {})["ablation"] = ablation
    config.setdefault("paths", {})["output_dir"] = str(output_dir.resolve())
    config["paths"]["output_run_subdir"] = True
    return config


def run_suite(
    config_path: Path,
    results_root: Path,
    mode: str,
    dry_run: bool = False,
) -> list[list[str]]:
    base_config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    commands: list[list[str]] = []
    results_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="cogniguard-ablation-") as temp_dir:
        temp_root = Path(temp_dir)
        for ablation in ABLATION_MODES:
            generated_config = build_ablation_config(
                base_config,
                ablation,
                results_root / ablation,
            )
            generated_path = temp_root / f"{ablation}.yaml"
            generated_path.write_text(
                yaml.safe_dump(generated_config, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            command = [
                sys.executable,
                str(AUDIT_ROOT / "src" / "main.py"),
                "--config",
                str(generated_path),
                "--mode",
                mode,
            ]
            commands.append(command)
            print(f"[ablation:{ablation}] {' '.join(command)}")
            if not dry_run:
                subprocess.run(command, cwd=PROJECT_ROOT, check=True)

    return commands


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the HSW-ST ablation suite."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument(
        "--mode",
        choices=("demo", "experiment"),
        default="experiment",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated commands without loading models.",
    )
    args = parser.parse_args()
    run_suite(
        config_path=args.config.resolve(),
        results_root=args.results_root.resolve(),
        mode=args.mode,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
