"""Real-log check (Sum Leaks, Protocol B2 answer streams): runs where the CA-PD gate with the REFERENCE
knowledge state (DEGC "Oracle" arm: glm-5.2 reference labels, owner-policy target) did not block, yet the
official judge says the sensitive inference was performed. Trace each run: owner target, E7 computed
witnesses, Alice's own tables, every answer with its reference label (filtered and raw), and which target
units were never covered. Reads only existing logs; no new model calls."""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from experiments.cogniguard_comparison_phase2.protocol_b2.diagnose import target_sets

B2 = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/protocol_b2")
DEGC = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/degc")
DATA = Path("/Users/MBP/Exp/CogniGuard/cogniguard_raw/sumleaks_repo/data")
OUT = Path(__file__).parent


def main():
    st = json.loads((DEGC / "stage_b_llm_noisy_or.json").read_text())
    orc = [r for r in st["rows"] if r["arm"] == "Oracle"][0]["per_run"]
    bad = sorted(int(k.split("|")[0]) for k, v in orc.items()
                 if k.endswith("sensitive") and v["performed"] and not v["sub_block"])
    n_sens = sum(1 for k, v in orc.items() if k.endswith("sensitive") and v["performed"])
    answers = [json.loads(l) for l in (B2 / "answers.jsonl").read_text().splitlines()]
    gold = {(g["scenario"], g["goal"], g["idx"]): g for g in map(json.loads, (B2 / "gold.jsonl").read_text().splitlines())}
    out = []
    for sid in bad:
        cfg = json.loads((DATA / f"experiment_{sid}_def_adv_both.json").read_text())
        names = sorted(f"{a}.{t}" for a, s in cfg["data_distribution"].items() for t in s.get("table", {}))
        alice = sorted(n for n in names if n.startswith("Alice."))
        pol = target_sets(cfg, sid, "policy")
        e7 = target_sets(cfg, sid, "e7")
        held, held_raw, trace = set(alice), set(alice), []
        for a in sorted((x for x in answers if x["scenario"] == sid and x["goal"] == "sensitive"), key=lambda x: x["idx"]):
            g = gold.get((sid, "sensitive", a["idx"]), {})
            m = re.search(r"\{.*\}", g.get("raw", ""), re.S)
            try:
                raw = json.loads(m.group(0))["revealed"] if m else []
            except Exception:
                raw = []
            fixed = [x if x in names else (difflib.get_close_matches(x, names, 1, 0.75) or [None])[0] for x in raw]
            held |= set(g.get("gold") or [])
            held_raw |= {x for x in fixed if x}
            trace.append({"idx": a["idx"], "query": a["query"], "answer": a["answer"][:400],
                          "ref_label": g.get("gold"), "raw_label": raw,
                          "raw_label_name_repaired": fixed})
        tables = {f"{a}.{t}": body["rows"] for a, s in cfg["data_distribution"].items() for t, body in s.get("table", {}).items()}
        out.append({"scenario": sid, "defense": cfg.get("defense", "")[:600],
                    "owner_policy_target": pol, "e7_witnesses": e7, "alice_tables": alice,
                    "answers": trace,
                    "covered_by_ref_labels": [sorted(set(w) - held) for w in (pol or [])],
                    "missing_after_name_repair": [sorted(set(w) - held_raw) for w in (pol or [])],
                    "e7_missing_ref": [sorted(set(w) - held) for w in (e7 or [])],
                    "tables": {k: v[:6] for k, v in tables.items()}})
    res = {"oracle_residual_runs": bad, "n_sensitive_runs_performed_any_arm_ref": n_sens, "runs": out}
    (OUT / "real_b2_residual.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    for r in out:
        print("== scenario", r["scenario"])
        print("  policy target:", r["owner_policy_target"], "| E7:", r["e7_witnesses"])
        print("  alice:", r["alice_tables"])
        print("  missing (ref labels):", r["covered_by_ref_labels"], "| after name repair:", r["missing_after_name_repair"],
              "| E7 missing:", r["e7_missing_ref"])
        for t in r["answers"]:
            print(f"   [{t['idx']}] ref={t['ref_label']} raw={t['raw_label']} :: {t['answer'][:160]}")


if __name__ == "__main__":
    main()
