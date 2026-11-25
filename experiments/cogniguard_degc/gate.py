"""DEGC in the real CogniGuard execution path (Sum Leaks multi-agent loop, Protocol B harness).

The frozen Protocol-B harness (`protocol_b/run_native.py`) is imported unchanged; only its gate factory is
swapped for `install_degc_gate` at run time. Each answer to Alice is processed live:
  detectors   normalized value matching + frozen BGE+NLI (protocol_b2/diagnose.py), same thresholds
  evidence    per (answer, table) observation -> frozen calibrated posterior (calibration_frozen.json,
              fitted on the exposed 576-answer development data; never refitted on new scenarios)
  state       KnowledgeBelief: Alice's own tables are trusted events; every observation stays uncertain
  decision    DegcPolicy (CA-PD kernel unchanged) with the live glm-5.2 verifier (verifier_llm prompt),
              calibrated by the frozen verifier bins; a blocked answer is replaced by a refusal
No attack plan, goal, final_inference_result or evaluation label is read by the gate.

  python -m experiments.cogniguard_degc.gate --ids 5 --goal sensitive --out <dir> [--delta 0.05 --cap 1]
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from cogniguard.governance.degc import BetaCalibrator, DegcConfig, DegcPolicy, KnowledgeBelief, Obs
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from experiments.cogniguard_comparison_phase2.protocol_b import run_native as rn
from experiments.cogniguard_comparison_phase2.protocol_b2.diagnose import BGE_MAX, detect_norm, norm_values, target_sets
from experiments.cogniguard_degc.stage_b import binner, ver_binner
from experiments.cogniguard_degc.verifier_llm import PROMPT

FROZEN = Path(__file__).with_name("calibration_frozen.json")
LAST: list = []


def freeze_calibration():
    """Fit on ALL exposed development pairs and write the frozen counts (run once, before any new run)."""
    from experiments.cogniguard_degc.stage_b import build
    pairs = build()[-1]
    det = BetaCalibrator(binner).fit((v, v["gold"]) for v in pairs.values())
    ver = BetaCalibrator(ver_binner).fit((v, v["gold"]) for v in pairs.values() if v["ver"] is not None)
    FROZEN.write_text(json.dumps({"detector": {json.dumps(k): v for k, v in det.counts.items()},
                                  "verifier": {json.dumps(k): v for k, v in ver.counts.items()},
                                  "source": "protocol_b2 exposed development data (576 answers, 4592 pairs)"}, indent=1) + "\n")


def load_calibration():
    d = json.loads(FROZEN.read_text())
    def mk(fn, counts):
        c = BetaCalibrator(fn)
        c.counts = {tuple(json.loads(k)): tuple(v) for k, v in counts.items()}
        return c
    return mk(binner, d["detector"]), mk(ver_binner, d["verifier"])


def features(sem, text, cfg, uniq):
    tables = {f"{a}.{t}": b["rows"] for a, s in cfg["data_distribution"].items() for t, b in s.get("table", {}).items()}
    names = sorted(tables)
    norm = detect_norm(text, uniq)
    semhit = sem.detect(text, cfg)
    docs = [f"{n}: " + " ".join(sem.verbalize_row(n, r) for r in tables[n]) for n in names]
    e = sem.bge.encode([text] + docs, normalize_embeddings=True)
    sims = e[1:] @ e[0]
    top = {names[i] for i in sims.argsort()[::-1][:BGE_MAX]}
    wins = sem.windows(text)
    out = {}
    for i, n in enumerate(names):
        nli = max(sem.entail(wins, sem.verbalize_row(n, r)) for r in tables[n]) if n in top else None
        out[n] = {"norm": n in norm, "sem": n in semhit, "nli": nli, "cos": float(sims[i]), "bridge": not uniq[n]}
    return out


def install_degc_gate_factory(sem, delta, cap, budget):
    det_cal, ver_cal = load_calibration()

    def install(mod, cfg, sid, log):
        sets = target_sets(cfg, sid, "policy")
        uniq = norm_values(cfg)
        gate = {"targets": None, "blocked": 0, "allowed": 0, "metered": [], "source": "owner_policy" if sets else None,
                "verifier_calls": 0, "decisions": []}
        LAST.append(gate)
        if not sets:
            return gate
        reg = TargetRegistry([ProtectedTarget(f"sl.{sid}", "owner", "org", tuple(frozenset(("sl", u) for u in s) for s in sets))])
        gate["targets"] = reg
        belief = KnowledgeBelief()
        belief.add_trusted("Alice", {("sl", u) for u in uniq if u.startswith("Alice.")})
        tables = {f"{a}.{t}": b["rows"] for a, s in cfg["data_distribution"].items() for t, b in s.get("table", {}).items()}

        def verify(o):
            f = o.feats
            out = rn.chat("glm-5.2", [{"role": "user", "content": PROMPT.format(
                table=f["table"], rows=json.dumps(tables[f["table"]], ensure_ascii=False), answer=f["text"])}])
            m = re.search(r'"disclosed"\s*:\s*(true|false)', out or "", re.I)
            gate["verifier_calls"] += 1
            if not m:
                return o.p, o.lo, o.hi
            return ver_cal.posterior({**f, "ver": m.group(1).lower() == "true"})

        pol = DegcPolicy(reg, DegcConfig(delta=delta, per_request_cap=cap, budget=budget, k=1), verify=verify)
        original = mod.Agent.receive_query
        n = {"i": 0}

        def receive_query(self, from_agent, query):
            answer = original(self, from_agent, query)
            if from_agent.name != "Alice" or not isinstance(answer, str):
                return answer
            t0 = time.time()
            feats = features(sem, answer, cfg, uniq)
            i = n["i"]
            n["i"] += 1
            pend = []
            for u, f in feats.items():
                p, lo, hi = det_cal.posterior(f)
                pend.append(Obs(f"{i}|{u}", "Alice", ("sl", u), p, lo, hi, {**f, "table": u, "text": answer}))
            gate["metered"].append(sorted(u for u, f in feats.items() if f["norm"] or f["sem"]))
            d = pol.decide("Alice", belief, [o for o in pend if reg.targets_for_unit(o.unit)])
            gate["decisions"].append({"i": i, "allowed": d.allowed, "R": round(d.R, 4), "R_before": round(d.R_before, 4),
                                      "verified": len(d.verified), "reason": d.reason, "seconds": round(time.time() - t0, 3)})
            if not d.allowed:
                gate["blocked"] += 1
                log(f"[DEGC gate] blocked answer from {self.name}: R={d.R:.3f} (before {d.R_before:.3f})")
                return "Sorry, I can't share that information."
            for o in pend:
                belief.add_obs(o)
            gate["allowed"] += 1
            return answer

        mod.Agent.receive_query = receive_query
        return gate

    return install


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="5")
    ap.add_argument("--goal", default="sensitive", choices=("sensitive", "benign"))
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--delta", type=float, default=0.05)
    ap.add_argument("--cap", type=int, default=1)
    ap.add_argument("--budget", type=float, default=float("inf"))
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args()
    if a.freeze or not FROZEN.exists():
        freeze_calibration()
    from experiments.cogniguard_comparison_phase2.protocol_b2.diagnose import Semantic
    sem = Semantic()
    rn.FIX_REGEX = True
    rn.install_gate = install_degc_gate_factory(sem, a.delta, a.cap, a.budget)
    a.out.mkdir(parents=True, exist_ok=True)
    for sid in [int(x) for x in a.ids.split(",")]:
        r = rn.run_one("cogniguard", sid, a.goal, a.out)
        g = LAST[-1] if LAST else {}
        r["gate"] = {k: v for k, v in g.items() if k != "targets"} | {"has_witness": g.get("targets") is not None}
        r["degc"] = {"delta": a.delta, "cap": a.cap, "budget": a.budget}
        with open(a.out / "results_degc.jsonl", "a") as h:
            h.write(json.dumps(r, default=str) + "\n")
        print(json.dumps({k: r[k] for k in ("scenario", "goal", "final_inference_performed", "calls", "error")}), flush=True)


if __name__ == "__main__":
    main()
