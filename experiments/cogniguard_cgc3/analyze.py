"""Analysis for the three CGC v3 candidates: paired bootstrap CIs, ablations, Pareto fronts, figures."""

from __future__ import annotations

import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

R = Path(__file__).parent / "results"
rng = np.random.default_rng(0)


def boot(d, n=4000):
    d = np.asarray(d, float)
    if len(d) == 0:
        return None
    bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(n)]
    return {"mean": float(d.mean()), "lo": float(np.quantile(bs, .025)), "hi": float(np.quantile(bs, .975)), "n": int(len(d))}


# ------------------------------------------------------------------ A

def analyze_a():
    rows = json.loads(gzip.open(R / "cand_a_raw.json.gz").read())
    H = 6
    pols = list(rows[0]["res"])
    out = {"n_instances": len(rows), "by_budget": {}, "paired": {}, "robust": {}, "time_ms_per_decision": {}}
    for v in (0.25, 0.5, 0.75, "all"):
        rs = [r for r in rows if v == "all" or r["v_thr"] == v]
        out["by_budget"][str(v)] = {p: {"completion": float(np.mean([r["res"][p]["in"]["served"] for r in rs]) / H),
                                         "final_V1": float(np.mean([r["res"][p]["in"]["final_V1"] for r in rs])),
                                         "final_Lstar": float(np.mean([r["res"][p]["in"]["final_Lstar"] for r in rs]))}
                                     for p in pols}
    d = lambda a, b, key="served", setting="in": [(r["res"][a][setting][key] - r["res"][b]["in"][key]) / (H if key == "served" else 1)
                                                  for r in rows]
    for a, b in (("OPT", "CAPD_FIRST"), ("CONFLICT", "CAPD_FIRST"), ("CONFLICT", "GREEDY_MIN"), ("CONFLICT", "GREEDY_LEAK"),
                 ("OPT", "CONFLICT"), ("ROLLOUT", "CONFLICT"), ("EXPECTIMAX2", "CONFLICT"), ("OPT", "OPT_SERVE"),
                 ("LA", "CONFLICT"), ("CONFLICT", "RANDOM")):
        out["paired"][f"{a} - {b}"] = {"completion": boot(d(a, b)), "final_V1": boot(d(a, b, "final_V1"))}
    gap = [(r["res"]["CONFLICT"]["in"]["served"] - r["res"]["CAPD_FIRST"]["in"]["served"]) /
           (r["res"]["OPT"]["in"]["served"] - r["res"]["CAPD_FIRST"]["in"]["served"])
           for r in rows if r["res"]["OPT"]["in"]["served"] - r["res"]["CAPD_FIRST"]["in"]["served"] > 1e-6]
    num = [r["res"]["CONFLICT"]["in"]["served"] - r["res"]["CAPD_FIRST"]["in"]["served"] for r in rows]
    den = [r["res"]["OPT"]["in"]["served"] - r["res"]["CAPD_FIRST"]["in"]["served"] for r in rows]
    bs = []
    for _ in range(2000):
        i = rng.integers(0, len(rows), len(rows))
        bs.append(np.sum(np.array(num)[i]) / np.sum(np.array(den)[i]))
    out["conflict_share_of_opt_gain"] = {"ratio_of_means": float(np.sum(num) / np.sum(den)),
                                         "lo": float(np.quantile(bs, .025)), "hi": float(np.quantile(bs, .975)),
                                         "share_instances_with_opt_gain": len(gap) / len(rows),
                                         "share_instances_conflict_below_capd": float(np.mean(np.array(num) < -1e-9))}
    for p in ("CONFLICT", "LA", "EXPECTIMAX2", "ROLLOUT", "OPT"):
        out["robust"][p] = {s: boot(d(p, "CAPD_FIRST", setting=s)) for s in ("in", "uniform", "wrong_q", "unseen_types")}
    for p in pols:
        out["time_ms_per_decision"][p] = float(1000 * np.sum([r["res"][p]["in"]["sec"] for r in rows]) /
                                               max(1, np.sum([r["res"][p]["in"]["decisions"] for r in rows])))
    # same cumulative leakage: compare at matched realized final V1 using the lambda / budget families
    pts = defaultdict(list)
    for v in (0.25, 0.5, 0.75):
        rs = [r for r in rows if r["v_thr"] == v]
        for p in pols:
            pts[p].append((float(np.mean([r["res"][p]["in"]["final_V1"] for r in rs])),
                           float(np.mean([r["res"][p]["in"]["served"] for r in rs])) / H, v))
    out["pareto_points"] = pts
    return out


# ------------------------------------------------------------------ B

