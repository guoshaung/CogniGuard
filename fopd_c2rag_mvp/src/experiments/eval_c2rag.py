from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.common.text_utils import write_json
from src.pipeline.run_demo import run_pipeline


def evaluate(config_path: str | Path) -> dict[str, Any]:
    root = Path(config_path).resolve().parent.parent
    result = run_pipeline(
        root / "data/profiles.jsonl",
        root / "data/student_questions.jsonl",
        root / "data/teacher_resources.jsonl",
        config_path,
        root / "outputs/eval_c2rag_results.jsonl",
    )
    rows = result["rows"]
    summary = {
        "PlainRAG_note": "PlainRAG baseline is demonstrated in simulate_attacks.py.",
        "C2RAG_full": result["summary"],
        "variant_count": sum(1 for r in rows if r["return_mode"] == "variant"),
        "quote_count": sum(1 for r in rows if r["return_mode"] == "quote"),
    }
    write_json(root / "outputs/eval_c2rag.json", summary)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    args = ap.parse_args()
    print(evaluate(args.config))


if __name__ == "__main__":
    main()
