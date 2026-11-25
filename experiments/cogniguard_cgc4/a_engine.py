"""Task A: look-ahead disclosure control on a witness hypergraph.

Instance: units 0..n-1, a witness family W (bitmasks; formal CA-PD derivation sets, Lemma 1), N agents and
a safety grouping: pooled (k = N, one knowledge set) or per-agent (k = 1, one set per agent). A legitimate
task type is (agent, options); any one option (a unit set) serves it. Hard safety: no group's knowledge
ever contains a witness. Tasks arrive i.i.d. from q for H steps.

Opportunity loss (incremental). For a group state K and a candidate option o, an alive option o' of a
future task is killed iff some witness W touching o has residual r = W minus (K u o) with r a subset of o'.
Only witnesses touching o are scanned (unit -> witness index), and residuals larger than the largest option
are skipped, so the update costs O(sum_{u in o} deg(u) * options-per-residual) instead of re-checking
every option against every witness.

Policies (same information: q_hat, H, current state):
  CAPD_FIRST              immediate CA-PD
  A0                      max sum_t q_t 1[t still servable]                  (CGC3 CONFLICT)
  A1(g)                   max sum_t q_t (1 - g^{#alive options of t})         soft opportunity value
  A1_DRO(g, r)            A1 minus (r/2)(max_t - min_t) over task types: worst case in an L1 ball of q
  MPC(d)                  expectimax depth d over q_hat, leaf = remaining steps x A1 value rate
  BEAM(w, d, S)           S sampled futures (common across actions), beam width w, depth d, leaf A1
  SAA(S, h)               sample-average hindsight planning, exact DFS per scenario, depth h, leaf A1
  OPT                     exact DP over (t, state) under q_hat (small pooled instances only)
"""

from __future__ import annotations

import math
import random
import time
from functools import lru_cache


def popcount(x):
    return bin(x).count("1")


class Instance:
    def __init__(self, n, witnesses, types, q, H, N=1, pooled=True, K0=None, meta=None):
        self.n, self.W, self.types, self.q, self.H, self.N, self.pooled = n, list(witnesses), list(types), list(q), H, N, pooled
        self.meta = meta or {}
        self.by_unit = [[] for _ in range(n)]
        for w in self.W:
            for u in range(n):
                if w >> u & 1:
                    self.by_unit[u].append(w)
        self.maxopt = max(popcount(o) for _, opts in self.types for o in opts)
        self.groups = 1 if pooled else N
        self.K0 = tuple(K0) if K0 is not None else tuple([0] * self.groups)
        self.types_of_group = [[i for i, (a, _) in enumerate(self.types) if self.group(a) == g] for g in range(self.groups)]

    def group(self, agent):
        return 0 if self.pooled else agent

    def feasible(self, K, o):
        Ko = K | o
        x = o & ~K
        while x:
            u = (x & -x).bit_length() - 1
            for w in self.by_unit[u]:
                if w & ~Ko == 0:
                    return False
            x &= x - 1
        return True


class Engine:
    """Caches alive-option sets per (group knowledge, type) and computes opportunity values incrementally."""

    def __init__(self, inst: Instance):
        self.I = inst
        self.alive_cache = {}
        self.evals = 0

    def alive(self, K, ti):
        key = (K, ti)
        if key not in self.alive_cache:
            self.alive_cache[key] = tuple(o for o in self.I.types[ti][1] if self.I.feasible(K, o))
        return self.alive_cache[key]

    def killed_after(self, K, o, ti):
        """Alive options of type ti that disclosing o would kill (incremental, witness-local)."""
        I = self.I
        Ko = K | o
        res = set()
        x = o & ~K
        while x:
            u = (x & -x).bit_length() - 1
            for w in I.by_unit[u]:
                r = w & ~Ko
                if r and popcount(r) <= I.maxopt:
                    res.add(r)
            x &= x - 1
        al = self.alive(K, ti)
        if not res:
            return 0
        return sum(1 for o2 in al if any(r & ~o2 == 0 for r in res))

    def value_after(self, K, o, g, gamma, mode="soft"):
        """sum over task types of the same group of q_t * phi(#alive after o)."""
        self.evals += 1
        I = self.I
        tot, vals = 0.0, []
        for ti in I.types_of_group[g]:
            n_alive = len(self.alive(K, ti)) - self.killed_after(K, o, ti) if o else len(self.alive(K, ti))
            v = (1.0 if n_alive > 0 else 0.0) if mode == "hard" else 1.0 - gamma ** n_alive
            tot += I.q[ti] * v
            vals.append(v)
        return tot, vals


def leaf_rate(eng, state, q, gamma):
    I = eng.I
    s = 0.0
    for ti, (a, _) in enumerate(I.types):
        s += q[ti] * (1.0 - gamma ** len(eng.alive(state[I.group(a)], ti)))
    return s


