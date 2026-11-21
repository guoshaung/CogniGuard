# TheoremQA 与 GSM8K 领域数据实验记录

## TheoremQA 开放候选检索

本轮完成了 48 条查询、302 条候选资源的运行检查，但由于项目资源与题目存在直接的一一对应关系，五种方法均得到满分。该结果只作为数据对齐诊断，不进入方法比较、汇报主表或论文结论；真正用于区分检索器的是 BEIR SciFact。

## GSM8K 数据核验

本地已保存 OpenAI 官方 GSM8K 格式数据：训练集 7,473 条，测试集 1,319 条，每条包含 `question` 和 `answer`。GSM8K 没有文档级检索 qrels，因此本轮不把“从训练题检索测试题”伪装成 Recall/MRR 实验。

GSM8K 下一步用于两项任务：

1. 构造数学教育资源库，评价教学回答效用；
2. 在有明确资源来源和授权字段的配对资源上，接入 C²-RAG 的返回粒度和版权成本评价。

本轮没有把 GSM8K 训练题和测试题强行当作文档检索 qrels，因为官方数据没有文档级相关性标注；这样做会得到不可解释的 Recall/MRR。它已完成数据规模和字段核验，正式检索实验待建立有明确资源映射的资源库。

## OpenStax 资源检查

OpenStax 官方权限页面可访问，提供开放教材和许可说明；书籍页面当前由 JavaScript 应用渲染，直接请求页面不能取得正文。官方 CNX Archive 仓库是归档服务代码，不是可直接下载的教材语料库。本轮完成了来源和许可入口核验，但没有把未成功取得的正文伪造成已运行的版权实验。

进入真实版权实验前，需要取得具体书籍的可下载章节包，并为每章保存 `book/chapter/section/source_url/version/license` 元数据。

## 当前算法决策

BEIR SciFact 的结果用于冻结检索组合：Dense 负责高召回候选，RRF 负责融合，Late Interaction 负责精排；BM25 作为基线，Cross-Encoder 作为对比精排器。TheoremQA 和 GSM8K 用于领域迁移验证，不与 BEIR 的标准检索分数简单平均。

## 结果文件

- TheoremQA：`experiments/results/theoremqa_test_open_collection_pilot/summary.json`
- GSM8K：`data/datasets/gsm8k/train.jsonl`、`data/datasets/gsm8k/test.jsonl`
- BEIR：`experiments/results/beir_scifact_retrieval_pilot/summary.json`
