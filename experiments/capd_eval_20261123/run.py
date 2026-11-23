"""Run the four defenses on one seeded stream and write CSV and Markdown tables."""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

from cogniguard.governance.targets import ProtectedTarget, TargetRegistry

from experiments.capd_eval_20261123.arms import Capd, GlobalBudget, NoDefense, PerRecipientBudget
from experiments.capd_eval_20261123.metrics import (
    Decision,
    delivered_utility,
    false_refusal_rate,
    mean_decision_seconds,
    reconstruction_success_rate,
    utility_retention,
)
from experiments.capd_eval_20261123.workload import Request, generate_requests

COLUMNS = (
    "arm",
    "reconstruction_success_rate",
    "false_refusal_rate",
    "utility_retention",
    "mean_decision_seconds",
)


def smoke_registry() -> TargetRegistry:
    targets = []
    for index in range(5):
        witness = frozenset(("course", f"t{index}-u{unit}") for unit in range(3))
        targets.append(ProtectedTarget(f"target-{index}", "owner", "org", (witness,)))
    return TargetRegistry(targets)


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
            )
        )
    recorded = tuple(decisions)
    undefended = sum(max(candidate.utility for candidate in request.candidates) for request in requests)
    return {
        "arm": name,
        "reconstruction_success_rate": reconstruction_success_rate(registry, recorded),
        "false_refusal_rate": false_refusal_rate(recorded),
        "utility_retention": utility_retention(delivered_utility(recorded), undefended),
        "mean_decision_seconds": mean_decision_seconds(recorded),
    }


def run_comparison(
    registry: TargetRegistry,
    *,
    student_count: int,
    coalition_sizes: tuple[int, ...],
    seed: int,
    budget: float,
    coalition_k: int,
    normal_requests: int,
    out_dir: Path,
) -> tuple[Path, Path]:
    requests = generate_requests(
        registry,
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
        smoke_registry(),
        student_count=20,
        coalition_sizes=(3, 3),
        seed=20261123,
        budget=2.0,
        coalition_k=2,
        normal_requests=2,
        out_dir=out_dir,
    )


def _cell(value) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the CA-PD comparison tables.")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    csv_path, md_path = smoke(args.out)
    print(csv_path)
    print(md_path)


if __name__ == "__main__":
    main()
