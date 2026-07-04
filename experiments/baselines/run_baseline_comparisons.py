from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from experiments.attacks.copyright_reconstruction import simulate as run_copyright_baselines
from experiments.evaluation.eval_fopd import evaluate as run_privacy_baselines
from protection.common.text_utils import write_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "protection" / "student_profile" / "configs" / "default.yaml"
DEFAULT_RESULTS = PROJECT_ROOT / "experiments" / "results" / "baselines"


def run_suite(
    config_path: str | Path = DEFAULT_CONFIG,
    results_root: str | Path = DEFAULT_RESULTS,
    *,
    privacy_only: bool = False,
    copyright_only: bool = False,
) -> dict[str, Any]:
    config_path = Path(config_path)
    results_root = Path(results_root)
    results_root.mkdir(parents=True, exist_ok=True)

    privacy_summary = None
    copyright_summary = None
    if not copyright_only:
        privacy_summary = run_privacy_baselines(config_path)
    if not privacy_only:
        copyright_summary = run_copyright_baselines(config_path)

    summary = {
        "config": str(config_path.resolve()),
        "privacy_baselines": privacy_summary,
        "copyright_baselines": copyright_summary,
        "artifacts": {
            "privacy_rows_csv": str((results_root / "privacy_baseline_comparison_rows.csv").resolve()),
            "privacy_summary_csv": str((results_root / "privacy_baseline_comparison_summary.csv").resolve()),
            "copyright_rows_csv": str((results_root / "copyright_baseline_comparison_rows.csv").resolve()),
            "copyright_summary_csv": str((results_root / "copyright_baseline_comparison_summary.csv").resolve()),
        },
    }
    write_json(results_root / "baseline_comparison_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run CogniGuard external privacy and copyright baseline comparisons."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--privacy-only", action="store_true")
    group.add_argument("--copyright-only", action="store_true")
    args = parser.parse_args()
    print(
        run_suite(
            args.config,
            args.results_root,
            privacy_only=args.privacy_only,
            copyright_only=args.copyright_only,
        )
    )


if __name__ == "__main__":
    main()
