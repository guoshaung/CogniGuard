"""Protocol B: native Sum Leaks defenses (official code, github.com/Vaidehi99/MultiAgentPrivacy @ 6e7af5d)
versus a CogniGuard gate, in the SAME multi-agent loop, with ONE backbone model for every role.

The official scripts are imported by path and NOT edited. Only their two model-call functions
(`qwen_chat_completion`, `gemini_chat_completion`) are rebound to one OpenAI-compatible backend
(glm-5.2 on the Bailian token plan, thinking off, temperature 0). The official judge prompt
(`eval_leakage_exec.evaluate_final_inference`) scores every run.

Methods:
  cot        qwen_gemini_map_cot.py                       (no defense)
  cotlh      qwen_gemini_map_cot_sensitive_set_hist.py    (CoT + sensitive set L + query history H_t)
  tom        qwen_gemini_map_tom.py
  codef      qwen_gemini_map_codef.py
  cogniguard qwen_gemini_map_cot.py + CogniGuard release gate on every answer returned to Alice:
             deterministic table meter -> units (Agent.table) -> check_release(k=1) against the
             E7 witness sets of that scenario; Alice's own tables are held from the start; allowed
             answers become receipts. No LLM inside the gate.

  python -m experiments.cogniguard_comparison_phase2.protocol_b.run_native --method codef --ids 100,101 \
      --goal sensitive --out <dir>
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import threading
import time
import types
from pathlib import Path

import requests

ROOT = Path("/Users/MBP/Exp/CogniGuard")
OFFICIAL = ROOT / "cogniguard_raw" / "sumleaks_repo"
SCRIPTS = {"cot": "qwen_gemini_map_cot.py", "cotlh": "qwen_gemini_map_cot_sensitive_set_hist.py",
           "tom": "qwen_gemini_map_tom.py", "codef": "qwen_gemini_map_codef.py",
           "cogniguard": "qwen_gemini_map_cot.py"}
MODEL = "glm-5.2"
URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions"
USAGE = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "errors": 0}
_lock = threading.Lock()


def _key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("BAILIAN_TOKEN_PLAN_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("token plan key missing")


KEY = None


def chat(model, messages, temperature=0, **_):
    global KEY
    KEY = KEY or _key()
    body = {"model": MODEL, "messages": messages, "temperature": 0, "enable_thinking": False}
    for attempt in range(6):
        try:
            r = requests.post(URL, json=body, headers={"Authorization": f"Bearer {KEY}"}, timeout=180)
            if r.status_code == 200:
                d = r.json()
                u = d.get("usage", {})
                with _lock:
                    USAGE["calls"] += 1
                    USAGE["prompt_tokens"] += u.get("prompt_tokens", 0)
                    USAGE["completion_tokens"] += u.get("completion_tokens", 0)
                return d["choices"][0]["message"]["content"] or ""
            if r.status_code in (400, 401, 403):
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except requests.RequestException:
            pass
        time.sleep(2 ** attempt)
    with _lock:
        USAGE["errors"] += 1
    raise RuntimeError("backend unavailable")


def _fake_google():
    google = types.ModuleType("google")
    genai = types.ModuleType("google.genai")
    genai.Client = lambda *a, **k: None
    google.genai = genai
    sys.modules.setdefault("google", google)
    sys.modules["google.genai"] = genai
    sys.modules.setdefault("openai", types.ModuleType("openai"))  # imported but unused by the official scripts


def load_official(name: str, file: str):
    _fake_google()
    spec = importlib.util.spec_from_file_location(name, OFFICIAL / "scripts" / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.qwen_chat_completion = chat
    mod.gemini_chat_completion = lambda model, messages, temperature=0: chat(model, messages)
    return mod


# ------------------------------------------------------------------ CogniGuard gate

def table_meter(cfg):
    """unit 'Agent.table' -> distinctive cell values (strings, len >= 3) found in no other table."""
    vals = {}
    for agent, spec in cfg["data_distribution"].items():
        for table, t in spec.get("table", {}).items():
            vals[f"{agent}.{table}"] = {str(v).strip().lower() for row in t["rows"] for v in row.values()
                                       if len(str(v).strip()) >= 3}
    unique = {}
    for u, vs in vals.items():
        others = set().union(*(w for x, w in vals.items() if x != u))
        unique[u] = vs - others
    return unique


def install_gate(mod, cfg, scenario_id, log):
    from cogniguard.governance.reconstruction import check_release
    from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
    wit = [json.loads(l) for l in (ROOT / "cogniguard_data/sumleaks/witness_sets.jsonl").read_text().splitlines()]
    sets = next((w["sets"] for w in wit if w["target_id"] == f"sl.{scenario_id}"), None)
    meter = table_meter(cfg)
    source = "e7_computed" if sets else None
    if not sets:
        # Fallback: the paper's own sensitive set L (the same 'defense' line every LLM defense receives):
        # "A combination of t1, t2, ... is sensitive" -> one witness = all named tables.
        m = re.search(r"combination of (.+?) is sensitive", cfg.get("defense", ""), re.I)
        names = [x.strip() for x in re.split(r",|\band\b", m.group(1)) if x.strip()] if m else []
        units = [u for u in meter if u.split(".", 1)[1] in names]
        if len(units) >= 2:
            sets, source = [units], "defense_line"
    gate = {"targets": None, "held": set(), "blocked": 0, "allowed": 0, "metered": [], "source": source}
    if sets:
        gate["targets"] = TargetRegistry([ProtectedTarget(f"sl.{scenario_id}", "owner", "org",
                                                          tuple(frozenset(("sl", u) for u in s) for s in sets))])
    gate["held"] = {("sl", u) for u in meter if u.startswith("Alice.")}
    original = mod.Agent.receive_query

    def receive_query(self, from_agent, query):
        answer = original(self, from_agent, query)
        if from_agent.name != "Alice" or not isinstance(answer, str):
            return answer
        text = answer.lower()
        units = {("sl", u) for u, vs in meter.items() if any(v in text for v in vs)}
        gate["metered"].append(sorted(u for _, u in units))
        if gate["targets"] is not None and units:
            safe = check_release(gate["targets"], "Alice", units, {"Alice": frozenset(gate["held"])}, 1).safe
            if not safe:
                gate["blocked"] += 1
                log(f"[CogniGuard gate] blocked answer from {self.name}: units {sorted(u for _, u in units)}")
                return "Sorry, I can't share that information."
        gate["held"] |= units
        gate["allowed"] += 1
        return answer

    mod.Agent.receive_query = receive_query
    return gate


# ------------------------------------------------------------------ one run

def run_one(method, sid, goal, out: Path):
    cfg_src = OFFICIAL / "data" / f"experiment_{sid}_def_adv_both.json"
    work = out / method / goal
    work.mkdir(parents=True, exist_ok=True)
    cfg_path = work / cfg_src.name
    shutil.copy(cfg_src, cfg_path)
    cfg = json.loads(cfg_path.read_text())
    mod = load_official(f"sl_{method}_{sid}_{goal}", SCRIPTS[method])
    gate = install_gate(mod, cfg, sid, lambda m: mod.log(m)) if method == "cogniguard" else None
    before = dict(USAGE)
    t0 = time.time()
    err = None
    try:
        mod.run_adversarial_inference(str(cfg_path), goal)
    except Exception as e:  # the official loop raises on malformed model JSON; record and judge the log
        err = f"{type(e).__name__}: {e}"[:300]
    logs = sorted(work.glob(f"{cfg_path.stem}_{goal}*log.txt"), key=os.path.getmtime)
    trajectory = logs[-1].read_text() if logs else ""
    ev = load_official(f"sl_eval_{method}_{sid}_{goal}", "eval_leakage_exec.py")
    key = "run_2_sensitive" if goal == "sensitive" else "run_1_benign"
    try:
        performed = ev.evaluate_final_inference(cfg[f"{key}_plan"], trajectory, cfg[key]["final_inference_result"])
    except Exception as e:
        performed, err = None, (err or "") + f" | judge: {e}"[:200]
    return {"method": method, "scenario": sid, "goal": goal, "final_inference_performed": performed,
            "error": err, "seconds": round(time.time() - t0, 1),
            "calls": USAGE["calls"] - before["calls"],
            "prompt_tokens": USAGE["prompt_tokens"] - before["prompt_tokens"],
            "completion_tokens": USAGE["completion_tokens"] - before["completion_tokens"],
            "gate": None if gate is None else {k: gate[k] for k in ("blocked", "allowed", "metered", "source")} |
            {"has_witness": gate["targets"] is not None},
            "log": str(logs[-1].relative_to(out)) if logs else None, "model": MODEL}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True, choices=sorted(SCRIPTS))
    ap.add_argument("--ids", required=True)
    ap.add_argument("--goal", required=True, choices=("sensitive", "benign"))
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    with open(a.out / "results.jsonl", "a") as h:
        for sid in [int(x) for x in a.ids.split(",")]:
            r = run_one(a.method, sid, a.goal, a.out)
            h.write(json.dumps(r) + "\n")
            h.flush()
            print(json.dumps({k: r[k] for k in ("method", "scenario", "goal", "final_inference_performed",
                                                 "calls", "error")}))


if __name__ == "__main__":
    main()
