"""Offline stage-loss audit for the native C²-RAG HotpotQA transfer probe.

This is a diagnostic on twelve already examined public cases, not a new
independent benchmark or a claim that exact quotation is desirable under a
restrictive copyright policy. No answer model/API is called.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

from .control_probe import BUDGET, CASES, compact, relevant_sentences
from .prepare import ROOT, load_lock
from .retrieval import REV_CROSS, REV_DENSE, code_hashes, dump, local_model_paths, select_hotpot, sha


HASH_SEED = "20261013"
METHODS = ("advanced_rag_no_defense", "full_c2rag_v3")


def sentence_fraction(sentences: list[str], text: str) -> float:
    usable = [compact(sentence) for sentence in sentences if compact(sentence)]
    target = compact(text)
    return sum(sentence in target for sentence in usable) / max(1, len(usable))


def run(cache: Path, output: Path, device: str):
    from cogniguard.workflows.model_site import enable_existing_model_environment
    enable_existing_model_environment()
    from .graph import CONTROL_GRAPH, invoke_batch
    return invoke_batch(CONTROL_GRAPH, _steps(cache, output, device), recursion_limit=100)


def _steps(cache: Path, output: Path, device: str):
    if output.exists():
        raise FileExistsError("fresh output directory required")
    if os.getenv("PYTHONHASHSEED") != HASH_SEED or os.getenv("HF_HUB_OFFLINE") != "1":
        raise ValueError("isolated local-only worker required")
    from experiments.c2rag_v3.core import C2RAGConfig, C2RAGV3, ResourceDocument

    lock = load_lock(cache)
    _, selected = select_hotpot(cache)
    picked = {item["id"] for item in selected[:CASES]}
    original = json.loads((cache / "hotpot-validation.json").read_text(encoding="utf-8"))
    by_id = {str(item["id"]): item for item in original if str(item["id"]) in picked}
    hashes = code_hashes()
    own_path = Path(__file__)
    hashes[str(own_path.relative_to(ROOT))] = sha(own_path.read_bytes())
    protocol = {
        "status": "FROZEN_EXPLORATORY_STAGE_LOSS_PROBE",
        "protocol": "hotpot_native_c2rag_stage_loss_v1",
        "source_lock_sha256": sha((cache / "source-lock.json").read_bytes()),
        "case_public_ids": [item["id"] for item in selected[:CASES]],
        "methods": METHODS, "budget": BUDGET, "copyright_level": .85,
        "generator_backend": "fallback", "retrieval_backend": "locked_neural",
        "reranker_backend": "locked_neural", "device": device,
        "metric": "exact_supporting_sentence_fraction_at_each_stage",
        "caveat": "Exact supporting-sentence retention is not semantic answer correctness or a target that a restrictive quotation policy must maximize.",
        "source_code_sha256": hashes,
        "real_api_calls": 0, "model_generation_calls": 0,
    }
    output.mkdir(parents=True, exist_ok=False)
    dump(output / "protocol-lock.json", protocol)
    yield ("prepare", CASES)

    dense_path, cross_path = local_model_paths()
    rows = []
    for count, query in enumerate(selected[:CASES], 1):
        source = by_id[query["id"]]
        resources = []
        for title, sentences in source["context"]:
            content = " ".join(str(sentence).strip() for sentence in sentences if str(sentence).strip())
            if not content:
                continue
            did = sha((str(title) + "\x1f" + content).encode())[:24]
            resources.append(ResourceDocument(
                document_id=did, parent_id=did, section_id="body", text=content,
                title=str(title), owner="Wikipedia via HotpotQA", license="CC-BY-SA-4.0",
                copyright_level=.85, allowed_roles=("teacher",), allowed_use=("tutoring",),
                source_hash=sha(content.encode()), source_family=f"hotpot:{query['id']}",
                semantic_topic=str(title), knowledge_units=(),
            ))
        refs = relevant_sentences(source)
        if not refs:
            raise ValueError("case has no supporting sentences")
        corpus_text = " ".join(resource.text for resource in resources)
        corpus_fraction = sentence_fraction(refs, corpus_text)
        config = C2RAGConfig(
            retrieval_backend="neural", dense_model_path=str(dense_path),
            dense_model_revision=REV_DENSE,
            reranker_backend="neural", reranker_model_path=str(cross_path),
            reranker_model_revision=REV_CROSS, model_device=device,
            generator_backend="fallback", total_copyright_budget=BUDGET,
        )
        engine = C2RAGV3(resources, config)
        if engine.dense.is_fallback or engine.reranker.is_fallback or not engine.generator.is_fallback:
            raise RuntimeError("backend differs from locked protocol")
        chunks = {item.chunk_id: item for item in engine.chunks}
        for method in METHODS:
            result = engine.run_round(
                session_id=f"alignment-{method}-{query['id']}", round_id=1,
                identity=f"reader-{query['id']}", query=query["text"],
                role="teacher", purpose="tutoring", method=method,
                target_resource_id=None,
            )
            chosen = [chunks[item["chunk_id"]] for item in result.selected_chunks]
            first_text = chosen[0].text if chosen else ""
            selected_text = " ".join(chunk.text for chunk in chosen)
            rows.append({
                "case_public_id": query["id"], "method": method,
                "supporting_sentence_count": len(refs),
                "corpus_support_fraction": corpus_fraction,
                "first_document_gold": int(bool(chosen and chosen[0].document_id in query["gold"])),
                "any_selected_document_gold": int(any(chunk.document_id in query["gold"] for chunk in chosen)),
                "first_chunk_support_fraction": sentence_fraction(refs, first_text),
                "selected_chunks_support_fraction": sentence_fraction(refs, selected_text),
                "allowed_evidence_support_fraction": sentence_fraction(refs, result.allowed_evidence),
                "generated_answer_support_fraction": sentence_fraction(refs, result.generated_answer),
                "released_answer_support_fraction": sentence_fraction(refs, result.released_answer),
                "planned_action": result.planned_action.get("action"),
                "executed_action": result.executed_action,
                "refused": int(result.refusal),
                "plan_execution_match": int(result.plan_execution_match),
                "selected_chunk_count": len(chosen),
                "allowed_word_count": len(result.allowed_evidence.split()),
                "released_word_count": len(result.released_answer.split()),
            })
        print(json.dumps({"stage_audit_progress": count, "cases": CASES}), flush=True)
        yield "item"
    current_hashes = code_hashes()
    current_hashes[str(own_path.relative_to(ROOT))] = sha(own_path.read_bytes())
    if current_hashes != hashes or load_lock(cache) != lock:
        raise ValueError("source code or corpus changed during audit")
    dump(output / "per_case_public_ids_metrics_only.json", rows)
    metrics = (
        "corpus_support_fraction", "first_document_gold", "any_selected_document_gold",
        "first_chunk_support_fraction", "selected_chunks_support_fraction",
        "allowed_evidence_support_fraction", "generated_answer_support_fraction",
        "released_answer_support_fraction", "refused", "plan_execution_match",
        "selected_chunk_count", "allowed_word_count", "released_word_count",
    )
    summary = []
    for method in METHODS:
        subset = [row for row in rows if row["method"] == method]
        summary.append({
            "method": method, "cases": len(subset),
            **{metric: statistics.mean(row[metric] for row in subset) for metric in metrics},
            "planned_action_counts": {action: sum(row["planned_action"] == action for row in subset)
                                      for action in sorted({row["planned_action"] for row in subset})},
            "executed_action_counts": {action: sum(row["executed_action"] == action for row in subset)
                                       for action in sorted({row["executed_action"] for row in subset})},
        })
    final = {
        "status": "COMPLETED_EXPLORATORY_STAGE_LOSS_PROBE",
        "protocol": protocol["protocol"], "cases": CASES,
        "methods": summary, "real_api_calls": 0,
        "model_generation_calls": 0,
        "limitations": [
            "Same twelve already examined cases; not an independent test.",
            "Exact support-sentence retention does not measure semantic answer quality.",
            "Restrictive policy on openly licensed paragraphs is an experimental control, not a legal conclusion.",
            "The native fallback generator is math-oriented; no HotpotQA answer model was evaluated.",
        ],
    }
    dump(output / "summary.json", final)
    print(json.dumps({"status": final["status"], "output": str(output)}), flush=True)
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
                               "experiments.rag_real.alignment_probe", *sys.argv[1:], "--worker"],
                              cwd=ROOT, env=env)
        raise SystemExit(done.returncode)
    run(args.cache, args.output, args.device)


if __name__ == "__main__":
    main()
