"""Phase 2 reporting: unified metric table, matched targets, DESCRIPTIVE classification and the
POST-HOC unbounded-oracle sensitivity. Nothing here changes the frozen A0-A4 verdicts.

  python -m experiments.cogniguard_comparison_phase2.report --data <root> --points <operating_points.json> --out <dir>
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from experiments.cogniguard_comparison_phase2.analyze import ci, load, mean

MAIN = ("B0-Access", "CAPD(k=K)", "CAPD(k=1)", "Staddon-def(k=K)", "CrowdControl", "WS04-quota(k=K)",
        "SumLeaks-Local(CoT+L+H)", "SumLeaks-CoDef", "ExactEnum(k=K)")
FAM = {"OCELOT-PF[field]": "OCELOT-PF[field](B={:g})", "OCELOT-PF[trajectory]": "OCELOT-PF[trajectory](B={:g})",
       "SumLeaks-ToM": "SumLeaks-ToM(rho={:g})"}
TARGETS = ("harm<=0.01", "harm<=0.05", "harm<=0.1", "util>=0.9", "util>=0.95", "util>=0.99")


def methods(points, cell, k):
    out = {m.replace("K", str(k)): m.replace("K", str(k)) for m in MAIN}
    for fam, fmt in FAM.items():
        for tgt, v in points.get(cell, {}).get(fam, {}).items():
            if v is not None:
                out[f"{fam}@{tgt}"] = fmt.format(v)
    return out


def classify(dh, du):
    """Descriptive, from paired 95% CIs (M3 minus baseline)."""
    hl, hh = dh["ci95"]
    ul, uh = du["ci95"]
    if None in (hl, hh, ul, uh):
        return "NA"
    safer, less_safe = hh < -0.005, hl > 0.005
    more_useful, less_useful = ul > 0.005, uh < -0.005
    if not less_safe and not less_useful and (safer or more_useful):
        return "M3 dominates" if (safer and more_useful) else ("M3 safer, equal utility" if safer else
                                                               "M3 more useful, equal safety")
    if not safer and not more_useful and (less_safe or less_useful):
        return "baseline dominates"
    if more_useful and less_safe:
        return "trade-off: M3 more useful, baseline safer"
    if safer and less_useful:
        return "trade-off: M3 safer, baseline more useful"
    return "equivalent"


def paired(A, B, m):
    seeds = sorted(set(A) & set(B))
    d = [A[s][m] - B[s][m] for s in seeds if A[s].get(m) is not None and B[s].get(m) is not None]
    return {"diff": mean(d), "ci95": ci(d)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--points", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    pts = json.loads(a.points.read_text())
    base = a.data / "comparison_phase2"
    F = load(base / "formal" / "runs.jsonl")
    S = load(base / "sensitivity_unbounded" / "runs.jsonl")
    cells = sorted({(d, p, k) for d, p, k, *_ in F})
    rows, cls, matched, sens = [], {}, {}, {}
    metrics = ("harmful_rate", "harmful_rate_nonhistorical", "utility", "over_refusal", "unauth_success_rate",
               "p50_us", "p95_us")
    for d, p, k in cells:
        cell = f"{d}/{p}/k{k}"
        ms = methods(pts, cell, k)
        ours = F[(d, p, k, "snapshot", f"CAPD(k={k})")]
        ours_s = S.get((d, p, k, "snapshot_unbounded_oracle", f"CAPD(k={k})"), {})
        cls[cell], sens[cell] = {}, {}
        for label, rule in ms.items():
            runs = F.get((d, p, k, "snapshot", rule))
            if not runs:
                continue
            row = {"dataset": d, "prop": p, "k": k, "protocol": "A-snapshot", "method": label, "rule": rule}
            for m in metrics:
                xs = [r.get(m) for r in runs.values()]
                row[m], (row[m + "_lo"], row[m + "_hi"]) = mean(xs), ci(xs)
            path = F.get((d, p, k, "path", rule))
            if path:
                for m in ("coalition_violation", "new_secret_reconstruction"):
                    xs = [r.get(m) for r in path.values()]
                    row[m], (row[m + "_lo"], row[m + "_hi"]) = mean(xs), ci(xs)
            rows.append(row)
            if rule != f"CAPD(k={k})":
                cls[cell][label] = classify(paired(ours, runs, "harmful_rate"), paired(ours, runs, "utility"))
                srun = S.get((d, p, k, "snapshot_unbounded_oracle", rule))
                if srun:
                    sens[cell][label] = {"harm_M3": mean([r["harmful_rate"] for r in ours_s.values()]),
                                         "harm_base": mean([r["harmful_rate"] for r in srun.values()]),
                                         "util_M3": mean([r["utility"] for r in ours_s.values()]),
                                         "util_base": mean([r["utility"] for r in srun.values()]),
                                         "class": classify(paired(ours_s, srun, "harmful_rate"),
                                                           paired(ours_s, srun, "utility"))}
        # matched targets on the FORMAL set: who meets each target and with what utility / harm
        mt = {}
        for tgt in TARGETS:
            kind, thr = ("harm", float(tgt.split("<=")[1])) if tgt.startswith("harm") else ("util", float(tgt.split(">=")[1]))
            entry = {}
            for label, rule in ms.items():
                if "@" in label and not label.endswith(tgt):
                    continue
                runs = F.get((d, p, k, "snapshot", rule))
                if not runs:
                    continue
                h, u = mean([r["harmful_rate"] for r in runs.values()]), mean([r["utility"] for r in runs.values()])
                meets = (h is not None and h <= thr) if kind == "harm" else (u is not None and u >= thr)
                entry[label.split("@")[0]] = {"harm": h, "util": u, "meets": meets}
            best = None
            for name, v in entry.items():
                if not v["meets"] or name == "B0-Access":
                    continue
                score = v["util"] if kind == "harm" else -v["harm"]
                if best is None or score > best[1]:
                    best = (name, score)
            mt[tgt] = {"methods": entry, "best_meeting_target": best[0] if best else "NA"}
        matched[cell] = mt
    with open(a.out / "metrics_table.csv", "w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=sorted({k for r in rows for k in r}, key=lambda x: (x not in (
            "dataset", "prop", "k", "protocol", "method", "rule"), x)))
        w.writeheader()
        w.writerows(rows)
    (a.out / "classification_descriptive.json").write_text(json.dumps(cls, indent=1) + "\n")
    (a.out / "matched_targets.json").write_text(json.dumps(matched, indent=1) + "\n")
    (a.out / "sensitivity_unbounded_oracle.json").write_text(json.dumps(sens, indent=1) + "\n")
    print(a.out)


if __name__ == "__main__":
    main()
