from __future__ import annotations

METHODS = (
    "advanced_rag_no_defense",
    "reranking_protection",
    "summarization_protection",
    "static_excerpt",
    "independent_ngram_guard",
    "semantic_similarity_guard",
    "full_c2rag_v3",
    "full_c2rag_v3+cg",
    "late_interaction_c2rag",
    "crag_style_correction",
    "self_rag_style_reflection",
    "adaptive_rag_risk_router",
    "c2rag_without_provenance",
    "c2rag_without_cumulative_budget",
    "c2rag_without_reconstruction_history",
)

EXTERNAL_BASELINES = {
    "RAGFort": {
        "status": "NOT_RUN",
        "official_repo": "https://github.com/happywinder/RAGFort",
        "official_commit": "9ad13fcd42039dab790cc7d9b92a4bd54f484bb4",
        "reason": "official architecture requires contrastive reindexing, training conditions and draft/reference cascade models not present in this repository; no local simplification is reported as RAGFort",
    },
    "CanaryRAG": {
        "status": "NOT_RUN",
        "reason": "canary construction, oracle-path streaming detection and post-detection enforcement were not available as a locked compatible implementation",
    },
}


def baseline_manifest() -> list[dict[str, str]]:
    return [
        {"method": "advanced_rag_no_defense", "type": "comparison", "description": "same modern RAG retrieval, no copyright defense"},
        {"method": "reranking_protection", "type": "comparison", "description": "shared neural reranker plus a distinct similarity-threshold filtering branch and controlled quote"},
        {"method": "summarization_protection", "type": "comparison", "description": "summary-only output"},
        {"method": "static_excerpt", "type": "comparison", "description": "fixed excerpt output"},
        {"method": "independent_ngram_guard", "type": "comparison", "description": "post-output lexical guard without cumulative semantic state"},
        {"method": "semantic_similarity_guard", "type": "comparison", "description": "post-output semantic-similarity guard without cumulative budget"},
        {"method": "full_c2rag_v3", "type": "target", "description": "metadata filtering, RRF/reranking, history and actual disclosure budget"},
        {"method": "full_c2rag_v3+cg", "type": "integration", "description": "C²-RAG candidate generation plus CG-owned final candidate selection"},
        {"method": "late_interaction_c2rag", "type": "retrieval_variant", "description": "C²-RAG with token-level MaxSim late-interaction retrieval pilot; reuses the locked encoder and is not an official ColBERT reproduction"},
        {"method": "crag_style_correction", "type": "modern_baseline", "description": "CRAG-style retrieval correction and conservative fallback, adapted to the shared C²-RAG output contract"},
        {"method": "self_rag_style_reflection", "type": "modern_baseline", "description": "Self-RAG-style reflection gate for deciding whether to expand, summarize, or refuse"},
        {"method": "adaptive_rag_risk_router", "type": "modern_baseline", "description": "Adaptive-RAG-style risk-aware routing among summary, variant, hint, and refusal"},
        {"method": "c2rag_without_provenance", "type": "ablation", "description": "removes provenance-aware policy branch"},
        {"method": "c2rag_without_cumulative_budget", "type": "ablation", "description": "removes cumulative budget enforcement only; reconstruction history remains enabled"},
        {"method": "c2rag_without_reconstruction_history", "type": "ablation", "description": "removes session reconstruction state"},
    ]
