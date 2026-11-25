"""Candidate C: individual vs coalition information control with partial information decomposition (PID).

Setting. N agents (N = 1..4). Each agent i holds unit set K_i (it learns the true values). A request
(i, u) is a legitimate task of agent i (utility 1 if served). Gates use CHANNEL-LEVEL quantities (averages
over the synthetic prior), so their decisions do not depend on the true secret value: no denial side channel.

Quantities (bits):
  I_i      = I(S; V_i)                     individual leakage
  I_coal   = I(S; V_1..V_N)                grand-coalition leakage (k = N)
  PID of I(S; V_i', V_-i) with sources V_i' (agent i after the release) and V_-i (all other agents pooled):
     Red, Unq_i, Unq_-i, Syn                 under two redundancy measures: I_min (Williams & Beer 2010)
                                             and MMI (min of the two mutual informations)
  Identity: I(S; V_i', V_-i) = Red + Unq_i + Unq_-i + Syn.

Gates (sequential, one decision per request):
  IND(b)          I(S; V_i') <= b                         individual bound only
  COAL(b)         I(S; V_all') <= b                       coalition bound (exact for the k = N target)
  COAL_IND(b,bi)  both
  SYN(bs)         Syn <= bs                               PID candidate, synergy only
  SYN_IND(bs,bi)  Syn <= bs and I(S;V_i') <= bi           PID candidate as proposed (keep own task info,
                                                          suppress collusive synergy)
  CAPD_VI         value-independent witness coverage of the pooled view (k = N)
Each gate is run with both PID measures where relevant. Metrics per episode: served fraction, final
I_coal, final expected coalition Bayes vulnerability, max individual leakage, worst pairwise (k = 2) leakage.
"""

from __future__ import annotations

import itertools
import json
import math
import random
import time
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from experiments.cogniguard_cgc3.common import NAMES, entropy, table

OUT = Path(__file__).parent / "results"
L_REQ = 8


@lru_cache(maxsize=None)
def stats(name, masks):
    """Exact channel-level quantities for the tuple of agent masks (pooled where needed)."""
    T = table(name)
    pr, sidx = T.prior, T.sidx
    ns = len(T.svals)

    def pj(ms):
        keys = np.stack([T.gid[m] for m in ms], 1) if ms else np.zeros((len(pr), 1), int)
        out = {}
        for i in range(len(pr)):
            k = (int(sidx[i]),) + tuple(int(v) for v in keys[i])
            out[k] = out.get(k, 0.0) + pr[i]
        return out
    return pj(list(masks))


def mi_from(pj, cols):
    """I(S; V_cols) from a joint dict keyed (s, v1, v2, ...)."""
    ps, pv, psv = {}, {}, {}
    for k, p in pj.items():
        v = tuple(k[1 + c] for c in cols)
        ps[k[0]] = ps.get(k[0], 0) + p
        pv[v] = pv.get(v, 0) + p
        psv[(k[0], v)] = psv.get((k[0], v), 0) + p
    return sum(p * math.log2(p / (ps[s] * pv[v])) for (s, v), p in psv.items() if p > 0)


def pid(name, m1, m2):
    """Two-source PID of I(S; V_m1, V_m2): returns dict for I_min and MMI redundancy."""
    pj = stats(name, (m1, m2))
    I1, I2, I12 = mi_from(pj, [0]), mi_from(pj, [1]), mi_from(pj, [0, 1])
    # specific information I(S=s; V_j)
    ps = {}
    for k, p in pj.items():
        ps[k[0]] = ps.get(k[0], 0) + p

    def spec(col):
        psv, pv = {}, {}
        for k, p in pj.items():
            psv[(k[0], k[1 + col])] = psv.get((k[0], k[1 + col]), 0) + p
            pv[k[1 + col]] = pv.get(k[1 + col], 0) + p
        out = {}
        for (s, v), p in psv.items():
            out[s] = out.get(s, 0) + (p / ps[s]) * math.log2((p / pv[v]) / ps[s])
        return out
    s1, s2 = spec(0), spec(1)
    red_imin = sum(ps[s] * min(s1.get(s, 0), s2.get(s, 0)) for s in ps)
    res = {"I1": I1, "I2": I2, "I12": I12}
    for tag, red in (("imin", red_imin), ("mmi", min(I1, I2))):
        res[tag] = {"red": red, "unq1": I1 - red, "unq2": I2 - red, "syn": I12 - I1 - I2 + red}
    return res


def coal_I(name, masks):
    pooled = 0
    for m in masks:
        pooled |= m
    return mi_from(stats(name, (pooled,)), [0])


def coal_V(name, pooled):
    pj = stats(name, (pooled,))
    best = {}
    for (s, v), p in pj.items():
        best.setdefault(v, {})
        best[v][s] = best[v].get(s, 0) + p
    return sum(max(d.values()) for d in best.values())


