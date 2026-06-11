from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from protection.common.text_utils import write_json
from protection.student_profile.src.pipeline.run_demo import run_pipeline


def evaluate(config_path: str | Path) -> dict[str, Any]:
    student_root = Path(config_path).resolve().parent.parent
    project_root = Path(__file__).resolve().parents[2]
    teacher_root = project_root / "protection" / "teacher_resource"
    output_root = project_root / "experiments" / "results" / "evaluation"
    result = run_pipeline(
        student_root / "data/profiles.jsonl",
        student_root / "data/student_questions.jsonl",
        teacher_root / "data/teacher_resources.jsonl",
        config_path,
        output_root / "eval_c2rag_results.jsonl",
    )
    rows = result["rows"]
    summary = {
        "PlainRAG_note": (
            "PlainRAG baseline is demonstrated in "
            "experiments.attacks.copyright_reconstruction."
        ),
        "C2RAG_full": result["summary"],
        "variant_count": sum(1 for r in rows if r["return_mode"] == "variant"),
        "quote_count": sum(1 for r in rows if r["return_mode"] == "quote"),
    }
    write_json(output_root / "eval_c2rag.json", summary)
    return summary


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
