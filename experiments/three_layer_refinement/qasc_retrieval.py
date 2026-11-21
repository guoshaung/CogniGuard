"""QASC retrieval on a curated global annotated-fact corpus.

NOT the official 17-million-sentence corpus, not generated QA accuracy. All
train/validation fact sentences form one global source collection; no query
is restricted to its own gold facts and answer labels never enter the query.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .qasc_data import ROOT, load, sha


def adapted_corpus(splits, limit=100):
    corpus = {}
    for split in ("train", "validation"):
        for row in splits[split]:
            for key in ("fact1", "fact2"):
                text = " ".join(row[key].split())
                did = sha(text.encode())[:24]
                if did in corpus and corpus[did] != ("", text):
                    raise ValueError("source sentence hash collision")
                corpus[did] = ("", text)
    selected = sorted(splits["validation"], key=lambda row: (sha(("20261016:" + row["id"]).encode()), row["id"]))[:limit]
    if len(selected) != limit:
        raise ValueError("insufficient QASC validation cases")
    queries = []
    for row in selected:
        gold = {sha(" ".join(row[key].split()).encode())[:24]: 1 for key in ("fact1", "fact2")}
        queries.append({"id": row["id"], "text": row["question"], "gold": gold,
                        "type": "grade_school_science", "supporting_titles": len(gold)})
    return corpus, queries


def steps(cache, output, cases):
    from cogniguard.workflows.model_site import enable_existing_model_environment
    enable_existing_model_environment()
    from experiments.rag_real.retrieval import evaluate_dataset, dump, code_hashes
    lock, splits = load(cache)
    corpus, queries = adapted_corpus(splits, cases)
    hashes = code_hashes()
    paths = (Path(__file__), ROOT / "experiments/three_layer_refinement/qasc_data.py")
    hashes.update({str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths})
    output.mkdir(parents=True, exist_ok=False)
    dump(output / "protocol-lock.json", {
        "protocol": "qasc_global_annotated_fact_retrieval_v1", "status": "FROZEN_BEFORE_RETRIEVAL",
        "source_revision": lock["revision"], "source_lock_sha256": sha((cache / "source-lock.json").read_bytes()),
        "corpus_sentences": len(corpus), "case_ids": [q["id"] for q in queries],
        "query_input": "question only; no answerKey, combinedfact, correct-choice filtering or per-query gold prefilter",
        "source_code_sha256": hashes, "real_api_calls": 0,
        "limitations": ["Curated corpus built from global annotated evidence, including validation source facts; not official 17M corpus performance.",
                        "Evidence annotations define source availability; this makes retrieval easier than open-corpus deployment.",
                        "Retrieval metrics do not measure answer correctness or copyright protection.",
                        "No model-generated QA answers in this run."],
    })
    yield "prepare", 1
    result = evaluate_dataset("QASC-curated-fact-corpus", corpus, queries, "cpu")
    dump(output / "per-query.json", result.pop("per_query"))
    yield "item"
    after = code_hashes()
    after.update({str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths})
    if hashes != after:
        raise ValueError("retrieval implementation changed during experiment")
    final = {"status": "COMPLETED_REAL_DATA_CURATED_RETRIEVAL", **result,
             "official_full_corpus_evaluation": False, "real_api_calls": 0, "model_generated_answers": False}
    dump(output / "summary.json", final)
    return final


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache/qasc-real-v1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=int, default=100)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.worker:
        env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONHASHSEED="20261016",
                   LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false", TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="2")
        raise SystemExit(subprocess.run([sys.executable, "-X", "utf8", "-m", __spec__.name,
                                        *sys.argv[1:], "--worker"], cwd=ROOT, env=env).returncode)
    from experiments.rag_real.graph import CONTROL_GRAPH, invoke_batch
    result = invoke_batch(CONTROL_GRAPH, steps(args.cache, args.output, args.cases))
    print(json.dumps({"status": result["status"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
