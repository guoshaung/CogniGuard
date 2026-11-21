"""Open-candidate retrieval pilot on a pinned BEIR SciFact slice.

This is a retrieval-only experiment. It deliberately does not run the
copyright renderer, so retrieval quality and output safety are not conflated.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import zipfile
from pathlib import Path

import requests

from .core import Chunk, DenseEmbeddingIndex, BM25Index, C2RAGConfig, CrossEncoderReranker


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "experiments" / "external_data" / "beir_scifact"
URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"


def fetch() -> Path:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    marker = DATA_ROOT / "scifact" / "corpus.jsonl"
    if marker.exists():
        return marker.parent
    response = requests.get(URL, timeout=120, verify=False)
    response.raise_for_status()
    payload = response.content
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        archive.extractall(DATA_ROOT)
    return marker.parent


def load_rows(root: Path, limit: int) -> tuple[list[Chunk], list[tuple[str, str, set[str]]]]:
    corpus = []
    with (root / "corpus.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                corpus.append(row)
    chunks = [Chunk(
        chunk_id=str(row["_id"]), document_id=str(row["_id"]), parent_id=str(row["_id"]),
        section_id="body", section_type="body", text=f"{row.get('title','')} {row.get('text','')}",
        owner="public", license="BEIR-SciFact", copyright_level=0.0,
        allowed_roles=("researcher", "teacher"), allowed_use=("retrieval",),
        source_hash=str(row["_id"]), source_family="beir_scifact", semantic_topic="scifact",
        knowledge_units=(),
    ) for row in corpus]
    queries = {}
    with (root / "queries.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                queries[str(row["_id"])] = str(row["text"])
    qrels = {}
    with (root / "qrels" / "test.tsv").open(encoding="utf-8") as handle:
        next(handle)
        for line in handle:
            qid, did, score = line.rstrip("\n").split("\t")
            if int(score) > 0:
                qrels.setdefault(qid, set()).add(did)
    selected = [(qid, queries[qid], qrels[qid]) for qid in sorted(qrels) if qid in queries][:limit]
    return chunks, selected


def ranks_to_scores(ranks: dict[int, float], k: int) -> list[int]:
    return sorted(ranks, key=lambda i: (-ranks[i], i))[:k]


def average_precision(retrieved: list[int], relevant: set[str], chunks: list[Chunk]) -> float:
    hit = 0
    total = 0.0
    for rank, index in enumerate(retrieved, 1):
        if chunks[index].document_id in relevant:
            hit += 1
            total += hit / rank
    return total / max(1, len(relevant))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=int, default=100)
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/results/beir_scifact_retrieval_pilot")
    args = parser.parse_args()
    root = fetch()
    chunks, queries = load_rows(root, args.queries)
    config = C2RAGConfig(retrieval_backend="neural", reranker_backend="neural", model_device="auto")
    bm25 = BM25Index(chunks)
    dense = DenseEmbeddingIndex(chunks, backend="neural", model_path=ROOT / "assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41", model_revision=config.dense_model_revision, device="auto")
    reranker = CrossEncoderReranker(backend="neural", model_path=ROOT / "assets/models/hf_cache/models--cross-encoder--ms-marco-TinyBERT-L-2-v2/snapshots/81d1926f67cb8eee2c2be17ca9f793c7c3bd20cc", model_revision=config.reranker_model_revision, device="auto")
    methods = ["bm25", "dense", "rrf", "late_interaction"]
    rows = []
    for qid, query, relevant in queries:
        sparse = bm25.search(query, 100)
        dense_hits = dense.search(query, 100)
        sparse_ids = [i for i, _ in sparse]
        dense_ids = [i for i, _ in dense_hits]
        rrf = {}
        for rank, i in enumerate(sparse_ids, 1): rrf[i] = rrf.get(i, 0.0) + 1 / (60 + rank)
        for rank, i in enumerate(dense_ids, 1): rrf[i] = rrf.get(i, 0.0) + 1 / (60 + rank)
        candidate = ranks_to_scores(rrf, 30)
        reranked = sorted(candidate, key=lambda i: (-reranker.score(query, chunks[i]), i))
        late = sorted(candidate, key=lambda i: (-dense.late_interaction_score(query, chunks[i]), i))
        rankings = {"bm25": sparse_ids, "dense": dense_ids, "rrf": candidate, "late_interaction": late}
        for method, ranking in rankings.items():
            top10 = ranking[:10]
            top100 = ranking[:100]
            rows.append({"query_id": qid, "method": method, "relevant": len(relevant), "recall_at_10": int(any(chunks[i].document_id in relevant for i in top10)), "recall_at_100": int(any(chunks[i].document_id in relevant for i in top100)), "mrr": next((1/(rank+1) for rank,i in enumerate(top100) if chunks[i].document_id in relevant), 0.0), "map": average_precision(top100, relevant, chunks)})
        rows.append({"query_id": qid, "method": "cross_encoder_on_rrf", "relevant": len(relevant), "recall_at_10": int(any(chunks[i].document_id in relevant for i in reranked[:10])), "recall_at_100": int(any(chunks[i].document_id in relevant for i in reranked[:100])), "mrr": next((1/(rank+1) for rank,i in enumerate(reranked[:100]) if chunks[i].document_id in relevant), 0.0), "map": average_precision(reranked[:100], relevant, chunks)})
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "per_query.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    summary = []
    for method in sorted({r["method"] for r in rows}):
        subset = [r for r in rows if r["method"] == method]
        summary.append({"method": method, "queries": len(subset), "recall_at_10": sum(r["recall_at_10"] for r in subset)/len(subset), "recall_at_100": sum(r["recall_at_100"] for r in subset)/len(subset), "mrr": sum(r["mrr"] for r in subset)/len(subset), "map": sum(r["map"] for r in subset)/len(subset)})
    (args.output / "summary.json").write_text(json.dumps({"dataset": "BEIR SciFact", "dataset_url": URL, "queries": len(queries), "corpus_documents": len(chunks), "summary": summary}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
