"""Protocol E analysis: the frozen Protocol D analysis (with the D3 tie handling) applied to Protocol E results,
plus |W'| strata and meter quality (secondary)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from experiments.cogniguard_comparison_phase2.protocol_d import analyze_d as AD

RES = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/protocol_e/results")
OUT = Path(__file__).parent / "results"


def main():
    AD.RES, AD.OUT = RES, OUT
    AD.main()
    (OUT / "d_analysis.json").rename(OUT / "e_analysis.json")
    rows = [json.loads(p.read_text()) for p in sorted(RES.glob("*.json"))]
    extra = {"meter_recall": float(np.mean([r["conds"][c]["meter_recall"] for r in rows for c in r["conds"]])),
             "strata": {}}
    b = lambda r, c, m: r["conds"][c]["methods"][m]["benign_served"] / max(1, r["conds"][c]["methods"][m]["benign_total"])
    for c in ("2", "3"):
        for name, sel in (("Wp=3", lambda r: len(r["Wp"]) == 3), ("Wp>=4", lambda r: len(r["Wp"]) >= 4)):
            rs = [r for r in rows if sel(r)]
            if not rs:
                continue
            extra["strata"][f"c{c}:{name}"] = {"n": len(rs), **{m: {"leak": float(np.mean([r["conds"][c]["methods"][m]["leak"] for r in rs])),
                                                               "benign": float(np.mean([b(r, c, m) for r in rs]))}
                                                           for m in rows[0]["conds"][c]["methods"]}}
    (OUT / "e_extra.json").write_text(json.dumps(extra, indent=1) + "\n")
    print("meter recall", extra["meter_recall"])


if __name__ == "__main__":
    main()
