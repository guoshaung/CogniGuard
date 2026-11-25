"""Task AB: one small sequential model with both long-run task reachability (A) and joint-channel safety (B).

The attacker starts with a known view K0 (cell C0 around x*) and knows every mechanism used. After each step
it updates its posterior pi_t over worlds from the output it saw; the governor can compute the same pi_t.
SAME SAFETY RULE FOR ALL ARMS: every emitted output o must satisfy max_s P(S=s | history, o) <= thr_t with
thr_t = max(tau, V1(pi_t)) (a mechanism cannot undo what is already known). Same information (pi_t, q, H),
no verification budget, same tau. Option choices use only pi_t-level quantities (never x*), so the choice
itself is not a side channel.

Arms
  CAPD        first option; release iff releasing is safe for EVERY world in the support (simulatable),
              else refuse
  CAPD+A      same release rule; choose the option maximizing expected future reachability
  CAPD+B      first option; per-step joint-channel LP (release / degrade / refuse) on pi_t
  CAPD+A+B    LP per option; choose the option maximizing expected LP utility + expected future reachability
Reference (not guaranteed): CAPD_F = formal CA-PD on realized values (refusal depends on x*).
Future reachability (same proxy for A and A+B): sum_t' q_t' 1[some option of t' can be released or degraded
safely for every world of the expected next posterior].
"""

from __future__ import annotations

import gzip
import json
import random
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

from experiments.cogniguard_cgc3.common import NAMES, table

OUT = Path(__file__).parent / "results"
H = 5
BETA = 0.5


def val(T, u, x):
    return T.st.units[T.units[u]](T.st.worlds[x])


def coarse_map(T, u, xs):
    vals = sorted({val(T, u, x) for x in xs}, key=repr)
    return {v: i % 2 for i, v in enumerate(vals)}


def vmax(T, pi):
    ps = np.zeros(len(T.svals))
    for x, p in pi.items():
        ps[T.sidx[x]] += p
    return float(ps.max() / ps.sum())


def split(T, pi, key):
    groups = {}
    for x, p in pi.items():
        groups.setdefault(key(x), {})[x] = p
    return groups


def sim_ok(T, pi, u, thr, degrade=False):
    """Releasing (or degrading) u is safe whatever the true world in the support is."""
    cm = coarse_map(T, u, pi)
    key = (lambda x: cm[val(T, u, x)]) if degrade else (lambda x: val(T, u, x))
    return all(vmax(T, g) <= thr + 1e-9 for g in split(T, pi, key).values())


def lp(T, pi, u, thr):
    xs = list(pi)
    cm = coarse_map(T, u, xs)
    vals = sorted({val(T, u, x) for x in xs}, key=repr)
    outs = [("R", v) for v in vals] + [("D", 0), ("D", 1), ("X",)]
    allowed = {x: {("R", val(T, u, x)), ("D", cm[val(T, u, x)]), ("X",)} for x in xs}
    idx = {(x, o): i for i, (x, o) in enumerate((x, o) for x in xs for o in outs)}
    n = len(idx)
    z = sum(pi.values())
    c = np.zeros(n)
    bounds = [(0, 0)] * n
    for (x, o), i in idx.items():
        if o in allowed[x]:
            bounds[i] = (0, 1)
        c[i] = -(pi[x] / z) * (1.0 if o[0] == "R" else BETA if o[0] == "D" else 0.0)
    A_eq = []
    for x in xs:
        r = np.zeros(n)
        for o in outs:
            r[idx[(x, o)]] = 1
        A_eq.append(r)
    A_ub = []
    for o in outs:
        for s in sorted({int(T.sidx[x]) for x in xs}):
            r = np.zeros(n)
            for x in xs:
                r[idx[(x, o)]] = pi[x] * ((1 if T.sidx[x] == s else 0) - thr)
            A_ub.append(r)
    res = linprog(c, A_ub=np.array(A_ub), b_ub=np.zeros(len(A_ub)), A_eq=np.array(A_eq), b_eq=np.ones(len(xs)),
                  bounds=bounds, method="highs")
    if res.status != 0:
        return None, None
    M = {x: {o: max(0.0, res.x[idx[(x, o)]]) for o in outs} for x in xs}
    return M, -res.fun


def reach(T, pi, types, q, thr):
    return sum(p for p, opts in zip(q, types) if any(sim_ok(T, pi, u, thr) or sim_ok(T, pi, u, thr, True) for u in opts))


def expected_reach_after_release(T, pi, u, types, q, thr):
    z = sum(pi.values())
    return sum(sum(g.values()) / z * reach(T, g, types, q, thr) for g in split(T, pi, lambda x: val(T, u, x)).values())


def expected_reach_after_mech(T, pi, M, types, q, thr):
    outs = {o for d in M.values() for o in d}
    tot, z = 0.0, sum(pi.values())
    for o in outs:
        g = {x: pi[x] * M[x].get(o, 0.0) for x in pi if pi[x] * M[x].get(o, 0.0) > 1e-12}
        if g:
            tot += sum(g.values()) / z * reach(T, g, types, q, thr)
    return tot


