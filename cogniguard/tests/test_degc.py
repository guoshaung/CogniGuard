"""Stage A: mathematical correctness of DEGC (minimal counterexamples, boundaries, calibration)."""

import math
import random

import pytest

from cogniguard.governance.degc import (BetaCalibrator, DegcConfig, DegcPolicy, KnowledgeBelief, Obs, beta_ppf,
                                        brier, ece, h2, leakage_entropy, reconstruction_risk, state_unsafe)
from cogniguard.governance.reconstruction import check_release
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry


def reg(*witnesses):
    return TargetRegistry([ProtectedTarget("t", "o", "org", tuple(frozenset(("r", u) for u in w) for w in witnesses))])


def U(x):
    return ("r", x)


def obs(i, unit, p, who="A", width=0.0):
    return Obs(str(i), who, U(unit), p, max(0.0, p - width), min(1.0, p + width))


# ---------------------------------------------------------------- kernel equivalence and exactness

def test_deterministic_risk_equals_kernel():
    r = reg("ab", "c")
    rng = random.Random(0)
    for _ in range(200):
        held = {u for u in "abcd" if rng.random() < 0.5}
        b = KnowledgeBelief()
        b.add_trusted("A", {U(u) for u in held})
        R = reconstruction_risk(r, b, "A", 1)
        assert R == float(state_unsafe(r, "A", {"A": {U(u) for u in held}}, 1))


def test_inclusion_exclusion():
    r = reg("ab", "c")
    b = KnowledgeBelief()
    for i, (u, p) in enumerate((("a", .6), ("b", .5), ("c", .2))):
        b.add_obs(obs(i, u, p))
    assert reconstruction_risk(r, b, "A", 1) == pytest.approx(1 - (1 - .3) * (1 - .2))


def test_coalition_k2():
    r = reg("ab")
    know = {"A": {U("a")}, "B": {U("b")}}
    assert not state_unsafe(r, "A", know, 1) and state_unsafe(r, "A", know, 2)
    assert not check_release(r, "A", {U("a")}, {p: frozenset(v) for p, v in know.items()}, 1).safe is False
    b = KnowledgeBelief()
    b.add_trusted("A", {U("a")})
    b.add_obs(obs(0, "b", .7, who="B"))
    assert reconstruction_risk(r, b, "A", 1) == 0.0
    assert reconstruction_risk(r, b, "A", 2) == pytest.approx(.7)


def test_recipient_contributes_nothing():
    r = reg("ab")
    assert state_unsafe(r, "A", {"A": set(), "B": {U("a")}, "C": {U("b")}}, 3)
    assert not state_unsafe(r, "A", {"A": set(), "B": {U("a")}, "C": {U("b")}}, 2)


# ---------------------------------------------------------------- the three counterexamples

def test_low_leakage_high_state_entropy_spends_nothing():
    """Many uncertain units, none in a witness: state entropy is high, leakage risk is 0."""
    r = reg("ab")
    b = KnowledgeBelief()
    for i, u in enumerate("cdefgh"):
        b.add_obs(obs(i, u, .5, width=.4))
    calls = []
    pol = DegcPolicy(r, DegcConfig(delta=.1), verify=lambda o: calls.append(o) or (1.0, 1.0, 1.0))
    d = pol.decide("A", b, [obs(99, "z", .5, width=.4)])
    assert d.allowed and d.R == 0 and not calls
    # the epistemic-only ablation verifies anyway (it cannot tell relevant from irrelevant uncertainty)
    pol3 = DegcPolicy(r, DegcConfig(delta=.1, use_leakage=False), verify=lambda o: calls.append(o) or (0.0, 0.0, 0.0))
    pol3.decide("A", b, [obs(98, "z", .5, width=.4)])
    assert len(calls) == 2


def test_high_leakage_low_state_entropy_denies_without_verification():
    r = reg("ab")
    b = KnowledgeBelief()
    b.add_trusted("A", {U("a")})
    calls = []
    pol = DegcPolicy(r, DegcConfig(delta=.1), verify=lambda o: calls.append(o) or (1.0, 1.0, 1.0))
    d = pol.decide("A", b, [obs(0, "b", .99, width=.005)])
    assert not d.allowed and not calls and d.R > .98


