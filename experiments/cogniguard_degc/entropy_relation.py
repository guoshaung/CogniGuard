"""How the two entropies relate to actual dangerous releases (Stage B data, no gating: every answer of the
ungated CoT stream is released in order). For each answer: R (posterior reconstruction probability after
the release, cross-fitted calibrator), leakage bits L(R), state entropy h(R), and the reference outcome
Z_ref = the reference state (Alice + reference units of all answers so far) covers the witness for the
first time at this answer. Reports reliability of R, and the decision error of the chance-constraint rule
per state-entropy bin."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from cogniguard.governance.degc import KnowledgeBelief, Obs, brier, ece, h2, leakage_entropy, reconstruction_risk
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from experiments.cogniguard_comparison_phase2.protocol_b2.diagnose import target_sets
from experiments.cogniguard_degc.stage_b import binner, build, crossfit, folds

OUT = Path(__file__).parent / "results" / "entropy_relation.json"


def main():
    data = build()
    answers, gold, det, runs, by_run, cfgs, key, pairs = data
    cal = crossfit(pairs, folds({k[0] for k in pairs}), binner)
    recs = []
    for (sid, goal), performed in sorted(runs.items()):
        if performed is None:
            continue
        cfg = cfgs[sid]
        sets = target_sets(cfg, sid, "policy")
        if not sets:
            continue
        reg = TargetRegistry([ProtectedTarget("t", "o", "org", tuple(frozenset(("sl", u) for u in s) for s in sets))])
        alice = {f"Alice.{t}" for t in cfg["data_distribution"].get("Alice", {}).get("table", {})}
        b = KnowledgeBelief()
        b.add_trusted("Alice", {("sl", u) for u in alice})
        ref = set(alice)
        done = any(set(w) <= ref for w in sets)
        tables = sorted({k[3] for k in pairs if k[0] == sid and k[1] == goal})
        for a in by_run.get((sid, goal), []):
            k = key(a)
            pend = [Obs(f"{k}|{u}", "Alice", ("sl", u), *cal[(*k, u)], {}) for u in tables if reg.targets_for_unit(("sl", u))]
            R0 = reconstruction_risk(reg, b, "Alice", 1)
            R = reconstruction_risk(reg, b, "Alice", 1, pend)
            ref |= gold[k]
            z = (not done) and any(set(w) <= ref for w in sets)
            done = done or z
            recs.append({"R": R, "dR": R - R0, "h": h2(R), "L": leakage_entropy(R), "z": int(z), "goal": goal})
            for o in pend:
                b.add_obs(o)
    ps, ys = [r["dR"] for r in recs], [r["z"] for r in recs]
    rel = defaultdict(lambda: [0, 0])
    for r in recs:
        bkt = min(9, int(r["dR"] * 10)) if r["dR"] > 0 else -1
        rel[bkt][0] += 1
        rel[bkt][1] += r["z"]
    herr = defaultdict(lambda: [0, 0])
    for r in recs:
        bkt = round(min(0.99, r["h"]) // 0.2 * 0.2, 1)
        herr[bkt][0] += 1
        herr[bkt][1] += int((r["dR"] > 0.05) != bool(r["z"]))
    out = {"n_answers": len(recs), "n_new_reconstructions": sum(ys),
           "dR_as_predictor": {"brier": brier(ps, ys), "ece": ece(ps, ys)},
           "reliability_dR_bins": {str(k): {"n": v[0], "observed_rate": v[1] / v[0]} for k, v in sorted(rel.items())},
           "decision_error_by_state_entropy_bin(delta=0.05)": {str(k): {"n": v[0], "error_rate": v[1] / v[0]} for k, v in sorted(herr.items())},
           "note": "leakage bits L are a monotone transform of R, so their relation to Z is that of R"}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
