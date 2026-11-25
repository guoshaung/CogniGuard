"""CGC4 analysis: Task A (test seeds, dev-chosen parameters), Task B, Task AB. Paired bootstrap 95% CIs."""

from __future__ import annotations

import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

R = Path(__file__).parent / "results"
rng = np.random.default_rng(0)
TOL = 1e-7


def boot(d, n=4000):
    d = np.asarray([x for x in d if x is not None], float)
    if len(d) == 0:
        return None
    bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(n)]
    return {"mean": float(d.mean()), "lo": float(np.quantile(bs, .025)), "hi": float(np.quantile(bs, .975)), "n": int(len(d))}


def fam(label):
    return label.split("|")[0]


# ------------------------------------------------------------------ A

def analyze_a():
    rows = json.load(gzip.open(R / "a_test_raw.json.gz", "rt"))
    ch = json.loads((R / "a_dev_choices.json").read_text())["choice"]
    cond = lambda r: r["meta"].get("cond")
    out = {"choice": ch, "conditions": {}, "paired": {}, "horizon": {}}
    conds = sorted({cond(r) for r in rows})
    for c in conds:
        rs = [r for r in rows if cond(r) == c]
        main = [l for l in rs[0]["res"] if l in {k for r in rs for k in r["res"]}]
        tab = {}
        for lab in sorted({l for r in rs for l in r["res"]}):
            rr = [r for r in rs if lab in r["res"]]
            if len(rr) < len(rs) * 0.5:
                continue
            get = lambda q, k: [r["res"][lab][q][k] for r in rr if q in r["res"][lab] and r["res"][lab][q][k] is not None]
            tab[lab] = {q: {"completion": float(np.mean(get(q, "completion"))) if get(q, "completion") else None,
                            "shift_completion": float(np.mean(get(q, "shift_completion"))) if q == "emp" and get(q, "shift_completion") else None,
                            "ms": float(np.mean(get(q, "ms_per_decision"))) if get(q, "ms_per_decision") else None,
                            "peak_mem_kb": float(np.mean(get(q, "peak_mem_kb"))) if get(q, "peak_mem_kb") else None,
                            "cache": float(np.mean(get(q, "cache_entries"))) if get(q, "cache_entries") else None,
                            "unsafe_episodes": int(sum(get(q, "unsafe_episodes"))),
                            "final_V1": float(np.mean(get(q, "final_V1"))) if get(q, "final_V1") else None}
                        for q in ("true", "emp", "unif") if any(q in r["res"][lab] for r in rr)}
        n = {"instances": len(rs), "n": float(np.mean([r["n"] for r in rs])), "m": float(np.mean([r["m"] for r in rs])),
             "P": float(np.mean([r["P"] for r in rs])), "H": float(np.mean([r["H"] for r in rs]))}
        out["conditions"][c] = {"size": n, "table": tab}
        # paired differences (instance means), q_hat = emp unless the policy has only 'true'
        def lab_of(f):
            ls = [l for l in tab if fam(l) == f]
            # default variant = the one from the main spec (first in rows' res order)
            for l in rs[0]["res"]:
                if fam(l) == f:
                    return l
            return ls[0] if ls else None

        def series(lab, q="emp", key="completion"):
            qq = q if q in rs[0]["res"].get(lab, {}) else "true"
            return {tuple(r["key"]): r["res"][lab][qq][key] for r in rs if lab in r["res"] and qq in r["res"][lab]}
        pairs = {}
        base = lab_of("CAPD_FIRST")
        for f in ("A0", "A1", "A1_DRO", "MPC", "BEAM", "SAA", "SAA_DEFER", "OPT_SERVE", "OPT"):
            lf = lab_of(f)
            if not lf:
                continue
            a, b = series(lf), series(base, "true")
            ks = set(a) & set(b)
            pairs[f"{f} - CAPD_FIRST"] = boot([a[k] - b[k] for k in ks])
            a1 = series(lab_of("A1"))
            if f != "A1":
                ks = set(a) & set(a1)
                pairs[f"{f} - A1"] = boot([a[k] - a1[k] for k in ks])
            # distribution shift (planner's q from history, test sequences from a shifted q)
            sa, sb = series(lf, "emp", "shift_completion"), series(base, "true", "completion")
        for f in ("A1", "A1_DRO", "MPC", "SAA", "OPT"):
            lf = lab_of(f)
            if lf:
                a1s = series(lab_of("A1"), "emp", "shift_completion")
                fs = series(lf, "emp", "shift_completion")
                ks = [k for k in set(a1s) & set(fs) if a1s[k] is not None and fs[k] is not None]
                if f != "A1":
                    pairs[f"{f} - A1 | shifted q"] = boot([fs[k] - a1s[k] for k in ks])
        lA1, lO = lab_of("A1"), lab_of("OPT")
        if lO:
            a, o, b = series(lA1), series(lO), series(base, "true")
            ks = set(a) & set(o) & set(b)
            num = np.array([a[k] - b[k] for k in ks])
            den = np.array([o[k] - b[k] for k in ks])
            pairs["A1 share of OPT gain (ratio of means)"] = float(num.sum() / den.sum()) if den.sum() > 0 else None
        out["paired"][c] = pairs
        sub = [r for r in rs if any(l.startswith("MPC|d=1") for l in r["res"])]
        if sub:
            hz = {}
            a1 = lab_of("A1")
            for l in sorted({l for r in sub for l in r["res"] if fam(l) in ("MPC", "SAA")}):
                d = [r["res"][l]["emp"]["completion"] - r["res"][a1]["emp"]["completion"] for r in sub if l in r["res"]]
                hz[l] = {"completion": float(np.mean([r["res"][l]["emp"]["completion"] for r in sub if l in r["res"]])),
                         "minus_A1": boot(d), "ms": float(np.mean([r["res"][l]["emp"]["ms_per_decision"] for r in sub if l in r["res"]]))}
            hz["A1"] = {"completion": float(np.mean([r["res"][a1]["emp"]["completion"] for r in sub])),
                        "ms": float(np.mean([r["res"][a1]["emp"]["ms_per_decision"] for r in sub]))}
            out["horizon"][c] = {"n_instances": len(sub), **hz}
    return out


