"""Exact attacker-side quantities for every (view, true world) pair of a small structure.

For a view K (a set of units, encoded as a bitmask) and true world x*, the attacker's realized posterior is
P(S = s | f_u(x) = f_u(x*) for u in K) under the structure's synthetic prior. From it we tabulate:

  V1   Bayes vulnerability (one-guess success probability of the Bayes-optimal guesser) = 2^-H_inf
  H    Shannon entropy H(S | V = v) of the realized posterior, bits
  Vg   g-vulnerability with the structure's partial-credit gain function
  P3   3-tries vulnerability (sum of the top-3 posterior masses)
  pst  posterior mass on the true secret
  det  the realized view determines S (V1 == 1)

cov[mask] (complete witness coverage) holds iff the view determines S for EVERY world, i.e. the units form a
value-independent witness. Minimal covered masks are the witness family handed to the unchanged CA-PD kernel.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cogniguard.governance.reconstruction import check_release, residual_distance
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry

RES = "asset"


@dataclass
class Tables:
    st: object
    units: list
    prior: np.ndarray        # (n,)
    sidx: np.ndarray         # (n,) secret index per world
    svals: list
    V1: np.ndarray           # (2^m, n)
    H: np.ndarray
    Vg: np.ndarray
    P3: np.ndarray
    pst: np.ndarray
    det: np.ndarray          # bool
    cov: np.ndarray          # (2^m,) bool
    witnesses: list          # list of masks
    relevant: int            # mask of units that ever change the posterior of S

    def bit(self, name):
        return 1 << self.units.index(name)

    def mask(self, names):
        m = 0
        for n in names:
            m |= self.bit(n)
        return m

    def names(self, mask):
        return [u for i, u in enumerate(self.units) if mask >> i & 1]

    def prior_V1(self):
        return float(self.V1[0, 0])


def build(st, prior=None) -> Tables:
    worlds, units = st.worlds, st.unit_names
    n, m = len(worlds), len(units)
    svals = sorted({st.secret(w) for w in worlds}, key=repr)
    sid = {s: i for i, s in enumerate(svals)}
    sidx = np.array([sid[st.secret(w)] for w in worlds])
    pr = np.full(n, 1.0 / n) if prior is None else np.asarray(prior, float) / np.sum(prior)
    obs = np.zeros((n, m), dtype=np.int64)
    for j, u in enumerate(units):
        vals = {}
        for i, w in enumerate(worlds):
            obs[i, j] = vals.setdefault(st.units[u](w), len(vals))
    G = np.array([[st.gain(g, s) for s in svals] for g in svals])      # G[guess, secret]
    ns = len(svals)
    M = 1 << m
    V1, H, Vg, P3, pst = (np.zeros((M, n)) for _ in range(5))
    for mask in range(M):
        cols = [j for j in range(m) if mask >> j & 1]
        if cols:
            _, inv = np.unique(obs[:, cols], axis=0, return_inverse=True)
            inv = inv.reshape(-1)
        else:
            inv = np.zeros(n, dtype=np.int64)
        ng = inv.max() + 1
        P = np.zeros((ng, ns))
        np.add.at(P, (inv, sidx), pr)
        P /= P.sum(1, keepdims=True)
        srt = -np.sort(-P, 1)
        with np.errstate(divide="ignore", invalid="ignore"):
            h = -np.nansum(np.where(P > 0, P * np.log2(P), 0.0), 1)
        V1[mask] = srt[inv, 0]
        P3[mask] = srt[inv, :3].sum(1)
        H[mask] = h[inv]
        Vg[mask] = (P @ G.T).max(1)[inv]
        pst[mask] = P[inv, sidx]
    det = V1 > 1 - 1e-12
    cov = det.all(1)
    wit = [k for k in range(M) if cov[k] and not any(cov[k & ~(1 << j)] for j in range(m) if k >> j & 1)]
    rel = 0
    for j in range(m):
        if any(np.abs(V1[k | 1 << j] - V1[k]).max() > 1e-12 or np.abs(H[k | 1 << j] - H[k]).max() > 1e-12
               for k in range(M) if not k >> j & 1):
            rel |= 1 << j
    return Tables(st, units, pr, sidx, svals, V1, H, Vg, P3, pst, det, cov, wit, rel)


def cell_ids(T: Tables) -> np.ndarray:
    """(2^m, n): id of the attacker's observation cell for every view mask and world."""
    st, units = T.st, T.units
    n, m = len(st.worlds), len(units)
    obs = np.zeros((n, m), dtype=np.int64)
    for j, u in enumerate(units):
        vals = {}
        for i, w in enumerate(st.worlds):
            obs[i, j] = vals.setdefault(st.units[u](w), len(vals))
    out = np.zeros((1 << m, n), dtype=np.int64)
    for mask in range(1 << m):
        cols = [j for j in range(m) if mask >> j & 1]
        if cols:
            out[mask] = np.unique(obs[:, cols], axis=0, return_inverse=True)[1].reshape(-1)
    return out


# ---------------------------------------------------------------- CA-PD kernel adapter (kernel unchanged)

def registry(T: Tables):
    tgt = ProtectedTarget(target_id=T.st.name, owner_principal_id="owner", org_id="org",
                          witness_sets=tuple(frozenset((RES, u) for u in T.names(w)) for w in T.witnesses))
    return TargetRegistry([tgt])


def refs(T: Tables, mask):
    return frozenset((RES, u) for u in T.names(mask))


def capd_safe(T: Tables, reg, recipient: str, release_mask: int, know: dict, k: int) -> bool:
    """CA-PD verdict through the unchanged kernel. know: agent -> unit mask."""
    kn = {a: refs(T, m) for a, m in know.items()}
    return check_release(reg, recipient, refs(T, release_mask), kn, k).safe


def capd_distance(T: Tables, reg, recipient: str, release_mask: int, know: dict, k: int) -> int:
    kn = {a: refs(T, m) for a, m in know.items()}
    d = residual_distance(reg, recipient, refs(T, release_mask), kn, k)
    return min(d.values()) if d else 10 ** 6
