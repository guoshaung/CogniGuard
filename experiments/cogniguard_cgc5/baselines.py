"""CGC5 strong baselines for look-ahead disclosure. A1 itself is imported unchanged from CGC4.

Every method sees the same candidate options, the same task-type estimate q_hat and horizon H, and the same
hard safety constraint (no group's knowledge may contain a witness). Methods that add their own refusals
(budgets, risk thresholds) can only refuse MORE than the constraint requires.

MECHANISM PROXIES (not reproductions; no claim about the original papers' results):
  OCELOT_P     after OCELOT (Xie & Li 2026, arXiv:2606.12341): every release is charged its leakage against a
               cumulative budget B; among admissible options the one with the smallest charge is released
               (minimal necessary disclosure). Charge = exact min-entropy leakage increase where the instance
               has a secret model (KSL, Eedi); otherwise a witness-progress proxy sum_W |W n new| / |W|.
  PFLOW_P      after PrivacyFlow (Staab et al. 2026, arXiv:2610.40714): simulate the inference consequence of
               each candidate plan step (risk = largest covered fraction of any witness after the release),
               choose the least-risk option, block if risk >= rho.
  DYNCQE_P     after dynamic CQE with the longest-honeymoon property (Bonatti, Cima, Lembo, Rosati, Savo):
               keep the candidate censors (maximal witness-free unit sets over the option units) consistent
               with the history and release the option that keeps the most of them, i.e. maximize the chance
               of answering the next query honestly. Censors are enumerated exactly when <= 2^14 subsets,
               otherwise sampled (random-order greedy maximal sets) with a fixed seed.
Exact re-implementations:
  A1_FULL      identical objective to A1, but alive sets of every task type are recomputed from scratch for
               each candidate (no witness-local incremental update, no cache).
  OCOST        online opportunity-cost greedy (exponential pricing as in online packing): unit price
               p_u = sum_{uncovered W containing u} 2^-(|W minus K| - 1); release the cheapest option.
  MPC_OPT      depth-d expectimax with (i) a persistent cache across decisions and episodes, (ii) exact
               state merging: two knowledge states are equivalent when they leave the same residuals
               W minus K on witnesses that can still be completed by option units; leaf = A1 value rate.
  OPT_CANON    exact DP optimum over the same canonical states (serve-only and with deferral).
"""

from __future__ import annotations

import itertools
import math
import random
from functools import lru_cache

from experiments.cogniguard_cgc4.a_engine import Engine, Policy, leaf_rate, popcount


class Canon:
    """Exact equivalence of knowledge states for future feasibility."""

    def __init__(self, inst):
        self.I = inst
        om = 0
        for _, opts in inst.types:
            for o in opts:
                om |= o
        self.optmask = om

    def key(self, K):
        res = []
        for w in self.I.W:
            r = w & ~K
            if r == 0:
                return ("UNSAFE",)
            if r & ~self.optmask == 0:          # can still be completed by future option disclosures
                res.append(r)
        return tuple(sorted(set(res)))

    def state_key(self, state):
        return tuple(self.key(K) for K in state)


