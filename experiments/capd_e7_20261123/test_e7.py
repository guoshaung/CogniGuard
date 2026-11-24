"""E7 wiring checks and the Sum Leaks join rule on a tiny hand-made scene."""

from __future__ import annotations

import json
from itertools import combinations

import pytest

from experiments.capd_e7_20261123 import run
from experiments.capd_e7_20261123.data import load_secrets
from experiments.datasets.sumleaks import generate as gen

DATA = run.data_dir()
needs_data = pytest.mark.skipif(not (DATA / "targets.jsonl").exists(), reason="Sum Leaks data absent")


def _scene(tmp_path):
    raw = {
        "data_distribution": {
            "Alice": {"table": {
                "bookings": {"sensitivity": "non-sensitive",
                             "rows": [{"apartment_id": 1, "status": "ok"},
                                      {"apartment_id": 2, "status": "ok"}]},
                "emp_apartment": {"sensitivity": "sensitive",
                                  "rows": [{"employee_id": 10, "apartment_id": 1},
                                           {"employee_id": 20, "apartment_id": 2}]}}},
            "Bob": {"table": {
                "cities": {"sensitivity": "non-sensitive",
                           "rows": [{"apartment_id": 1, "city": "A"}, {"apartment_id": 2, "city": "B"}]},
                "salary": {"sensitivity": "sensitive",
                           "rows": [{"employee_id": 10, "salary": 100},
                                    {"employee_id": 20, "salary": 200},
                                    {"employee_id": 30, "salary": 300}]}}},
        },
        "defense": "A combination of emp_apartment and salary is sensitive.",
    }
    path = tmp_path / "experiment_7_def_adv_both.json"
    path.write_text(json.dumps(raw))
    return path


def test_grid_size() -> None:
    assert len(tuple(run.iter_specs())) == 2 * 10 * (1 + 5 + len(run.GLOBAL_FRACTIONS) + 3 + 3)


def test_join_rule_needs_both_tables(tmp_path) -> None:
    scene = gen.load_scene(_scene(tmp_path))
    chosen, pairs, _ = gen.pick(scene)
    assert pairs > 0 and chosen["status"] == "computed"
    names = [t["unit_id"] for t in scene["tables"]]
    sets = [{names[i] for i in range(len(names)) if m >> i & 1} for m in chosen["witnesses"]]
    assert {"Alice.emp_apartment", "Bob.salary"} in sets
    assert all(len(s) >= 2 for s in sets)
    assert chosen["K"] == 3


def test_build_writes_outside_repo_only(tmp_path) -> None:
    _scene(tmp_path)
    with pytest.raises(ValueError):
        gen.build(tmp_path, gen.REPO / "experiments")
    out = gen.build(tmp_path, tmp_path / "out")
    assert (out / "targets.jsonl").exists() and (out / "secrets_private.jsonl").exists()


@needs_data
def test_lemma_1_holds_on_every_secret() -> None:
    secrets = load_secrets()
    assert len(secrets) >= 50
    for secret in secrets:
        assert {s.kind for s in [secret.target()]} == {"student_attribute"}
        for size in range(len(secret.units) + 1):
            for subset in combinations(secret.units, size):
                held = frozenset(subset)
                over = secret.leakage_star(held) > secret.tau + 1e-9
                assert over == any(w <= held for w in secret.witness_sets)
