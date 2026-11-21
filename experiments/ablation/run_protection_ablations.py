from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from experiments.attacks.copyright_reconstruction import simulate as run_c2rag_ablation
from experiments.evaluation.eval_fopd import evaluate as run_fopd_ablation
from experiments.common.sequential_suite_graph import run_sequential_suite
from protection.common.text_utils import write_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "protection" / "student_profile" / "configs" / "default.yaml"
DEFAULT_RESULTS = PROJECT_ROOT / "experiments" / "results" / "ablation"


def run_suite(
    config_path: str | Path,
    results_root: str | Path = DEFAULT_RESULTS,
    *,
    student_data_root: str | Path | None = None,
    teacher_data_root: str | Path | None = None,
) -> dict[str, Any]:
    config_path = Path(config_path)
    results_root = Path(results_root)
    results = run_sequential_suite([
        ("fopd", lambda: run_fopd_ablation(
            config_path, student_data_root=student_data_root,
            results_root=results_root)),
        ("c2rag", lambda: run_c2rag_ablation(
            config_path, teacher_data_root=teacher_data_root,
            results_root=results_root)),
    ])
    fopd_summary = results["fopd"]
    c2rag_summary = results["c2rag"]
    summary = {
        "config": str(config_path.resolve()),
        "student_data_root": str(Path(student_data_root).resolve()) if student_data_root else None,
        "teacher_data_root": str(Path(teacher_data_root).resolve()) if teacher_data_root else None,
        "fopd_component_ablation": fopd_summary,
        "c2rag_component_ablation": c2rag_summary,
        "artifacts": {
            "fopd": str((results_root / "fopd_component_ablation.json").resolve()),
            "c2rag": str((results_root / "c2rag_component_ablation.json").resolve()),
        },
    }
    write_json(results_root / "protection_component_ablation_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run CogniGuard FOPD/CG and C2-RAG component ablations."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--student-data-root", type=Path)
    parser.add_argument("--teacher-data-root", type=Path)
    args = parser.parse_args()
    print(
        run_suite(
            args.config,
            args.results_root,
            student_data_root=args.student_data_root,
            teacher_data_root=args.teacher_data_root,
        )
    )


if __name__ == "__main__":
    main()
