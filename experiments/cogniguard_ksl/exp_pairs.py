"""Experiment 2 (exact): paired states.

(A) Same complete-witness verdict, different attacker guessing power (and Shannon vs min-entropy disagreement).
(B) Governance uncertainty: the governor's posterior over the attacker's knowledge K is a product of
    Bernoulli(p_u) over uncertain units (exactly the L3h state model). For a pending release M we compute,
    by exact enumeration over K:
      E[V1]       expected Bayes vulnerability after release (QIF expected vulnerability of the hyper)
      P_harm      P(V1(K u M) >= tau | E)                 (chance-constraint / Bayes 0-1 risk statistic)
      H_K         H(K|E) over the uncertain units          (governance entropy)
      H_K_rel     H(K|E) restricted to units that can change V1 after M
      VoI1        myopic value of verifying one unit for the Bayes decision with costs (1, rho)
      VoI2        value of verifying two units (non-myopic, both answers seen before deciding)
    and look for pairs that share one quantity but differ in another.
"""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np

from experiments.cogniguard_ksl import engine, structures as S

OUT = Path(__file__).parent / "results"
TAU, DELTA = 0.5, 0.1
RHO = DELTA / (1 - DELTA)     # refusal cost relative to harm cost: Bayes rule blocks iff P_harm > DELTA


def h2(p):
    return 0.0 if p <= 0 or p >= 1 else -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def hyper(T, x, base, unc, M):
    """unc: {unit: p}. Returns the list of (prob, V1 after release) over K = base + subset(unc)."""
    names = list(unc)
    out = []
    for bits in itertools.product((0, 1), repeat=len(names)):
        pr = 1.0
        mask = base | M
        for b, u in zip(bits, names):
            pr *= unc[u] if b else 1 - unc[u]
            if b:
                mask |= T.bit(u)
        out.append((pr, float(T.V1[mask, x]), bits))
    return names, out


def bayes_risk(hy):
    ph = sum(p for p, v, _ in hy if v >= TAU - 1e-12)
    return min(ph, RHO * (1 - ph)) if True else None, ph


def risk_of(hy):
    tot = sum(p for p, _, _ in hy)
    if tot <= 0:
        return 0.0
    ph = sum(p for p, v, _ in hy if v >= TAU - 1e-12) / tot
    return tot * min(ph * 1.0, RHO * (1 - ph))      # release costs 1 per harm; refuse costs RHO per benign


def stats(T, x, base, unc, M):
    names, hy = hyper(T, x, base, unc, M)
    ph = sum(p for p, v, _ in hy if v >= TAU - 1e-12)
    ev = sum(p * v for p, v, _ in hy)
    r0 = risk_of(hy)
    voi1 = {}
    for i, u in enumerate(names):
        r = sum(risk_of([t for t in hy if t[2][i] == b]) for b in (0, 1))
        voi1[u] = r0 - r
    voi2 = 0.0
    for i, j in itertools.combinations(range(len(names)), 2):
        r = sum(risk_of([t for t in hy if t[2][i] == a and t[2][j] == b]) for a in (0, 1) for b in (0, 1))
        voi2 = max(voi2, r0 - r)
    relv = [u for i, u in enumerate(names) if any(
        abs(a[1] - b[1]) > 1e-12 for a in hy for b in hy if a[2][:i] + a[2][i + 1:] == b[2][:i] + b[2][i + 1:] and a[2][i] != b[2][i])]
    return {"E_V1": ev, "P_harm": ph, "decision_bayes": "block" if ph > DELTA else "release",
            "decision_mean": "block" if ev >= TAU else "release",
            "H_K": sum(h2(p) for p in unc.values()), "H_K_rel": sum(h2(unc[u]) for u in relv),
            "VoI1_max": max(voi1.values()) if voi1 else 0.0, "VoI2_max": voi2, "relevant_uncertain": relv}


