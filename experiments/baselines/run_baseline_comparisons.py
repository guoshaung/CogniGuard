from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from experiments.attacks.copyright_reconstruction import simulate as run_copyright_baselines
from experiments.evaluation.eval_fopd import evaluate as run_privacy_baselines
from experiments.common.sequential_suite_graph import run_sequential_suite
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
    student_data_root: str | Path | None = None,
    teacher_data_root: str | Path | None = None,
) -> dict[str, Any]:
    config_path = Path(config_path)
    results_root = Path(results_root)
    steps = [("prepare", lambda: results_root.mkdir(parents=True, exist_ok=True))]
    if not copyright_only:
        steps.append(("privacy", lambda: run_privacy_baselines(
            config_path, student_data_root=student_data_root,
            results_root=results_root)))
    if not privacy_only:
        steps.append(("copyright", lambda: run_copyright_baselines(
            config_path, teacher_data_root=teacher_data_root,
            results_root=results_root)))
    results = run_sequential_suite(steps)
    privacy_summary = results.get("privacy")
    copyright_summary = results.get("copyright")

    summary = {
        "config": str(config_path.resolve()),
        "student_data_root": str(Path(student_data_root).resolve()) if student_data_root else None,
        "teacher_data_root": str(Path(teacher_data_root).resolve()) if teacher_data_root else None,
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
    parser.add_argument("--student-data-root", type=Path)
    parser.add_argument("--teacher-data-root", type=Path)
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
            student_data_root=args.student_data_root,
            teacher_data_root=args.teacher_data_root,
        )
    )


if __name__ == "__main__":
    main()
