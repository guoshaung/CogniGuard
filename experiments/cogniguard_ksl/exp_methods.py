"""Experiment 3 (pilot): gate comparison under governance uncertainty, same information, same budget, same target.

World: a structure, a true world x* (the owner-side governor knows x*, as CA-PD's protected targets do), N
agents. Each agent may know units from background (prob q, unseen by the governor). Each request is a message
carrying true units T_m; the governor only sees detected units D_m (each true unit missed w.p. MISS, one
spurious unit added w.p. FP). The governor's belief about history is the exact per-message posterior
P(u in T_m | D_m), combined over messages by noisy-OR (the L3h state model). Every method uses the same
belief, the same D_m as the pending release, and the same verification oracle (reveals whether agent a
truly knows unit u; one call each).

Safety target (primary, partial leakage): a released request is harmful iff, for the TRUE knowledge state,
some coalition C (recipient in C, |C| <= k) has Bayes vulnerability V1(S | K_C + T_m) >= TAU and the release
increased it. Secondary target (complete reconstruction): the release makes S realized-determined for some
coalition. Over-refusal: refusing a request that is not harmful under the primary target.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from experiments.cogniguard_ksl import engine, structures as S

OUT = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/ksl")
Q_BG, MISS, FP, P_EXTRA, P_REL = 0.1, 0.3, 0.05, 0.3, 0.65
L_REQ, NS = 10, 1024
CAP = 2                                         # verification calls per request

_TAB = {}
_MPOST = {}


def tables(name):
    if name not in _TAB:
        st = {s.name: s for s in S.all_structures()}[name]
        T = engine.build(st)
        T.gid = engine.cell_ids(T)
        _TAB[name] = (T, engine.registry(T))
    return _TAB[name]


# ------------------------------------------------------------------ episode generation

def message_space(T):
    """All possible true message unit sets with their generator probabilities."""
    m = len(T.units)
    rel = [j for j in range(m) if T.relevant >> j & 1]
    dec = [j for j in range(m) if not T.relevant >> j & 1]
    space = {}
    for j in range(m):
        pj = P_REL / len(rel) if j in rel else (1 - P_REL) / len(dec)
        space[1 << j] = space.get(1 << j, 0) + pj * (1 - P_EXTRA)
        for i in range(m):
            if i != j:
                key = 1 << j | 1 << i
                space[key] = space.get(key, 0) + pj * P_EXTRA / (m - 1)
    return space


def detect_lik(T, true_mask, det_mask):
    """P(D | T): each true unit missed w.p. MISS; w.p. FP one uniformly chosen non-true unit is added."""
    m = len(T.units)
    tr = [j for j in range(m) if true_mask >> j & 1]
    extra = det_mask & ~true_mask
    kept = det_mask & true_mask
    p = 1.0
    for j in tr:
        p *= (1 - MISS) if kept >> j & 1 else MISS
    nonT = m - len(tr)
    ne = bin(extra).count("1")
    if ne == 0:
        return p * (1 - FP)
    if ne == 1:
        return p * FP / nonT
    return 0.0


def posterior_units(T, det_mask, space):
    """Exact marginal P(u in T_m | D_m) under the generator."""
    w = {t: pt * detect_lik(T, t, det_mask) for t, pt in space.items()}
    z = sum(w.values())
    m = len(T.units)
    return np.array([sum(v for t, v in w.items() if t >> j & 1) / z for j in range(m)])


def episode(name, N, seed):
    T, _ = tables(name)
    rng = random.Random(seed)
    m = len(T.units)
    x = rng.choices(range(len(T.st.worlds)), weights=T.prior)[0]
    bg = [sum(1 << j for j in range(m) if rng.random() < Q_BG) for _ in range(N)]
    space = message_space(T)
    keys, probs = list(space), list(space.values())
    reqs = []
    for _ in range(L_REQ):
        a = rng.randrange(N)
        t = rng.choices(keys, weights=probs)[0]
        d = 0
        for j in range(m):
            if t >> j & 1 and rng.random() > MISS:
                d |= 1 << j
        if rng.random() < FP:
            cand = [j for j in range(m) if not t >> j & 1]
            d |= 1 << rng.choice(cand)
        reqs.append((a, t, d))
    return {"x": x, "bg": bg, "reqs": reqs}


# ------------------------------------------------------------------ risk evaluation over K samples

class Ctx:
    def __init__(self, name, N, k, x, seed):
        self.T, self.reg = tables(name)
        self.N, self.k, self.x = N, k, x
        self.m = len(self.T.units)
        self.V1 = self.T.V1[:, x]
        self.Vg = self.T.Vg[:, x]
        self.H = self.T.H[:, x]
        self.cov = self.T.cov
        self.pow = 1 << np.arange(self.m)
        self.rs = np.random.default_rng(seed)
        self.U = self.rs.random((NS, N, self.m))          # common random numbers for this decision
        self._ps = {}

    def coalitions(self, a):
        return [c for r in range(1, self.k + 1) for c in itertools.combinations(range(self.N), r) if a in c]

    def masks(self, P):
        """P: (N, m) belief -> sampled agent masks (NS, N)."""
        bits = self.U < P[None]
        return (bits * self.pow).sum(-1)

    def stats(self, P, a, M, tbl="V1"):
        V = getattr(self, tbl)
        am = self.masks(P)
        cs = self.coalitions(a)
        cm = np.stack([np.bitwise_or.reduce(am[:, list(c)], axis=1) for c in cs], 1)    # (NS, C)
        before = V[cm].max(1)
        Mb = M[:, None] if isinstance(M, np.ndarray) else M
        after = V[cm | Mb].max(1)
        return before, after, cm

    def p_harm(self, P, a, M, tau, tbl="V1"):
        b, af, _ = self.stats(P, a, M, tbl)
        return float(np.mean((af >= tau - 1e-12) & (af > b + 1e-12)))

    def p_cover(self, P, a, M):
        _, _, cm = self.stats(P, a, M)
        assert not isinstance(M, np.ndarray)
        if not any(M & w for w in self.T.witnesses):
            return 0.0
        return float(np.mean(self.cov[cm | M].any(1)))

    def msamples(self, d):
        """Pending-release uncertainty: NS draws from the exact posterior P(T_m | D_m) (same information D_m)."""
        key = (self.T.st.name, d)
        if key not in _MPOST:
            space = message_space(self.T)
            w = {t: pt * detect_lik(self.T, t, d) for t, pt in space.items()}
            ks = np.array(list(w))
            ps = np.array(list(w.values()))
            _MPOST[key] = (ks, ps / ps.sum())
        ks, ps = _MPOST[key]
        return ks[self.rs.choice(len(ks), NS, p=ps)]

    def psim(self, c, M, tau):
        """Simulatable harm probability: over the worlds the coalition with view c cannot rule out, the
        probability that releasing M lifts its Bayes vulnerability to >= tau. Depends on x* only through the
        coalition's own observations, so a refusal based on it reveals nothing new (no denial leak)."""
        key = (c, M, tau)
        if key not in self._ps:
            T = self.T
            sel = T.gid[c] == T.gid[c, self.x]
            f = (T.V1[c | M] >= tau - 1e-12) & (T.V1[c | M] > T.V1[c] + 1e-12)
            w = T.prior * sel
            self._ps[key] = float((w * f).sum() / w.sum())
        return self._ps[key]

    def p_harm_sim(self, P, a, M, tau):
        am = self.masks(P)
        cs = self.coalitions(a)
        cm = np.stack([np.bitwise_or.reduce(am[:, list(c)], axis=1) for c in cs], 1)
        Ms = M if isinstance(M, np.ndarray) else np.full(NS, M)
        rows = np.concatenate([cm, Ms[:, None]], 1)
        uniq, inv = np.unique(rows, axis=0, return_inverse=True)
        vals = np.array([max(self.psim(int(c), int(r[-1]), tau) for c in r[:-1]) for r in uniq])
        return float(vals[inv.reshape(-1)].mean())

    def point(self, P):
        return (P >= 0.5).astype(float)