def part_a():
    rows = []
    for st in S.all_structures():
        T = engine.build(st)
        nonw = [k for k in range(len(T.V1)) if not T.cov[k] and k & T.relevant]
        ev = T.V1[nonw] @ T.prior
        es = T.H[nonw] @ T.prior
        lo, hi = nonw[int(np.argmin(ev))], nonw[int(np.argmax(ev))]
        rows.append({"structure": st.name, "capd_verdict_both": "no witness covered",
                     "low_view": T.names(lo), "low_E_V1": float(T.V1[lo] @ T.prior), "low_E_H": float(T.H[lo] @ T.prior),
                     "high_view": T.names(hi), "high_E_V1": float(T.V1[hi] @ T.prior), "high_E_H": float(T.H[hi] @ T.prior),
                     "prior_V1": T.prior_V1(), "prior_H": float(T.H[0, 0])})
        # Shannon vs min-entropy disagreement among non-covering views: same E[V1], different E[H]
        best = None
        for i, a in enumerate(nonw):
            for j, b in enumerate(nonw):
                if j <= i or abs(ev[i] - ev[j]) > 1e-9:
                    continue
                gap = abs(es[i] - es[j])
                if best is None or gap > best[0]:
                    best = (gap, a, b)
        if best and best[0] > 1e-6:
            rows[-1]["same_V1_diff_H"] = {"views": [T.names(best[1]), T.names(best[2])],
                                          "E_V1": float(T.V1[best[1]] @ T.prior),
                                          "E_H": [float(T.H[best[1]] @ T.prior), float(T.H[best[2]] @ T.prior)]}
    # realized pair, AND/max: same view (in_a), same witness status, different realized V1
    T = engine.build(S.and_join("max"))
    m = T.mask(["in_a"])
    rows.append({"structure": "and_max realized", "view": ["in_a"],
                 "V1_if_a=3": float(T.V1[m, [i for i, w in enumerate(T.st.worlds) if w[0][0] == 3][0]]),
                 "V1_if_a=0": float(T.V1[m, [i for i, w in enumerate(T.st.worlds) if w[0][0] == 0][0]])})
    return rows


def part_b():
    """Exact constructions on the relation structure (true matching = identity)."""
    T = engine.build(S.relation())
    x = [i for i, w in enumerate(T.st.worlds) if w[0] == (0, 1, 2, 3)][0]
    b = T.bit
    M = b("adv_of_s1")
    cases = {
        # same expected risk statistic, different governance entropy
        "G1 certain K={s0}": (b("adv_of_s0"), {}),
        "G2 s0 uncertain p=.95, decoys unknown": (0, {"adv_of_s0": 0.95, "d_room": 0.5, "d_shift": 0.5}),
        # same governance entropy, opposite decisions
        "G3 s0 p=.5": (0, {"adv_of_s0": 0.5}),
        "G4 decoy p=.5 (s0 absent)": (0, {"d_room": 0.5}),
        # same entropy, myopic VoI = 0 but two-step VoI > 0 (AND of two uncertain units)
        "G5 s2,s3 p=.3 each": (0, {"adv_of_s2": 0.3, "adv_of_s3": 0.3}),
        "G6 s0 p=.3, decoy p=.3": (0, {"adv_of_s0": 0.3, "d_room": 0.3}),
    }
    out = {}
    for name, (base, unc) in cases.items():
        out[name] = stats(T, x, base, unc, M)
    return out


def grid_b():
    """Grid over two uncertain witness-relevant units + one decoy: is H(K|E) informative about the Bayes
    decision or about VoI once P_harm is known?"""
    T = engine.build(S.relation())
    x = [i for i, w in enumerate(T.st.worlds) if w[0] == (0, 1, 2, 3)][0]
    M = T.bit("adv_of_s1")
    ps = [0.02, 0.1, 0.3, 0.5, 0.7, 0.9, 0.98]
    rows = []
    for p0, p2, pd in itertools.product(ps, ps, ps):
        s = stats(T, x, 0, {"adv_of_s0": p0, "adv_of_s2": p2, "d_room": pd}, M)
        rows.append({"p": [p0, p2, pd], **{k: v for k, v in s.items() if k != "relevant_uncertain"}})
    a = np.array([[r["H_K"], r["H_K_rel"], r["P_harm"], r["VoI1_max"], r["VoI2_max"], r["decision_bayes"] == "block"] for r in rows], float)

    def spearman(u, v):
        ru, rv = np.argsort(np.argsort(u)), np.argsort(np.argsort(v))
        return float(np.corrcoef(ru, rv)[0, 1])
    # same H_K bucket, different Bayes decision
    buckets = {}
    for r in rows:
        buckets.setdefault(round(r["H_K"], 6), set()).add(r["decision_bayes"])
    return {"n_states": len(rows),
            "spearman_H_K_vs_VoI1": spearman(a[:, 0], a[:, 3]), "spearman_H_K_rel_vs_VoI1": spearman(a[:, 1], a[:, 3]),
            "spearman_Pharm_term_vs_VoI1": spearman(np.minimum(a[:, 2], RHO * (1 - a[:, 2])), a[:, 3]),
            "frac_H_K_levels_with_both_decisions": float(np.mean([len(v) == 2 for v in buckets.values()])),
            "decision_is_function_of_P_harm": True,
            "states_VoI1_zero_but_VoI2_positive": int(np.sum((a[:, 3] < 1e-12) & (a[:, 4] > 1e-9)))}


