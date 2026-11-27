"""Estimate the witness-misspecification prior from the E3b-v2 GLM-5.2 attack logs (PREREG_PRIOR.md)."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from experiments.cogniguard_cgc4 import a_exp as AX
from experiments.cogniguard_cgc5.c5_exp import build
from experiments.cogniguard_ms import ms

HERE = Path(__file__).parent
OUT = HERE / "results"
E3 = HERE.parents[1] / "capd_e3b2_20261124/results"
DATA = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data")
TYPES = ("construct", "misconception", "number", "answer", "subject")


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def views(path):
    agg = defaultdict(lambda: {"hits": 0, "n": 0, "p": []})
    for r in csv.DictReader(open(path)):
        if r["valid"] != "True":
            continue
        a = agg[r["view_id"]]
        a["hits"] += int(r["hit"])
        a["n"] += 1
        a["p"].append(float(r["p_true"]))
    return agg


def load():
    items = [json.loads(l) for l in open(DATA / "e3b2/items.jsonl")]
    feat = {}
    for l in open(DATA / "eedi_exam/units.jsonl"):
        r = json.loads(l)
        feat[r["unit_id"]] = r["predicate"]["feature"]
    orig, para = views(E3 / "control_attack.csv"), views(E3 / "attack.csv")
    units, combos = [], []
    for it in items:
        for v in it["views"]:
            o, p = orig.get(v["text_id"]), para.get(v["text_id"])
            if v["role"] == "unit" and o and o["n"] >= 3:
                u = v["gold_units"][0]
                units.append({"target": it["target_id"], "unit": u, "type": feat[u], "consistent": v["consistent"],
                              "hid": o["hits"] / o["n"] > 0.5, "hid_p": float(np.mean(o["p"])) > 0.5,
                              "hits": o["hits"], "n": o["n"],
                              "hid_para": (p["hits"] / p["n"] > 0.5) if p and p["n"] >= 3 else None})
            if v["role"] == "combo" and o and o["n"] >= 3:
                combos.append({"target": it["target_id"], "hits": o["hits"], "n": o["n"],
                               "unexploited": o["hits"] / o["n"] <= 0.5})
    tids = sorted({it["target_id"] for it in items})
    est = set(tids[0::2])          # odd positions (1st, 3rd, ...) = estimation; even positions = validation
    return units, combos, est


def bucket(c):
    return "2" if c == 2 else ("3-4" if c <= 4 else ">=5")


def fit(rows, key):
    k, n = defaultdict(int), defaultdict(int)
    for r in rows:
        g = key(r)
        k[g] += r["hid"]
        n[g] += 1
    return {g: {"rate": (k[g] + 1) / (n[g] + 2), "k": k[g], "n": n[g], "wilson": wilson(k[g], n[g])} for g in n}


def score(model, key, rows, fallback):
    ll = br = 0.0
    for r in rows:
        p = model.get(key(r), {"rate": fallback})["rate"]
        y = r["hid"]
        ll += math.log(p if y else 1 - p)
        br += (p - y) ** 2
    return {"loglik": ll, "brier": br / len(rows), "n": len(rows)}


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return {"agreement": po, "kappa": (po - pe) / (1 - pe) if pe < 1 else None, "n": n}


def estimate():
    units, combos, est = load()
    tr = [u for u in units if u["target"] in est]
    va = [u for u in units if u["target"] not in est]
    pi = (sum(u["hid"] for u in tr) + 1) / (len(tr) + 2)
    M = {"M0": ({"all": {"rate": pi}}, lambda r: "all"), "M1": (fit(tr, lambda r: r["type"]), lambda r: r["type"]),
         "M2": (fit(tr, lambda r: bucket(r["consistent"])), lambda r: bucket(r["consistent"]))}
    out = {"n_units": len(units), "n_est": len(tr), "n_val": len(va),
           "overall": {"k": sum(u["hid"] for u in units), "n": len(units),
                       "rate": sum(u["hid"] for u in units) / len(units), "wilson": wilson(sum(u["hid"] for u in units), len(units))},
           "overall_sensitivity_p_true": sum(u["hid_p"] for u in units) / len(units),
           "models": {}, "validation": {}}
    for name, (m, key) in M.items():
        out["models"][name] = m
        out["validation"][name] = score(m, key, va, pi)
    out["by_type_all"] = fit(units, lambda r: r["type"])
    out["by_bucket_all"] = fit(units, lambda r: bucket(r["consistent"]))
    pairs = [(u["hid"], u["hid_para"]) for u in units if u["hid_para"] is not None]
    out["retest_orig_vs_paraphrase"] = kappa([a for a, _ in pairs], [b for _, b in pairs])
    out["retest_para_rate"] = sum(b for _, b in pairs) / len(pairs)
    k = sum(c["unexploited"] for c in combos)
    out["formal_witness_unexploited"] = {"k": k, "n": len(combos), "rate": k / len(combos), "wilson": wilson(k, len(combos))}
    return out, units


def real_misspec(units):
    """Section 4: Eedi instances whose true witnesses add the attacker-found single-unit leaks."""
    lines = (DATA / "eedi_exam/witness_sets.jsonl").read_text().splitlines()
    index = {json.loads(l)["target_id"]: i for i, l in enumerate(lines)}
    hid_by_t = defaultdict(list)
    for u in units:
        if u["hid"]:
            hid_by_t[u["target"]].append(u["unit"])
    rows = []
    for tid in sorted({u["target"] for u in units}):
        i = index[tid]
        inst = build("eedi", (i,))
        if inst is None:
            continue
        uni = json.loads(lines[i])["universe"]
        pos = {u: j for j, u in enumerate(uni)}
        Wh = [1 << pos[u] for u in hid_by_t[tid] if u in pos]
        it = ms.true_instance(inst, Wh)
        q = AX.q_variants(inst, i)["emp"]
        seqs = AX.sequences(inst, i, 20, inst.q)
        res = {m: ms.run(inst, Wh, ms.make(m, inst, it, q), seqs, i) for m in ms.DEV_METHODS}
        rows.append({"target": tid, "n_hidden": len(Wh), "res": {m: {k: v for k, v in r.items() if k != "U_ep"} for m, r in res.items()}})
    rng = np.random.default_rng(0)
    summ = {"n": len(rows), "with_hidden": sum(r["n_hidden"] > 0 for r in rows), "U": {}, "breach": {}, "delta_U_pp": {}}
    for m in ms.DEV_METHODS:
        summ["U"][m] = float(np.mean([r["res"][m]["U"] for r in rows]))
        summ["breach"][m] = float(np.mean([r["res"][m]["breach"] for r in rows]))
        if m != "A1":
            d = np.array([100 * (r["res"][m]["U"] - r["res"]["A1"]["U"]) for r in rows])
            s = d[rng.integers(0, len(d), size=(2000, len(d)))].mean(1)
            summ["delta_U_pp"][m] = {"mean": float(d.mean()), "lo": float(np.percentile(s, 2.5)), "hi": float(np.percentile(s, 97.5))}
    return summ, rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    out, units = estimate()
    (OUT / "prior.json").write_text(json.dumps(out, indent=1) + "\n")
    summ, rows = real_misspec(units)
    (OUT / "real_misspec.json").write_text(json.dumps({"summary": summ, "rows": rows}, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k not in ("models",)}, indent=1))
    print(json.dumps(out["models"]["M1"], indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()


def exploratory():
    """Post-data (DEVIATIONS P1/P2): null model of a predicate-optimal attacker, and the real-misspec run
    restricted to units with consistent >= 3 (excluding units that sit exactly at tau)."""
    from math import comb
    units, _, _ = load()

    def tail(n, p):
        return sum(comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(n // 2 + 1, n + 1))

    null = {}
    for name, sel in (("all", lambda u: True), ("c=2", lambda u: u["consistent"] == 2),
                      ("c=3-4", lambda u: 3 <= u["consistent"] <= 4), ("c>=5", lambda u: u["consistent"] >= 5)):
        xs = [u for u in units if sel(u)]
        null[name] = {"n": len(xs), "observed": sum(u["hid"] for u in xs) / len(xs),
                      "null_predicate_optimal": sum(tail(u["n"], 1 / u["consistent"]) for u in xs) / len(xs)}
    by_type = {}
    for t in TYPES:
        xs = [u for u in units if u["type"] == t]
        by_type[t] = {"n": len(xs), "observed": sum(u["hid"] for u in xs) / len(xs),
                      "null_predicate_optimal": sum(tail(u["n"], 1 / u["consistent"]) for u in xs) / len(xs)}
    strict = [dict(u, hid=u["hid"] and u["consistent"] >= 3) for u in units]
    summ, _ = real_misspec(strict)
    out = {"null": null, "null_by_type": by_type, "real_misspec_c_ge_3": summ}
    (OUT / "exploratory.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
