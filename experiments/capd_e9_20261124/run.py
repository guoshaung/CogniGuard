"""Run the frozen E9 grid (CPU timing; single process per method call with SIGALRM timeouts)."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import random
import signal
import statistics
import subprocess
import time
import tracemalloc
from pathlib import Path

from experiments.capd_e9_20261124.solvers import bnb, dp, naive, quota_check

HERE = Path(__file__).resolve().parent
NS = (10, 100, 1000)
KS = (2, 4, 8)
MS = (2, 4, 8, 12, 16, 20, 24)
PS = (0.05, 0.2)
INSTANCES = 10
TIMEOUT = 1.0
EARLY_STOP = 3
MAX_FREE_UNITS = 20


class Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise Timeout()


signal.signal(signal.SIGALRM, _alarm)


def timed(fn, *args):
    signal.setitimer(signal.ITIMER_REAL, TIMEOUT)
    t0 = time.perf_counter_ns()
    try:
        out = fn(*args)
        return out, (time.perf_counter_ns() - t0) / 1e6, False
    except Timeout:
        return None, TIMEOUT * 1000, True
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def instance(N, m, p, seed):
    rng = random.Random(f"e9/{N}/{m}/{p}/{seed}")
    missing = frozenset(f"u{i}" for i in range(m))
    knowledge = {"recipient": frozenset({"held", "release"})}
    for a in range(N - 1):
        units = frozenset(u for u in missing if rng.random() < p) | frozenset({f"x{rng.randrange(50)}"})
        knowledge[f"a{a}"] = units
    return missing, knowledge


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=HERE / "results")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    grid = [(N, k, m, p) for N in NS for k in KS for m in MS for p in PS]
    if args.dry_run:
        grid = [(10, 2, 4, 0.2), (100, 4, 12, 0.05), (1000, 8, 24, 0.2)]
    from multiprocessing import Pool
    with Pool(4) as pool:
        rows = [r for chunk in pool.map(run_cell, [(c, args.dry_run) for c in grid]) for r in chunk]
    if args.dry_run:
        print(json.dumps(rows, indent=1, default=str)[:1500])
        return
    _write(rows, args)


def run_cell(arg):
    (N, k, m, p), dry = arg
    signal.signal(signal.SIGALRM, _alarm)
    rows = []
    for _cell in [0]:
        streak = {"dp": 0, "naive": 0, "bnb": 0}
        skipped = {"dp": False, "naive": False, "bnb": False}
        for i in range(INSTANCES if not dry else 3):
            missing, knowledge = instance(N, m, p, i)
            row = {"N": N, "k": k, "m": m, "p": p, "instance": i}
            results = {}
            for name, fn in (("dp", dp), ("naive", naive), ("bnb", bnb)):
                if name == "dp" and m > MAX_FREE_UNITS:
                    row[f"{name}_status"] = "too_large_conservative_refuse"
                    row[f"{name}_ms"] = ""
                    continue
                if skipped[name]:
                    row[f"{name}_status"] = "skipped_after_timeouts"
                    row[f"{name}_ms"] = ""
                    continue
                out, ms, to = timed(fn, missing, knowledge, "recipient", k)
                streak[name] = streak[name] + 1 if to else 0
                if streak[name] >= EARLY_STOP:
                    skipped[name] = True
                row[f"{name}_status"] = "timeout" if to else "ok"
                row[f"{name}_ms"] = ms
                if not to:
                    results[name] = out
            row["unsafe_dp"] = results["dp"][0] if "dp" in results else ""
            row["unsafe_naive"] = results["naive"][0] if "naive" in results else ""
            row["unsafe_bnb"] = results["bnb"][0] if "bnb" in results else ""
            row["need_dp"] = results["dp"][1] if "dp" in results else ""
            row["need_bnb"] = results["bnb"][1] if "bnb" in results else ""
            ok_dp_helpers = ""
            if "dp" in results and results["dp"][0]:
                cov = set().union(*(knowledge[h] for h in results["dp"][2])) if results["dp"][2] else set()
                ok_dp_helpers = missing <= cov
            row["dp_witness_valid"] = ok_dp_helpers
            t0 = time.perf_counter_ns()
            for _ in range(100):
                quota_check(0, m + 2, k)
            row["quota_ms"] = (time.perf_counter_ns() - t0) / 1e6 / 100
            if i == 0 and m <= MAX_FREE_UNITS:
                tracemalloc.start()
                timed(dp, missing, knowledge, "recipient", k)
                row["dp_peak_kib"] = tracemalloc.get_traced_memory()[1] / 1024
                tracemalloc.stop()
            rows.append(row)
    return rows


def _write(rows, args):
    args.out.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for r in rows for k in r}, key=lambda x: (x not in ("N", "k", "m", "p", "instance"), x))
    with (args.out / "latency.csv").open("w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    (args.out / "environment.json").write_text(json.dumps(
        {"python": platform.python_version(), "machine": platform.machine(), "processor": platform.processor(),
         "git_commit": commit, "timeout_s": TIMEOUT}, indent=2) + "\n")
    print(len(rows), "rows")


if __name__ == "__main__":
    main()
