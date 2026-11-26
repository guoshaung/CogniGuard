"""P0 section 4.1 numerical checks of the mathematical relations (MATH_P0.md). Writes results/checks.json.

C1  H2 vs Koepf-Basin Shannon adaptive leakage, computed independently by brute-force enumeration of all
    deterministic attack trees (det propagation, no relays, h = 2).
C2  unrestricted acquisition (E = all units, p = 1, budget >= m, h >= m, no relays): H2 == H1 when the units
    jointly determine S.
C3  det propagation, unit cost, no relays: worst-case crossing within h (any strategy) <=> d_acc <= h.
C4  complete gating (every channel gated with the pooled coalition, k = N): zero crossings.
C5  exact p_cross vs Monte Carlo sampling (implementation check).
C6  minimal counterexamples: (a) equal (V1_obs, H1_obs, d_capd, d_acc, coalition, n_wit_h) but different R_star;
    (b) H2 ordering opposite to R_star.
"""

from __future__ import annotations

import gzip
import itertools
import json
import random
from pathlib import Path

import numpy as np

from experiments.cogniguard_lh2 import model as M

OUT = Path(__file__).parent / "results"


def det_inst(S, w, E, h_budget=99):
    return {"w": w, "E": E, "c": [1] * S.m, "RA": 0, "RB": 0, "RC": 0, "p_ext": 1.0, "p_rel": 0.0, "topo": "star"}


def kb_bruteforce(S, inst, A, h):
    """Koepf-Basin: min over all deterministic adaptive strategies (explicit trees) of E[H(S | leaf)]."""
    w = inst["w"]
    cell0 = S.cell(A, w)

    def trees(A, cell, s):
        # enumerate every strategy tree; yield its expected terminal entropy
        opts = list(M.bits(inst["E"] & ~A))
        if s == 0 or not opts:
            yield S.Hc(cell)
            return
        for j in opts:
            parts = S.split(cell, j)
            subs = [list(trees(A | 1 << j, c, s - 1)) for _, c in parts]
            for combo in itertools.product(*subs):
                yield sum(p * v for (p, _), v in zip(parts, combo))

    return S.Hc(cell0) - min(trees(A, cell0, h))


