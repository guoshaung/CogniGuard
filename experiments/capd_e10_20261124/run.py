"""Run the frozen E10 grid on the E5 (synthetic), E6 (Eedi) and E7 (Sum Leaks) data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
from multiprocessing import Pool
from pathlib import Path

from experiments.capd_e5_20261123.arms import GateArm, NoDefense, prefer
from experiments.capd_e5_20261123.data import REPO, load_secrets
from experiments.capd_e5_20261123.workload import generate
from experiments.capd_e7_20261123.data import load_secrets as load_join_secrets
from experiments.capd_e10_20261124.arms import UnionView, Ws04Quota

HERE = Path(__file__).resolve().parent
CELLS = [("synthetic", K) for K in (8, 16, 32)] + [("eedi_exam", K) for K in (8, 16, 32)] + [("sumleaks", 0)]
CS = (0.0, 0.2)
SEEDS = tuple(range(10))
KS = (2, 3, 4)
DELTAS = (0.0, 0.5, 1.0, 2.0)


def root() -> Path:
    r = os.environ.get("COGNIGUARD_DATA_DIR")
    return Path(r) if r else REPO.parent / "cogniguard_data"


def arms():
    yield ("no_defense", None)
    for k in KS:
        yield ("ours", k)
        yield ("ws04_quota", k)
    for d in DELTAS:
        yield ("union_view", d)


def make(arm, param, secrets):
    if arm == "no_defense":
        return NoDefense()
    if arm == "ours":
        return GateArm(secrets, int(param))
    if arm == "ws04_quota":
        return Ws04Quota(secrets, int(param))
    return UnionView(secrets, float(param))


def gini(values):
    v = sorted(values)
    n = len(v)
    total = sum(v)
    if n == 0 or total == 0:
        return 0.0
    return sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(v)) / (n * total)


def run_one(arm, param, secrets, stream):
    policy = make(arm, param, secrets)
    by_id = {s.target_id: s for s in secrets}
    wmin = {}
    for s in secrets:
        for w in s.witness_sets:
            for u in w:
                wmin[u] = min(wmin.get(u, 99), len(w))
    delivered: dict[str, set] = {}
    per_user = {}
    strata = {"w2": [0.0, 0.0, 0, 0], "w3plus": [0.0, 0.0, 0, 0]}  # util, best, full, n
    complete_total = complete_refused = 0
    for req in stream.requests:
        chosen = policy.select(req.recipient_id, req.candidates)
        delivered.setdefault(req.recipient_id, set()).update((u.resource_id, u.unit_id) for u in chosen.units)
        if req.role == "normal":
            best = prefer(req.candidates).utility
            u = per_user.setdefault(req.recipient_id, [0.0, 0.0])
            u[0] += chosen.utility
            u[1] += best
            s = strata["w2" if wmin.get(req.unit, 99) <= 2 else "w3plus"]
            s[0] += chosen.utility
            s[1] += best
            s[2] += chosen.name == "full"
            s[3] += 1
        elif req.role == "complete":
            complete_total += 1
            complete_refused += chosen.name != "full"
    groups = []
    for g in stream.groups:
        view = set().union(*(delivered.get(m, set()) for m in g.members))
        violated = any(s.leakage_star(view) > s.tau + 1e-9 for s in {by_id[u[0]] for u in view})
        groups.append({"g": len(g.members), "w": len(g.witness), "violated": int(violated)})
    util = sum(x[0] for x in per_user.values())
    best = sum(x[1] for x in per_user.values())
    nfull = sum(s[2] for s in strata.values())
    nreq = sum(s[3] for s in strata.values())
    row = {
        "VR_all": sum(x["violated"] for x in groups) / len(groups),
        "UR_normal": util / best if best else 0.0,
        "DR_normal": 1 - nfull / nreq if nreq else 0.0,
        "CR_complete": complete_refused / complete_total if complete_total else 0.0,
        "gini_user_UR": gini([x[0] / x[1] for x in per_user.values() if x[1]]),
        "UR_w2": strata["w2"][0] / strata["w2"][1] if strata["w2"][1] else "",
        "UR_w3plus": strata["w3plus"][0] / strata["w3plus"][1] if strata["w3plus"][1] else "",
        "n_w2": strata["w2"][3], "n_w3plus": strata["w3plus"][3],
    }
    return row, groups


_cache = {}


def work(job):
    ds, K, c, seed = job
    if (ds, K) not in _cache:
        _cache[(ds, K)] = load_join_secrets(root() / ds) if ds == "sumleaks" else load_secrets(K, root() / ds)
    secrets = _cache[(ds, K)]
    stream = generate(secrets, student_count=60, coalition_sizes=(2, 2, 3, 3, 4, 4), seed=seed,
                      normal_requests=4, complete_ratio=c)
    rows, grows = [], []
    for arm, param in arms():
        row, groups = run_one(arm, param, secrets, stream)
        key = {"dataset": ds, "K": K, "c": c, "seed": seed, "arm": arm, "param": "" if param is None else param}
        rows.append({**key, **row})
        grows += [{**key, **g} for g in groups]
    return rows, grows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=HERE / "results")
    parser.add_argument("--dry-run-seed", type=int, default=None)
    args = parser.parse_args()
    seeds = (args.dry_run_seed,) if args.dry_run_seed is not None else SEEDS
    jobs = [(ds, K, c, s) for ds, K in CELLS for c in CS for s in seeds]
    rows, groups = [], []
    with Pool(4) as pool:
        for r, g in pool.imap_unordered(work, jobs):
            rows += r
            groups += g
    if args.dry_run_seed is not None:
        from experiments.capd_e10_20261124.analysis import decidability
        print(json.dumps(decidability(rows, groups), indent=2, ensure_ascii=False))
        return
    key = lambda r: (r["dataset"], r["K"], r["c"], r["arm"], str(r["param"]), r["seed"])
    rows.sort(key=key)
    groups.sort(key=key)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, data in (("raw.csv", rows), ("groups.csv", groups)):
        with (args.out / name).open("w", newline="") as h:
            w = csv.DictWriter(h, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    env = {"python": platform.python_version(), "git_commit": commit,
           "manifests": {d: hashlib.sha256((root() / d / "MANIFEST.json").read_bytes()).hexdigest()
                         for d in ("synthetic", "eedi_exam", "sumleaks")}}
    (args.out / "environment.json").write_text(json.dumps(env, indent=2) + "\n")
    print(len(rows), "rows")


if __name__ == "__main__":
    main()
