"""Exact-enumeration correctness checks (run: python -m pytest experiments/cogniguard_ksl/test_ksl.py)."""

import itertools
import math
import random

import numpy as np
import pytest

from experiments.cogniguard_ksl import engine, structures as S

ALL = {s.name: engine.build(s) for s in S.all_structures()}


def brute(T, mask, x):
    st, w0 = T.st, T.st.worlds[x]
    names = T.names(mask)
    post = {}
    for i, w in enumerate(st.worlds):
        if all(st.units[u](w) == st.units[u](w0) for u in names):
            post[st.secret(w)] = post.get(st.secret(w), 0) + T.prior[i]
    z = sum(post.values())
    post = {k: v / z for k, v in post.items()}
    v1 = max(post.values())
    h = -sum(p * math.log2(p) for p in post.values() if p > 0)
    vg = max(sum(p * st.gain(g, s) for s, p in post.items()) for g in T.svals)
    return v1, h, vg, post.get(st.secret(w0), 0.0)


@pytest.mark.parametrize("name", list(ALL))
def test_tables_match_brute_force(name):
    T = ALL[name]
    rng = random.Random(0)
    for _ in range(60):
        mask = rng.randrange(1 << len(T.units))
        x = rng.randrange(len(T.st.worlds))
        v1, h, vg, ps = brute(T, mask, x)
        assert T.V1[mask, x] == pytest.approx(v1)
        assert T.H[mask, x] == pytest.approx(h, abs=1e-9)
        assert T.Vg[mask, x] == pytest.approx(vg)
        assert T.pst[mask, x] == pytest.approx(ps)


def test_closed_forms():
    P = ALL["parallel"]
    assert P.prior_V1() == pytest.approx(1 / 64)
    assert np.allclose(P.V1[P.mask(["branch_1", "branch_2"])], 1 / 4)
    assert P.witnesses == [P.mask(["branch_1", "branch_2", "branch_3"])]
    R = ALL["relation"]
    assert np.allclose(R.V1[R.mask(["adv_of_s0", "adv_of_s1"])], 1 / 2)        # no witness yet, V1 = 0.5
    assert not R.cov[R.mask(["adv_of_s0", "adv_of_s1"])]
    assert sorted(R.witnesses) == sorted(R.mask(c) for c in itertools.combinations([f"adv_of_s{i}" for i in range(4)], 3))
    X = ALL["and_xor"]
    for m in (X.mask(["in_a"]), X.mask(["in_b"]), X.mask(["in_a_hi"])):   # perfect sharing: no partial leak
        assert np.allclose(X.V1[m], X.prior_V1())
    M = ALL["and_max"]
    a3 = [i for i, w in enumerate(M.st.worlds) if w[0][0] == 3]
    assert np.all(M.det[M.mask(["in_a"]), a3]) and not M.cov[M.mask(["in_a"])]   # realized determination, no witness


@pytest.mark.parametrize("name", list(ALL))
def test_expected_vulnerability_monotone_under_refinement(name):
    T = ALL[name]
    ev = T.V1 @ T.prior
    for k in range(1 << len(T.units)):
        for j in range(len(T.units)):
            assert ev[k | 1 << j] >= ev[k] - 1e-12


@pytest.mark.parametrize("name", list(ALL))
def test_kernel_agrees_with_coverage_table(name):
    T = ALL[name]
    reg = engine.registry(T)
    rng = random.Random(1)
    m = len(T.units)
    for _ in range(150):
        know = {a: rng.randrange(1 << m) & rng.randrange(1 << m) for a in "ABC"}
        rel = 1 << rng.randrange(m)
        k = rng.choice([1, 2, 3])
        rec = rng.choice("ABC")
        others = [a for a in "ABC" if a != rec]
        exposed = any(T.cov[know[rec] | rel | (know[c[0]] if c else 0) | (know[c[1]] if len(c) > 1 else 0)]
                      for r in range(0, k) for c in itertools.combinations(others, r))
        # the kernel only inspects targets touched by the release
        touched = any(rel & w for w in T.witnesses)
        assert engine.capd_safe(T, reg, rec, rel, know, k) == (not (exposed and touched))


def exact_p_harm(ctx, P, a, M_post, tau):
    """Exact enumeration over every agent-unit bit and the pending-release posterior (small N only)."""
    N, m = P.shape
    cs = ctx.coalitions(a)
    tot = 0.0
    for bits in itertools.product((0, 1), repeat=N * m):
        pr = 1.0
        masks = [0] * N
        for idx, b in enumerate(bits):
            i, j = divmod(idx, m)
            pr *= P[i, j] if b else 1 - P[i, j]
            masks[i] |= b << j
        if pr == 0:
            continue
        for Mt, pm in M_post:
            cm = [int(np.bitwise_or.reduce([masks[i] for i in c])) for c in cs]
            bf = max(ctx.V1[c] for c in cm)
            af = max(ctx.V1[c | Mt] for c in cm)
            tot += pr * pm * (af >= tau - 1e-12 and af > bf + 1e-12)
    return tot


@pytest.mark.parametrize("name", ["relation", "and_max", "or_alt", "mixed"])
def test_monte_carlo_matches_exact(name):
    from experiments.cogniguard_ksl import exp_methods as X
    rng = np.random.default_rng(3)
    T, _ = X.tables(name)
    space = X.message_space(T)
    errs = []
    for trial in range(6):
        ctx = X.Ctx(name, 1, 1, int(rng.integers(len(T.st.worlds))), trial)
        P = rng.choice([0.0, 0.1, 0.3, 0.6, 0.9, 1.0], size=(1, len(T.units)))
        d = 1 << int(rng.integers(len(T.units)))
        w = {t: pt * X.detect_lik(T, t, d) for t, pt in space.items()}
        z = sum(w.values())
        ex = exact_p_harm(ctx, P, 0, [(t, v / z) for t, v in w.items() if v > 0], 0.5)
        mc = ctx.p_harm(P, 0, ctx.msamples(d), 0.5)
        se = math.sqrt(max(ex * (1 - ex), 1e-4) / X.NS)
        errs.append(abs(mc - ex) / se)
    assert max(errs) < 4.5
