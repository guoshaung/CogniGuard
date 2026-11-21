"""Public-corpus retrieval for the existing BM25, neural dense and cross-encoder stack."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import subprocess
import sys

from .prepare import ROOT, load_lock

HASH_SEED = "20261013"
HOTPOT_N = 120
METHODS = ("BM25", "Dense", "RRF", "RRF+CrossEncoder")
REV_DENSE = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
REV_CROSS = "81d1926f67cb8eee2c2be17ca9f793c7c3bd20cc"


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def dump(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def doc_id(title: str, text: str) -> str:
    return sha((title + "\x1f" + text).encode())[:24]


def select_hotpot(cache: Path, limit: int = HOTPOT_N):
    rows = json.loads((cache / "hotpot-validation.json").read_text(encoding="utf-8"))
    # Frozen public row-ID sample, before looking at retrieval results.
    picked = sorted(rows, key=lambda r: (sha((HASH_SEED + str(r["id"])).encode()), str(r["id"])))[:limit]
    corpus = {}
    queries = []
    for row in picked:
        context = {}
        for title, sentences in row["context"]:
            text = " ".join(str(s).strip() for s in sentences if str(s).strip())
            if not text:
                continue
            did = doc_id(title, text)
            corpus[did] = (str(title), text)
            context.setdefault(str(title), set()).add(did)
        supporting = {str(title) for title, _ in row["supporting_facts"]}
        relevant = set().union(*(context.get(title, set()) for title in supporting))
        if not relevant or supporting - set(context):
            raise ValueError("Hotpot gold supporting title missing from provided context")
        queries.append({"id": str(row["id"]), "text": str(row["question"]), "gold": {did: 1 for did in relevant}, "type": str(row["type"]), "supporting_titles": len(supporting)})
    return corpus, queries


def select_scifact(cache: Path):
    corpus = {}
    with (cache / "corpus.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                corpus[str(row["_id"])] = (str(row.get("title", "")), str(row.get("text", "")))
    questions = {}
    with (cache / "queries.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                questions[str(row["_id"])] = str(row["text"])
    import csv
    gold = defaultdict(dict)
    with (cache / "test.tsv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if int(row["score"]) > 0:
                gold[row["query-id"]][row["corpus-id"]] = int(row["score"])
    if len(corpus) != 5183 or len(gold) != 300:
        raise ValueError("SciFact public corpus or gold count changed")
    queries = [{"id": qid, "text": questions[qid], "gold": gold[qid], "type": "scientific_claim", "supporting_titles": len(gold[qid])} for qid in sorted(gold)]
    if any(not set(q["gold"]) <= set(corpus) for q in queries):
        raise ValueError("SciFact qrels refer to absent corpus documents")
    return corpus, queries


def rrf_rank(a: list[int], b: list[int], chunks) -> list[int]:
    scores = defaultdict(float)
    for ranking in (a, b):
        for rank, i in enumerate(ranking, 1):
            scores[i] += 1.0 / (60 + rank)
    return sorted(scores, key=lambda i: (-scores[i], chunks[i].chunk_id))


def retrieval_metrics(rank_ids: list[str], gold: dict[str, int]) -> dict[str, float]:
    if not gold:
        raise ValueError("missing relevance judgments")
    result = {}
    relevant = set(gold)
    for k in (1, 3, 5, 10, 100):
        top = rank_ids[:k]
        found = len(relevant & set(top))
        result[f"recall@{k}"] = found / len(relevant)
        if k <= 10:
            result[f"hit@{k}"] = float(found > 0)
            result[f"all_evidence@{k}"] = float(found == len(relevant))
    first = next((rank for rank, did in enumerate(rank_ids[:100], 1) if did in relevant), None)
    result["mrr@100"] = 1.0 / first if first else 0.0
    gain = sum((2**gold.get(did, 0)-1)/math.log2(rank+1) for rank, did in enumerate(rank_ids[:10], 1))
    ideal = sum((2**grade-1)/math.log2(rank+1) for rank, grade in enumerate(sorted(gold.values(), reverse=True)[:10], 1))
    result["ndcg@10"] = gain / ideal if ideal else 0.0
    return result


def neural_chunks(corpus: dict[str, tuple[str, str]]):
    from experiments.c2rag_v3.core import Chunk
    return [Chunk(
        chunk_id=did, document_id=did, parent_id=did, section_id="body", section_type="body",
        text=f"{title} {body}", owner="public_dataset", license="public_dataset_source_terms",
        copyright_level=0.0, allowed_roles=("researcher", "teacher"), allowed_use=("retrieval",),
        source_hash=sha(body.encode()), source_family="public_corpus", semantic_topic="",
        knowledge_units=(),
    ) for did, (title, body) in sorted(corpus.items())]


def local_model_paths():
    return (
        ROOT / "assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots" / REV_DENSE,
        ROOT / "assets/models/hf_cache/models--cross-encoder--ms-marco-TinyBERT-L-2-v2/snapshots" / REV_CROSS,
    )


def model_hash(path: Path) -> str:
    candidate = path / "model.safetensors"
    if not candidate.is_file():
        candidate = path / "pytorch_model.bin"
    if not candidate.is_file():
        raise FileNotFoundError("locked local model weights unavailable")
    h = hashlib.sha256()
    with candidate.open("rb") as handle:
        for piece in iter(lambda: handle.read(1024*1024), b""):
            h.update(piece)
    return h.hexdigest()


def code_hashes():
    paths = [Path(__file__), ROOT / "experiments/c2rag_v3/core.py", ROOT / "experiments/c2rag_v3/generator.py", ROOT / "experiments/c2rag_v3/policy_selector.py"]
    return {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in paths}


def rerank_batch(query: str, indices: list[int], chunks, reranker) -> list[tuple[int, float]]:
    import torch
    if reranker.is_fallback:
        raise RuntimeError("neural reranker required")
    scores=[]
    for start in range(0, len(indices), 16):
        batch = indices[start:start+16]
        enc = reranker.tokenizer([query]*len(batch), [chunks[i].text for i in batch], padding=True, truncation=True, max_length=256, return_tensors="pt")
        enc = {key:value.to(reranker.device) for key,value in enc.items()}
        with torch.inference_mode():
            values = reranker.model(**enc).logits.reshape(-1).float().cpu().tolist()
        scores.extend(zip(batch, values))
    return sorted(scores, key=lambda pair: (-pair[1], chunks[pair[0]].chunk_id))


def evaluate_dataset(name: str, corpus, queries, device: str):
    from experiments.c2rag_v3.core import BM25Index, DenseEmbeddingIndex, CrossEncoderReranker
    chunks = neural_chunks(corpus)
    dense_path, cross_path = local_model_paths()
    bm25 = BM25Index(chunks)
    dense = DenseEmbeddingIndex(chunks, backend="neural", model_path=str(dense_path), model_revision=REV_DENSE, device=device)
    reranker = CrossEncoderReranker(backend="neural", model_path=str(cross_path), model_revision=REV_CROSS, device=device)
    if dense.is_fallback or reranker.is_fallback:
        raise RuntimeError("a real neural model fell back")
    # Identity check: batching may speed inference, but it cannot change the locked reranker score.
    reference = reranker.score(queries[0]["text"], chunks[0])
    batched = rerank_batch(queries[0]["text"], [0], chunks, reranker)[0][1]
    if abs(reference - batched) > 1e-4:
        raise ValueError("cross-encoder batch/singleton mismatch")
    rows=[]
    for index, query in enumerate(queries, 1):
        sparse = [i for i,_ in bm25.search(query["text"], 100)]
        dense_ids = [i for i,_ in dense.search(query["text"], 100)]
        rrf = rrf_rank(sparse, dense_ids, chunks)
        head = [i for i,_ in rerank_batch(query["text"], rrf[:30], chunks, reranker)]
        fused_rerank = head + [i for i in rrf if i not in set(head)]
        for method, ranking in zip(METHODS, (sparse,dense_ids,rrf,fused_rerank)):
            ids = [chunks[i].chunk_id for i in ranking[:100]]
            rows.append({"query_id":query["id"], "query_type":query["type"], "gold_document_count":len(query["gold"]), "method":method,
                         **retrieval_metrics(ids,query["gold"])})
        if index % 20 == 0 or index == len(queries):
            print(json.dumps({"dataset":name,"retrieval_progress":index,"queries":len(queries)}),flush=True)
    metrics=[k for k in rows[0] if k.startswith(("recall@","hit@","all_evidence@","mrr@","ndcg@"))]
    summary=[]
    for method in METHODS:
        subset=[r for r in rows if r["method"]==method]
        summary.append({"method":method,"query_count":len(subset), **{metric:sum(r[metric] for r in subset)/len(subset) for metric in metrics}})
    return {"dataset":name,"documents":len(chunks),"queries":len(queries),"methods":summary,"per_query":rows,
            "dense_real_model":not dense.is_fallback,"cross_real_model":not reranker.is_fallback,"model_device":device}


def run(cache: Path, output: Path, device: str):
    from cogniguard.workflows.model_site import enable_existing_model_environment
    enable_existing_model_environment()
    from .graph import RETRIEVAL_GRAPH, invoke_batch
    return invoke_batch(RETRIEVAL_GRAPH, _retrieval_steps(cache, output, device))


def _retrieval_steps(cache: Path, output: Path, device: str):
    if output.exists():
        raise FileExistsError("fresh output directory required")
    if os.getenv("PYTHONHASHSEED") != HASH_SEED or os.getenv("HF_HUB_OFFLINE") != "1":
        raise ValueError("isolated offline worker with frozen hash seed required")
    lock = load_lock(cache)
    dense_path, cross_path = local_model_paths()
    hashes = code_hashes()
    protocol={
        "status":"FROZEN_BEFORE_EVALUATION", "protocol":"real_public_corpus_open_retrieval_v1",
        "sources":lock,"hotpot_sampling":"SHA256(seed+public ID), first 120 of distractor validation; no model-score selection",
        "scifact_sampling":"all 300 test qrels; all 5183 corpus abstracts", "hash_seed":HASH_SEED,
        "retrieval_contract":"No gold-target prefilter; all corpus documents ranked. BM25 and dense top100, RRF reciprocal constant 60, CrossEncoder reranks RRF first30 and preserves tail.",
        "query_gold_isolation":"Gold IDs used only after rankings; answer text and supporting facts not passed to retriever or reranker.",
        "backend":{"dense":"locked all-MiniLM-L6-v2","dense_revision":REV_DENSE,"dense_weight_sha256":model_hash(dense_path),
                   "reranker":"locked ms-marco-TinyBERT-L-2-v2","reranker_revision":REV_CROSS,"reranker_weight_sha256":model_hash(cross_path),"requested_device":device,
                   "fallback_allowed":False},
        "source_code_sha256":hashes,
        "dependencies":{name:importlib.metadata.version(name) for name in ("numpy","scikit-learn","torch","transformers")},
        "real_api_calls":0,"model_generation_calls":0,"langsmith_upload":False,
    }
    output.mkdir(parents=True,exist_ok=False)
    dump(output/"protocol-lock.json",protocol)
    yield ("prepare", 2)
    results=[]
    for name, loader in (("HotpotQA-distractor120",select_hotpot),("BEIR-SciFact-test300",select_scifact)):
        corpus,questions=loader(cache)
        result=evaluate_dataset(name,corpus,questions,device)
        dump(output/(name+"-per-query.json"),result.pop("per_query"))
        dump(output/(name+"-summary.json"),result)
        results.append(result)
        yield "item"
    if code_hashes()!=hashes:
        raise ValueError("code changed during evaluation")
    final={"status":"COMPLETED_REAL_CORPUS_RETRIEVAL_ONLY","protocol":protocol["protocol"],"results":results,
           "real_api_calls":0,"model_generation_calls":0,
           "limitations":[
               "Retrieval quality only; no answer generation, answer EM/F1, teaching utility, copyright protection ASR or official HotpotQA leaderboard score.",
               "HotpotQA evaluates a frozen 120-question slice against the merged provided 10-paragraph contexts; neither full 7405 dev questions nor whole-Wikipedia fullwiki retrieval.",
               "SciFact evaluates all 300 BEIR test claims against all 5183 corpus abstracts, but this model/protocol is a CogniGuard baseline and not an official leaderboard run.",
               "Hotpot paragraphs can be reused across sampled questions, so query observations are not independent.",
               "Corpus contains licensed public materials; any access/quote budget imposed in separate tests is an experimental policy, not a legal requirement.",
           ]}
    dump(output/"summary.json",final)
    print(json.dumps({"status":final["status"],"output":str(output)}),flush=True)
    return final


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cache",type=Path,default=ROOT/".cache/rag-real-v1")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--device",choices=("cpu","cuda"),default="cuda")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not args.worker:
        env=dict(os.environ,PYTHONHASHSEED=HASH_SEED,HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",LANGSMITH_TRACING="false",LANGCHAIN_TRACING_V2="false",TOKENIZERS_PARALLELISM="false",OMP_NUM_THREADS="2")
        result=subprocess.run([sys.executable,"-X","utf8","-m","experiments.rag_real.retrieval",*sys.argv[1:],"--worker"],cwd=ROOT,env=env)
        raise SystemExit(result.returncode)
    run(args.cache,args.output,args.device)


if __name__=="__main__":
    main()
