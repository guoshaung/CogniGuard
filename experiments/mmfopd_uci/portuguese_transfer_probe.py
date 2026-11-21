"""Cross-subject UCI Portuguese grade-transfer stress test for field alignment.

The G1/G2 alignment rule was fixed after the Math diagnostic and is applied
unchanged here. Math and Portuguese rows may overlap in student identity, so
this is a new subject outcome but not an independent student cohort.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

import numpy as np

from protection.common.schemas import Task
from .alignment_probe import ARMS, evaluate_arm
from .runner import (
    HASH_SEED, ROOT, load_lock, make_profile, parse_csv, sha,
    split_indices, train_mi_order,
)


SEEDS = (17, 29, 43, 71, 101)


def make_portuguese_profile(row: dict[str, str], index: int):
    profile, old_task = make_profile(row, index)
    for record in profile.profile_records:
        if record.knowledge == "math_progress":
            record.knowledge = "language_progress"
    task = Task(
        request_id=f"portuguese-grade-{index}", student_id=old_task.student_id,
        question=("Predict third period Portuguese language grade using previous grades "
                  "G1 G2 studytime absences failures schoolsup famsup paid activities "
                  "nursery higher internet traveltime"),
        knowledge="language_progress", difficulty="grade_prediction",
        need_resource=False,
    )
    return profile, task


def run(cache: Path, output: Path, seeds=SEEDS):
    if output.exists():
        raise FileExistsError("fresh output directory required")
    if os.getenv("PYTHONHASHSEED") != HASH_SEED:
        raise ValueError("frozen PYTHONHASHSEED worker required")
    lock = load_lock(cache)
    rows = parse_csv((cache / "student-por.csv").read_bytes(), 649)
    code_paths = [Path(__file__), ROOT / "experiments/mmfopd_uci/alignment_probe.py",
                  ROOT / "experiments/mmfopd_uci/runner.py",
                  ROOT / "protection/student_profile/src/fopd/profile_selector.py"]
    hashes = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in code_paths}
    output.mkdir(parents=True, exist_ok=False)
    protocol = {
        "status": "FROZEN_CROSS_SUBJECT_EXPLORATORY_TRANSFER",
        "protocol": "uci_portuguese_g1_g2_alignment_transfer_v1",
        "source_lock_sha256": sha((cache / "source-lock.json").read_bytes()),
        "subject": "Portuguese_language", "rows": 649, "seeds": list(seeds),
        "arms_fixed_from_math_diagnostic": ARMS,
        "field_budget": 3, "same_private_policy": True,
        "method_selection_uses_portuguese_test_labels": False,
        "cohort_warning": "Math and Portuguese records overlap in student identity; not an independent student population.",
        "source_code_sha256": hashes,
        "dependencies": {name: importlib.metadata.version(name)
                         for name in ("scikit-learn", "numpy", "scipy")},
        "real_api_calls": 0, "langsmith_upload": False,
    }
    (output / "protocol-lock.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    profiles = [make_portuguese_profile(row, index) for index, row in enumerate(rows)]
    y = np.array([int(row["G3"]) for row in rows], dtype=float)
    per_seed = []
    for seed in seeds:
        train, dev, test = split_indices(rows, seed)
        mi_order = train_mi_order(rows, train, seed)
        arms = [evaluate_arm(rows, profiles, train, dev, test, y, seed, mi_order, arm)
                for arm in ARMS]
        per_seed.append({"seed": seed, "test_n": len(test), "arms": arms})
        print(json.dumps({"progress": "seed_done", "seed": seed}), flush=True)
    if {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in code_paths} != hashes or load_lock(cache) != lock:
        raise ValueError("source or code changed while running")
    keys = ("mae", "released_fields_mean", "any_private_field_rate",
            "G1_frequency", "G2_frequency", "residual_attack_macro_ba",
            "residual_attack_macro_auc")
    summary = []
    for arm in ARMS:
        chosen = [next(item for item in run_item["arms"] if item["arm"] == arm)
                  for run_item in per_seed]
        summary.append({"arm": arm,
                        **{key: {"mean": statistics.mean(item[key] for item in chosen),
                                 "std": statistics.stdev(item[key] for item in chosen)
                                 if len(chosen) > 1 else 0.0} for key in keys},
                        "field_release_frequency": {
                            field: statistics.mean(item["field_release_frequency"][field]
                                                   for item in chosen)
                            for field in chosen[0]["field_release_frequency"]}})
    final = {
        "status": "COMPLETED_CROSS_SUBJECT_EXPLORATORY_TRANSFER",
        "protocol": protocol["protocol"], "source_students": len(rows),
        "test_evaluations_per_arm": sum(item["test_n"] for item in per_seed),
        "arms": summary, "real_api_calls": 0,
        "limitations": [
            "Portuguese and Math subjects may share students; this is not an independent cohort.",
            "The field-alignment rule was proposed after seeing Math test results, though no Portuguese test label selected an arm.",
            "Overlapping repeated splits are descriptive, not independent replications.",
            "Grade prediction is not measured teaching quality.",
        ],
    }
    (output / "summary.json").write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": final["status"], "output": str(output)}), flush=True)
    return final


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache/uci-student-performance-v1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.seeds or len(set(args.seeds)) != len(args.seeds):
        parser.error("unique seeds required")
    if not args.worker:
        env = dict(os.environ, PYTHONHASHSEED=HASH_SEED, LANGSMITH_TRACING="false",
                   LANGCHAIN_TRACING_V2="false", OMP_NUM_THREADS="1",
                   OPENBLAS_NUM_THREADS="1")
        done = subprocess.run([sys.executable, "-X", "utf8", "-m",
                               "experiments.mmfopd_uci.portuguese_transfer_probe",
                               *sys.argv[1:], "--worker"], cwd=ROOT, env=env)
        raise SystemExit(done.returncode)
    run(args.cache, args.output, args.seeds)


if __name__ == "__main__":
    main()
