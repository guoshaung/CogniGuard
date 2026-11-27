"""D4: the per-run records of the first process of every method (the sensitive goal on the old set) were lost
(results.jsonl replaced by an empty file); the full trajectory logs survived. Re-score each surviving log with
the SAME official judge call run_b4 uses (evaluate_final_inference, glm-5.2, temperature 0). Gate block counts
are recovered from the gate lines each gate writes into the trajectory log. Calls/tokens of these runs are lost
(None). Output written once, at the end, to runs/<set>/<method>/results_rejudged_<goal>.jsonl."""

from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from experiments.cogniguard_comparison_phase2.protocol_b import run_native as RN
from experiments.cogniguard_comparison_phase2.protocol_b4.run_b4 import scenario_path

RUNS = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/protocol_b4/runs")
GATE_LINE = re.compile(r"\[(cg_llm|cg_b2|ocelot_r|PrivacyFlow-R)\] blocked answer")


def one(args):
    kind, method, goal, log = args
    sid = re.match(r"experiment_(\w+?)_def_adv_both", log.name).group(1)
    cfg = json.loads(scenario_path(kind, sid).read_text())
    traj = log.read_text()
    ev = RN.load_official(f"rj_{method}_{kind}_{sid}_{goal}", "eval_leakage_exec.py")
    key = "run_2_sensitive" if goal == "sensitive" else "run_1_benign"
    err = None
    try:
        performed = ev.evaluate_final_inference(cfg[f"{key}_plan"], traj, cfg[key]["final_inference_result"])
    except Exception as e:
        performed, err = None, f"judge: {e}"[:200]
    return {"method": method, "set": kind, "scenario": sid, "goal": goal, "final_inference_performed": performed,
            "error": err, "seconds": None, "calls": None, "prompt_tokens": None, "completion_tokens": None,
            "gate": {"blocked_from_log": len(GATE_LINE.findall(traj))}, "log": str(log), "model": RN.MODEL,
            "rejudged": True}


def main(kind, goal):
    RN.FIX_REGEX = True
    jobs = []
    for mdir in sorted((RUNS / kind).iterdir()):
        if not mdir.is_dir():
            continue
        for log in sorted((mdir / mdir.name / goal).glob(f"*_{goal}*log.txt")):
            jobs.append((kind, mdir.name, goal, log))
    with ThreadPoolExecutor(8) as ex:
        rows = list(ex.map(one, jobs))
    by = {}
    for r in rows:
        by.setdefault(r["method"], []).append(r)
    for m, rs in by.items():
        (RUNS / kind / m / f"results_rejudged_{goal}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rs))
    print(len(rows), {m: len(v) for m, v in by.items()}, "usage", RN.USAGE)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
