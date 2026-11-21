"""Reproducibility manifest helpers for CG V3 episodes."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable


def _run_git(project_root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "unavailable"
    return result.stdout.strip() or result.stderr.strip() or ""


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    *,
    project_root: str | Path,
    mode: str,
    config: dict[str, Any],
    input_paths: Iterable[str | Path] = (),
    seed: int = 0,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    files = {}
    for value in input_paths:
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        if path.is_file():
            try:
                display_path = str(path.relative_to(root))
            except ValueError:
                display_path = str(path)
            files[display_path] = file_sha256(path)
    return {
        "manifest_version": "cg-v3-1",
        "controller_mode": mode,
        "seed": seed,
        "config": config,
        "input_files": files,
        "git_commit": _run_git(root, "rev-parse", "HEAD"),
        "git_branch": _run_git(root, "branch", "--show-current"),
        "git_status": _run_git(root, "status", "--short"),
        "sensitive_data_policy": "hashes and field names only; no secrets, raw profiles, or protected resource text",
    }


def write_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