def test_joint_units_state_divergence():
    """Two earlier observations each below the MAP threshold: a deterministic gate thinks the witness
    is far from complete; the joint posterior says releasing c completes {a,b,c} with probability .16."""
    r = reg("abc")
    b = KnowledgeBelief()
    b.add_obs(obs(0, "a", .4, width=.1))
    b.add_obs(obs(1, "b", .4, width=.1))
    pend = [obs(2, "c", 1.0)]
    det = DegcPolicy(r, DegcConfig(delta=.1, use_leakage=False, use_epistemic=False))
    assert det.decide("A", b, pend).allowed                       # deterministic MAP gate releases
    ours = DegcPolicy(r, DegcConfig(delta=.1, per_request_cap=0))
    d = ours.decide("A", b, pend)
    assert d.R == pytest.approx(.16) and not d.allowed            # chance constraint denies
    # verification repairs the state in both directions
    ours = DegcPolicy(r, DegcConfig(delta=.1, per_request_cap=2), verify=lambda o: (1.0,) * 3)
    d = ours.decide("A", b, [obs(3, "c", 1.0)])
    assert not d.allowed and d.verified and d.R_lo > .1            # a was learned: stop, deny
    b2 = KnowledgeBelief()
    b2.add_obs(obs(0, "a", .4, width=.1))
    b2.add_obs(obs(1, "b", .4, width=.1))
    ours = DegcPolicy(r, DegcConfig(delta=.1, per_request_cap=2), verify=lambda o: (0.0,) * 3)
    d = ours.decide("A", b2, [obs(3, "c", 1.0)])
    assert d.allowed and d.verified and d.R == 0.0                 # a was not learned: release


def test_bounded_conservatism():
    """Ambiguous (R_lo <= delta < R_hi) but no budget: the point chance constraint decides, not R_hi."""
    r = reg("ab")
    b = KnowledgeBelief()
    b.add_trusted("A", {U("a")})
    d = DegcPolicy(r, DegcConfig(delta=.1, budget=0), verify=lambda o: (1.0,) * 3).decide("A", b, [obs(0, "b", .08, width=.07)])
    assert d.R_hi > .1 and d.allowed


def test_historical_leak_not_attributed():
    r = reg("ab")
    b = KnowledgeBelief()
    b.add_trusted("A", {U("a"), U("b")})
    d = DegcPolicy(r, DegcConfig(delta=.1)).decide("A", b, [obs(0, "b", 1.0)])
    assert d.R_before == 1.0 and d.allowed  # no NEW reconstruction


# ---------------------------------------------------------------- entropies, correlation, calibration

def test_leakage_entropy_bounds_and_monotone():
    assert leakage_entropy(0, 3) == 0 and leakage_entropy(1, 3) == pytest.approx(3)
    xs = [leakage_entropy(r / 10, 2) for r in range(11)]
    assert all(a <= b for a, b in zip(xs, xs[1:]))
    assert h2(.5) == 1 and h2(0) == 0


def test_correlation_brackets():
    r = reg("ab")
    vals = {}
    for comb in ("noisy_or", "max"):
        b = KnowledgeBelief(comb)
        b.add_trusted("A", {U("a")})
        b.add_obs(obs(0, "b", .3))
        b.add_obs(obs(1, "b", .3))
        vals[comb] = reconstruction_risk(r, b, "A", 1)
    assert vals["max"] == pytest.approx(.3) and vals["noisy_or"] == pytest.approx(.51)


def test_beta_ppf():
    assert beta_ppf(.5, 1, 1) == pytest.approx(.5, abs=1e-6)
    assert beta_ppf(.95, 2, 5) == pytest.approx(0.5818, abs=1e-3)


def test_calibrator_recovers_rates_and_ece():
    rng = random.Random(1)
    true = {"x": .9, "y": .2, "z": .5}
    rows = [({"b": k}, rng.random() < true[k]) for _ in range(3000) for k in true]
    cal = BetaCalibrator(lambda f: (f["b"],)).fit(rows)
    for k, t in true.items():
        p, lo, hi = cal.posterior({"b": k})
        assert lo <= t <= hi and abs(p - t) < .03
    test = [({"b": k}, rng.random() < true[k]) for _ in range(2000) for k in true]
    ps = [cal.posterior(f)[0] for f, _ in test]
    ys = [y for _, y in test]
    assert ece(ps, ys) < .03 and brier(ps, ys) < .2
    # unseen bin falls back to its family / the prior, never crashes
    assert 0 < cal.posterior({"b": "new"})[0] < 1


def test_verification_budget_respected():
    r = reg("abcd")
    b = KnowledgeBelief()
    for i, u in enumerate("abc"):
        b.add_obs(obs(i, u, .5, width=.3))
    pol = DegcPolicy(r, DegcConfig(delta=.2, per_request_cap=5, budget=2), verify=lambda o: (.5, .2, .8))
    pol.decide("A", b, [obs(9, "d", 1.0)])
    assert pol.calls == 2
