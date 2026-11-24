"""Phase 2 analysis (PREREG.md §4-6).

  dev:    python -m experiments.cogniguard_comparison_phase2.analyze --data <root> --tag dev --choose-points
  formal: python -m experiments.cogniguard_comparison_phase2.analyze --data <root> --tag formal --points <json>
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

BOOT, BOOT_SEED = 5000, 20261126
HARM_TARGETS = (0.01, 0.05, 0.10)
UTIL_TARGETS = (0.90, 0.95, 0.99)
FAMILIES = {"OCELOT-PF[field]": "OCELOT-PF[field](B=", "OCELOT-PF[trajectory]": "OCELOT-PF[trajectory](B=",
            "SumLeaks-ToM": "SumLeaks-ToM(rho="}
FIXED = ("B0-Access", "CAPD(k=K)", "CAPD(k=1)", "Staddon-def(k=K)", "CrowdControl", "WS04-quota(k=K)",
         "SumLeaks-Local(CoT+L+H)", "SumLeaks-CoDef", "ExactEnum(k=K)")


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def ci(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return [None, None]
    rng = random.Random(BOOT_SEED)
    ms = sorted(sum(xs[rng.randrange(len(xs))] for _ in xs) / len(xs) for _ in range(BOOT))
    return [ms[int(0.025 * BOOT)], ms[int(0.975 * BOOT) - 1]]


def load(path):
    idx = defaultdict(dict)
    for line in path.read_text().splitlines():
        r = json.loads(line)
        idx[(r["dataset"], r["prop"], r["k"], r["mode"], r["rule"])][r["seed"]] = r
    return idx


def cells(idx):
    return sorted({(d, p, k) for d, p, k, *_ in idx})


def resolve(name, k):
    return name.replace("K", str(k)) if "(k=K)" in name else name


def param(rule, prefix):
    return float(rule[len(prefix):-1])


def choose_points(idx):
    out = {}
    for d, p, k in cells(idx):
        fam_out = {}
        for fam, prefix in FAMILIES.items():
            pts = []
            for (dd, pp, kk, mode, rule), runs in idx.items():
                if (dd, pp, kk, mode) == (d, p, k, "snapshot") and rule.startswith(prefix):
                    pts.append((param(rule, prefix), mean([r["harmful_rate"] for r in runs.values()]),
                                mean([r["utility"] for r in runs.values()])))
            res = {}
            for h in HARM_TARGETS:
                ok = [x for x in pts if x[1] is not None and x[1] <= h]
                res[f"harm<={h:g}"] = max(ok, key=lambda x: (x[2], -x[0]))[0] if ok else None
            for u in UTIL_TARGETS:
                ok = [x for x in pts if x[2] is not None and x[2] >= u]
                res[f"util>={u:g}"] = min(ok, key=lambda x: (x[1], x[0]))[0] if ok else None
            fam_out[fam] = res
        out[f"{d}/{p}/k{k}"] = fam_out
    return out


def rule_name(fam, value):
    return f"{FAMILIES[fam]}{value:g})"


def summarize(runs):
    keys = ("harmful_rate", "harmful_rate_nonhistorical", "utility", "over_refusal", "unauth_success_rate",
            "p50_us", "p95_us", "coalition_violation", "new_secret_reconstruction", "historical_reconstructable",
            "external_reconstructable")
    seeds = sorted(runs)
    return {m: {"mean": mean([runs[s].get(m) for s in seeds]), "ci95": ci([runs[s].get(m) for s in seeds])}
            for m in keys if any(m in runs[s] for s in seeds)}


def paired(A, B, metric):
    seeds = sorted(set(A) & set(B))
    d = [A[s][metric] - B[s][metric] for s in seeds if A[s].get(metric) is not None and B[s].get(metric) is not None]
    return {"diff": mean(d), "ci95": ci(d), "n": len(d)}


def formal(idx, points):
    table, contrasts, matched, path = {}, {}, {}, {}
    for d, p, k in cells(idx):
        key = f"{d}/{p}/k{k}"
        pts = points.get(key, {})
        rows = {}
        for f in FIXED:
            n = resolve(f, k)
            if (d, p, k, "snapshot", n) in idx:
                rows[n] = summarize(idx[(d, p, k, "snapshot", n)])
        for fam in FAMILIES:
            for tgt, v in pts.get(fam, {}).items():
                if v is not None and (d, p, k, "snapshot", rule_name(fam, v)) in idx:
                    rows[f"{fam}@{tgt}"] = {"param": v, **summarize(idx[(d, p, k, "snapshot", rule_name(fam, v))])}
        table[key] = rows
        ours = idx.get((d, p, k, "snapshot", f"CAPD(k={k})"), {})
        c = {}
        for n in rows:
            if n == f"CAPD(k={k})":
                continue
            src = n
            if "@" in n:
                fam, tgt = n.split("@")
                src = rule_name(fam, pts[fam][tgt])
            other = idx.get((d, p, k, "snapshot", src), {})
            c[f"M3 vs {n}"] = {m: paired(ours, other, m) for m in ("harmful_rate", "utility")}
        contrasts[key] = c
        # matched targets: every method's achieved formal value at the frozen dev point (NA if none)
        mt = {}
        for tgt in [f"harm<={h:g}" for h in HARM_TARGETS] + [f"util>={u:g}" for u in UTIL_TARGETS]:
            entry = {}
            for fam in FAMILIES:
                v = pts.get(fam, {}).get(tgt)
                entry[fam] = None if v is None else {"param": v, **{m: summarize(idx[(d, p, k, "snapshot", rule_name(fam, v))])[m]["mean"]
                                                                    for m in ("harmful_rate", "utility")}}
            for f in FIXED:
                n = resolve(f, k)
                if (d, p, k, "snapshot", n) not in idx:
                    continue
                s = summarize(idx[(d, p, k, "snapshot", n)])
                h, u = s["harmful_rate"]["mean"], s["utility"]["mean"]
                meets = (h is not None and h <= float(tgt.split("<=")[1])) if tgt.startswith("harm") else \
                        (u is not None and u >= float(tgt.split(">=")[1]))
                entry[n] = {"harmful_rate": h, "utility": u, "meets_target": meets}
            mt[tgt] = entry
        matched[key] = mt
        path[key] = {r: summarize(runs) for (dd, pp, kk, mode, r), runs in idx.items()
                     if (dd, pp, kk, mode) == (d, p, k, "path")}
    return table, contrasts, matched, path


def exact_check(req_path):
    mism, n = Counter(), Counter()
    with gzip.open(req_path, "rt") as h:
        for line in h:
            r = json.loads(line)
            if r["mode"] != "snapshot":
                continue
            k = r["k"]
            dec = r["decisions"]
            n[r["dataset"]] += 1
            mism[r["dataset"]] += dec[f"CAPD(k={k})"] != dec[f"ExactEnum(k={k})"]
    return {d: {"requests": n[d], "mismatches": mism[d]} for d in n}


def verdicts(res, points):
    """PREREG §3 (A0-A4)."""
    mism = sum(v["mismatches"] for v in res["capd_vs_exact"].values())
    out = {"A0": "pass" if res["unauth_success_total"] == 0 and mism == 0 else "INVALID"}
    for key, c in res["contrasts"].items():
        k = int(key.split("/k")[1])
        cell = {}
        groups = {"A1": ["OCELOT-PF[field]@harm<=0.05", "OCELOT-PF[trajectory]@harm<=0.05"],
                  "A2": ["SumLeaks-Local(CoT+L+H)", "SumLeaks-CoDef", "SumLeaks-ToM@harm<=0.05"],
                  "A3": [f"Staddon-def(k={k})", "CrowdControl", f"WS04-quota(k={k})"]}
        for g, names in groups.items():
            for n in names:
                if g == "A2" and n == "SumLeaks-CoDef" and k == 1:
                    cell[n] = "NA (identical to CA-PD at k=1)"
                    continue
                cc = c.get(f"M3 vs {n}")
                if cc is None:
                    cell[n] = "NA (no dev operating point)"
                    continue
                u, h = cc["utility"]["ci95"], cc["harmful_rate"]["ci95"]
                ok = u[0] is not None and u[0] > 0 and h[1] is not None and h[1] <= 0.01
                cell[n] = "supported" if ok else "not supported"
        t = res["table"][key]
        a, e = t.get(f"CAPD(k={k})"), t.get(f"ExactEnum(k={k})")
        cell["A4 p95 CAPD/ExactEnum"] = (a["p95_us"]["mean"] / e["p95_us"]["mean"]) if a and e else None
        out[key] = cell
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--choose-points", action="store_true")
    ap.add_argument("--points", type=Path)
    a = ap.parse_args()
    base = a.data / "comparison_phase2" / a.tag
    idx = load(base / "runs.jsonl")
    if a.choose_points:
        pts = choose_points(idx)
        (base / "operating_points.json").write_text(json.dumps(pts, indent=1) + "\n")
        print(base / "operating_points.json")
        return
    points = json.loads(a.points.read_text())
    table, contrasts, matched, path = formal(idx, points)
    res = {"runs": sum(len(v) for v in idx.values()),
           "unauth_success_total": sum(r.get("unauth_success", 0) for v in idx.values() for r in v.values()),
           "capd_vs_exact": exact_check(base / "requests.jsonl.gz"),
           "table": table, "contrasts": contrasts, "matched": matched, "path": path}
    res["verdicts"] = verdicts(res, points)
    (base / "analysis.json").write_text(json.dumps(res, indent=1) + "\n")
    print(base / "analysis.json")


if __name__ == "__main__":
    main()
