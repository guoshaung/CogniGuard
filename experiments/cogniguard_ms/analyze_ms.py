"""Analysis and gates (PREREG section 5). Paired bootstrap over instances, B = 2000, seed 0."""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np

from experiments.cogniguard_ms.ms import MODES, RHOS

OUT = Path(__file__).parent / "results"
B = 2000
REGS = ("base", "tight", "overlap", "conflict", "ksl", "eedi")
PAIRS = [("OCELOT_P", "A1"), ("PFLOW_P", "A1"), ("DYNCQE_P", "A1"), ("OCOST", "A1"), ("CAPD_FIRST", "A1"),
         ("MPC_OPT", "A1"), ("ORACLE_A1", "A1"), ("OCELOT_P", "ORACLE_A1"), ("PFLOW_P", "ORACLE_A1")]


def boot(x, rng):
    x = np.asarray(x)
    s = x[rng.integers(0, len(x), size=(B, len(x)))].mean(1)
    return {"mean": float(x.mean()), "lo": float(np.percentile(s, 2.5)), "hi": float(np.percentile(s, 97.5)), "n": len(x)}


def main(stage):
    rows = json.load(gzip.open(OUT / f"{stage}_rows.json.gz", "rt"))
    rng = np.random.default_rng(0)
    out = {"stage": stage, "cells": {}}
    unsafe = 0
    for mode in MODES:
        for rho in RHOS:
            c = f"{mode}|{rho}"
            C = {}
            for reg in REGS:
                rs = [r for r in rows if r["regime"] == reg]
                if not rs:
                    continue
                cell = [r["cells"][c] for r in rs]
                meths = list(cell[0]["res"])
                R = {"n": len(rs), "mean_hidden": float(np.mean([x["n_hidden"] for x in cell])),
                     "U": {m: float(np.mean([x["res"][m]["U"] for x in cell])) for m in meths},
                     "raw": {m: float(np.mean([x["res"][m]["raw"] for x in cell])) for m in meths},
                     "breach": {m: float(np.mean([x["res"][m]["breach"] for x in cell])) for m in meths},
                     "ms": {m: float(np.mean([x["res"][m]["ms"] for x in cell])) for m in meths}, "delta_U_pp": {}}
                unsafe += sum(x["res"][m]["unsafe_obs"] for x in cell for m in meths)
                for a, b in PAIRS:
                    if a in meths and b in meths:
                        R["delta_U_pp"][f"{a}-{b}"] = boot([100 * (x["res"][a]["U"] - x["res"][b]["U"]) for x in cell], rng)
                d1, d2 = R["delta_U_pp"]["OCELOT_P-A1"], R["delta_U_pp"]["PFLOW_P-A1"]
                R["pass"] = all(d["mean"] >= 1.0 and d["lo"] > 0 for d in (d1, d2))
                C[reg] = R
            passed = [r for r, R in C.items() if R["pass"]]
            out["cells"][c] = {"regimes": C, "pass_regimes": passed,
                               "valid": len(passed) >= 4 and any(r in ("ksl", "eedi") for r in passed)}
    out["unsafe_obs_total"] = unsafe
    valid = [c for c, v in out["cells"].items() if v["valid"]]
    if any(c.split("|")[0] in ("near", "shrink") for c in valid):
        verdict = "GO"
    elif valid:
        verdict = "LIMITED"
    else:
        verdict = "STOP"
    out["valid_cells"], out["verdict"] = valid, verdict
    (OUT / f"{stage}_analysis.json").write_text(json.dumps(out, indent=1) + "\n")
    print("verdict", verdict, "valid", valid, "unsafe_obs", unsafe)
    for c, v in out["cells"].items():
        print(c, "pass:", v["pass_regimes"])
        for reg, R in v["regimes"].items():
            d = R["delta_U_pp"]
            print(f"  {reg:9s} hid={R['mean_hidden']:.1f} U_A1={100*R['U']['A1']:.1f} br_A1={R['breach']['A1']:.2f} "
                  + " ".join(f"{k.split('-')[0]}={v['mean']:+.1f}[{v['lo']:+.1f},{v['hi']:+.1f}]" for k, v in d.items()
                             if k.endswith("-A1")))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "test")
