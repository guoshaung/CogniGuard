"""Record admission metadata and integrity; no baseline scoring."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("r38_prepare", HERE / "prepare.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
OUT = module.OUT

BASELINES = [
    ("keyword_ngram", "DIRECT_COMPONENT", "NOT_RUN", "stdlib lexical overlap; not relation risk truth"),
    ("MiniLM", "NEEDS_ADAPTATION", "NOT_LOADED", "weights present; English model; pooling/runtime and Chinese admission pending"),
    ("fixed_LLM_Judge", "NEEDS_ADAPTATION", "NOT_RUN", "GGUF files only; pinned runtime/model suitability not admitted; prompt draft only"),
    ("mature_NLI_semantic_parser", "UNAVAILABLE_CURRENT_ENV", "NOT_RUN", "no trained NLI checkpoint located; generator/ranker cannot substitute"),
    ("VeriScore", "UNAVAILABLE_CURRENT_ENV", "NOT_RUN", "official implementation exists; local package/models/search adapter missing"),
    ("AlignScore", "UNAVAILABLE_CURRENT_ENV", "NOT_RUN", "official code/checkpoint exists; local package/checkpoint/spacy absent; language adaptation pending"),
    ("semantic_binding_exact_closure", "NEEDS_ADAPTATION", "NOT_RUN", "exact backend available; general NL front-end not admitted"),
    ("human_relations_exact_closure", "OFFLINE_UPPER_BOUND_ONLY", "PENDING_HUMAN_REVIEW", "no human relations yet; cannot be online baseline"),
    ("OCELOT_evidence_verification", "UNAVAILABLE_CURRENT_ARTIFACTS", "NOT_RUN", "paper reviewed; sufficient author runtime/weights/calibration not located"),
    ("registered_catalogue_exact_closure", "DIRECT_COMPONENT", "NOT_RUN", "existing infer() runnable with stdlib; unsupported paraphrase means UNKNOWN, not general-NL result"),
]


def main():
    with (OUT / "BASELINE_ADMISSION.csv").open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["baseline", "admission", "actual_execution", "reason"])
        writer.writerows(BASELINES)
    records = module.read(OUT / "researcher_only/case_construction.json")
    with (OUT / "researcher_only/CASE_REGISTER.csv").open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["internal_id", "visible_case_id", "construction_condition", "turns",
                         "annotation_status", "gold_complete", "ambiguity_status"])
        for record in records:
            writer.writerow([record["internal_id"], record["visible_case_id"],
                             record["construction_condition"], len(record["visible"]["turns"]),
                             "PENDING_HUMAN_REVIEW", "", "SEE_DATA_QUALITY_NOT_A_GOLD_LABEL"])
    source_checks = []
    for a in module.ASSETS:
        p = module.read(module.SOURCE / "private" / f"{a}.json")
        actual = module.digest((module.SOURCE / "documents" / f"{a}.md").read_bytes())
        source_checks.append({"asset_id": a, "private_declared_document_hash_matches": actual == p["original_material"]["sha256"]})
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                         text=True, check=True, timeout=10).stdout.strip()
    module.write(OUT / "CODE_VERSION.json", {
        "base_git_HEAD_not_clean_tree_version": git,
        "workspace_had_preexisting_changes": True,
        "source_script_hashes": {p.name: module.digest(p.read_bytes()) for p in sorted(HERE.iterdir()) if p.is_file()},
        "commands": [
            ".venv-langgraph/Scripts/python.exe -B experiments/c2rag_r38_semantic_admission_20261029_01/prepare.py",
            ".venv-langgraph/Scripts/python.exe -B experiments/c2rag_r38_semantic_admission_20261029_01/validate.py",
            ".venv-langgraph/Scripts/python.exe -B experiments/c2rag_r38_semantic_admission_20261029_01/finalize.py",
        ],
        "manual_deliverables": ["REPORT.md", "DATA_QUALITY.md", "ANNOTATION_GUIDE.md", "BASELINE_ADMISSION.md", "JUDGE_PROMPT_DRAFT.txt", "decision.json"],
        "reproduction_scope": "prepare.py regenerates cases, source register, packets and environment metadata; hand-written audit prose is retained as source deliverables",
    })
    module.write(OUT / "FINAL_QA.json", {
        "preparation_validation": module.read(OUT / "VALIDATION.json")["status"],
        "source_document_identity": source_checks,
        "source_r37_remote_bytes_verified": all(c["byte_equal"] for c in module.read(OUT / "REMOTE_EVIDENCE_CHECK.json")),
        "all_24_gold_labels_pending": all(c["expected_leak_label"] is None for c in records),
        "independent_humans_completed": 0, "mature_strong_NL_baselines_admitted": 0,
        "new_method_scores": None, "metrics_not_tested_are_not_zero": True,
        "next_experiment_started": False,
    })
    # Snapshot integrity only, expressly NOT a gold or formal test freeze.
    files = {p.relative_to(OUT).as_posix(): module.digest(p.read_bytes())
             for p in sorted(OUT.rglob("*")) if p.is_file() and p.name != "MANIFEST.json"}
    module.write(OUT / "MANIFEST.json", {
        "scope": "PREPARATION_SNAPSHOT_ONLY_NOT_HUMAN_GOLD_OR_FORMAL_TEST_FREEZE",
        "files": files,
        "scripts": {p.relative_to(ROOT).as_posix(): module.digest(p.read_bytes()) for p in sorted(HERE.iterdir()) if p.is_file()},
    })
    print(json.dumps({"snapshot_files": len(files), "source_identity_checks": source_checks,
                      "formal_gold_frozen": False}))


if __name__ == "__main__":
    main()
