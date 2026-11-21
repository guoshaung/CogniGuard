# C²-RAG V3 Architecture

## Boundary

C²-RAG V3 只负责教师资源版权支路：检索、来源授权、局部返回策略、版权累计暴露和多轮重构控制。隐私、输出保护和跨域统一状态仍归 CG/对应模块负责，不在 C²-RAG V3 内复制。

## Execution flow

`query -> metadata authorization filter -> structure-aware chunks -> BM25 + dense retrieval -> reciprocal rank fusion -> cross-encoder rerank -> source diversity/context budget selection -> policy plan -> allowed evidence -> generation -> actual disclosure measurement -> deterministic enforcement -> commit`

实现位于 `experiments/c2rag_v3/core.py`：

- `ResourceDocument`、`StructureAwareChunker`：保存 document/parent/section/owner/license/copyright/source metadata，并按教育内容标签切块。
- `BM25Index`：稀疏检索。
- `DenseEmbeddingIndex`：确定性 dense vector 检索；当前环境未安装 neural embedding package，development pilot 使用明确标记的 sklearn hashing dense fallback，不冒充 Sentence-BERT。
- `CrossEncoderReranker`：统一 reranker 接口；当前 pilot 使用 deterministic token cross-encoder fallback。替换为真实 cross-encoder 时不改变接口。
- `C2RAGV3._retrieve`：先 metadata authorization，再 BM25/dense candidate fusion 和 reranking；禁止无权限资源先进入可见候选。
- `ExposureState`：按 identity/session/source family 保存 released spans、n-grams、knowledge units、adjacent chunks、round outputs 和累计 cost。
- `C2RAGV3.run_round`：生成结构化 plan、allowed evidence、最终 released answer，并按实际输出计算 LCS、n-gram、semantic 和 knowledge-unit disclosure；commit 只写 actual cost。

## Baseline adapters

`experiments/c2rag_v3/baselines.py` 注册 9 个共享底座的方法。它们只改变显式防护开关或返回策略，所有方法共用同一个 loader、资源集合、生成器、输出契约和 offline evaluator。

RAGFort 和 CanaryRAG 不在本地实现中伪造。RAGFort 的官方设计是 inter-class structure-aware reindexing 加 intra-class constrained cascade；CanaryRAG 是带 canary 的 dual-path runtime detection。若未满足官方模型、训练、canary 和 enforcement 条件，注册状态保持 `NOT_RUN`。
