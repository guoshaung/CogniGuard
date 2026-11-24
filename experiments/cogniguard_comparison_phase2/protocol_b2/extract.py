"""Protocol B2 step 1: answers returned to Alice, from the frozen Protocol B logs (b26de9f).

Base trajectories are the UNGATED CoT runs (cot-sensitive, cot-benign): the same backbone and tasks,
so any gate variant can be replayed offline on the same answer stream. Every record is the text an
agent returned to Alice for one plan step, in order.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

FULL = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/protocol_b/full")
DATA = Path("/Users/MBP/Exp/CogniGuard/cogniguard_raw/sumleaks_repo/data")
STEP = re.compile(r"\[Alice\] Step (\d+): Ask '([^']+)' about '(.*)'$")
RECV = re.compile(r"\[(\w+)\] Received query from Alice: (.*)$")
DEC = re.compile(r"\[(\w+)\] Backend decision: (.*)$")


def answers_from_log(text: str):
    out, cur = [], None
    for line in text.splitlines():
        line = re.sub(r"^\[\d{4}-\d\d-\d\d [\d:]+\] ", "", line)
        m = STEP.search(line)
        if m:
            if cur and cur.get("responder"):
                out.append(cur)
            cur = {"step": int(m.group(1)), "target": m.group(2), "query": m.group(3), "responder": None,
                   "answer": None}
            continue
        if cur is None:
            continue
        m = RECV.search(line)
        if m and cur["responder"] is None:
            cur["responder"] = m.group(1)
            continue
        m = DEC.search(line)
        if m and cur["responder"] == m.group(1):
            raw = m.group(2)
            r = re.search(r'"response"\s*:\s*"(.*)"\s*\}?\s*$', raw, re.S)
            if '"respond"' in raw and r:
                cur["answer"] = r.group(1)
    if cur and cur.get("responder"):
        out.append(cur)
    return out


def main():
    recs = []
    for goal in ("sensitive", "benign"):
        res = {json.loads(l)["scenario"]: json.loads(l) for l in (FULL / f"cot-{goal}" / "results.jsonl").read_text().splitlines()}
        for sid, r in sorted(res.items()):
            log = (FULL / f"cot-{goal}" / r["log"]).read_text() if r.get("log") else ""
            for i, a in enumerate(answers_from_log(log)):
                if a["answer"]:
                    recs.append({"scenario": sid, "goal": goal, "idx": i, **a,
                                 "run_inference_performed": r["final_inference_performed"]})
    out = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/protocol_b2")
    out.mkdir(parents=True, exist_ok=True)
    (out / "answers.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    print(len(recs), "answers;", len({(r["scenario"], r["goal"]) for r in recs}), "runs")


if __name__ == "__main__":
    main()
