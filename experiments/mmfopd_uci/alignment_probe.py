"""Exploratory equal-budget UCI field-alignment diagnostic.

This is a post-hoc probe motivated by an already inspected test result. It
never changes the frozen MM-FOPD selector, never calls a model API, and must
not be reported as an independent confirmatory test or a new main baseline.
"""
from __future__ import annotations

import argparse
import copy
import importlib.metadata
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score, mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from protection.student_profile.src.fopd.profile_selector import ProfileSelector
from .runner import (
    ATTACK_TARGETS, CONFIG, HASH_SEED, INPUT_FIELDS, PRIVATE, ROOT,
    attack_metrics, load_lock, make_profile, parse_csv, release,
    select_fields, sha, split_indices, train_mi_order,
)


SEEDS = (17, 29, 43, 71, 101)
ARMS = ("MM-FOPD", "SwapG1ForG2-3", "AlignedG1G2-3", "TrainMI-SafeTopK-3")


def aligned_fields(arm: str, profile, task, seed: int, mi_order: list[str]) -> set[str]:
    if arm in {"MM-FOPD", "TrainMI-SafeTopK-3"}:
        return select_fields(arm, profile, task, seed, mi_order)
    if arm not in ARMS:
        raise ValueError("unknown alignment arm")
    original_ranked = ProfileSelector(copy.deepcopy(CONFIG)).select(profile, task)
    original = {item.record.record_id for item in original_ranked}
    if arm == "SwapG1ForG2-3":
        selected = (original - {"G1"}) | {"G2"}
    else:
        non_grades = [item.record.record_id for item in original_ranked
                      if item.record.record_id not in {"G1", "G2"}]
        if not non_grades:
            non_grades = [field for field in mi_order if field not in {"G1", "G2"}]
        selected = {"G1", "G2", non_grades[0]}
    if len(selected) != 3 or selected & PRIVATE or not selected <= set(INPUT_FIELDS):
        raise ValueError("aligned arm violated three-field nonprivate contract")
    return selected


def evaluate_arm(rows, profiles, train, dev, test, y, seed, mi_order, arm, *, selector=aligned_fields):
    selected = [selector(arm, profile, task, seed, mi_order)
                for profile, task in profiles]
    views = [release(row, fields) for row, fields in zip(rows, selected)]
    candidates = []
    for alpha in (1., 10., 100.):
        model = make_pipeline(DictVectorizer(), StandardScaler(with_mean=False),
                              Ridge(alpha=alpha, solver="lsqr"))
        model.fit([views[i] for i in train], y[train])
        loss = mean_absolute_error(y[dev], model.predict([views[i] for i in dev]))
        candidates.append((float(loss), alpha, model))
    _, alpha, model = min(candidates, key=lambda item: (item[0], item[1]))
    prediction = model.predict([views[i] for i in test])
    attacks = {}
    for target, labeler in ATTACK_TARGETS.items():
        labels = np.array([labeler(row) for row in rows])
        if any(len(set(labels[idx])) != 2 for idx in (train, dev, test)):
            raise ValueError("attack split has only one class")
        attacker_views = [release(row, fields, target)
                          for row, fields in zip(rows, selected)]
        candidates = []
        for name, estimator in (
            ("logistic", LogisticRegression(C=1., class_weight="balanced",
                                             solver="liblinear", max_iter=2000,
                                             random_state=seed)),
            ("random_forest", RandomForestClassifier(
                n_estimators=100, max_depth=6, min_samples_leaf=3,
                class_weight="balanced_subsample", random_state=seed, n_jobs=1)),
        ):
            attacker = make_pipeline(DictVectorizer(), StandardScaler(with_mean=False), estimator)
            attacker.fit([attacker_views[i] for i in train], labels[train])
            score = balanced_accuracy_score(labels[dev], attacker.predict([attacker_views[i] for i in dev]))
            candidates.append((float(score), name, attacker))
        _, attacker_name, attacker = max(candidates, key=lambda item: (item[0], item[1]))
        attacks[target] = {
            "selected_on_dev": attacker_name,
            "explicit_release_rate": float(np.mean([target in selected[i] for i in test])),
            **attack_metrics(labels[test], attacker.predict([attacker_views[i] for i in test]),
                             attacker.predict_proba([attacker_views[i] for i in test])[:, 1]),
        }
    return {
        "arm": arm, "seed": seed, "test_n": len(test),
        "ridge_alpha_selected_on_dev": alpha,
        "mae": float(mean_absolute_error(y[test], prediction)),
        "released_fields_mean": float(np.mean([len(selected[i]) for i in test])),
        "any_private_field_rate": float(np.mean([bool(selected[i] & PRIVATE) for i in test])),
        "G1_frequency": float(np.mean(["G1" in selected[i] for i in test])),
        "G2_frequency": float(np.mean(["G2" in selected[i] for i in test])),
        "field_release_frequency": {field: float(np.mean([field in selected[i] for i in test]))
                                    for field in INPUT_FIELDS},
        "residual_attack_macro_ba": float(np.mean([item["balanced_accuracy"] for item in attacks.values()])),
        "residual_attack_macro_auc": float(np.mean([item["auc"] for item in attacks.values()])),
        "attack_targets": attacks,
    }


