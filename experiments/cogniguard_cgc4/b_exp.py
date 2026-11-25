"""Task B: joint-channel governance when the attacker's view is unknown, knowledge is correlated, several
agents collude, and more governance behaviour is observable. Exact LPs on KSL structures.

The governor knows the true world x* (owner side) but not the attacker's view K0. Its belief is a
distribution over candidate views {K0^j}. A truthful mechanism M(o | x) is defined on the union U of the
attacker cells c_j(x*) (the worlds some candidate attacker cannot rule out). SAFETY IS PER OUTPUT: for the
true view j*, every output o with positive probability must satisfy max_s P(S=s | c_j*(x*), o) <= tau.
Averages (mutual information) are reported only next to the per-output maximum, never instead of it.

Mechanisms
  ORACLE_LP     knows the true view (CGC3 Oracle)          ROBUST_LP    constraints for every candidate view
  CHANCE_LP(e)  drop least-likely views up to mass e       MAP_LP       constraints for the MAP view only
  SIM_ROBUST    action independent of x, safe for all views (simulatable auditing)
  STEP_QIF      release iff realized V1 after release <= tau under the MAP view, else refuse (per-step QIF)
  CAPD_F        formal CA-PD under the MAP view (= STEP_QIF with tau at full determination)
Beliefs: 'product' (independent unit inclusion) and 'corr' (units come in bundles); methods may be built on the
product approximation while the truth is correlated. Multi-agent: k = 1 (requester only) vs k = 2 (requester
+ colluder) constraints. Timing: a pipeline that answers fast when the realized risk is low adds an
observable latency label. Compression: exact lumping of worlds with identical (s, f_u, cell ids) and exact
pruning of views whose constraint cannot bind.
"""

from __future__ import annotations

import gzip
import itertools
import json
import math
import random
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

from experiments.cogniguard_cgc3.common import NAMES, table

OUT = Path(__file__).parent / "results"
BETA = 0.5
TOL = 1e-7


def util_of(o):
    return 1.0 if o[0] in ("R", "Rf", "Rs") else BETA if o[0] == "D" else 0.0


def outputs(T, u, xs):
    st = T.st
    vals = sorted({st.units[T.units[u]](st.worlds[x]) for x in xs}, key=repr)
    coarse = {v: i % 2 for i, v in enumerate(vals)}
    outs = [("R", v) for v in vals] + [("D", 0), ("D", 1), ("X",)]
    allowed = {x: {("R", st.units[T.units[u]](st.worlds[x])), ("D", coarse[st.units[T.units[u]](st.worlds[x])]), ("X",)} for x in xs}
    return outs, allowed


def cell(T, K, x):
    return [y for y in range(len(T.prior)) if T.gid[K, y] == T.gid[K, x]]


def cell_prior_V1(T, cell_ws):
    ps = np.zeros(len(T.svals))
    for y in cell_ws:
        ps[T.sidx[y]] += T.prior[y]
    return float(ps.max() / ps.sum())


def thr(T, cell_ws, tau):
    """A mechanism cannot undo what the attacker already knows: the bound is max(tau, prior V1 in the cell)."""
    return max(tau, cell_prior_V1(T, cell_ws))


def excess(T, M, cell_ws, outs, tau):
    return posterior_max(T, M, cell_ws, outs) - thr(T, cell_ws, tau)


def posterior_max(T, M, cell_ws, outs):
    """Per-output max posterior vulnerability inside one attacker cell (worlds cell_ws)."""
    pr = np.array([T.prior[x] for x in cell_ws])
    pr = pr / pr.sum()
    worst = 0.0
    for o in outs:
        w = np.zeros(len(T.svals))
        for x, p in zip(cell_ws, pr):
            w[T.sidx[x]] += p * M.get(x, {}).get(o, 0.0)
        if w.sum() > 1e-12:
            worst = max(worst, w.max() / w.sum())
    return worst


def mutual_info(T, M, cell_ws, outs):
    pr = np.array([T.prior[x] for x in cell_ws])
    pr = pr / pr.sum()
    J = {o: np.zeros(len(T.svals)) for o in outs}
    for x, p in zip(cell_ws, pr):
        for o in outs:
            J[o][T.sidx[x]] += p * M.get(x, {}).get(o, 0.0)
    Ps = sum(J.values())
    return float(sum(v[s] * math.log2(v[s] / (v.sum() * Ps[s])) for v in J.values() for s in range(len(Ps)) if v[s] > 1e-15))


