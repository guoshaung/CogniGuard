from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from protection.fopd_c2rag_mvp.src.pipeline.run_demo import run_pipeline


def evaluate(config_path: str | Path) -> dict[str, Any]:
    root = Path(config_path).resolve().parent.parent
    return run_pipeline(
        root / "data/profiles.jsonl",
        root / "data/student_questions.jsonl",
        root / "data/teacher_resources.jsonl",
        config_path,
        root / "outputs/unified_results.jsonl",
    )["summary"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    args = ap.parse_args()
    print(evaluate(args.config))


if __name__ == "__main__":
    main()
