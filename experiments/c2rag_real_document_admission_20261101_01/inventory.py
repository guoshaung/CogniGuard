"""Bounded metadata inventory; no inference, parsing of office files, or downloads."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.paths import PROJECT_ROOT, RESULTS_DIR

RUN = "c2rag_real_document_admission_20261101_01"
OUT = RESULTS_DIR / RUN
SCOPES = ("data", "docs", "experiments", "artifacts")
EXCLUDE = {
    ".git", "node_modules", "__pycache__", "assets", "hf_cache", ".venv",
    ".venv-langgraph", "third_party", "_root_workspaces_20261023", ".tmp",
    "sync-checkout",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "LOCAL_INVENTORY.json"
    if target.exists():
        raise SystemExit("Preserve prior inventory; select a new run ID.")
    offices = []
    counts: Counter[str] = Counter()
    errors = []
    for scope in SCOPES:
        def onerror(error: OSError) -> None:
            errors.append(str(error))

        for root, dirs, files in os.walk(PROJECT_ROOT / scope, onerror=onerror):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDE and not d.startswith(".venv"))
            for name in sorted(files):
                path = Path(root) / name
                suffix = path.suffix.lower()
                counts[suffix] += 1
                if suffix in {".pdf", ".docx", ".doc", ".odt"}:
                    offices.append({"path": path.relative_to(PROJECT_ROOT).as_posix(),
                                    "bytes": path.stat().st_size, "sha256": digest(path)})
    refs = [
        "CONTRIBUTING.md", "LICENSE", "pyproject.toml", "docs/getting-started.md",
        "experiments/c2rag_r9_real_text_20261019_01/LICENSE_SOURCE_MATERIAL.md",
        "experiments/c2rag_r10_20261020_01/LICENSE_SOURCE_MATERIAL.md",
        "experiments/relation_closure_20261019_02/document_preparation/annotated_assets.json",
        "experiments/relation_closure_20261019_02/document_preparation/source_registry.json",
        "var/results/c2rag_r36_authorization_audit_20261029_01/RESULT.md",
        "var/results/c2rag_semantic_admission_status_20261101_01/RESULT.md",
        "var/results/c2rag_semantic_admission_status_20261101_01/decision.json",
        "data/datasets/education_scenarios/teacher_resources.jsonl",
        "data/scenario_layers/teacher_resources/teacher_resources_v1.jsonl",
    ]
    source_hashes = [{"path": p, "sha256": digest(PROJECT_ROOT / p)} for p in refs]
    fixture_path = PROJECT_ROOT / refs[-2]
    fixtures = [json.loads(s) for s in fixture_path.read_text(encoding="utf-8-sig").splitlines() if s.strip()]
    placeholders = sum("这是教师的原创课件内容" in json.dumps(r, ensure_ascii=False) for r in fixtures)
    old_integrity = json.loads((PROJECT_ROOT / "var/results/c2rag_semantic_admission_status_20261101_01/SOURCE_INTEGRITY.json").read_text(encoding="utf-8-sig"))
    old_records = [{"path": r["path"], "sha256": digest(PROJECT_ROOT / r["path"]),
                    "matches": digest(PROJECT_ROOT / r["path"]) == r["expected_sha256"]}
                   for r in old_integrity["records"]]
    inventory = {
        "run": RUN, "utc": datetime.now(timezone.utc).isoformat(),
        "scopes": SCOPES, "excluded_directory_names": sorted(EXCLUDE),
        "outside_scope": "Personal directories, other drives, excluded archives and whole disk not searched",
        "office_files": offices, "extension_counts": dict(sorted(counts.items())),
        "read_errors": errors, "reference_hashes": source_hashes,
        "fixture_records": len(fixtures), "placeholder_records": placeholders,
        "old_semantic_materials": old_records,
        "old_semantic_materials_all_match": all(r["matches"] for r in old_records),
        "admission_is_human_interpretation_not_automated_license_detection": True,
    }
    target.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "run": RUN, "scopes": SCOPES, "pdf_files": sum(p["path"].endswith(".pdf") for p in offices),
        "office_files": len(offices), "read_errors": len(errors),
        "fixture_records": len(fixtures), "placeholder_records": placeholders,
        "old_materials_checked": len(old_records),
        "old_materials_all_match": inventory["old_semantic_materials_all_match"],
        "local_inventory_sha256": digest(target), "model_calls": 0, "solver_calls": 0,
        "paid_api_calls": 0, "gpu_tasks": 0,
    }
    (OUT / "INVENTORY_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
