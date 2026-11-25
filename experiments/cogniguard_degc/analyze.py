"""DEGC analysis: Pareto fronts, three fair comparisons, paired bootstrap, simulation summary, figures.

Stage B numbers are offline diagnosis on exposed data; operating points are selected on the same data and
are therefore optimistic. They decide only whether a held-out Stage C is warranted.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

D = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/degc")
NAMES = {"B0": "B0 deployed CGC (raw+E7)", "B1": "B1 CA-PD + joint detection", "B2": "B2 leakage only (chance constraint)",
         "B3": "B3 state entropy only", "B4": "B4 random verification", "B5": "B5 low-confidence first",
         "B6": "B6 risk-driven (witness order)", "B7": "B7 myopic VoI", "B8": "B8 full verification",
         "OCL": "OCELOT-style conservative", "EC2": "EC2 selector", "HZ": "h(Z)-triggered", "Ours": "DEGC", "Oracle": "Oracle"}


def indicators(row):
    sens = {k: int(v["performed"] and not v["sub_block"]) for k, v in row["per_run"].items() if k.endswith("sensitive")}
    ben = {k: int(v["sub_block"]) for k, v in row["per_run"].items() if k.endswith("benign") and v["performed"]}
    return sens, ben


def boot(a, b, keys, n=4000, seed=0):
    rng = random.Random(seed)
    keys = sorted(keys)
    obs = sum(a[k] - b[k] for k in keys) / len(keys)
    ds = []
    for _ in range(n):
        s = [rng.choice(keys) for _ in keys]
        ds.append(sum(a[k] - b[k] for k in s) / len(s))
    ds.sort()
    return {"diff": obs, "lo": ds[int(.025 * n)], "hi": ds[int(.975 * n)]}


def front(rows, x="calls", y="harmful_rate"):
    out, best = [], 9e9
    for r in sorted(rows, key=lambda r: (r[x], r[y], r["over_refusal"])):
        if r[y] < best - 1e-12:
            out.append(r)
            best = r[y]
    return out


def best_under_budget(rows, B):
    ok = [r for r in rows if r["calls"] <= B]
    return min(ok, key=lambda r: (r["harmful_rate"], r["over_refusal"], r["calls"])) if ok else None


def stage_b(tag):
    res = json.loads((D / f"stage_b_{tag}.json").read_text())
    if tag == "llm_noisy_or" and (D / "stage_b_llm_detraw.json").exists():
        # deterministic verification arms: primary = raw verifier yes/no; the calibrated-threshold variant
        # from the main grid is kept under "<arm>-cal"
        raw = json.loads((D / "stage_b_llm_detraw.json").read_text())["rows"]
        swap = {r["arm"] for r in raw}
        for r in res["rows"]:
            if r["arm"] in swap:
                r["arm"] += "-cal"
        res["rows"] += raw
    by = defaultdict(list)
    for r in res["rows"]:
        by[r["arm"]].append(r)
    out = {"calibration": res["calibration"], "fronts": {}, "same_budget": {}, "same_harm": {}, "same_both": {}, "paired": {}}
    for arm, rows in by.items():
        out["fronts"][arm] = [{"config": r["config"], "calls": r["calls"], "harmful": r["harmful_rate"],
                               "over_refusal": r["over_refusal"], "new_rec": r["new_reconstruction_rate"]} for r in front(rows)]
    for B in (0, 25, 50, 100, 250, 600, 1200, 5000):
        out["same_budget"][B] = {arm: (lambda r: r and {"harmful": r["harmful_rate"], "over_refusal": r["over_refusal"],
                                                         "calls": r["calls"], "config": r["config"]})(best_under_budget(rows, B))
                                 for arm, rows in by.items()}
    for h in (0.06, 0.045):
        out["same_harm"][h] = {}
        for arm, rows in by.items():
            ok = [r for r in rows if r["harmful_rate"] <= h + 1e-9]
            r = min(ok, key=lambda r: (r["over_refusal"], r["calls"])) if ok else None
            out["same_harm"][h][arm] = r and {"benign_success": r["benign_success"], "over_refusal": r["over_refusal"],
                                              "calls": r["calls"], "config": r["config"]}
    for h, o in ((0.06, 0.024), (0.045, 0.024), (0.035, 0.024)):
        out["same_both"][f"harm<={h},over<={o}"] = {}
        for arm, rows in by.items():
            ok = [r for r in rows if r["harmful_rate"] <= h + 1e-9 and r["over_refusal"] <= o + 1e-9]
            r = min(ok, key=lambda r: r["calls"]) if ok else None
            out["same_both"][f"harm<={h},over<={o}"][arm] = r and {"calls": r["calls"], "config": r["config"],
                                                                   "p95_ms": r["with_verifier_ms_p95"]}
    # paired: same delta / cap (level 0.9, vcost 0)
    idx = {(r["arm"], json.dumps({k: v for k, v in r["config"].items() if k in ("delta", "cap")}, sort_keys=True),
            r["config"].get("level", .9), r["config"].get("vcost", 0.0)): r for r in res["rows"]}
    for d in (0.02, 0.05, 0.1):
        for cap in (1, 2):
            key = json.dumps({"cap": cap, "delta": d}, sort_keys=True)
            ours = idx.get(("Ours", key, .9, 0.0))
            for other, okey in (("B7", ("B7", key, .9, 0.0)), ("EC2", ("EC2", key, .9, 0.0)),
                                ("B2", ("B2", json.dumps({"delta": d}), .9, 0.0))):
                o = idx.get(okey)
                if not (ours and o):
                    continue
                s1, b1 = indicators(ours)
                s2, b2 = indicators(o)
                out["paired"][f"Ours vs {other} delta={d} cap={cap}"] = {
                    "harmful": boot(s1, s2, s1.keys()), "over_refusal": boot(b1, b2, b1.keys()),
                    "calls": (ours["calls"], o["calls"])}
    return out


def sim():
    rows = []
    for f in sorted((D / "sim").glob("sim_k*.json")):
        grp = "small40" if "small40" in f.name else "main"
        rows += [{**r, "k": f"{r['k']}" + ("" if grp == "main" else "-small40")} for r in json.loads(f.read_text())]
    out = {}
    for k in sorted({r["k"] for r in rows}):
        rk = [r for r in rows if r["k"] == k]
        by = defaultdict(list)
        for r in rk:
            by[r["arm"]].append(r)
        out[k] = {"fronts": {a: [{"config": r["config"], "calls": round(r["calls_per_world"], 2), "leak": r["leak_rate"],
                                  "over_refusal": r["over_refusal"]} for r in front(v, "calls_per_world", "leak_rate")]
                             for a, v in by.items()}}
        # paired at matched delta/cap: Ours vs B7 / B2 / EC2
        pairs = {}
        idx = {(r["arm"], json.dumps(r["config"], sort_keys=True)): r for r in rk}
        for d in (0.02, 0.05, 0.1):
            for cap in (1, 2):
                o = idx.get(("Ours", json.dumps({"cap": cap, "delta": d}, sort_keys=True)))
                for other, c in (("B7", {"cap": cap, "delta": d, "vcost": 0.0}), ("EC2", {"cap": cap, "delta": d}), ("B2", {"delta": d})):
                    b = idx.get((other, json.dumps(c, sort_keys=True)))
                    if o and b:
                        A = {i: x[0] for i, x in enumerate(o["per_world"])}
                        B_ = {i: x[0] for i, x in enumerate(b["per_world"])}
                        Ao = {i: x[1] for i, x in enumerate(o["per_world"])}
                        Bo = {i: x[1] for i, x in enumerate(b["per_world"])}
                        pairs[f"Ours vs {other} delta={d} cap={cap}"] = {
                            "leak": boot(A, B_, A.keys(), 2000), "over_refusal": boot(Ao, Bo, Ao.keys(), 2000),
                            "calls_per_world": (round(o["calls_per_world"], 2), round(b["calls_per_world"], 2))}
        out[k]["paired"] = pairs
    return out


def plots(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    show = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "OCL", "EC2", "Ours", "Oracle"]
    col = {"B1": "#b0b0b0", "B2": "#1f77b4", "B3": "#9467bd", "B4": "#bcbd22", "B5": "#17becf", "B6": "#8c564b",
           "B7": "#ff7f0e", "B8": "#3b3b3b", "OCL": "#e377c2", "EC2": "#2ca02c", "Ours": "#d62728", "Oracle": "#000000"}
    panels = [("llm_noisy_or", "Stage B, real LLM verifier"), ("oracle_noisy_or", "Stage B, ideal verifier (upper bound)")]
    sims = {k: v for k, v in res.get("sim", {}).items() if "small" not in str(k)}
    fig, axs = plt.subplots(2, 3, figsize=(14, 8.4))
    axes = list(axs.flat)
    for ax in axes[len(panels) + len(sims):]:
        ax.axis("off")
    for ax, (tag, title) in zip(axes, panels):
        fr = res["stage_b"][tag]["fronts"]
        for a in show:
            if a in fr:
                xs = [max(r["calls"], 1) for r in fr[a]]
                ys = [r["harmful"] for r in fr[a]]
                ax.step(xs, ys, where="post", marker="o", ms=3, lw=1.4, color=col[a], label=NAMES[a])
        ax.set_xscale("log")
        ax.set_xlabel("verification calls (log; 0 drawn at 1)")
        ax.set_ylabel("harmful release rate")
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=.25)
    for ax, (k, v) in zip(axes[len(panels):], sorted(sims.items())):
        for a in show:
            if a in v["fronts"]:
                xs = [max(r["calls"], .01) for r in v["fronts"][a]]
                ax.step(xs, [r["leak"] for r in v["fronts"][a]], where="post", marker="o", ms=3, lw=1.4, color=col[a])
        ax.set_xscale("log")
        ax.set_xlabel("calls per world (log)")
        ax.set_ylabel("new reconstruction rate")
        ax.set_title(f"Controlled simulation, k={k}", fontsize=10)
        ax.grid(alpha=.25)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower right", ncol=2, fontsize=8, bbox_to_anchor=(0.98, 0.08))
    fig.tight_layout()
    out = Path(__file__).parent / "results" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "fig_degc_pareto.png", dpi=200, bbox_inches="tight")
    fig.savefig(out / "fig_degc_pareto.svg", bbox_inches="tight")


def main():
    res = {"stage_b": {}, "sim": {}}
    for tag in ("llm_noisy_or", "oracle_noisy_or", "llm_max"):
        if (D / f"stage_b_{tag}.json").exists():
            res["stage_b"][tag] = stage_b(tag)
    if (D / "sim").exists():
        res["sim"] = sim()
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    (out / "analysis.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    plots(res)
    print("ok")


if __name__ == "__main__":
    main()
