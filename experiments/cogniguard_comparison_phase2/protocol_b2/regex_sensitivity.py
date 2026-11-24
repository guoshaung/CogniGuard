"""Regex-bug sensitivity (B2 item 7): replace every run that raised the official `(?R)` PatternError
with its rerun under the SAME parser fix (all methods), then recompute the frozen Protocol B metrics and
contrasts on the held-out 116 scenarios. The frozen b26de9f results stay unchanged; this is a sensitivity
table only.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from experiments.cogniguard_comparison_phase2.protocol_b.analyze_b import METHODS, boot_diff, load, per_scenario, verdict

FULL = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/protocol_b/full")
FIX = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/protocol_b/regexfix")
PILOT = {5, 40, 100}


def main():
    tmp = Path(tempfile.mkdtemp())
    replaced = 0
    for d in FULL.iterdir():
        if not (d / "results.jsonl").exists():
            continue
        fixed = {}
        if (FIX / d.name / "results.jsonl").exists():
            fixed = {json.loads(l)["scenario"]: l for l in (FIX / d.name / "results.jsonl").read_text().splitlines()}
        (tmp / d.name).mkdir()
        lines = []
        for l in (d / "results.jsonl").read_text().splitlines():
            r = json.loads(l)
            if r["error"] and "PatternError" in r["error"] and r["scenario"] in fixed:
                lines.append(fixed[r["scenario"]])
                replaced += 1
            else:
                lines.append(l)
        (tmp / d.name / "results.jsonl").write_text("\n".join(lines) + "\n")
    R = load(tmp)
    S = sorted({s for v in R.values() for s in v} - PILOT)
    per = {m: per_scenario(R, m, S) for m in METHODS}
    table = {}
    for m in METHODS:
        def rate(k):
            v = [per[m][s][k] for s in S if per[m][s][k] is not None]
            return sum(v) / len(v)
        table[m] = {"sensitive_blocked": rate("blocked"), "benign_succeeded": rate("benign_ok"), "overall": rate("overall")}
    contrasts = {f"cogniguard vs {b}": (lambda c: {"overall": c, "verdict": verdict(c)})(
        boot_diff(per["cogniguard"], per[b], "overall", S)) for b in ("codef", "tom", "cotlh", "cot")}
    remaining = sum(1 for v in R.values() for r in v.values() if r["error"] and "PatternError" in r["error"])
    out = {"replaced_runs": replaced, "remaining_pattern_errors": remaining, "heldout": len(S),
           "table": table, "contrasts": contrasts}
    Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/protocol_b2/regex_sensitivity.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
