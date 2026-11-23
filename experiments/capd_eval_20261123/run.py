"""Run the pre-registered E2 grid, and the small smoke comparison."""

from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from pathlib import Path

from cogniguard.governance.targets import ProtectedTarget, TargetRegistry

from experiments.capd_eval_20261123.arms import Capd, GlobalBudget, NoDefense, PerRecipientBudget
from experiments.capd_eval_20261123.metrics import (
    Decision,
    cr_complete,
    crr,
    delivered_utility,
    frr,
    mean_decision_seconds,
    ur_normal,
    utility_retention,
)
from experiments.capd_eval_20261123.registries import education_targets, synthetic_targets
from experiments.capd_eval_20261123.workload import Request, generate_requests

STUDENT_COUNT = 60
COALITION_SIZES = (2, 2, 3, 3, 4, 4)
NORMAL_REQUESTS = 4
REGISTRIES = ("R-syn", "R-edu")
COMPLETE_RATIOS = (0.0, 0.2)
SEEDS = tuple(range(10))
PER_RECIPIENT_BUDGETS = (1, 2, 3, 4)
GLOBAL_BUDGETS = (10, 20, 40, 80)
CAPD_K = (1, 2, 3, 4)
CAPD_LAMBDA = (0, 1)
CAPD_DECAY = 1

RAW_COLUMNS = (
    "arm",
    "registry",
    "c",
    "seed",
    "budget",
    "k",
    "price_lambda",
    "price_decay",
    "CRR",
    "UR_normal",
    "FRR",
    "CR_complete",
    "mean_decision_seconds",
)
PARETO_COLUMNS = (
    "arm",
    "registry",
    "c",
    "budget",
    "k",
    "price_lambda",
    "UR_normal",
    "CRR",
)

COLUMNS = (
    "arm",
    "reconstruction_success_rate",
    "false_refusal_rate",
    "utility_retention",
    "mean_decision_seconds",
)


@dataclass(frozen=True)
class Spec:
    arm: str
    registry: str
    complete_ratio: float
    seed: int
    budget: int | None = None
    k: int | None = None
    price_lambda: int | None = None
    price_decay: int | None = None


def iter_specs():
    """Section 4 grid. Counting these does not run a configuration."""
    for registry in REGISTRIES:
        for complete_ratio in COMPLETE_RATIOS:
            for seed in SEEDS:
                for arm, budget, k, price_lambda in _arm_parameters():
                    yield Spec(
                        arm,
                        registry,
                        complete_ratio,
                        seed,
                        budget,
                        k,
                        price_lambda,
                        CAPD_DECAY if arm == "capd" else None,
                    )


def _arm_parameters():
    yield ("no_defense", None, None, None)
    for budget in PER_RECIPIENT_BUDGETS:
        yield ("per_recipient_budget", budget, None, None)
    for budget in GLOBAL_BUDGETS:
        yield ("global_budget", budget, None, None)
    for k in CAPD_K:
        for price_lambda in CAPD_LAMBDA:
            yield ("capd", None, k, price_lambda)


def smoke_targets() -> tuple[ProtectedTarget, ...]:
    targets = []
    for index in range(5):
        witness = frozenset(("course", f"t{index}-u{unit}") for unit in range(3))
        targets.append(ProtectedTarget(f"target-{index}", "owner", "org", (witness,)))
    return tuple(targets)


def run_arm(name: str, arm, requests: tuple[Request, ...], registry: TargetRegistry) -> dict[str, float | str]:
    decisions: list[Decision] = []
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
    undefended = sum(decision.undefended_utility for decision in recorded)
    return {
        "arm": name,
        "reconstruction_success_rate": crr(registry, recorded),
        "false_refusal_rate": frr(recorded),
        "utility_retention": utility_retention(delivered_utility(recorded), undefended),
        "mean_decision_seconds": mean_decision_seconds(recorded),
        "CRR": crr(registry, recorded),
        "UR_normal": ur_normal(recorded),
        "FRR": frr(recorded),
        "CR_complete": cr_complete(recorded),
    }


def run_comparison(
    targets: tuple[ProtectedTarget, ...],
    *,
    student_count: int,
    coalition_sizes: tuple[int, ...],
    seed: int,
    budget: float,
    coalition_k: int,
    normal_requests: int,
    out_dir: Path,
) -> tuple[Path, Path]:
    registry = TargetRegistry(targets)
    requests = generate_requests(
        targets,
        student_count=student_count,
        coalition_sizes=coalition_sizes,
        seed=seed,
        normal_requests=normal_requests,
    )
    arms = (
        ("no_defense", NoDefense()),
        ("per_recipient_budget", PerRecipientBudget(budget)),
        ("global_budget", GlobalBudget(budget)),
        ("capd", Capd(registry, coalition_k)),
    )
    rows = [run_arm(name, arm, requests, registry) for name, arm in arms]
    return write_tables(rows, out_dir)