class Policy:
    def __init__(self, kind, inst, q_hat, **kw):
        self.kind, self.I, self.q, self.kw = kind, inst, list(q_hat), kw
        self.eng = Engine(inst)
        self.calls = 0
        if kind in ("OPT", "OPT_SERVE"):
            self._opt = lru_cache(maxsize=None)(self._opt_raw)
            if kind == "OPT":
                self.kw["defer"] = True

    # ---------------------------------------------------------------- helpers
    def _step(self, state, ti, o):
        a = self.I.types[ti][0]
        g = self.I.group(a)
        st = list(state)
        st[g] |= o
        return tuple(st)

    def _opts(self, state, ti):
        a = self.I.types[ti][0]
        return self.eng.alive(state[self.I.group(a)], ti)

    def _leaf(self, state, steps):
        return steps * leaf_rate(self.eng, state, self.q, self.kw.get("gamma", 0.5))

    # ---------------------------------------------------------------- planners
    def _emax(self, t, state, d):
        if t >= self.I.H:
            return 0.0
        if d == 0:
            return self._leaf(state, self.I.H - t)
        v = 0.0
        for ti, p in enumerate(self.q):
            if p <= 0:
                continue
            best = self._emax(t + 1, state, d - 1)
            for o in self._opts(state, ti):
                best = max(best, 1 + self._emax(t + 1, self._step(state, ti, o), d - 1))
            v += p * best
        return v

    def _opt_raw(self, t, state):
        if t >= self.I.H:
            return 0.0
        v = 0.0
        for ti, p in enumerate(self.q):
            if p <= 0:
                continue
            best = self._opt(t + 1, state)
            for o in self._opts(state, ti):
                best = max(best, 1 + self._opt(t + 1, self._step(state, ti, o)))
            v += p * best
        return v

    def _scenarios(self, t, rng, S, h):
        L = min(h, self.I.H - t - 1)
        return [[rng.choices(range(len(self.q)), weights=self.q)[0] for _ in range(L)] for _ in range(S)]

    def _dfs(self, state, seq, i, beam=None):
        if i >= len(seq):
            return 0.0
        ti = seq[i]
        opts = self._opts(state, ti)
        if beam is None:
            best = self._dfs(state, seq, i + 1)
            for o in opts:
                best = max(best, 1 + self._dfs(self._step(state, ti, o), seq, i + 1))
            return best
        return None

    def _beam(self, state, seq, w):
        frontier = [(0.0, state)]
        for ti in seq:
            nxt = []
            for val, st in frontier:
                nxt.append((val, st))
                for o in self._opts(st, ti):
                    nxt.append((val + 1, self._step(st, ti, o)))
            gamma = self.kw.get("gamma", 0.5)
            nxt.sort(key=lambda x: -(x[0] + 1e-3 * leaf_rate(self.eng, x[1], self.q, gamma)))
            frontier = nxt[:w]
        return frontier

    # ---------------------------------------------------------------- act
    def act(self, t, state, ti, rng):
        """Return chosen option or None (refuse)."""
        self.calls += 1
        I, kind = self.I, self.kind
        opts = self._opts(state, ti)
        if not opts:
            return None
        if kind == "CAPD_FIRST":
            return opts[0]
        g = I.group(I.types[ti][0])
        K = state[g]
        if kind in ("A0", "A1", "A1_DRO"):
            gamma = self.kw.get("gamma", 0.5)
            mode = "hard" if kind == "A0" else "soft"
            best, bs = None, -1e18
            for o in opts:
                v, vals = self.eng.value_after(K, o, g, gamma, mode)
                if kind == "A1_DRO":
                    r = self.kw.get("r", 0.2)
                    v -= (r / 2) * (max(vals) - min(vals)) if vals else 0.0
                key = v - 1e-6 * popcount(o & ~K)
                if key > bs:
                    best, bs = o, key
            return best
        rem = I.H - t - 1
        if kind == "OPT_SERVE":
            kind = "OPT"
        if kind == "SAA_DEFER":
            kind = "SAA"
        if kind == "MPC":
            d = self.kw.get("d", 2)
            q = {o: 1 + self._emax(t + 1, self._step(state, ti, o), d - 1) for o in opts}
            ref = self._emax(t + 1, state, d - 1)
        elif kind == "OPT":
            q = {o: 1 + self._opt(t + 1, self._step(state, ti, o)) for o in opts}
            ref = self._opt(t + 1, state)
        elif kind in ("SAA", "BEAM"):
            S, h = self.kw.get("S", 8), self.kw.get("h", 3)
            scen = self._scenarios(t, rng, S, h)

            def val(st):
                tot = 0.0
                for seq in scen:
                    if kind == "SAA":
                        tot += self._dfs(st, seq, 0)
                        end = st
                    else:
                        fr = self._beam(st, seq, self.kw.get("w", 3))
                        best = max(fr, key=lambda x: x[0])
                        tot += best[0]
                return tot / len(scen) + self._leaf(st, max(0, rem - h))
            q = {o: 1 + val(self._step(state, ti, o)) for o in opts}
            ref = val(state)
        else:
            raise ValueError(kind)
        best = max(q, key=lambda o: (q[o], -popcount(o)))
        if not self.kw.get("defer", False):          # default: serve whenever possible (no deferral)
            return best
        return best if q[best] >= ref - 1e-9 else None


def run_episode(inst, policy, seq, seed):
    rng = random.Random(seed)
    state = inst.K0
    served = 0
    t0 = time.perf_counter()
    for t, ti in enumerate(seq):
        o = policy.act(t, state, ti, rng)
        if o is not None:
            g = inst.group(inst.types[ti][0])
            st = list(state)
            st[g] |= o
            state = tuple(st)
            served += 1
    return served, time.perf_counter() - t0, state


def check_safe(inst, state):
    return all(not any(w & ~K == 0 for w in inst.W) for K in state)
