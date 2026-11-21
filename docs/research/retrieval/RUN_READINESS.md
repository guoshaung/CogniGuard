# C²-RAG V3 Run Readiness

## Decision

**NOT_READY_FOR_HELD_OUT_FORMAL_TEST**。本轮仅运行 development pilot。

## Recomputed evidence

- raw rounds: 3888; sessions: 108。
- 逐轮与 session-level mismatch 由同一 aggregation script 生成，见 `mismatch_summary.json`。
- hidden labels remain post-hoc only；原始结果不得据此推断攻击成功。
- 真实 dense encoder 已接入；cross-encoder 若 fallback=true，不能作为完整现代 RAG 结果。

## Blocking conditions

2. development 结果中的 mismatch 仍需按策略预注册后才能进入 held-out formal test。
3. RAGFort/CanaryRAG 尚未达到忠实复现条件。
4. 本轮未读取 held-out split。
