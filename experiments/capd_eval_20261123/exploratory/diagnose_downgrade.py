"""Read-only classification of E2 capd downgrades.

Replays the recorded capd rows. Does not write into results/ and does not
change the harness. A downgrade is an ordinary-learner request whose selected
candidate is summary rather than full.

Before each selection, check_release is called on the full candidate and the
knowledge the gate would see. Unsafe means the release is charged to a
coalition of size at most k. Safe but not selected means the lambda price
outranked the full answer. The named partners are holders already in the
disclosure log. This replay does not observe whether those students cooperated.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from cogniguard.governance.reconstruction import check_release
from cogniguard.governance.targets import TargetRegistry

from experiments.capd_eval_20261123.metrics import Decision, crr
from experiments.capd_eval_20261123.registries import education_targets, synthetic_targets
from experiments.capd_eval_20261123.run import (
    COALITION_SIZES,
    NORMAL_REQUESTS,
    STUDENT_COUNT,
    _arm_for,
    iter_specs,
)
from experiments.capd_eval_20261123.workload import generate_requests

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "results" / "raw.csv"
SUMMARY_PATH = Path(__file__).resolve().parent / "downgrade_summary.csv"

SUMMARY_COLUMNS = (
    "registry",
    "c",
    "k",
    "price_lambda",
    "normal_requests",
    "full",
    "summary",
    "refuse",
    "summary_assumed_coalition",
    "summary_price",
    "assumed_with_other_student",
    "helper_normal",
    "helper_complete",
    "helper_coalition",
)


def protected_unit_count(targets) -> int:
    return len(
        {
            unit
            for target in targets
            for witness in target.witness_sets
            for unit in witness
        }
    )


def _affected_units(registry: TargetRegistry, release: frozenset) -> set[tuple[str, str]]:
    units: set[tuple[str, str]] = set()
    seen: set[str] = set()
    for unit in release:
        for target in registry.targets_for_unit(unit):
            if target.target_id in seen:
                continue
            seen.add(target.target_id)
            for witness in target.witness_sets:
                units.update(witness)
    return units


def _replay(spec, targets, raw_crr: str) -> dict[str, int]:
    registry = TargetRegistry(targets)
    requests = generate_requests(
        targets,
        student_count=STUDENT_COUNT,
        coalition_sizes=COALITION_SIZES,
        seed=spec.seed,
        normal_requests=NORMAL_REQUESTS,
        complete_ratio=spec.complete_ratio,
    )
    roles = {}
    for request in requests:
        roles.setdefault(request.recipient_id, request.role)
    arm = _arm_for(spec, registry)
    counts: dict[str, int] = defaultdict(int)
    decisions = []
    for request in requests:
        full = next(candidate for candidate in request.candidates if candidate.name == "full")
        release = frozenset((unit.resource_id, unit.unit_id) for unit in full.units)
        knowledge = arm.store.holders_of(_affected_units(registry, release))
        verdict = check_release(
            registry,
            request.recipient_id,
            release,
            knowledge,
            int(spec.k),
        )
        selected = arm.select(request.recipient_id, request.candidates)
        decisions.append((request, selected))
        if request.role != "normal":
            continue
        counts["normal_requests"] += 1
        counts[selected.name] += 1
        if selected.name != "summary":
            continue
        if verdict.safe:
            counts["summary_price"] += 1
            continue
        counts["summary_assumed_coalition"] += 1
        others = {
            member
            for violation in verdict.violations
            for member in violation.coalition
            if member != request.recipient_id
        }
        if others:
            counts["assumed_with_other_student"] += 1
        for member in others:
            role = roles.get(member, "other")
            counts[f"helper_{role}"] += 1
    recorded = tuple(
        Decision(request.recipient_id, request.role, request.group_id, selected, 0.0)
        for request, selected in decisions
    )
    got = f"{crr(registry, recorded):.6f}"
    if got != raw_crr:
        raise SystemExit(f"CRR mismatch {spec} {got} != {raw_crr}")
    return counts


def main() -> None:
    recorded = {}
    with RAW_PATH.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["arm"] != "capd":
                continue
            recorded[
                (row["registry"], row["c"], row["seed"], row["k"], row["price_lambda"])
            ] = row["CRR"]
    catalogs = {"R-syn": synthetic_targets(), "R-edu": education_targets()}
    print(f"R-edu-units {protected_unit_count(catalogs['R-edu'])}")
    print(f"R-syn-units {protected_unit_count(catalogs['R-syn'])}")
    totals: dict[str, int] = defaultdict(int)
    grouped: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    matched = 0
    for spec in iter_specs():
        if spec.arm != "capd":
            continue
        key = (
            spec.registry,
            f"{spec.complete_ratio:.1f}",
            str(spec.seed),
            str(spec.k),
            str(spec.price_lambda),
        )
        counts = _replay(spec, catalogs[spec.registry], recorded[key])
        matched += 1
        bucket = (spec.registry, f"{spec.complete_ratio:.1f}", spec.k, spec.price_lambda)
        for name, value in counts.items():
            grouped[bucket][name] += value
            totals[name] += value
    print(f"capd-rows-matched {matched}")
    print("totals " + " ".join(f"{name}={totals[name]}" for name in sorted(totals)))
    rows = []
    for registry, complete_ratio, k, price_lambda in sorted(
        grouped, key=lambda item: (item[0], item[1], item[2], item[3])
    ):
        counts = grouped[(registry, complete_ratio, k, price_lambda)]
        rows.append(
            {
                "registry": registry,
                "c": complete_ratio,
                "k": k,
                "price_lambda": price_lambda,
                "normal_requests": counts["normal_requests"],
                "full": counts["full"],
                "summary": counts["summary"],
                "refuse": counts["refuse"],
                "summary_assumed_coalition": counts["summary_assumed_coalition"],
                "summary_price": counts["summary_price"],
                "assumed_with_other_student": counts["assumed_with_other_student"],
                "helper_normal": counts["helper_normal"],
                "helper_complete": counts["helper_complete"],
                "helper_coalition": counts["helper_coalition"],
            }
        )
    with SUMMARY_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(SUMMARY_PATH)


if __name__ == "__main__":
    main()