def solve_lp(T, xs, outs, allowed, cells, tau, x_star, lump=False, prune_u=None):
    """Maximize the true world's... no: maximize expected utility over the union prior (the mechanism must be
    fixed before x* is revealed to anyone else, and utility at x* alone would let the LP release only at x*).
    Constraints: per-output posterior <= tau inside every given cell."""
    t0 = time.perf_counter()
    # exact lumping: worlds with the same secret, same allowed outputs and same cell membership pattern
    groups = {}
    for x in xs:
        key = (int(T.sidx[x]), tuple(sorted(allowed[x])), tuple(any(x == y for y in c) for c in cells)) if lump else (x,)
        groups.setdefault(key, []).append(x)
    reps = list(groups.values())
    if prune_u is not None:      # exact pruning: a cell whose worst realized V1 after full release <= tau never binds
        cells = [c for c in cells if max(T.V1[prune_u, y] for y in c) > tau + 1e-12]
    idx = {}
    for gi, g in enumerate(reps):
        for o in outs:
            idx[(gi, o)] = len(idx)
    n = len(idx)
    c = np.zeros(n)
    bounds = [(0, 0)] * n
    wsum = sum(T.prior[x] for x in xs)
    for gi, g in enumerate(reps):
        pg = sum(T.prior[x] for x in g) / wsum
        for o in outs:
            if o in allowed[g[0]]:
                bounds[idx[(gi, o)]] = (0, 1)
            c[idx[(gi, o)]] = -pg * util_of(o)
    A_eq = []
    for gi in range(len(reps)):
        r = np.zeros(n)
        for o in outs:
            r[idx[(gi, o)]] = 1
        A_eq.append(r)
    A_ub = []
    gid_of = {x: gi for gi, g in enumerate(reps) for x in g}
    n_cons = 0
    for cw in cells:
        svals = sorted({int(T.sidx[x]) for x in cw})
        tc = thr(T, cw, tau)
        for o in outs:
            for s in svals:
                r = np.zeros(n)
                for x in cw:
                    r[idx[(gid_of[x], o)]] += T.prior[x] * ((1 if T.sidx[x] == s else 0) - tc)
                A_ub.append(r)
                n_cons += 1
    res = linprog(c, A_ub=np.array(A_ub) if A_ub else None, b_ub=np.zeros(len(A_ub)) if A_ub else None,
                  A_eq=np.array(A_eq), b_eq=np.ones(len(A_eq)), bounds=bounds, method="highs")
    if res.status != 0:
        return None, {"vars": n, "cons": n_cons, "sec": time.perf_counter() - t0}
    M = {}
    for gi, g in enumerate(reps):
        for x in g:
            M[x] = {o: max(0.0, res.x[idx[(gi, o)]]) for o in outs}
    return M, {"vars": n, "cons": n_cons, "sec": time.perf_counter() - t0}


def belief(T, rng, kind):
    """Candidate attacker views with probabilities. 2-4 uncertain relevant units on top of a base view."""
    m = len(T.units)
    rel = [j for j in range(m) if T.relevant >> j & 1]
    base = 0
    for j in rng.sample(rel, rng.randrange(0, max(1, len(rel) - 2))):
        base |= 1 << j
    unc = [j for j in rel if not base >> j & 1]
    rng.shuffle(unc)
    unc = unc[: rng.randint(2, min(4, len(unc)))] if len(unc) >= 2 else unc
    p = {j: rng.choice([0.2, 0.4, 0.6, 0.8]) for j in unc}
    views = {}
    if kind == "product":
        for bits in itertools.product((0, 1), repeat=len(unc)):
            pr = 1.0
            v = base
            for b, j in zip(bits, unc):
                pr *= p[j] if b else 1 - p[j]
                v |= (1 << j) if b else 0
            views[v] = views.get(v, 0) + pr
    else:   # bundles of two: both or neither, with the same marginals
        pairs = [unc[i:i + 2] for i in range(0, len(unc), 2)]
        for bits in itertools.product((0, 1), repeat=len(pairs)):
            pr = 1.0
            v = base
            for b, pair in zip(bits, pairs):
                pp = float(np.mean([p[j] for j in pair]))
                pr *= pp if b else 1 - pp
                if b:
                    for j in pair:
                        v |= 1 << j
            views[v] = views.get(v, 0) + pr
    return base, unc, p, views


def product_of(views, unc, base):
    marg = {j: sum(pr for v, pr in views.items() if v >> j & 1) for j in unc}
    out = {}
    for bits in itertools.product((0, 1), repeat=len(unc)):
        pr = 1.0
        v = base
        for b, j in zip(bits, unc):
            pr *= marg[j] if b else 1 - marg[j]
            v |= (1 << j) if b else 0
        out[v] = out.get(v, 0) + pr
    return out


