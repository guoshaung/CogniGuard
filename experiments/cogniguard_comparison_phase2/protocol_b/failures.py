"""Failure cases for Protocol B: CogniGuard runs where the sensitive inference succeeded (leak) or the
benign task failed (over-refusal), with the gate trace and the last log lines. Negative results kept.

  python -m experiments.cogniguard_comparison_phase2.protocol_b.failures --runs <full dir> --out <dir>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

OFFICIAL = Path("/Users/MBP/Exp/CogniGuard/cogniguard_raw/sumleaks_repo/data")
WIT = {w["target_id"]: w["sets"] for w in map(json.loads, Path(
    "/Users/MBP/Exp/CogniGuard/cogniguard_data/sumleaks/witness_sets.jsonl").read_text().splitlines())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    cases = []
    for goal in ("sensitive", "benign"):
        f = a.runs / f"cogniguard-{goal}" / "results.jsonl"
        for line in f.read_text().splitlines():
            r = json.loads(line)
            bad = (goal == "sensitive" and r["final_inference_performed"]) or \
                  (goal == "benign" and r["final_inference_performed"] is False) or r["final_inference_performed"] is None
            if not bad:
                continue
            log = (a.runs / f"cogniguard-{goal}" / r["log"]).read_text() if r.get("log") else ""
            g = r.get("gate") or {}
            kind = ("judge_error" if r["final_inference_performed"] is None else
                    "leak" if goal == "sensitive" else "benign_failure")
            if kind == "leak":
                # SCORING-SIDE diagnosis only: the official sensitive plan is test truth and was never
                # given to the gate; it is read here, after all decisions, to explain the failure.
                cfg = json.loads((OFFICIAL / f"experiment_{r['scenario']}_def_adv_both.json").read_text())
                plan = json.dumps(cfg["run_2_sensitive_plan"]) + json.dumps(cfg["run_2_sensitive"])
                tables = {f"{x}.{t}" for x, sp in cfg["data_distribution"].items() for t in sp.get("table", {})}
                used = {u for u in tables if u.split(".", 1)[1] in plan}
                sets = WIT.get(f"sl.{r['scenario']}") if g.get("source") == "e7_computed" else None
                if g.get("source") == "defense_line":
                    m = __import__("re").search(r"combination of (.+?) is sensitive", cfg.get("defense", ""), 2)
                    names = [x.strip() for x in __import__("re").split(r",|\band\b", m.group(1))] if m else []
                    sets = [[u for u in tables if u.split(".", 1)[1] in names]]
                if not g.get("source"):
                    cause = "no witness for scenario"
                elif g.get("blocked", 0):
                    cause = "leak despite a block (other path or partial answer)"
                elif sets and not any(set(w) <= used for w in sets):
                    cause = ("witness coarser than the attack (defense-line combination not all needed)"
                             if g.get("source") == "defense_line" else
                             "witness differs from the attacked inference (E7 secret is not the attack target)")
                else:
                    cause = "meter missed a disclosed table"
            elif kind == "benign_failure":
                cause = "gate blocked a benign answer" if g.get("blocked", 0) else "task failed without any gate block"
            else:
                cause = r.get("error")
            cases.append({"scenario": r["scenario"], "goal": goal, "kind": kind, "cause": cause,
                          "witness_source": g.get("source"), "gate_blocked": g.get("blocked"),
                          "metered": g.get("metered"), "log_tail": log[-1500:]})
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "protocol_b_failure_cases.json").write_text(json.dumps(cases, indent=1, ensure_ascii=False) + "\n")
    from collections import Counter
    print(json.dumps(Counter((c["kind"], c["cause"]) for c in cases).most_common(), ensure_ascii=False))


if __name__ == "__main__":
    main()
