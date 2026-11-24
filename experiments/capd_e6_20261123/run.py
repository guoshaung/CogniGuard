"""E6: the E5 design on the Eedi "which question will be set" secrets.

Reuses the frozen E5 modules (workload, arms, run_spec, analysis) unchanged.
Only the data directory and the per-recipient grid differ (see PREREG_E6.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path

from experiments.capd_e5_20261123 import run as e5
from experiments.capd_e5_20261123.data import REPO, load_secrets
from experiments.capd_e5_20261123.workload import generate

HERE = Path(__file__).resolve().parent
KS = (8, 16, 32)
COMPLETE_RATIOS = (0.0, 0.2)
SEEDS = tuple(range(10))
PER_RECIPIENT_BITS = (1, 2, 3, 4, 6, 8, 12, 16)
GLOBAL_FRACTIONS = e5.GLOBAL_FRACTIONS
GATE_K = e5.GATE_K


def data_dir() -> Path:
    root = os.environ.get("COGNIGUARD_DATA_DIR")
    return (Path(root) if root else REPO.parent / "cogniguard_data") / "eedi_exam"


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
    for K in KS:
        for c in COMPLETE_RATIOS:
            for seed in seeds:
                for arm, param in arm_parameters():
                    yield e5.Spec(arm, param, K, c, seed)


def run_grid(seeds=SEEDS):
    rows, groups, cache, streams = [], [], {}, {}
    for spec in iter_specs(seeds):
        if spec.K not in cache:
            cache[spec.K] = load_secrets(spec.K, data_dir())
        secrets = cache[spec.K]
        key = (spec.K, spec.c, spec.seed)
        if key not in streams:
            streams[key] = generate(
                secrets,
                student_count=e5.STUDENT_COUNT,
                coalition_sizes=e5.COALITION_SIZES,
                seed=spec.seed,
                normal_requests=e5.NORMAL_REQUESTS,
                complete_ratio=spec.c,
            )
        row, group_rows = e5.run_spec(spec, secrets, streams[key])
        rows.append(row)
        groups.extend(group_rows)
    return rows, groups


def environment() -> dict:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE,
                            capture_output=True, text=True).stdout.strip()
    manifest = (data_dir() / "MANIFEST.json").read_bytes()
    return {"python": platform.python_version(), "git_commit": commit,
            "data_manifest_sha256": hashlib.sha256(manifest).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the pre-registered E6 grid.")
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
    e5.write_csv(args.out / "raw.csv", e5.RAW_COLUMNS, rows)
    e5.write_csv(args.out / "groups.csv", e5.GROUP_COLUMNS, groups)
    (args.out / "environment.json").write_text(json.dumps(environment(), indent=2) + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