def run(args):
    name, seed, tau, bkind = args
    T = table(name)
    rng = random.Random(seed)
    x_star = rng.choices(range(len(T.prior)), weights=T.prior)[0]
    base, unc, p, views_true = belief(T, rng, bkind)
    views_true = {v: pr for v, pr in views_true.items() if not T.cov[v]}
    if len(views_true) < 2:
        return None
    z = sum(views_true.values())
    views_true = {v: pr / z for v, pr in views_true.items()}
    rel = [j for j in range(len(T.units)) if T.relevant >> j & 1 and not any(v >> j & 1 for v in views_true)]
    if not rel:
        return None
    u = rng.choice(rel)
    true_view = rng.choices(list(views_true), weights=list(views_true.values()))[0]
    # the governor's model: exact belief, or the product approximation when the truth is correlated
    models = {"exact": views_true}
    if bkind == "corr":
        models["product_approx"] = product_of(views_true, unc, base)
    out = {"name": name, "seed": seed, "tau": tau, "belief": bkind, "n_views": len(views_true), "res": {}}
    for mname, views in models.items():
        cells_all = {v: cell(T, v, x_star) for v in set(views) | {true_view}}
        U = sorted(set().union(*[set(cells_all[v]) for v in views]) | set(cells_all[true_view]))
        # skip instances whose prior in the true cell is already above tau (nothing to protect)
        ps = np.zeros(len(T.svals))
        for y in cells_all[true_view]:
            ps[T.sidx[y]] += T.prior[y]
        if ps.max() / ps.sum() > tau - 1e-9:
            return None
        outs, allowed = outputs(T, u, U)
        Ku = lambda v: v | (1 << u)
        mapv = max(views, key=views.get)
        mechs, stats = {}, {}
        mechs["ORACLE_LP"], stats["ORACLE_LP"] = solve_lp(T, U, outs, allowed, [cells_all[true_view]], tau, x_star)
        mechs["ROBUST_LP"], stats["ROBUST_LP"] = solve_lp(T, U, outs, allowed, [cells_all[v] for v in views], tau, x_star)
        for eps in (0.05, 0.2):
            keep, dropped = [], 0.0
            for v in sorted(views, key=views.get):
                if dropped + views[v] <= eps:
                    dropped += views[v]
                else:
                    keep.append(v)
            mechs[f"CHANCE_LP_{eps}"], stats[f"CHANCE_LP_{eps}"] = solve_lp(T, U, outs, allowed, [cells_all[v] for v in keep], tau, x_star)
        mechs["MAP_LP"], stats["MAP_LP"] = solve_lp(T, U, outs, allowed, [cells_all[mapv]], tau, x_star)
        # compression variants of the robust LP (must reproduce the same optimum)
        mL, sL = solve_lp(T, U, outs, allowed, [cells_all[v] for v in views], tau, x_star, lump=True)
        mP, sP = solve_lp(T, U, outs, allowed, [cells_all[v] for v in views], tau, x_star, lump=True, prune_u=None)
        # rule-based
        def rule(f):
            M = {}
            for x in U:
                rel_o = [o for o in allowed[x] if o[0] == "R"][0]
                M[x] = {rel_o: 1.0} if f(x) else {("X",): 1.0}
            return M
        safe_all = all(T.V1[Ku(v), y] <= tau + 1e-12 for v in views for y in cells_all[v])
        mechs["SIM_ROBUST"] = rule(lambda x: safe_all)
        mechs["STEP_QIF"] = rule(lambda x: T.V1[Ku(mapv), x] <= tau + 1e-12)
        mechs["CAPD_F"] = rule(lambda x: T.V1[Ku(mapv), x] < 1 - 1e-12)
        # timing pipeline on top of the robust LP: releases are labelled fast if realized risk is low
        if mechs["ROBUST_LP"] is not None:
            Mt = {}
            for x, d in mechs["ROBUST_LP"].items():
                Mt[x] = {}
                for o, q in d.items():
                    if o[0] == "R":
                        lab = "Rf" if T.V1[Ku(mapv), x] <= tau / 2 + 1e-12 else "Rs"
                        Mt[x][(lab,) + o[1:]] = Mt[x].get((lab,) + o[1:], 0) + q
                    else:
                        Mt[x][o] = Mt[x].get(o, 0) + q
            mechs["ROBUST_LP+timing"] = Mt
        outs_t = outs + [("Rf",) + o[1:] for o in outs if o[0] == "R"] + [("Rs",) + o[1:] for o in outs if o[0] == "R"]
        res = {}
        for k, M in mechs.items():
            if M is None:
                res[k] = None
                continue
            o_used = outs_t if k.endswith("timing") else outs
            true_worst = posterior_max(T, M, cells_all[true_view], o_used)
            true_excess = excess(T, M, cells_all[true_view], o_used, tau)
            # probability (under the TRUE belief) that the realized attacker view sees a violating output
            pviol = sum(pr for v, pr in views_true.items()
                        if excess(T, M, cell(T, v, x_star), o_used, tau) > TOL)
            res[k] = {"utility_at_xstar": float(sum(q * util_of(o) for o, q in M[x_star].items())),
                      "utility_U": float(sum(T.prior[x] * sum(q * util_of(o) for o, q in M[x].items()) for x in U) /
                                         sum(T.prior[x] for x in U)),
                      "true_view_worst_posterior": true_worst, "true_view_excess": true_excess,
                      "violates_true_view": true_excess > TOL,
                      "p_violation_under_true_belief": pviol,
                      "mi_true_view": mutual_info(T, M, cells_all[true_view], o_used),
                      **({"lp": stats[k]} if k in stats else {})}
        lumped_same = (mL is not None and mechs["ROBUST_LP"] is not None and
                       abs(sum(T.prior[x] * sum(q * util_of(o) for o, q in mL[x].items()) for x in U) -
                           sum(T.prior[x] * sum(q * util_of(o) for o, q in mechs["ROBUST_LP"][x].items()) for x in U)) < 1e-6)
        res["compression"] = {"vars_full": stats["ROBUST_LP"]["vars"], "vars_lumped": sL["vars"],
                              "sec_full": stats["ROBUST_LP"]["sec"], "sec_lumped": sL["sec"], "same_optimum": lumped_same,
                              "cells": len(views), "U": len(U)}
        out["res"][mname] = res
    return out


