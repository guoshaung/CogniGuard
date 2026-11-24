"""Gate W0 F4/F5 supplement (PREREG_GATEW0_F45.md). Frozen w0.py / run.py are not edited.

F4_bge and F5_bge_rerank reuse the frozen control and attribution loops unchanged: the
worker swaps `w0.Index` for a dense index whose `bm25()` lookup is the dense method, then
runs the frozen code path for "F3_bm25". Every other line of the simulation is identical.
"""

from __future__ import annotations

import numpy as np

from experiments.capd_gatew0_20261124 import w0

EMBED_MODEL, EMBED_REV = "BAAI/bge-small-en-v1.5", "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
RERANK_MODEL, RERANK_REV = "BAAI/bge-reranker-base", "2cfc18c9415c912f9d8155881c133215df768a70"
TOP_N = 10
TIE = 1e-6

_models = {}
_emb_cache: dict[str, np.ndarray] = {}
_pair_cache: dict[tuple[str, str], float] = {}


def _embedder():
    if "e" not in _models:
        from sentence_transformers import SentenceTransformer
        _models["e"] = SentenceTransformer(EMBED_MODEL, revision=EMBED_REV, device="cpu")
    return _models["e"]


def _reranker():
    if "r" not in _models:
        from sentence_transformers import CrossEncoder
        _models["r"] = CrossEncoder(RERANK_MODEL, revision=RERANK_REV, device="cpu")
    return _models["r"]


def embed(texts):
    todo = [t for t in dict.fromkeys(texts) if t not in _emb_cache]
    if todo:
        vecs = _embedder().encode(todo, normalize_embeddings=True, batch_size=64)
        for t, v in zip(todo, vecs):
            _emb_cache[t] = np.asarray(v, dtype=np.float32)
    return np.stack([_emb_cache[t] for t in texts])


def rerank(query, docs):
    todo = [d for d in docs if (query, d) not in _pair_cache]
    if todo:
        import torch
        # Raw logits (sentence-transformers applies a sigmoid by default), then one sigmoid.
        logits = _reranker().predict([(query, d) for d in todo], activation_fn=torch.nn.Identity(),
                                     batch_size=32)
        for d, s in zip(todo, np.atleast_1d(logits)):
            _pair_cache[(query, d)] = float(1 / (1 + np.exp(-float(s))))
    return np.array([_pair_cache[(query, d)] for d in docs])


def dense_scores(query, texts):
    """method -> (scores aligned with the returned texts). F5 scores only the F4 top-N."""
    sims = embed(texts) @ embed([query])[0]
    if MODE["method"] == "F4_bge":
        return texts, sims
    order = np.argsort(-sims, kind="stable")[:TOP_N]
    top = [texts[i] for i in order]
    return top, rerank(query, top)


MODE = {"method": "F4_bge", "threshold": None, "null": None}


class DenseIndex(w0.Index):
    """Same server-side index; `bm25()` is replaced by the dense lookup for this run."""

    def bm25(self, q, *args, **kwargs):  # noqa: D401 - frozen call site name
        texts = list(self.docs)
        if MODE["null"] is not None:
            texts = MODE["null"](q, self.docs)
        if not texts:
            return set()
        cand, scores = dense_scores(q, texts)
        best = float(np.max(scores))
        if MODE["null_scores"] is not None:
            MODE["null_scores"].append(best)
            return set()
        if best < MODE["threshold"]:
            return set()
        top = [t for t, s in zip(cand, scores) if best - float(s) < TIE]
        return set().union(*(self.docs[t] for t in top))


def install(method, threshold=None, null=None, null_scores=None):
    MODE.update(method=method, threshold=threshold, null=null, null_scores=null_scores)
    w0.Index = DenseIndex