# ------------------------------------------------------------------ B

def analyze_b():
    raw = json.load(gzip.open(R / "b_raw.json.gz", "rt"))
    uv, ma = raw["unknown_view"], raw["multi_agent"]
    out = {"n_instances": len(uv), "by_setting": {}, "compression": {}, "multi_agent": {}}
    settings = {"product belief (exact model)": [(r, "exact") for r in uv if r["belief"] == "product"],
                "correlated belief (exact model)": [(r, "exact") for r in uv if r["belief"] == "corr"],
                "correlated truth, product-approx model": [(r, "product_approx") for r in uv if r["belief"] == "corr" and "product_approx" in r["res"]]}
    mechs = ["ORACLE_LP", "ROBUST_LP", "CHANCE_LP_0.05", "CHANCE_LP_0.2", "MAP_LP", "SIM_ROBUST", "STEP_QIF", "CAPD_F", "ROBUST_LP+timing"]
    for sname, items in settings.items():
        tab = {}
        for m in mechs:
            vals = [r["res"][mod].get(m) for r, mod in items]
            ok = [v for v in vals if v]
            if not ok:
                continue
            tab[m] = {"feasible_share": len(ok) / len(vals),
                      "utility": boot([v["utility_U"] for v in ok]),
                      "utility_at_xstar": float(np.mean([v["utility_at_xstar"] for v in ok])),
                      "violates_true_view": float(np.mean([v["violates_true_view"] for v in ok])),
                      "mean_p_violation": float(np.mean([v["p_violation_under_true_belief"] for v in ok])),
                      "max_excess": float(max(v["true_view_excess"] for v in ok)),
                      "violating_with_mi_below_0.1bit": float(np.mean([v["violates_true_view"] and v["mi_true_view"] < 0.1 for v in ok])),
                      "lp_sec": float(np.mean([v["lp"]["sec"] for v in ok if "lp" in v])) if any("lp" in v for v in ok) else None}
        # paired utility differences on instances where both are feasible
        pd = {}
        for a, b in (("ROBUST_LP", "ORACLE_LP"), ("ROBUST_LP", "SIM_ROBUST"), ("ROBUST_LP", "STEP_QIF"), ("MAP_LP", "ROBUST_LP"),
                     ("CHANCE_LP_0.05", "ROBUST_LP"), ("CHANCE_LP_0.2", "ROBUST_LP")):
            d = [r["res"][mod][a]["utility_U"] - r["res"][mod][b]["utility_U"] for r, mod in items
                 if r["res"][mod].get(a) and r["res"][mod].get(b)]
            pd[f"{a} - {b}"] = boot(d)
        tab["paired"] = pd
        out["by_setting"][sname] = tab
    comp = [r["res"]["exact"]["compression"] for r in uv]
    comp = [c for c in comp if c["vars_lumped"]]
    out["compression"] = {"vars_ratio_mean": float(np.mean([c["vars_lumped"] / c["vars_full"] for c in comp])),
                          "time_ratio_median": float(np.median([c["sec_lumped"] / max(c["sec_full"], 1e-9) for c in comp])),
                          "same_optimum_share": float(np.mean([bool(c["same_optimum"]) for c in comp])),
                          "U_mean": float(np.mean([c["U"] for c in comp])), "cells_mean": float(np.mean([c["cells"] for c in comp])),
                          "n": len(comp)}
    out["multi_agent"] = {"n": len(ma),
                          "k1_lp_violates_coalition": float(np.mean([r["k1"]["coalition_excess"] > TOL for r in ma])),
                          "k1_lp_max_coalition_excess": float(max(r["k1"]["coalition_excess"] for r in ma)),
                          "k2_lp_violates_coalition": float(np.mean([r["k2"]["coalition_excess"] > TOL for r in ma])),
                          "utility_k1": float(np.mean([r["k1"]["utility"] for r in ma])),
                          "utility_k2": float(np.mean([r["k2"]["utility"] for r in ma])),
                          "k2_minus_k1": boot([r["k2"]["utility"] - r["k1"]["utility"] for r in ma])}
    return out


