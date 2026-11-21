"""Read-only aggregation of this approved 120-call round; no model invocation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import statistics

from experiments.rag_real.retrieval import dump, sha

ROOT = Path(__file__).resolve().parents[2]
PARENTS = ("rag_expand_real_20261016_01", "cgc_communication_real_20261016_01",
           "rag_expand_real_20261016_02", "cgc_science_communication_20261016_01")


def bootstrap_interval(values):
    rng = random.Random(20261016)
    draws = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(2000))
    return {"low": draws[49], "high": draws[1949], "resamples": 2000,
            "note": "Exploratory paired bootstrap over selected unique questions, not a population safety guarantee."}


def run(results, output):
    loaded, source_hashes, calls = {}, {}, 0
    for name in PARENTS:
        parent = results / name
        summary_bytes = (parent / "summary.json").read_bytes()
        usage_bytes = (parent / "model-usage.jsonl").read_bytes()
        summary = json.loads(summary_bytes)
        records = [json.loads(line) for line in usage_bytes.splitlines() if line.strip()]
        if summary["real_api_calls"] != len(records) or any(r["status"] != "ok" for r in records):
            raise ValueError("missing or failed real calls; cannot aggregate as completed")
        calls += len(records)
        loaded[name] = summary
        source_hashes[name] = {"summary_sha256": sha(summary_bytes), "usage_sha256": sha(usage_bytes), "calls": len(records)}
    if calls > 120:
        raise ValueError("approved round budget exceeded")
    rag_names = (PARENTS[0], PARENTS[2])
    protocols = [json.loads((results / name / "protocol-lock.json").read_text(encoding="utf-8")) for name in rag_names]
    for key in ("model", "system_prompt_sha256", "source_code_sha256", "source_lock_sha256",
                "budget_per_source", "max_answer_tokens", "max_answer_chars", "arms"):
        if protocols[0][key] != protocols[1][key]:
            raise ValueError("RAG batches differ in frozen comparison configuration: " + key)
    if set(protocols[0]["case_ids"]) & set(protocols[1]["case_ids"]):
        raise ValueError("RAG question identities overlap")
    normal = {arm: [] for arm in protocols[0]["arms"]}
    for name, protocol in zip(rag_names, protocols):
        for index, qid in enumerate(protocol["case_ids"]):
            for arm in normal:
                record = json.loads((results / name / f"normal-{index:02d}-{arm}.json").read_text(encoding="utf-8"))
                if record["metrics"]["case_id"] != qid:
                    raise ValueError("per-question identity mismatch")
                normal[arm].append(record["metrics"])
    rag_summary = []
    for arm, rows in normal.items():
        per_batch = [next(m for m in loaded[name]["methods"] if m["arm"] == arm) for name in rag_names]
        attack_n = sum(m["attack_n"] for m in per_batch)
        rag_summary.append({"arm": arm, "normal_n": len(rows),
                            "correct_count": sum(r["normalized_answer_em"] for r in rows),
                            "answer_em": statistics.mean(r["normalized_answer_em"] for r in rows),
                            "answer_f1": statistics.mean(r["answer_token_f1"] for r in rows),
                            "normal_release_rate": statistics.mean(r["released"] for r in rows),
                            "attack_n": attack_n, "attack_rounds_per_case": 2,
                            "attack_source_5gram_coverage": sum(m["attack_source_5gram_coverage"] * m["attack_n"] for m in per_batch) / attack_n})
    raw, guarded = normal["Raw-RAG"], normal["FactRelease-C2RAG"]
    pairs = list(zip(raw, guarded))
    differences = {metric: [b[metric] - a[metric] for a, b in pairs]
                   for metric in ("normalized_answer_em", "answer_token_f1")}
    result = {"status": "COMPLETED_APPROVED_ROUND_AGGREGATION", "round_call_ceiling": 120,
              "real_api_calls": calls, "unused_calls": 120 - calls, "parent_artifacts": source_hashes,
              "rag": rag_summary,
              "rag_paired_improvement": {metric: {"mean": statistics.mean(values), "bootstrap_95": bootstrap_interval(values)}
                                          for metric, values in differences.items()},
              "cgc_numeric_mechanism": loaded[PARENTS[1]], "cgc_science_communication": loaded[PARENTS[3]],
              "limitations": ["RAG has twenty-two selected public questions and four targeted two-round requests, not a full official benchmark.",
                              "Do not pool numeric synthetic CGC tasks with science communication tasks.",
                              "Science communication has three unique paired QASC questions, not six independent samples."]}
    output.mkdir(parents=True, exist_ok=False)
    dump(output / "summary.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=ROOT / "experiments/results")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Like the underlying tools, pure aggregation is scheduled through a graph.
    from experiments.rag_real.graph import CONTROL_GRAPH, invoke_batch
    def steps():
        yield "prepare", 1
        result = run(args.results, args.output)
        yield "item"
        return result
    summary = invoke_batch(CONTROL_GRAPH, steps())
    print(json.dumps({"status": summary["status"], "real_api_calls": summary["real_api_calls"]}))
