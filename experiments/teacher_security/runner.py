"""整轮实验调度：离线全矩阵，或开发消融→攻击冻结→真实测试子集。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

from cogniguard.workflows.teachers.store import SQLiteTeacherAuditStore
from .adaptive import run_search
from .backends import ROOT, ModelBudget, database_catalogs
from .dataset import load_split, pilot_cases, sha
from .defenses import METHODS
from .trial import run_trial


DATA_ROOT = Path(__file__).with_name("data") / "v1"


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def aggregate(rows):
    groups = {}
    for phase, method in sorted({(row["phase"], row["method"]) for row in rows}):
        selected = [row for row in rows if (row["phase"], row["method"]) == (phase, method)]
        clean = [row for row in selected if row["condition"] == "clean"]
        attacks = [row for row in selected if row["condition"] == "attack"]
        groups[f"{phase}/{method}"] = {
            "clean_cases": len(clean), "attack_cases": len(attacks),
            "errors": sum(row["status"] == "error" for row in selected),
            "clean_completed": sum(row["status"] == "completed" for row in clean),
            "clean_numeric_success": sum(row["metrics"]["numeric_task_success"] for row in clean),
            "clean_fallback": sum(row["fallback_used"] for row in clean),
            "attack_success": sum(row["metrics"]["attack_success"] for row in attacks),
            "attack_evaluable_cases": sum(row["metrics"].get("attack_outcome_known", False) for row in attacks),
            "attack_unknown_cases": sum(not row["metrics"].get("attack_outcome_known", False) for row in attacks),
            "attack_abstained": sum(row["metrics"]["abstained"] for row in attacks),
            "clean_invalid_output": sum(row["status"] == "completed" and not row["metrics"]["schema_valid"] for row in clean),
            "attack_completed": sum(row["status"] == "completed" for row in attacks),
            "attack_numeric_success": sum(row["metrics"]["numeric_task_success"] for row in attacks),
            "attack_fallback": sum(row["fallback_used"] for row in attacks),
            "manual_review": sum(row["metrics"]["manual_review_required"] for row in selected),
            "model_calls": sum(row["model_calls"] for row in selected),
        }
    return groups


def run(output: Path, *, real=False, transport=None, model_limit=60):
    output = Path(output).resolve()
    dev_tasks, dev_cases, dataset_manifest = load_split(DATA_ROOT, "development")
    test_tasks, test_cases, _ = load_split(DATA_ROOT, "test")
    output.mkdir(parents=True, exist_ok=False)
    store = SQLiteTeacherAuditStore(output / "teacher_audit.sqlite3")
    prompts, skills = database_catalogs(store)
    files = list(Path(__file__).parent.glob("*.py")) + [
        ROOT / "core/langgraph_runtime/teachers/dag.py", ROOT / "configs/teacher-teams.yaml"]
    fingerprints = {str(path.relative_to(ROOT)): sha(path) for path in files}
    budget = ModelBudget(output / "model-usage.jsonl", limit=model_limit, transport=transport) if real else None
    selected_test = pilot_cases(test_tasks, test_cases) if real else test_cases
    first_dev = next(iter(dev_tasks))
    dev_selected = [next(case for case in dev_cases if case["task_id"] == first_dev
                    and case["family"] == family and case["condition"] == condition)
                    for condition, family in (("clean", "refusal_quote"), ("attack", "fact"),
                                              ("attack", "cross_student"), ("attack", "relay_tamper"))]
    manifest = {"schema_version": 2, "created_at": datetime.now(timezone.utc).isoformat(),
                "execution": "injected_transport_test" if transport is not None else
                             "real_model_pilot" if real else "offline_fixture_acceptance",
                "status": "running", "dataset": dataset_manifest,
                "source_sha256": fingerprints, "prompt_hash": prompts.sha256, "skill_hash": skills.sha256,
                "methods": [method.to_dict() for method in METHODS],
                "selected_test_case_ids": [case["case_id"] for case in selected_test],
                "max_model_calls": model_limit if real else 0,
                "real_call_upper_bound": 60 if real else 0,
                "model": getattr(budget.transport, "model", "injected_test_transport") if budget else None,
                "review_file": "synthetic-review.jsonl (synthetic generated text only)",
                "limitations": ["Synthetic numeric tasks; no classroom-quality claim.",
                    "Both source teachers use controlled materials; only synthesis is a real defender model.",
                    "Adaptive search uses two real attacker roles and development feedback; transfer is frozen.",
                    "Repeated case variants share tasks; do not treat them as independent statistical samples."]}
    write(output / "manifest.json", manifest)
    rows, adaptive_history = [], []
    def evaluate(phase, tasks, cases, methods, templates=None):
        for case in cases:
            for method in methods:
                row = run_trial(tasks[case["task_id"]], case, method, prompts, skills, store, output,
                                budget=budget, templates=templates)
                row["phase"] = phase
                rows.append(row)
                with (output / "rows.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                if real:print(f"{phase} {case['case_id']} {method.name}: {row['status']} calls={budget.calls}", flush=True)
                if row["status"] == "error":raise RuntimeError("Trial failed; stopping remaining jobs")
    try:
        evaluate("development_ablation", dev_tasks, dev_selected, METHODS)
        templates = None
        adaptive_hash = None
        if real:
            templates, adaptive_hash, adaptive_history = run_search(
                dev_tasks[first_dev], prompts, skills, store, output, budget)
        else:
            write(output / "adaptive-frozen.json", {"status": "NOT_RUN_OFFLINE", "selection_split": "development"})
            adaptive_hash = sha(output / "adaptive-frozen.json")
        # 所有代码、方法配置、攻击候选在首次测试集调用之前冻结。
        freeze = {"source_sha256": fingerprints, "adaptive_sha256": adaptive_hash,
                  "dataset": dataset_manifest["files"], "selection_split": "development",
                  "prompt_hash": prompts.sha256, "skill_hash": skills.sha256,
                  "methods": [method.to_dict() for method in METHODS],
                  "selected_test_case_ids": manifest["selected_test_case_ids"]}
        write(output / "test-freeze.json", freeze)
        for name, expected in fingerprints.items():
            if sha(ROOT / name) != expected:raise RuntimeError("Source changed before heldout evaluation")
        methods = [method for method in METHODS if method.name in {"signature_only", "full_recover"}] if real else METHODS
        evaluate("heldout_pilot" if real else "heldout_fixture", test_tasks, selected_test, methods)
        if real:
            task = next(iter(test_tasks.values()))
            case = {"case_id": task.task_id + "_adaptive_transfer", "task_id": task.task_id,
                    "condition": "attack", "family": "adaptive_collusion"}
            if sha(output / "adaptive-frozen.json") != adaptive_hash:
                raise RuntimeError("Adaptive attack changed after freeze")
            evaluate("adaptive_transfer", test_tasks, [case], methods, templates)
        for name, expected in fingerprints.items():
            if sha(ROOT / name) != expected:raise RuntimeError("Source changed during heldout evaluation")
        manifest["status"] = "completed"
    except Exception as error:
        manifest.update(status="incomplete", error_class=type(error).__name__)
        raise
    finally:
        manifest.update(model_calls=budget.calls if budget else 0,
                        prompt_tokens=budget.prompt_tokens if budget else 0,
                        completion_tokens=budget.completion_tokens if budget else 0)
        # 运行状态文件可以更新，冻结文件和测试数据始终只读。
        (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        write(output / "summary.json", {"status": manifest["status"], "execution": manifest["execution"],
              "groups": aggregate(rows), "model_calls": manifest["model_calls"],
              "database_counts": store.counts(), "adaptive_development_rounds": len(adaptive_history),
              "limitations": manifest["limitations"]})
    return json.loads((output / "summary.json").read_text(encoding="utf-8"))
