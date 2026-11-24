"""Mechanism tests on a hand-built secret, plus data checks when the dataset is present."""

from __future__ import annotations

import math
from itertools import combinations

import pytest

from experiments.capd_e5_20261123.arms import GateArm, PerRecipientBits, no_defense_spend
from experiments.capd_e5_20261123.data import Secret, data_dir, load_secrets
from experiments.capd_e5_20261123.workload import _request, generate
from experiments.capd_e5_20261123 import run


def _toy() -> Secret:
    # K=8, tau=2. u0 keeps {q0..q3} (1 bit), u1 keeps {q0,q1,q4,q5} (1 bit),
    # u2 keeps {q0,q2,q4,q6} (1 bit). Any pair keeps 2 (2 bits); all three keep 1 (3 bits).
    tid = "toy"
    sat = {
        (tid, "u0"): frozenset({"q0", "q1", "q2", "q3"}),
        (tid, "u1"): frozenset({"q0", "q1", "q4", "q5"}),
        (tid, "u2"): frozenset({"q0", "q2", "q4", "q6"}),
    }
    return Secret(tid, 8, 2.0, tuple(sorted(sat)), sat, (frozenset(sat),))


def test_leakage_matches_definition() -> None:
    s = _toy()
    assert s.leakage(()) == 0.0
    assert s.leakage([("toy", "u0")]) == 1.0
    assert s.leakage([("toy", "u0"), ("toy", "u1")]) == 2.0
    assert s.leakage_star(s.units) == 3.0 > s.tau


def test_gate_blocks_a_split_witness_when_g_le_k() -> None:
    s = _toy()
    arm = GateArm((s,), 3)
    picks = [arm.select(f"m{i}", _request(f"m{i}", "coalition", "g", u).candidates)
             for i, u in enumerate(s.units)]
    assert [p.name for p in picks] == ["full", "full", "summary"]


def test_pairwise_only_misses_a_size_three_witness() -> None:
    s = _toy()
    arm = GateArm((s,), 3, max_witness=2)
    picks = [arm.select(f"m{i}", _request(f"m{i}", "coalition", "g", u).candidates)
             for i, u in enumerate(s.units)]
    assert all(p.name == "full" for p in picks)


def test_per_recipient_bits_charges_own_view_only() -> None:
    s = _toy()
    arm = PerRecipientBits((s,), 2.0)
    a = [arm.select("a", _request("a", "normal", None, u).candidates).name for u in s.units]
    assert a == ["full", "full", "summary"]
    assert arm.select("b", _request("b", "normal", None, s.units[2]).candidates).name == "full"


def test_global_fraction_one_spends_what_no_defense_spends() -> None:
    s = _toy()
    stream = generate((s,), student_count=4, coalition_sizes=(2,), seed=1,
                      normal_requests=2, complete_ratio=0.0)
    spec = run.Spec("global_bits", 1.0, 8, 0.0, 1)
    row, _ = run.run_spec(spec, (s,), stream)
    nd, _ = run.run_spec(run.Spec("no_defense", None, 8, 0.0, 1), (s,), stream)
    assert row["UR_normal"] == nd["UR_normal"]
    assert no_defense_spend((s,), stream.requests) > 0


def test_grid_size() -> None:
    assert len(tuple(run.iter_specs())) == 3 * 2 * 10 * 20


DATA = data_dir()
needs_data = pytest.mark.skipif(not (DATA / "targets.jsonl").exists(), reason="synthetic data absent")


@needs_data
@pytest.mark.parametrize("K", (8, 16, 32))
def test_lemma_1_on_every_subset(K) -> None:
    for secret in load_secrets(K)[:40]:
        assert math.isclose(secret.tau, math.log2(K) - 1)
        for size in range(len(secret.units) + 1):
            for subset in combinations(secret.units, size):
                held = frozenset(subset)
                exceeds = secret.leakage_star(held) > secret.tau + 1e-9
                assert exceeds == any(w <= held for w in secret.witness_sets)


@needs_data
def test_streams_are_reproducible() -> None:
    secrets = load_secrets(8)
    kwargs = dict(student_count=60, coalition_sizes=(2, 2, 3, 3, 4, 4), seed=3,
                  normal_requests=4, complete_ratio=0.2)
    assert generate(secrets, **kwargs) == generate(secrets, **kwargs)