def decide(gate, name, know, i, u, T):
    kn = list(know)
    kn[i] = kn[i] | (1 << u)
    others = 0
    for j, m in enumerate(kn):
        if j != i:
            others |= m
    kind = gate["kind"]
    if kind == "CAPD_VI":
        pooled = 0
        for m in kn:
            pooled |= m
        return not T.cov[pooled]
    Ii = mi_from(stats(name, (kn[i],)), [0])
    if kind == "IND":
        return Ii <= gate["bi"] + 1e-12
    Ic = coal_I(name, tuple(kn))
    if kind == "COAL":
        return Ic <= gate["b"] + 1e-12
    if kind == "COAL_IND":
        return Ic <= gate["b"] + 1e-12 and Ii <= gate["bi"] + 1e-12
    p = pid(name, kn[i], others)[gate["pid"]]
    if kind == "SYN":
        return p["syn"] <= gate["bs"] + 1e-12
    if kind == "SYN_IND":
        return p["syn"] <= gate["bs"] + 1e-12 and Ii <= gate["bi"] + 1e-12
    raise ValueError(kind)


def gates(H):
    G = [{"kind": "CAPD_VI", "label": "CAPD_VI"}]
    fr = (0.15, 0.3, 0.5, 0.7, 0.9)
    for f in fr:
        G.append({"kind": "COAL", "b": f * H, "label": f"COAL|{f}"})
        G.append({"kind": "IND", "bi": f * H, "label": f"IND|{f}"})
        for fi in fr:
            if fi <= f:
                G.append({"kind": "COAL_IND", "b": f * H, "bi": fi * H, "label": f"COAL_IND|{f}|{fi}"})
    for tag in ("imin", "mmi"):
        for fs in (0.02, 0.05, 0.1, 0.2, 0.4):
            G.append({"kind": "SYN", "bs": fs * H, "pid": tag, "label": f"SYN_{tag}|{fs}"})
            for fi in fr:
                G.append({"kind": "SYN_IND", "bs": fs * H, "bi": fi * H, "pid": tag, "label": f"SYN_IND_{tag}|{fs}|{fi}"})
    return G


def episode(args):
    name, N, seed = args
    T = table(name)
    H = entropy(np.bincount(T.sidx, weights=T.prior))
    rng = random.Random(seed)
    m = len(T.units)
    rel = [j for j in range(m) if T.relevant >> j & 1]
    reqs = [(rng.randrange(N), rng.choice(rel) if rng.random() < 0.8 else rng.randrange(m)) for _ in range(L_REQ)]
    out = {}
    for g in gates(H):
        know = [0] * N
        served = 0
        t0 = time.perf_counter()
        for i, u in reqs:
            if know[i] >> u & 1:
                served += 1
                continue
            if decide(g, name, tuple(know), i, u, T):
                know[i] |= 1 << u
                served += 1
        pooled = 0
        for k in know:
            pooled |= k
        pair = max((coal_I(name, (know[a], know[b])) for a, b in itertools.combinations(range(N), 2)), default=0.0)
        out[g["label"]] = {"served": served / L_REQ, "I_coal": coal_I(name, tuple(know)) / H,
                           "V_coal": coal_V(name, pooled), "I_ind_max": max(mi_from(stats(name, (k,)), [0]) for k in know) / H,
                           "I_pair_max": (pair / H) if N >= 2 else None, "sec": time.perf_counter() - t0}
    return {"name": name, "N": N, "seed": seed, "H": H, "res": out}


def pid_vs_witness():
    """Does PID synergy line up with the witness structure? For every split of the units into two agents:
    is the pooled view covering a value-independent witness that neither side covers alone (a 'crossing'
    witness), and how large is the synergy?"""
    rows = []
    for name in NAMES:
        T = table(name)
        m = len(T.units)
        H = entropy(np.bincount(T.sidx, weights=T.prior))
        for a in range(1 << m):
            for b in range(1 << m):
                if a & b or not (a and b) or (a | b) & ~T.relevant:
                    continue
                cross = bool(T.cov[a | b]) and not T.cov[a] and not T.cov[b]
                p = pid(name, a, b)
                rows.append({"name": name, "cross": cross, "syn_imin": p["imin"]["syn"] / H, "syn_mmi": p["mmi"]["syn"] / H,
                             "I12": p["I12"] / H, "red_imin": p["imin"]["red"] / H})
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(n, N, s) for n in NAMES for N in (1, 2, 3, 4) for s in range(24)]
    with Pool(9) as pool:
        res = [r for r in pool.imap_unordered(episode, jobs, chunksize=2)]
    (OUT / "cand_c_raw.json").write_text(json.dumps(res) + "\n")
    (OUT / "cand_c_pid_witness.json").write_text(json.dumps(pid_vs_witness()) + "\n")
    print(len(res))


if __name__ == "__main__":
    main()