def risk(ph, delta):
    rho = delta / (1 - delta)
    return min(ph, rho * (1 - ph))


# ------------------------------------------------------------------ methods

def decide(method, ctx, P, a, M, budget, verify, cfg):
    """Returns (block: bool, calls_used)."""
    tau, delta = cfg["tau"], cfg["delta"]
    T = ctx.T
    calls = 0
    D = M
    if cfg.get("marg_release", True) and method in ("BAYES", "BAYES_MEAN", "RANDV", "VOI", "VOI2", "DE2", "DE2_strict", "BAYES_SIM"):
        M = ctx.msamples(D)
    if method == "CAPD":
        K = ctx.point(P)
        know = {i: int((K[i] * ctx.pow).sum()) for i in range(ctx.N)}
        return (not engine.capd_safe(T, ctx.reg, a, M, know, ctx.k)), 0
    if method == "CAPD_d1":
        K = ctx.point(P)
        know = {i: int((K[i] * ctx.pow).sum()) for i in range(ctx.N)}
        return engine.capd_distance(T, ctx.reg, a, M, know, ctx.k) <= 1, 0
    if method == "L3h":
        return ctx.p_cover(P, a, M) > delta, 0
    if method in ("SHANNON", "MINENT", "GLEAK"):
        K = ctx.point(P)
        tbl = {"SHANNON": "H", "MINENT": "V1", "GLEAK": "Vg"}[method]
        b, af, _ = ctx.stats(K, a, M, tbl)
        b, af = float(b[0]), float(af[0])
        if method == "SHANNON":                      # entropy floor matched to tau: H <= log2(1/tau)
            # coalition with the lowest entropy is the most dangerous: recompute with min
            am = ctx.masks(K)
            cs = ctx.coalitions(a)
            cm = np.array([int(np.bitwise_or.reduce(am[0, list(c)])) for c in cs])
            hb, ha = ctx.H[cm].min(), ctx.H[cm | M].min()
            return bool(ha <= cfg["h0"] + 1e-12 and ha < hb - 1e-12), 0
        tr = cfg.get("tau_rule", tau)
        return bool(af >= tr - 1e-12 and af > b + 1e-12), 0
    if method == "BAYES_MEAN":
        b, af, _ = ctx.stats(P, a, M)
        tr = cfg.get("tau_rule", tau)
        return bool(af.mean() >= tr - 1e-12 and af.mean() > b.mean() + 1e-12), 0
    if method == "MINENT_SIM":
        return ctx.p_harm_sim(ctx.point(P), a, D, tau) > delta, 0
    if method == "BAYES_SIM":
        return ctx.p_harm_sim(P, a, M, tau) > delta, 0
    if method in ("BAYES", "BAYES_D"):          # BAYES_D: same rule, pending release fixed at D_m
        return ctx.p_harm(P, a, M, tau) > delta, 0
    if method in ("VOI", "VOI2", "RANDV", "DE2", "DE2_strict"):
        rel = [(i, j) for i in set(itertools.chain(*ctx.coalitions(a))) for j in range(ctx.m)
               if T.relevant >> j & 1 and 0 < P[i, j] < 1]
        while calls < min(CAP, budget):
            cand = [(i, j) for (i, j) in rel if 0 < P[i, j] < 1]
            if not cand:
                break
            ph = ctx.p_harm(P, a, M, tau)
            if method.startswith("DE2"):
                hk = sum(_h2(P[i, j]) for i, j in cand)
                if hk <= cfg["eta"]:
                    break
                pick = max(cand, key=lambda c: _h2(P[c]))
            elif method == "RANDV":
                if ph in (0.0, 1.0):
                    break
                pick = cand[ctx.rs.integers(len(cand))]
            else:
                r0 = risk(ph, delta)
                vo = {}
                for c in cand:
                    p = P[c]
                    r = 0.0
                    for val, w in ((1.0, p), (0.0, 1 - p)):
                        Q = P.copy()
                        Q[c] = val
                        r += w * risk(ctx.p_harm(Q, a, M, tau), delta)
                    vo[c] = r0 - r
                pick = max(vo, key=vo.get)
                if vo[pick] <= 1e-9:
                    if method != "VOI2":
                        break
                    best, bv = None, 1e-9
                    for c1, c2 in itertools.combinations(cand, 2):
                        r = 0.0
                        for v1, w1 in ((1.0, P[c1]), (0.0, 1 - P[c1])):
                            for v2, w2 in ((1.0, P[c2]), (0.0, 1 - P[c2])):
                                Q = P.copy()
                                Q[c1], Q[c2] = v1, v2
                                r += w1 * w2 * risk(ctx.p_harm(Q, a, M, tau), delta)
                        if r0 - r > bv:
                            best, bv = c1, r0 - r
                    if best is None:
                        break
                    pick = best
            P[pick] = float(verify(*pick))
            calls += 1
        if method.startswith("DE2"):
            cand = [(i, j) for (i, j) in rel if 0 < P[i, j] < 1]
            hk = sum(_h2(P[i, j]) for i, j in cand)
            if hk <= cfg["eta"]:                  # governance nearly certain: plug in the MAP knowledge state
                return ctx.p_harm(ctx.point(P), a, M, tau) > delta, calls
            if method == "DE2_strict":
                return True, calls
        return ctx.p_harm(P, a, M, tau) > delta, calls
    raise ValueError(method)


