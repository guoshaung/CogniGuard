"""E6 wiring checks. The mechanism itself is covered by the frozen E5 tests."""

from __future__ import annotations

import math
from itertools import combinations

import pytest

from experiments.capd_e5_20261123.data import load_secrets
from experiments.capd_e6_20261123 import run

DATA = run.data_dir()
needs_data = pytest.mark.skipif(not (DATA / "targets.jsonl").exists(), reason="Eedi data absent")


def test_grid_size() -> None:
    assert len(tuple(run.iter_specs())) == 3 * 2 * 10 * 21


@needs_data
@pytest.mark.parametrize("K", (8, 16, 32))
def test_secrets_load_and_lemma_1_holds(K) -> None:
    secrets = load_secrets(K, DATA)
    assert len(secrets) > 250
    for secret in secrets[:15]:
        assert math.isclose(secret.tau, math.log2(K) - 1)
        for size in range(len(secret.units) + 1):
            for subset in combinations(secret.units, size):
                held = frozenset(subset)
                over = secret.leakage_star(held) > secret.tau + 1e-9
                assert over == any(w <= held for w in secret.witness_sets)
