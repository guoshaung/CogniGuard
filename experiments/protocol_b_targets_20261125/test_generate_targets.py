"""Non-degenerate checks for complete protection targets.

The scenes are synthetic. They do not use Sum Leaks attack plans, goals, or
final answers. A one-secret picker that keeps only the largest domain fails
the completeness check. A rule that reads an injected attack key fails the
independence check.
"""

import json
from pathlib import Path

import pytest

from cogniguard.governance.reconstruction import check_release
from cogniguard.governance.targets import TargetRegistry

from experiments.protocol_b_targets_20261125.generate_targets import (
    CLASS_EXTERNAL,
    CLASS_INITIAL,
    CLASS_SYSTEM,
    SOURCE_POLICY,
    SOURCE_SCHEMA,
    from_scenario_record,
    gate_targets,
    generate_protection_plan,
    knowledge_units,
)

HERE = Path(__file__).resolve().parent


def _rows(pairs, keys):
    return [dict(zip(keys, row, strict=True)) for row in pairs]


def _distribution():
    """Two declared secrets. The larger domain sits entirely on Alice.

    E7's picker keeps the size-4 note and drops the size-2 grade. The note
    witness is Alice's own tables. The grade witness still needs Bob.
    ``vault`` has the largest domain and is not in the owner line.
    """
    return {
        "Public": {"table": {
            "people": {
                "sensitivity": "public",
                "rows": _rows([("p1",)], ("person_id",)),
            },
        }},
        "Alice": {"table": {
            "enrollment": {
                "sensitivity": "sensitive",
                "rows": _rows([("p1", "c1")], ("person_id", "course_id")),
            },
            "notes": {
                "sensitivity": "sensitive",
                "rows": _rows(
                    [("c1", "n1"), ("c2", "n2"), ("c3", "n3"), ("c4", "n4")],
                    ("course_id", "note"),
                ),
            },
        }},
        "Bob": {"table": {
            "grades": {
                "sensitivity": "sensitive",
                "rows": _rows([("c1", "s1"), ("c2", "s2")], ("course_id", "score")),
            },
        }},
        "Eve": {"table": {
            "vault": {
                "sensitivity": "sensitive",
                "rows": _rows(
                    [("p1", f"v{i}") for i in range(8)], ("person_id", "loot")
                ),
            },
        }},
    }


DEFENSE = "The combination of enrollment, notes, and grades is sensitive."


def _plan(**kwargs):
    initial = kwargs.pop("initial_units", ("Alice.enrollment", "Alice.notes"))
    return generate_protection_plan(
        _distribution(), DEFENSE, initial_units=initial, scene_id="syn", **kwargs
    )


def _by_column(plan):
    return {target.column: target for target in plan.targets}


def test_both_declared_secrets_are_kept_and_the_larger_domain_is_not_the_only_one():
    plan = _plan()
    by_column = _by_column(plan)
    assert set(by_column) == {"note", "score"}
    assert by_column["note"].domain_size == 4
    assert by_column["score"].domain_size == 2
    assert plan.complexity["schema_targets"] == 2
    assert plan.complexity["policy_targets"] == 0
    assert all(target.source == SOURCE_SCHEMA for target in plan.targets)
    assert all("Eve.vault" not in target.table_unit for target in plan.targets)


def test_visible_anchor_is_not_a_unit_that_must_be_acquired():
    plan = _plan()
    score = _by_column(plan)["score"]
    assert score.witness_unit_sets() == (
        frozenset({"Alice.enrollment", "Bob.grades"}),
    )
    assert "Public.people" not in score.witnesses[0].unit_ids


def test_alice_owned_secret_is_initial_and_the_other_secret_is_system_new():
    plan = _plan()
    by_column = _by_column(plan)
    assert by_column["note"].leak_class == CLASS_INITIAL
    assert by_column["note"].witnesses[0].unit_ids <= set(plan.initial_units)
    assert by_column["score"].leak_class == CLASS_SYSTEM
    assert "Bob.grades" not in plan.initial_units


def test_external_holdings_are_not_labeled_as_a_system_disclosure():
    plan = _plan(
        initial_units=(),
        external_units=("Alice.enrollment", "Bob.grades"),
    )
    by_column = _by_column(plan)
    assert by_column["score"].leak_class == CLASS_EXTERNAL
    assert by_column["note"].leak_class == CLASS_SYSTEM
    assert {target.leak_class for target in plan.targets} >= {CLASS_EXTERNAL, CLASS_SYSTEM}


