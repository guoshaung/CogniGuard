"""Atomic at-most-once claim. Unknown/stale RUNNING jobs are never regenerated."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .protocol import Task, canonical, digest


def atomic_json(path: Path, data: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("xb") as stream:
        stream.write(canonical(data))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


class JobStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def claim(self, task: Task) -> tuple[bool, dict | None]:
        task.validate()
        job = self.root / task.task_id
        if job.is_symlink():
            raise ValueError("Symlink job directories forbidden")
        job.mkdir(exist_ok=True)
        lock = job / "claim.json"
        try:
            with lock.open("xb") as stream:
                stream.write(canonical({"task_sha256": task.sha256, "state": "RUNNING_OR_UNKNOWN"}))
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            try:
                existing = json.loads(lock.read_bytes())
            except (json.JSONDecodeError, OSError):
                # Another claimant may be between exclusive creation and fsync.
                # A crashed/partial claim is also conservatively UNKNOWN.
                return False, {
                    "task_id": task.task_id,
                    "status": "RUNNING_OR_UNKNOWN",
                    "reason": "CLAIM_NOT_COMPLETE_REQUIRES_RECONCILIATION",
                    "automatic_retry": False,
                }
            if existing["task_sha256"] != task.sha256:
                raise ValueError("Task ID reused with a different payload")
            result = job / "result.json"
            if result.exists():
                return False, json.loads(result.read_bytes())
            return False, {
                "task_id": task.task_id,
                "status": "RUNNING_OR_UNKNOWN",
                "task_sha256": task.sha256,
                "automatic_retry": False,
            }
        atomic_json(job / "task.json", task.to_dict())
        return True, None

    def finish(self, task: Task, result: dict) -> str:
        result = {
            **result,
            "task_id": task.task_id,
            "task_sha256": task.sha256,
            "output_relpath": task.output_relpath,
        }
        if result.get("status") not in {"COMPLETED", "FAILED"}:
            raise ValueError("Explicit terminal status required")
        job = self.root / task.task_id
        current = json.loads((job / "claim.json").read_bytes())
        if current["task_sha256"] != task.sha256 or (job / "result.json").exists():
            raise ValueError("No result overwrite")
        atomic_json(job / "result.json", result)
        return digest((job / "result.json").read_bytes())
