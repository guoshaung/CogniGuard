"""Shadow-price (LP-dual bid-price) disclosure policies on the CGC4/CGC5 Task A instances.

Fluid (deterministic) LP over the remaining horizon, built from the canonical state (residuals W minus K that can
still be completed by option units; baselines.Canon):

  max  sum_{t,o} y_{t,o}
  s.t. sum_o y_{t,o} <= n_t                         (n_t = h * q_t expected future arrivals of type t)
       y_{t,o} <= n_t * x_{g,u}    for u in o that lies in some residual of group g
       sum_{u in r} x_{g,u} <= |r| - 1               for every residual r of group g   (dual lambda_r >= 0)
       0 <= x <= 1, y >= 0
Only alive options (no residual inside o) get a y variable. Units already known (in K) never appear in residuals,
so they cost nothing, exactly as in the integer problem.

Policies (all serve-only unless *_D; same candidates, same q_hat, same hard constraint as CGC5):
  SP_LP      bid price of an option = sum over its residual units u of sum_{r containing u} lambda_r; release the
             cheapest feasible option (ties: fewer new units, then option id; same tie rule as OCOST).
  SP_DISP    displacement cost LP(state) - LP(state after o), re-solved per candidate; release the cheapest.
  SP_MYOPIC  same as SP_LP but the LP contains only the current request type with n = 1 (no future).
  SP_D       SP_LP + deferral: release the cheapest option iff its bid price <= 1 (the immediate reward), else refuse.
  A1_D       A1 (unchanged choice) + deferral: release A1's option o* iff rem * (rate_g(K) - rate_g(K u o*)) <= 1,
             rate_g = sum_{t of group g} q_t (1 - gamma^#alive) (A1's own value rate), rem = H - t - 1.
Dual degeneracy: at degenerate optima the residual-row duals are not unique (any value between the right and left
derivative); HiGHS returns an arbitrary vertex. We tighten every residual row by EPS, so the returned dual is the
left derivative = marginal loss when one unit of a residual's capacity is consumed (the bid-price meaning).
The LP horizon is h = rem (remaining arrivals after the current one); no tuned parameter.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from experiments.cogniguard_cgc4.a_engine import Policy, popcount
from experiments.cogniguard_cgc5.baselines import Baseline, Canon


EPS = 1e-5      # residual rows are tightened by EPS so the dual is the LEFT derivative (cost of consuming
                # capacity); without it degenerate vertices return arbitrary duals (test_sp, PREREG)


def bits(x):
    while x:
        b = x & -x
        yield b.bit_length() - 1
        x ^= b


def alive_c(ckey, opts):
    return [o for o in opts if not any(r & ~o == 0 for r in ckey)]


def solve_lp(I, ckeys, nvec):
    """ckeys: canonical residual tuple per group; nvec: expected arrivals per type (0 = absent).
    Returns (value, {(g, r): lambda}, {(g, u): unit price}, stats)."""
    xs, ys = {}, []
    rows, cols, vals, b = [], [], [], []
    nr = 0

    def xv(g, u):
        k = (g, u)
        if k not in xs:
            xs[k] = len(xs)
        return xs[k]

    res_units = [set(u for r in ck for u in bits(r)) for ck in ckeys]
    ylink = []
    for t, (a, opts) in enumerate(I.types):
        n = nvec[t]
        if n <= 0:
            continue
        g = I.group(a)
        al = alive_c(ckeys[g], opts)
        if not al:
            continue
        ids = []
        for o in al:
            ids.append(len(ys))
            ys.append((t, o))
            ylink.append([(u, g, n) for u in bits(o) if u in res_units[g]])
        for j in ids:
            rows.append(nr); cols.append(("y", j)); vals.append(1.0)
        b.append(n); nr += 1
    for j, links in enumerate(ylink):
        for u, g, n in links:
            rows += [nr, nr]; cols += [("y", j), ("x", xv(g, u))]; vals += [1.0, -n]
            b.append(0.0); nr += 1
    lam_rows = []
    for g, ck in enumerate(ckeys):
        for r in ck:
            if popcount(r) < 2:
                continue                 # single-unit residual: its unit is in no alive option, row is inert
            for u in bits(r):
                rows.append(nr); cols.append(("x", xv(g, u))); vals.append(1.0)
            b.append(popcount(r) - 1.0 - EPS)
            lam_rows.append((nr, g, r)); nr += 1
    if not ys:
        return 0.0, {}, {}, {"ny": 0, "nres": len(lam_rows)}
    ny, nx = len(ys), len(xs)
    ci = [c[1] if c[0] == "y" else ny + c[1] for c in cols]
    A = coo_matrix((vals, (rows, ci)), shape=(nr, ny + nx)).tocsr()
    c = np.concatenate([-np.ones(ny), np.zeros(nx)])
    bounds = [(0, None)] * ny + [(0, 1)] * nx
    res = linprog(c, A_ub=A, b_ub=np.array(b), bounds=bounds, method="highs")
    if res.status != 0:
        raise RuntimeError(res.message)
    marg = -res.ineqlin.marginals
    lam = {(g, r): max(0.0, float(marg[i])) for i, g, r in lam_rows}
    price = {}
    for (g, r), l in lam.items():
        if l > 0:
            for u in bits(r):
                price[(g, u)] = price.get((g, u), 0.0) + l
    return float(-res.fun), lam, price, {"ny": ny, "nres": len(lam_rows)}


class SPPolicy(Baseline):
    def __init__(self, kind, inst, q_hat, **kw):
        super().__init__("A1_FULL", inst, q_hat, **kw)        # Baseline init only (canon, caches); act overridden
        self.kind = kind
        self._lp = {}
        self.a1 = Policy("A1", inst, q_hat, gamma=kw.get("gamma", 0.3)) if kind == "A1_D" else None

    def lp(self, ckeys, nvec_key, nvec):
        k = (ckeys, nvec_key)
        if k not in self._lp:
            self._lp[k] = solve_lp(self.I, ckeys, nvec)
        return self._lp[k]

    def option_price(self, price, g, ck, o):
        ru = set(u for r in ck for u in bits(r))
        return sum(price.get((g, u), 0.0) for u in bits(o) if u in ru)

    def act(self, t, state, ti, rng):
        self.calls += 1
        I, kind = self.I, self.kind
        a = I.types[ti][0]
        g = I.group(a)
        K = state[g]
        opts = [o for o in I.types[ti][1] if I.feasible(K, o)]
        if not opts:
            return None
        rem = I.H - t - 1
        if kind == "A1_D":
            o = self.a1.act(t, state, ti, rng)
            gamma = self.kw.get("gamma", 0.3)
            cur, _ = self.a1.eng.value_after(K, 0, g, gamma)
            aft, _ = self.a1.eng.value_after(K, o, g, gamma)
            return o if rem * (cur - aft) <= 1.0 + 1e-12 else None
        ck = self.canon.state_key(state)
        tie = lambda o: (popcount(o & ~K), o)
        if kind in ("SP_LP", "SP_D", "SP_MYOPIC"):
            if kind == "SP_MYOPIC":
                nvec = [1.0 if j == ti else 0.0 for j in range(len(self.q))]
                _, _, price, _ = self.lp(ck, ("my", ti), nvec)
            else:
                nvec = [rem * p for p in self.q]
                _, _, price, _ = self.lp(ck, ("h", rem), nvec)
            pr = {o: self.option_price(price, g, ck[g], o) for o in opts}
            best = min(opts, key=lambda o: (round(pr[o], 9),) + tie(o))
            if kind == "SP_D" and pr[best] > 1.0 + 1e-9:
                return None
            return best
        if kind == "SP_DISP":
            nvec = [rem * p for p in self.q]
            v0 = self.lp(ck, ("h", rem), nvec)[0]
            d = {}
            for o in opts:
                nk = list(ck)
                nk[g] = self._next_c(ck[g], o)
                d[o] = v0 - self.lp(tuple(nk), ("h", rem), nvec)[0]
            return min(opts, key=lambda o: (round(d[o], 9),) + tie(o))
        raise ValueError(kind)
