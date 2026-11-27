import random

from experiments.cogniguard_cgc4 import a_exp as AX
from experiments.cogniguard_cgc4.a_engine import Instance, Policy
from experiments.cogniguard_cgc5.c5_exp import build
from experiments.cogniguard_ms.prior.sr import SoftRisk


def test_zero_risk_noref_equals_a1():
    for i in (0, 2, 4):
        inst = build("eedi", (i,))
        q = AX.q_variants(inst, i)["emp"]
        a, s = Policy("A1", inst, q, gamma=0.3), SoftRisk(inst, q, {}, refuse=False)
        for seq in AX.sequences(inst, i, 5, inst.q):
            s.reset_episode()
            state = inst.K0
            for t, ti in enumerate(seq):
                oa, os_ = a.act(t, state, ti, random.Random(0)), s.act(t, state, ti, random.Random(0))
                assert oa == os_
                if oa is not None:
                    state = (state[0] | oa,)


def test_risk_and_refusal():
    I = Instance(2, [0b11], [(0, (0b01, 0b10))], [1.0], 3)
    pol = SoftRisk(I, [1.0], {0: 0.9, 1: 0.0})
    assert abs(pol.risk(0, 0b01) - 0.9) < 1e-12 and pol.risk(0b01, 0b01) == 0
    assert pol.act(0, (0,), 0, None) == 0b10           # picks the safe option
    pol2 = SoftRisk(I, [1.0], {0: 0.99, 1: 0.99})
    assert pol2.act(0, (0,), 0, None) is None          # both risky: refuse
