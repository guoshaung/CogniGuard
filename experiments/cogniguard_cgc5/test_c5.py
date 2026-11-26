"""Decision-correctness checks for A1 and the exact baselines (python -m pytest experiments/cogniguard_cgc5/test_c5.py)."""

import random

import pytest

from experiments.cogniguard_cgc4 import a_exp as AX
from experiments.cogniguard_cgc4.a_engine import Engine, Policy, popcount
from experiments.cogniguard_cgc5.baselines import Baseline, Canon


def instances():
    out = []
    for c in ("small", "base", "tight", "overlap", "conflict"):
        for s in range(8):
            out.append(AX.gen_synth(500 + s, c))
    return out


@pytest.mark.parametrize("inst", instances())
def test_incremental_kill_count_matches_brute_force(inst):
    eng = Engine(inst)
    rng = random.Random(0)
    for _ in range(40):
        K = 0
        for ti in rng.sample(range(len(inst.types)), min(4, len(inst.types))):
            for o in inst.types[ti][1]:
                if inst.feasible(K, o):
                    K |= o
                    break
        for ti, (_, opts) in enumerate(inst.types):
            for o in opts:
                if not inst.feasible(K, o):
                    continue
                for tj in range(len(inst.types)):
                    alive = [o2 for o2 in inst.types[tj][1] if inst.feasible(K, o2)]
                    brute = sum(1 for o2 in alive if not inst.feasible(K | o, o2))
                    assert eng.killed_after(K, o, tj) == brute


@pytest.mark.parametrize("inst", instances())
def test_canonical_alive_sets_match_raw(inst):
    b = Baseline("MPC_OPT", inst, inst.q)
    rng = random.Random(1)
    for _ in range(30):
        K = 0
        for ti in rng.sample(range(len(inst.types)), min(5, len(inst.types))):
            for o in inst.types[ti][1]:
                if inst.feasible(K, o):
                    K |= o
                    break
        ck = b.canon.key(K)
        for ti, (_, opts) in enumerate(inst.types):
            assert b._alive_c(ck, ti) == tuple(o for o in opts if inst.feasible(K, o))


@pytest.mark.parametrize("seed", range(6))
def test_canonical_opt_equals_plain_dp(seed):
    inst = AX.gen_synth(700 + seed, "small")
    plain = Policy("OPT_SERVE", inst, inst.q)
    canon = Baseline("OPT_CANON_SERVE", inst, inst.q)
    v_plain = plain._opt(0, inst.K0)
    v_canon = canon._opt_c(canon.canon.state_key(inst.K0), inst.H, False)
    # plain OPT in CGC4 allows deferral; compare with the deferral variant
    v_canon_d = canon._opt_c(canon.canon.state_key(inst.K0), inst.H, True)
    assert v_canon_d == pytest.approx(v_plain, abs=1e-9)
    assert v_canon <= v_canon_d + 1e-12
