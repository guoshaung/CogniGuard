"""Run the pre-registered E5 grid. `--dry-run-seed S` runs one seed and prints only
whether each hypothesis can be decided (counts, no metric values)."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from experiments.capd_e5_20261123.arms import (
    GateArm,
    GlobalBits,
    NoDefense,
    PerRecipientBits,
    no_defense_spend,
    prefer,
)
from experiments.capd_e5_20261123.data import load_secrets, manifest_sha
from experiments.capd_e5_20261123.workload import Stream, generate

HERE = Path(__file__).resolve().parent
STUDENT_COUNT = 60
COALITION_SIZES = (2, 2, 3, 3, 4, 4)
NORMAL_REQUESTS = 4
KS = (8, 16, 32)
COMPLETE_RATIOS = (0.0, 0.2)
SEEDS = tuple(range(10))
PER_RECIPIENT_BITS = (1, 2, 3, 4, 6, 8, 12)
GLOBAL_FRACTIONS = (0.5, 0.75, 0.9, 0.95, 0.98, 1.0)
GATE_K = (2, 3, 4)

RAW_COLUMNS = (
    "arm", "param", "K", "c", "seed",
    "violation_rate", "max_coalition_bits", "FAR_normal", "UR_normal",
    "CR_complete", "mean_decision_seconds",
)
GROUP_COLUMNS = ("arm", "param", "K", "c", "seed", "group_id", "g", "w", "violated", "L_star_bits")


@dataclass(frozen=True)
class Spec:
    arm: str
    param: float | None
    K: int
    c: float
    seed: int


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
                    yield Spec(arm, param, K, c, seed)


def make_arm(spec: Spec, secrets, stream: Stream):
    if spec.arm == "no_defense":
        return NoDefense()
    if spec.arm == "per_recipient_bits":
        return PerRecipientBits(secrets, spec.param)
    if spec.arm == "global_bits":
        return GlobalBits(secrets, spec.param * no_defense_spend(secrets, stream.requests))
    if spec.arm == "pairwise_only":
        return GateArm(secrets, int(spec.param), max_witness=2)
    if spec.arm == "ours":
        return GateArm(secrets, int(spec.param))
    raise ValueError(spec.arm)


def run_spec(spec: Spec, secrets, stream: Stream) -> tuple[dict, list[dict]]:
    arm = make_arm(spec, secrets, stream)
    by_id = {secret.target_id: secret for secret in secrets}
    delivered: dict[str, set] = {}
    normal_total = normal_full = 0
    normal_utility = normal_best = 0.0
    complete_total = complete_refused = 0
    elapsed = 0.0
    for request in stream.requests:
        started = time.perf_counter()
        chosen = arm.select(request.recipient_id, request.candidates)
        elapsed += time.perf_counter() - started
        delivered.setdefault(request.recipient_id, set()).update(
            (unit.resource_id, unit.unit_id) for unit in chosen.units
        )
        if request.role == "normal":
            normal_total += 1
            normal_full += chosen.name == "full"
            normal_utility += chosen.utility
            normal_best += prefer(request.candidates).utility
        elif request.role == "complete":
            complete_total += 1
            complete_refused += chosen.name != "full"
    group_rows = []
    for group in stream.groups:
        view = set().union(*(delivered.get(member, set()) for member in group.members))
        secret = by_id[group.target_id]
        bits = secret.leakage_star(view)
        violated = any(
            s.leakage_star(view) > s.tau + 1e-9
            for s in {by_id[unit[0]] for unit in view}
        )
        group_rows.append(
            {
                **_key(spec),
                "group_id": group.group_id,
                "g": len(group.members),
                "w": len(group.witness),
                "violated": int(violated),
                "L_star_bits": bits,
            }
        )
    row = {
        **_key(spec),
        "violation_rate": sum(r["violated"] for r in group_rows) / len(group_rows),
        "max_coalition_bits": max(r["L_star_bits"] for r in group_rows),
        "FAR_normal": 1 - normal_full / normal_total if normal_total else 0.0,
        "UR_normal": normal_utility / normal_best if normal_best else 0.0,
        "CR_complete": complete_refused / complete_total if complete_total else 0.0,
        "mean_decision_seconds": elapsed / len(stream.requests),
    }
    return row, group_rows


def run_grid(seeds=SEEDS) -> tuple[list[dict], list[dict]]:
    rows, groups = [], []
    cache: dict[int, tuple] = {}
    streams: dict[tuple, Stream] = {}
    for spec in iter_specs(seeds):
        if spec.K not in cache:
            cache[spec.K] = load_secrets(spec.K)
        secrets = cache[spec.K]
        key = (spec.K, spec.c, spec.seed)
        if key not in streams:
            streams[key] = generate(
                secrets,
                student_count=STUDENT_COUNT,
                coalition_sizes=COALITION_SIZES,
                seed=spec.seed,
                normal_requests=NORMAL_REQUESTS,
                complete_ratio=spec.c,
            )
        row, group_rows = run_spec(spec, secrets, streams[key])
        rows.append(row)
        groups.extend(group_rows)
    return rows, groups


def write_csv(path: Path, columns, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: _cell(row[col]) for col in columns})


def environment() -> dict:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True
    ).stdout.strip()
    return {
        "python": platform.python_version(),
        "git_commit": commit,
        "data_manifest_sha256": manifest_sha(),
    }


def _key(spec: Spec) -> dict:
    return {"arm": spec.arm, "param": spec.param, "K": spec.K, "c": spec.c, "seed": spec.seed}


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the pre-registered E5 grid.")
    parser.add_argument("--count", action="store_true", help="print the number of runs")
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
    write_csv(args.out / "raw.csv", RAW_COLUMNS, rows)
    write_csv(args.out / "groups.csv", GROUP_COLUMNS, groups)
    (args.out / "environment.json").write_text(json.dumps(environment(), indent=2) + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