class Baseline(Policy):
    def __init__(self, kind, inst, q_hat, **kw):
        super().__init__(kind if kind in ("A1",) else "A1", inst, q_hat, **kw)
        self.kind = kind
        self.kw = kw
        self.canon = Canon(inst)
        if kind == "DYNCQE_P":
            self.censors = self._censors(kw.get("samples", 256), kw.get("seed", 0))
        self.spent = [0.0] * inst.groups
        self._mcache = {}
        self._ocache = {}

    # ---------------------------------------------------------------- helpers
    def charge(self, K, o):
        I = self.I
        if hasattr(I, "leak"):
            return max(0.0, I.leak(K | o) - I.leak(K))
        new = o & ~K
        return sum(popcount(w & new) / popcount(w) for w in I.W if w & new)

    def risk(self, K):
        return max((popcount(w & K) / popcount(w) for w in self.I.W), default=0.0)

    def _censors(self, samples, seed):
        I = self.I
        units = [u for u in range(I.n) if self.canon.optmask >> u & 1]
        maximal = set()
        if len(units) <= 14:
            for r in range(len(units), -1, -1):
                for comb in itertools.combinations(units, r):
                    s = sum(1 << u for u in comb)
                    if any(w & ~s == 0 for w in I.W):
                        continue
                    if any(s & ~m == 0 for m in maximal):
                        continue
                    maximal.add(s)
            self.censor_mode = "exact"
        else:
            rng = random.Random(seed)
            for _ in range(samples):
                order = units[:]
                rng.shuffle(order)
                s = 0
                for u in order:
                    if not any(w & ~(s | 1 << u) == 0 for w in I.W):
                        s |= 1 << u
                maximal.add(s)
            self.censor_mode = "sampled"
        return list(maximal)

    def full_value(self, K, o, g, gamma):
        """A1 objective recomputed from scratch (no incremental killed set, no alive cache)."""
        I = self.I
        Ko = K | o
        tot = 0.0
        for ti in I.types_of_group[g]:
            n_alive = sum(1 for o2 in I.types[ti][1] if I.feasible(Ko, o2))
            tot += I.q[ti] * (1.0 - gamma ** n_alive)
        return tot

    def _alive_c(self, ckey, ti):
        """Alive options for a canonical state (residual tuple) - exact."""
        return tuple(o for o in self.I.types[ti][1] if not any(r & ~o == 0 for r in ckey))

    def _next_c(self, ckey, o):
        if any(r & ~o == 0 for r in ckey):
            return ("UNSAFE",)
        return tuple(sorted({r & ~o for r in ckey}))

    def _mpc(self, ckeys, rem, d):
        key = (ckeys, rem, d)
        if key in self._mcache:
            return self._mcache[key]
        I, gamma = self.I, self.kw.get("gamma", 0.3)
        if rem <= 0:
            v = 0.0
        elif d == 0:
            v = rem * sum(self.q[ti] * (1 - gamma ** len(self._alive_c(ckeys[I.group(a)], ti)))
                          for ti, (a, _) in enumerate(I.types))
        else:
            v = 0.0
            for ti, p in enumerate(self.q):
                if p <= 0:
                    continue
                g = I.group(I.types[ti][0])
                best = self._mpc(ckeys, rem - 1, d - 1)
                for o in self._alive_c(ckeys[g], ti):
                    nk = list(ckeys)
                    nk[g] = self._next_c(ckeys[g], o)
                    best = max(best, 1 + self._mpc(tuple(nk), rem - 1, d - 1))
                v += p * best
        self._mcache[key] = v
        return v

    def _opt_c(self, ckeys, rem, defer):
        key = (ckeys, rem, defer)
        if key in self._ocache:
            return self._ocache[key]
        I = self.I
        if rem <= 0:
            v = 0.0
        else:
            v = 0.0
            for ti, p in enumerate(self.q):
                if p <= 0:
                    continue
                g = I.group(I.types[ti][0])
                al = self._alive_c(ckeys[g], ti)
                best = self._opt_c(ckeys, rem - 1, defer) if (defer or not al) else -1e18
                for o in al:
                    nk = list(ckeys)
                    nk[g] = self._next_c(ckeys[g], o)
                    best = max(best, 1 + self._opt_c(tuple(nk), rem - 1, defer))
                v += p * best
        self._ocache[key] = v
        return v

    # ---------------------------------------------------------------- act
    def act(self, t, state, ti, rng):
        self.calls += 1
        I, kind = self.I, self.kind
        if kind == "A1":
            return super().act(t, state, ti, rng)
        a = I.types[ti][0]
        g = I.group(a)
        K = state[g]
        opts = [o for o in I.types[ti][1] if I.feasible(K, o)]       # same hard constraint, no cache
        if not opts:
            return None
        if kind == "A1_FULL":
            gamma = self.kw.get("gamma", 0.3)
            best, bs = None, -1e18
            for o in opts:
                key = self.full_value(K, o, g, gamma) - 1e-6 * popcount(o & ~K)
                if key > bs:
                    best, bs = o, key
            return best
        if kind == "OCELOT_P":
            B = self.kw.get("budget", math.inf)
            o = min(opts, key=lambda o: (self.charge(K, o), popcount(o & ~K), o))
            c = self.charge(K, o)
            if self.spent[g] + c > B + 1e-12:
                return None
            self.spent[g] += c
            return o
        if kind == "PFLOW_P":
            rho = self.kw.get("rho", 1.01)
            o = min(opts, key=lambda o: (self.risk(K | o), popcount(o & ~K), o))
            return o if self.risk(K | o) < rho else None
        if kind == "DYNCQE_P":
            return max(opts, key=lambda o: (sum(1 for c in self.censors if (K | o) & ~c == 0), -popcount(o & ~K), -o))
        if kind == "OCOST":
            price = [0.0] * I.n
            for w in I.W:
                r = w & ~K
                if r:
                    p = 2.0 ** -(popcount(r) - 1)
                    x = w
                    while x:
                        u = (x & -x).bit_length() - 1
                        price[u] += p
                        x &= x - 1
            cost = lambda o: sum(price[u] for u in range(I.n) if (o & ~K) >> u & 1)
            return min(opts, key=lambda o: (cost(o), popcount(o & ~K), o))
        if kind == "MPC_OPT":
            d = self.kw.get("d", 3)
            ck = self.canon.state_key(state)
            rem = I.H - t - 1
            q = {}
            for o in opts:
                nk = list(ck)
                nk[g] = self._next_c(ck[g], o)
                q[o] = 1 + self._mpc(tuple(nk), rem, d - 1)
            return max(q, key=lambda o: (q[o], -popcount(o)))
        if kind in ("OPT_CANON", "OPT_CANON_SERVE"):
            defer = kind == "OPT_CANON"
            ck = self.canon.state_key(state)
            rem = I.H - t - 1
            q = {}
            for o in opts:
                nk = list(ck)
                nk[g] = self._next_c(ck[g], o)
                q[o] = 1 + self._opt_c(tuple(nk), rem, defer)
            best = max(q, key=lambda o: (q[o], -popcount(o)))
            if defer and q[best] < self._opt_c(ck, rem, defer) - 1e-9:
                return None
            return best
        raise ValueError(kind)

    def reset_episode(self):
        self.spent = [0.0] * self.I.groups