def _h2(p):
    return 0.0 if p <= 0 or p >= 1 else -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def oracle_harm(ctx, K, a, T_m, tau):
    cs = ctx.coalitions(a)
    cm = np.array([int(np.bitwise_or.reduce([K[i] for i in c])) for c in cs])
    b, af = ctx.V1[cm].max(), ctx.V1[cm | T_m].max()
    harm = af >= tau - 1e-12 and af > b + 1e-12
    full = ctx.V1[cm | T_m].max() > 1 - 1e-12 and ctx.V1[cm].max() < 1 - 1e-12
    return bool(harm), bool(full)


def run_episode(args):
    name, N, k, seed, variants, env = args
    global Q_BG, MISS
    Q_BG, MISS = env["q_bg"], env["miss"]
    ep = episode(name, N, seed)
    T, _ = tables(name)
    space = message_space(T)
    out = {}
    for label, meth, budget, cfg in variants:
        K = list(ep["bg"])                       # true knowledge
        P = np.full((N, len(T.units)), Q_BG)     # governor belief
        used = 0
        rec = {"harm_req": 0, "harm_rel": 0, "benign_req": 0, "benign_ref": 0, "full_req": 0, "full_rel": 0,
               "calls": 0, "sec": 0.0}
        for step, (a, t, d) in enumerate(ep["reqs"]):
            ctx = Ctx(name, N, k, ep["x"], hash((seed, step)) % 2 ** 32)
            t0 = time.perf_counter()
            if meth == "ORACLE":
                block = oracle_harm(ctx, K, a, t, cfg["tau"])[0]
                calls = 0
            else:
                verify = lambda i, j: (K[i] >> j) & 1
                block, calls = decide(meth, ctx, P, a, d, budget - used, verify, cfg)
            rec["sec"] += time.perf_counter() - t0
            used += calls
            harm, full = oracle_harm(ctx, K, a, t, cfg["tau"])
            rec["harm_req"] += harm
            rec["full_req"] += full
            rec["benign_req"] += not harm
            if block:
                rec["benign_ref"] += not harm
            else:
                rec["harm_rel"] += harm
                rec["full_rel"] += full
                K[a] |= t
                post = posterior_units(T, d, space)
                P[a] = 1 - (1 - P[a]) * (1 - post)
        rec["calls"] = used
        out[label] = rec
    return {"structure": name, "N": N, "k": k, "seed": seed, "env": env, "res": out}


