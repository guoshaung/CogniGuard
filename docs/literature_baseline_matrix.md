# Literature Baseline Matrix

## Reproducibility status

| 方法 | 官方证据 | 核心机制 | 本仓库状态 | 能否作为本轮数值基线 |
|---|---|---|---|---|
| RAGFort | [AAAI paper](https://ojs.aaai.org/index.php/AAAI/article/view/40432/44393), [official code](https://github.com/happywinder/RAGFort) | structure-aware contrastive reindexing + constrained cascade generation | `NOT_RUN`；缺官方训练/模型与兼容数据配置 | 否 |
| CanaryRAG | [ACL Anthology paper](https://aclanthology.org/2026.acl-long.385/), [arXiv record](https://arxiv.org/abs/2604.10717) | canary injection + dual-path runtime detection + enforcement | `NOT_RUN`；缺忠实 canary/runtime/oracle 配置 | 否 |
| RAG extraction benchmark | [Benchmarking Knowledge-Extraction Attack and Defense](https://arxiv.org/abs/2602.09319) | attack/defense evaluation protocol | 作为威胁模型参考，不是防御实现 | 否 |
| RAG-Thief / feedback extraction | [Feedback-Guided Extraction](https://arxiv.org/abs/2411.14110) | adaptive feedback-guided extraction | 作为攻击设计参考 | 否 |
| IKEA | [Silent Leaks](https://proceedings.iclr.cc/paper_files/paper/2026/hash/2974844555dc383ea16c5f35833c7a57-Abstract-Conference.html) | benign-query implicit extraction | 作为隐式提取攻击参考 | 否 |

## Enforcement note

CanaryRAG 是检测型方法。即使将来接入，也必须分别报告 detection positive、后续 `block/rewrite/refuse` 和最终实际 disclosure；检测成功不能直接等价于泄露被阻止。本轮没有用自制 n-gram guard 冒充 CanaryRAG。

## Comparison policy

V3 pilot 的 `advanced_rag_no_defense`、`reranking_protection`、`summarization_protection`、`static_excerpt` 和 `independent_ngram_guard` 是本地定义的可复现实验基线，不使用 RAGFort/CanaryRAG 名称。只有完成官方实现和配置核验后，才可从 `NOT_RUN` 改为可比较状态。
