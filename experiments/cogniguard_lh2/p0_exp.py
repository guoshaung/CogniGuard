"""P0 data generation and frozen evaluation (PREREG.md). Usage: python -m experiments.cogniguard_lh2.p0_exp {dev,test,analyze}"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from experiments.cogniguard_lh2 import model as M

OUT = Path(__file__).parent / "results"
CELLS = [(s, t, p, c) for s in M.STRUCTS for t in M.TOPOS for p in M.PROPS for c in M.COSTS]
SINGLE = ["V1_obs", "H1_obs", "d_capd", "d_acc", "coalition", "n_wit_h", "wsum", "belief_V1", "belief_cross_now",
          "KB_min", "H2", "H2_obs", "R_cross", "R_star"]
JOINT = ["V1_obs", "H1_obs", "d_capd", "d_acc", "coalition", "n_wit_h", "wsum", "belief_V1", "belief_cross_now", "KB_min"]


def job(args):
    seed, cell = args
    inst = M.gen_instance(seed, *cell)
    f = M.features(inst)
    f = {k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in f.items()}
    f.update({"seed": seed, "struct": cell[0], "topo": cell[1], "prop": cell[2], "cost": cell[3],
              "RA": inst["RA"], "RB": inst["RB"], "RC": inst["RC"], "E": inst["E"], "w": inst["w"],
              "hidden": inst["hidden"], "atype": inst["atype"]})
    return f


def gen(split, workers):
    per, base = (100, 0) if split == "dev" else (300, 5 * 10 ** 7)
    jobs = [(base + ci * 10 ** 5 + i, cell) for ci, cell in enumerate(CELLS) for i in range(per)]
    with Pool(workers) as pool:
        rows = list(pool.imap(job, jobs, chunksize=20))
    with gzip.open(OUT / f"{split}_rows.json.gz", "wt") as h:
        json.dump(rows, h)
    print(split, len(rows), "pos", sum(r["y"] for r in rows))


# ---------------------------------------------------------------------------------------- evaluation

def auc(y, s):
    y, s = np.asarray(y), np.asarray(s, float)
    pos, neg = y == 1, y == 0
    if pos.sum() == 0 or neg.sum() == 0:
        return float("nan")
    from scipy.stats import rankdata
    r = rankdata(s)
    return float((r[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * neg.sum()))


def auprc(y, s):
    from sklearn.metrics import average_precision_score
    return float(average_precision_score(y, s))


def ece(y, p, bins=10):
    y, p = np.asarray(y), np.asarray(p)
    e = 0.0
    for b in range(bins):
        m = (p >= b / bins) & ((p < (b + 1) / bins) if b < bins - 1 else (p <= 1))
        if m.any():
            e += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(e)


def X(rows, cols):
    return np.array([[r[c] for c in cols] for r in rows], float)


def fit(dev, cols):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
    m.fit(X(dev, cols), [r["y"] for r in dev])
    return m


def boot_delta(y, a, b, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    y, a, b = np.asarray(y), np.asarray(a), np.asarray(b)
    d = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        d.append(auc(y[i], a[i]) - auc(y[i], b[i]))
    d = np.array(d)
    d = d[~np.isnan(d)]
    return {"delta": auc(y, a) - auc(y, b), "lo": float(np.quantile(d, .025)), "hi": float(np.quantile(d, .975))}


def boot_auc(y, a, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    y, a = np.asarray(y), np.asarray(a)
    v = [auc(y[i], a[i]) for i in (rng.integers(0, len(y), len(y)) for _ in range(n))]
    v = np.array(v)
    v = v[~np.isnan(v)]
    return {"auc": auc(y, a), "lo": float(np.quantile(v, .025)), "hi": float(np.quantile(v, .975))}


def analyze():
    dev = json.load(gzip.open(OUT / "dev_rows.json.gz", "rt"))
    test = json.load(gzip.open(OUT / "test_rows.json.gz", "rt"))
    ydev = [r["y"] for r in dev]
    sign = {c: (1 if auc(ydev, [r[c] for r in dev]) >= 0.5 else -1) for c in SINGLE}
    mj, mh = fit(dev, JOINT), fit(dev, JOINT + ["H2"])
    sc = {c: [sign[c] * r[c] for r in test] for c in SINGLE}
    sc["JOINT"] = mj.predict_proba(X(test, JOINT))[:, 1].tolist()
    sc["JOINT+H2"] = mh.predict_proba(X(test, JOINT + ["H2"]))[:, 1].tolist()
    y = [r["y"] for r in test]
    out = {"n_test": len(test), "n_dev": len(dev), "base_rate_test": float(np.mean(y)),
           "events_test": {"ext_capable": int(sum(r["ext_capable"] for r in test)),
                           "ext_capable_and_crossed": int(sum(r["ext_capable"] and r["y_cross"] for r in test)),
                           "avoidable_y1": int(sum(y)), "y1_at_t0": int(sum(r["y"] and r["t_cross"] == 0 for r in test)),
                           "no_cross": int(sum(not r["y_cross"] for r in test))},
           "sign": sign, "joint_coef": dict(zip(JOINT, mj[-1].coef_[0].tolist())),
           "jointH2_coef": dict(zip(JOINT + ["H2"], mh[-1].coef_[0].tolist())), "auc": {}, "aux": {}}
    for k, s in sc.items():
        out["auc"][k] = boot_auc(y, s)
        out["aux"][k] = {"auprc": auprc(y, s)}
    for k in ("JOINT", "JOINT+H2", "R_star"):
        p = np.clip(sc[k], 0, 1)
        out["aux"][k].update({"brier": float(np.mean((p - np.asarray(y)) ** 2)), "ece": ece(y, p)})
    out["gate_delta"] = boot_delta(y, sc["JOINT+H2"], sc["JOINT"])
    out["rstar_minus_joint"] = boot_delta(y, sc["R_star"], sc["JOINT"])
    out["H2_minus_KBmin"] = boot_delta(y, sc["H2"], sc["KB_min"])
    out["by_struct"] = {}
    for s in M.STRUCTS:
        idx = [i for i, r in enumerate(test) if r["struct"] == s]
        yy = [y[i] for i in idx]
        g = lambda k: [sc[k][i] for i in idx]
        out["by_struct"][s] = {"n": len(idx), "pos": int(sum(yy)),
                               "gate_delta": boot_delta(yy, g("JOINT+H2"), g("JOINT")),
                               "auc": {k: auc(yy, g(k)) for k in sc}}
    out["by_factor"] = {}
    for fac, vals in (("topo", M.TOPOS), ("prop", list(M.PROPS)), ("cost", M.COSTS)):
        for v in vals:
            idx = [i for i, r in enumerate(test) if r[fac] == v]
            yy = [y[i] for i in idx]
            g = lambda k: [sc[k][i] for i in idx]
            out["by_factor"][f"{fac}={v}"] = {"n": len(idx), "pos": int(sum(yy)),
                                             "gate_delta": boot_delta(yy, g("JOINT+H2"), g("JOINT"), n=1000),
                                             "auc": {k: auc(yy, g(k)) for k in ("JOINT", "JOINT+H2", "R_star", "H2", "d_acc")}}
    n_struct_ok = sum(out["by_struct"][s]["gate_delta"]["lo"] > 0 for s in M.STRUCTS)
    gd = out["gate_delta"]
    out["gate"] = {"g1_not_renaming": False, "g2_delta>=0.05_and_lo>0": bool(gd["delta"] >= 0.05 and gd["lo"] > 0),
                   "g3_structs_with_lo>0": n_struct_ok, "g3_pass": n_struct_ok >= 3,
                   "g4_same_information": True, "g5_agent_mechanism": True}
    out["gate"]["PASS"] = all([out["gate"]["g1_not_renaming"], out["gate"]["g2_delta>=0.05_and_lo>0"],
                               out["gate"]["g3_pass"]])
    (OUT / "p0_analysis.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("base_rate_test", "events_test", "gate_delta", "rstar_minus_joint", "gate")}, indent=1))
    for k, v in out["auc"].items():
        print(f"{k:18s} {v['auc']:.3f} [{v['lo']:.3f},{v['hi']:.3f}]")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["dev", "test", "analyze"])
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    analyze() if a.stage == "analyze" else gen(a.stage, a.workers)
