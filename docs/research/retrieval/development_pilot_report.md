# C²-RAG V3 Development Pilot Report

## Status

这是仅使用 development split 的工程 pilot，不是 held-out formal test。原始 `development_pilot` 结果未覆盖；本报告由 `aggregate_results.py` 从当前输出 raw trace 自动生成。

## Design

- 108 个 development sessions、4 个 round/session、9 个方法，共 3888 条逐轮记录。
- 运行时只接收 public session 输入；attack family、source text 和 oracle 由 post-hoc evaluator 读取。
- mismatch 同时报告逐轮和 session-level；二者不是同一分母。

## Mismatch summary

| 方法 | round mismatch | session mismatch |
|---|---:|---:|
| advanced_rag_no_defense | 0/432 | 0/108 |
| c2rag_without_cumulative_budget | 0/432 | 0/108 |
| c2rag_without_provenance | 320/432 | 104/108 |
| c2rag_without_reconstruction_history | 209/432 | 81/108 |
| full_c2rag_v3 | 209/432 | 81/108 |
| independent_ngram_guard | 432/432 | 108/108 |
| reranking_protection | 432/432 | 108/108 |
| static_excerpt | 432/432 | 108/108 |
| summarization_protection | 209/432 | 81/108 |

round-level mismatch 总数由 raw trace 重算；session-level mismatch 表示该 session 是否至少有一轮 mismatch。不能把二者互相替换。

## Results

完整方法×指标表在 `D:/pycharm/CogniGuard/experiments/c2rag_v3/results/development_pilot_v4/aggregated_metrics.csv`；每行保留分子、分母或均值分母及延迟统计。

## Retrieval status

dense encoder fallback=False；cross-encoder fallback=False。模型名称、revision、权重 hash、维度和 device 见 `D:/pycharm/CogniGuard/experiments/c2rag_v3/results/development_pilot_v4/model_manifest.json`。

## External baselines

RAGFort 和 CanaryRAG 未以本地简化规则冒充；官方复现条件、训练/模型要求和适配差异见 `docs/literature_baseline_matrix.md`。

## Readiness

仍为 development-only。不得将该结果当作 held-out formal test 或论文主结果。
当前失败案例记录数：719，详见 `D:/pycharm/CogniGuard/experiments/c2rag_v3/results/development_pilot_v4/failure_cases.jsonl`。
