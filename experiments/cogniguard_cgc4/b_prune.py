"""Task B: does the witness structure compress the robust LP?

Witness pruning: a candidate attacker view v whose cell cannot reach the threshold even if the requested unit is
released in full (max over its cell of V1(v + u) <= max(tau, prior V1)) can never bind, so its constraints are
dropped. Witness lumping: worlds are merged when they agree on the secret, the requested unit's outputs and
membership in every remaining cell. Both are exact by construction; we verify the optimum is unchanged and
measure the reduction. Uses the same test instances as b_exp (seeds 100000+)."""

from __future__ import annotations

import gzip
import json
import random
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from experiments.cogniguard_cgc3.common import NAMES, table
from experiments.cogniguard_cgc4.b_exp import TOL, belief, cell, excess, outputs, solve_lp, thr, util_of

OUT = Path(__file__).parent / "results"


def run(args):
    name, seed, tau, bkind = args
    T = table(name)
    rng = random.Random(seed)
    x_star = rng.choices(range(len(T.prior)), weights=T.prior)[0]
    base, unc, p, views = belief(T, rng, bkind)
    views = {v: pr for v, pr in views.items() if not T.cov[v]}
    if len(views) < 2:
        return None
    rel = [j for j in range(len(T.units)) if T.relevant >> j & 1 and not any(v >> j & 1 for v in views)]
    if not rel:
        return None
    u = rng.choice(rel)
    cells = {v: cell(T, v, x_star) for v in views}
    U = sorted(set().union(*map(set, cells.values())))
    outs, allowed = outputs(T, u, U)
    full = [cells[v] for v in views]
    keep = [cells[v] for v in views if max(T.V1[v | 1 << u, y] for y in cells[v]) > thr(T, cells[v], tau) + 1e-12]
    M0, s0 = solve_lp(T, U, outs, allowed, full, tau, x_star)
    M1, s1 = solve_lp(T, U, outs, allowed, keep, tau, x_star, lump=True) if keep else (None, None)
    if M0 is None:
        return None
    uo = lambda M: sum(T.prior[x] * sum(q * util_of(o) for o, q in M[x].items()) for x in U) / sum(T.prior[x] for x in U)
    if not keep:          # nothing can bind: release everything
        Mr = {x: {[o for o in allowed[x] if o[0] == "R"][0]: 1.0} for x in U}
        viol = any(excess(T, Mr, c, outs, tau) > TOL for c in full)
        return {"name": name, "views": len(views), "kept": 0, "same": abs(uo(M0) - 1.0) < 1e-6, "pruned_violates": viol,
                "utility_gain_vs_exact": 1.0 - uo(M0),
                "vars_full": s0["vars"], "vars_pruned": 0, "cons_full": s0["cons"], "cons_pruned": 0,
                "sec_full": s0["sec"], "sec_pruned": 0.0}
    viol = any(excess(T, M1, c, outs, tau) > TOL for c in full)
    return {"name": name, "views": len(views), "kept": len(keep), "same": abs(uo(M0) - uo(M1)) < 1e-6, "pruned_violates": viol,
            "utility_gain_vs_exact": uo(M1) - uo(M0),
            "vars_full": s0["vars"], "vars_pruned": s1["vars"], "cons_full": s0["cons"], "cons_pruned": s1["cons"],
            "sec_full": s0["sec"], "sec_pruned": s1["sec"]}


def main():
    names = [n for n in NAMES if n != "serial"]
    jobs = [(n, 100000 + s, t, b) for n in names for s in range(30) for t in (0.34, 0.5) for b in ("product", "corr")]
    with Pool(9) as pool:
        rows = [r for r in pool.imap_unordered(run, jobs, chunksize=2) if r]
    summ = {"n": len(rows), "same_optimum_share": float(np.mean([r["same"] for r in rows])),
            "views_mean": float(np.mean([r["views"] for r in rows])), "kept_views_mean": float(np.mean([r["kept"] for r in rows])),
            "share_fully_pruned": float(np.mean([r["kept"] == 0 for r in rows])),
            "pruned_solution_violates_a_dropped_view": float(np.mean([r["pruned_violates"] for r in rows])),
            "utility_gain_of_pruned_vs_exact_mean": float(np.mean([r["utility_gain_vs_exact"] for r in rows])),
            "cons_ratio_mean": float(np.mean([r["cons_pruned"] / r["cons_full"] for r in rows if r["cons_full"]])),
            "vars_ratio_mean": float(np.mean([r["vars_pruned"] / r["vars_full"] for r in rows])),
            "sec_ratio_median": float(np.median([r["sec_pruned"] / max(r["sec_full"], 1e-9) for r in rows]))}
    with gzip.open(OUT / "b_prune_raw.json.gz", "wt") as h:
        json.dump(rows, h, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    (OUT / "b_prune_summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(summ)


if __name__ == "__main__":
    main()
