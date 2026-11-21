"""Offline real-record benchmark; never imports an LLM client or teaching generator."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import urllib.request
import zipfile

import numpy as np
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_selection import mutual_info_regression
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score, mean_absolute_error, mean_squared_error, r2_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from protection.common.schemas import ProfileRecord, StudentProfile, Task
from protection.student_profile.src.fopd.profile_selector import ProfileSelector

ROOT = Path(__file__).resolve().parents[2]
URL = "https://archive.ics.uci.edu/static/public/320/student%2Bperformance.zip"
HASH_SEED = "20261013"
FIELDS = "school sex age address famsize Pstatus Medu Fedu Mjob Fjob reason guardian traveltime studytime failures schoolsup famsup paid activities nursery higher internet romantic famrel freetime goout Dalc Walc health absences G1 G2 G3".split()
INPUT_FIELDS = [f for f in FIELDS if f != "G3"]
# Research policy, not a legal classification or a dataset-provided annotation.
PRIVATE = {"health", "Dalc", "Walc", "romantic", "famrel", "Pstatus", "Medu", "Fedu", "Mjob", "Fjob", "guardian", "famsize"}
BEHAVIOR = {"studytime", "failures", "absences"}
SUPPORT = {"schoolsup", "famsup", "paid", "activities", "nursery", "higher"}
ACCESS = {"internet", "traveltime"}
NUMERIC = {"age", "Medu", "Fedu", "traveltime", "studytime", "failures", "famrel", "freetime", "goout", "Dalc", "Walc", "health", "absences", "G1", "G2"}
ATTACK_TARGETS = {
    "health": lambda r: int(int(r["health"]) <= 3),
    "romantic": lambda r: int(r["romantic"] == "yes"),
    "Pstatus": lambda r: int(r["Pstatus"] == "A"),
    "Dalc": lambda r: int(int(r["Dalc"]) >= 2),
}
METHODS = ["FullProfile", "DropSensitive", "TaskTopK-3", "SafeTaskTopK-3", "RandomSafe-3", "TrainMI-SafeTopK-3", "MM-FOPD", "MM-FOPD-no-orthogonal", "MM-FOPD-no-attention", "MM-FOPD-no-bottleneck"]
CONFIG = {"fopd": {
    "use_enhanced_fopd": True,
    "components": {"use_orthogonal": True, "use_task_attention": True, "use_bottleneck": True},
    "top_k_profile_records": 3, "relevance_threshold": .15, "sensitivity_threshold": .70,
    "weights": {"rel": .50, "tag": .25, "confidence": .15, "recency": .10, "sens_gate": .20},
    "bottleneck": {"max_mutual_info_bits": 6., "privacy_lambda": .5},
    "unit_budget": {"max_units": 3, "allowed": ["mastery", "behavior_aggregate", "educational_context", "access_context"]},
}}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def parse_csv(blob: bytes, expected_count: int) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(blob.decode("utf-8-sig")), delimiter=";")
    if reader.fieldnames != FIELDS:
        raise ValueError("unexpected UCI columns")
    rows = list(reader)
    if len(rows) != expected_count or any(set(r) != set(FIELDS) or any(v in ("", "?", None) for v in r.values()) for r in rows):
        raise ValueError("unexpected UCI row count or missing cells")
    for row in rows:
        for field in NUMERIC | {"G3"}:
            int(row[field])
        if any(not 0 <= int(row[f]) <= 20 for f in ("G1", "G2", "G3")):
            raise ValueError("invalid grade range")
    return rows


def prepare(cache: Path) -> dict:
    if cache.exists():
        return load_lock(cache)
    request = urllib.request.Request(URL, headers={"User-Agent": "CogniGuard-public-dataset-research/1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        if not response.url.startswith("https://archive.ics.uci.edu/"):
            raise ValueError("unexpected download destination")
        blob = response.read(1_000_001)
    if len(blob) > 1_000_000:
        raise ValueError("archive too large")
    outer = zipfile.ZipFile(io.BytesIO(blob))
    inner = zipfile.ZipFile(io.BytesIO(outer.read("student.zip")))
    files = {name: inner.read(name) for name in ("student-mat.csv", "student-por.csv", "student.txt", "student-merge.R")}
    for name, count in (("student-mat.csv", 395), ("student-por.csv", 649)):
        parse_csv(files[name], count)
    cache.mkdir(parents=True, exist_ok=False)
    with (cache / "source.zip").open("xb") as handle:
        handle.write(blob)
    for name, content in files.items():
        with (cache / name).open("xb") as handle:
            handle.write(content)
    lock = {
        "dataset": "UCI Student Performance", "doi": "10.24432/C5TG7T", "url": URL,
        "license": "CC-BY-4.0 (UCI dataset page)", "checked_client_date": "2026-10-13",
        "archive_sha256": sha(blob), "files": {name: sha(content) for name, content in files.items()},
        "rows": {"student-mat.csv": 395, "student-por.csv": 649},
        "note": "Subjects overlap; only mathematics is evaluated. Hashes lock observed official bytes, not an upstream signed checksum.",
    }
    dump(cache / "source-lock.json", lock)
    return lock


def load_lock(cache: Path) -> dict:
    lock = json.loads((cache / "source-lock.json").read_text(encoding="utf-8"))
    if lock["url"] != URL or sha((cache / "source.zip").read_bytes()) != lock["archive_sha256"]:
        raise ValueError("source archive mismatch")
    for name, digest in lock["files"].items():
        if name not in {"student-mat.csv", "student-por.csv", "student.txt", "student-merge.R"} or sha((cache / name).read_bytes()) != digest:
            raise ValueError("cached file mismatch")
    return lock


def field_policy(field: str) -> tuple[str, str, float]:
    if field in PRIVATE:
        return "sensitive_profile", "personal_background", .9
    if field in {"G1", "G2"}:
        return "mastery", "math_progress", .25
    if field in BEHAVIOR:
        return "behavior_aggregate", "math_progress", .35
    if field in SUPPORT:
        return "educational_context", "math_progress", .4
    if field in ACCESS:
        return "access_context", "math_progress", .45
    return "background_context", "personal_background", .5


def make_profile(row: dict[str, str], index: int) -> tuple[StudentProfile, Task]:
    # G3 never enters the selector; no inferred preferences, errors or fabricated attributes.
    records = []
    for field in INPUT_FIELDS:
        kind, knowledge, sensitivity = field_policy(field)
        value = float(row[field]) / 20 if kind == "mastery" else f"{field}={row[field]}"
        records.append(ProfileRecord(field, kind, knowledge, value, 1., sensitivity, ""))
    sid = f"uci-math-{index}"
    profile = StudentProfile(sid, {}, records)
    task = Task(f"grade-{index}", sid,
                "Predict third period mathematics grade using previous grades G1 G2 studytime absences failures schoolsup famsup paid activities nursery higher internet traveltime",
                "math_progress", "grade_prediction", False)
    return profile, task


def select_fields(method: str, profile: StudentProfile, task: Task, seed: int, mi_order: list[str]) -> set[str]:
    if method == "FullProfile":
        return set(INPUT_FIELDS)
    if method == "DropSensitive":
        return set(INPUT_FIELDS) - PRIVATE
    if method == "RandomSafe-3":
        rng = random.Random(f"{seed}:{profile.student_id}")
        return set(rng.sample(sorted(set(INPUT_FIELDS) - PRIVATE), 3))
    if method == "TrainMI-SafeTopK-3":
        return set(mi_order[:3])
    config = copy.deepcopy(CONFIG)
    if method == "TaskTopK-3":
        selected = ProfileSelector(config).score_records(profile, task)[:3]
    elif method == "SafeTaskTopK-3":
        selected = [x for x in ProfileSelector(config).score_records(profile, task) if x.record.record_id not in PRIVATE][:3]
    else:
        switches = {"MM-FOPD-no-orthogonal": "use_orthogonal", "MM-FOPD-no-attention": "use_task_attention", "MM-FOPD-no-bottleneck": "use_bottleneck"}
        if method != "MM-FOPD" and method not in switches:
            raise ValueError("unknown method")
        if method in switches:
            config["fopd"]["components"][switches[method]] = False
        selected = ProfileSelector(config).select(profile, task)
    result = {x.record.record_id for x in selected}
    if not result <= set(INPUT_FIELDS):
        raise ValueError("selector returned unknown field")
    return result


def release(row: dict[str, str], selected: set[str], exclude: str | None = None) -> dict[str, float]:
    if not selected <= set(INPUT_FIELDS):
        raise ValueError("invalid release fields")
    result = {}
    for field in INPUT_FIELDS:
        if field == exclude:
            continue
        present = field in selected
        result[f"present:{field}"] = float(present)
        if present:
            if field in NUMERIC:
                result[f"value:{field}"] = float(row[field])
            else:
                result[f"value:{field}={row[field]}"] = 1.
    return result


def split_indices(rows: list[dict[str, str]], seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y = np.array([int(r["G3"]) >= 10 for r in rows])
    train_dev, test = train_test_split(np.arange(len(rows)), test_size=.2, random_state=seed, stratify=y)
    train, dev = train_test_split(train_dev, test_size=.25, random_state=seed, stratify=y[train_dev])
    return train, dev, test


def train_mi_order(rows: list[dict[str, str]], train: np.ndarray, seed: int) -> list[str]:
    candidates = sorted(set(INPUT_FIELDS) - PRIVATE)
    # One discrete code per field; mapping is fitted only on training students.
    matrix = []
    for field in candidates:
        mapping = {value: i for i, value in enumerate(sorted({rows[i][field] for i in train}))}
        matrix.append([mapping[rows[i][field]] for i in train])
    scores = mutual_info_regression(np.array(matrix).T, [int(rows[i]["G3"]) for i in train], discrete_features=True, random_state=seed)
    return [field for _, field in sorted(zip(scores, candidates), key=lambda pair: (-pair[0], pair[1]))]


def grade_metrics(y: np.ndarray, prediction: np.ndarray) -> dict:
    return {"mae": float(mean_absolute_error(y, prediction)), "rmse": float(mean_squared_error(y, prediction) ** .5), "r2": float(r2_score(y, prediction))}


def attack_metrics(y: np.ndarray, prediction: np.ndarray, probability: np.ndarray) -> dict:
    return {"balanced_accuracy": float(balanced_accuracy_score(y, prediction)), "auc": float(roc_auc_score(y, probability)), "positive_count": int(y.sum()), "negative_count": int(len(y) - y.sum())}


def evaluate_seed(rows: list[dict[str, str]], seed: int) -> dict:
    random.seed(seed)
    np.random.seed(seed)
    train, dev, test = split_indices(rows, seed)
    y = np.array([int(r["G3"]) for r in rows], dtype=float)
    profiles = [make_profile(r, i) for i, r in enumerate(rows)]
    mi_order = train_mi_order(rows, train, seed)
    dummy = DummyRegressor(strategy="mean").fit(np.zeros((len(train), 1)), y[train])
    results = []
    for method in METHODS:
        selected = [select_fields(method, p, t, seed, mi_order) for p, t in profiles]
        views = [release(r, s) for r, s in zip(rows, selected)]
        candidates = []
        for alpha in (1., 10., 100.):
            model = make_pipeline(DictVectorizer(), StandardScaler(with_mean=False), Ridge(alpha=alpha, solver="lsqr"))
            model.fit([views[i] for i in train], y[train])
            loss = mean_absolute_error(y[dev], model.predict([views[i] for i in dev]))
            candidates.append((float(loss), alpha, model))
        _, alpha, model = min(candidates, key=lambda item: (item[0], item[1]))
        prediction = model.predict([views[i] for i in test])
        attacks = {}
        for target, labeler in ATTACK_TARGETS.items():
            labels = np.array([labeler(r) for r in rows])
            if any(len(set(labels[idx])) != 2 for idx in (train, dev, test)):
                raise ValueError("attack split has only one class")
            # Remove the target value AND its own availability bit for all methods.
            # This isolates inference from other released fields, separate from explicit disclosure.
            attacker_views = [release(r, s, target) for r, s in zip(rows, selected)]
            attackers = []
            for name, estimator in (
                ("logistic", LogisticRegression(C=1., class_weight="balanced", solver="liblinear", max_iter=2000, random_state=seed)),
                ("random_forest", RandomForestClassifier(n_estimators=100, max_depth=6, min_samples_leaf=3, class_weight="balanced_subsample", random_state=seed, n_jobs=1)),
            ):
                attacker = make_pipeline(DictVectorizer(), StandardScaler(with_mean=False), estimator)
                attacker.fit([attacker_views[i] for i in train], labels[train])
                validation_score = balanced_accuracy_score(labels[dev], attacker.predict([attacker_views[i] for i in dev]))
                attackers.append((float(validation_score), name, attacker))
            _, attacker_name, attacker = max(attackers, key=lambda item: (item[0], item[1]))
            target_prediction = attacker.predict([attacker_views[i] for i in test])
            probability = attacker.predict_proba([attacker_views[i] for i in test])[:, 1]
            attacks[target] = {
                "selected_on_dev": attacker_name,
                "explicit_release_rate": float(np.mean([target in selected[i] for i in test])),
                **attack_metrics(labels[test], target_prediction, probability),
                "majority_baseline_balanced_accuracy": .5, "constant_score_baseline_auc": .5,
            }
        results.append({
            "method": method, "seed": seed, "test_n": len(test), "ridge_alpha_selected_on_dev": alpha,
            **grade_metrics(y[test], prediction),
            "released_fields_mean": float(np.mean([len(selected[i]) for i in test])),
            "released_fields_min": min(len(selected[i]) for i in test), "released_fields_max": max(len(selected[i]) for i in test),
            "private_field_release_fraction": float(np.mean([len(selected[i] & PRIVATE) / len(PRIVATE) for i in test])),
            "any_private_field_rate": float(np.mean([bool(selected[i] & PRIVATE) for i in test])),
            "residual_attack_macro_ba": float(np.mean([a["balanced_accuracy"] for a in attacks.values()])),
            "residual_attack_macro_auc": float(np.mean([a["auc"] for a in attacks.values()])),
            "attack_targets": attacks,
            "field_release_frequency": {field: float(np.mean([field in selected[i] for i in test])) for field in INPUT_FIELDS},
        })
        print(json.dumps({"progress": "method_done", "seed": seed, "method": method, "mae": results[-1]["mae"]}), flush=True)
    return {
        "seed": seed, "split_counts": {"train": len(train), "dev": len(dev), "test": len(test)},
        "partition_hashes": {name: sha(np.sort(idx).astype("<i8").tobytes()) for name, idx in (("train", train), ("dev", dev), ("test", test))},
        "test_row_indices_local_only": [int(i) for i in test],
        "dummy_mean_grade": grade_metrics(y[test], dummy.predict(np.zeros((len(test), 1)))),
        "train_mi_field_order": mi_order, "methods": results,
    }


def source_hashes() -> dict:
    paths = [Path(__file__), ROOT / "protection/common/schemas.py", ROOT / "protection/common/text_utils.py"]
    paths += sorted((ROOT / "protection/student_profile/src/fopd").glob("*.py"))
    return {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths}


def run(cache: Path, output: Path, seeds: list[int]) -> dict:
    if output.exists():
        raise FileExistsError("output must be a fresh directory")
    if os.environ.get("PYTHONHASHSEED") != HASH_SEED:
        raise ValueError("worker must start with frozen PYTHONHASHSEED")
    lock = load_lock(cache)
    rows = parse_csv((cache / "student-mat.csv").read_bytes(), 395)
    output.mkdir(parents=True, exist_ok=False)
    code_hashes = source_hashes()
    protocol = {
        "status": "FROZEN_BEFORE_EVALUATION", "protocol": "uci_math_raw_field_mmfopd_adapter_v1",
        "source_lock": lock, "subject": "mathematics_only", "n_rows": len(rows), "seeds": seeds,
        "split": "repeated student-row 60/20/20, stratified by G3>=10; one math row per student; splits overlap across seeds",
        "hash_seed": HASH_SEED, "selector_config": CONFIG, "methods": METHODS,
        "private_fields": sorted(PRIVATE),
        "field_adapter": {field: dict(zip(("type", "knowledge", "sensitivity"), field_policy(field))) for field in INPUT_FIELDS},
        "mapping_note": "G1/G2 become normalized observed-performance mastery proxies; all other values remain real source attributes. No errors, teaching preferences, multimodal measurements or knowledge-level annotations are invented.",
        "release_boundary": "selected raw fields, not legacy build_context_card or full ProtectionPipeline; identifiers, G3 and unselected values excluded; field availability is visible",
        "utility": "Ridge grade prediction, alpha selected on dev among 1/10/100; train-only preprocessing; no refit on dev; no clipping",
        "privacy": "four binary targets; own target value and its availability bit removed from all attacker inputs; train logistic and RF, select per method/target on dev; report test balanced accuracy/AUC separately from explicit release",
        "attack_labels": {"health": "self-report <=3 of 5", "romantic": "yes", "Pstatus": "parents apart A", "Dalc": "weekday alcohol >=2 of 5"},
        "source_code_sha256": code_hashes,
        "dependencies": {name: importlib.metadata.version(name) for name in ("scikit-learn", "numpy", "scipy")},
        "real_api_calls": 0, "langsmith_upload": False,
    }
    dump(output / "protocol-lock.json", protocol)
    runs = []
    for seed in seeds:
        result = evaluate_seed(rows, seed)
        dump(output / f"seed-{seed}.json", result)
        runs.append(result)
    if source_hashes() != code_hashes:
        raise ValueError("source changed while running")
    summary = []
    keys = ("mae", "rmse", "r2", "released_fields_mean", "private_field_release_fraction", "any_private_field_rate", "residual_attack_macro_ba", "residual_attack_macro_auc")
    for method in METHODS:
        items = [next(item for item in run["methods"] if item["method"] == method) for run in runs]
        summary.append({"method": method, "seeds": len(seeds), **{key: {"mean": statistics.mean(item[key] for item in items), "std": statistics.stdev(item[key] for item in items) if len(items) > 1 else 0.} for key in keys},
                        "field_release_frequency": {field: statistics.mean(item["field_release_frequency"][field] for item in items) for field in INPUT_FIELDS},
                        "attack_targets": {target: {key: {"mean": statistics.mean(item["attack_targets"][target][key] for item in items), "std": statistics.stdev(item["attack_targets"][target][key] for item in items) if len(items) > 1 else 0.} for key in ("balanced_accuracy", "auc", "explicit_release_rate")} for target in ATTACK_TARGETS}})
    unique_test = len({i for run in runs for i in run["test_row_indices_local_only"]})
    contrasts = []
    for comparator in ("SafeTaskTopK-3", "TrainMI-SafeTopK-3", "MM-FOPD-no-orthogonal", "MM-FOPD-no-attention", "MM-FOPD-no-bottleneck"):
        differences = []
        for run_item in runs:
            by_method = {item["method"]: item for item in run_item["methods"]}
            differences.append(by_method["MM-FOPD"]["mae"] - by_method[comparator]["mae"])
        contrasts.append({"contrast": f"MM-FOPD minus {comparator}", "metric": "grade_MAE", "mean": statistics.mean(differences), "std": statistics.stdev(differences) if len(differences) > 1 else 0., "negative_favors_mmfopd": True})
    final = {
        "status": "COMPLETED_OFFLINE_REAL_RECORDS", "protocol": protocol["protocol"], "n_source_students": len(rows),
        "test_evaluations_per_method": sum(run["split_counts"]["test"] for run in runs), "unique_test_students_across_seeds": unique_test,
        "seeds": seeds, "methods": summary, "paired_seed_contrasts": contrasts,
        "dummy_grade_mae": {"mean": statistics.mean(run["dummy_mean_grade"]["mae"] for run in runs), "std": statistics.stdev(run["dummy_mean_grade"]["mae"] for run in runs) if len(runs) > 1 else 0.},
        "target_class_counts": {target: {"positive": sum(labeler(r) for r in rows), "negative": sum(not labeler(r) for r in rows)} for target, labeler in ATTACK_TARGETS.items()},
        "real_api_calls": 0, "raw_student_records_in_shared_output": False,
        "limitations": [
            "One historical small two-school sample; not representative of current Chinese students.",
            "Real tabular profiles, not student dialogues, fine-grained behavior sequences or multimodal measurements.",
            "Adapter configuration changes allowed information-unit types; not the identical original synthetic protocol.",
            "Raw-selected-field boundary differs from legacy context-card serialization; no end-to-end cloud-teaching claim.",
            "Private-field designations are predeclared experimental policy, not legal conclusions or per-task necessity gold labels.",
            "No field-recall/F1 against fabricated necessary-field ground truth; grade prediction is not teaching efficacy.",
            "Repeated test splits overlap; mean/std are descriptive, not independent replications or a significance test.",
            "Residual inference removes the target itself for every method and does not prove differential privacy or universal safety.",
            "The no-orthogonal ablation jointly removes projection and sensitivity gating in the unchanged implementation.",
        ],
    }
    dump(output / "summary.json", final)
    print(json.dumps({"status": final["status"], "output": str(output), "real_api_calls": 0}), flush=True)
    return final


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache/uci-student-performance-v1")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--seeds", nargs="+", type=int, default=[17, 29, 43, 71, 101])
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.prepare:
        print(json.dumps(prepare(args.cache), indent=2))
        return
    if args.output is None or not args.seeds or len(set(args.seeds)) != len(args.seeds):
        parser.error("fresh --output and unique seeds required")
    if not args.worker:
        env = dict(os.environ, PYTHONHASHSEED=HASH_SEED, LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
        completed = subprocess.run([sys.executable, "-X", "utf8", "-m", "experiments.mmfopd_uci.runner", *sys.argv[1:], "--worker"], cwd=ROOT, env=env)
        raise SystemExit(completed.returncode)
    run(args.cache, args.output, args.seeds)


if __name__ == "__main__":
    main()
