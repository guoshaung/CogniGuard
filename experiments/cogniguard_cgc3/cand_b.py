"""Candidate B: two-channel leakage control (content + governance behaviour), exact.

Setting. The attacker already holds view K0 (it knows the values), so it knows the world lies in its cell C.
It requests unit u. A truthful mechanism outputs one of
  ("R", f_u(x))      release the true value
  ("D", c_u(x))      degrade: a fixed binary coarsening of the true value
  ("X",)             refuse
with probabilities M[x, o] that may depend on the true world x (governance behaviour is a channel too).
The attacker knows the mechanism (Kerckhoffs) and observes the output o (content AND action jointly).

Leakage is computed on the JOINT output o, never as a sum of per-channel terms:
  max-case:  max_o max_s P(S=s | cell, o)                      (constraint: <= tau_V)
  expected:  sum_o max_s P(S=s, o | cell)  (Bayes vulnerability)  (constraint variant)
  Shannon:   I(S; O | cell)
We also report the two common mistakes: content-only accounting (refusal treated as uninformative) and the
naive sum I(S;A) + I(S;C) with A = action label, C = content.

Mechanisms: CAPD_VI (value-independent witness), CAPD_F (formal CA-PD: realized V1 <= tau), CAPD_F_DEG,
SIM / SIM_DEG (simulatable auditing, worst case over the attacker's cell), RAND (x-independent random
release), LP_JOINT (exact optimum over truthful channels, joint constraint), LP_NODEG (no degrade action),
LP_SIMUL (action law independent of x), LP_CONTENT (constraint only on content outputs; then audited jointly).
Two-step extension: myopic per-step LP versus joint two-step LP.
"""

from __future__ import annotations

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
BETA = 0.5       # utility of a degraded answer relative to a full one


def outputs_for(T, u, xs):
    st = T.st
    vals = sorted({st.units[T.units[u]](st.worlds[x]) for x in xs}, key=repr)
    coarse = {v: i % 2 for i, v in enumerate(vals)}
    outs = [("R", v) for v in vals] + [("D", 0), ("D", 1), ("X",)]
    allowed = {}
    for x in xs:
        v = st.units[T.units[u]](st.worlds[x])
        allowed[x] = {("R", v), ("D", coarse[v]), ("X",)}
    return outs, allowed


def evaluate(T, xs, pi, M, outs):
    """M: dict x -> dict o -> prob. Returns joint leakage metrics and utility."""
    ns = len(T.svals)
    Ps = np.zeros(ns)
    for x, p in zip(xs, pi):
        Ps[T.sidx[x]] += p
    joint = {o: np.zeros(ns) for o in outs}
    util = 0.0
    for x, p in zip(xs, pi):
        for o, q in M[x].items():
            if q <= 0:
                continue
            joint[o][T.sidx[x]] += p * q
            util += p * q * (1.0 if o[0] == "R" else BETA if o[0] == "D" else 0.0)
    po = {o: v.sum() for o, v in joint.items()}
    maxcase = max((v.max() / po[o] for o, v in joint.items() if po[o] > 1e-12), default=0.0)
    expected = sum(v.max() for v in joint.values())
    I = sum(v[s] * math.log2(v[s] / (po[o] * Ps[s])) for o, v in joint.items() for s in range(ns) if v[s] > 1e-15)
    # content-only accounting: refusal treated as uninformative (its posterior := cell prior)
    content_max = max([v.max() / po[o] for o, v in joint.items() if po[o] > 1e-12 and o[0] != "X"] + [Ps.max()])
    # naive sum: I(S;A) + I(S;C), A = action label, C = content (refuse/degrade content = bottom/coarse)
    def mi_of(keyf):
        agg = {}
        for o, v in joint.items():
            agg.setdefault(keyf(o), np.zeros(ns))
            agg[keyf(o)] += v
        return sum(w[s] * math.log2(w[s] / (w.sum() * Ps[s])) for w in agg.values() for s in range(ns) if w[s] > 1e-15)
    I_A = mi_of(lambda o: o[0])
    I_C = mi_of(lambda o: o[1] if o[0] == "R" else ("deg", o[1]) if o[0] == "D" else "bottom")
    return {"utility": util, "joint_maxcase_V": maxcase, "joint_expected_V": expected, "I_joint": I,
            "content_only_maxcase_V": content_max, "naive_sum_I": I_A + I_C, "I_action": I_A, "prior_V": float(Ps.max())}


