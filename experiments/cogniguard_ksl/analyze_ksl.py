"""Analysis of the KSL-V2 pilots: Pareto fronts, matched-safety comparisons (dev-selected, test-reported),
paired episode bootstrap, LLM-attacker predictiveness, figures."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np

D = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/ksl")
R = Path(__file__).parent / "results"
FAM_ORDER = ["CAPD", "CAPD_d1", "L3h", "SHANNON", "MINENT", "GLEAK", "BAYES_MEAN", "BAYES_D", "BAYES",
             "RANDV", "VOI", "VOI2", "DE2", "DE2_eta2", "DE2_strict", "ORACLE"]


def fam(label):
    return label.split("|")[0]


def budget(label):
    for p in label.split("|"):
        if p.startswith("B="):
            return int(p[2:])
    return 0


def load(tag):
    return [json.loads(l) for l in (D / f"methods_{tag}.jsonl").read_text().splitlines()]


def is_dev(row):
    return ((row["seed"] - 7) // 1000) % 2 == 0


def agg(rows, label):
    c = defaultdict(float)
    for r in rows:
        for k, v in r["res"][label].items():
            c[k] += v
    n = len(rows)
    return {"harm": c["harm_rel"] / max(c["harm_req"], 1), "over_refusal": c["benign_ref"] / max(c["benign_req"], 1),
            "full_leak": c["full_rel"] / max(c["full_req"], 1), "calls_per_ep": c["calls"] / n,
            "ms_per_decision": 1000 * c["sec"] / (n * 10), "n_eps": n,
            "harm_req": c["harm_req"], "benign_req": c["benign_req"]}


def paired(rows, la, lb, key, n=2000, seed=0):
    """Episode-cluster bootstrap of the difference in a ratio-of-sums rate (a - b)."""
    num, den = {"harm": ("harm_rel", "harm_req"), "over_refusal": ("benign_ref", "benign_req")}[key]
    A = np.array([[r["res"][la][num], r["res"][la][den], r["res"][lb][num], r["res"][lb][den]] for r in rows], float)
    rate = lambda X: X[:, 0].sum() / max(X[:, 1].sum(), 1) - X[:, 2].sum() / max(X[:, 3].sum(), 1)
    rng = np.random.default_rng(seed)
    bs = [rate(A[rng.integers(0, len(A), len(A))]) for _ in range(n)]
    return {"diff": float(rate(A)), "lo": float(np.quantile(bs, .025)), "hi": float(np.quantile(bs, .975))}


def front(points):
    out, best = [], 9.0
    for p in sorted(points, key=lambda p: (p["over_refusal"], p["harm"])):
        if p["harm"] < best - 1e-12:
            out.append(p)
            best = p["harm"]
    return out


FAMS_CMP = ["CAPD", "CAPD_d1", "L3h", "SHANNON", "MINENT", "GLEAK", "MINENT_SIM", "BAYES_MEAN", "BAYES_D", "BAYES",
            "BAYES_SIM", "RANDV", "VOI", "VOI2", "DE2", "DE2_eta2", "DE2_strict"]


def matched(rows, labels):
    dev = [r for r in rows if is_dev(r)]
    test = [r for r in rows if not is_dev(r)]
    res = {}
    for h in (0.05, 0.10, 0.15, 0.20):
        out = {}
        for f in FAMS_CMP:
            for B in (0, 3, 8):
                cands = [lab for lab in labels if fam(lab) == f and budget(lab) == B]
                if not cands:
                    continue
                dv = {lab: agg(dev, lab) for lab in cands}
                ok = [lab for lab in cands if dv[lab]["harm"] <= h + 1e-9]
                if not ok:
                    out[f"{f}|B={B}"] = None
                    continue
                pick = min(ok, key=lambda lab: (dv[lab]["over_refusal"], dv[lab]["harm"]))
                out[f"{f}|B={B}"] = {"label": pick, "dev": dv[pick], "test": agg(test, pick)}
        pairs = {}
        for key, v in out.items():
            if not v:
                continue
            B = budget(v["label"])
            refs = ["BAYES|B=0", "BAYES_SIM|B=0"] + ([f"VOI2|B={B}", f"VOI|B={B}"] if B else [])
            for refk in refs:
                rf = out.get(refk)
                if rf and rf["label"] != v["label"]:
                    pairs[f"{key} - {refk}"] = {m: paired(test, v["label"], rf["label"], m) for m in ("harm", "over_refusal")}
        res[f"harm<={h}"] = {"picked": out, "paired": pairs}
    return res


def analyze(tag):
    rows = load(tag)
    labels = list(rows[0]["res"])
    settings = sorted({(r["N"], r["k"]) for r in rows})
    res = {"tag": tag, "env": rows[0]["env"], "n_episodes": len(rows), "settings": {}, "matched": {}, "by_structure": {}}
    groups = {"all": rows, **{f"N={n},k={k}": [r for r in rows if (r["N"], r["k"]) == (n, k)] for n, k in settings}}
    for g, rs in groups.items():
        pts = {lab: agg(rs, lab) for lab in labels}
        fr = defaultdict(list)
        for lab, p in pts.items():
            fr[(fam(lab), budget(lab))].append({"label": lab, **p})
        res["settings"][g] = {"points": pts, "fronts": {f"{f}|B={b}": front(v) for (f, b), v in fr.items()}}
    # matched safety: choose on dev episodes the variant with the lowest over-refusal s.t. harm <= h*, report test
    for g, rs in groups.items():
        res["matched"][g] = matched(rs, labels)
    # same rule, same delta, same budget, same episodes: paired differences
    res["same_rule"] = {}
    for g, rs in groups.items():
        sr = {}
        for B in (3, 8):
            for d in (0.05, 0.1, 0.2, 0.35, 0.5):
                for a_, b_ in (("DE2", "VOI2"), ("DE2", "VOI"), ("DE2", "RANDV"), ("VOI2", "VOI"), ("DE2_eta2", "VOI2")):
                    la, lb = f"{a_}|B={B}|d={d}", f"{b_}|B={B}|d={d}"
                    if la in labels and lb in labels:
                        sr[f"{la} - {lb}"] = {m: paired(rs, la, lb, m, n=1000) for m in ("harm", "over_refusal")}
                lv, l0 = f"VOI2|B={B}|d={d}", f"BAYES|d={d}"
                if lv in labels and l0 in labels:
                    sr[f"{lv} - {l0}"] = {m: paired(rs, lv, l0, m, n=1000) for m in ("harm", "over_refusal")}
        for d in (0.05, 0.1, 0.2, 0.35, 0.5):
            for a_, b_ in (("BAYES_SIM", "BAYES"), ("MINENT_SIM", "BAYES_D"), ("BAYES", "L3h"), ("BAYES_D", "L3h")):
                la, lb = f"{a_}|d={d}", f"{b_}|d={d}"
                if la in labels and lb in labels:
                    sr[f"{la} - {lb}"] = {m: paired(rs, la, lb, m, n=1000) for m in ("harm", "over_refusal")}
        res["same_rule"][g] = sr
    for st in sorted({r["structure"] for r in rows}):
        rs = [r for r in rows if r["structure"] == st]
        res["by_structure"][st] = {lab: agg(rs, lab) for lab in labels
                                   if lab in ("CAPD", "CAPD_d1", "L3h|d=0.1", "MINENT|t=0.5", "BAYES|d=0.1", "ORACLE")}
    return res


def attack():
    f = D / "attack_llm.jsonl"
    if not f.exists():
        return None
    rows = [json.loads(l) for l in f.read_text().splitlines()]
    rows = [r for r in rows if r["parsed"] > 0]
    y1 = np.array([r["hit1"] for r in rows], float)
    y3 = np.array([r["hit3"] for r in rows], float)
    V1 = np.array([r["V1"] for r in rows])
    P3 = np.array([r["P3"] for r in rows])
    H = np.array([r["H"] for r in rows])
    cov = np.array([r["cov"] for r in rows], float)

    def auc(score, y):
        n1, n0 = int((y == 1).sum()), int((y == 0).sum())
        if not n1 or not n0:
            return None
        order = np.argsort(score, kind="mergesort")
        ranks = np.empty(len(score))
        s_sorted = score[order]
        i = 0
        while i < len(score):                      # average ranks for ties
            j = i
            while j + 1 < len(score) and s_sorted[j + 1] == s_sorted[i]:
                j += 1
            ranks[order[i:j + 1]] = (i + j) / 2 + 1
            i = j + 1
        return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))

    def boot_auc(score, y, n=400):
        rng = np.random.default_rng(0)
        v = []
        for _ in range(n):
            i = rng.integers(0, len(y), len(y))
            a = auc(score[i], y[i])
            if a is not None:
                v.append(a)
        return [float(np.quantile(v, .025)), float(np.quantile(v, .975))]
    nc = cov == 0
    bins = [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.999), (0.999, 1.01)]
    calib = []
    for lo, hi in bins:
        s = nc & (V1 >= lo) & (V1 < hi)
        if s.sum():
            calib.append({"V1_bin": [lo, hi], "n": int(s.sum()), "mean_V1": float(V1[s].mean()), "llm_top1": float(y1[s].mean()),
                          "mean_P3": float(P3[s].mean()), "llm_top3": float(y3[s].mean())})
    s = cov == 1
    calib.append({"V1_bin": "covered witness", "n": int(s.sum()), "mean_V1": float(V1[s].mean()) if s.sum() else None,
                  "llm_top1": float(y1[s].mean()) if s.sum() else None})
    per_struct = {}
    for st in sorted({r["structure"] for r in rows}):
        i = np.array([r["structure"] == st for r in rows])
        j = i & nc
        per_struct[st] = {"n": int(i.sum()), "top1": float(y1[i].mean()), "mean_V1": float(V1[i].mean()),
                          "noncov_auc_V1": auc(V1[j], y1[j]), "noncov_top1": float(y1[j].mean()) if j.sum() else None,
                          "noncov_mean_V1": float(V1[j].mean()) if j.sum() else None}
    resid = y1 - V1
    return {"n": len(rows), "parse_fail": None,
            "auc_all": {"V1": auc(V1, y1), "V1_ci": boot_auc(V1, y1), "negH": auc(-H, y1), "witness_flag": auc(cov, y1)},
            "auc_noncovered_only": {"V1": auc(V1[nc], y1[nc]), "V1_ci": boot_auc(V1[nc], y1[nc]), "negH": auc(-H[nc], y1[nc])},
            "brier_V1_as_prediction": float(np.mean(resid ** 2)), "mean_top1_minus_V1": float(resid.mean()),
            "calibration_noncovered": calib, "per_structure": per_struct,
            "noncovered_top1_rate": float(y1[nc].mean()), "noncovered_mean_V1": float(V1[nc].mean()),
            "noncovered_V1_ge_0.5_top1": float(y1[nc & (V1 >= 0.5)].mean()), "noncovered_V1_lt_0.2_top1": float(y1[nc & (V1 < 0.2)].mean())}


def plots(res_main):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    col = {"CAPD": "#7f7f7f", "CAPD_d1": "#bcbd22", "L3h": "#9467bd", "SHANNON": "#17becf", "MINENT": "#1f77b4",
           "GLEAK": "#aec7e8", "BAYES_MEAN": "#8c564b", "BAYES_D": "#e377c2", "BAYES": "#2ca02c", "VOI2|B=8": "#ff7f0e",
           "DE2|B=8": "#d62728", "RANDV|B=8": "#c49c94", "ORACLE": "#000000"}
    gs = [g for g in res_main["settings"] if g != "all"]
    fig, axs = plt.subplots(1, len(gs), figsize=(4.2 * len(gs), 4.2), sharey=True)
    for ax, g in zip(np.atleast_1d(axs), gs):
        fr = res_main["settings"][g]["fronts"]
        for key, c in col.items():
            k2 = key if "|B=" in key else f"{key}|B=0"
            if k2 in fr:
                xs = [p["over_refusal"] for p in fr[k2]]
                ys = [p["harm"] for p in fr[k2]]
                ax.plot(xs, ys, marker="o", ms=3.5, lw=1.4, color=c, label=key)
        ax.set_title(g, fontsize=10)
        ax.set_xlabel("over-refusal")
        ax.grid(alpha=.25)
    np.atleast_1d(axs)[0].set_ylabel("harmful release (partial-leak target, tau=0.5)")
    h, l = np.atleast_1d(axs)[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=7, fontsize=8, bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    (R / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(R / "figures" / "fig_ksl_pareto.png", dpi=180, bbox_inches="tight")
    fig.savefig(R / "figures" / "fig_ksl_pareto.svg", bbox_inches="tight")


def plot_exact_and_attack(att):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    part = json.loads((R / "partial.json").read_text())
    names = list(part)
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.2))
    x = np.arange(len(names))
    a1 = [part[n]["static"]["frac_view_world_leak_ge_1bit"] for n in names]
    a2 = [part[n]["static"]["frac_view_world_V1_ge_0.5"] for n in names]
    a3 = [part[n]["static"]["realized_determination_without_witness"] for n in names]
    for off, v, c, lab in ((-0.27, a1, "#1f77b4", ">= 1 bit min-entropy leak"), (0, a2, "#ff7f0e", "V1 >= 0.5"),
                           (0.27, a3, "#d62728", "S already determined (V1 = 1)")):
        axs[0].bar(x + off, v, 0.26, color=c, label=lab)
    axs[0].set_xticks(x)
    axs[0].set_xticklabels(names, rotation=30, fontsize=8)
    axs[0].set_ylabel("share of (view, world), no witness covered")
    axs[0].set_title("Exact: attacker power before any complete witness", fontsize=10)
    axs[0].legend(fontsize=8)
    axs[0].grid(alpha=.25, axis="y")
    if att:
        cal = [c for c in att["calibration_noncovered"] if isinstance(c["V1_bin"], list)]
        mv = [c["mean_V1"] for c in cal]
        axs[1].plot([0, 1], [0, 1], color="#999", lw=1, ls="--", label="perfect Bayes guesser")
        axs[1].plot(mv, [c["llm_top1"] for c in cal], marker="o", color="#2ca02c", label="glm-5.2 top-1 hit rate")
        for c in cal:
            axs[1].annotate(f"n={c['n']}", (c["mean_V1"], c["llm_top1"]), fontsize=7, xytext=(4, -10), textcoords="offset points")
        axs[1].set_xlabel("exact V1 (no complete witness covered)")
        axs[1].set_ylabel("LLM attacker success")
        axs[1].set_title(f"LLM attacker vs exact V1 (AUC {att['auc_noncovered_only']['V1']:.2f}, non-covered states)", fontsize=10)
        axs[1].legend(fontsize=8)
        axs[1].grid(alpha=.25)
    fig.tight_layout()
    (R / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(R / "figures" / "fig_ksl_exact_attack.png", dpi=180, bbox_inches="tight")
    fig.savefig(R / "figures" / "fig_ksl_exact_attack.svg", bbox_inches="tight")


def main():
    out = {}
    for tag in ("pilot", "lownoise"):
        if (D / f"methods_{tag}.jsonl").exists():
            out[tag] = analyze(tag)
    out["attack_llm"] = attack()
    R.mkdir(exist_ok=True)
    (R / "methods_analysis.json").write_text(json.dumps(out, indent=1) + "\n")
    if "pilot" in out:
        plots(out["pilot"])
    plot_exact_and_attack(out["attack_llm"])
    print("ok")


if __name__ == "__main__":
    main()