# ------------------------------------------------------------------ AB

def analyze_ab():
    rows = json.load(gzip.open(R / "ab_raw.json.gz", "rt"))
    arms = ["CAPD", "CAPD+A", "CAPD_D", "CAPD_D+A", "CAPD+B", "CAPD+A+B", "CAPD_F"]
    out = {"n_instances": len(rows)}
    for tau in ("0.34", "0.5", "all"):
        items = [(r, t) for r in rows for t in r["res"] if tau == "all" or t == tau]
        tab = {}
        for a in arms:
            tab[a] = {"utility": boot([r["res"][t][a]["utility"] for r, t in items]),
                      "violating_steps_total": int(sum(r["res"][t][a]["violating_steps"] for r, t in items)),
                      "instances_with_violation": float(np.mean([r["res"][t][a]["violating_steps"] > 0 for r, t in items])),
                      "final_V1": float(np.mean([r["res"][t][a]["final_V1"] for r, t in items]))}
        d = lambda a, b: [r["res"][t][a]["utility"] - r["res"][t][b]["utility"] for r, t in items]
        tab["effects"] = {"A without B (CAPD+A - CAPD)": boot(d("CAPD+A", "CAPD")),
                          "B without A (CAPD+B - CAPD)": boot(d("CAPD+B", "CAPD")),
                          "A with B (CAPD+A+B - CAPD+B)": boot(d("CAPD+A+B", "CAPD+B")),
                          "B with A (CAPD+A+B - CAPD+A)": boot(d("CAPD+A+B", "CAPD+A")),
                          "full vs CAPD": boot(d("CAPD+A+B", "CAPD")),
                          "interaction (A|B - A|no B)": boot([x - y for x, y in zip(d("CAPD+A+B", "CAPD+B"), d("CAPD+A", "CAPD"))]),
                          "degrade action alone (CAPD_D - CAPD)": boot(d("CAPD_D", "CAPD")),
                          "joint LP beyond degrade (CAPD+B - CAPD_D)": boot(d("CAPD+B", "CAPD_D")),
                          "A+B vs same-action-space A (CAPD+A+B - CAPD_D+A)": boot(d("CAPD+A+B", "CAPD_D+A")),
                          "A with degrade (CAPD_D+A - CAPD_D)": boot(d("CAPD_D+A", "CAPD_D"))}
        out[tau] = tab
    by_name = defaultdict(list)
    for r in rows:
        for t in r["res"]:
            by_name[r["name"]].append(r["res"][t]["CAPD+A+B"]["utility"] - r["res"][t]["CAPD+A"]["utility"])
    out["B_with_A_by_structure"] = {k: boot(v) for k, v in by_name.items()}
    return out


