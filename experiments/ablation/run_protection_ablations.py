from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from experiments.attacks.copyright_reconstruction import simulate as run_c2rag_ablation
from experiments.evaluation.eval_fopd import evaluate as run_fopd_ablation
from protection.common.text_utils import write_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "protection" / "student_profile" / "configs" / "default.yaml"
DEFAULT_RESULTS = PROJECT_ROOT / "experiments" / "results" / "ablation"


def run_suite(config_path: str | Path, results_root: str | Path = DEFAULT_RESULTS) -> dict[str, Any]:
    config_path = Path(config_path)
    results_root = Path(results_root)
    fopd_summary = run_fopd_ablation(config_path)
    c2rag_summary = run_c2rag_ablation(config_path)
    summary = {
        "config": str(config_path.resolve()),
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
        description="Run CogniGuard FOPD/TPCS and C2-RAG component ablations."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args()
    print(run_suite(args.config, args.results_root))


if __name__ == "__main__":
    main()