def test_two_join_paths_stay_minimal_and_the_superset_is_absent():
    distribution = _distribution()
    distribution["Cara"] = {"table": {
        "roster": {
            "sensitivity": "sensitive",
            "rows": _rows([("p1", "c1")], ("person_id", "course_id")),
        },
    }}
    defense = "The combination of enrollment, roster, and grades is sensitive."
    plan = generate_protection_plan(
        distribution, defense, scene_id="paths", initial_units=()
    )
    score = _by_column(plan)["score"]
    sets = set(score.witness_unit_sets())
    assert sets == {
        frozenset({"Alice.enrollment", "Bob.grades"}),
        frozenset({"Cara.roster", "Bob.grades"}),
    }
    assert not any(
        left < right for left in sets for right in sets
    )


def test_schema_bridge_outside_the_declaration_remains_in_the_witness():
    distribution = {
        "Public": {"table": {
            "people": {
                "sensitivity": "public",
                "rows": _rows([("p1", "d1"), ("p2", "d2")], ("person_id", "dept_id")),
            },
        }},
        "Bob": {"table": {
            "records": {
                "sensitivity": "sensitive",
                "rows": _rows([("d1", "flu"), ("d2", "cold")], ("dept_id", "finding")),
            },
        }},
    }
    defense = "The combination of records is sensitive."
    plan = generate_protection_plan(distribution, defense, scene_id="bridge")
    person = [target for target in plan.targets if target.anchor_column == "person_id"]
    assert person
    assert all(target.table_unit == "Bob.records" for target in person)
    assert all(target.column == "finding" for target in person)
    assert all(
        target.witness_unit_sets() == (frozenset({"Public.people", "Bob.records"}),)
        for target in person
    )
    assert all(target.leak_class == CLASS_SYSTEM for target in person)
    assert plan.single_table_excluded >= 1


def test_a_single_table_leak_is_counted_and_not_promoted():
    distribution = {
        "Public": {"table": {
            "people": {
                "sensitivity": "public",
                "rows": _rows([("p1",), ("p2",)], ("person_id",)),
            },
        }},
        "Alice": {"table": {
            "chart": {
                "sensitivity": "sensitive",
                "rows": _rows([("p1", "flu"), ("p2", "cold")], ("person_id", "finding")),
            },
            "other": {
                "sensitivity": "sensitive",
                "rows": _rows([("z1", "a"), ("z2", "b")], ("ticket_id", "tag")),
            },
        }},
    }
    defense = "The combination of chart and other is sensitive."
    plan = generate_protection_plan(distribution, defense, scene_id="single")
    assert plan.single_table_excluded >= 1
    assert [target.source for target in plan.targets] == [SOURCE_POLICY]
    assert plan.targets[0].witness_unit_sets() == (
        frozenset({"Alice.chart", "Alice.other"}),
    )
    assert all(target.column != "finding" for target in plan.targets)


def test_broad_joins_that_change_the_witness_are_not_registered():
    distribution = {
        "Public": {"table": {
            "people": {
                "sensitivity": "public",
                "rows": _rows([("p1",)], ("person_id",)),
            },
        }},
        "Alice": {"table": {
            "link_id": {
                "sensitivity": "sensitive",
                "rows": _rows([("p1", "i1")], ("person_id", "item_id")),
            },
            "link_tag": {
                "sensitivity": "sensitive",
                "rows": _rows([("p1", "t1")], ("person_id", "tag")),
            },
        }},
        "Bob": {"table": {
            "by_item": {
                "sensitivity": "sensitive",
                "rows": _rows(
                    [("i1", "t1", "s1"), ("i2", "t2", "s2")],
                    ("item_id", "tag", "score"),
                ),
            },
        }},
    }
    defense = "The combination of link_id, link_tag, and by_item is sensitive."
    plan = generate_protection_plan(distribution, defense, scene_id="wide")
    assert plan.undetermined_excluded >= 1
    assert all(target.column != "score" for target in plan.targets)


