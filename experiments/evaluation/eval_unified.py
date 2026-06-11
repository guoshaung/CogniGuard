from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from protection.student_profile.src.pipeline.run_demo import run_pipeline


def evaluate(config_path: str | Path) -> dict[str, Any]:
    root = Path(config_path).resolve().parent.parent
    teacher_root = root.parent / "teacher_resource"
    output_root = Path(__file__).resolve().parents[1] / "results" / "evaluation"
    return run_pipeline(
        root / "data/profiles.jsonl",
        root / "data/student_questions.jsonl",
        teacher_root / "data/teacher_resources.jsonl",
        config_path,
        output_root / "unified_results.jsonl",
    )["summary"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        default="protection/student_profile/configs/default.yaml",
    )
    args = ap.parse_args()
    print(evaluate(args.config))


if __name__ == "__main__":
    main()
