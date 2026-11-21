"""固定补测原试跑未覆盖的正常题；与原试跑合计最多60次模型调用。"""
from __future__ import annotations

import json
from pathlib import Path

from cogniguard.workflows.teachers.store import SQLiteTeacherAuditStore
from .backends import ROOT, ModelBudget, database_catalogs
from .dataset import CLEAN_STYLES, load_split, sha
from .defenses import METHODS
from .runner import DATA_ROOT, aggregate, write
from .trial import run_trial


def extend_normal_coverage(prior_run: Path, output: Path, *, transport=None):
    original = json.loads((prior_run / "manifest.json").read_text(encoding="utf-8"))
    if original["status"] != "completed":raise ValueError("Prior pilot must be complete")
    if original["execution"] != "real_model_pilot" and transport is None:
        raise ValueError("Prior run is not a real model pilot")
    tasks, cases, data_manifest = load_split(DATA_ROOT, "test")
    if data_manifest != original["dataset"]:raise ValueError("Dataset changed after prior pilot")
    policy_files = [Path(__file__).with_name(name) for name in
                    ("defenses.py", "protocol.py", "attacks.py", "tasks.py", "trial.py")]
    policy_files += [ROOT / "core/langgraph_runtime/teachers/dag.py", ROOT / "configs/teacher-teams.yaml"]
    fingerprints = {}
    for path in policy_files:
        key = str(path.relative_to(ROOT))
        expected = original["source_sha256"][key]
        if sha(path) != expected:raise ValueError("Defense/public-task code changed before coverage extension")
        fingerprints[key] = expected
    lookup = {case["case_id"]: case for case in cases}
    used_tasks = {lookup[case_id]["task_id"] for case_id in original["selected_test_case_ids"]}
    unused_tasks = sorted(set(tasks) - used_tasks)
    remaining = 60 - int(original["model_calls"])
    selected = []
    for index, task_id in enumerate(unused_tasks[:max(0, remaining // 2)]):
        style = CLEAN_STYLES[index % len(CLEAN_STYLES)]
        selected.append(next(case for case in cases if case["task_id"] == task_id
                             and case["condition"] == "clean" and case["family"] == style))
    if not selected:raise ValueError("No untested tasks fit the remaining shared budget")
    output.mkdir(parents=True, exist_ok=False)
    store = SQLiteTeacherAuditStore(output / "teacher_audit.sqlite3")
    prompts, skills = database_catalogs(store)
    if (prompts.sha256, skills.sha256) != (original["prompt_hash"], original["skill_hash"]):
        raise ValueError("Prompt/skill snapshot changed")
    budget = ModelBudget(output / "model-usage.jsonl", limit=remaining, transport=transport)
    methods = [method for method in METHODS if method.name in {"signature_only", "full_recover"}]
    manifest = {"schema_version": 2, "status": "running", "dataset": data_manifest,
                "execution": "injected_transport_test" if transport is not None else "real_model_normal_extension",
                "prior_manifest_sha256": sha(prior_run / "manifest.json"),
                "prior_model_calls": original["model_calls"], "max_model_calls": remaining,
                "source_sha256": fingerprints, "prompt_hash": prompts.sha256, "skill_hash": skills.sha256,
                "selected_test_case_ids": [case["case_id"] for case in selected],
                "model": getattr(budget.transport, "model", "injected_test_transport"),
                "limitations": ["Fixed extension of previously unused normal tasks only; same frozen defenses.",
                                "No additional attack coverage or human teaching-quality judgment."]}
    write(output / "manifest.json", manifest)
    write(output / "test-freeze.json", {**manifest, "methods": [method.to_dict() for method in methods]})
    rows = []
    try:
        for case in selected:
            for method in methods:
                row = run_trial(tasks[case["task_id"]], case, method, prompts, skills, store, output, budget=budget)
                row["phase"] = "heldout_normal_extension"
                rows.append(row)
                with (output / "rows.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(f"extension {case['case_id']} {method.name}: {row['status']} total_calls={original['model_calls']+budget.calls}", flush=True)
                if row["status"] == "error":raise RuntimeError("Coverage trial failed")
        for name, expected in fingerprints.items():
            if sha(ROOT / name) != expected:raise RuntimeError("Defense changed during extension")
        manifest["status"] = "completed"
    except Exception as error:
        manifest.update(status="incomplete", error_class=type(error).__name__)
        raise
    finally:
        manifest.update(model_calls=budget.calls, combined_model_calls=original["model_calls"]+budget.calls,
                        prompt_tokens=budget.prompt_tokens, completion_tokens=budget.completion_tokens)
        (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        write(output / "summary.json", {"status": manifest["status"], "groups": aggregate(rows),
              "model_calls": budget.calls, "combined_model_calls": manifest["combined_model_calls"],
              "new_task_count": len(selected), "limitations": manifest["limitations"]})
    return json.loads((output / "summary.json").read_text(encoding="utf-8"))
