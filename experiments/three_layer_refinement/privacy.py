"""Equal-budget check of a generic task-slot selector on real UCI records."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

import numpy as np

from experiments.mmfopd_uci.alignment_probe import evaluate_arm
from experiments.mmfopd_uci.runner import (
    CONFIG, HASH_SEED, ROOT, load_lock, make_profile, parse_csv,
    select_fields, sha, split_indices, train_mi_order,
)
from experiments.mmfopd_uci.portuguese_transfer_probe import make_portuguese_profile
from protection.student_profile.src.fopd.profile_selector import ProfileSelector

ARMS = ("MM-FOPD", "TaskSlot-MMFOPD-3", "TrainMI-SafeTopK-3")
SEEDS = (17, 29, 43, 71, 101)


def slot_fields(arm, profile, task, seed, mi_order):
    if arm != "TaskSlot-MMFOPD-3":
        return select_fields(arm, profile, task, seed, mi_order)
    config = copy.deepcopy(CONFIG)
    config["fopd"]["unit_budget"]["distinct_requested_types"] = ["mastery"]
    return {x.record.record_id for x in ProfileSelector(config).select(profile, task)}


def steps(cache, output):
    from experiments.rag_real.retrieval import dump
    load_lock(cache)
    paths = [Path(__file__), ROOT / "protection/student_profile/src/fopd/profile_selector.py",
             ROOT / "experiments/mmfopd_uci/alignment_probe.py"]
    hashes = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths}
    output.mkdir(parents=True, exist_ok=False)
    dump(output / "protocol-lock.json", {
        "protocol": "task_slot_mmfopd_real_uci_v1", "status": "FROZEN_EXPLORATORY",
        "test_informed_adaptation": True, "seeds": SEEDS, "arms": ARMS,
        "field_budget": 3, "task_slot_rule": "preserve distinct explicitly requested mastery record IDs before refill",
        "source_lock_sha256": sha((cache / "source-lock.json").read_bytes()),
        "source_code_sha256": hashes, "real_api_calls": 0,
        "limitations": ["Previously inspected split identities; not independent confirmation.",
                        "Subjects overlap; grade prediction is a utility proxy, not teaching effectiveness."],
    })
    yield "prepare", 10
    rows_out = []
    for subject, filename, n, builder in (
        ("math", "student-mat.csv", 395, make_profile),
        ("portuguese", "student-por.csv", 649, make_portuguese_profile),
    ):
        rows = parse_csv((cache / filename).read_bytes(), n)
        profiles = [builder(row, i) for i, row in enumerate(rows)]
        y = np.array([int(row["G3"]) for row in rows], dtype=float)
        for seed in SEEDS:
            train, dev, test = split_indices(rows, seed)
            mi_order = train_mi_order(rows, train, seed)
            results = [evaluate_arm(rows, profiles, train, dev, test, y, seed, mi_order, arm,
                                    selector=slot_fields) for arm in ARMS]
            rows_out.extend({"subject": subject, **r} for r in results)
            dump(output / f"{subject}-{seed}.json", {"arms": results})
            print(json.dumps({"subject": subject, "seed": seed, "completed": True}), flush=True)
            yield "item"
    if hashes != {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths}:
        raise ValueError("source changed during run")
    keys = ("mae", "released_fields_mean", "any_private_field_rate", "residual_attack_macro_ba")
    summary = []
    for subject in ("math", "portuguese"):
        for arm in ARMS:
            items = [r for r in rows_out if r["subject"] == subject and r["arm"] == arm]
            summary.append({"subject": subject, "arm": arm, **{
                key: {"mean": statistics.mean(r[key] for r in items),
                      "std": statistics.stdev(r[key] for r in items)} for key in keys}})
    result = {"status": "COMPLETED_EXPLORATORY", "methods": summary,
              "test_informed_adaptation": True, "real_api_calls": 0}
    dump(output / "summary.json", result)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cache", type=Path, default=ROOT / ".cache/uci-student-performance-v1")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    a = p.parse_args()
    if not a.worker:
        env = dict(os.environ, PYTHONHASHSEED=HASH_SEED, LANGSMITH_TRACING="false",
                   LANGCHAIN_TRACING_V2="false", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
        raise SystemExit(subprocess.run([sys.executable, "-X", "utf8", "-m", __spec__.name,
                                        *sys.argv[1:], "--worker"], cwd=ROOT, env=env).returncode)
    if os.environ.get("PYTHONHASHSEED") != HASH_SEED:
        raise ValueError("frozen hash seed required")
    from experiments.rag_real.graph import CONTROL_GRAPH, invoke_batch
    result = invoke_batch(CONTROL_GRAPH, steps(a.cache, a.output))
    print(json.dumps({"status": result["status"], "output": str(a.output)}))


if __name__ == "__main__":
    main()