def test_attack_fields_do_not_change_the_plan_or_add_the_named_table():
    record = {
        "data_distribution": _distribution(),
        "defense": DEFENSE,
        "run_2_sensitive_plan": [{"table": "vault", "goal": "loot of p1"}],
        "run_2_sensitive": "Infer loot from vault.",
        "final_inference_result": "v0",
        "scene": "syn",
    }
    clean = generate_protection_plan(
        record["data_distribution"], record["defense"],
        initial_units=("Alice.enrollment", "Alice.notes"), scene_id="syn",
    )
    dirty = from_scenario_record(
        record, initial_units=("Alice.enrollment", "Alice.notes")
    )
    assert [target.target_id for target in dirty.targets] == [
        target.target_id for target in clean.targets
    ]
    assert all(target.table_unit != "Eve.vault" for target in dirty.targets)
    source = (HERE / "generate_targets.py").read_text()
    for banned in ("run_2_sensitive_plan", "final_inference_result", "run_2_sensitive"):
        assert banned not in source


def test_gate_blocks_the_system_new_witness_and_not_the_historical_one():
    plan = _plan()
    registry = TargetRegistry(gate_targets(plan))
    knowledge = {"Alice": knowledge_units(plan)}
    grades = frozenset({("sl", "Bob.grades")})
    notes = frozenset({("sl", "Alice.notes")})
    assert check_release(registry, "Alice", grades, knowledge, 1).safe is False
    assert check_release(registry, "Alice", notes, knowledge, 1).safe is True
    registered = {target.target_id for target in gate_targets(plan)}
    assert registered == {
        target.target_id for target in plan.targets if target.leak_class == CLASS_SYSTEM
    }
    assert not any(target.leak_class == CLASS_INITIAL and target.target_id in registered
                   for target in plan.targets)


def test_complexity_counts_every_determined_candidate():
    plan = _plan()
    tables = plan.complexity["tables"]
    assert tables == 5
    assert plan.complexity["targets"] == 2
    assert plan.complexity["mask_evaluations"] >= 2 * (1 << tables)
    assert plan.complexity["distinct_witness_families"] == 2
    assert plan.truncated is False


def test_missing_clause_does_not_invent_a_target_from_sensitive_tables():
    plan = generate_protection_plan(_distribution(), "No policy sentence here.")
    assert plan.parse_status == "no_clause"
    assert plan.targets == ()
    assert plan.declared_names == ()


def test_sumleaks_audit_matches_the_thirteen_and_thirty_three():
    raw = Path("/Users/MBP/Exp/CogniGuard/cogniguard_raw/sumleaks_repo/data")
    witness = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/sumleaks/witness_sets.jsonl")
    failures = Path(
        "/Users/MBP/Exp/CogniGuard/cmp2/experiments/cogniguard_comparison_phase2"
        "/results/protocol_b/protocol_b_failure_cases.json"
    )
    if not (raw.exists() and witness.exists() and failures.exists()):
        pytest.skip("Sum Leaks inputs are not on this machine")
    from experiments.protocol_b_targets_20261125.audit_cases import audit

    report = audit(raw, witness, failures)
    dest = HERE / "results"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "audit.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False) + "\n"
    )
    assert report["invariant_violations"] == []
    assert report["e7_initial_held"] == 33
    assert report["counts"]["e7_all_witnesses_initial"] == 32
    assert len(report["wrong_scene_ids"]) == 13
    assert report["counts"]["external_propagation"] == 0
    assert report["counts"]["scenes_with_two_schema_targets"] > 1
    assert report["counts"]["schema_targets"] > report["counts"]["e7_scenes"]


def test_witnesses_are_minimal_and_classes_match_the_holding_sets():
    plan = _plan()
    initial = set(plan.initial_units)
    external = set(plan.external_units)
    for target in plan.targets:
        sets = [witness.unit_ids for witness in target.witnesses]
        assert sets
        assert all(len(units) >= 2 for units in sets)
        assert not any(left < right for left in sets for right in sets)
        for witness in target.witnesses:
            if witness.unit_ids <= initial:
                assert witness.leak_class == CLASS_INITIAL
            elif witness.unit_ids <= initial | external:
                assert witness.leak_class == CLASS_EXTERNAL
            else:
                assert witness.leak_class == CLASS_SYSTEM
        name = target.table_unit.split(".", 1)[1]
        assert name in plan.declared_names
