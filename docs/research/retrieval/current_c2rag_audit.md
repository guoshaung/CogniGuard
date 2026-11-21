# Current C²-RAG Audit

## Scope and name

本审计区分当前生产/legacy `C2-RAG` 与新实验支路 `C²-RAG`。本轮统一使用 **C²-RAG（Copyright-Constrained Retrieval-Augmented Generation）**。新支路位于 `experiments/c2rag_v3/`，不改变既有 import 和课堂链路。

## Actual legacy call path

1. `experiments/formal_v2/run_formal.py:196-198` 创建 `ExposureBudget`，调用 `decide_return_mode` 和 `render_controlled_resource`。
2. `protection/teacher_resource/src/c2rag/retriever.py:9-60` 的 `CopyrightAwareRetriever.retrieve` 构造 query，调用 `ResourceIndex.similarities`，并按固定权重排序。
3. `protection/teacher_resource/src/c2rag/resource_index.py:7-25` 使用 `SimpleTfidfVectorizer` 和 cosine similarity 扫描全 resource list；没有 BM25、dense neural embedding、RRF 或 cross-encoder reranker。
4. `protection/teacher_resource/src/c2rag/return_policy.py:13-41` 的固定优先级规则决定 quote/variant/summary/outline/refuse，`render_controlled_resource:80-103` 生成受控文本。
5. `protection/teacher_resource/src/c2rag/return_policy.py:108-145` 的 `produce_controlled_resource` 调用 `ExposureBudget.update` 并建立 trace。
6. `protection/teacher_resource/src/c2rag/exposure_budget.py:9-54` 以 `chunk_id` 为主维护 exposure 和短 `recent_hits`；它不是按 user、resource、source family、topic、session、cross-session 的完整状态。
7. `protection/teacher_resource/src/c2rag/c2rag_metrics.py:7-65` 对完整 resource list 计算最大 cosine/LCS；它不是严格绑定最终真实多轮回答的 reconstruction evaluator。

仓库还存在 `protection/Layer2_c2rag/src/c2rag/` 的重复旧实现；其 `retriever.py:3-28` 依赖 `protection.fopd_c2rag_mvp`，不能视为新 V3 的调用路径。`experiments/evaluation/eval_c2rag.py:10-33` 通过 student `run_pipeline` 运行旧 demo，未调用 `experiments/c2rag_v3`。

## Legacy findings

| 项目 | 当前事实 | 判断 |
|---|---|---|
| Chunking | legacy `TeacherResource` 通常已经是一个 chunk；没有按 title/section/question/answer/explanation 的二次结构切块 | 仅适合 legacy engineering evidence |
| Embedding/retrieval | Simple TF-IDF + cosine，全库扫描 | 不是现代混合检索 |
| top-k | `top_k_resources` 默认 3 | 固定配置，未证明 dev/test 冻结流程 |
| BM25/RRF/reranker | 未实现 | legacy 缺失 |
| provenance filter | legacy retriever 不做检索前 metadata authorization | 资源先进入候选，再由返回规则控制 |
| budget | `ExposureBudget` 按 chunk 更新；formal runner 每条 case 新建 budget | 不是完整跨 session 累计 |
| history | `recent_hits` 仅短窗口；没有多轮 reconstruction memory | 不能支撑真实多轮结论 |
| evaluator | legacy metrics 可以扫描完整 resource bank；formal runner 计算最终字符串的 LCS/cosine，但数据是单行 pair | 只能作为 limited-scale/legacy |

## Formal V2 validity

Formal V2 的统一字段、隐藏标签隔离、实际输出成本和计划—执行一致性回归仍有价值。其 C2-RAG 结果只能说明旧 adapter 在 96-case synthetic split 上的工程行为；不能作为 C²-RAG V3 的检索质量或多轮版权保护结论。旧结果见 `experiments/formal_v2/results/`，不得覆盖。

V3 development pilot 只读取 `experiments/datasets/cogniguard_math_suite/mixed_math_suite/splits/dev`，并以完整 session 为统计单位。新的真实 held-out test 尚未运行。