def lp(T, xs, pi, outs, allowed, tau, mode="maxcase", deg=True, simul=False, content_only=False):
    idx = {(x, o): k for k, (x, o) in enumerate((x, o) for x in xs for o in outs)}
    n = len(idx)
    c = np.zeros(n)
    bounds = [(0, 0)] * n
    for (x, o), k in idx.items():
        p = pi[xs.index(x)]
        if o in allowed[x] and (deg or o[0] != "D"):
            bounds[k] = (0, 1)
        c[k] = -p * (1.0 if o[0] == "R" else BETA if o[0] == "D" else 0.0)
    A_eq, b_eq, A_ub, b_ub = [], [], [], []
    for x in xs:
        row = np.zeros(n)
        for o in outs:
            row[idx[(x, o)]] = 1
        A_eq.append(row)
        b_eq.append(1.0)
    if simul:   # action label distribution independent of x
        labels = ["R", "D", "X"]
        x0 = xs[0]
        for x in xs[1:]:
            for lab in labels:
                row = np.zeros(n)
                for o in outs:
                    if o[0] == lab:
                        row[idx[(x, o)]] += 1
                        row[idx[(x0, o)]] -= 1
                A_eq.append(row)
                b_eq.append(0.0)
    svals = sorted({int(T.sidx[x]) for x in xs})
    extra = 0
    if mode == "expected":
        extra = len(outs)
        c = np.concatenate([c, np.zeros(extra)])
        bounds = bounds + [(0, 1)] * extra
        A_eq = [np.concatenate([r, np.zeros(extra)]) for r in A_eq]
    for oi, o in enumerate(outs):
        if content_only and o[0] == "X":
            continue
        for s in svals:
            row = np.zeros(n + extra)
            for x, p in zip(xs, pi):
                k = idx[(x, o)]
                if mode == "maxcase":
                    row[k] = p * ((1 if T.sidx[x] == s else 0) - tau)
                else:
                    row[k] = p * (1 if T.sidx[x] == s else 0)
            if mode == "expected":
                row[n + oi] = -1
            A_ub.append(row)
            b_ub.append(0.0)
    if mode == "expected":
        row = np.zeros(n + extra)
        row[n:] = 1
        A_ub.append(row)
        b_ub.append(tau)
    res = linprog(c, A_ub=np.array(A_ub) if A_ub else None, b_ub=b_ub or None, A_eq=np.array(A_eq), b_eq=b_eq,
                  bounds=bounds, method="highs")
    if res.status != 0:
        return None
    M = {x: {o: max(0.0, res.x[idx[(x, o)]]) for o in outs} for x in xs}
    return M


def rule_mech(T, xs, outs, allowed, K0, u, tau, kind):
    """Deterministic rule-based mechanisms."""
    Ku = K0 | (1 << u)
    M = {}
    deg_v = {}
    if kind in ("CAPD_F_DEG", "SIM_DEG"):
        # realized V1 after a degraded answer: posterior within the cell given the coarse bit
        for x in xs:
            o_d = [o for o in allowed[x] if o[0] == "D"][0]
            sel = [y for y in xs if o_d in allowed[y]]
            w = np.zeros(len(T.svals))
            for y in sel:
                w[T.sidx[y]] += T.prior[y]
            deg_v[x] = w.max() / w.sum()
    for x in xs:
        rel = [o for o in allowed[x] if o[0] == "R"][0]
        dg = [o for o in allowed[x] if o[0] == "D"][0]
        safe_r = T.V1[Ku, x] <= tau + 1e-12
        if kind == "CAPD_VI":
            a = rel if not T.cov[Ku] else ("X",)
        elif kind == "CAPD_F":
            a = rel if safe_r else ("X",)
        elif kind == "CAPD_F_DEG":
            a = rel if safe_r else dg if deg_v[x] <= tau + 1e-12 else ("X",)
        elif kind == "SIM":
            a = rel if all(T.V1[Ku, y] <= tau + 1e-12 for y in xs) else ("X",)
        elif kind == "SIM_DEG":
            a = rel if all(T.V1[Ku, y] <= tau + 1e-12 for y in xs) else dg if all(deg_v[y] <= tau + 1e-12 for y in xs) else ("X",)
        M[x] = {a: 1.0}
    return M