def plots(a, b, ab):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(17, 4.8))
    ax = axs[0]
    cols = {"CAPD_FIRST": "#7f7f7f", "A0": "#ff9896", "A1": "#d62728", "A1_DRO": "#e377c2", "MPC": "#1f77b4",
            "BEAM": "#17becf", "SAA": "#2ca02c", "OPT": "#000000"}
    for c, mk in (("base", "o"), ("tight", "s"), ("conflict", "^"), ("overlap", "D"), ("large_kN", "P"), ("large_k1", "X")):
        if c not in a["conditions"]:
            continue
        tab = a["conditions"][c]["table"]
        for l, v in tab.items():
            f = fam(l)
            q = "emp" if "emp" in v else "true"
            if f in cols and v[q]["ms"] and l.count("|") <= 1 or f in ("A1", "A1_DRO", "MPC", "BEAM", "SAA") and v.get(q):
                if f not in cols or not v[q]["ms"]:
                    continue
                ax.scatter(v[q]["ms"], v[q]["completion"], color=cols[f], marker=mk, s=22)
    ax.set_xscale("log")
    ax.set_xlabel("ms per decision (log)")
    ax.set_ylabel("task completion (q from history)")
    ax.set_title("A: utility vs compute (shape = condition)", fontsize=10)
    for f, c in cols.items():
        ax.scatter([], [], color=c, label=f)
    ax.legend(fontsize=7, ncol=2)
    ax.grid(alpha=.25)
    ax = axs[1]
    s = b["by_setting"]["correlated truth, product-approx model"] if "correlated truth, product-approx model" in b["by_setting"] else list(b["by_setting"].values())[0]
    ms = [m for m in ("ORACLE_LP", "ROBUST_LP", "CHANCE_LP_0.05", "CHANCE_LP_0.2", "MAP_LP", "SIM_ROBUST", "STEP_QIF", "CAPD_F", "ROBUST_LP+timing") if m in s]
    xs = np.arange(len(ms))
    ax.bar(xs - 0.2, [s[m]["utility"]["mean"] for m in ms], 0.4, color="#1f77b4", label="utility")
    ax.bar(xs + 0.2, [s[m]["violates_true_view"] for m in ms], 0.4, color="#d62728", label="violates (true view)")
    ax.set_xticks(xs)
    ax.set_xticklabels(ms, rotation=35, fontsize=7)
    ax.set_title("B: unknown, correlated attacker view (product-approx model)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=.25, axis="y")
    ax = axs[2]
    arms = ["CAPD", "CAPD+A", "CAPD+B", "CAPD+A+B"]
    for i, t in enumerate(("0.34", "0.5")):
        vals = [ab[t][x]["utility"]["mean"] for x in arms]
        lo = [ab[t][x]["utility"]["mean"] - ab[t][x]["utility"]["lo"] for x in arms]
        hi = [ab[t][x]["utility"]["hi"] - ab[t][x]["utility"]["mean"] for x in arms]
        ax.bar(np.arange(4) + (i - 0.5) * 0.38, vals, 0.38, yerr=[lo, hi], label=f"tau = {t}", color=["#9ecae1", "#3182bd"][i])
    ax.set_xticks(np.arange(4))
    ax.set_xticklabels(arms, fontsize=8)
    ax.set_ylabel("utility per step (same joint per-output rule)")
    ax.set_title("AB: four-arm ablation", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=.25, axis="y")
    fig.tight_layout()
    (R / "figures").mkdir(exist_ok=True)
    fig.savefig(R / "figures" / "fig_cgc4.png", dpi=170, bbox_inches="tight")
    fig.savefig(R / "figures" / "fig_cgc4.svg", bbox_inches="tight")


def main():
    a = analyze_a() if (R / "a_test_raw.json.gz").exists() else None
    b = analyze_b() if (R / "b_raw.json.gz").exists() else None
    ab = analyze_ab() if (R / "ab_raw.json.gz").exists() else None
    (R / "analysis.json").write_text(json.dumps({"A": a, "B": b, "AB": ab}, indent=1) + "\n")
    if a and b and ab:
        plots(a, b, ab)
    print("ok", bool(a), bool(b), bool(ab))


if __name__ == "__main__":
    main()
