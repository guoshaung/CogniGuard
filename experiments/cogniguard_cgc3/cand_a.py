"""Candidate A: forward-looking disclosure selection (look-ahead dual quantity).

Model. One recipient (or the grand coalition, k = N: pooled knowledge K). Tasks arrive i.i.d. from a pool;
task type t can be served by any one of its option unit sets O_t,1..O_t,r (alternatives). Serving with
option o discloses o: K <- K u o. Safety (hard): L*(K) <= tau at the true world (formal CA-PD semantics).
Horizon H. Objective: expected number of served tasks.

Quantity 1 (attacker side): L*(K), leakage of the secret.
Quantity 2 (look-ahead): R(K) = sum_t q(t) 1[some option of t is still safe from K]: the safe reachability of
future legitimate needs.

Policies (all respect the same safety constraint and the same task information):
  CAPD_FIRST   immediate CA-PD: serve with the first safe option
  GREEDY_MIN   fewest new units          GREEDY_LEAK  least resulting leakage       RANDOM
  CONFLICT     max R(K u o) (witness-conflict prediction, one step), always serve if possible
  LA           1-step look-ahead with deferral: Q(o) = 1 + (H-t-1) R(K u o), Q(refuse) = (H-t-1) R(K)
  LA_l<lam>    LA minus lam * (L*(K u o) - L*(K))   (adds quantity 1 as a soft term)
  EXPECTIMAX2  depth-2 Bayesian planning with leaf (H-t) R(K)
  ROLLOUT      receding horizon: 24 sampled futures of length 3 under GREEDY_MIN
  OPT_SERVE    exact DP optimum restricted to "serve whenever possible"
  OPT          exact DP optimum (may refuse to keep future tasks reachable)
Every policy is evaluated EXACTLY by dynamic programming over (t, K) under the TRUE task distribution.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from experiments.cogniguard_cgc3.common import NAMES, lstar, table

OUT = Path(__file__).parent / "results"
H = 6


def make_instance(name, seed, v_thr, n_types=8):
    T = table(name)
    rng = random.Random(seed)
    x = rng.choices(range(len(T.prior)), weights=T.prior)[0]
    pri = T.V1[0, x]
    if pri >= v_thr:
        return None
    tau = math.log2(v_thr / pri)
    Ls = lstar(T, x)
    m = len(T.units)
    rel = [j for j in range(m) if T.relevant >> j & 1]
    types = []
    while len(types) < n_types:
        opts = []
        for _ in range(rng.choice([1, 2, 3])):
            o = 0
            pool = rel if rng.random() < 0.85 else list(range(m))
            for j in rng.sample(pool, min(len(pool), rng.choice([1, 2]))):
                o |= 1 << j
            if Ls[o] <= tau + 1e-12 and o not in opts:
                opts.append(o)
        if opts:
            types.append(tuple(opts))
    q = np.random.default_rng(seed).dirichlet(np.ones(n_types))
    return {"name": name, "x": x, "tau": tau, "Ls": Ls, "types": types, "q": q, "m": m}


class Planner:
    def __init__(self, inst, q_plan, types_plan=None):
        self.I = inst
        self.q = q_plan
        self.types = types_plan if types_plan is not None else inst["types"]
        self.Ls, self.tau = inst["Ls"], inst["tau"]
        self.calls = 0

    def feas(self, K, opts):
        return [o for o in opts if self.Ls[K | o] <= self.tau + 1e-12]

    @lru_cache(maxsize=None)
    def R(self, K):
        return sum(p for p, opts in zip(self.q, self.types) if self.feas(K, opts))

    @lru_cache(maxsize=None)
    def opt(self, t, K, serve_only=False, lam=0.0):
        if t >= H:
            return -lam * float(self.Ls[K])
        v = 0.0
        for p, opts in zip(self.q, self.types):
            best = self.opt(t + 1, K, serve_only, lam)
            f = self.feas(K, opts)
            if f:
                sv = max(1 + self.opt(t + 1, K | o, serve_only, lam) for o in f)
                best = sv if serve_only else max(best, sv)
            v += p * best
        return v

    @lru_cache(maxsize=None)
    def emax(self, t, K, d):
        if t >= H:
            return 0.0
        if d == 0:
            return (H - t) * self.R(K)
        v = 0.0
        for p, opts in zip(self.q, self.types):
            best = self.emax(t + 1, K, d - 1)
            for o in self.feas(K, opts):
                best = max(best, 1 + self.emax(t + 1, K | o, d - 1))
            v += p * best
        return v

    def act(self, pol, t, K, opts, seed):
        """Return chosen option (int) or None (refuse)."""
        self.calls += 1
        f = self.feas(K, opts)
        if not f:
            return None
        Ls = self.Ls
        if pol == "CAPD_FIRST":
            return f[0]
        if pol == "GREEDY_MIN":
            return min(f, key=lambda o: (bin(o & ~K).count("1"), Ls[K | o], o))
        if pol == "GREEDY_LEAK":
            return min(f, key=lambda o: (Ls[K | o], bin(o & ~K).count("1"), o))
        if pol == "RANDOM":
            return random.Random(hash((seed, t, K, opts))).choice(f)
        if pol.startswith("CONFLICT"):
            lam = float(pol.split("_l")[1]) if "_l" in pol else 0.0
            rem = H - t - 1
            return max(f, key=lambda o: (rem * self.R(K | o) - lam * Ls[K | o], -Ls[K | o], -o))
        if pol.startswith("LA"):
            lam = float(pol.split("_l")[1]) if "_l" in pol else 0.0
            rem = H - t - 1
            q = {o: 1 + rem * self.R(K | o) - lam * (Ls[K | o] - Ls[K]) for o in f}
            best = max(q, key=lambda o: (q[o], -o))
            return best if q[best] >= rem * self.R(K) - 1e-12 else None
        if pol == "EXPECTIMAX2":
            q = {o: 1 + self.emax(t + 1, K | o, 1) for o in f}
            best = max(q, key=lambda o: (q[o], -o))
            return best if q[best] >= self.emax(t + 1, K, 1) - 1e-12 else None
        if pol == "ROLLOUT":
            rng = random.Random(hash((seed, t, K, opts, "r")))
            futs = [[rng.choices(range(len(self.types)), weights=self.q)[0] for _ in range(min(3, H - t - 1))] for _ in range(24)]

            def sim(K0):
                tot = 0
                for fut in futs:
                    Kc = K0
                    for ty in fut:
                        ff = self.feas(Kc, self.types[ty])
                        if ff:
                            o2 = min(ff, key=lambda o: (bin(o & ~Kc).count("1"), Ls[Kc | o], o))
                            Kc |= o2
                            tot += 1
                return tot / len(futs)
            q = {o: 1 + sim(K | o) for o in f}
            best = max(q, key=lambda o: (q[o], -o))
            return best if q[best] >= sim(K) - 1e-12 else None
        if pol.startswith("OPT_l"):
            lam = float(pol.split("_l")[1])
            q = {o: 1 + self.opt(t + 1, K | o, False, lam) for o in f}
            best = max(q, key=lambda o: (q[o], -o))
            return best if q[best] >= self.opt(t + 1, K, False, lam) - 1e-12 else None
        if pol in ("OPT", "OPT_SERVE"):
            so = pol == "OPT_SERVE"
            q = {o: 1 + self.opt(t + 1, K | o, so) for o in f}
            best = max(q, key=lambda o: (q[o], -o))
            if so:
                return best
            return best if q[best] >= self.opt(t + 1, K, False) - 1e-12 else None
        raise ValueError(pol)


def evaluate(inst, pol, q_plan, types_plan=None, seed=0):
    """Exact expected served tasks and expected final leakage under the TRUE distribution."""
    P = Planner(inst, q_plan, types_plan)
    q_true, types_true = inst["q"], inst["types"]
    memo = {}

    def V(t, K):
        if t >= H:
            return 0.0, float(inst["Ls"][K]), float(table(inst["name"]).V1[K, inst["x"]])
        key = (t, K)
        if key in memo:
            return memo[key]
        s = l = v1 = 0.0
        for p, opts in zip(q_true, types_true):
            o = P.act(pol, t, K, opts, seed)
            if o is None:
                a, b, c = V(t + 1, K)
            else:
                a, b, c = V(t + 1, K | o)
                a += 1
            s += p * a
            l += p * b
            v1 += p * c
        memo[key] = (s, l, v1)
        return memo[key]
    t0 = time.perf_counter()
    s, l, v1 = V(0, 0)
    return {"served": s, "final_Lstar": l, "final_V1": v1, "sec": time.perf_counter() - t0, "decisions": P.calls}


POLS = ["CAPD_FIRST", "GREEDY_MIN", "GREEDY_LEAK", "RANDOM", "CONFLICT", "CONFLICT_l0.3", "CONFLICT_l1",
        "LA", "LA_l0.5", "LA_l2", "EXPECTIMAX2", "ROLLOUT", "OPT_SERVE", "OPT", "OPT_l0.3", "OPT_l1", "OPT_l3"]


def run(args):
    name, seed, v_thr = args
    inst = make_instance(name, seed, v_thr)
    if inst is None:
        return None
    rng = np.random.default_rng(seed + 99)
    n = len(inst["types"])
    q_uniform = np.ones(n) / n
    q_wrong = rng.dirichlet(np.ones(n))
    keep = sorted(rng.choice(n, size=n - 3, replace=False))        # planner unaware of 3 task types
    out = {"name": name, "seed": seed, "v_thr": v_thr, "tau": inst["tau"], "res": {}}
    for pol in POLS:
        r = {"in": evaluate(inst, pol, inst["q"], seed=seed)}
        if pol not in ("CAPD_FIRST", "GREEDY_MIN", "GREEDY_LEAK", "RANDOM"):
            r["uniform"] = evaluate(inst, pol, q_uniform, seed=seed)
            r["wrong_q"] = evaluate(inst, pol, q_wrong, seed=seed)
            qk = inst["q"][keep] / inst["q"][keep].sum()
            r["unseen_types"] = evaluate(inst, pol, qk, [inst["types"][i] for i in keep], seed=seed)
        out["res"][pol] = r
    # upper bound with no safety (every task served if it has an option): H
    out["no_safety_bound"] = H
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=24)
    a = ap.parse_args()
    jobs = [(n, s, v) for n in NAMES for s in range(a.seeds) for v in (0.25, 0.5, 0.75)]
    OUT.mkdir(parents=True, exist_ok=True)
    with Pool(9) as pool:
        res = [r for r in pool.imap_unordered(run, jobs, chunksize=2) if r]
    (OUT / "cand_a_raw.json").write_text(json.dumps(res) + "\n")
    print(len(res))


if __name__ == "__main__":
    main()
