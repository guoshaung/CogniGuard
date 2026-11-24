"""Audit the 13 wrong E7 targets and the 33 already-held E7 secrets.

The generator sees the owner line, ``data_distribution``, visible identifier
fields, and Alice's tables as the initial holding. It does not see attack
plans. ``posthoc_attack_tables`` repeats the frozen failure scorer and is
used only to describe those 13 scenes after the plans have been built.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from experiments.protocol_b_targets_20261125.generate_targets import (
    CLASS_EXTERNAL,
    CLASS_INITIAL,
    CLASS_SYSTEM,
    SOURCE_SCHEMA,
    declared_names,
    from_scenario_record,
    generate_protection_plan,
    load_tables,
    units_owned_by,
)

RAW = Path("/Users/MBP/Exp/CogniGuard/cogniguard_raw/sumleaks_repo/data")
WITNESS = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/sumleaks/witness_sets.jsonl")
FAILURES = Path(
    "/Users/MBP/Exp/CogniGuard/cmp2/experiments/cogniguard_comparison_phase2"
    "/results/protocol_b/protocol_b_failure_cases.json"
)
PILOTS = {5, 40, 100}
WRONG = "witness differs from the attacked inference (E7 secret is not the attack target)"


def _scene_id(path: Path) -> int:
    return int(path.name.split("_")[1])


def _e7_witnesses(path: Path) -> dict[str, list[list[str]]]:
    found = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        found[row["target_id"]] = row["sets"]
    return found


def _wrong_ids(path: Path) -> list[int]:
    rows = json.loads(path.read_text())
    return sorted({
        int(row["scenario"])
        for row in rows
        if row.get("cause") == WRONG and row.get("kind") == "leak"
    })


def posthoc_attack_tables(record: dict) -> set[str]:
    """Tables named by the frozen scorer. Not an input to target generation."""
    text = json.dumps(record.get("run_2_sensitive_plan")) + json.dumps(
        record.get("run_2_sensitive")
    )
    tables = {
        f"{agent}.{name}"
        for agent, spec in record["data_distribution"].items()
        for name in (spec.get("table") or {})
    }
    return {unit for unit in tables if unit.split(".", 1)[1] in text}


def _names(units) -> set[str]:
    return {unit.split(".", 1)[1] for unit in units}


def _jaccard(left: set[str], right: set[str]) -> float | None:
    if not left and not right:
        return None
    return len(left & right) / len(left | right)


def _witness_matches(sets, used: set[str]) -> bool:
    return any(set(group) <= used for group in sets)


def _check_plan(plan, tables) -> list[str]:
    violations = []
    schema = {table["unit_id"] for table in tables}
    declared = set(plan.declared_names)
    seen = set()
    for target in plan.targets:
        if target.target_id in seen:
            violations.append(f"duplicate {target.target_id}")
        seen.add(target.target_id)
        if target.source == SOURCE_SCHEMA:
            name = target.table_unit.split(".", 1)[1]
            if name not in declared:
                violations.append(f"{target.target_id} outside the declaration")
            if target.table_unit not in schema:
                violations.append(f"{target.target_id} missing table")
        sets = [witness.unit_ids for witness in target.witnesses]
        if not sets or any(len(units) < 2 for units in sets):
            violations.append(f"{target.target_id} degenerate witness")
        if any(left < right for left in sets for right in sets):
            violations.append(f"{target.target_id} superset witness")
        initial = set(plan.initial_units)
        external = set(plan.external_units)
        for witness in target.witnesses:
            if not witness.unit_ids <= schema:
                violations.append(f"{target.target_id} unknown unit")
            if witness.unit_ids <= initial and witness.leak_class != CLASS_INITIAL:
                violations.append(f"{target.target_id} mislabeled initial")
            elif (
                witness.unit_ids <= initial | external
                and not witness.unit_ids <= initial
                and witness.leak_class != CLASS_EXTERNAL
            ):
                violations.append(f"{target.target_id} mislabeled external")
            elif (
                not witness.unit_ids <= initial | external
                and witness.leak_class != CLASS_SYSTEM
            ):
                violations.append(f"{target.target_id} mislabeled system")
    classes = {target.leak_class for target in plan.targets}
    if plan.external_units == () and CLASS_EXTERNAL in classes:
        violations.append("external class with an empty external holding")
    return violations


def _family_key(target) -> tuple:
    return tuple(sorted(tuple(sorted(units)) for units in target.witness_unit_sets()))


def audit(
    raw: Path = RAW,
    witness_path: Path = WITNESS,
    failure_path: Path = FAILURES,
) -> dict:
    files = sorted(raw.glob("experiment_*_def_adv_both.json"))
    if not files:
        raise ValueError(f"no Sum Leaks files in {raw}")
    e7 = _e7_witnesses(witness_path)
    wrong_ids = set(_wrong_ids(failure_path))
    totals = Counter()
    sizes = Counter()
    violations = []
    jaccard_e7 = []
    jaccard_ours = []
    historical = []
    wrong = []
    per_scene = []
    mask_total = 0
    probe_total = 0
    for path in files:
        record = json.loads(path.read_bytes())
        scene = _scene_id(path)
        tables = load_tables(record["data_distribution"])
        plan = from_scenario_record(
            record,
            initial_units=units_owned_by(tables, "Alice"),
            scene_id=str(scene),
        )
        # Independence: building from the two allowed fields matches the record call.
        again = generate_protection_plan(
            record["data_distribution"],
            record.get("defense", ""),
            initial_units=plan.initial_units,
            scene_id=str(scene),
        )
        if [item.target_id for item in again.targets] != [
            item.target_id for item in plan.targets
        ]:
            violations.append(f"{scene} record wrapper changed the targets")
        violations.extend(f"{scene}: {item}" for item in _check_plan(plan, tables))
        totals[f"parse_{plan.parse_status}"] += 1
        totals["scenes"] += 1
        totals["schema_targets"] += plan.complexity["schema_targets"]
        totals["policy_targets"] += plan.complexity["policy_targets"]
        totals["targets"] += plan.complexity["targets"]
        totals["system_new"] += plan.complexity["system_new"]
        totals["initial_held"] += plan.complexity["initial_held"]
        totals["external_propagation"] += plan.complexity["external_propagation"]
        totals["single_table_excluded"] += plan.single_table_excluded
        totals["undetermined_excluded"] += plan.undetermined_excluded
        totals["families"] += plan.complexity["distinct_witness_families"]
        if plan.complexity["schema_targets"] >= 2:
            totals["scenes_with_two_schema_targets"] += 1
        if plan.complexity["system_new"]:
            totals["scenes_with_system_new"] += 1
        if not plan.targets:
            totals["scenes_without_target"] += 1
        mask_total += plan.complexity["mask_evaluations"]
        probe_total += plan.complexity["full_join_probes"]
        for target in plan.targets:
            for witness in target.witnesses:
                sizes[len(witness.units)] += 1
                names = _names(witness.unit_ids)
                score = _jaccard(names, set(plan.declared_names))
                if score is not None:
                    jaccard_ours.append(score)
        e7_sets = e7.get(f"sl.{scene}")
        e7_units = [unit for group in (e7_sets or []) for unit in group]
        # One finished witness is enough: the secret is already known.
        e7_initial = bool(e7_sets) and any(
            all(unit.startswith("Alice.") for unit in group) for group in e7_sets
        )
        e7_all_initial = bool(e7_sets) and all(
            unit.startswith("Alice.") for unit in e7_units
        )
        if e7_sets:
            totals["e7_scenes"] += 1
            score = _jaccard(_names(e7_units), set(plan.declared_names))
            if score is not None:
                jaccard_e7.append(score)
            ours = [set(group) for target in plan.targets for group in target.witness_unit_sets()]
            if any(set(group) in ours for group in e7_sets):
                totals["e7_witness_reproduced"] += 1
        if e7_all_initial:
            totals["e7_all_witnesses_initial"] += 1
        if e7_initial:
            totals["e7_initial_held"] += 1
            if scene not in PILOTS:
                totals["e7_initial_held_heldout"] += 1
        heldout = scene not in PILOTS
        if heldout:
            totals["heldout_scenes"] += 1
            if plan.complexity["system_new"]:
                totals["heldout_scenes_with_system_new"] += 1
        summary = {
            "scene": scene,
            "parse": plan.parse_status,
            "declared": list(plan.declared_names),
            "schema_targets": plan.complexity["schema_targets"],
            "policy_targets": plan.complexity["policy_targets"],
            "system_new": plan.complexity["system_new"],
            "initial_held": plan.complexity["initial_held"],
            "families": plan.complexity["distinct_witness_families"],
            "e7_initial_held": e7_initial,
            "e7_all_witnesses_initial": e7_all_initial,
            "heldout": heldout,
        }
        per_scene.append(summary)
        if e7_initial:
            historical.append({
                **summary,
                "e7_sets": e7_sets,
                "system_new_families": [
                    [sorted(units) for units in target.witness_unit_sets()]
                    for target in plan.targets
                    if target.leak_class == CLASS_SYSTEM
                ],
            })
            if plan.complexity["system_new"]:
                totals["historical_scenes_with_system_new"] += 1
        if scene in wrong_ids:
            used = posthoc_attack_tables(record)
            system_sets = [
                set(units)
                for target in plan.targets
                if target.leak_class == CLASS_SYSTEM
                for units in target.witness_unit_sets()
            ]
            all_sets = [
                set(units)
                for target in plan.targets
                for units in target.witness_unit_sets()
            ]
            wrong.append({
                **summary,
                "e7_sets": e7_sets,
                "e7_matches_attack_tables": _witness_matches(e7_sets or [], used),
                "system_new_matches_attack_tables": _witness_matches(system_sets, used),
                "any_witness_matches_attack_tables": _witness_matches(all_sets, used),
                "schema_columns": sorted({
                    target.column for target in plan.targets if target.source == SOURCE_SCHEMA
                }),
                "system_new_witnesses": [sorted(units) for units in system_sets],
            })
            if _witness_matches(system_sets, used):
                totals["wrong_scenes_covered_by_system_new"] += 1
            if _witness_matches(all_sets, used):
                totals["wrong_scenes_covered_by_any"] += 1
    if len(wrong) != len(wrong_ids):
        violations.append(f"wrong scenes found {len(wrong)} of {len(wrong_ids)}")
    mean = lambda values: (sum(values) / len(values)) if values else None
    return {
        "scenes": totals["scenes"],
        "heldout_scenes": totals["heldout_scenes"],
        "counts": dict(totals),
        "witness_size_histogram": {str(key): sizes[key] for key in sorted(sizes)},
        "mask_evaluations": mask_total,
        "full_join_probes": probe_total,
        "e7_jaccard_mean": mean(jaccard_e7),
        "our_witness_jaccard_mean": mean(jaccard_ours),
        "e7_initial_held": totals["e7_initial_held"],
        "historical_scenes_with_system_new": totals["historical_scenes_with_system_new"],
        "wrong_scene_ids": sorted(wrong_ids),
        "wrong_scenes_covered_by_system_new": totals["wrong_scenes_covered_by_system_new"],
        "wrong_scenes_covered_by_any": totals["wrong_scenes_covered_by_any"],
        "invariant_violations": violations,
        "historical": historical,
        "wrong": wrong,
        "scenes_without_target": [
            row["scene"] for row in per_scene if row["schema_targets"] + row["policy_targets"] == 0
        ],
        "per_scene": per_scene,
    }


def main():
    report = audit()
    dest = Path(__file__).resolve().parent / "results"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "audit.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    brief = {
        key: report[key]
        for key in (
            "scenes", "heldout_scenes", "counts", "witness_size_histogram",
            "mask_evaluations", "full_join_probes", "e7_jaccard_mean",
            "our_witness_jaccard_mean", "e7_initial_held",
            "historical_scenes_with_system_new", "wrong_scene_ids",
            "wrong_scenes_covered_by_system_new", "wrong_scenes_covered_by_any",
            "invariant_violations", "scenes_without_target",
        )
    }
    print(json.dumps(brief, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
