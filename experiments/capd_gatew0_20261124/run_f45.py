"""Gate W0 F4/F5 supplement runner (PREREG_GATEW0_F45.md).

  --check        re-run frozen F3_bm25 on 2 seeds and compare with results/control.csv
  --calibrate    seed 99 only: null top-score distribution -> thresholds (results/f45/calibration.json)
  (default)      main grid seeds 0-29 for F4/F5, attribution rows, final W0-1 judgment
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import platform
import subprocess
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "results" / "f45"
METHODS = ("F4_bge", "F5_bge_rerank")
FROZEN_FBEST = ("F1_sha", "F2_minhash", "F3_bm25")
NULL_QUANTILE = 0.95
CAL_SEED = 99


def _setup():
    import torch
    torch.set_num_threads(2)


def _null_filter(kind):
    from experiments.capd_gatew0_20261124 import w0

    def keep(q, docs):
        sources = [t for t in docs if w0.transform(t, kind) == q]
        true_units = {u for t in sources for u, _ in docs[t]}
        return [t for t, items in docs.items() if not ({u for u, _ in items} & true_units)]
    return keep


def control_job(job):
    method, ds, K, kind, seed, threshold, calibrate = job
    _setup()
    from experiments.capd_gatew0_20261124 import f45, run as R, w0
    secrets, preds = R._cache.get((ds, K)) or R._cache.setdefault(
        (ds, K), (R.load_secrets(K, R.root() / ds), w0.load_predicates(R.root() / ds)))
    if calibrate:
        scores = []
        f45.install(method, null=_null_filter(kind), null_scores=scores)
        w0.run_control(secrets, preds, seed=seed, method="F3_bm25", kind=kind)
        return scores
    f45.install(method, threshold=threshold)
    res = w0.run_control(secrets, preds, seed=seed, method="F3_bm25", kind=kind)
    return {"dataset": ds, "K": K, "transform": kind, "method": method, "seed": seed, "status": "RUN", **res}


def check_job(job):
    ds, K, kind, seed = job
    from experiments.capd_gatew0_20261124 import run as R
    return R.work((ds, K, kind, "F3_bm25", seed))


def attribution_job(job):
    method, threshold = job
    _setup()
    from experiments.capd_gatew0_20261124 import f45, run as R, w0
    f45.install(method, threshold=threshold)
    frozen_one = w0._attr_one

    def only_dense(scen, issued, kind, m, rng):
        if m != "F3_bm25":
            return None
        row = frozen_one(scen, issued, kind, m, rng)
        row["method"] = method
        return row
    w0._attr_one = only_dense
    rows = [r for r in w0.run_attribution(R.root() / "eedi_exam") if r and r.get("status") == "RUN"]
    return rows


def frozen_rows():
    with (HERE / "results" / "control.csv").open() as h:
        rows = [r for r in csv.DictReader(h) if r["status"] == "RUN"]
    for r in rows:
        r["K"], r["seed"] = int(r["K"]), int(r["seed"])
        for x in ("harmful_releases",):
            r[x] = int(r[x])
        for x in ("UR_normal", "unneeded_refusal_rate"):
            r[x] = float(r[x])
    return rows


def judge_final(rows):
    from experiments.capd_gatew0_20261124 import run as R
    by = {}
    for r in rows:
        by.setdefault((r["dataset"], r["K"], r["transform"], r["method"]), {})[r["seed"]] = r
    out, any_value = {}, False
    pool = FROZEN_FBEST + METHODS
    for ds, K in R.DATASETS:
        for kind in R.KINDS:
            means = {m: (np.mean([x["harmful_releases"] for x in by[(ds, K, kind, m)].values()]),
                         np.mean([x["unneeded_refusal_rate"] for x in by[(ds, K, kind, m)].values()]))
                     for m in pool}
            fbest = min(means, key=lambda m: means[m])
            a, b = by[(ds, K, kind, fbest)], by[(ds, K, kind, "F3_plus_Wstar")]
            d = [a[s]["harmful_releases"] - b[s]["harmful_releases"] for s in R.SEEDS]
            lo = R.lower(d)
            ur_w = float(np.mean([x["unneeded_refusal_rate"] for x in b.values()]))
            value = lo > 0 and ur_w <= means[fbest][1]
            any_value |= value
            out[f"{ds}{K}/{kind}"] = {
                "F_best": fbest, "harmful_mean_F_best": float(means[fbest][0]),
                "harmful_mean_F3_plus_Wstar": float(np.mean([x["harmful_releases"] for x in b.values()])),
                "diff_lower": lo, "unneeded_F_best": float(means[fbest][1]), "unneeded_F3_plus_Wstar": ur_w,
                "cell_extra_value": bool(value),
                "per_method": {m: {"harmful_mean": float(v[0]), "unneeded_mean": float(v[1])} for m, v in means.items()},
            }
    out["final_verdict"] = "有额外价值" if any_value else "无额外价值"
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    p.add_argument("--calibrate", action="store_true")
    p.add_argument("--workers", type=int, default=4)
    a = p.parse_args()
    from experiments.capd_gatew0_20261124 import run as R
    ctx = mp.get_context("spawn")
    OUT.mkdir(parents=True, exist_ok=True)
    if a.check:
        frozen = {(r["dataset"], r["K"], r["transform"], r["seed"]): r for r in frozen_rows() if r["method"] == "F3_bm25"}
        jobs = [(ds, K, kind, s) for ds, K in R.DATASETS for kind in R.KINDS for s in (0, 1)]
        with ctx.Pool(a.workers) as pool:
            got = pool.map(check_job, jobs)
        bad = [j for j, g in zip(jobs, got)
               if (g["harmful_releases"], round(g["UR_normal"], 9)) !=
               (frozen[j]["harmful_releases"], round(frozen[j]["UR_normal"], 9))]
        print(json.dumps({"checked": len(jobs), "mismatches": bad}))
        return
    if a.calibrate:
        cal = {}
        for m in METHODS:
            jobs = [(m, ds, K, kind, CAL_SEED, None, True) for ds, K in R.DATASETS for kind in R.KINDS]
            with ctx.Pool(a.workers) as pool:
                scores = [s for part in pool.map(control_job, jobs) for s in part]
            cal[m] = {"null_n": len(scores), "quantile": NULL_QUANTILE,
                      "threshold": float(np.quantile(scores, NULL_QUANTILE)),
                      "null_median": float(np.median(scores))}
        (OUT / "calibration.json").write_text(json.dumps(cal, indent=2) + "\n")
        print(json.dumps(cal))
        return
    cal = json.loads((OUT / "calibration.json").read_text())
    jobs = [(m, ds, K, kind, s, cal[m]["threshold"], False)
            for m in METHODS for ds, K in R.DATASETS for kind in R.KINDS for s in R.SEEDS]
    with ctx.Pool(a.workers) as pool:
        rows = pool.map(control_job, jobs, chunksize=6)
        attr = [r for part in pool.map(attribution_job, [(m, cal[m]["threshold"]) for m in METHODS]) for r in part]
    rows.sort(key=lambda r: (r["dataset"], r["K"], r["transform"], r["method"], r["seed"]))
    fields = ["dataset", "K", "transform", "method", "seed", "status", "harmful_releases", "UR_normal",
              "unneeded_refusal_rate", "unit_precision", "unit_recall"]
    with (OUT / "control_f45.csv").open("w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    with (OUT / "attribution_f45.csv").open("w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(attr[0]))
        w.writeheader()
        w.writerows(attr)
    judgments = {"W0-1_frozen_recomputed": R.judge(frozen_rows())["W0-1"],
                 "W0-1_final": judge_final(frozen_rows() + rows)}
    (OUT / "judgments_f45.json").write_text(json.dumps(judgments, indent=2, ensure_ascii=False) + "\n")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    import sentence_transformers
    import torch
    (OUT / "environment.json").write_text(json.dumps({
        "python": platform.python_version(), "git_commit": commit, "torch": torch.__version__,
        "sentence_transformers": sentence_transformers.__version__, "device": "cpu"}, indent=2) + "\n")
    print(json.dumps({"final_verdict": judgments["W0-1_final"]["final_verdict"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