def multi_agent(args):
    """k = 1 (requester's view) vs k = 2 (requester + colluder): both views known; does the k = 1 LP leak to the
    coalition, and what does protecting the coalition cost?"""
    name, seed, tau = args
    T = table(name)
    rng = random.Random(seed)
    m = len(T.units)
    rel = [j for j in range(m) if T.relevant >> j & 1]
    x_star = rng.choices(range(len(T.prior)), weights=T.prior)[0]
    KA = sum(1 << j for j in rng.sample(rel, rng.randrange(0, len(rel) - 1)))
    KB = sum(1 << j for j in rng.sample(rel, rng.randrange(0, len(rel) - 1)))
    if T.cov[KA | KB]:
        return None
    cand = [j for j in rel if not (KA | KB) >> j & 1]
    if not cand:
        return None
    u = rng.choice(cand)
    cA, cAB = cell(T, KA, x_star), cell(T, KA | KB, x_star)
    U = sorted(set(cA))
    outs, allowed = outputs(T, u, U)
    M1, s1 = solve_lp(T, U, outs, allowed, [cA], tau, x_star)
    M2, s2 = solve_lp(T, U, outs, allowed, [cA, cAB], tau, x_star)
    if M1 is None or M2 is None:
        return None
    u_of = lambda M: float(sum(T.prior[x] * sum(q * util_of(o) for o, q in M[x].items()) for x in U) / sum(T.prior[x] for x in U))
    return {"name": name, "seed": seed, "tau": tau,
            "k1": {"utility": u_of(M1), "coalition_excess": excess(T, M1, cAB, outs, tau), "own_excess": excess(T, M1, cA, outs, tau)},
            "k2": {"utility": u_of(M2), "coalition_excess": excess(T, M2, cAB, outs, tau), "own_excess": excess(T, M2, cA, outs, tau)}}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    names = [n for n in NAMES if n != "serial"]          # serial: 480 worlds, LP too large for the robust union
    test = [(n, 100000 + s, t, b) for n in names for s in range(30) for t in (0.34, 0.5) for b in ("product", "corr")]
    ma = [(n, 100000 + s, t) for n in names for s in range(40) for t in (0.34, 0.5)]
    with Pool(9) as pool:
        r1 = [r for r in pool.imap_unordered(run, test, chunksize=2) if r]
        r2 = [r for r in pool.imap_unordered(multi_agent, ma, chunksize=4) if r]
    with gzip.open(OUT / "b_raw.json.gz", "wt") as h:
        json.dump({"unknown_view": r1, "multi_agent": r2}, h, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(len(r1), len(r2))


if __name__ == "__main__":
    main()