def instance(name, seed, tau_V):
    T = table(name)
    rng = random.Random(seed)
    m = len(T.units)
    rel = [j for j in range(m) if T.relevant >> j & 1]
    for _ in range(200):
        K0 = 0
        for j in rng.sample(rel, rng.randrange(0, len(rel))):
            K0 |= 1 << j
        x0 = rng.choices(range(len(T.prior)), weights=T.prior)[0]
        cand = [j for j in rel if not K0 >> j & 1]
        if not cand or T.cov[K0]:
            continue
        u = rng.choice(cand)
        xs = [x for x in range(len(T.prior)) if T.gid[K0, x] == T.gid[K0, x0]]
        pi = np.array([T.prior[x] for x in xs])
        pi = pi / pi.sum()
        ps = np.zeros(len(T.svals))
        for x, p in zip(xs, pi):
            ps[T.sidx[x]] += p
        if ps.max() > tau_V - 1e-9:
            continue
        # keep only instances where the request is not trivially safe for every world
        if all(T.V1[K0 | 1 << u, x] <= tau_V + 1e-12 for x in xs):
            continue
        return T, K0, u, xs, list(pi)
    return None


def run(args):
    name, seed, tau_V = args
    got = instance(name, seed, tau_V)
    if got is None:
        return None
    T, K0, u, xs, pi = got
    outs, allowed = outputs_for(T, u, xs)
    res = {}
    for kind in ("CAPD_VI", "CAPD_F", "CAPD_F_DEG", "SIM", "SIM_DEG"):
        t0 = time.perf_counter()
        M = rule_mech(T, xs, outs, allowed, K0, u, tau_V, kind)
        res[kind] = {**evaluate(T, xs, pi, M, outs), "sec": time.perf_counter() - t0}
    for kind, kw in (("LP_JOINT", {}), ("LP_NODEG", {"deg": False}), ("LP_SIMUL", {"simul": True}),
                     ("LP_CONTENT", {"content_only": True}), ("LP_EXP", {"mode": "expected"}),
                     ("LP_EXP_SIMUL", {"mode": "expected", "simul": True})):
        t0 = time.perf_counter()
        M = lp(T, xs, pi, outs, allowed, tau_V, **kw)
        res[kind] = None if M is None else {**evaluate(T, xs, pi, M, outs), "sec": time.perf_counter() - t0}
    # x-independent random release (best rho with joint max-case <= tau; usually 0 under max-case)
    best = None
    for rho in np.linspace(0, 1, 21):
        M = {x: {[o for o in allowed[x] if o[0] == "R"][0]: rho, ("X",): 1 - rho} for x in xs}
        ev = evaluate(T, xs, pi, M, outs)
        if ev["joint_maxcase_V"] <= tau_V + 1e-9:
            best = {**ev, "rho": float(rho)}
    res["RAND"] = best
    best = None
    for rho in np.linspace(0, 1, 21):
        M = {x: {[o for o in allowed[x] if o[0] == "R"][0]: rho, ("X",): 1 - rho} for x in xs}
        ev = evaluate(T, xs, pi, M, outs)
        if ev["joint_expected_V"] <= tau_V + 1e-9:
            best = {**ev, "rho": float(rho)}
    res["RAND_EXP"] = best
    return {"name": name, "seed": seed, "tau_V": tau_V, "cell": len(xs), "res": res}


# ------------------------------------------------------------------ two-step: myopic vs joint

