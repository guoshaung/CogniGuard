"""k = 1 controlled-simulation Pareto (zero verification): deterministic calibrated threshold (OCL tau),
probabilistic state (B2 delta), history-only probabilistic state (B2h delta), B1. Test worlds 1000..1299."""
import json
import random
import statistics
from pathlib import Path

from experiments.cogniguard_degc import sim as S

OUT = Path(__file__).parent / "results" / "sim_pareto_k1.json"


def main():
    cal, vcal = S.fit(1)
    worlds = [S.world(1000 + s, 1) for s in range(300)]
    rows = []
    cfgs = [("B1", {})] + [("OCL", {"tau": t}) for t in (0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5)] + \
           [(a, {"delta": d}) for a in ("B2", "B2h") for d in (0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5)]
    for arm, c in cfgs:
        per = [S.play(W, arm, c, 1, cal, vcal, random.Random(0)) for W in worlds]
        r = {"arm": arm, "config": c, "leak": statistics.mean(x["leak"] for x in per),
             "over_refusal": statistics.mean(x["over_refusal"] for x in per),
             "per_world": [[int(x["leak"]), round(x["over_refusal"], 4)] for x in per]}
        rows.append(r)
        print(arm, c, round(r["leak"], 3), round(r["over_refusal"], 3), flush=True)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rows) + "\n")


if __name__ == "__main__":
    main()
