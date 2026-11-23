"""Run the pre-registered E3a grid. Counting it does not run a configuration."""

from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from pathlib import Path

from cogniguard.governance.targets import TargetRegistry

from experiments.capd_e3a_20261123.arms import CapdRel
from experiments.capd_e3a_20261123.metrics import far_normal
from experiments.capd_e3a_20261123.population import (
    ERROR_RATES,
    SCENARIOS,
    STUDENT_COUNT,
    assign_true_groups,
    generate_stream,
    registered_groups,
)
from experiments.capd_eval_20261123.arms import Capd, NoDefense
from experiments.capd_eval_20261123.metrics import Decision, cr_complete, crr, ur_normal
from experiments.capd_eval_20261123.registries import education_targets, synthetic_targets

REGISTRIES = ("R-syn", "R-edu")
COMPLETE_RATIOS = (0.0, 0.2)
SEEDS = tuple(range(10))
CAPD_K = (2, 3, 4)
CAPD_M = (1, 2)
NORMAL_REQUESTS = 4

RAW_COLUMNS = (
    "arm",
    "k",
    "m",
    "registry",
    "c",
    "scenario",
    "e",
    "seed",
    "FAR_normal",
    "UR_normal",
    "CRR_S",
    "CR_complete",
)


@dataclass(frozen=True)
class Spec:
    arm: str
    registry: str
    complete_ratio: float
    scenario: str
    error_rate: float
    seed: int
    k: int | None = None
    m: int | None = None


def iter_specs():
    """Section 5 grid. Counting these does not run a configuration."""
    for registry in REGISTRIES:
        for complete_ratio in COMPLETE_RATIOS:
            for scenario in SCENARIOS:
                for error_rate in ERROR_RATES:
                    for seed in SEEDS:
                        for arm, k, m in _arm_parameters():
                            yield Spec(
                                arm,
                                registry,
                                complete_ratio,
                                scenario,
                                error_rate,
                                seed,
                                k,
                                m,
                            )


def _arm_parameters():
    yield ("no_defense", None, None)
    for k in CAPD_K:
        yield ("capd_any", k, None)
    for k in CAPD_K:
        for m in CAPD_M:
            yield ("capd_rel", k, m)


def run_grid(out_dir: Path) -> Path:
    """Run every pre-registered configuration once."""
    rows = [_run_spec(spec) for spec in iter_specs()]
    return write_results(rows, out_dir)


def write_results(rows: list[dict], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "raw.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {column: _cell(column, row[column]) for column in RAW_COLUMNS}
            )
    return path


def _run_spec(spec: Spec) -> dict:
    targets = synthetic_targets() if spec.registry == "R-syn" else education_targets()
    registry = TargetRegistry(targets)
    true_groups = assign_true_groups(STUDENT_COUNT)
    registered = registered_groups(true_groups, spec.error_rate, spec.seed)
    requests = generate_stream(
        targets,
        true_groups=true_groups,
        scenario=spec.scenario,
        seed=spec.seed,
        complete_ratio=spec.complete_ratio,
        normal_requests=NORMAL_REQUESTS,
    )
    decisions: list[Decision] = []
    arm = _arm_for(spec, registry, registered)
    for request in requests:
        started = time.perf_counter()
        selected = arm.select(request.recipient_id, request.candidates)
        elapsed = time.perf_counter() - started
        decisions.append(
            Decision(
                request.recipient_id,
                request.role,
                request.group_id,
                selected,
                elapsed,
                max(candidate.utility for candidate in request.candidates),
            )
        )
    recorded = tuple(decisions)
    return {
        "arm": spec.arm,
        "k": spec.k,
        "m": spec.m,
        "registry": spec.registry,
        "c": spec.complete_ratio,
        "scenario": spec.scenario,
        "e": spec.error_rate,
        "seed": spec.seed,
        "FAR_normal": far_normal(recorded),
        "UR_normal": ur_normal(recorded),
        "CRR_S": crr(registry, recorded),
        "CR_complete": cr_complete(recorded),
    }


def _arm_for(spec: Spec, registry: TargetRegistry, registered: dict[str, str]):
    if spec.arm == "no_defense":
        return NoDefense()
    if spec.arm == "capd_any":
        return Capd(registry, int(spec.k), price_lambda=0.0, price_decay=1.0)
    if spec.arm == "capd_rel":
        return CapdRel(
            registry,
            int(spec.k),
            int(spec.m),
            registered,
            price_lambda=0.0,
            price_decay=1.0,
        )
    raise ValueError(spec.arm)


def _cell(column: str, value) -> str:
    if value is None:
        return ""
    if column in {"FAR_normal", "UR_normal", "CRR_S", "CR_complete"}:
        return f"{float(value):.6f}"
    if column in {"c", "e"}:
        return f"{float(value):.1f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the pre-registered E3a grid.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "results",
    )
    args = parser.parse_args()
    if args.dry_run:
        print(len(tuple(iter_specs())))
        return
    print(run_grid(args.out))


if __name__ == "__main__":
    main()
