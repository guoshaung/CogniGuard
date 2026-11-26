import random

import pytest

from experiments.cogniguard_cgc4 import a_exp as AX
from experiments.cogniguard_cgc4.a_engine import Instance, check_safe
from experiments.cogniguard_sp import sp_exp as X
from experiments.cogniguard_sp.sp import SPPolicy, solve_lp


def tiny(alt_free):
    # units 0,1,2 ; witness {0,1}; type A options {0} (+ {2} if alt_free); type B options {1}
    tA = (0, (1, 4)) if alt_free else (0, (1,))
    return Instance(3, [0b011], [tA, (0, (2,))], [0.5, 0.5], 6)


def test_price_zero_with_free_alternative():
    I = tiny(True)
    sp = SPPolicy("SP_LP", I, I.q)
    ck = sp.canon.state_key(I.K0)
    v, lam, price, _ = solve_lp(I, ck, [3, 3])
    assert v == pytest.approx(6, abs=1e-3)   # A routed to free unit 2, B uses unit 1
    # consuming unit 0 displaces B (left-derivative price 3); unit 2 is free
    assert price.get((0, 0), 0) == pytest.approx(3, abs=1e-3) and price.get((0, 2), 0) == 0
    assert sp.act(0, I.K0, 0, random.Random(0)) == 4


def test_price_positive_when_conflict():
    I = tiny(False)
    sp = SPPolicy("SP_LP", I, I.q)
    ck = sp.canon.state_key(I.K0)
    v, lam, price, _ = solve_lp(I, ck, [3, 3])
    assert v == pytest.approx(3, abs=1e-3)   # x0 + x1 <= 1 -> fractional LP serves 3 of 6
    assert sum(lam.values()) > 0


def test_homogeneity_in_h():
    I = AX.gen_synth(3, "base")
    sp = SPPolicy("SP_LP", I, I.q)
    ck = sp.canon.state_key(I.K0)
    v1, l1, p1, _ = solve_lp(I, ck, [2 * p for p in I.q])
    v2, l2, p2, _ = solve_lp(I, ck, [10 * p for p in I.q])
    assert v2 == pytest.approx(5 * v1, rel=1e-6)


@pytest.mark.parametrize("name", ["SP_LP", "SP_DISP", "SP_MYOPIC", "SP_D", "A1_D"])
def test_safe_and_feasible(name):
    for seed in range(3):
        I = AX.gen_synth(seed, "conflict")
        pol = SPPolicy(name, I, I.q, gamma=0.3)
        for seq in AX.sequences(I, seed, 3, I.q):
            st = I.K0
            for t, ti in enumerate(seq):
                o = pol.act(t, st, ti, random.Random(0))
                if o is not None:
                    assert o in I.types[ti][1] and I.feasible(st[0], o)
                    st = (st[0] | o,)
            assert check_safe(I, st)


def test_opt_dominates_on_dev_instance():
    r = X.evaluate(("base", 1, "dev", ["A1", "SP_LP", "OPT_CANON_SERVE"]))
    c = {m: r["res"][m]["completion"] for m in r["res"]}
    assert c["OPT_CANON_SERVE"] >= c["A1"] - 0.15 and c["OPT_CANON_SERVE"] >= c["SP_LP"] - 0.15  # expectation-optimal; per-sample noise


def test_multi_group():
    I = AX.gen_synth(0, "k1_N3")
    assert I.groups == 3
    pol = SPPolicy("SP_LP", I, I.q)
    st = I.K0
    for t, ti in enumerate(AX.sequences(I, 0, 1, I.q)[0]):
        o = pol.act(t, st, ti, random.Random(0))
        if o is not None:
            g = I.group(I.types[ti][0])
            s2 = list(st); s2[g] |= o; st = tuple(s2)
    assert check_safe(I, st)


def test_ocost_counterexample():
    # residuals r1={0,1} (unit 1 never demanded), r2={2,3,4} (B demands {3,4}); A chooses {0} or {2}
    from experiments.cogniguard_cgc5.baselines import Baseline
    I = Instance(5, [0b00011, 0b11100], [(0, (1, 4)), (0, (24,))], [0.5, 0.5], 8)
    sp = SPPolicy("SP_LP", I, I.q)
    oc = Baseline("OCOST", I, I.q)
    rng = random.Random(0)
    assert oc.act(0, I.K0, 0, rng) == 4      # OCOST: p(2)=0.25 < p(0)=0.5 -> kills B
    assert sp.act(0, I.K0, 0, rng) == 1      # SP: unit 1 undemanded -> p(0)=0
