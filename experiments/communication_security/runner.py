"""CGC propagation experiment over 3 DAGs, with frozen source interventions.

Offline is a susceptible relay fixture, never measured LLM security. In real
mode both relays and the synthesis node use MiMo, sharing a hard 24-call cap.
No final-compromise shortcut is used: all attacks originate upstream.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import statistics

from cogniguard.workflows.teachers.store import SQLiteTeacherAuditStore
from experiments.teacher_security.backends import ROOT, ModelBudget, database_catalogs
from experiments.teacher_security.dataset import load_split, sha
from experiments.teacher_security.defenses import Defense
from experiments.teacher_security.runner import write
from experiments.teacher_security.trial import run_trial
from .topologies import NAMES, build

METHODS = (Defense("NoCGC", False, False, False, False, False, False),
           Defense("SignatureOnly", True, False, False, False, False, False),
           Defense("FinalOnly", handoff=False), Defense("FullCGC"),
           Defense("FullCGC-Recover", recovery=True))


def steps(output, real=False):
    tasks, _, dataset = load_split(ROOT / "experiments/teacher_security/data/v1", "test")
    chosen = [tasks[key] for key in sorted(tasks)[:6]]
    output.mkdir(parents=True, exist_ok=False)
    store = SQLiteTeacherAuditStore(output / "teacher_audit.sqlite3")
    prompts, skills = database_catalogs(store)
    teams = {name: build(name, ROOT, prompts) for name in NAMES}
    budget = ModelBudget(output / "model-usage.jsonl", limit=24) if real else None
    methods = (METHODS[1], METHODS[4]) if real else METHODS
    if real:
        cases = [(chosen[0], "parallel_merge", "clean", "standard"),
                 (chosen[1], "serial_merge", "attack", "fact"),
                 (chosen[2], "correlated_echo", "attack", "fact"),
                 (chosen[3], "parallel_merge", "attack", "collusion")]
    else:
        cases = [(task, topology, condition, family) for task in chosen for topology in NAMES
                 for condition, family in (("clean", "standard"), ("clean", "refusal_quote"),
                                           ("attack", "fact"), ("attack", "collusion"),
                                           ("attack", "relay_tamper"), ("attack", "cross_student"))]
    paths = [*Path(__file__).parent.glob("*.py"), ROOT / "experiments/teacher_security/trial.py",
             ROOT / "experiments/teacher_security/defenses.py", ROOT / "core/langgraph_runtime/teachers/dag.py",
             ROOT / "core/langgraph_runtime/teachers/chain.py"]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    write(output / "protocol-lock.json", {
        "protocol": "cgc_multihop_communication_v1", "status": "FROZEN_BEFORE_EVALUATION",
        "execution": "real_relay_and_synthesis_pilot" if real else "offline_susceptible_relay_fixture",
        "dataset": dataset, "source_code_sha256": hashes, "prompt_hash": prompts.sha256,
        "team_hashes": {k: v.sha256 for k, v in teams.items()}, "methods": [m.to_dict() for m in methods],
        "cases": [{"task_id": t.task_id, "topology": top, "condition": c, "family": f} for t, top, c, f in cases],
        "max_real_calls": 24 if real else 0, "scoring_access": "post-run only",
        "limitations": ["Sources are controlled synthetic interventions; both relays and synthesis are real only in real mode.",
                        "Public numeric task recomputation is a bounded verifier, not a general semantic truth oracle.",
                        "Recovery is a deterministic solver and must be reported as degraded service.",
                        "Root-message counts reveal correlated paths, not proof of independent evidence or collusion detection.",
                        "No adversary directly replaces the final answer; four-case real mode is a mechanism pilot."],
    })
    rows = []
    yield "prepare", len(cases)
    for index, (task, topology, condition, family) in enumerate(cases):
        case = {"case_id": f"{task.task_id}-{topology}-{condition}-{family}",
                "task_id": task.task_id, "condition": condition, "family": family}
        for method in methods:
            row = run_trial(task, case, method, prompts, skills, store, output,
                            budget=budget, team=teams[topology])
            row["topology"] = topology
            rows.append(row)
            with (output / "rows.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            if row["status"] == "error":
                raise RuntimeError("teacher execution failed; no mock fallback allowed")
        print(json.dumps({"communication_case_completed": index + 1, "cases": len(cases),
                          "model_calls": budget.calls if budget else 0}), flush=True)
        yield "item"
    if hashes != {str(p.relative_to(ROOT)): sha(p) for p in paths}:
        raise ValueError("source changed during communication experiment")
    groups = []
    for topology, method in sorted({(r["topology"], r["method"]) for r in rows}):
        items = [r for r in rows if r["topology"] == topology and r["method"] == method]
        clean = [r for r in items if r["condition"] == "clean"]
        attack = [r for r in items if r["condition"] == "attack"]
        groups.append({"topology": topology, "method": method, "clean_n": len(clean), "attack_n": len(attack),
                       "clean_task_success": sum(r["metrics"]["numeric_task_success"] for r in clean),
                       "attack_success": sum(r["metrics"]["attack_success"] for r in attack),
                       "attack_unknown": sum(not r["metrics"]["attack_outcome_known"] for r in attack),
                       "attack_recovery": sum(r["fallback_used"] for r in attack),
                       "contaminated_nonroot_mean": statistics.mean(r["communication"]["contaminated_nonroot_nodes"] for r in items),
                       "blocked_edges_mean": statistics.mean(r["communication"]["blocked_communication_edges"] for r in items),
                       "correlated_report_excess_mean": statistics.mean(r["communication"]["correlated_report_excess"] for r in items)})
    result = {"status": "COMPLETED_REAL_MECHANISM_PILOT" if real else "COMPLETED_OFFLINE_FIXTURE_ACCEPTANCE",
              "trials": len(rows), "groups": groups, "real_api_calls": budget.calls if budget else 0,
              "database_counts": store.counts()}
    write(output / "summary.json", result)
    return result


def main(real_default=False):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--real", action="store_true", default=real_default)
    args = parser.parse_args()
    from experiments.rag_real.graph import CONTROL_GRAPH, invoke_batch
    result = invoke_batch(CONTROL_GRAPH, steps(args.output, args.real), recursion_limit=200)
    print(json.dumps({"status": result["status"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