def analyze_b():
    raw = json.loads(gzip.open(R / "cand_b_raw.json.gz").read())
    one, two = raw["one_step"], raw["two_step"]
    mechs = ["CAPD_VI", "CAPD_F", "CAPD_F_DEG", "SIM", "SIM_DEG", "RAND", "LP_CONTENT", "LP_SIMUL", "LP_NODEG",
             "LP_JOINT", "LP_EXP_SIMUL", "RAND_EXP", "LP_EXP"]
    out = {"n_one_step": len(one), "n_two_step": len(two), "mechanisms": {}, "paired": {}}
    for m in mechs:
        rs = [r for r in one if r["res"].get(m)]
        tau = np.array([r["tau_V"] for r in rs])
        g = lambda k: np.array([r["res"][m][k] for r in rs])
        out["mechanisms"][m] = {
            "n_feasible": len(rs), "utility": boot(g("utility")),
            "violates_joint_maxcase": float(np.mean(g("joint_maxcase_V") > tau + 1e-9)),
            "violates_joint_expected": float(np.mean(g("joint_expected_V") > tau + 1e-9)),
            "content_only_says_safe_but_joint_unsafe": float(np.mean((g("content_only_maxcase_V") <= tau + 1e-9) & (g("joint_maxcase_V") > tau + 1e-9))),
            "I_joint": float(g("I_joint").mean()), "naive_sum_I": float(g("naive_sum_I").mean()),
            "naive_minus_joint_I": boot(g("naive_sum_I") - g("I_joint")),
            "ms": float(1000 * np.mean([r["res"][m].get("sec", np.nan) for r in rs]))}
    for a, b in (("LP_JOINT", "SIM_DEG"), ("LP_JOINT", "LP_SIMUL"), ("LP_JOINT", "LP_NODEG"), ("LP_JOINT", "CAPD_F"),
                 ("LP_EXP", "LP_EXP_SIMUL"), ("LP_EXP", "RAND_EXP")):
        rs = [r for r in one if r["res"].get(a) and r["res"].get(b)]
        out["paired"][f"{a} - {b}"] = boot([r["res"][a]["utility"] - r["res"][b]["utility"] for r in rs])
    # LP_JOINT vs CAPD_F restricted to instances where CAPD_F is jointly safe (a fair head-to-head)
    rs = [r for r in one if r["res"]["CAPD_F"]["joint_maxcase_V"] <= r["tau_V"] + 1e-9]
    out["paired"]["LP_JOINT - CAPD_F | CAPD_F jointly safe"] = boot([r["res"]["LP_JOINT"]["utility"] - r["res"]["CAPD_F"]["utility"] for r in rs])
    out["capd_f_jointly_safe_share"] = len(rs) / len(one)
    t = [r for r in two if r["joint_util"] is not None and r["myopic_util"] is not None]
    out["two_step"] = {"joint_minus_myopic": boot([r["joint_util"] - r["myopic_util"] for r in t]),
                       "joint_util": float(np.mean([r["joint_util"] for r in t])) / 2,
                       "myopic_util": float(np.mean([r["myopic_util"] for r in t])) / 2,
                       "ms_joint": float(1000 * np.mean([r["sec_joint"] for r in t])),
                       "ms_myopic": float(1000 * np.mean([r["sec_myopic"] for r in t])),
                       "max_outputs": int(max(r["n_outputs"] for r in t))}
    return out


# ------------------------------------------------------------------ C

def fam(label):
    return label.split("|")[0]


def analyze_c():
    rows = json.loads(gzip.open(R / "cand_c_raw.json.gz").read())
    labels = list(rows[0]["res"])
    out = {"n_episodes": len(rows), "matched": {}, "fronts": {}, "pid_witness": {}}
    for N in ("all", 1, 2, 3, 4):
        rs = [r for r in rows if N == "all" or r["N"] == N]
        pts = {lab: {"served": float(np.mean([r["res"][lab]["served"] for r in rs])),
                     "I_coal": float(np.mean([r["res"][lab]["I_coal"] for r in rs])),
                     "I_coal_max": float(np.max([r["res"][lab]["I_coal"] for r in rs])),
                     "I_ind_max": float(np.max([r["res"][lab]["I_ind_max"] for r in rs]))} for lab in labels}
        out["fronts"][str(N)] = pts
        m = {}
        for b in (0.3, 0.5, 0.7):
            for bi in (None, 0.3):
                key = f"coal<={b}" + (f",ind<={bi}" if bi else "")
                m[key] = {}
                for f in sorted({fam(l) for l in labels}):
                    ok = [l for l in labels if fam(l) == f and pts[l]["I_coal_max"] <= b + 1e-9
                          and (bi is None or pts[l]["I_ind_max"] <= bi + 1e-9)]
                    if ok:
                        best = max(ok, key=lambda l: pts[l]["served"])
                        m[key][f] = {"label": best, "served": pts[best]["served"]}
                    else:
                        m[key][f] = None
                # paired bootstrap of the best SYN_IND variant vs the best COAL / COAL_IND at this guarantee
                ref = m[key].get("COAL_IND" if bi else "COAL")
                for f in ("SYN_IND_imin", "SYN_IND_mmi", "SYN_imin", "SYN_mmi", "IND", "CAPD_VI"):
                    if ref and m[key].get(f):
                        m[key][f"{f} - ref"] = boot([r["res"][m[key][f]["label"]]["served"] - r["res"][ref["label"]]["served"] for r in rs])
        out["matched"][str(N)] = m
    pw = json.loads(gzip.open(R / "cand_c_pid_witness.json.gz").read())
    for tag in ("syn_imin", "syn_mmi"):
        c = np.array([r["cross"] for r in pw], bool)
        s = np.array([r[tag] for r in pw])
        pos, neg = s[c], s[~c]
        auc = float(np.mean([(p > q) + 0.5 * (p == q) for p in pos[:400] for q in neg[:4000]])) if len(pos) and len(neg) else None
        out["pid_witness"][tag] = {"n_pairs": int(len(s)), "n_crossing": int(c.sum()),
                                   "mean_syn_crossing": float(pos.mean()) if len(pos) else None,
                                   "mean_syn_noncrossing": float(neg.mean()), "auc_syn_predicts_crossing_subsample": auc,
                                   "share_noncrossing_with_syn_gt_0.1H": float(np.mean(neg > 0.1))}
    return out