def instance(seed):
    rng = random.Random(seed)
    names = [n for n in NAMES if n != "serial"]
    T = table(names[seed % len(names)])
    m = len(T.units)
    rel = [j for j in range(m) if T.relevant >> j & 1]
    for _ in range(100):
        x = rng.choices(range(len(T.prior)), weights=T.prior)[0]
        K0 = sum(1 << j for j in rng.sample(rel, rng.randrange(0, max(1, len(rel) - 2))))
        if T.cov[K0]:
            continue
        cand = [j for j in rel if not K0 >> j & 1]
        if len(cand) < 2:
            continue
        types = [tuple(rng.sample(cand, min(len(cand), rng.choice([1, 2])))) for _ in range(5)]
        q = list(np.random.default_rng(seed).dirichlet(np.ones(len(types))))
        cell = [y for y in range(len(T.prior)) if T.gid[K0, y] == T.gid[K0, x]]
        pi = {y: float(T.prior[y]) for y in cell}
        return T, x, pi, types, q
    return None


def episode(T, x, pi0, types, q, tau, arm, seq, rng):
    pi = dict(pi0)
    util, viol, worst_excess = 0.0, 0, -1.0
    for ti in seq:
        thr = max(tau, vmax(T, pi))
        opts = types[ti]
        out = None
        if arm in ("CAPD", "CAPD+A", "CAPD_D", "CAPD_D+A"):
            ok = [u for u in opts if sim_ok(T, pi, u, thr)]
            if ok:
                u = ok[0] if arm in ("CAPD", "CAPD_D") else max(ok, key=lambda u: (expected_reach_after_release(T, pi, u, types, q, thr), -opts.index(u)))
                out = ("R", val(T, u, x))
                key = lambda y, u=u: val(T, u, y)
                pi = {y: p for y, p in pi.items() if key(y) == key(x)}
                util += 1
            elif arm in ("CAPD_D", "CAPD_D+A"):      # same action space as B: simulatable degrade fallback
                okd = [u for u in opts if sim_ok(T, pi, u, thr, degrade=True)]
                if okd:
                    def after_deg(u):
                        cm = coarse_map(T, u, pi)
                        z = sum(pi.values())
                        return sum(sum(g.values()) / z * reach(T, g, types, q, thr)
                                   for g in split(T, pi, lambda y: cm[val(T, u, y)]).values())
                    u = okd[0] if arm == "CAPD_D" else max(okd, key=lambda u: (after_deg(u), -opts.index(u)))
                    cm = coarse_map(T, u, pi)
                    pi = {y: p for y, p in pi.items() if cm[val(T, u, y)] == cm[val(T, u, x)]}
                    util += BETA
        elif arm == "CAPD_F":
            u = opts[0]
            g = {y: p for y, p in pi.items() if val(T, u, y) == val(T, u, x)}
            if vmax(T, g) <= thr + 1e-9:
                # the refusal event is informative: attacker conditions on 'released'/'refused' by the rule
                rel_worlds = {y for y in pi if vmax(T, {w: p for w, p in pi.items() if val(T, u, w) == val(T, u, y)}) <= thr + 1e-9}
                pi = g
                util += 1
            else:
                rel_worlds = {y for y in pi if vmax(T, {w: p for w, p in pi.items() if val(T, u, w) == val(T, u, y)}) <= thr + 1e-9}
                pi = {y: p for y, p in pi.items() if y not in rel_worlds}
        else:
            cands = []
            for u in (opts[:1] if arm == "CAPD+B" else opts):
                M, eu = lp(T, pi, u, thr)
                if M is None:
                    continue
                score = eu if arm == "CAPD+B" else eu + expected_reach_after_mech(T, pi, M, types, q, thr)
                cands.append((score, -opts.index(u), u, M))
            if cands:
                _, _, u, M = max(cands, key=lambda c: (c[0], c[1]))
                os_ = list(M[x])
                o = os_[rng.choices(range(len(os_)), weights=[M[x][k] for k in os_])[0]]
                util += 1.0 if o[0] == "R" else BETA if o[0] == "D" else 0.0
                pi = {y: p * M[y].get(o, 0.0) for y, p in pi.items() if p * M[y].get(o, 0.0) > 1e-15}
        e = vmax(T, pi) - thr
        worst_excess = max(worst_excess, e)
        viol += e > 1e-7
    return util / len(seq), viol, worst_excess, vmax(T, pi)


def run(seed):
    got = instance(seed)
    if got is None:
        return None
    T, x, pi, types, q = got
    out = {"seed": seed, "name": T.st.name, "res": {}}
    for tau in (0.34, 0.5):
        if vmax(T, pi) > tau - 1e-9:
            continue
        r = {}
        for arm in ("CAPD", "CAPD+A", "CAPD_D", "CAPD_D+A", "CAPD+B", "CAPD+A+B", "CAPD_F"):
            us, vs, ws, fv = [], 0, -1.0, []
            for e in range(12):
                srng = random.Random(hash((seed, e)) & 0xFFFFFFFF)
                seq = [srng.choices(range(len(q)), weights=q)[0] for _ in range(H)]
                u, v, w, f = episode(T, x, pi, types, q, tau, arm, seq, random.Random(hash((seed, e, "o")) & 0xFFFFFFFF))
                us.append(u)
                vs += v
                ws = max(ws, w)
                fv.append(f)
            r[arm] = {"utility": float(np.mean(us)), "per_episode": us, "violating_steps": vs, "worst_excess": ws,
                      "final_V1": float(np.mean(fv))}
        out["res"][str(tau)] = r
    return out if out["res"] else None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with Pool(9) as pool:
        rows = [r for r in pool.imap_unordered(run, [100000 + s for s in range(400)], chunksize=2) if r]
    with gzip.open(OUT / "ab_raw.json.gz", "wt") as h:
        json.dump(rows, h, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(len(rows))


if __name__ == "__main__":
    main()
