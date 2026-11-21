"""只读原始结果、另存评分审计。不会覆盖已冻结运行或调用模型。"""
from __future__ import annotations

import json
from pathlib import Path

from .dataset import load_split, sha
from .runner import DATA_ROOT, aggregate, write
from .scoring import score


def audit_run(source: Path, output: Path):
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    tasks = {}
    for split in ("development", "test"):
        part, _, data_manifest = load_split(DATA_ROOT, split)
        if data_manifest != manifest["dataset"]:raise ValueError("Dataset changed since original run")
        tasks.update(part)
    reviews = {}
    for line in (source / "synthetic-review.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        key = item["case_id"], item["method"]
        if key in reviews:raise ValueError("Ambiguous review identity")
        reviews[key] = item
    rows = []
    for line in (source / "rows.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        review = reviews[row["case_id"], row["method"]]
        row["metrics"] = score(tasks[row["task_id"]], review["final_answer"], status=row["status"],
                               tool_event=row["tool_event"],
                               attack_family=row["family"] if row["condition"] == "attack" else None)
        rows.append(row)
    output.mkdir(parents=True, exist_ok=False)
    write(output / "audit-manifest.json", {
        "original_manifest_sha256": sha(source / "manifest.json"),
        "original_rows_sha256": sha(source / "rows.jsonl"),
        "original_review_sha256": sha(source / "synthetic-review.jsonl"),
        "scorer_sha256": sha(Path(__file__).with_name("scoring.py")),
        "aggregation_sha256": sha(Path(__file__).with_name("runner.py")),
        "protocol_sha256": sha(Path(__file__).with_name("protocol.py")),
        "reporter_sha256": sha(Path(__file__)), "model_calls": 0,
        "purpose": "Post-run scorer audit; original defense/data/attack freeze unchanged",
    })
    with (output / "rows-audited.jsonl").open("x", encoding="utf-8") as stream:
        for row in rows:stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {"status": manifest["status"], "execution": manifest["execution"],
               "groups": aggregate(rows), "model_calls_in_original": manifest["model_calls"],
               "limitations": manifest["limitations"]}
    write(output / "summary-audited.json", summary)
    return summary
