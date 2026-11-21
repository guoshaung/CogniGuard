# C²-RAG Naming Collision Report

## Collision

仓库中的 `C2-RAG` 曾被用于 Copyright-Constrained Retrieval-Augmented Generation，也有 2026 文档/实验语境将其解释为 Context Completeness RAG。当前 `protection/teacher_resource/src/c2rag/` 的实际代码包含版权等级、exposure budget、return mode 和 source trace，因此继续使用无上标 `C2-RAG` 会造成论文对象和上下文完整性对象混淆。

## Candidate names

1. **C²-RAG** — Copyright-Constrained Retrieval-Augmented Generation；最接近现有代码和论文语义，推荐。
2. **CRAG-Guard** — Copyright-aware Retrieval and Guarded generation；可读性高，但与既有 CRAG 缩写生态有冲突风险。
3. **Provenance-Budgeted RAG (PB-RAG)** — 强调来源和累计预算；语义准确，但弱化版权约束和 retrieval identity。

## Decision for this branch

本轮仅将新支路文档和包名写为 `C²-RAG V3` / `c2rag_v3`，不对全仓库自动重命名。旧接口、旧目录、旧结果保持原样。正式论文前需人工选择唯一名称并做一次全仓库术语迁移。
