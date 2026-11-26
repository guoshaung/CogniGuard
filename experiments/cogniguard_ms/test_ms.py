import math

from experiments.cogniguard_cgc4.a_engine import Instance, popcount
from experiments.cogniguard_cgc5.c5_exp import build
from experiments.cogniguard_ms import ms


def inst():
    return build("synth", (3, "base"))


def test_nested_and_shapes():
    I = inst()
    for mode in ms.MODES:
        a = ms.hidden(I, "synth", (3, "base"), mode, 0.1)
        b = ms.hidden(I, "synth", (3, "base"), mode, 0.5)
        assert set(a) <= set(b)
        for h in b:
            assert h not in I.W and not any(w & ~h == 0 for w in I.W)
            assert popcount(h) >= 1
    for h in ms.hidden(I, "synth", (3, "base"), "shrink", 0.5):
        assert any(h & ~w == 0 and popcount(w) == popcount(h) + 1 for w in I.W)


def test_breach_voids_episode():
    # units 0,1,2; observed witness {0,1}; hidden {0,2}; one task with options {0},{2}
    I = Instance(3, [0b011], [(0, (0b001,)), (0, (0b100,))], [0.5, 0.5], 2)

    class Fixed:
        calls = 0

        def act(self, t, state, ti, rng):
            self.calls += 1
            return I.types[ti][1][0]

    r = ms.run(I, [0b101], Fixed(), [[0, 1]], 0)
    assert r["raw"] == 1.0 and r["U"] == 0.0 and r["breach"] == 1.0
    r = ms.run(I, [], Fixed(), [[0, 1]], 0)
    assert r["U"] == 1.0


def test_a1_unchanged_without_hidden():
    I = inst()
    q = ms.AX.q_variants(I, 3)["emp"]
    seqs = ms.AX.sequences(I, 3, 4, I.q)
    r = ms.run(I, [], ms.make("A1", I, I, q), seqs, 3)
    o = ms.run(I, [], ms.make("ORACLE_A1", I, ms.true_instance(I, []), q), seqs, 3)
    assert r["U_ep"] == o["U_ep"] and r["unsafe_obs"] == 0
