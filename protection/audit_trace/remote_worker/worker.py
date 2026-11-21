"""Explicit opt-in worker entry point; never calls an original-answer API."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .protocol import Task
from .store import JobStore


def run_task(task: Task, spool: Path, engine_factory, key: str | None) -> dict:
    store = JobStore(spool)
    claimed, cached = store.claim(task)
    if not claimed:
        return cached
    try:
        result = engine_factory().generate(task, key)
    except Exception as exc:
        # No exception body, prompt, source or credential enters shared logs.
        result = {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "automatic_retry": False,
            "input_sha256": task.input_sha256,
        }
    store.finish(task, result)
    return json.loads((spool / task.task_id / "result.json").read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, type=Path)
    parser.add_argument("--spool", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--model-manifest", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    task = Task.from_dict(json.loads(args.task.read_bytes()))
    if not args.execute:
        print(
            json.dumps(
                {"status": "VALIDATED_NOT_RUN", "task_id": task.task_id, "task_sha256": task.sha256}
            )
        )
        return 0
    os.environ.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
    )
    from .engine import MusaHFEngine

    manifest = json.loads(args.model_manifest.read_bytes())
    result = run_task(
        task,
        args.spool,
        lambda: MusaHFEngine(args.model_dir, task.model, manifest, "musa:0"),
        os.environ.get("CG_HSW_KGW_KEY") if task.method == "kgw" else None,
    )
    print(json.dumps({"task_id": task.task_id, "status": result["status"]}))
    return 0 if result["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
