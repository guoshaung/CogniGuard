"""Per-group replay for the E3a exploratory notes.

Reads results/raw.csv. Does not write into results/ and does not change the
harness or the pre-registered grid. A group record is one capd_rel coalition
inside one (registry, c, scenario, e, seed, k, m). Success means that
coalition's CRR is 1.0. Span is the number of distinct true groups among its
members. A member is misregistered when the registered group differs from the
true group.

Run from the repository root:

    PYTHONPATH=. COGNIGUARD_ASSET_PACK=../C2RAG_5_Pedagogical_Assets_Pilot_v1 \\
        python experiments/capd_e3a_20261123/exploratory/replay_groups.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

from cogniguard.governance.targets import TargetRegistry

from experiments.capd_e3a_20261123.arms import CapdRel
from experiments.capd_e3a_20261123.metrics import far_normal
from experiments.capd_e3a_20261123.population import (
    STUDENT_COUNT,
    assign_true_groups,
    generate_stream,
    place_coalitions,
    registered_groups,
)
from experiments.capd_e3a_20261123.run import NORMAL_REQUESTS, iter_specs
from experiments.capd_eval_20261123.metrics import Decision, crr, ur_normal
from experiments.capd_eval_20261123.registries import education_targets, synthetic_targets

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "results" / "raw.csv"
REGISTRIES = ("R-syn", "R-edu")
SCENARIOS = ("S-in", "S-x2", "S-xg")


def load_raw() -> list[dict[str, str]]:
    with RAW_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def replay(raw_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], int, int]:
    recorded = {
        (
            row["arm"],
            row["k"],
            row["m"],
            row["registry"],
            row["c"],
            row["scenario"],
            row["e"],
            row["seed"],
        ): row
        for row in raw_rows
    }
    catalogs = {"R-syn": synthetic_targets(), "R-edu": education_targets()}
    registries = {name: TargetRegistry(targets) for name, targets in catalogs.items()}
    true_groups = assign_true_groups(STUDENT_COUNT)
    placements = {
        scenario: place_coalitions(scenario, true_groups) for scenario in SCENARIOS
    }
    groups: list[dict[str, object]] = []
    mismatches = 0
    checked = 0
    for spec in iter_specs():
        if spec.arm != "capd_rel":
            continue
        raw = recorded[
            (
                spec.arm,
                str(spec.k),
                str(spec.m),
                spec.registry,
                f"{spec.complete_ratio:.1f}",
                spec.scenario,
                f"{spec.error_rate:.1f}",
                str(spec.seed),
            )
        ]
        targets = catalogs[spec.registry]
        registry = registries[spec.registry]
        registered = registered_groups(true_groups, spec.error_rate, spec.seed)
        requests = generate_stream(
            targets,
            true_groups=true_groups,
            scenario=spec.scenario,
            seed=spec.seed,
            complete_ratio=spec.complete_ratio,
            normal_requests=NORMAL_REQUESTS,
        )
        arm = CapdRel(
            registry,
            int(spec.k),
            int(spec.m),
            registered,
            price_lambda=0.0,
            price_decay=1.0,
        )
        decisions = []
        for request in requests:
            selected = arm.select(request.recipient_id, request.candidates)
            decisions.append(
                Decision(
                    request.recipient_id,
                    request.role,
                    request.group_id,
                    selected,
                    0.0,
                    max(candidate.utility for candidate in request.candidates),
                )
            )
        recorded_decisions = tuple(decisions)
        got_crr = f"{crr(registry, recorded_decisions):.6f}"
        got_far = f"{far_normal(recorded_decisions):.6f}"
        got_ur = f"{ur_normal(recorded_decisions):.6f}"
        if (
            got_crr != raw["CRR_S"]
            or got_far != raw["FAR_normal"]
            or got_ur != raw["UR_normal"]
        ):
            mismatches += 1
        placed = placements[spec.scenario]
        for index, members in enumerate(placed):
            group_id = f"coalition-{index}"
            subset = tuple(item for item in recorded_decisions if item.group_id == group_id)
            span = len({true_groups[member] for member in members})
            groups.append(
                {
                    "registry": spec.registry,
                    "c": spec.complete_ratio,
                    "scenario": spec.scenario,
                    "e": spec.error_rate,
                    "seed": spec.seed,
                    "k": spec.k,
                    "m": spec.m,
                    "group": group_id,
                    "size": len(members),
                    "span": span,
                    "success": crr(registry, subset) == 1.0,
                    "mismatched": any(
                        registered[member] != true_groups[member] for member in members
                    ),
                }
            )
        checked += 1
        if checked % 200 == 0:
            print(f"replayed {checked}", file=sys.stderr, flush=True)
    return groups, mismatches, checked


def inside(item: dict[str, object]) -> bool:
    return int(item["span"]) <= int(item["m"]) and int(item["size"]) <= int(item["k"])


def boundary_lines(groups: list[dict[str, object]]) -> list[str]:
    lines = [
        "| m | 登记表 | 场景 | e=0 记录数 | e=0 成功数 | e>0 成功数 | e>0 至少一名登记错误 | e>0 全员登记正确 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for m in (1, 2):
        total = [0, 0, 0, 0, 0]
        for registry in REGISTRIES:
            for scenario in SCENARIOS:
                chosen = [
                    item
                    for item in groups
                    if item["m"] == m
                    and item["registry"] == registry
                    and item["scenario"] == scenario
                    and inside(item)
                ]
                e0 = [item for item in chosen if item["e"] == 0.0]
                e0_success = sum(bool(item["success"]) for item in e0)
                epos = [item for item in chosen if float(item["e"]) > 0.0 and item["success"]]
                mismatched = sum(bool(item["mismatched"]) for item in epos)
                clean = sum(not item["mismatched"] for item in epos)
                counts = [len(e0), e0_success, len(epos), mismatched, clean]
                total = [left + right for left, right in zip(total, counts)]
                lines.append(
                    f"| {m} | {registry} | {scenario} | {counts[0]} | {counts[1]} | {counts[2]} | {counts[3]} | {counts[4]} |"
                )
        lines.append(
            f"| {m} | 合计 |  | {total[0]} | {total[1]} | {total[2]} | {total[3]} | {total[4]} |"
        )
    return lines


def _paired(raw_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    cells: dict[tuple[str, str, int, str], dict[int, dict[str, str]]] = defaultdict(dict)
    for row in raw_rows:
        if row["scenario"] != "S-in" or row["e"] != "0.0":
            continue
        if row["arm"] == "capd_rel" and row["m"] == "2":
            arm = "capd_rel"
        elif row["arm"] == "capd_any" and row["m"] == "":
            arm = "capd_any"
        else:
            continue
        cells[(row["registry"], row["c"], int(row["k"]), arm)][int(row["seed"])] = row
    reports = []
    for registry in REGISTRIES:
        for complete in ("0.0", "0.2"):
            for k in (2, 3, 4):
                rel = cells[(registry, complete, k, "capd_rel")]
                base = cells[(registry, complete, k, "capd_any")]
                seeds = list(range(10))
                if sorted(rel) != seeds or sorted(base) != seeds:
                    raise RuntimeError(f"missing seeds for {registry} c={complete} k={k}")
                rel_far = [float(rel[seed]["FAR_normal"]) for seed in seeds]
                any_far = [float(base[seed]["FAR_normal"]) for seed in seeds]
                rel_ur = [float(rel[seed]["UR_normal"]) for seed in seeds]
                any_ur = [float(base[seed]["UR_normal"]) for seed in seeds]
                far_diff = [left - right for left, right in zip(rel_far, any_far)]
                ur_diff = [left - right for left, right in zip(rel_ur, any_ur)]
                reports.append(
                    {
                        "registry": registry,
                        "c": complete,
                        "k": k,
                        "rel_far": rel_far,
                        "any_far": any_far,
                        "rel_ur": rel_ur,
                        "any_ur": any_ur,
                        "far_diff": far_diff,
                        "ur_diff": ur_diff,
                    }
                )
    return reports


def _fmt(values: list[float]) -> str:
    mean = sum(values) / len(values)
    return f"{mean:.6f} [{min(values):.6f}, {max(values):.6f}]"


def utility_lines(raw_rows: list[dict[str, str]]) -> list[str]:
    lines = [
        "| 登记表 | c | k | capd_rel FAR_normal | capd_any FAR_normal | FAR 差值 | capd_rel UR_normal | capd_any UR_normal | UR 差值 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in _paired(raw_rows):
        lines.append(
            "| {registry} | {c} | {k} | {rel_far} | {any_far} | {far_diff} | {rel_ur} | {any_ur} | {ur_diff} |".format(
                registry=item["registry"],
                c=item["c"],
                k=item["k"],
                rel_far=_fmt(item["rel_far"]),
                any_far=_fmt(item["any_far"]),
                far_diff=_fmt(item["far_diff"]),
                rel_ur=_fmt(item["rel_ur"]),
                any_ur=_fmt(item["any_ur"]),
                ur_diff=_fmt(item["ur_diff"]),
            )
        )
    return lines


def crr_lines(raw_rows: list[dict[str, str]]) -> list[str]:
    buckets: dict[tuple[str, str, int, str], list[float]] = defaultdict(list)
    for row in raw_rows:
        if row["arm"] != "capd_rel" or row["m"] != "2":
            continue
        buckets[(row["registry"], row["scenario"], int(row["k"]), row["e"])].append(
            float(row["CRR_S"])
        )
    lines = [
        "| 登记表 | 场景 | k | e | 行数 | CRR |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for registry in REGISTRIES:
        for scenario in SCENARIOS:
            for k in (2, 3, 4):
                for error in ("0.0", "0.1", "0.3"):
                    values = buckets[(registry, scenario, k, error)]
                    if len(values) != 20:
                        raise RuntimeError(
                            f"expected 20 rows for {registry} {scenario} k={k} e={error}, got {len(values)}"
                        )
                    mean = sum(values) / len(values)
                    lines.append(
                        f"| {registry} | {scenario} | {k} | {error} | {len(values)} | {mean:.6f} |"
                    )
    return lines


def main() -> None:
    raw_rows = load_raw()
    groups, mismatches, checked = replay(raw_rows)
    print(f"checked {checked} mismatches {mismatches} group_records {len(groups)}")
    if mismatches:
        raise SystemExit(1)
    print("\n".join(boundary_lines(groups)))
    print("\n".join(utility_lines(raw_rows)))
    print("\n".join(crr_lines(raw_rows)))


if __name__ == "__main__":
    main()