def run(cache: Path, prior: Path, output: Path, seeds=SEEDS):
    if output.exists():
        raise FileExistsError("fresh output directory required")
    if os.environ.get("PYTHONHASHSEED") != HASH_SEED:
        raise ValueError("frozen PYTHONHASHSEED worker required")
    source_lock = load_lock(cache)
    rows = parse_csv((cache / "student-mat.csv").read_bytes(), 395)
    prior_summary = json.loads((prior / "summary.json").read_text(encoding="utf-8"))
    if prior_summary["protocol"] != "uci_math_raw_field_mmfopd_adapter_v1":
        raise ValueError("prior protocol mismatch")
    code_paths = [Path(__file__), ROOT / "experiments/mmfopd_uci/runner.py",
                  ROOT / "protection/student_profile/src/fopd/profile_selector.py"]
    code_hashes = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in code_paths}
    output.mkdir(parents=True, exist_ok=False)
    protocol = {
        "status": "FROZEN_EXPLORATORY_ALIGNMENT_PROBE",
        "protocol": "uci_math_equal_budget_field_alignment_probe_v1",
        "source_lock_sha256": sha((cache / "source-lock.json").read_bytes()),
        "prior_result_protocol": prior_summary["protocol"],
        "same_prior_test_rows": True,
        "test_informed_design": True,
        "claim_scope": "diagnostic_only_not_independent_test",
        "arms": ARMS, "seeds": list(seeds), "field_budget": 3,
        "aligned_arm": "G1 and G2 are grade-period fields named in the task; third is the highest-ranked non-grade field from unchanged MM-FOPD selection",
        "swap_arm": "replace selected G1 with G2 while keeping the other two selected fields",
        "privacy": "same policy-private field exclusions and four target-masked residual attacks as prior run",
        "source_code_sha256": code_hashes,
        "dependencies": {name: importlib.metadata.version(name)
                         for name in ("scikit-learn", "numpy", "scipy")},
        "real_api_calls": 0, "langsmith_upload": False,
    }
    (output / "protocol-lock.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    profiles = [make_profile(row, i) for i, row in enumerate(rows)]
    y = np.array([int(row["G3"]) for row in rows], dtype=float)
    per_seed = []
    for seed in seeds:
        train, dev, test = split_indices(rows, seed)
        prior_seed = json.loads((prior / f"seed-{seed}.json").read_text(encoding="utf-8"))
        mi_order = train_mi_order(rows, train, seed)
        if mi_order != prior_seed["train_mi_field_order"]:
            raise ValueError("train-only MI order drifted from prior run")
        arms = [evaluate_arm(rows, profiles, train, dev, test, y, seed, mi_order, arm)
                for arm in ARMS]
        prior_base = next(item for item in prior_seed["methods"] if item["method"] == "MM-FOPD")
        actual_base = next(item for item in arms if item["arm"] == "MM-FOPD")
        if abs(actual_base["mae"] - prior_base["mae"]) > 1e-9:
            raise ValueError("unchanged MM-FOPD MAE does not reproduce prior seed")
        per_seed.append({"seed": seed, "split_counts": {"train": len(train), "dev": len(dev), "test": len(test)},
                         "arms": arms})
        print(json.dumps({"progress": "seed_done", "seed": seed}), flush=True)
    if {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in code_paths} != code_hashes:
        raise ValueError("alignment probe source changed while running")
    if load_lock(cache) != source_lock:
        raise ValueError("UCI source lock changed while running")
    summary = []
    for arm in ARMS:
        selected = [next(item for item in run_item["arms"] if item["arm"] == arm)
                    for run_item in per_seed]
        keys = ("mae", "released_fields_mean", "any_private_field_rate",
                "G1_frequency", "G2_frequency", "residual_attack_macro_ba", "residual_attack_macro_auc")
        summary.append({"arm": arm,
                        **{key: {"mean": statistics.mean(item[key] for item in selected),
                                 "std": statistics.stdev(item[key] for item in selected)
                                 if len(selected) > 1 else 0.0} for key in keys},
                        "field_release_frequency": {
                            field: statistics.mean(item["field_release_frequency"][field]
                                                   for item in selected)
                            for field in INPUT_FIELDS}})
    final = {
        "status": "COMPLETED_EXPLORATORY_ALIGNMENT_PROBE",
        "protocol": protocol["protocol"], "source_students": len(rows),
        "test_evaluations_per_arm": sum(item["split_counts"]["test"] for item in per_seed),
        "seeds": list(seeds), "arms": summary,
        "paired_mae_differences": {
            arm: {"mean": statistics.mean(
                next(item for item in run_item["arms"] if item["arm"] == arm)["mae"]
                - next(item for item in run_item["arms"] if item["arm"] == "MM-FOPD")["mae"]
                for run_item in per_seed)}
            for arm in ARMS if arm != "MM-FOPD"
        },
        "no_raw_student_records": True,
        "limitations": [
            "Post-hoc diagnostic on test splits already inspected in the prior run; not independent confirmation.",
            "The grade task uses previous grades, not measured teaching effectiveness.",
            "Five repeated splits overlap and are not five independent cohorts.",
            "Equal three-field release does not equalize semantic information or all inference risks.",
        ],
    }
    (output / "summary.json").write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": final["status"], "output": str(output)}), flush=True)
    return final


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache/uci-student-performance-v1")
    parser.add_argument("--prior", type=Path, default=ROOT / "experiments/results/uci_math_20261013_01")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.seeds or len(set(args.seeds)) != len(args.seeds):
        parser.error("unique seeds required")
    if not args.worker:
        env = dict(os.environ, PYTHONHASHSEED=HASH_SEED, LANGSMITH_TRACING="false",
                   LANGCHAIN_TRACING_V2="false", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
        done = subprocess.run([sys.executable, "-X", "utf8", "-m",
                               "experiments.mmfopd_uci.alignment_probe", *sys.argv[1:], "--worker"],
                              cwd=ROOT, env=env)
        raise SystemExit(done.returncode)
    run(args.cache, args.prior, args.output, args.seeds)


if __name__ == "__main__":
    main()
