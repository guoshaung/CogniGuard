"""Analysis for Phase 1 (PREREG.md §5–6). Paired bootstrap over seeds (5000, seed 20261125).

  python -m experiments.cogniguard_nowm_phase1.analyze --data <dir> --tag pilot|formal
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

BOOT, BOOT_SEED = 5000, 20261125
METRICS = ("harmful_rate", "utility", "violation_rate", "unneeded_rate", "unauth_success_rate", "p50_us", "p95_us")
ARMS = {  # display name -> (rule, layer); rule "CAPD(k=K)" is resolved per k
    "B0 access control": ("B0", "receipts"),
    "B1 budget (best b)": ("B1*", "nli"),
    "B2 fixed quota": ("B2", "nli"),
    "B3 pairwise": ("B3", "nli"),
    "B4 global union": ("B4", "nli"),
    "M1 dyn-state + single": ("CAPD(k=1)", "nli"),
    "M2 receipts + CA-PD": ("CAPD(k=K)", "receipts"),
    "M3 CogniGuard-NoWM": ("CAPD(k=K)", "nli"),
    "Oracle": ("CAPD(k=K)", "true"),
}


def rule_name(rule, k):
    return rule.replace("K", str(k)) if rule.startswith("CAPD(k=K") else rule


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def boot_ci(per_seed: list[float]):
    xs = [x for x in per_seed if x is not None]
    if not xs:
        return (None, None)
    rng = random.Random(BOOT_SEED)
    ms = sorted(sum(xs[rng.randrange(len(xs))] for _ in xs) / len(xs) for _ in range(BOOT))
    return ms[int(0.025 * BOOT)], ms[int(0.975 * BOOT) - 1]


def load(data: Path, tag: str):
    runs = [json.loads(l) for l in (data / tag / "runs.jsonl").read_text().splitlines()]
    idx = defaultdict(dict)
    for r in runs:
        idx[(r["prop"], r["k"], r["rule"], r["layer"])][r["seed"]] = r
    return runs, idx


def pick(idx, prop, k, rule, layer, budgets=(1, 2, 3, 4, 6, 8)):
    """B1*: the budget chosen on the pilot (PREREG §3); here resolved by the frozen value passed in."""
    return idx.get((prop, k, rule_name(rule, k), layer), {})


def nondegeneracy(data: Path, tag: str):
    """Per (prop, k): oracle has both safe and dangerous requests; danger profile distribution."""
    out = {}
    with gzip.open(data / tag / "requests.jsonl.gz", "rt") as h:
        prof = defaultdict(Counter)
        cnt = defaultdict(Counter)
        for line in h:
            r = json.loads(line)
            if r["rule"] != "B0" or not r["auth"]:
                continue
            key = f"{r['prop']}/k{r['k']}"
            cnt[key]["safe" if r["oracle_safe"] else "danger"] += 1
            if not r["oracle_safe"]:
                prof[key][f"w{r['w']}/helpers{r['helpers']}/missing{r['missing']}"] += 1
    for key in cnt:
        p = prof[key]
        miss = Counter()
        for lab, n in p.items():
            miss[lab.split("/missing")[1]] += n
        out[key] = {"oracle_safe": cnt[key]["safe"], "oracle_danger": cnt[key]["danger"],
                    "danger_by_missing_units": dict(sorted(miss.items())),
                    "danger_k_lt_w": sum(n for lab, n in p.items()
                                         if int(lab.split("/")[0][1:]) > int(key.split("/k")[1])),
                    "danger_total": sum(p.values())}
    return out


def choose_best_b(idx, max_harm=0.05):
    """B1* per (prop, k): the budget with the highest mean utility among budgets whose mean harmful
    rate is <= max_harm on the nli layer; if none qualifies, the lowest-harm budget. Run on PILOT only."""
    out = {}
    for prop, k in sorted({(p, k) for p, k, *_ in idx}):
        cands = []
        for (p, kk, rule, layer), runs in idx.items():
            if p == prop and kk == k and layer == "nli" and rule.startswith("B1(b="):
                b = int(rule[5:-1])
                cands.append((b, mean([r["harmful_rate"] for r in runs.values()]), mean([r["utility"] for r in runs.values()])))
        ok = [c for c in cands if c[1] is not None and c[1] <= max_harm]
        best = max(ok, key=lambda c: (c[2], -c[0])) if ok else min(cands, key=lambda c: (c[1], -c[2]))
        out[f"{prop}/k{k}"] = best[0]
    return out


def table(idx, best_b):
    out = {}
    props = sorted({k[0] for k in idx})
    ks = sorted({k[1] for k in idx})
    for prop in props:
        for k in ks:
            cell = {}
            for name, (rule, layer) in ARMS.items():
                rule = f"B1(b={best_b[f'{prop}/k{k}']})" if rule == "B1*" else rule
                runs = idx.get((prop, k, rule_name(rule, k), layer), {})
                if not runs:
                    continue
                cell[name] = {m: {"mean": mean([r[m] for r in runs.values()]),
                                  "ci95": boot_ci([r[m] for r in sorted(runs.values(), key=lambda x: x["seed"])])}
                              for m in METRICS}
            out[f"{prop}/k{k}"] = cell
    return out


def paired(idx, prop, k, a, b, metric):
    A = idx.get((prop, k, rule_name(a[0], k), a[1]), {})
    B = idx.get((prop, k, rule_name(b[0], k), b[1]), {})
    seeds = sorted(set(A) & set(B))
    d = [A[s][metric] - B[s][metric] for s in seeds if A[s][metric] is not None and B[s][metric] is not None]
    lo, hi = boot_ci(d)
    return {"diff": mean(d), "ci95": [lo, hi], "n": len(d)}


def contrasts(idx, best_b):
    C = {}
    defs = {
        # algorithm effect, same evidence (nli layer for all)
        "M3 vs B2 (same evidence)": (("CAPD(k=K)", "nli"), ("B2", "nli")),
        "M3 vs B3 (same evidence)": (("CAPD(k=K)", "nli"), ("B3", "nli")),
        "M3 vs B4 (same evidence)": (("CAPD(k=K)", "nli"), ("B4", "nli")),
        "M3 vs M1 (CA-PD effect, same evidence)": (("CAPD(k=K)", "nli"), ("CAPD(k=1)", "nli")),
        # information effect, same rule
        "M3 vs M2 (evidence effect, same rule)": (("CAPD(k=K)", "nli"), ("CAPD(k=K)", "receipts")),
        "M2 vs receipts+single (CA-PD effect without evidence)": (("CAPD(k=K)", "receipts"), ("CAPD(k=1)", "receipts")),
        "M1 vs receipts+single (evidence effect without CA-PD)": (("CAPD(k=1)", "nli"), ("CAPD(k=1)", "receipts")),
        "Oracle vs M3 (remaining evidence gap)": (("CAPD(k=K)", "true"), ("CAPD(k=K)", "nli")),
    }
    for key in sorted({(p, k) for p, k, *_ in idx}):
        prop, k = key
        defs["M3 vs B1* (same evidence)"] = (("CAPD(k=K)", "nli"), (f"B1(b={best_b[f'{prop}/k{k}']})", "nli"))
        for name, (a, b) in defs.items():
            if k == 1 and "CA-PD effect" in name:
                continue
            C.setdefault(f"{prop}/k{k}", {})[name] = {m: paired(idx, prop, k, a, b, m)
                                                    for m in ("harmful_rate", "utility", "violation_rate")}
    return C


def matched(idx):
    """Same-safety utility and same-utility leakage over every rule x layer x parameter."""
    out = {}
    for prop in sorted({k[0] for k in idx}):
        for k in sorted({k[1] for k in idx}):
            pts = []
            for (p, kk, rule, layer), runs in idx.items():
                if p != prop or kk != k:
                    continue
                pts.append({"rule": rule, "layer": layer,
                            "harmful_rate": mean([r["harmful_rate"] for r in runs.values()]),
                            "utility": mean([r["utility"] for r in runs.values()]),
                            "violation_rate": mean([r["violation_rate"] for r in runs.values()])})
            res = {}
            for layer in ("receipts", "nli"):
                cand = [x for x in pts if x["layer"] == layer or x["rule"] == "B0"]
                safe = [x for x in cand if x["harmful_rate"] is not None and x["harmful_rate"] <= 0.05]
                useful = [x for x in cand if x["utility"] is not None and x["utility"] >= 0.95]
                res[layer] = {
                    "best_utility_at_harm<=0.05": max(safe, key=lambda x: x["utility"]) if safe else None,
                    "lowest_harm_at_utility>=0.95": min(useful, key=lambda x: x["harmful_rate"]) if useful else None,
                }
            out[f"{prop}/k{k}"] = {"points": pts, "matched": res}
    return out


def verdicts(C, nondeg, unauth):
    """PREREG §3-4."""
    def sig_lower(c):   # harmful diff CI upper < 0 and utility non-inferior
        h, u = c["harmful_rate"]["ci95"], c["utility"]["ci95"]
        return h[1] is not None and h[1] < 0 and u[0] is not None and u[0] >= -0.01
    out = {"H-Auth": "pass" if unauth == 0 else "IMPLEMENTATION ERROR"}
    valid = []
    for cell, v in nondeg.items():
        k = int(cell.split("/k")[1])
        ok = v["oracle_safe"] > 0 and v["oracle_danger"] > 0 and v["danger_k_lt_w"] > 0
        if k >= 2:
            ok = ok and any(int(m) >= 2 and n > 0 for m, n in v["danger_by_missing_units"].items() if m != "None")
        valid.append((cell, ok))
    out["validity"] = {c: ok for c, ok in valid}
    for cell, cs in C.items():
        k = int(cell.split("/k")[1])
        h1 = sig_lower(cs["M3 vs M1 (CA-PD effect, same evidence)"]) if k >= 2 else None
        h2 = sig_lower(cs["M3 vs M2 (evidence effect, same rule)"])
        h4 = {}
        for b in ("B1*", "B2", "B4"):
            c = cs[f"M3 vs {b} (same evidence)"]
            h, u = c["harmful_rate"]["ci95"], c["utility"]["ci95"]
            h4[b] = ("M3 dominates" if h[1] is not None and h[1] <= 0.01 and u[0] is not None and u[0] > 0
                     else "not dominated")
        out[cell] = {"H1 CA-PD independent": None if h1 is None else ("supported" if h1 else "not supported"),
                     "H2 dynamic state independent": "supported" if h2 else "not supported",
                     "H3 joint (both needed)": None if h1 is None else ("supported" if h1 and h2 else "not supported"),
                     "H4 vs same-evidence baselines": h4}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--best-b", type=Path, help="JSON {prop/k: budget} frozen from the pilot")
    ap.add_argument("--choose-best-b", action="store_true", help="pilot only: compute and write B1*")
    a = ap.parse_args()
    runs, idx = load(a.data, a.tag)
    if a.choose_best_b:
        best = choose_best_b(idx)
        (a.data / a.tag / "best_b.json").write_text(json.dumps(best, indent=1) + "\n")
    else:
        best = json.loads(a.best_b.read_text())
    a.best_b = best
    res = {"runs": len(runs), "seeds": sorted({r["seed"] for r in runs}),
           "unauth_success_total": sum(r["unauth_success"] for r in runs),
           "nondegeneracy": nondegeneracy(a.data, a.tag), "table": table(idx, a.best_b),
           "contrasts": contrasts(idx, a.best_b), "matched": matched(idx), "best_b": a.best_b}
    res["verdicts"] = verdicts(res["contrasts"], res["nondegeneracy"], res["unauth_success_total"])
    (a.data / a.tag / "analysis.json").write_text(json.dumps(res, indent=1) + "\n")
    print(a.data / a.tag / "analysis.json")


if __name__ == "__main__":
    main()
