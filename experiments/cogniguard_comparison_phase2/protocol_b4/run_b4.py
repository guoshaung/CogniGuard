"""Protocol B4 runner. Official Sum Leaks scripts via protocol_b.run_native (imported, not edited); the regex fix
is applied to every method. Scenarios: --set old (official data/, 119) or --set new (locked new scenarios).

  python -m experiments.cogniguard_comparison_phase2.protocol_b4.run_b4 --method cg_llm --set new --goal sensitive \
      --ids 0,1 --out <dir>
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path

from experiments.cogniguard_comparison_phase2.protocol_b import run_native as RN
from experiments.cogniguard_comparison_phase2.protocol_b4 import gates

OFFICIAL_METHODS = {"cot": "qwen_gemini_map_cot.py", "cotlh": "qwen_gemini_map_cot_sensitive_set_hist.py",
                    "tom": "qwen_gemini_map_tom.py", "codef": "qwen_gemini_map_codef.py"}
GATED = ("cg_llm", "cg_b2", "ocelot_r", "pflow_r")
NEW = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/protocol_b4/locked")
HERE = Path(__file__).parent
_SEM = None


def scenario_path(kind, sid):
    if kind == "old":
        return RN.OFFICIAL / "data" / f"experiment_{sid}_def_adv_both.json"
    return NEW / f"experiment_{sid}_def_adv_both.json"


def run_one(method, kind, sid, goal, out: Path):
    global _SEM
    RN.FIX_REGEX = True
    src = scenario_path(kind, sid)
    work = out / method / goal
    work.mkdir(parents=True, exist_ok=True)
    cfg_path = work / src.name
    shutil.copy(src, cfg_path)
    cfg = json.loads(cfg_path.read_text())
    script = OFFICIAL_METHODS.get(method, "qwen_gemini_map_cot.py")
    mod = RN.load_official(f"b4_{method}_{kind}_{sid}_{goal}", script)
    st = None
    if method in GATED:
        B = None
        if method == "ocelot_r":
            B = json.loads((HERE / "results/b4_dev_choices.json").read_text())["ocelot_B"]
        if method == "cg_b2" and _SEM is None:
            from experiments.cogniguard_comparison_phase2.protocol_b2.diagnose import Semantic
            _SEM = Semantic()
        st = gates.install(mod, cfg, method, RN.chat, lambda m: mod.log(m), B=B, semantic=_SEM)
    before = dict(RN.USAGE)
    t0 = time.time()
    err = None
    try:
        mod.run_adversarial_inference(str(cfg_path), goal)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"[:300]
    logs = sorted(work.glob(f"{cfg_path.stem}_{goal}*log.txt"), key=os.path.getmtime)
    trajectory = logs[-1].read_text() if logs else ""
    ev = RN.load_official(f"b4_eval_{method}_{kind}_{sid}_{goal}", "eval_leakage_exec.py")
    key = "run_2_sensitive" if goal == "sensitive" else "run_1_benign"
    try:
        performed = ev.evaluate_final_inference(cfg[f"{key}_plan"], trajectory, cfg[key]["final_inference_result"])
    except Exception as e:
        performed, err = None, (err or "") + f" | judge: {e}"[:200]
    return {"method": method, "set": kind, "scenario": sid, "goal": goal, "final_inference_performed": performed,
            "error": err, "seconds": round(time.time() - t0, 1), "calls": RN.USAGE["calls"] - before["calls"],
            "prompt_tokens": RN.USAGE["prompt_tokens"] - before["prompt_tokens"],
            "completion_tokens": RN.USAGE["completion_tokens"] - before["completion_tokens"],
            "gate": st, "log": str(logs[-1].relative_to(out)) if logs else None, "model": RN.MODEL}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True, choices=sorted(OFFICIAL_METHODS) + list(GATED))
    ap.add_argument("--set", required=True, choices=("old", "new"))
    ap.add_argument("--ids", required=True)
    ap.add_argument("--goal", required=True, choices=("sensitive", "benign"))
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    with open(a.out / "results.jsonl", "a") as h:
        for sid in a.ids.split(","):
            r = run_one(a.method, a.set, sid, a.goal, a.out)
            h.write(json.dumps(r, default=str) + "\n")
            h.flush()
            print(json.dumps({k: r[k] for k in ("method", "scenario", "goal", "final_inference_performed", "calls", "error")}))


if __name__ == "__main__":
    main()
