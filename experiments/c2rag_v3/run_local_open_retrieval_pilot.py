"""Open-candidate retrieval evaluation on CogniGuard's local dev resources.

Unlike the old C2-RAG runtime, this script does not filter candidates by the
target resource before retrieval. It evaluates BM25, Dense, RRF and the
late-interaction MaxSim pilot on the same 65-resource dev collection.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .core import BM25Index, C2RAGConfig, Chunk, DenseEmbeddingIndex, CrossEncoderReranker, ResourceDocument

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = ROOT / "experiments/datasets/cogniguard_math_suite/mixed_math_suite/splits/dev"


def average_precision(ranking: list[int], relevant: set[str], chunks: list[Chunk]) -> float:
    hits = 0
    total = 0.0
    for rank, index in enumerate(ranking, 1):
        if chunks[index].document_id in relevant:
            hits += 1
            total += hits / rank
    return total / max(1, len(relevant))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--collection-root", type=Path, default=None, help="Separate root containing teacher_resource/data")
    ap.add_argument("--queries", type=int, default=96)
    ap.add_argument("--output", type=Path, default=ROOT / "experiments/results/local_open_retrieval_pilot")
    args = ap.parse_args()
    collection_root = args.collection_root or args.data_root
    resource_file = collection_root / "teacher_resource/data/teacher_resources.jsonl"
    resource_rows = [json.loads(line) for line in resource_file.read_text(encoding="utf8").splitlines() if line.strip()]
    resources = [ResourceDocument.from_row(row) for row in resource_rows]
    chunks = []
    for resource in resources:
        words = resource.text.split()
        chunks.append(Chunk(resource.document_id, resource.document_id, resource.parent_id, resource.section_id, "body", resource.text, resource.owner, resource.license, resource.copyright_level, resource.allowed_roles, resource.allowed_use, resource.source_hash, resource.source_family, resource.semantic_topic, resource.knowledge_units))
    episodes = [json.loads(line) for line in (args.data_root / "evaluation/data/episodes.jsonl").read_text(encoding="utf8").splitlines() if line.strip()]
    question_file = args.data_root / "student_profile/data/student_questions.jsonl"
    questions = {str(row["request_id"]): row for row in (json.loads(line) for line in question_file.read_text(encoding="utf8").splitlines() if line.strip())}
    queries = []
    for row in episodes:
        if str(row.get("condition")) != "clean":
            continue
        task = questions.get(str(row["request_id"]), {})
        query = f"{row['user_request']} Knowledge point: {task.get('expected_knowledge', '')}. Difficulty: {task.get('difficulty', '')}."
        target_resource = str(task.get("source_resource_id") or row["resource_id"])
        queries.append((str(row["request_id"]), query, target_resource))
        if len(queries) >= args.queries:
            break
    cfg = C2RAGConfig(retrieval_backend="neural", reranker_backend="neural", model_device="auto")
    dense_path = ROOT / "assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    reranker_path = ROOT / "assets/models/hf_cache/models--cross-encoder--ms-marco-TinyBERT-L-2-v2/snapshots/81d1926f67cb8eee2c2be17ca9f793c7c3bd20cc"
    bm25 = BM25Index(chunks)
    dense = DenseEmbeddingIndex(chunks, backend="neural", model_path=dense_path, model_revision=cfg.dense_model_revision, device="auto")
    reranker = CrossEncoderReranker(backend="neural", model_path=reranker_path, model_revision=cfg.reranker_model_revision, device="auto")
    results = []
    for query_id, query, target in queries:
        sparse = bm25.search(query, len(chunks)); dense_hits = dense.search(query, len(chunks))
        sparse_ids = [i for i, _ in sparse]; dense_ids = [i for i, _ in dense_hits]
        fused = {}
        for rank, index in enumerate(sparse_ids, 1): fused[index] = fused.get(index, 0.0) + 1/(60+rank)
        for rank, index in enumerate(dense_ids, 1): fused[index] = fused.get(index, 0.0) + 1/(60+rank)
        rrf = sorted(fused, key=lambda i: (-fused[i], chunks[i].chunk_id))
        candidate = rrf[:min(30, len(rrf))]
        cross = sorted(candidate, key=lambda i: (-reranker.score(query, chunks[i]), chunks[i].chunk_id))
        late = sorted(candidate, key=lambda i: (-dense.late_interaction_score(query, chunks[i]), chunks[i].chunk_id))
        rankings = {"bm25": sparse_ids, "dense": dense_ids, "rrf": rrf, "late_interaction": late, "cross_encoder_on_rrf": cross}
        for method, ranking in rankings.items():
            top10 = ranking[:10]
            top100 = ranking[:100]
            hit = lambda i: chunks[i].document_id == target
            results.append({"query_id": query_id, "target_resource": target, "method": method, "recall_at_10": int(any(hit(i) for i in top10)), "recall_at_100": int(any(hit(i) for i in top100)), "mrr": next((1/(rank+1) for rank,i in enumerate(top100) if hit(i)), 0.0), "map": average_precision(top100, {target}, chunks), "rank": next((rank+1 for rank,i in enumerate(top100) if hit(i)), 0)})
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "per_query.csv").open("w", newline="", encoding="utf8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0])); writer.writeheader(); writer.writerows(results)
    summary = []
    for method in sorted({row["method"] for row in results}):
        rows = [row for row in results if row["method"] == method]
        summary.append({"method": method, "queries": len(rows), **{metric: sum(float(row[metric]) for row in rows)/len(rows) for metric in ("recall_at_10", "recall_at_100", "mrr", "map")}})
    (args.output / "summary.json").write_text(json.dumps({"dataset": "CogniGuard local open-candidate dev resources", "resources": len(resources), "queries": len(queries), "target_filter_before_retrieval": False, "collection_root": str(collection_root), "query_metadata": "task knowledge and difficulty appended from the public task schema", "summary": summary}, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
