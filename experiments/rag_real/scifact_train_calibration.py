"""Train-only SciFact RRF/cross-encoder fusion calibration.

Development selection uses a fixed hash-selected subset of official train
qrels. The already inspected test set is evaluated once after the fusion
weight is frozen. Results are exploratory, not an independent leaderboard run.
No external API or model download is performed.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import zipfile

from .prepare import ROOT, load_lock
from .retrieval import (
    REV_CROSS, REV_DENSE, code_hashes, dump, local_model_paths,
    model_hash, neural_chunks, rerank_batch, retrieval_metrics,
    rrf_rank, select_scifact, sha,
)


HASH_SEED = "20261013"
TRAIN_LIMIT = 200
ALPHAS = (0.0, 0.1, 0.25, 0.5, 0.75, 1.0)
SELECT_METRICS = ("recall@10", "mrr@100", "ndcg@10")


def load_train_queries(cache: Path, corpus: dict) -> list[dict]:
    texts = {}
    with (cache / "queries.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                texts[str(row["_id"])] = str(row["text"])
    with zipfile.ZipFile(cache / "scifact.zip") as archive:
        qrels = archive.read("scifact/qrels/train.tsv").decode("utf-8")
    gold = {}
    for row in csv.DictReader(io.StringIO(qrels), delimiter="\t"):
        if int(row["score"]) > 0:
            gold.setdefault(str(row["query-id"]), {})[str(row["corpus-id"])] = int(row["score"])
    if len(gold) != 809 or any(qid not in texts or not set(labels) <= set(corpus) for qid, labels in gold.items()):
        raise ValueError("official SciFact train qrels changed or refer to missing corpus")
    ids = sorted(gold, key=lambda qid: (sha((HASH_SEED + ":train:" + qid).encode()), qid))[:TRAIN_LIMIT]
    return [{"id": qid, "text": texts[qid], "gold": gold[qid]} for qid in ids]


def load_corpus_without_test_labels(cache: Path) -> dict[str, tuple[str, str]]:
    corpus = {}
    with (cache / "corpus.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                corpus[str(row["_id"])] = (str(row.get("title", "")), str(row.get("text", "")))
    if len(corpus) != 5183:
        raise ValueError("SciFact corpus count changed")
    return corpus


def blend_ranking(rrf: list[int], ce_scores: dict[int, float], alpha: float, chunks) -> list[int]:
    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be in [0,1]")
    head = rrf[:30]
    if not head:
        return rrf
    if set(head) != set(ce_scores):
        raise ValueError("cross-encoder scores must match the RRF head")
    lo, hi = min(ce_scores.values()), max(ce_scores.values())
    denom = max(hi - lo, 1e-12)
    positions = {idx: rank for rank, idx in enumerate(head)}

    def score(idx: int) -> float:
        rank_component = 1.0 - positions[idx] / max(len(head) - 1, 1)
        ce_component = (ce_scores[idx] - lo) / denom if hi > lo else rank_component
        return (1.0 - alpha) * rank_component + alpha * ce_component

    reranked = sorted(head, key=lambda idx: (-score(idx), positions[idx], chunks[idx].chunk_id))
    return reranked + rrf[len(head):]


def aggregate(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("no retrieval rows")
    keys = [key for key in rows[0] if key.startswith(("recall@", "mrr@", "ndcg@", "hit@", "all_evidence@"))]
    return {key: statistics.mean(float(row[key]) for row in rows) for key in keys}


def choose_alpha(development: dict[float, dict[str, float]]) -> float:
    base = development[0.0]
    feasible = [alpha for alpha in ALPHAS if alpha in development and all(
        development[alpha][metric] >= base[metric] - 1e-12 for metric in SELECT_METRICS)]
    if not feasible:
        raise RuntimeError("RRF alpha=0 failed its own non-inferiority gate")
    return max(feasible, key=lambda alpha: (
        development[alpha]["mrr@100"], development[alpha]["recall@10"],
        development[alpha]["ndcg@10"], -alpha))


def run(cache: Path, output: Path, device: str):
    from cogniguard.workflows.model_site import enable_existing_model_environment
    enable_existing_model_environment()
    from .graph import RETRIEVAL_GRAPH, invoke_batch
    return invoke_batch(RETRIEVAL_GRAPH, _steps(cache, output, device),
                        recursion_limit=2 * (TRAIN_LIMIT + 300) + 20)


def _steps(cache: Path, output: Path, device: str):
    if output.exists():
        raise FileExistsError("fresh output directory required")
    if os.getenv("PYTHONHASHSEED") != HASH_SEED or os.getenv("HF_HUB_OFFLINE") != "1":
        raise ValueError("local-only fixed-hash worker required")
    from experiments.c2rag_v3.core import BM25Index, DenseEmbeddingIndex, CrossEncoderReranker

    source_lock = load_lock(cache)
    corpus = load_corpus_without_test_labels(cache)
    train_queries = load_train_queries(cache, corpus)
    dense_path, cross_path = local_model_paths()
    paths = code_hashes()
    own = Path(__file__)
    paths[str(own.relative_to(ROOT))] = sha(own.read_bytes())
    protocol = {
        "status": "FROZEN_TRAIN_ONLY_CALIBRATION",
        "protocol": "scifact_train200_fusion_test300_v1",
        "source_lock_sha256": sha((cache / "source-lock.json").read_bytes()),
        "official_train_queries_available": 809,
        "train_subset": "200 public IDs by SHA256 of fixed seed and ID before relevance scores",
        "train_query_id_hash": sha("|".join(item["id"] for item in train_queries).encode()),
        "official_test_queries_expected": 300,
        "test_qrels_source_sha256": sha((cache / "test.tsv").read_bytes()),
        "alphas": ALPHAS,
        "fusion": "min-max normalized cross-encoder score and RRF head rank position, top30 only; tail unchanged",
        "selection": "train subset only: recall@10, MRR@100, NDCG@10 must each be at least RRF; maximize MRR with smallest-alpha tie break",
        "test_already_inspected": True,
        "model": "locked ms-marco-TinyBERT-L-2-v2",
        "dense_revision": REV_DENSE, "cross_revision": REV_CROSS,
        "dense_weight_sha256": model_hash(dense_path),
        "cross_weight_sha256": model_hash(cross_path),
        "source_code_sha256": paths,
        "real_api_calls": 0,
    }
    output.mkdir(parents=True, exist_ok=False)
    dump(output / "protocol-lock.json", protocol)
    yield ("prepare", len(train_queries) + 300)

    chunks = neural_chunks(corpus)
    bm25 = BM25Index(chunks)
    dense = DenseEmbeddingIndex(chunks, backend="neural", model_path=str(dense_path),
                                model_revision=REV_DENSE, device=device)
    reranker = CrossEncoderReranker(backend="neural", model_path=str(cross_path),
                                    model_revision=REV_CROSS, device=device)
    if dense.is_fallback or reranker.is_fallback:
        raise RuntimeError("locked neural retrieval or reranker fell back")

    def rank_query(query: dict) -> dict[float, dict[str, float]]:
        sparse = [idx for idx, _ in bm25.search(query["text"], 100)]
        dense_ids = [idx for idx, _ in dense.search(query["text"], 100)]
        rrf = rrf_rank(sparse, dense_ids, chunks)
        ce_scores = dict(rerank_batch(query["text"], rrf[:30], chunks, reranker))
        result = {}
        for alpha in ALPHAS:
            ranking = blend_ranking(rrf, ce_scores, alpha, chunks)
            if alpha == 0.0 and ranking != rrf:
                raise ValueError("RRF baseline changed under alpha zero")
            result[alpha] = retrieval_metrics([chunks[idx].chunk_id for idx in ranking[:100]], query["gold"])
        return result

    train_rows = {alpha: [] for alpha in ALPHAS}
    for count, query in enumerate(train_queries, 1):
        item = rank_query(query)
        for alpha in ALPHAS:
            train_rows[alpha].append(item[alpha])
        if count % 20 == 0 or count == len(train_queries):
            print(json.dumps({"split": "train", "progress": count, "queries": len(train_queries)}), flush=True)
        yield "item"
    development = {alpha: aggregate(rows) for alpha, rows in train_rows.items()}
    chosen = choose_alpha(development)
    print(json.dumps({"stage": "train_selection_complete", "chosen_alpha": chosen}), flush=True)

    test_corpus, test_queries = select_scifact(cache)
    if test_corpus != corpus or len(test_queries) != 300:
        raise ValueError("SciFact test corpus/count changed")
    if set(item["id"] for item in train_queries) & set(item["id"] for item in test_queries):
        raise ValueError("SciFact train/test query IDs overlap")
    test_rows = {alpha: [] for alpha in (0.0, chosen, 1.0)}
    for count, query in enumerate(test_queries, 1):
        item = rank_query(query)
        for alpha in test_rows:
            test_rows[alpha].append(item[alpha])
        if count % 20 == 0 or count == len(test_queries):
            print(json.dumps({"split": "test", "progress": count, "queries": len(test_queries)}), flush=True)
        yield "item"
    test_summary = {str(alpha): aggregate(rows) for alpha, rows in test_rows.items()}
    if code_hashes() | {str(own.relative_to(ROOT)): sha(own.read_bytes())} != paths or load_lock(cache) != source_lock:
        raise ValueError("code or source lock changed during calibration")
    final = {
        "status": "COMPLETED_TRAIN_ONLY_CALIBRATION",
        "protocol": protocol["protocol"],
        "train_queries": len(train_queries), "test_queries": len(test_queries),
        "test_query_id_hash": sha("|".join(item["id"] for item in test_queries).encode()),
        "chosen_alpha": chosen,
        "development_metrics": {str(alpha): values for alpha, values in development.items()},
        "test_metrics": test_summary,
        "test_paired_delta_selected_minus_rrf": {
            key: statistics.mean(
                selected[key] - base[key] for selected, base in zip(test_rows[chosen], test_rows[0.0]))
            for key in SELECT_METRICS
        },
        "real_api_calls": 0,
        "limitations": [
            "The train subset selects alpha, but the test set had already been inspected in previous experiments; exploratory confirmation only.",
            "No model retraining or new external weight download; the same general-domain reranker is score-blended.",
            "Development non-inferiority does not guarantee test non-inferiority.",
            "Retrieval metrics do not measure answer quality, teaching utility or copyright control.",
        ],
    }
    dump(output / "summary.json", final)
    print(json.dumps({"status": final["status"], "chosen_alpha": chosen,
                      "output": str(output)}), flush=True)
    return final


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache/rag-real-v1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.worker:
        env = dict(os.environ, PYTHONHASHSEED=HASH_SEED, HF_HUB_OFFLINE="1",
                   TRANSFORMERS_OFFLINE="1", LANGSMITH_TRACING="false",
                   LANGCHAIN_TRACING_V2="false", TOKENIZERS_PARALLELISM="false",
                   OMP_NUM_THREADS="2")
        done = subprocess.run([sys.executable, "-X", "utf8", "-m",
                               "experiments.rag_real.scifact_train_calibration",
                               *sys.argv[1:], "--worker"], cwd=ROOT, env=env)
        raise SystemExit(done.returncode)
    run(args.cache, args.output, args.device)


if __name__ == "__main__":
    main()
