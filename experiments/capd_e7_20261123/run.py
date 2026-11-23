"""E7: the E5 design on Sum Leaks join secrets (privacy side).

Reuses the frozen E5 modules (workload, arms, run_spec, analysis) unchanged. Only the
data loader (join leakage lookup), the pooled K and the per-recipient grid differ
(see PREREG_E7.md). `--dry-run-seed S` prints decidability counts only.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
from pathlib import Path

from experiments.capd_e5_20261123 import run as e5
from experiments.capd_e5_20261123.workload import generate
from experiments.capd_e7_20261123.data import POOLED_K, data_dir, load_secrets, manifest_sha

HERE = Path(__file__).resolve().parent
COMPLETE_RATIOS = (0.0, 0.2)
SEEDS = tuple(range(10))
PER_RECIPIENT_BITS = (0.5, 1, 1.5, 2, 3)
GLOBAL_FRACTIONS = e5.GLOBAL_FRACTIONS
GATE_K = e5.GATE_K


def arm_parameters():
    yield ("no_defense", None)
    for budget in PER_RECIPIENT_BITS:
        yield ("per_recipient_bits", budget)
    for fraction in GLOBAL_FRACTIONS:
        yield ("global_bits", fraction)
    for k in GATE_K:
        yield ("pairwise_only", k)
    for k in GATE_K:
        yield ("ours", k)


def iter_specs(seeds=SEEDS):
    for c in COMPLETE_RATIOS:
        for seed in seeds:
            for arm, param in arm_parameters():
                yield e5.Spec(arm, param, POOLED_K, c, seed)


def run_grid(seeds=SEEDS, secrets=None):
    secrets = secrets if secrets is not None else load_secrets()
    rows, groups, streams = [], [], {}
    for spec in iter_specs(seeds):
        key = (spec.c, spec.seed)
        if key not in streams:
            streams[key] = generate(secrets, student_count=e5.STUDENT_COUNT,
                                    coalition_sizes=e5.COALITION_SIZES, seed=spec.seed,
                                    normal_requests=e5.NORMAL_REQUESTS, complete_ratio=spec.c)
        row, group_rows = e5.run_spec(spec, secrets, streams[key])
        rows.append(row)
        groups.extend(group_rows)
    return rows, groups


def environment() -> dict:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE,
                            capture_output=True, text=True).stdout.strip()
    return {"python": platform.python_version(), "git_commit": commit,
            "data_manifest_sha256": manifest_sha()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the pre-registered E7 grid.")
    parser.add_argument("--count", action="store_true")
    parser.add_argument("--dry-run-seed", type=int, default=None)
    parser.add_argument("--out", type=Path, default=HERE / "results")
    args = parser.parse_args()
    if args.count:
        print(len(tuple(iter_specs())))
        return
    if args.dry_run_seed is not None:
        from experiments.capd_e5_20261123.analysis import decidability

        rows, groups = run_grid(seeds=(args.dry_run_seed,))
        print(json.dumps(decidability(rows, groups), indent=2, ensure_ascii=False))
        return
    rows, groups = run_grid()
    args.out.mkdir(parents=True, exist_ok=True)
    e5.write_csv(args.out / "raw.csv", e5.RAW_COLUMNS, rows)
    e5.write_csv(args.out / "groups.csv", e5.GROUP_COLUMNS, groups)
    (args.out / "environment.json").write_text(json.dumps(environment(), indent=2) + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
