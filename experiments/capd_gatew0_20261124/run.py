"""Run the frozen Gate W0 grid. Data: $COGNIGUARD_DATA_DIR/{synthetic,eedi_exam}."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import random
import subprocess
from multiprocessing import Pool
from pathlib import Path

from experiments.capd_e5_20261123.data import REPO, load_secrets
from experiments.capd_gatew0_20261124.w0 import (CONTROL_METHODS, NOT_RUN, load_predicates,
                                                  run_attribution, run_control)

HERE = Path(__file__).resolve().parent
DATASETS = (("synthetic", 16), ("synthetic", 32))
KINDS = ("identity", "paraphrase", "fragment")
SEEDS = tuple(range(30))
BOOT, BOOT_SEED = 5000, 20261124


def root() -> Path:
    r = os.environ.get("COGNIGUARD_DATA_DIR")
    return Path(r) if r else REPO.parent / "cogniguard_data"


_cache = {}


def work(job):
    ds, K, kind, method, seed = job
    if (ds, K) not in _cache:
        _cache[(ds, K)] = (load_secrets(K, root() / ds), load_predicates(root() / ds))
    secrets, preds = _cache[(ds, K)]
    res = run_control(secrets, preds, seed=seed, method=method, kind=kind)
    return {"dataset": ds, "K": K, "transform": kind, "method": method, "seed": seed, "status": "RUN", **res}


def lower(values):
    rng = random.Random(BOOT_SEED)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(BOOT))
    return means[int(0.025 * BOOT)]


def judge(rows):
    by = {}
    for r in rows:
        by.setdefault((r["dataset"], r["K"], r["transform"], r["method"]), {})[r["seed"]] = r
    out = {"W0-0": {}, "W0-1": {}, "W0-2": {}}
    diffs0 = []
    for (ds, K, kind, m), runs in by.items():
        if m == "Wstar":
            c = by[(ds, K, kind, "Cstar")]
            for s in runs:
                if any(runs[s][x] != c[s][x] for x in ("harmful_releases", "UR_normal", "unneeded_refusal_rate")):
                    diffs0.append((ds, K, kind, s))
    out["W0-0"] = {"verdict": "Wstar 与 Cstar 完全一致" if not diffs0 else "存在差异", "differences": diffs0[:20]}
    provisional_value = False
    for ds, K in DATASETS:
        for kind in KINDS:
            means = {m: (sum(r["harmful_releases"] for r in by[(ds, K, kind, m)].values()) / len(SEEDS),
                         sum(r["unneeded_refusal_rate"] for r in by[(ds, K, kind, m)].values()) / len(SEEDS))
                     for m in ("F1_sha", "F2_minhash", "F3_bm25")}
            fbest = min(means, key=lambda m: means[m])
            a, b = by[(ds, K, kind, fbest)], by[(ds, K, kind, "F3_plus_Wstar")]
            d = [a[s]["harmful_releases"] - b[s]["harmful_releases"] for s in SEEDS]
            lo = lower(d)
            ur = means[fbest][1]
            ur_w = sum(r["unneeded_refusal_rate"] for r in b.values()) / len(SEEDS)
            cell_value = lo > 0 and ur_w <= ur
            provisional_value |= cell_value
            out["W0-1"][f"{ds}{K}/{kind}"] = {"F_best": fbest, "harmful_mean_F_best": means[fbest][0],
                                              "harmful_mean_F3_plus_Wstar": sum(r["harmful_releases"] for r in b.values()) / len(SEEDS),
                                              "diff_lower": lo, "unneeded_F_best": ur, "unneeded_F3_plus_Wstar": ur_w,
                                              "cell_extra_value": cell_value}
            w = by[(ds, K, kind, "Wstar")]
            a1 = {m: sum(r["harmful_releases"] for r in by[(ds, K, kind, m)].values()) / len(SEEDS)
                  for m in ("A1_minhash", "A1_bm25")}
            out["W0-2"][f"{ds}{K}/{kind}"] = {"Wstar_harmful": sum(r["harmful_releases"] for r in w.values()) / len(SEEDS),
                                              "best_A1_harmful": min(a1.values())}
    out["W0-1"]["provisional_verdict"] = "暂定有额外价值" if provisional_value else "暂定无额外价值"
    out["W0-1"]["final_verdict"] = "无法判定（F4_bge、F5_bge_rerank 为 NOT_RUN）"
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=HERE / "results")
    parser.add_argument("--dry-run-seed", type=int, default=None)
    args = parser.parse_args()
    seeds = (args.dry_run_seed,) if args.dry_run_seed is not None else SEEDS
    jobs = [(ds, K, kind, m, s) for ds, K in DATASETS for kind in KINDS for m in CONTROL_METHODS for s in seeds]
    with Pool(4) as pool:
        rows = list(pool.imap_unordered(work, jobs, chunksize=4))
    if args.dry_run_seed is not None:
        print(json.dumps({"rows": len(rows), "methods": sorted({r["method"] for r in rows}),
                          "any_harm_none": sum(r["harmful_releases"] for r in rows if r["method"] == "none")}))
        return
    rows.sort(key=lambda r: (r["dataset"], r["K"], r["transform"], r["method"], r["seed"]))
    for m in NOT_RUN:
        rows.append({"dataset": "*", "K": "*", "transform": "*", "method": m, "seed": "*", "status": "NOT_RUN"})
    args.out.mkdir(parents=True, exist_ok=True)
    fields = ["dataset", "K", "transform", "method", "seed", "status", "harmful_releases", "UR_normal",
              "unneeded_refusal_rate", "unit_precision", "unit_recall"]
    with (args.out / "control.csv").open("w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    attr = run_attribution(root() / "eedi_exam")
    with (args.out / "attribution.csv").open("w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=["scenario", "transform", "method", "status", "issuance_precision",
                                          "issuance_recall", "unit_precision", "unit_recall",
                                          "ambiguity_resolved_rate"])
        w.writeheader()
        w.writerows(attr)
    judgments = judge([r for r in rows if r["status"] == "RUN"])
    (args.out / "judgments.json").write_text(json.dumps(judgments, indent=2, ensure_ascii=False) + "\n")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    (args.out / "environment.json").write_text(json.dumps({"python": platform.python_version(),
                                                           "git_commit": commit}, indent=2) + "\n")
    print(json.dumps({k: v.get("verdict", v.get("provisional_verdict")) for k, v in judgments.items()},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
