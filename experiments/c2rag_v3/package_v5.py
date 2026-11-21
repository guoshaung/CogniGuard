from __future__ import annotations

import ast
import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "experiments/c2rag_v3/results/development_pilot_v5"


def digest_text(value: str) -> dict[str, int | str]:
    return {"sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(), "length": len(value)}


def redact_jsonl(source: Path, destination_name: str, archive: zipfile.ZipFile) -> None:
    sensitive = {"allowed_evidence", "generated_answer", "released_answer", "source_text"}
    lines = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        for key in sensitive:
            if key in row and isinstance(row[key], str):
                row[key] = {"redacted": True, **digest_text(row[key])}
        lines.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
    archive.writestr(destination_name, "\n".join(lines) + ("\n" if lines else ""))


def add_file(archive: zipfile.ZipFile, path: Path, name: str | None = None) -> None:
    if path.is_file():
        archive.write(path, name or path.relative_to(ROOT).as_posix())


def documentation_paths(root: Path | None = None) -> list[Path]:
    """Locate current retrieval docs without relying on the former flat docs layout."""
    docs = (ROOT if root is None else root) / "docs" / "research" / "retrieval"
    selected = [path for path in docs.glob("*.md") if "c2rag" in path.name.casefold()]
    selected.extend([docs / "development_pilot_report.md", docs / "RUN_READINESS.md"])
    return sorted(set(selected))


def main() -> None:
    package = ROOT / "artifacts" / "packages" / "verification_package_v5.zip"
    package.parent.mkdir(parents=True, exist_ok=True)
    manifest: list[str] = []
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "experiments/c2rag_v3").rglob("*.py")):
            add_file(archive, path)
            manifest.append(path.relative_to(ROOT).as_posix())
        for path in documentation_paths():
            add_file(archive, path)
        for path in sorted(RESULTS.rglob("*")):
            if not path.is_file() or "runtime_fixture" in path.parts or "_fixture_probe" in path.parts or "shards" in path.parts or "measure_shard" in path.parts or path.name == "hidden_cases.jsonl":
                continue
            name = path.relative_to(ROOT).as_posix()
            if path.suffix == ".jsonl":
                redact_jsonl(path, name, archive)
            else:
                add_file(archive, path, name)
            manifest.append(name)
        legacy = ROOT / "experiments/c2rag_v3/results/development_pilot_v4"
        for name in ["raw_results.jsonl", "session_metrics.jsonl", "aggregated_metrics.csv", "mismatch_summary.json", "model_manifest.json", "freeze_manifest.json", "development_pilot_report.md"]:
            path = legacy / name
            if path.suffix == ".jsonl" and path.is_file():
                redact_jsonl(path, f"legacy_v4/{name}", archive)
            else:
                add_file(archive, path, f"legacy_v4/{name}")
        tests = []
        for path in sorted((ROOT / "experiments/c2rag_v3/tests").glob("test_*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            tests.extend(f"{path.relative_to(ROOT).as_posix()}::{node.name}" for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
        archive.writestr("test_discovery.json", json.dumps({"tests": sorted(tests), "count": len(tests)}, ensure_ascii=False, indent=2))
        archive.writestr("package_manifest.json", json.dumps({"status": "BLOCKED_LIMITED_PILOT", "held_out_test_included": False, "sensitive_resource_originals_included": False, "files": sorted(set(manifest))}, ensure_ascii=False, indent=2))
    print(json.dumps({"package": str(package), "files": len(set(manifest)), "tests": len(tests), "size": package.stat().st_size}, ensure_ascii=False))


if __name__ == "__main__":
    main()
