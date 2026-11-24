"""Run the frozen Gate 0-2 grid. Data: $COGNIGUARD_DATA_DIR/{synthetic,eedi_exam}."""

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

from experiments.capd_e5_20261123.data import REPO, load_secrets
from experiments.capd_gate012_20261124.sim import ARMS, Noise, make_world, run_arm

HERE = Path(__file__).resolve().parent
DATASETS = (("synthetic", 16), ("synthetic", 32), ("eedi_exam", 16))
FS = (2, 4, 8)
SEEDS = tuple(range(30))
G2_ARMS = ("B2", "B2b", "B3", "Ours")
G2_CELLS = {
    "base": Noise(), "r0.8": Noise(r=0.8), "r0.5": Noise(r=0.5),
    "q0.05": Noise(q=0.05), "q0.2": Noise(q=0.2), "dup0.1": Noise(p_dup=0.1),
    "phi0.01": Noise(phi=0.01), "mix0.2": Noise(p_mix=0.2), "delay5": Noise(delay=5),
    "combined": Noise(r=0.8, q=0.05, p_dup=0.1, phi=0.01, p_mix=0.2, delay=5),
    "phic0.01": Noise(phi_c=0.01), "phic0.05": Noise(phi_c=0.05),
}


def data_root() -> Path:
    root = os.environ.get("COGNIGUARD_DATA_DIR")
    return Path(root) if root else REPO.parent / "cogniguard_data"


def jobs():
    for ds, K in DATASETS:
        for f in FS:
            for seed in SEEDS:
                for graph in ("sparse", "complete"):
                    for mode in ("coalition", "benign"):
                        yield ("G01", ds, K, graph, mode, f, f, "base", ARMS, seed)
                for cell in G2_CELLS:
                    if cell != "base":
                        yield ("G2", ds, K, "sparse", "coalition", f, f, cell, G2_ARMS, seed)
                yield ("BV", ds, K, "sparse", "coalition", f, 2 * f, "base", ARMS, seed)


_cache: dict = {}


def work(job):
    phase, ds, K, graph, mode, f, f_true, cell, arms, seed = job
    key = (ds, K)
    if key not in _cache:
        _cache[key] = load_secrets(K, data_root() / ds)
    world = make_world(_cache[key], seed=seed, graph=graph, f=f, f_true=f_true, mode=mode)
    rows = []
    for arm in arms:
        res = run_arm(world, arm, G2_CELLS[cell], seed)
        rows.append({"phase": phase, "dataset": ds, "K": K, "graph": graph, "mode": mode,
                     "f": f, "f_true": f_true, "noise": cell, "arm": arm, "seed": seed, **res})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run-seed", type=int, default=None)
    parser.add_argument("--out", type=Path, default=HERE / "results")
    parser.add_argument("--procs", type=int, default=4)
    args = parser.parse_args()
    all_jobs = list(jobs())
    if args.dry_run_seed is not None:
        all_jobs = [j[:-1] + (args.dry_run_seed,) for j in all_jobs if j[-1] == 0]
    with Pool(args.procs) as pool:
        rows = [r for chunk in pool.imap_unordered(work, all_jobs, chunksize=8) for r in chunk]
    if args.dry_run_seed is not None:
        from experiments.capd_gate012_20261124.analysis import decidability
        print(json.dumps(decidability(rows), indent=2))
        return
    rows.sort(key=lambda r: (r["phase"], r["dataset"], r["K"], r["graph"], r["mode"], r["f"],
                             r["noise"], r["arm"], r["seed"]))
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "raw.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True,
                            text=True).stdout.strip()
    env = {"python": platform.python_version(), "git_commit": commit,
           "manifests": {ds: hashlib.sha256((data_root() / ds / "MANIFEST.json").read_bytes()).hexdigest()
                         for ds, _ in DATASETS}}
    (args.out / "environment.json").write_text(json.dumps(env, indent=2) + "\n")
    print(len(rows), "rows")


if __name__ == "__main__":
    main()
