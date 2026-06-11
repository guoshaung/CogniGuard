from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from protection.teacher_resource.src.c2rag.exposure_budget import ExposureBudget
from protection.teacher_resource.src.c2rag.return_policy import produce_controlled_resource
from protection.common.schemas import TeacherResource
from protection.common.text_utils import cosine_text, lcs_ratio, read_jsonl, write_json
from protection.student_profile.src.pipeline.run_demo import load_config, load_resources


def plain_rag_response(resource: TeacherResource, round_idx: int) -> str:
    if round_idx == 0:
        return resource.content[:30]
    if round_idx < 3:
        return resource.content[: min(len(resource.content), 45 + round_idx * 12)]
    return resource.content


def leakage_score(text: str, resource: TeacherResource) -> float:
    return max(cosine_text(text, resource.content), lcs_ratio(text, resource.content))


def simulate(config_path: str | Path) -> dict[str, Any]:
    config = load_config(config_path)
    project_root = Path(__file__).resolve().parents[2]
    teacher_root = project_root / "protection" / "teacher_resource"
    experiment_root = project_root / "experiments"
    resources = load_resources(teacher_root / "data/teacher_resources.jsonl")
    attacks = read_jsonl(
        experiment_root / "attacks" / "data" / "copyright_attack_cases.jsonl"
    )
    resource = max(resources, key=lambda r: r.copyright_level)
    budget = ExposureBudget(config)
    rows: list[dict[str, Any]] = []

    for idx, attack in enumerate(attacks):
        plain = plain_rag_response(resource, idx)
        controlled = produce_controlled_resource(resource, budget, config)
        rows.append(
            {
                "round": idx + 1,
                "attack_id": attack.get("attack_id", f"atk_{idx+1:03d}"),
                "prompt": attack.get("prompt", ""),
                "method": "PlainRAG",
                "return_mode": "quote",
                "output": plain,
                "leakage": leakage_score(plain, resource),
                "exposure": idx + 1,
            }
        )
        rows.append(
            {
                "round": idx + 1,
                "attack_id": attack.get("attack_id", f"atk_{idx+1:03d}"),
                "prompt": attack.get("prompt", ""),
                "method": "C2RAG-full",
                "return_mode": controlled.mode,
                "output": controlled.text,
                "leakage": leakage_score(controlled.text, resource),
                "exposure": controlled.exposure_after,
            }
        )

    output_root = experiment_root / "results" / "attacks"
    out_csv = output_root / "copyright_reconstruction.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "plain_avg_leakage": sum(r["leakage"] for r in rows if r["method"] == "PlainRAG") / len(attacks),
        "c2rag_avg_leakage": sum(r["leakage"] for r in rows if r["method"] == "C2RAG-full") / len(attacks),
        "c2rag_modes": [r["return_mode"] for r in rows if r["method"] == "C2RAG-full"],
    }
    write_json(output_root / "copyright_reconstruction_summary.json", summary)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        default="protection/student_profile/configs/default.yaml",
    )
    args = ap.parse_args()
    print(simulate(args.config))


if __name__ == "__main__":
    main()