def write_tables(rows: list[dict], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "capd_eval.csv"
    md_path = out_dir / "capd_eval.md"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _cell(row[column]) for column in COLUMNS})
    header = "| " + " | ".join(COLUMNS) + " |"
    rule = "| " + " | ".join("---" for _ in COLUMNS) + " |"
    body = [
        "| " + " | ".join(_cell(row[column]) for column in COLUMNS) + " |"
        for row in rows
    ]
    md_path.write_text("\n".join([header, rule, *body]) + "\n", encoding="utf-8")
    return csv_path, md_path


def smoke(out_dir: Path) -> tuple[Path, Path]:
    """Five targets, twenty students, two coalition groups."""
    return run_comparison(
        smoke_targets(),
        student_count=20,
        coalition_sizes=(3, 3),
        seed=20261123,
        budget=2.0,
        coalition_k=2,
        normal_requests=2,
        out_dir=out_dir,
    )


def run_grid(out_dir: Path) -> tuple[Path, Path]:
    """Run every pre-registered configuration once."""
    rows = [_run_spec(spec) for spec in iter_specs()]
    return write_results(rows, out_dir)


def write_results(rows: list[dict], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "raw.csv"
    pareto_path = out_dir / "pareto.csv"
    _write_csv(raw_path, RAW_COLUMNS, rows)
    _write_csv(pareto_path, PARETO_COLUMNS, pareto_rows(rows))
    return raw_path, pareto_path


def pareto_rows(rows: list[dict]) -> list[dict]:
    """One (UR_normal, CRR) point per arm and condition, averaged over seeds."""
    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for row in rows:
        key = (
            row["arm"],
            row["registry"],
            row["c"],
            row["budget"],
            row["k"],
            row["price_lambda"],
        )
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append(row)
    points = []
    for key in order:
        grouped = groups[key]
        points.append(
            {
                "arm": key[0],
                "registry": key[1],
                "c": key[2],
                "budget": key[3],
                "k": key[4],
                "price_lambda": key[5],
                "UR_normal": sum(float(item["UR_normal"]) for item in grouped) / len(grouped),
                "CRR": sum(float(item["CRR"]) for item in grouped) / len(grouped),
            }
        )
    return points


def _run_spec(spec: Spec) -> dict:
    targets = synthetic_targets() if spec.registry == "R-syn" else education_targets()
    registry = TargetRegistry(targets)
    requests = generate_requests(
        targets,
        student_count=STUDENT_COUNT,
        coalition_sizes=COALITION_SIZES,
        seed=spec.seed,
        normal_requests=NORMAL_REQUESTS,
        complete_ratio=spec.complete_ratio,
    )
    scored = run_arm(spec.arm, _arm_for(spec, registry), requests, registry)
    return {
        "arm": spec.arm,
        "registry": spec.registry,
        "c": spec.complete_ratio,
        "seed": spec.seed,
        "budget": spec.budget,
        "k": spec.k,
        "price_lambda": spec.price_lambda,
        "price_decay": spec.price_decay,
        "CRR": scored["CRR"],
        "UR_normal": scored["UR_normal"],
        "FRR": scored["FRR"],
        "CR_complete": scored["CR_complete"],
        "mean_decision_seconds": scored["mean_decision_seconds"],
    }


def _arm_for(spec: Spec, registry: TargetRegistry):
    if spec.arm == "no_defense":
        return NoDefense()
    if spec.arm == "per_recipient_budget":
        return PerRecipientBudget(float(spec.budget))
    if spec.arm == "global_budget":
        return GlobalBudget(float(spec.budget))
    if spec.arm == "capd":
        return Capd(
            registry,
            int(spec.k),
            price_lambda=float(spec.price_lambda),
            price_decay=float(spec.price_decay),
        )
    raise ValueError(spec.arm)


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _result_cell(column, row[column]) for column in columns})


def _result_cell(column: str, value) -> str:
    if value is None:
        return ""
    if column in {"CRR", "UR_normal", "FRR", "CR_complete", "mean_decision_seconds"}:
        return f"{float(value):.6f}"
    if column == "c":
        return f"{float(value):.1f}"
    return str(value)


def _cell(value) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the pre-registered E2 grid.")
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
    raw_path, pareto_path = run_grid(args.out)
    print(raw_path)
    print(pareto_path)


if __name__ == "__main__":
    main()