def two_step(args):
    name, seed, tau_V = args
    got = instance(name, seed, tau_V)
    if got is None:
        return None
    T, K0, u1, xs, pi = got
    rel = [j for j in range(len(T.units)) if T.relevant >> j & 1 and not (K0 | 1 << u1) >> j & 1]
    if not rel:
        return None
    u2 = random.Random(seed + 7).choice(rel)
    o1s, al1 = outputs_for(T, u1, xs)
    o2s, al2 = outputs_for(T, u2, xs)
    outs = [(a, b) for a in o1s for b in o2s]
    allowed = {x: {(a, b) for a in al1[x] for b in al2[x]} for x in xs}
    w = lambda o: (1.0 if o[0] == "R" else BETA if o[0] == "D" else 0.0)
    # joint LP over (o1, o2) with prefix constraints on o1 and full constraints on (o1, o2)
    idx = {(x, o): k for k, (x, o) in enumerate((x, o) for x in xs for o in outs)}
    n = len(idx)
    c = np.zeros(n)
    bounds = [(0, 0)] * n
    for (x, o), k in idx.items():
        if o in allowed[x]:
            bounds[k] = (0, 1)
        c[k] = -pi[xs.index(x)] * (w(o[0]) + w(o[1]))
    A_eq = []
    for x in xs:
        r = np.zeros(n)
        for o in outs:
            r[idx[(x, o)]] = 1
        A_eq.append(r)
    svals = sorted({int(T.sidx[x]) for x in xs})
    A_ub = []
    for o in outs:
        for s in svals:
            r = np.zeros(n)
            for x, p in zip(xs, pi):
                r[idx[(x, o)]] = p * ((1 if T.sidx[x] == s else 0) - tau_V)
            A_ub.append(r)
    for a in o1s:
        for s in svals:
            r = np.zeros(n)
            for o in outs:
                if o[0] != a:
                    continue
                for x, p in zip(xs, pi):
                    r[idx[(x, o)]] += p * ((1 if T.sidx[x] == s else 0) - tau_V)
            A_ub.append(r)
    t0 = time.perf_counter()
    res = linprog(c, A_ub=np.array(A_ub), b_ub=np.zeros(len(A_ub)), A_eq=np.array(A_eq), b_eq=np.ones(len(xs)),
                  bounds=bounds, method="highs")
    joint_u = -res.fun if res.status == 0 else None
    t_joint = time.perf_counter() - t0
    # myopic: optimal step-1 LP, then optimal step-2 LP for each step-1 output on its posterior
    t0 = time.perf_counter()
    M1 = lp(T, xs, pi, o1s, al1, tau_V)
    my_u = None
    if M1 is not None:
        my_u = sum(p * q * w(o) for x, p in zip(xs, pi) for o, q in M1[x].items())
        for a in o1s:
            px = np.array([p * M1[x].get(a, 0.0) for x, p in zip(xs, pi)])
            if px.sum() <= 1e-12:
                continue
            sub = [x for x, v in zip(xs, px) if v > 1e-15]
            sp = [v / px.sum() for v in px if v > 1e-15]
            M2 = lp(T, sub, sp, o2s, {x: al2[x] for x in sub}, tau_V)
            if M2 is None:
                continue
            my_u += px.sum() * sum(p * q * w(o) for x, p in zip(sub, sp) for o, q in M2[x].items())
    t_my = time.perf_counter() - t0
    return {"name": name, "seed": seed, "tau_V": tau_V, "joint_util": joint_u, "myopic_util": my_u,
            "sec_joint": t_joint, "sec_myopic": t_my, "n_outputs": len(outs)}


def main():
    jobs = [(n, s, t) for n in NAMES for s in range(40) for t in (0.34, 0.5, 0.67)]
    OUT.mkdir(parents=True, exist_ok=True)
    with Pool(9) as pool:
        one = [r for r in pool.imap_unordered(run, jobs, chunksize=4) if r]
        two = [r for r in pool.imap_unordered(two_step, [j for j in jobs if j[1] < 12], chunksize=2) if r]
    (OUT / "cand_b_raw.json").write_text(json.dumps({"one_step": one, "two_step": two}) + "\n")
    print(len(one), len(two))


if __name__ == "__main__":
    main()
