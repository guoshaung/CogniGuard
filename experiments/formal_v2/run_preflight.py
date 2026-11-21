"""Read-only formal-v2 preflight; it never starts a model or formal run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FORMAL = ROOT / "experiments" / "formal_v2"
LEGACY = ROOT / "experiments" / "results" / "cg_v3_five_baseline_pilot"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    checks: list[dict[str, object]] = []

    required = [
        FORMAL / "formal_experiment_design_v2.md",
        FORMAL / "dataset_manifest.csv",
        FORMAL / "split_manifest.csv",
        FORMAL / "frozen_config.json",
        FORMAL / "reproducibility_manifest.md",
    ]
    checks.append({"check": "formal_package_files", "passed": all(path.exists() for path in required)})

    legacy_dataset = ROOT / "experiments" / "datasets" / "cg_v3_pilot" / "episodes.jsonl"
    checks.append(
        {
            "check": "legacy_dataset_hash_unchanged_reference",
            "passed": legacy_dataset.exists()
            and sha256(legacy_dataset)
            == "fd072074a32e97c4d763e71e166429c44dd38f88604662887e0809ec0d3cf7c9",
        }
    )
    checks.append(
        {
            "check": "legacy_result_directory_present",
            "passed": LEGACY.exists(),
            "path": str(LEGACY),
        }
    )
    checks.append(
        {
            "check": "unified_actual_disclosure_gate",
            "passed": False,
            "status": "BLOCKED",
            "reason": "No single formal runner feeds real MM-FOPD, C2-RAG, HSW-ST and SCE-LocGuard released output into one evaluator.",
        }
    )
    checks.append(
        {
            "check": "hsw_runtime_gate",
            "passed": False,
            "status": "BLOCKED",
            "reason": "Smoke model cache and configured HSW input files are unavailable.",
        }
    )
    checks.append(
        {
            "check": "sce_locguard_paper_gate",
            "passed": False,
            "status": "BLOCKED",
            "reason": "Capabilities reported attack pipeline unavailable, paper_mode_ready false, missing registry secret and deterministic mode.",
        }
    )
    result = {"status": "BLOCKED", "checks": checks}
    (FORMAL / "preflight.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