def variants():
    base = {"tau": 0.5, "delta": 0.1, "h0": 1.0, "eta": 0.5}
    V = [("ORACLE", "ORACLE", 0, base), ("CAPD", "CAPD", 0, base), ("CAPD_d1", "CAPD_d1", 0, base)]
    deltas = (0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.7)
    taus = (0.2, 0.3, 0.4, 0.5, 0.65, 0.8, 1.0)
    for d in deltas:
        for m in ("L3h", "BAYES", "BAYES_D", "MINENT_SIM", "BAYES_SIM"):
            V.append((f"{m}|d={d}", m, 0, {**base, "delta": d}))
    for t in taus:
        for m in ("MINENT", "GLEAK", "BAYES_MEAN"):
            V.append((f"{m}|t={t}", m, 0, {**base, "tau_rule": t}))
    for h in (0.0, 0.5, 1.0, 1.5, 2.0, 3.0):
        V.append((f"SHANNON|h={h}", "SHANNON", 0, {**base, "h0": h}))
    for B in (3, 8):
        for d in (0.05, 0.1, 0.2, 0.35, 0.5):
            for m in ("RANDV", "VOI", "VOI2", "DE2"):
                V.append((f"{m}|B={B}|d={d}", m, B, {**base, "delta": d}))
            V.append((f"DE2_eta2|B={B}|d={d}", "DE2", B, {**base, "delta": d, "eta": 2.0}))
        V.append((f"DE2_strict|B={B}", "DE2_strict", B, base))
    return V


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eps", type=int, default=40)
    ap.add_argument("--tag", default="pilot")
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--procs", type=int, default=9)
    ap.add_argument("--structures", default="")
    ap.add_argument("--settings", default="1:1,3:1,3:3,5:5")
    ap.add_argument("--miss", type=float, default=0.3)
    ap.add_argument("--q_bg", type=float, default=0.1)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    env = {"miss": a.miss, "q_bg": a.q_bg}
    names = a.structures.split(",") if a.structures else [s.name for s in S.all_structures()]
    V = variants()
    if a.only:
        V = [v for v in V if v[1] in a.only.split(",")]
    jobs = []
    for name in names:
        for nk in a.settings.split(","):
            N, k = map(int, nk.split(":"))
            for e in range(a.eps):
                jobs.append((name, N, k, a.seed0 + 1000 * e + 7, V, env))
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with Pool(a.procs) as pool, open(OUT / f"methods_{a.tag}.jsonl", "w") as h:
        for i, r in enumerate(pool.imap_unordered(run_episode, jobs, chunksize=2)):
            h.write(json.dumps(r) + "\n")
            if i % 100 == 0:
                print(i, len(jobs), round(time.time() - t0), flush=True)
    print("done", len(jobs), round(time.time() - t0))


if __name__ == "__main__":
    main()