def main():
    rng = random.Random(0)
    out = {}
    # C1
    c1 = []
    for name in M.STRUCTS:
        S = M.Struct(name)
        for _ in range(15):
            w = rng.randrange(S.nw)
            E = sum(1 << j for j in range(S.m) if rng.random() < 0.7)
            A = sum(1 << j for j in range(S.m) if not E >> j & 1 and rng.random() < 0.4)
            inst = det_inst(S, w, E)
            a = M.H2_state(S, inst, A, 99, 2)
            b = kb_bruteforce(S, inst, A, 2)
            c1.append(abs(a - b))
    out["C1_H2_vs_KB_bruteforce"] = {"n": len(c1), "max_abs_diff": float(max(c1))}
    # C2
    c2 = []
    for name in M.STRUCTS:
        S = M.Struct(name)
        determines = bool(S.T.cov[S.allmask])
        for _ in range(15):
            w = rng.randrange(S.nw)
            A = sum(1 << j for j in range(S.m) if rng.random() < 0.3)
            inst = det_inst(S, w, S.allmask)
            h2 = M.H2_state(S, inst, A, 99, S.m)
            h1 = S.Hc(S.cell(A, w))
            c2.append({"struct": name, "units_determine_S": determines, "diff": h1 - h2})
    out["C2_unrestricted_H2_eq_H1"] = {"n": len(c2), "max_abs_diff_when_determined":
                                      float(max(abs(r["diff"]) for r in c2 if r["units_determine_S"]))}
    # C3
    agree, n = 0, 0
    for name in M.STRUCTS:
        S = M.Struct(name)
        for _ in range(40):
            w = rng.randrange(S.nw)
            E = sum(1 << j for j in range(S.m) if rng.random() < 0.5)
            A = sum(1 << j for j in range(S.m) if not E >> j & 1 and rng.random() < 0.3)
            ders = S.derivations(w)
            for h in (1, 2, 3):
                worst = any(S.cross[A | sum(1 << j for j in comb), w]
                            for r in range(h + 1) for comb in itertools.combinations(list(M.bits(E & ~A)), r))
                d_acc = min((M.popcount(d & ~A) for d in ders if d & ~(A | E) == 0), default=99)
                agree += worst == (d_acc <= h)
                n += 1
    out["C3_worstcase_cross_iff_dacc_le_h"] = {"n": n, "agree": agree}
    # C4: complete gating -- every acquisition on every channel is checked against the pooled knowledge
    crossings, steps = 0, 0
    for name in M.STRUCTS:
        S = M.Struct(name)
        ders_cache = {}
        for seed in range(200):
            inst = M.gen_instance(10 ** 9 + seed, name, "line", "det", "unit")
            w = inst["w"]
            ders = ders_cache.setdefault(w, S.derivations(w))
            pool = 0
            for x in (inst["RA"], inst["RB"], inst["RC"], inst["hidden"]):
                cand = pool | x
                if not any(d & ~cand == 0 for d in ders):
                    pool = cand
            A = pool
            for _ in range(M.H):
                for j in M.bits(inst["E"] & ~A):
                    if not any(d & ~(A | 1 << j) == 0 for d in ders):
                        A |= 1 << j
                        break
                steps += 1
                crossings += bool(S.cross[A, w])
    out["C4_complete_gating_crossings"] = {"steps": steps, "crossings": crossings}
    # C5
    c5 = []
    for name in M.STRUCTS:
        S = M.Struct(name)
        for seed in range(6):
            inst = M.gen_instance(2 * 10 ** 9 + seed, name, "star", "rand", "varied")
            A = inst["RA"] | inst["hidden"]
            ex = M.p_cross(S, inst, A, inst["RB"], inst["RC"], inst["bud0"], inst["atype"], M.H)
            hits = 0
            for r in range(3000):
                inst["label_rng"] = r
                hits += M.sample_cross(S, inst, M.H)[0]
            c5.append(abs(ex - hits / 3000))
    out["C5_exact_vs_mc_pcross"] = {"n": len(c5), "max_abs_diff": float(max(c5)), "mc_n": 3000}
    # C6 from dev rows
    rows = json.load(gzip.open(OUT / "dev_rows.json.gz", "rt"))
    keys = ("struct", "V1_obs", "H1_obs", "d_capd", "d_acc", "coalition", "n_wit_h")
    groups = {}
    for r in rows:
        groups.setdefault(tuple(round(r[k], 9) if isinstance(r[k], float) else r[k] for k in keys), []).append(r)
    diff = [(g, v) for g, v in groups.items() if max(x["R_star"] for x in v) - min(x["R_star"] for x in v) > 0.2]
    ex6a = []
    for g, v in sorted(diff, key=lambda gv: -(max(x["R_star"] for x in gv[1]) - min(x["R_star"] for x in gv[1])))[:5]:
        lo, hi = min(v, key=lambda x: x["R_star"]), max(v, key=lambda x: x["R_star"])
        ex6a.append({"shared": dict(zip(keys, g)), "low": {k: lo[k] for k in ("seed", "R_star", "H2", "KB_min", "topo", "prop", "E", "RB", "RC")},
                     "high": {k: hi[k] for k in ("seed", "R_star", "H2", "KB_min", "topo", "prop", "E", "RB", "RC")}})
    inv = 0
    pairs = 0
    rr = np.random.default_rng(0)
    for _ in range(20000):
        a, b = rows[rr.integers(len(rows))], rows[rr.integers(len(rows))]
        if a["struct"] != b["struct"] or abs(a["R_star"] - b["R_star"]) < 0.2 or abs(a["H2"] - b["H2"]) < 1e-9:
            continue
        pairs += 1
        inv += (a["R_star"] - b["R_star"]) * (a["H2"] - b["H2"]) < 0
    out["C6a_same_structural_indicators_diff_Rstar"] = {"groups": len(groups), "groups_with_Rstar_range>0.2": len(diff), "examples": ex6a}
    out["C6b_H2_vs_Rstar_discordant_pairs"] = {"pairs": pairs, "discordant": inv}
    (OUT / "checks.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps({k: v for k, v in out.items() if not k.startswith("C6a")}, indent=1))
    print("C6a", out["C6a_same_structural_indicators_diff_Rstar"]["groups_with_Rstar_range>0.2"])


if __name__ == "__main__":
    main()
