from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any

from experiments.mmfopd_v3.baselines import METHODS
from protection.common.schemas import StudentProfile, Task
from protection.common.text_utils import read_jsonl
from protection.student_profile.src.fopd.context_card import build_context_card
from protection.student_profile.src.pipeline.run_demo import load_config


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "experiments" / "datasets" / "cogniguard_math_suite" / "mixed_math_suite" / "student_profile" / "data"
DEFAULT_CONFIG = ROOT / "protection" / "student_profile" / "configs" / "default.yaml"
DEFAULT_OUTPUT = ROOT / "experiments" / "results" / "mmfopd_v3_pilot"


def _task(row: dict[str, Any]) -> Task:
    return Task(
        request_id=str(row["request_id"]),
        student_id=str(row["student_id"]),
        question=str(row["question"]),
        knowledge=str(row.get("expected_knowledge") or row.get("knowledge") or ""),
        difficulty=str(row.get("difficulty", "")),
        need_resource=bool(row.get("need_resource", False)),
    )


def _metrics(profile: StudentProfile, task: Task, selected: list[Any]) -> dict[str, float | int]:
    selected_records = [item.record for item in selected]
    selected_ids = {record.record_id for record in selected_records}
    relevant = [record for record in profile.profile_records if record.knowledge == task.knowledge]
    relevant_ids = {record.record_id for record in relevant}
    total_sensitivity = sum(max(0.0, record.sensitivity) for record in profile.profile_records)
    exposed_sensitivity = sum(max(0.0, record.sensitivity) for record in selected_records)
    sensitive = [record for record in profile.profile_records if record.sensitivity >= 0.7]
    exposed_sensitive = [record for record in selected_records if record.sensitivity >= 0.7]
    released_card, _ = build_context_card(profile, task, selected)
    sensitive_values = {str(record.value).lower() for record in sensitive if str(record.value)}
    released_sensitive = sum(1 for value in sensitive_values if value in released_card.lower())
    released_value_exposure = {}
    for threshold, key in ((0.5, "released_value_exposure_t05"), (0.6, "released_value_exposure_t06"), (0.7, "released_value_exposure_t07"), (0.8, "released_value_exposure_t08")):
        values = {str(record.value).lower() for record in profile.profile_records if record.sensitivity >= threshold and str(record.value)}
        released_value_exposure[key] = sum(1 for value in values if value in released_card.lower()) / len(values) if values else 0.0
    # Field-level units prevent identical record counts from producing identical
    # utility. A task normally requires state, error and teaching preference;
    # state/behavior are optional evidence rather than mandatory facts.
    required_units = {"knowledge_state", "error_pattern", "teaching_preference"}
    unit_by_type = {
        "mastery": "knowledge_state",
        "error_pattern": "error_pattern",
        "preference": "teaching_preference",
        "learning_state": "learning_state",
        "behavior_aggregate": "behavior",
        "multimodal_summary": "multimodal",
    }
    relevant_units = {
        unit_by_type.get(record.type, record.type)
        for record in relevant
        if record.type in unit_by_type
    }
    selected_units = {
        unit_by_type.get(record.type, record.type)
        for record in selected_records
        if record.knowledge == task.knowledge and record.type in unit_by_type
    }
    unit_relevant_recall = len(selected_units & required_units) / len(required_units)
    unit_f1 = 2 * unit_relevant_recall * (len(selected_units & relevant_units) / len(selected_units)) / (unit_relevant_recall + (len(selected_units & relevant_units) / len(selected_units))) if selected_units and (unit_relevant_recall + (len(selected_units & relevant_units) / len(selected_units))) else 0.0
    return {
        "selected_count": len(selected_records),
        "weighted_profile_exposure": exposed_sensitivity / total_sensitivity if total_sensitivity else 0.0,
        "selection_privacy_cost": exposed_sensitivity / total_sensitivity if total_sensitivity else 0.0,
        "released_profile_exposure": min(1.0, len(released_card) / max(1, sum(len(str(record.value)) for record in profile.profile_records))),
        "released_sensitive_attribute_exposure": released_sensitive / len(sensitive_values) if sensitive_values else 0.0,
        **released_value_exposure,
        "required_unit_recall": unit_relevant_recall,
        "unit_precision": len(selected_units & relevant_units) / len(selected_units) if selected_units else 0.0,
        "unit_reconstruction_f1": unit_f1,
        "irrelevant_unit_exposure": len(selected_units - relevant_units) / len(selected_units) if selected_units else 0.0,
        "sensitive_attribute_exposure": len(exposed_sensitive) / len(sensitive) if sensitive else 0.0,
        "sensitive_exposure_t05": sum(record.sensitivity >= 0.5 for record in selected_records) / max(1, sum(record.sensitivity >= 0.5 for record in profile.profile_records)),
        "sensitive_exposure_t06": sum(record.sensitivity >= 0.6 for record in selected_records) / max(1, sum(record.sensitivity >= 0.6 for record in profile.profile_records)),
        "sensitive_exposure_t08": sum(record.sensitivity >= 0.8 for record in selected_records) / max(1, sum(record.sensitivity >= 0.8 for record in profile.profile_records)),
        "mean_selected_sensitivity": exposed_sensitivity / len(selected_records) if selected_records else 0.0,
        "irrelevant_exposure_rate": len(selected_ids - relevant_ids) / len(selected_ids) if selected_ids else 0.0,
        "task_relevant_information_recall": len(selected_ids & relevant_ids) / len(relevant_ids) if relevant_ids else 0.0,
        # Exact field recovery is the deterministic lower-bound attacker. LLM and embedding attackers follow later.
        "exact_profile_reconstruction_recall": len(selected_ids) / len(profile.profile_records) if profile.profile_records else 0.0,
    }


def run(*, data_root: Path, config_path: Path, output: Path, split: str = "test") -> dict[str, Any]:
    from .graph import run_mm_graph
    return run_mm_graph(data_root=data_root, config_path=config_path,
                        output=output, split=split)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--split", choices=("train", "dev", "test"), default="test")
    args = parser.parse_args()
    print(json.dumps(run(data_root=args.data_root, config_path=args.config, output=args.output, split=args.split), indent=2))


if __name__ == "__main__":
    main()
