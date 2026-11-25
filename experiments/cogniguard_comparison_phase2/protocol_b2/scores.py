"""B2 follow-up: per-(answer, table) confidence scores of the FROZEN semantic interface, used only to rank
pairs for the verification-budget diagnostic (low-confidence-first). Thresholds are not changed and no
decision of the frozen detectors is altered. BGE cosine for every table; max-window NLI entailment for the
top-3 tables by cosine (the same retrieval width as the frozen interface, without the cosine threshold).
"""

from __future__ import annotations

import json
from pathlib import Path

from experiments.cogniguard_comparison_phase2.protocol_b2.diagnose import B2, DATA, Semantic, BGE_MAX


def main():
    sem = Semantic()
    answers = [json.loads(l) for l in (B2 / "answers.jsonl").read_text().splitlines()]
    out = open(B2 / "scores.jsonl", "w")
    for a in answers:
        cfg = json.loads((DATA / f"experiment_{a['scenario']}_def_adv_both.json").read_text())
        tables = {f"{x}.{t}": b["rows"] for x, s in cfg["data_distribution"].items() for t, b in s.get("table", {}).items()}
        names = sorted(tables)
        docs = [f"{n}: " + " ".join(sem.verbalize_row(n, r) for r in tables[n]) for n in names]
        e = sem.bge.encode([a["answer"]] + docs, normalize_embeddings=True)
        sims = e[1:] @ e[0]
        top = set(names[i] for i in sims.argsort()[::-1][:BGE_MAX])
        wins = sem.windows(a["answer"])
        rec = {}
        for i, n in enumerate(names):
            nli = max(sem.entail(wins, sem.verbalize_row(n, r)) for r in tables[n]) if n in top else None
            rec[n] = {"cos": float(sims[i]), "nli": nli}
        out.write(json.dumps({"scenario": a["scenario"], "goal": a["goal"], "idx": a["idx"], "scores": rec}) + "\n")
        out.flush()
    print("ok")


if __name__ == "__main__":
    main()
