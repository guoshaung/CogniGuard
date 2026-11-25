"""DEGC: dual-entropy governance control (a CGC decision layer around the unchanged CA-PD kernel).

Two uncertainties are kept apart:
  leakage entropy   adversary side. The secret S is reconstructed when the coalition's knowledge covers
                    a witness. With prior min-entropy H0 and reconstruction probability R, the expected
                    vulnerability is V = R + (1 - R) 2^-H0 and the min-entropy leakage is log2(V 2^H0).
  state entropy     governance side. The true knowledge state K* is unknown; evidence E only gives
                    calibrated per-observation disclosure probabilities. The decision-relevant quantity is
                    the Boolean event Z_a = [release a completes a witness]; its entropy h(R_a) given E is the
                    state (epistemic) entropy that matters for the decision, and a Beta posterior on every
                    calibration bin gives a second-order interval [R_lo, R_hi].
R is computed by enumerating the uncertain witness-relevant variables and calling the CA-PD kernel
(`check_release`) on each completion, so the combinatorial structure (witness covers, k-bounded
coalitions) is exactly the kernel's; nothing in the kernel changes.

Decision (per request):
  allow   if R_hi <= delta                                  (safe even under calibration uncertainty)
  verify  while R_lo <= delta < R_hi (ambiguous) and budget remains: pay for the pair with the largest
          expected reduction of h(R) per call (decision-focused information gain)
  final   allow iff R <= delta (chance constraint on the point posterior). High state entropy therefore
          only ever buys verification; it never refuses on its own (bounded conservatism).
Trusted events (the recipient's own data, receipts) enter with probability 1. Semantic observations never
do: an NLI hit is an observation with a calibrated probability, and so is a verifier answer.

This module never reads evaluation labels. A calibrator is fitted elsewhere and passed in.
"""

from __future__ import annotations

import itertools
import math
import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from cogniguard.governance.reconstruction import check_release

# ------------------------------------------------------------------ Beta utilities (no scipy)


def _betacf(a, b, x):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-30 else 1e-30)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-30 else 1e-30
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-30 else 1e-30
        de = d * c
        h *= de
        if abs(de - 1) < 1e-12:
            break
    return h


def beta_cdf(x, a, b):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lb = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lb) * _betacf(a, b, x) / a
    return 1 - math.exp(lb) * _betacf(b, a, 1 - x) / b


