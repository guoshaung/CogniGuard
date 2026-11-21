"""Run a pinned, balanced XSTest endpoint slice to measure over-refusal."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import requests

from cogniguard.applications.education.conversation import run_free_chat
from experiments.evaluation.run_cg_jailbreakbench import _refusal_proxy


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "experiments" / "results" / "cg_xstest"
REVISION = "d7bb5bd738c1fcbc36edd83d5e7d1b71a3e2d84d"
URL = f"https://raw.githubusercontent.com/paul-rottger/xstest/{REVISION}/xstest_prompts.csv"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run(per_label: int) -> list[dict[str, Any]]:
    response = requests.get(URL, timeout=30)
    response.raise_for_status()
    source = list(csv.DictReader(response.text.splitlines()))
    selected = [
        row
        for label in ("safe", "unsafe")
        for row in [item for item in source if item["label"] == label][:per_label]
    ]
    rows: list[dict[str, Any]] = []
    for source_row in selected:
        try:
            result = run_free_chat(message=source_row["prompt"])
        except Exception as error:
            rows.append(
                {
                    "id": source_row["id"], "label": source_row["label"], "type": source_row["type"],
                    "prompt_sha256": digest(source_row["prompt"]), "guardrail_decision": "error",
                    "input_blocked": False, "refusal_proxy": False, "answer_length": 0,
                    "error_type": type(error).__name__,
                }
            )
            continue
        guardrail = dict(result.get("guardrail") or {})
        answer = str(result.get("answer") or "")
        decision = str(guardrail.get("decision") or "allow")
        rows.append(
            {
                "id": source_row["id"],
                "label": source_row["label"],
                "type": source_row["type"],
                "prompt_sha256": digest(source_row["prompt"]),
                "guardrail_decision": decision,
                "input_blocked": decision == "block",
                "refusal_proxy": False if decision == "block" else _refusal_proxy(answer),
                "answer_length": len(answer),
                "error_type": "",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-label", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    rows = run(args.per_label)
    safe = [row for row in rows if row["label"] == "safe"]
    unsafe = [row for row in rows if row["label"] == "unsafe"]
    safe_scored = [row for row in safe if row["guardrail_decision"] != "error"]
    unsafe_scored = [row for row in unsafe if row["guardrail_decision"] != "error"]
    summary = {
        "benchmark": "XSTest",
        "dataset_revision": REVISION,
        "scope": "balanced endpoint slice; refusal proxy is not a human or LLM judge",
        "safe_cases": len(safe), "unsafe_cases": len(unsafe),
        "endpoint_error_count": sum(row["guardrail_decision"] == "error" for row in rows),
        "safe_false_block_rate": sum(row["input_blocked"] for row in safe_scored) / len(safe_scored) if safe_scored else None,
        "safe_refusal_proxy_rate": sum(row["refusal_proxy"] for row in safe_scored) / len(safe_scored) if safe_scored else None,
        "unsafe_input_block_rate": sum(row["input_blocked"] for row in unsafe_scored) / len(unsafe_scored) if unsafe_scored else None,
        "unsafe_refusal_proxy_rate_after_allow": (
            sum(row["refusal_proxy"] for row in unsafe_scored if not row["input_blocked"])
            / sum(not row["input_blocked"] for row in unsafe_scored)
            if any(not row["input_blocked"] for row in unsafe_scored) else None
        ),
        "guardrail_balanced_accuracy": (
            (
                sum(row["input_blocked"] for row in unsafe_scored) / len(unsafe_scored)
                + sum(not row["input_blocked"] for row in safe_scored) / len(safe_scored)
            ) / 2
            if safe_scored and unsafe_scored else None
        ),
        "rows": rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "rows"}))


if __name__ == "__main__":
    main()
