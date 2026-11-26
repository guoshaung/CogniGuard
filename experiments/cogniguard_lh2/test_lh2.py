"""Unit checks for the P0 model (python -m pytest experiments/cogniguard_lh2/test_lh2.py)."""
import pytest
from experiments.cogniguard_lh2 import model as M


@pytest.mark.parametrize("name", M.STRUCTS)
def test_lemma1_cross_iff_contains_derivation(name):
    S = M.Struct(name)
    for w in range(0, S.nw, max(1, S.nw // 12)):
        ders = S.derivations(w)
        for A in range(1 << S.m):
            assert bool(S.cross[A, w]) == any(d & ~A == 0 for d in ders)


@pytest.mark.parametrize("name", M.STRUCTS)
def test_belief_sums_to_one_and_contains_truth(name):
    for seed in range(10):
        inst = M.gen_instance(seed, name, "line", "rand", "varied")
        b = M.belief(M.Struct(name), inst)
        assert sum(b.values()) == pytest.approx(1.0)
        assert (inst["atype"], inst["hidden"], inst["bud0"]) in b


@pytest.mark.parametrize("name", M.STRUCTS)
def test_h2_bounds(name):
    S = M.Struct(name)
    for seed in range(8):
        inst = M.gen_instance(seed, name, "star", "rand", "unit")
        A = inst["RA"] | inst["hidden"]
        h2 = M.H2_state(S, inst, A, inst["bud0"])
        assert -1e-9 <= h2 <= S.Hc(S.cell(A, inst["w"])) + 1e-9