def beta_ppf(p, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if beta_cdf(mid, a, b) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def h2(p):
    return 0.0 if p <= 0 or p >= 1 else -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


# ------------------------------------------------------------------ calibration


@dataclass
class BetaCalibrator:
    """Maps an observation's bin to P(actually disclosed) with a Beta posterior per bin.

    Bins are produced by `binner(features)`; counts come from labelled development data only.
    A bin never seen falls back to the pooled rate of its `family` (first element of the bin key)."""

    binner: Callable[[dict], tuple]
    prior: tuple[float, float] = (1.0, 1.0)
    level: float = 0.9
    counts: dict = field(default_factory=dict)

    def fit(self, rows: Iterable[tuple[dict, bool]]):
        self.counts = {}
        self.__dict__.pop("_memo", None)
        for feats, y in rows:
            for key in (self.binner(feats), (self.binner(feats)[0],)):
                pos, n = self.counts.get(key, (0, 0))
                self.counts[key] = (pos + bool(y), n + 1)
        return self

    def posterior(self, feats: dict):
        key = self.binner(feats)
        pos, n = self.counts.get(key, self.counts.get((key[0],), (0, 0)))
        a, b = self.prior[0] + pos, self.prior[1] + n - pos
        memo = self.__dict__.setdefault("_memo", {})
        if (a, b, self.level) not in memo:
            t = (1 - self.level) / 2
            memo[(a, b, self.level)] = (a / (a + b), beta_ppf(t, a, b), beta_ppf(1 - t, a, b))
        return memo[(a, b, self.level)]


def ece(probs, ys, bins=10):
    tot, err = len(probs), 0.0
    for i in range(bins):
        sel = [(p, y) for p, y in zip(probs, ys) if (i / bins <= p < (i + 1) / bins) or (i == bins - 1 and p == 1)]
        if sel:
            err += len(sel) / tot * abs(sum(p for p, _ in sel) / len(sel) - sum(y for _, y in sel) / len(sel))
    return err


def brier(probs, ys):
    return sum((p - y) ** 2 for p, y in zip(probs, ys)) / len(probs)


# ------------------------------------------------------------------ knowledge-state belief


@dataclass
class Obs:
    """One observation that `principal` may have learned `unit` (from one released artifact)."""

    obs_id: str
    principal: str
    unit: tuple
    p: float
    lo: float
    hi: float
    feats: dict = field(default_factory=dict)
    verified: bool = False


class KnowledgeBelief:
    """Per principal, per unit: trusted units (probability 1) plus a list of uncertain observations.

    combine='noisy_or' treats observations of the same unit as independent; combine='max' treats them as
    fully correlated (comonotone) -- the two bracket the true dependence between repeated misses."""

    def __init__(self, combine: str = "noisy_or"):
        self.combine = combine
        self.trusted: dict[str, set] = {}
        self.obs: dict[tuple, Obs] = {}

    def add_trusted(self, principal, units):
        self.trusted.setdefault(principal, set()).update(units)

    def add_obs(self, o: Obs):
        self.obs[o.obs_id] = o

    def _comb(self, ps):
        if not ps:
            return 0.0
        if self.combine == "max":
            return max(ps)
        out = 1.0
        for p in ps:
            out *= 1 - p
        return 1 - out

    def marginal(self, principal, unit, which="p", extra: Iterable[Obs] = ()):
        if unit in self.trusted.get(principal, ()):
            return 1.0
        ps = [getattr(o, which) for o in itertools.chain(self.obs.values(), extra)
              if o.principal == principal and o.unit == unit]
        return self._comb(ps)

    def map_state(self, extra: Iterable[Obs] = ()):
        """Deterministic state a non-probabilistic gate would use (p >= 0.5)."""
        out = {p: set(u) for p, u in self.trusted.items()}
        for o in itertools.chain(self.obs.values(), extra):
            if o.p >= 0.5:
                out.setdefault(o.principal, set()).add(o.unit)
        return {p: frozenset(u) for p, u in out.items()}


# ------------------------------------------------------------------ reconstruction risk via the CA-PD kernel


MC = {"samples": 1024, "prune": 1e-6}


def reconstruction_risk(registry, belief: KnowledgeBelief, recipient: str, k: int, pending: Iterable[Obs] = (),
                        which: str = "p", max_enum: int = 12, samples: int | None = None, seed: int = 0):
    """P(exists coalition of size <= k containing recipient that covers a witness), with `pending`
    observations treated as already delivered. Exact enumeration over uncertain witness variables."""
    pending = list(pending)
    wit_units = set()
    for t in registry._by_id.values():
        for w in t.witness_sets:
            wit_units |= set(w)
    # with k = 1 only the recipient's own knowledge can matter
    principals = {recipient} if k == 1 else (set(belief.trusted) | {o.principal for o in belief.obs.values()} | {recipient})
    fixed, unc = {p: set() for p in principals}, []
    for p in principals:
        for u in wit_units:
            m = belief.marginal(p, u, which, pending)
            if m >= 1.0 - MC["prune"]:
                fixed[p].add(u)
            elif m > MC["prune"]:
                unc.append((p, u, m))
    if not wit_units:
        return 0.0

    def unsafe(extra):
        know = {p: frozenset(fixed[p] | extra.get(p, set())) for p in principals}
        return state_unsafe(registry, recipient, know, k)

    if len(unc) <= max_enum:
        tot = 0.0
        for bits in itertools.product((0, 1), repeat=len(unc)):
            pr, extra = 1.0, {}
            for (p, u, m), b in zip(unc, bits):
                pr *= m if b else 1 - m
                if b:
                    extra.setdefault(p, set()).add(u)
            if pr > 0 and unsafe(extra):
                tot += pr
        return tot
    samples = samples or MC["samples"]
    rng, hit = random.Random(seed), 0
    for _ in range(samples):
        extra = {}
        for p, u, m in unc:
            if rng.random() < m:
                extra.setdefault(p, set()).add(u)
        hit += unsafe(extra)
    return hit / samples


def state_unsafe(registry, recipient, know, k):
    """Does some coalition of size <= k containing `recipient` cover a witness in state `know`?
    Pure use of the CA-PD kernel: the recipient's witness-relevant holdings are passed as the release."""
    know = {p: frozenset(u) for p, u in know.items()}
    rel = frozenset(u for u in know.get(recipient, ()) if registry.targets_for_unit(u))
    if rel:
        return not check_release(registry, recipient, rel, know, k).safe
    if k < 2:
        return False
    # recipient contributes nothing: some coalition of <= k-1 others must cover a witness on its own
    others = {p: u for p, u in know.items() if p != recipient}
    return any(state_unsafe(registry, p, others, k - 1) for p in others)


def leakage_entropy(R, h0_bits=1.0):
    """Min-entropy leakage (bits) when the secret is reconstructed with probability R."""
    v0 = 2 ** -h0_bits
    return math.log2((R + (1 - R) * v0) / v0)


# ------------------------------------------------------------------ the policy


@dataclass
class DegcConfig:
    delta: float = 0.1            # per-release bound on new reconstruction probability
    use_leakage: bool = True      # False -> decide on the MAP state with the deterministic kernel
    use_epistemic: bool = True    # False -> no ambiguity trigger, no entropy-driven verification
    per_request_cap: int = 2      # verification calls per request
    budget: float = math.inf      # total verification calls
    h0_bits: float = 1.0
    k: int = 1
    selector: str = "eig"         # "eig": expected reduction of h(R); "ec2": of R(1-R) (EC2 edge weight)
    trigger: str = "interval"     # "interval": R_lo <= thr < R_hi; "entropy": h(R) >= eta (BALD-style, delta-blind)
    eta: float = 0.5


@dataclass
class DegcDecision:
    allowed: bool
    reason: str
    R: float
    R_lo: float
    R_hi: float
    R_before: float
    leak_bits: float
    state_entropy: float
    verified: list = field(default_factory=list)


class DegcPolicy:
    """CGC decision layer. `verify(obs) -> (p, lo, hi)` is the shared verifier (already calibrated)."""

    governance_mode = "degc"

    def __init__(self, registry, cfg: DegcConfig, verify: Callable[[Obs], tuple] | None = None):
        self.registry, self.cfg, self.verify_fn = registry, cfg, verify
        self.calls = 0

    def _risk(self, belief, recipient, pending, which="p"):
        return reconstruction_risk(self.registry, belief, recipient, self.cfg.k, pending, which)

    def _all(self, belief, recipient, pending):
        r = self._risk(belief, recipient, pending)
        return r, self._risk(belief, recipient, pending, "lo"), self._risk(belief, recipient, pending, "hi")

    def _eig(self, belief, recipient, pending, cand: Obs, r):
        """Expected reduction of h(R) if `cand` is verified (outcome probability = its current p)."""
        saved = (cand.p, cand.lo, cand.hi)
        out = []
        for val in (1.0, 0.0):
            cand.p = cand.lo = cand.hi = val
            out.append(self._risk(belief, recipient, pending))
        cand.p, cand.lo, cand.hi = saved
        f = h2 if self.cfg.selector == "eig" else (lambda x: x * (1 - x))
        return f(r) - (cand.p * f(out[0]) + (1 - cand.p) * f(out[1]))

    def _apply(self, cand: Obs):
        cand.p, cand.lo, cand.hi = self.verify_fn(cand)
        cand.verified = True
        self.calls += 1

    def decide(self, recipient: str, belief: KnowledgeBelief, pending: list[Obs]) -> DegcDecision:
        cfg = self.cfg
        before = self._risk(belief, recipient, [])
        verified = []
        if not cfg.use_leakage:
            # epistemic-only ablation: entropy-driven verification, then the deterministic kernel on MAP state
            while self.verify_fn and cfg.use_epistemic and len(verified) < cfg.per_request_cap and self.calls < cfg.budget:
                pool = [o for o in list(belief.obs.values()) + pending if not o.verified and 0 < o.p < 1]
                if not pool:
                    break
                c = max(pool, key=lambda o: h2(o.p))
                self._apply(c)
                verified.append(c.obs_id)
            units = {o.unit for o in pending if o.p >= 0.5}
            safe = not units or check_release(self.registry, recipient, units, belief.map_state(), cfg.k).safe
            r = self._risk(belief, recipient, pending)
            return DegcDecision(safe, "map-state kernel", r, r, r, before, leakage_entropy(r, cfg.h0_bits), h2(r), verified)
        r, lo, hi = self._all(belief, recipient, pending)
        def ambiguous():
            if cfg.trigger == "entropy":
                return h2(r) >= cfg.eta
            return lo <= self._thr(before) < hi

        while (cfg.use_epistemic and self.verify_fn and ambiguous()
               and len(verified) < cfg.per_request_cap and self.calls < cfg.budget):
            # only witness-relevant uncertainty can change the decision
            pool = [o for o in list(belief.obs.values()) + pending
                    if not o.verified and 0 < o.p < 1 and self.registry.targets_for_unit(o.unit)]
            if not pool:
                break
            c = max(pool, key=lambda o: self._eig(belief, recipient, pending, o, r))
            self._apply(c)
            verified.append(c.obs_id)
            r, lo, hi = self._all(belief, recipient, pending)
        allowed = r <= self._thr(before)
        reason = "chance constraint" if not verified else "after verification"
        if hi <= self._thr(before):
            reason = "robustly safe"
        return DegcDecision(allowed, reason, r, lo, hi, before, leakage_entropy(r, cfg.h0_bits), h2(r), verified)

    def _thr(self, before):
        # bound the NEW reconstruction probability: R - R_before <= delta (historical leakage is not
        # attributed to this release)
        return before + self.cfg.delta