def cells(T, mask):
    st = T.st
    names = T.names(mask)
    key = [tuple(st.units[u](w) for u in names) for w in st.worlds]
    ids = {}
    return np.array([ids.setdefault(k, len(ids)) for k in key])


def post_V1(T, sel):
    """Bayes vulnerability of S given that the true world lies in the boolean selection `sel`."""
    w = T.prior * sel
    if w.sum() <= 0:
        return None
    ps = np.bincount(T.sidx, weights=w, minlength=len(T.svals)) / w.sum()
    return float(ps.max())


def part_c(tau=TAU, delta=DELTA):
    """Denials leak (Kenthapadi, Mishra, Nissim 2005), exact, single agent, knowledge known to the governor.
    Gates: CAPD (value-independent witness coverage), REAL (refuse iff realized V1 after release >= tau and
    increases; depends on the unreleased values), SIM (refuse iff P(harm | attacker's current view) > delta;
    a function of what the attacker already knows, hence simulatable). For every non-covering view K, relevant
    unit u not in K and world x: harm, over-refusal and denial leak (the refusal itself lifts V1(S | view,
    refused) to >= tau)."""
    out = {}
    for st in S.all_structures():
        T = engine.build(st)
        m = len(T.units)
        rel = [j for j in range(m) if T.relevant >> j & 1]
        tot = {g: {"harm": 0.0, "harm_req": 0.0, "ref_benign": 0.0, "benign": 0.0, "denial_leak": 0.0, "refused": 0.0}
               for g in ("CAPD", "REAL", "SIM")}
        n_pairs = 0
        for K in range(1 << m):
            if T.cov[K] or not K & T.relevant:
                continue
            gid = cells(T, K)
            for j in rel:
                if K >> j & 1:
                    continue
                n_pairs += 1
                Ku = K | 1 << j
                harm = (T.V1[Ku] >= tau - 1e-12) & (T.V1[Ku] > T.V1[K] + 1e-12)          # per world
                # SIM: P(harm | attacker's view) computed within the attacker's cell
                ph = np.zeros(len(T.prior))
                for g in np.unique(gid):
                    sel = gid == g
                    ph[sel] = (T.prior[sel] * harm[sel]).sum() / T.prior[sel].sum()
                gates = {"CAPD": np.full(len(T.prior), bool(T.cov[Ku])), "REAL": harm.copy(), "SIM": ph > delta}
                for g, ref in gates.items():
                    w = T.prior
                    t = tot[g]
                    t["harm"] += (w * (harm & ~ref)).sum()
                    t["harm_req"] += (w * harm).sum()
                    t["ref_benign"] += (w * (~harm & ref)).sum()
                    t["benign"] += (w * ~harm).sum()
                    t["refused"] += (w * ref).sum()
                    # denial leak: attacker sees its view (cell) and the refusal; posterior restricted to refusing worlds
                    for c in np.unique(gid[ref]):
                        sel = (gid == c) & ref
                        v = post_V1(T, sel.astype(float))
                        before = post_V1(T, (gid == c).astype(float))
                        if v is not None and v >= tau - 1e-12 and v > before + 1e-12:
                            t["denial_leak"] += (w * sel).sum()
        out[st.name] = {g: {"harm_rate": t["harm"] / max(t["harm_req"], 1e-12),
                            "over_refusal": t["ref_benign"] / max(t["benign"], 1e-12),
                            "denial_leak_share_of_refusals": t["denial_leak"] / max(t["refused"], 1e-12),
                            "denial_leak_per_request": t["denial_leak"] / n_pairs} for g, t in tot.items()}
    return out


def main():
    OUT.mkdir(exist_ok=True)
    res = {"tau": TAU, "delta": DELTA, "A_same_witness_diff_guessing": part_a(), "B_constructions": part_b(), "B_grid": grid_b(),
           "C_denials_leak": part_c()}
    (OUT / "pairs.json").write_text(json.dumps(res, indent=1) + "\n")
    for k, v in res["B_constructions"].items():
        print(f"{k:42} EV1={v['E_V1']:.3f} Ph={v['P_harm']:.3f} HK={v['H_K']:.2f} HKrel={v['H_K_rel']:.2f} "
              f"VoI1={v['VoI1_max']:.3f} VoI2={v['VoI2_max']:.3f} bayes={v['decision_bayes']} mean={v['decision_mean']}")
    print(json.dumps(res["B_grid"], indent=1))
    for st, g in res["C_denials_leak"].items():
        print(st, {k: {a: round(b, 3) for a, b in v.items()} for k, v in g.items()})


if __name__ == "__main__":
    main()
