"""Shared exact substrate for the three CGC v3 candidates.

Reuses the KSL structures (finite worlds, secret, units as deterministic observations). Following
docs/FORMAL_DEFINITION_v0.1.md, a disclosed unit is the predicate "f_u = f_u(x*)" that holds at the true
world, and safety is L*(K) <= tau with L*(K) = max_{B subset of K} log2(V1(B, x*) / V1_prior) (monotone
closure). Derivation sets are the minimal masks with L* > tau. All priors and task pools are synthetic.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from experiments.cogniguard_ksl import engine, structures as S


@lru_cache(maxsize=None)
def table(name):
    st = {s.name: s for s in S.all_structures()}[name]
    T = engine.build(st)
    T.gid = engine.cell_ids(T)
    return T


NAMES = [s.name for s in S.all_structures()]


def lstar(T, x):
    """(2^m,) monotone-closure leakage at world x, bits."""
    m = len(T.units)
    L = np.log2(T.V1[:, x] / T.V1[0, x])
    out = L.copy()
    for mask in range(1, 1 << m):
        b = mask
        while b:
            j = b & -b
            out[mask] = max(out[mask], out[mask ^ j])
            b ^= j
    return out


def entropy(p):
    p = np.asarray(p, float)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def joint(T, masks):
    """Joint pmf over (S, cell ids of each mask) as a dict {(s, c1, c2, ...): p}."""
    out = {}
    for i in range(len(T.prior)):
        key = (int(T.sidx[i]),) + tuple(int(T.gid[m, i]) for m in masks)
        out[key] = out.get(key, 0.0) + float(T.prior[i])
    return out


def mi(T, mask):
    """I(S; V_mask), bits (channel level, averaged over worlds)."""
    pj = joint(T, [mask])
    ps, pv = {}, {}
    for (s, v), p in pj.items():
        ps[s] = ps.get(s, 0) + p
        pv[v] = pv.get(v, 0) + p
    return sum(p * math.log2(p / (ps[s] * pv[v])) for (s, v), p in pj.items() if p > 0)
