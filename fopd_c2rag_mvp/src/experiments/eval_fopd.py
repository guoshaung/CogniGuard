from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.common.text_utils import write_json
from src.fopd.context_card import build_context_card
from src.fopd.fopd_metrics import compute_fopd_metrics
from src.fopd.profile_selector import ProfileSelector, ScoredProfileRecord
from src.fopd.task_parser import parse_task
from src.pipeline.run_demo import load_config, load_profiles
from src.common.text_utils import read_jsonl


def evaluate(config_path: str | Path) -> dict[str, Any]:
    config = load_config(config_path)
    root = Path(config_path).resolve().parent.parent
    profiles = load_profiles(root / "data/profiles.jsonl")
    questions = read_jsonl(root / "data/student_questions.jsonl")
    selector = ProfileSelector(config)
    rows: list[dict[str, Any]] = []

    for qrow in questions:
        task = parse_task(qrow)
        profile = profiles[task.student_id]
        selected = selector.select(profile, task)
        card, _ = build_context_card(profile, task, selected)
        rows.append({"method": "FOPD-v0", **compute_fopd_metrics(profile, task, card, selected)})

        rows.append(
            {
                "method": "NoProfile",
                "CardLen": 0,
                "SelectedCount": 0,
                "PER": 0.0,
                "TaskCoverage": 0.0,
                "SensitiveLeakFlag": 0,
            }
        )
        full_selected = [
            ScoredProfileRecord(record=r, score=1.0, components={}) for r in profile.profile_records
        ]
        full_card = "\n".join(str(r.value) for r in profile.profile_records) + "\n" + str(profile.local_only_fields)
        rows.append({"method": "FullProfile", **compute_fopd_metrics(profile, task, full_card, full_selected)})
        rule_selected = [
            ScoredProfileRecord(record=r, score=1.0, components={})
            for r in profile.profile_records
            if r.type in {"mastery", "error_pattern", "preference"}
        ][:3]
        rule_card, _ = build_context_card(profile, task, rule_selected)
        rows.append({"method": "RuleSummary", **compute_fopd_metrics(profile, task, rule_card, rule_selected)})

    summary: dict[str, Any] = {}
    for method in sorted({r["method"] for r in rows}):
        subset = [r for r in rows if r["method"] == method]
        summary[method] = {
            "avg_PER": sum(float(r["PER"]) for r in subset) / len(subset),
            "avg_TaskCoverage": sum(float(r["TaskCoverage"]) for r in subset) / len(subset),
            "leak_count": sum(int(r["SensitiveLeakFlag"]) for r in subset),
        }
    out = root / "outputs/eval_fopd.json"
    write_json(out, {"rows": rows, "summary": summary})
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    args = ap.parse_args()
    print(evaluate(args.config))


if __name__ == "__main__":
    main()
