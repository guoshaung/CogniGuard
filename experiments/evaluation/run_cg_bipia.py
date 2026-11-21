"""Exercise CG's production retrieval rail with a pinned BIPIA EmailQA slice.

This is a retrieval-boundary metric, not BIPIA's full model-judged ASR.  BIPIA
inserts its public attack strings into untrusted external email content; this
runner measures whether CG marks that content unsafe before it can be composed
into a model context.  Raw emails and attack strings are not persisted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import requests

from cogniguard.protection.cg.nemo_guardrails_adapter import NeMoGuardrailsAdapter
from cogniguard.runtime.mode import DEFAULT_GUARDRAILS_CONFIG


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "experiments" / "results" / "cg_bipia"
REVISION = "a004b69ec0dd446e0afd461d98cb5e96e120a5d0"
RAW = "https://raw.githubusercontent.com/microsoft/BIPIA/{revision}/benchmark/{path}"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def get_json(path: str) -> Any:
    response = requests.get(RAW.format(revision=REVISION, path=path), timeout=30)
    response.raise_for_status()
    return response.json()


def get_jsonl(path: str) -> list[dict[str, Any]]:
    response = requests.get(RAW.format(revision=REVISION, path=path), timeout=30)
    response.raise_for_status()
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def run(limit: int) -> list[dict[str, Any]]:
    contexts = get_jsonl("email/test.jsonl")
    attacks_by_family = get_json("text_attack_test.json")
    attacks = [(family, attack) for family, values in attacks_by_family.items() for attack in values]
    adapter = NeMoGuardrailsAdapter(str(DEFAULT_GUARDRAILS_CONFIG), enabled=True)
    rows: list[dict[str, Any]] = []
    for index in range(limit):
        context = contexts[index % len(contexts)]
        family, attack = attacks[index % len(attacks)]
        # BIPIA's attack is injected into untrusted retrieved content.
        poisoned = f"{context['context']}\n\n{attack}"
        outcome = adapter.check_retrieved_chunks(
            [{"resource_id": f"bipia-email-{index}", "content": poisoned}],
            {"source_trust": "untrusted_external_content", "benchmark": "BIPIA"},
        )
        decision = str(outcome["decision"])
        rows.append(
            {
                "case_index": index,
                "task": "EmailQA",
                "attack_family": family,
                "context_sha256": digest(context["context"]),
                "attack_sha256": digest(attack),
                "rail_decision": decision,
                "matched_policy": str(outcome["matched_policy"]),
                "prevented_before_context_composition": decision in {"sanitize", "block"},
                "label": "injected",
            }
        )
        clean_outcome = adapter.check_retrieved_chunks(
            [{"resource_id": f"bipia-clean-email-{index}", "content": context["context"]}],
            {"source_trust": "untrusted_external_content", "benchmark": "BIPIA-clean-control"},
        )
        clean_decision = str(clean_outcome["decision"])
        rows.append(
            {
                "case_index": index,
                "task": "EmailQA",
                "attack_family": "clean_control",
                "context_sha256": digest(context["context"]),
                "attack_sha256": "",
                "rail_decision": clean_decision,
                "matched_policy": str(clean_outcome["matched_policy"]),
                "prevented_before_context_composition": clean_decision in {"sanitize", "block"},
                "label": "clean",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    rows = run(args.cases)
    injected = [row for row in rows if row["label"] == "injected"]
    clean = [row for row in rows if row["label"] == "clean"]
    tp = sum(row["prevented_before_context_composition"] for row in injected)
    fp = sum(row["prevented_before_context_composition"] for row in clean)
    recall = tp / len(injected) if injected else None
    precision = tp / (tp + fp) if tp + fp else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall and precision + recall else 0.0
    summary = {
        "benchmark": "microsoft/BIPIA",
        "dataset_revision": REVISION,
        "scope": "EmailQA retrieval-rail detection; not BIPIA's model-judged ASR",
        "injected_cases": len(injected),
        "clean_control_cases": len(clean),
        "prevented_before_context_composition_rate": recall,
        "clean_content_false_isolation_rate": fp / len(clean) if clean else None,
        "isolation_precision": precision,
        "isolation_f1": f1,
        "rows": rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "rows"}))


if __name__ == "__main__":
    main()
