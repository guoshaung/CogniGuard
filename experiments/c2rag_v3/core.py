from __future__ import annotations

import hashlib
import math
import re
import time
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .generator import TeachingGenerator

try:
    import numpy as np
    from sklearn.feature_extraction.text import HashingVectorizer
except ImportError:  # pragma: no cover - the repository's test environment has these
    np = None
    HashingVectorizer = None

try:
    import torch
    from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer
except ImportError:  # pragma: no cover - fallback remains available for minimal environments
    torch = None
    AutoModel = None
    AutoModelForSequenceClassification = None
    AutoTokenizer = None


_NEURAL_MODEL_CACHE: dict[tuple[str, str, str], Any] = {}
_NEURAL_QUERY_CACHE: dict[tuple[str, str, str], np.ndarray] = {}
_NEURAL_TOKEN_CACHE: dict[tuple[str, str, str], tuple[Any, int]] = {}


def stable_hash(value: Any) -> str:
    if isinstance(value, bytes):
        payload = value
    else:
        payload = repr(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower())


def ngrams(text: str, n: int = 5) -> set[tuple[str, ...]]:
    values = tokens(text)
    return {tuple(values[i : i + n]) for i in range(max(0, len(values) - n + 1))}


def lcs_length(left: str, right: str) -> int:
    a, b = tokens(left), tokens(right)
    previous = [0] * (len(b) + 1)
    for item in a:
        current = [0]
        for index, other in enumerate(b, start=1):
            current.append(previous[index - 1] + 1 if item == other else max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def lcs_ratio(left: str, right: str) -> float:
    denominator = max(1, len(tokens(right)))
    return lcs_length(left, right) / denominator


def lexical_cosine(left: str, right: str) -> float:
    lhs, rhs = Counter(tokens(left)), Counter(tokens(right))
    common = sum((lhs & rhs).values())
    return common / max(1, math.sqrt(sum(lhs.values()) * sum(rhs.values())))


semantic_similarity = lexical_cosine


def unique_ngram_coverage(output: str, source: str, n: int = 5) -> float:
    source_ngrams = ngrams(source, n)
    if not source_ngrams:
        return 0.0
    return len(source_ngrams & ngrams(output, n)) / len(source_ngrams)


def split_structure(content: str) -> list[tuple[str, str]]:
    """Split labelled educational content without losing its section type."""
    labels = ["title", "section", "question", "answer", "explanation", "problem", "reference"]
    matches = list(re.finditer(r"(?i)(title|section|question|answer|explanation|problem|reference)\s*:", content))
    if not matches:
        return [("body", content.strip())]
    result: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        value = content[start:end].strip(" \n\t;|")
        if value:
            result.append((match.group(1).lower(), value))
    return result or [("body", content.strip())]


def objective_knowledge_units(content: str, topic: str, difficulty: str) -> tuple[str, ...]:
    """Extract evaluator units already present in the resource; no LLM labels."""
    units = [topic, difficulty]
    answer = re.search(r"(?i)reference answer\s*:\s*([^.;\n]+)", content)
    if answer:
        units.append(answer.group(1).strip())
    solution = re.search(r"(?i)solution sketch\s*:\s*([^.!?]{8,100})", content)
    if solution:
        phrase = " ".join(solution.group(1).strip().split()[:10])
        if phrase:
            units.append(phrase)
    if len(units) <= 2:
        # Synthetic restricted resources are prose rather than labelled
        # Problem/Answer records. Use their own comma-separated teaching steps
        # as objective units instead of inventing semantic labels.
        tail = content.split(":", 1)[-1]
        clauses = re.split(r",|;|\band\b", tail, flags=re.IGNORECASE)
        for clause in clauses:
            phrase = " ".join(clause.strip(" .").split()[:10])
            if 3 <= len(phrase.split()) <= 10:
                units.append(phrase)
            if len(units) >= 7:
                break
    return tuple(dict.fromkeys(unit for unit in units if unit))


@dataclass(frozen=True)
class ResourceDocument:
    document_id: str
    parent_id: str
    section_id: str
    text: str
    title: str
    owner: str
    license: str
    copyright_level: float
    allowed_roles: tuple[str, ...]
    allowed_use: tuple[str, ...]
    source_hash: str
    source_family: str
    semantic_topic: str
    knowledge_units: tuple[str, ...] = ()

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ResourceDocument":
        rights = row.get("rights_metadata") or {}
        access = row.get("access_policy") or {}
        provenance = row.get("provenance") or {}
        content = str(row.get("content", ""))
        return cls(
            document_id=str(row.get("resource_id", row.get("chunk_id", ""))),
            parent_id=str(row.get("resource_id", "")),
            section_id=str(row.get("chunk_id", "")),
            text=content,
            title=str(row.get("knowledge", "")),
            owner=str(rights.get("rights_holder", "unknown")),
            license=str(rights.get("license_id", rights.get("license_name", "unknown"))),
            copyright_level=float(row.get("copyright_level", 0.0)),
            allowed_roles=tuple(str(x) for x in access.get("allowed_roles", ["teacher"])),
            allowed_use=tuple(str(x) for x in access.get("allowed_purposes", ["tutoring"])),
            source_hash=str(provenance.get("source_hash", stable_hash(content))),
            source_family=str(row.get("source_family_id", provenance.get("source_id", "unknown"))),
            semantic_topic=str(row.get("knowledge", "unknown")),
            knowledge_units=objective_knowledge_units(content, str(row.get("knowledge", "")), str(row.get("difficulty", ""))),
        )


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    parent_id: str
    section_id: str
    section_type: str
    text: str
    owner: str
    license: str
    copyright_level: float
    allowed_roles: tuple[str, ...]
    allowed_use: tuple[str, ...]
    source_hash: str
    source_family: str
    semantic_topic: str
    knowledge_units: tuple[str, ...]


class StructureAwareChunker:
    def __init__(self, max_tokens: int = 96, overlap: int = 12) -> None:
        self.max_tokens = max_tokens
        self.overlap = overlap

    def chunk(self, document: ResourceDocument) -> list[Chunk]:
        output: list[Chunk] = []
        for section_index, (section_type, section) in enumerate(split_structure(document.text)):
            words = section.split()
            if not words:
                continue
            stride = max(1, self.max_tokens - self.overlap)
            for start in range(0, len(words), stride):
                value = " ".join(words[start : start + self.max_tokens]).strip()
                if not value:
                    continue
                chunk_id = f"{document.document_id}:{section_type}:{section_index}:{start}"
                output.append(Chunk(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    parent_id=document.parent_id,
                    section_id=document.section_id,
                    section_type=section_type,
                    text=value,
                    owner=document.owner,
                    license=document.license,
                    copyright_level=document.copyright_level,
                    allowed_roles=document.allowed_roles,
                    allowed_use=document.allowed_use,
                    source_hash=document.source_hash,
                    source_family=document.source_family,
                    semantic_topic=document.semantic_topic,
                    knowledge_units=document.knowledge_units,
                ))
                if start + self.max_tokens >= len(words):
                    break
        return output


class BM25Index:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.term_freqs = [Counter(tokens(c.text)) for c in chunks]
        self.doc_freq = Counter()
        for tf in self.term_freqs:
            self.doc_freq.update(tf.keys())
        self.avg_len = sum(sum(tf.values()) for tf in self.term_freqs) / max(1, len(chunks))

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        query_terms = set(tokens(query))
        scores: list[tuple[int, float]] = []
        n_docs = len(self.chunks)
        for index, tf in enumerate(self.term_freqs):
            length = sum(tf.values()) or 1
            score = 0.0
            for term in query_terms:
                if term not in tf:
                    continue
                idf = math.log(1 + (n_docs - self.doc_freq[term] + 0.5) / (self.doc_freq[term] + 0.5))
                score += idf * (tf[term] * 2.0) / (tf[term] + 1.5 * (0.25 + 0.75 * length / max(1, self.avg_len)))
            scores.append((index, score))
        return sorted(scores, key=lambda item: (-item[1], self.chunks[item[0]].chunk_id))[:k]


class DenseEmbeddingIndex:
    """Dense index with a real transformer encoder and explicit pilot fallback."""

    def __init__(
        self,
        chunks: list[Chunk],
        dimensions: int = 384,
        backend: str = "auto",
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        model_revision: str = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
        model_path: str | None = None,
        device: str = "auto",
    ) -> None:
        if HashingVectorizer is None or np is None:
            raise RuntimeError("scikit-learn and numpy are required for the dense index")
        self.chunks = chunks
        self.backend_requested = backend
        self.model_name = model_name
        self.model_revision = model_revision
        self.model_path = model_path
        self.device = self._resolve_device(device)
        self.encoder_name = "sklearn_hashing_dense_fallback"
        self.dimensions = dimensions
        self.is_fallback = True
        self.failure_reason = ""
        self.vectorizer = None
        self.tokenizer = None
        self.model = None
        if backend in {"auto", "neural"}:
            try:
                self._load_neural()
            except Exception as exc:  # noqa: BLE001 - status is recorded in the manifest
                self.failure_reason = f"{type(exc).__name__}: {exc}"
                if backend == "neural":
                    raise RuntimeError(f"neural dense encoder unavailable: {self.failure_reason}") from exc
        if self.is_fallback:
            self.vectorizer = HashingVectorizer(n_features=dimensions, alternate_sign=False, norm="l2", ngram_range=(1, 2))
            self.matrix = self.vectorizer.transform([c.text for c in chunks]).toarray()
        else:
            self.matrix = self._encode([c.text for c in chunks])

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device != "auto":
            return device
        return "cuda" if torch is not None and torch.cuda.is_available() else "cpu"

    def _load_neural(self) -> None:
        if torch is None or AutoTokenizer is None or AutoModel is None:
            raise RuntimeError("transformers and torch are required")
        source = self.model_path or self.model_name
        cache_key = (source, self.model_revision, self.device)
        if cache_key not in _NEURAL_MODEL_CACHE:
            tokenizer = AutoTokenizer.from_pretrained(source, revision=self.model_revision, local_files_only=bool(self.model_path))
            model = AutoModel.from_pretrained(source, revision=self.model_revision, local_files_only=bool(self.model_path))
            model.to(self.device)
            model.eval()
            _NEURAL_MODEL_CACHE[cache_key] = (tokenizer, model)
        self.tokenizer, self.model = _NEURAL_MODEL_CACHE[cache_key]
        self.encoder_name = self.model_name
        self.is_fallback = False
        self.dimensions = int(getattr(self.model.config, "hidden_size", self.dimensions))

    def _encode(self, texts: list[str]) -> np.ndarray:
        if self.is_fallback:
            return self.vectorizer.transform(texts).toarray()
        batches = []
        for start in range(0, len(texts), 32):
            encoded = self.tokenizer(texts[start : start + 32], padding=True, truncation=True, max_length=256, return_tensors="pt")
            encoded = {key: value.to(self.device) for key, value in encoded.items()}
            with torch.inference_mode():
                hidden = self.model(**encoded).last_hidden_state
                mask = encoded["attention_mask"].unsqueeze(-1)
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
                pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            batches.append(pooled.cpu().numpy())
        return np.concatenate(batches, axis=0) if batches else np.empty((0, self.dimensions))

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        if self.is_fallback:
            q = self.vectorizer.transform([query]).toarray()[0]
        else:
            cache_key = (self.model_name, self.model_revision, query)
            if cache_key not in _NEURAL_QUERY_CACHE:
                _NEURAL_QUERY_CACHE[cache_key] = self._encode([query])[0]
            q = _NEURAL_QUERY_CACHE[cache_key]
        scores = self.matrix @ q
        order = sorted(range(len(scores)), key=lambda index: (-float(scores[index]), self.chunks[index].chunk_id))
        return [(index, float(scores[index])) for index in order[:k]]

    def late_interaction_score(self, query: str, chunk: Chunk) -> float:
        """Token-level MaxSim score for the late-interaction pilot.

        This follows the scoring idea of ColBERT-style retrieval while reusing
        the locked encoder already present in the repository. It is recorded as
        a pilot variant, not as an official ColBERT reproduction.
        """
        if self.is_fallback or self.tokenizer is None or self.model is None:
            query_terms, chunk_terms = set(tokens(query)), set(tokens(chunk.text))
            return len(query_terms & chunk_terms) / max(1, len(query_terms))
        def token_encode(text: str) -> tuple[Any, int]:
            cache_key = (self.model_name, self.model_revision, text)
            if cache_key in _NEURAL_TOKEN_CACHE:
                return _NEURAL_TOKEN_CACHE[cache_key]
            encoded = self.tokenizer(text, truncation=True, max_length=256, return_tensors="pt")
            encoded = {key: value.to(self.device) for key, value in encoded.items()}
            with torch.inference_mode():
                vector = torch.nn.functional.normalize(self.model(**encoded).last_hidden_state[0], p=2, dim=-1)
            length = int(encoded["attention_mask"][0].sum().item())
            _NEURAL_TOKEN_CACHE[cache_key] = (vector, length)
            return vector, length

        query_hidden, query_len = token_encode(query)
        doc_hidden, doc_len = token_encode(chunk.text)
        if query_len == 0 or doc_len == 0:
            return 0.0
        token_scores = query_hidden[:query_len] @ doc_hidden[:doc_len].transpose(0, 1)
        return float(token_scores.max(dim=1).values.mean().cpu())


class CrossEncoderReranker:
    """Cross-encoder interface with an explicit unavailable fallback."""

    def __init__(
        self,
        backend: str = "auto",
        model_name: str = "cross-encoder/ms-marco-TinyBERT-L-2-v2",
        model_revision: str = "81d1926f67cb8eee2c2be17ca9f793c7c3bd20cc",
        model_path: str | None = None,
        device: str = "auto",
    ) -> None:
        self.backend_requested = backend
        self.model_name = model_name
        self.model_revision = model_revision
        self.model_path = model_path
        self.device = DenseEmbeddingIndex._resolve_device(device)
        self.name = "deterministic_token_cross_encoder_fallback"
        self.is_fallback = True
        self.failure_reason = ""
        self.tokenizer = None
        self.model = None
        if backend in {"auto", "neural"}:
            try:
                self._load_neural()
            except Exception as exc:  # noqa: BLE001 - status is recorded in the manifest
                self.failure_reason = f"{type(exc).__name__}: {exc}"
                if backend == "neural":
                    raise RuntimeError(f"neural cross-encoder unavailable: {self.failure_reason}") from exc

    def _load_neural(self) -> None:
        if torch is None or AutoTokenizer is None or AutoModelForSequenceClassification is None:
            raise RuntimeError("transformers and torch are required")
        source = self.model_path or self.model_name
        cache_key = (source, self.model_revision, self.device)
        if cache_key not in _NEURAL_MODEL_CACHE:
            tokenizer = AutoTokenizer.from_pretrained(source, revision=self.model_revision, local_files_only=bool(self.model_path))
            model = AutoModelForSequenceClassification.from_pretrained(source, revision=self.model_revision, local_files_only=bool(self.model_path))
            model.to(self.device)
            model.eval()
            _NEURAL_MODEL_CACHE[cache_key] = (tokenizer, model)
        self.tokenizer, self.model = _NEURAL_MODEL_CACHE[cache_key]
        self.name = self.model_name
        self.is_fallback = False

    def score(self, query: str, chunk: Chunk) -> float:
        if not self.is_fallback:
            encoded = self.tokenizer(query, chunk.text, truncation=True, max_length=256, return_tensors="pt")
            encoded = {key: value.to(self.device) for key, value in encoded.items()}
            with torch.inference_mode():
                logits = self.model(**encoded).logits
            return float(logits.reshape(-1)[0].cpu())
        query_terms, chunk_terms = set(tokens(query)), set(tokens(chunk.text))
        overlap = len(query_terms & chunk_terms) / max(1, len(query_terms))
        topic = float(chunk.semantic_topic.lower() in query.lower())
        return 0.8 * overlap + 0.2 * topic


class MetadataAuthorizer:
    def filter(self, chunks: Iterable[Chunk], role: str, purpose: str) -> list[Chunk]:
        return [chunk for chunk in chunks if purpose in chunk.allowed_use and role in chunk.allowed_roles]


@dataclass
class ExposureState:
    session_cost: float = 0.0
    released_spans: set[str] = field(default_factory=set)
    released_ngrams: set[tuple[str, ...]] = field(default_factory=set)
    knowledge_units: set[str] = field(default_factory=set)
    adjacent_chunks: set[str] = field(default_factory=set)
    round_outputs: list[str] = field(default_factory=list)
    query_count: int = 0


@dataclass
class C2RAGConfig:
    candidate_k: int = 12
    rerank_k: int = 6
    top_k: int = 3
    context_token_budget: int = 180
    total_copyright_budget: float = 2.0
    max_quote_tokens: int = 24
    max_excerpt_tokens: int = 48
    ngram_size: int = 5
    semantic_reconstruction_threshold: float = 0.82
    lexical_reconstruction_threshold: float = 0.45
    chunk_size: int = 96
    chunk_overlap: int = 12
    retrieval_backend: str = "fallback"
    dense_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    dense_model_revision: str = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    dense_model_path: str | None = None
    reranker_backend: str = "fallback"
    reranker_model_name: str = "cross-encoder/ms-marco-TinyBERT-L-2-v2"
    reranker_model_revision: str = "81d1926f67cb8eee2c2be17ca9f793c7c3bd20cc"
    reranker_model_path: str | None = None
    model_device: str = "auto"
    reranking_similarity_threshold: float = -10.0
    generator_backend: str = "fallback"
    generator_model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"
    generator_model_revision: str = "7ae557604adf67be50417f59c2c2f167def9a775"
    generator_model_path: str | None = None
    generator_max_new_tokens: int = 96
    generator_seed: int = 20260827
    retrieval_variant: str = "hybrid_rrf"
    evidence_renderer: str = "legacy_math"


@dataclass
class C2RAGResult:
    session_id: str
    round_id: int
    method: str
    query: str
    selected_chunks: list[dict[str, Any]]
    planned_action: dict[str, Any]
    executed_action: str
    mismatch_reason: str
    allowed_evidence: str
    generated_answer: str
    released_answer: str
    actual_disclosure: dict[str, float]
    estimated_cost: float
    actual_cost: float
    committed_cost: float
    plan_execution_match: bool
    refusal: bool
    timings_ms: dict[str, float]
    target_resource_id: str = ""
    principal_id: str = ""
    cross_session_linked: bool = False
    session_cost_before: float = 0.0
    session_cost_after: float = 0.0
    cross_session_cost_before: float = 0.0
    cross_session_cost_after: float = 0.0
    remaining_budget: float = 0.0
    generation_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def copyright_risk_evidence(*, query: str, state: ExposureState, current_measure: dict[str, float], current_cost: float, budget: float, method: str) -> dict[str, Any]:
    """Expose copyright-domain evidence and candidates; CG owns the final decision."""
    query_lower = query.lower()
    verbatim = int(any(token in query_lower for token in ("exact", "verbatim", "原文", "逐字", "完整")))
    continuation = int(any(token in query_lower for token in ("next", "continue", "下一段", "继续", "补全", "fragment")))
    reconstruction = int(any(token in query_lower for token in ("combine", "recover", "reconstruct", "还原", "拼接", "恢复")))
    cumulative = min(1.0, float(state.session_cost) / max(budget, 1e-9))
    risk = min(1.0, 0.30 * verbatim + 0.20 * continuation + 0.20 * reconstruction + 0.20 * cumulative + 0.10 * float(current_measure.get("lexical_cosine", 0.0)))
    if risk >= 0.75:
        candidates = ["refuse", "minimal_hint", "generated_variant"]
    elif risk >= 0.45:
        candidates = ["generated_variant", "concept_only", "abstractive_summary", "refuse"]
    else:
        candidates = ["abstractive_summary", "concept_only", "generated_variant", "controlled_quote"]
    return {
        "schema": "c2rag.copyright_risk_evidence.v1", "method": method,
        "verbatim_request_risk": verbatim, "fragment_stitching_risk": continuation,
        "semantic_reconstruction_risk": reconstruction, "current_round_cost": float(current_cost),
        "cumulative_cost": float(state.session_cost), "remaining_budget": max(0.0, budget - state.session_cost),
        "cumulative_exposure": cumulative, "current_lcs_coverage": float(current_measure.get("lcs_coverage", 0.0)),
        "current_ngram_coverage": float(current_measure.get("ngram_coverage", 0.0)),
        "current_semantic_similarity": float(current_measure.get("lexical_cosine", 0.0)),
        "released_knowledge_unit_recovery": float(current_measure.get("key_knowledge_unit_recovery", 0.0)),
        "copyright_risk_score": risk, "candidate_actions": candidates, "domain_decision_owner": "C2-RAG",
    }


def disclosure_measurement(output: str, source: str, knowledge_units: Iterable[str], n: int = 5) -> dict[str, float]:
    return {
        "lcs_coverage": lcs_ratio(output, source),
        "ngram_coverage": unique_ngram_coverage(output, source, n),
        "lexical_cosine": lexical_cosine(output, source),
        "key_knowledge_unit_recovery": sum(1 for unit in knowledge_units if unit and unit.lower() in output.lower()) / max(1, len(tuple(knowledge_units))),
    }


class C2RAGV3:
    def __init__(self, resources: list[ResourceDocument], config: C2RAGConfig | None = None) -> None:
        self.config = config or C2RAGConfig()
        self.chunks = [chunk for resource in resources for chunk in StructureAwareChunker(self.config.chunk_size, self.config.chunk_overlap).chunk(resource)]
        self.bm25 = BM25Index(self.chunks)
        self.dense = DenseEmbeddingIndex(
            self.chunks,
            backend=self.config.retrieval_backend,
            model_name=self.config.dense_model_name,
            model_revision=self.config.dense_model_revision,
            model_path=self.config.dense_model_path,
            device=self.config.model_device,
        )
        self.reranker = CrossEncoderReranker(
            backend=self.config.reranker_backend,
            model_name=self.config.reranker_model_name,
            model_revision=self.config.reranker_model_revision,
            model_path=self.config.reranker_model_path,
            device=self.config.model_device,
        )
        self.generator = TeachingGenerator(
            backend=self.config.generator_backend,
            model_name=self.config.generator_model_name,
            model_revision=self.config.generator_model_revision,
            model_path=self.config.generator_model_path,
            device=self.config.model_device,
            max_new_tokens=self.config.generator_max_new_tokens,
            seed=self.config.generator_seed,
        )
        self.authorizer = MetadataAuthorizer()
        self.states: dict[tuple[str, str, str, str, str], ExposureState] = defaultdict(ExposureState)
        self.cross_session_total: dict[tuple[str, str], float] = defaultdict(float)

    def mechanism_snapshot(self, method: str) -> dict[str, bool]:
        return {
            "bm25_enabled": True,
            "dense_embedding_enabled": True,
            "rrf_enabled": True,
            "cross_encoder_reranker_enabled": True,
            "metadata_authorization_enabled": method not in {"advanced_rag_no_defense"},
            "provenance_enabled": method not in {"c2rag_without_provenance", "advanced_rag_no_defense"},
            "cumulative_budget_enabled": method not in {"c2rag_without_cumulative_budget", "advanced_rag_no_defense"},
            "reconstruction_history_enabled": method not in {"c2rag_without_reconstruction_history", "advanced_rag_no_defense"},
            "actual_output_accounting_enabled": True,
            "modern_rag_base_enabled": True,
            "late_interaction_enabled": method == "late_interaction_c2rag" or self.config.retrieval_variant == "late_interaction",
        }

    def _retrieve(self, query: str, role: str, purpose: str, method: str, target_resource_id: str | None = None) -> tuple[list[Chunk], dict[str, Any]]:
        if method == "advanced_rag_no_defense":
            visible = list(self.chunks)
        elif method == "c2rag_without_provenance":
            visible = [chunk for chunk in self.chunks if role in chunk.allowed_roles]
        else:
            visible = self.authorizer.filter(self.chunks, role, purpose)
        if target_resource_id:
            visible = [chunk for chunk in visible if chunk.document_id == target_resource_id]
        visible_ids = {chunk.chunk_id for chunk in visible}
        sparse = [(index, score) for index, score in self.bm25.search(query, len(self.chunks)) if self.chunks[index].chunk_id in visible_ids][: self.config.candidate_k]
        dense = [(index, score) for index, score in self.dense.search(query, len(self.chunks)) if self.chunks[index].chunk_id in visible_ids][: self.config.candidate_k]
        ranks: dict[int, float] = defaultdict(float)
        for rank, (index, _) in enumerate(sparse, start=1):
            ranks[index] += 1.0 / (60 + rank)
        for rank, (index, _) in enumerate(dense, start=1):
            ranks[index] += 1.0 / (60 + rank)
        candidates = sorted(ranks, key=lambda index: (-ranks[index], self.chunks[index].chunk_id))[: self.config.rerank_k]
        if method == "late_interaction_c2rag" or self.config.retrieval_variant == "late_interaction":
            rerank_scores = {index: self.dense.late_interaction_score(query, self.chunks[index]) for index in candidates}
            reranker_name = "locked-encoder-token-maxsim-pilot"
        else:
            rerank_scores = {index: self.reranker.score(query, self.chunks[index]) for index in candidates}
            reranker_name = self.reranker.name
        if method == "reranking_protection":
            filtered = [index for index in candidates if rerank_scores[index] >= self.config.reranking_similarity_threshold]
            # A target-scoped session may contain only one authorized document;
            # never turn a valid target into an empty retrieval solely because a
            # generic reranker score is below its global threshold.
            if not filtered and candidates:
                filtered = [max(candidates, key=lambda index: rerank_scores[index])]
            candidates = filtered
        ordered = sorted(candidates, key=lambda index: (-rerank_scores[index], self.chunks[index].chunk_id))[: self.config.top_k]
        return [self.chunks[index] for index in ordered], {
            "sparse_count": len(sparse),
            "dense_count": len(dense),
            "rrf_candidates": len(candidates),
            "reranker": reranker_name,
            "rerank_scores": {self.chunks[index].chunk_id: rerank_scores[index] for index in candidates},
            "target_resource_id": target_resource_id,
            "target_hit": bool(ordered and target_resource_id and self.chunks[ordered[0]].document_id == target_resource_id),
        }

    def _state(self, identity: str, session_id: str, chunk: Chunk) -> ExposureState:
        return self.states[(identity, session_id, chunk.document_id, chunk.source_family, chunk.semantic_topic)]

    def _render(self, chunk: Chunk, action: str) -> str:
        source_words = chunk.text.split()
        topic = chunk.semantic_topic
        difficulty = chunk.knowledge_units[1] if len(chunk.knowledge_units) > 1 else "unknown"
        answer = chunk.knowledge_units[2] if len(chunk.knowledge_units) > 2 else ""
        method = chunk.knowledge_units[3] if len(chunk.knowledge_units) > 3 else "identify conditions and verify the result"
        if action == "unrestricted_source":
            return chunk.text
        if action == "controlled_quote":
            return " ".join(source_words[: self.config.max_quote_tokens])
        if action == "minimal_excerpt":
            return " ".join(source_words[: self.config.max_excerpt_tokens])
        if action == "abstractive_summary":
            return f"结构化摘要：知识点={topic}；难度={difficulty}；方法提示={method}。不复述原题和参考答案。"
        if action == "concept_only":
            return f"概念提示：知识点={topic}。先识别条件关系，再独立选择方法并验算。"
        if action == "generated_variant":
            seed = int(stable_hash(chunk.chunk_id)[:4], 16) % 7 + 2
            return f"新例题：围绕{topic}，使用新参数{seed}和{seed + 3}设计同目标练习；难度={difficulty}。不沿用原题数字、措辞或答案。"
        if action == "minimal_hint":
            return f"最小提示：仅检查{topic}中的条件与目标是否对应。"
        return "当前资源不在允许的披露范围内。"

    def _candidate_package(self, chunk: Chunk) -> list[dict[str, Any]]:
        specs = (
            ("controlled_quote", 0.35, 0.55, True),
            ("abstractive_summary", 0.10, 0.22, True),
            ("generated_variant", 0.08, 0.12, True),
            ("concept_only", 0.05, 0.08, False),
            ("minimal_hint", 0.03, 0.04, False),
            ("refuse", 0.0, 0.0, False),
        )
        package = []
        for action, cost, residual, provenance_required in specs:
            content = "当前资源不在允许的披露范围内。" if action == "refuse" else self._render(chunk, action)
            package.append({"action": action, "content": content, "estimated_copyright_cost": cost, "residual_copyright_risk": residual, "provenance_required": provenance_required, "resource_id": chunk.document_id, "chunk_id": chunk.chunk_id})
        return package

    def _choose_action(self, chunk: Chunk, state: ExposureState, method: str) -> tuple[str, float]:
        if method == "advanced_rag_no_defense":
            return "unrestricted_source", 1.0
        if method == "summarization_protection":
            return "abstractive_summary", 0.10
        if method == "static_excerpt":
            return "minimal_excerpt", 0.25
        if method == "reranking_protection":
            return "controlled_quote", 0.35
        if method == "independent_ngram_guard":
            return ("concept_only", 0.08) if state.session_cost > 0.8 else ("minimal_excerpt", 0.25)
        if method == "semantic_similarity_guard":
            return "controlled_quote", 0.45
        if method == "crag_style_correction":
            # CRAG-style evaluator: low-confidence or repeated requests are
            # corrected to a safe concept/variant response instead of passing
            # the retrieved span through unchanged.
            if state.query_count > 0 or state.session_cost > 0.15:
                return "generated_variant", 0.08
            return "abstractive_summary", 0.10
        if method == "self_rag_style_reflection":
            # Self-RAG-style reflection gate: decide whether more source
            # evidence is justified before expanding the answer.
            if state.query_count > 0 or len(state.released_ngrams) >= 1:
                return "minimal_hint", 0.03
            return "abstractive_summary", 0.10
        if method == "adaptive_rag_risk_router":
            # Adaptive-RAG-style router: progressively stricter response modes
            # as the session accumulates disclosure risk.
            if state.session_cost >= 0.20 or state.query_count >= 2:
                return "refuse", 0.0
            if state.query_count >= 1:
                return "concept_only", 0.05
            return "abstractive_summary", 0.10
        if method == "c2rag_without_provenance":
            if chunk.copyright_level < 0.7:
                return "minimal_excerpt", 0.30
        if state.query_count >= 2 or len(state.released_ngrams) >= 2:
            return "minimal_hint", 0.08
        if chunk.copyright_level >= 0.7:
            return ("abstractive_summary", 0.25) if state.query_count == 0 else ("generated_variant", 0.15)
        if state.session_cost >= self.config.total_copyright_budget:
            return "refuse", 0.0
        return "abstractive_summary", 0.10

    def run_round(self, *, session_id: str, round_id: int, identity: str, query: str, role: str = "teacher", purpose: str = "tutoring", method: str = "full_c2rag_v3", target_resource_id: str | None = None, principal_id: str | None = None, cross_session_linked: bool = False) -> C2RAGResult:
        timings: dict[str, float] = {}
        started = time.perf_counter()
        principal = principal_id or identity
        retrieve_start = time.perf_counter()
        selected, retrieval_trace = self._retrieve(query, role, purpose, method, target_resource_id)
        timings["retrieval_ms"] = (time.perf_counter() - retrieve_start) * 1000
        if not selected:
            return C2RAGResult(session_id, round_id, method, query, [], {"action": "refuse"}, "refuse", "no_authorized_candidate", "", "", "", {"lcs_coverage": 0.0, "ngram_coverage": 0.0, "lexical_cosine": 0.0, "key_knowledge_unit_recovery": 0.0}, 0.0, 0.0, 0.0, True, True, {**timings, "total_ms": (time.perf_counter() - started) * 1000}, target_resource_id or "", principal, cross_session_linked)
        chunk = selected[0]
        state = self._state(principal, session_id, chunk)
        decision_state = ExposureState() if method == "c2rag_without_reconstruction_history" else state
        action, estimated = self._choose_action(chunk, decision_state, "full_c2rag_v3" if method == "full_c2rag_v3+cg" else method)
        candidate_package = self._candidate_package(chunk)
        copyright_selection = None
        if method in {"full_c2rag_v3", "full_c2rag_v3+cg", "late_interaction_c2rag"} and self.config.evidence_renderer == "legacy_math":
            from .policy_selector import select_copyright_candidate
            prior_evidence = copyright_risk_evidence(query=query, state=state, current_measure={}, current_cost=0.0, budget=self.config.total_copyright_budget, method=method)
            prior_evidence["provenance_valid"] = chunk.license not in {"", "unknown", "unverified"}
            copyright_selection = select_copyright_candidate(candidate_package, prior_evidence)
            action = copyright_selection.action
            estimated = next(item["estimated_copyright_cost"] for item in candidate_package if item["action"] == copyright_selection.action)
        if chunk.license in {"", "unknown", "unverified"} and method not in {"advanced_rag_no_defense", "c2rag_without_provenance"}:
            action, estimated = "refuse", 0.0
        planned_action = action
        session_before = state.session_cost
        cross_before = self.cross_session_total[(principal, chunk.source_family)] if cross_session_linked and method not in {"advanced_rag_no_defense", "c2rag_without_cumulative_budget"} else 0.0
        ledger_before = cross_before if cross_session_linked else session_before
        allowed = self._render(chunk, action)
        if self.config.evidence_renderer == "query_bounded" and method != "advanced_rag_no_defense":
            from .evidence_release import plan_excerpt
            remaining = self.config.total_copyright_budget
            if method != "c2rag_without_cumulative_budget":
                remaining = max(0., remaining - ledger_before)
            proposal = plan_excerpt(query, chunk, remaining, self.config.ngram_size, self.config.max_quote_tokens)
            if chunk.license in {"", "unknown", "unverified"} and method != "c2rag_without_provenance":
                proposal = {"action": "refuse", "content": "", "estimated_copyright_cost": 0.}
            action = planned_action = proposal["action"]
            allowed = proposal["content"]
            estimated = proposal["estimated_copyright_cost"]
            candidate_package = [proposal]
        projected_measure = disclosure_measurement(f"教学回答：{allowed}", chunk.text, chunk.knowledge_units, self.config.ngram_size)
        projected_cost = min(1.0, 0.45 * projected_measure["lcs_coverage"] + 0.25 * projected_measure["ngram_coverage"] + 0.20 * projected_measure["lexical_cosine"] + 0.10 * projected_measure["key_knowledge_unit_recovery"])
        estimated = max(float(estimated), projected_cost)
        planned = {"action": planned_action, "max_cost": estimated, "allowed_chunk_id": chunk.chunk_id, "allowed_source_family": chunk.source_family, "target_resource_id": target_resource_id or chunk.document_id, "budget_before": ledger_before, "budget_limit": self.config.total_copyright_budget}
        gen_start = time.perf_counter()
        generation = self.generator.generate(query, allowed, action, chunk.semantic_topic)
        generated = f"教学回答：{generation.text}" if generation.text else ""
        timings["generation_ms"] = (time.perf_counter() - gen_start) * 1000
        released = generated
        actual_measure = disclosure_measurement(released, chunk.text, chunk.knowledge_units, self.config.ngram_size)
        actual = min(1.0, 0.45 * actual_measure["lcs_coverage"] + 0.25 * actual_measure["ngram_coverage"] + 0.20 * actual_measure["lexical_cosine"] + 0.10 * actual_measure["key_knowledge_unit_recovery"])
        executed_action = action
        mismatch_reason = ""
        if method == "independent_ngram_guard" and actual_measure["ngram_coverage"] > 0.30:
            executed_action = "concept_only"
            mismatch_reason = "independent_overlap_guard"
            generation = self.generator.generate(query, self._render(chunk, "concept_only"), "concept_only", chunk.semantic_topic)
            released = f"教学回答：{generation.text}"
            actual_measure = disclosure_measurement(released, chunk.text, chunk.knowledge_units, self.config.ngram_size)
            actual = min(1.0, 0.45 * actual_measure["lcs_coverage"] + 0.25 * actual_measure["ngram_coverage"] + 0.20 * actual_measure["lexical_cosine"] + 0.10 * actual_measure["key_knowledge_unit_recovery"])
        if method == "semantic_similarity_guard" and actual_measure["lexical_cosine"] > 0.45:
            executed_action = "concept_only"
            mismatch_reason = "independent_semantic_similarity_guard"
            generation = self.generator.generate(query, self._render(chunk, "concept_only"), "concept_only", chunk.semantic_topic)
            released = f"教学回答：{generation.text}"
            actual_measure = disclosure_measurement(released, chunk.text, chunk.knowledge_units, self.config.ngram_size)
            actual = min(1.0, 0.45 * actual_measure["lcs_coverage"] + 0.25 * actual_measure["ngram_coverage"] + 0.20 * actual_measure["lexical_cosine"] + 0.10 * actual_measure["key_knowledge_unit_recovery"])
        if action == "refuse":
            released, generated, actual = "当前资源不在允许的披露范围内。", "", 0.0
        if cross_session_linked and method not in {"advanced_rag_no_defense", "c2rag_without_cumulative_budget"} and cross_before + actual > self.config.total_copyright_budget:
            executed_action = "refuse"
            mismatch_reason = "actual_cost_exceeded_remaining_budget"
            released = "当前累计版权预算不足，无法继续提供该资源细节。"
            actual = 0.0
            actual_measure = disclosure_measurement(released, chunk.text, chunk.knowledge_units, self.config.ngram_size)
        elif not cross_session_linked and method not in {"advanced_rag_no_defense", "c2rag_without_cumulative_budget"} and session_before + actual > self.config.total_copyright_budget:
            executed_action = "refuse"
            mismatch_reason = "actual_cost_exceeded_remaining_budget"
            released = "当前累计版权预算不足，无法继续提供该资源细节。"
            actual = 0.0
            actual_measure = disclosure_measurement(released, chunk.text, chunk.knowledge_units, self.config.ngram_size)
        match = executed_action == planned_action and actual <= float(planned["max_cost"]) + 1e-9
        if not match and executed_action != "refuse":
            executed_action = "concept_only"
            mismatch_reason = "projected_cost_underestimated_actual_disclosure"
            generation = self.generator.generate(query, self._render(chunk, "concept_only"), "concept_only", chunk.semantic_topic)
            released = f"教学回答：{generation.text}"
            actual_measure = disclosure_measurement(released, chunk.text, chunk.knowledge_units, self.config.ngram_size)
            actual = min(1.0, 0.45 * actual_measure["lcs_coverage"] + 0.25 * actual_measure["ngram_coverage"] + 0.20 * actual_measure["lexical_cosine"] + 0.10 * actual_measure["key_knowledge_unit_recovery"])
            match = executed_action == planned_action and actual <= float(planned["max_cost"]) + 1e-9
        if method != "advanced_rag_no_defense":
            state.session_cost += actual
            state.round_outputs.append(released)
            state.query_count += 1
            state.released_ngrams.update(ngrams(released, self.config.ngram_size))
            state.knowledge_units.update(unit for unit in chunk.knowledge_units if unit.lower() in released.lower())
            state.adjacent_chunks.add(chunk.chunk_id)
            if cross_session_linked and method != "c2rag_without_cumulative_budget":
                self.cross_session_total[(principal, chunk.source_family)] += actual
        current_measure = {**actual_measure, "composite_cost": actual}
        risk_evidence = copyright_risk_evidence(query=query, state=state, current_measure=current_measure, current_cost=actual, budget=self.config.total_copyright_budget, method=method)
        risk_evidence["candidate_plans"] = candidate_package
        if copyright_selection is not None:
            risk_evidence["copyright_selection"] = {"action": copyright_selection.action, "reason": copyright_selection.reason, "score": copyright_selection.score, "evaluated_candidates": copyright_selection.evaluated}
        timings["posthoc_measurement_ms"] = 0.0
        timings["total_ms"] = (time.perf_counter() - started) * 1000
        session_after = state.session_cost
        cross_after = self.cross_session_total[(principal, chunk.source_family)] if cross_session_linked and method != "c2rag_without_cumulative_budget" else cross_before
        remaining = self.config.total_copyright_budget - (cross_after if cross_session_linked else session_after)
        return C2RAGResult(
            session_id=session_id, round_id=round_id, method=method, query=query,
            selected_chunks=[{"chunk_id": item.chunk_id, "document_id": item.document_id, "source_family": item.source_family, "copyright_level": item.copyright_level, "rrf": retrieval_trace["rerank_scores"].get(item.chunk_id, 0.0)} for item in selected],
            planned_action=planned, executed_action=executed_action, mismatch_reason=mismatch_reason, allowed_evidence=allowed, generated_answer=generated, released_answer=released,
            actual_disclosure={**current_measure, "copyright_risk_evidence": risk_evidence}, estimated_cost=float(planned["max_cost"]), actual_cost=actual, committed_cost=actual,
            plan_execution_match=match, refusal=executed_action == "refuse", timings_ms=timings,
            target_resource_id=target_resource_id or chunk.document_id, principal_id=principal, cross_session_linked=cross_session_linked,
            session_cost_before=session_before, session_cost_after=session_after, cross_session_cost_before=cross_before, cross_session_cost_after=cross_after,
            remaining_budget=remaining, generation_calls=generation.calls, input_tokens=generation.input_tokens, output_tokens=generation.output_tokens,
        )

    def reset_session(self, session_id: str, identity: str) -> None:
        for key in list(self.states):
            if key[0] == identity and key[1] == session_id:
                del self.states[key]

    def retrieval_manifest(self) -> dict[str, Any]:
        return {
            "dense": {
                "requested_backend": self.dense.backend_requested,
                "encoder": self.dense.encoder_name,
                "model_name": self.dense.model_name,
                "revision": self.dense.model_revision,
                "path": self.dense.model_path,
                "dimensions": self.dense.dimensions,
                "device": self.dense.device,
                "fallback": self.dense.is_fallback,
                "failure_reason": self.dense.failure_reason,
            },
            "reranker": {
                "requested_backend": self.reranker.backend_requested,
                "encoder": self.reranker.name,
                "model_name": self.reranker.model_name,
                "revision": self.reranker.model_revision,
                "path": self.reranker.model_path,
                "device": self.reranker.device,
                "fallback": self.reranker.is_fallback,
                "failure_reason": self.reranker.failure_reason,
            },
        }