def plots(a, b, c):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(16, 4.6))
    col = {"CAPD_FIRST": "#7f7f7f", "GREEDY_MIN": "#bcbd22", "GREEDY_LEAK": "#17becf", "RANDOM": "#c7c7c7",
           "CONFLICT": "#d62728", "CONFLICT_l0.3": "#ff9896", "CONFLICT_l1": "#f7b6d2", "LA": "#9467bd",
           "ROLLOUT": "#8c564b", "EXPECTIMAX2": "#e377c2", "OPT_SERVE": "#aec7e8", "OPT": "#000000",
           "OPT_l0.3": "#1f77b4", "OPT_l1": "#2ca02c"}
    ax = axs[0]
    for p, cl in col.items():
        pts = sorted(a["pareto_points"][p])
        ax.plot([x for x, _, _ in pts], [y for _, y, _ in pts], marker="o", ms=3.5, lw=1.3, color=cl, label=p)
    ax.set_xlabel("mean final attacker V1 (cumulative leakage)")
    ax.set_ylabel("long-run task completion")
    ax.set_title("A: look-ahead disclosure (budgets V1<=.25/.5/.75)", fontsize=10)
    ax.legend(fontsize=6.5, ncol=2)
    ax.grid(alpha=.25)
    ax = axs[1]
    ms = [m for m in ("CAPD_VI", "CAPD_F", "CAPD_F_DEG", "SIM_DEG", "LP_CONTENT", "LP_SIMUL", "LP_NODEG", "LP_JOINT")]
    u = [b["mechanisms"][m]["utility"]["mean"] for m in ms]
    v = [b["mechanisms"][m]["violates_joint_maxcase"] for m in ms]
    xs = np.arange(len(ms))
    ax.bar(xs - 0.2, u, 0.4, color="#1f77b4", label="utility")
    ax.bar(xs + 0.2, v, 0.4, color="#d62728", label="share violating joint max-case")
    ax.set_xticks(xs)
    ax.set_xticklabels(ms, rotation=35, fontsize=7.5)
    ax.set_title("B: content + governance channel (one step)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=.25, axis="y")
    ax = axs[2]
    fr = c["fronts"]["all"]
    for f, cl in (("COAL", "#000000"), ("COAL_IND", "#7f7f7f"), ("IND", "#bcbd22"), ("SYN_imin", "#ff9896"),
                  ("SYN_IND_imin", "#d62728"), ("SYN_IND_mmi", "#1f77b4"), ("CAPD_VI", "#2ca02c")):
        pts = sorted((v["I_coal"], v["served"]) for l, v in fr.items() if fam(l) == f)
        best, front = -1, []
        for x, y in pts:
            if y > best:
                front.append((x, y))
                best = y
        ax.plot([x for x, _ in front], [y for _, y in front], marker="o", ms=3.5, lw=1.3, color=cl, label=f)
    ax.set_xlabel("mean final coalition leakage I(S;V_all)/H(S)")
    ax.set_ylabel("served fraction")
    ax.set_title("C: individual vs coalition (N=1..4, Pareto per family)", fontsize=10)
    ax.legend(fontsize=7)
    ax.grid(alpha=.25)
    fig.tight_layout()
    (R / "figures").mkdir(exist_ok=True)
    fig.savefig(R / "figures" / "fig_cgc3.png", dpi=170, bbox_inches="tight")
    fig.savefig(R / "figures" / "fig_cgc3.svg", bbox_inches="tight")


def main():
    a, b, c = analyze_a(), analyze_b(), analyze_c()
    (R / "analysis.json").write_text(json.dumps({"A": a, "B": b, "C": c}, indent=1) + "\n")
    plots(a, b, c)
    print("ok")


if __name__ == "__main__":
    main()
