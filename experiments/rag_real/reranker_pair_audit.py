"""Read-only paired audit of frozen RRF vs CrossEncoder retrieval artifacts.

No corpus text, model call, API call, or query is loaded. This is a post-hoc
diagnostic on already inspected public test sets, not a new model benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics

from .prepare import ROOT


DATASETS = ("HotpotQA-distractor120", "BEIR-SciFact-test300")
METRICS = ("recall@10", "mrr@100", "ndcg@10", "hit@10", "all_evidence@10")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_rows(rows: list[dict]) -> dict:
    grouped: dict[str, dict[str, dict]] = {}
    for row in rows:
        qid = str(row["query_id"])
        method = str(row["method"])
        if method not in {"RRF", "RRF+CrossEncoder"}:
            continue
        bucket = grouped.setdefault(qid, {})
        if method in bucket:
            raise ValueError("duplicate query-method row")
        bucket[method] = row
    if not grouped or any(set(bucket) != {"RRF", "RRF+CrossEncoder"} for bucket in grouped.values()):
        raise ValueError("unpaired query rankings")
    pairs = []
    for qid, bucket in sorted(grouped.items()):
        base, reranked = bucket["RRF"], bucket["RRF+CrossEncoder"]
        if base["gold_document_count"] != reranked["gold_document_count"] or base["query_type"] != reranked["query_type"]:
            raise ValueError("query metadata differs between methods")
        if abs(float(base["recall@100"]) - float(reranked["recall@100"])) > 1e-9:
            raise ValueError("candidate-recall parity violated")
        pairs.append({
            "query_id": qid,
            "gold_document_count": int(base["gold_document_count"]),
            "query_type": str(base["query_type"]),
            "delta": {key: float(reranked[key]) - float(base[key]) for key in METRICS},
            "rrf_hit10": float(base["hit@10"]),
            "reranked_hit10": float(reranked["hit@10"]),
        })

    def summarize(subset: list[dict]) -> dict:
        if not subset:
            return {"queries": 0}
        return {
            "queries": len(subset),
            "metric_delta": {
                key: {
                    "mean": statistics.mean(item["delta"][key] for item in subset),
                    "improved": sum(item["delta"][key] > 1e-9 for item in subset),
                    "worsened": sum(item["delta"][key] < -1e-9 for item in subset),
                    "unchanged": sum(abs(item["delta"][key]) <= 1e-9 for item in subset),
                }
                for key in METRICS
            },
            "hit10_lost": sum(item["rrf_hit10"] == 1 and item["reranked_hit10"] == 0 for item in subset),
            "hit10_gained": sum(item["rrf_hit10"] == 0 and item["reranked_hit10"] == 1 for item in subset),
        }

    return {
        "all": summarize(pairs),
        "single_gold": summarize([item for item in pairs if item["gold_document_count"] == 1]),
        "multi_gold": summarize([item for item in pairs if item["gold_document_count"] > 1]),
        "by_query_type": {
            kind: summarize([item for item in pairs if item["query_type"] == kind])
            for kind in sorted({item["query_type"] for item in pairs})
        },
        "per_query_public_id_numeric_deltas": pairs,
    }


def run(retrieval_root: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError("fresh output directory required")
    lock_path = retrieval_root / "protocol-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("protocol") != "real_public_corpus_open_retrieval_v1":
        raise ValueError("frozen retrieval protocol mismatch")
    sources = {dataset: retrieval_root / f"{dataset}-per-query.json" for dataset in DATASETS}
    source_hashes = {dataset: sha(path) for dataset, path in sources.items()}
    code_hash = sha(Path(__file__))
    output.mkdir(parents=True, exist_ok=False)
    protocol = {
        "status": "FROZEN_EXPLORATORY_RERANKER_PAIR_AUDIT",
        "protocol": "public_corpus_rrf_crossencoder_pair_audit_v1",
        "retrieval_lock_sha256": sha(lock_path), "source_hashes": source_hashes,
        "source_code_sha256": code_hash,
        "compared_methods": ["RRF", "RRF+CrossEncoder"],
        "candidate_set_invariant": "recall@100 must match for every query",
        "test_informed_analysis": True,
        "real_model_calls": 0, "real_api_calls": 0,
    }
    (output / "protocol-lock.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    datasets = []
    for dataset, path in sources.items():
        rows = json.loads(path.read_text(encoding="utf-8"))
        result = compare_rows(rows)
        public_deltas = result.pop("per_query_public_id_numeric_deltas")
        (output / f"{dataset}-public-id-deltas.json").write_text(
            json.dumps(public_deltas, ensure_ascii=False, indent=2), encoding="utf-8")
        datasets.append({"dataset": dataset, **result})
    if sha(lock_path) != protocol["retrieval_lock_sha256"] or sha(Path(__file__)) != code_hash or any(sha(path) != source_hashes[name] for name, path in sources.items()):
        raise ValueError("source changed during paired audit")
    final = {
        "status": "COMPLETED_EXPLORATORY_RERANKER_PAIR_AUDIT",
        "protocol": protocol["protocol"],
        "datasets": datasets,
        "real_model_calls": 0, "real_api_calls": 0,
        "limitations": [
            "Post-hoc analysis of already inspected public retrieval results, not an independent benchmark.",
            "Candidate recall parity only identifies ranking loss, not why the cross-encoder scored evidence lower.",
            "The locked reranker is an MS MARCO TinyBERT model, not a SciFact-trained relevance model.",
            "No answer generation or educational utility is evaluated here.",
        ],
    }
    (output / "summary.json").write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    return final


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieval-root", type=Path,
                        default=ROOT / "experiments/results/rag_real_retrieval_20261013_01")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.retrieval_root, args.output)
    print(json.dumps({"status": result["status"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
