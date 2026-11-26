"""P1 analysis (PREREG section 3). Paired bootstrap over instances, 2000 resamples, seed 0.
Original regimes: MPC_OPT / OPT_CANON_SERVE / OPT_CANON taken from CGC5 test_raw (same seeds, same sequences);
A1 re-run here must equal CGC5's A1 episode by episode."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

from experiments.cogniguard_sp.sp_exp import ORIG, REGIMES, STRESS

OUT = Path(__file__).parent / "results"
CGC5 = Path(__file__).parents[1] / "cogniguard_cgc5/results/test_raw.json.gz"
B = 2000


def cgc5_index():
    idx = {}
    for r in json.load(gzip.open(CGC5, "rt")):
        if r["kind"] == "synth":
            reg, key = r["key"][1], r["key"][0]
        elif r["kind"] in ("ksl", "eedi"):
            reg, key = r["kind"], r["key"][0]
        else:
            continue
        idx[(reg, key)] = r["res"]
    return idx


def boot(x, rng):
    x = np.asarray(x)
    m = rng.integers(0, len(x), size=(B, len(x)))
    s = x[m].mean(1)
    return float(x.mean()), float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))


def main():
    rows = json.load(gzip.open(OUT / "test_rows.json.gz", "rt"))
    c5 = cgc5_index()
    rng = np.random.default_rng(0)
    mismatch = 0
    per = {}
    for r in rows:
        res = dict(r["res"])
        if r["regime"] in ORIG:
            old = c5.get((r["regime"], r["key"]))
            if old is None:
                continue
            if old["A1"].get("per_episode") != res["A1"]["per_episode"]:
                mismatch += 1
            for m in ("MPC_OPT", "OPT_CANON_SERVE", "OPT_CANON"):
                res[m] = old.get(m, {"skipped": "absent"})
        per.setdefault(r["regime"], []).append((r, res))
    methods = [m for m in ("A1", "OCOST", "SP_LP", "SP_DISP", "SP_MYOPIC", "A1_D", "SP_D", "MPC_OPT", "OPT_CANON_SERVE", "OPT_CANON")
               if any(m in res for v in per.values() for _, res in v)]
    out = {"a1_cgc5_mismatch_instances": mismatch, "regimes": {}}
    for reg in REGIMES:
        items = per.get(reg, [])
        if not items:
            continue
        R = {"n": len(items)}
        comp = {m: [res[m]["completion"] if "completion" in res.get(m, {}) else None for _, res in items] for m in methods}
        R["completion"] = {m: float(np.mean([v for v in comp[m] if v is not None])) for m in methods if any(v is not None for v in comp[m])}
        R["ms"] = {m: float(np.mean([res[m]["ms"] for _, res in items if "ms" in res.get(m, {})]))
                   for m in methods if any("ms" in res.get(m, {}) for _, res in items)}
        R["unsafe"] = {m: int(sum(res[m].get("unsafe", res[m].get("unsafe_episodes", 0)) for _, res in items if "completion" in res.get(m, {}))) for m in methods}
        R["delta_pp"] = {}
        for m, ref in (("SP_LP", "A1"), ("SP_DISP", "A1"), ("SP_MYOPIC", "A1"), ("OCOST", "A1"), ("SP_LP", "OCOST"),
                       ("SP_D", "A1_D"), ("SP_D", "A1"), ("A1_D", "A1"), ("OPT_CANON_SERVE", "A1"), ("OPT_CANON", "A1_D"), ("MPC_OPT", "A1")):
            pairs = [(a, b) for a, b in zip(comp.get(m, []), comp.get(ref, [])) if a is not None and b is not None]
            if pairs:
                d = [100 * (a - b) for a, b in pairs]
                R["delta_pp"][f"{m}-{ref}"] = dict(zip(("mean", "lo", "hi"), boot(d, rng)), n=len(d))
        # capture vs the matching upper bound on instances where it exists
        for m, ref, up in (("SP_LP", "A1", "OPT_CANON_SERVE"), ("SP_D", "A1_D", "OPT_CANON")):
            tr = [(a, b, c) for a, b, c in zip(comp.get(m, []), comp.get(ref, []), comp.get(up, [])) if None not in (a, b, c)]
            if tr:
                gap = np.mean([c - b for a, b, c in tr])
                R[f"capture_{m}"] = float(np.mean([a - b for a, b, c in tr]) / gap) if gap > 1e-12 else None
                R[f"headroom_pp_{m}"] = float(100 * gap)
        ag = {}
        for m in ("SP_LP", "OCOST", "SP_D"):
            a = sum(r["agree_A1"]["traj_multi"][m][0] for r, _ in items if m in r["agree_A1"].get("traj_multi", {}))
            n = sum(r["agree_A1"]["traj_multi"][m][1] for r, _ in items if m in r["agree_A1"].get("traj_multi", {}))
            if n:
                ag[m] = a / n
        R["traj_agreement_multi"] = ag
        out["regimes"][reg] = R

    def gate(m, ref, cap_key):
        ok, worse, cis = [], [], []
        for reg, R in out["regimes"].items():
            d = R["delta_pp"].get(f"{m}-{ref}")
            if not d:
                continue
            cis.append(d["lo"] <= 0 <= d["hi"])
            if d["hi"] < -0.3:
                worse.append(reg)
            cap = R.get(cap_key)
            if d["mean"] >= 0.5 and d["lo"] > 0 and cap is not None and cap >= 0.5:
                ok.append(reg)
        tot_a = sum(R["traj_agreement_multi"].get(m, 0) * 1 for R in out["regimes"].values())
        agree_all = None
        num = den = 0
        for r in rows:
            t = r["agree_A1"].get("traj_multi", {}).get(m)
            if t:
                num += t[0]
                den += t[1]
        agree_all = num / den if den else None
        if len(ok) >= 2 and not worse and any(x in ORIG for x in ok):
            v = "GO"
        elif len(ok) >= 2 and not worse:
            v = "LIMITED_GO"
        elif (agree_all is not None and agree_all > 0.95) or (cis and all(cis)):
            v = "MERGE"
        else:
            v = "STOP"
        return {"pass_regimes": ok, "significantly_worse": worse, "all_ci_contain_0": bool(cis) and all(cis),
                "traj_agreement_all": agree_all, "verdict": v}

    out["gate_primary_SP_LP"] = gate("SP_LP", "A1", "capture_SP_LP")
    if "SP_D" in methods:
        out["gate_secondary_SP_D"] = gate("SP_D", "A1_D", "capture_SP_D")
    (OUT / "p1_analysis.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "regimes"}, indent=1))
    for reg, R in out["regimes"].items():
        print(reg, R["n"], {k: round(v["mean"], 2) for k, v in R["delta_pp"].items()}, R.get("capture_SP_LP"), R["traj_agreement_multi"])


if __name__ == "__main__":
    main()
