# OpenStax 来源追踪内容指纹预实验

在同一批 12 个 OpenStax 教学来源、24 次发行和 552 个传播端点上执行七个基线。每个来源有两次发行，两个发行人提供逐字相同的正文。所有方法读取同一份公开发行登记和终端文本。校准使用传播框架指定的 138 个端点，汇报结果使用其余 414 个。来源真值取仍有教学事实保留的来源集合。源集合最多返回三个标签，阈值与分差只在校准集上按来源 micro-F1 固定。

- SHA-256 比较终端与登记的完整文档。发行登记查询还检查终端句段与所有发行正文是否逐字相同。
- MinHash 使用 96 维签名和三个词的滑动片段。BM25 检索文档和句段。
- BGE-small-en-v1.5 编码终端与文档的候选句段。TinyBERT MS MARCO 交叉编码器重排 BGE 返回的前八个来源。
- 主动变体基线预注册来源的摘录、重排和缩写变体，并由 BM25 检索。预注册过程只读来源正文。

## 实测结果

MinHash 的来源 micro-F1 最高，为 0.881，Precision 1.000，Recall 0.787。两源及三源子集精确恢复率为 66.0%。BGE 的 F1 为 0.845，Recall 为 0.928。传播 1、3、5 轮时，MinHash 的 Recall 依次为 0.970、0.718、0.585，BGE 为 0.974、0.912、0.877。

强改写端点的 F1 分别为 MinHash 0.541、BGE 0.791、BGE 加重排 0.799。BGE 加重排在全部 414 个端点上的 F1 是 0.757。普通 BM25 为 0.761，加入预注册变体后为 0.788。两个 BM25 配置均对 72 个无保留来源端点给出了来源标签。SHA-256 和完整发行登记查询的 F1 均为 0.018。

独特发行 ID 恢复率为 0%。所有可匹配来源均有正文相同的两次发行，发行登记输出候选集合并在存在多个兼容 ID 时弃权。BGE 的真实发行 ID 候选覆盖率为 92.8%。该指标表示真实发行仍在候选集合中，身份恢复指标单独记录。

在 153 个已丢失全部事实的上游来源标签中，MinHash 仍归因 0 个，BGE 4 个，BGE 加重排 12 个，普通 BM25 29 个，主动变体 BM25 28 个。归因统计同时保留完全不在上游的来源误报。

单端点检索的平均时间约为 MinHash 11.3 ms，BGE 283.0 ms，BGE 加重排 356.7 ms。BGE 计入批量嵌入摊销。三个 CPU 线程执行，GPU-hours 为 0。该批主要是受控事实级传播，独立训练语料和真实生成式传播的覆盖需根据同批总报告解释。

## 复现

运行同目录的 `run.py`。输入为 `experiments/hsw_provenance/propagation` 中的 `sources.json`、`releases.json` 和 `cases.jsonl`。脚本接收 `--data`、`--out`、`--bge` 和 `--rerank`。本次 English BGE 下载版次为 `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`，本机 TinyBERT 快照版次为 `81d1926f67cb8eee2c2be17ca9f793c7c3bd20cc`。模型权重和输入哈希见配置。

`plot.py` 读取同一 `--data` 和输出目录，产生图和丢失知识误归因统计。实测产物位于 `var/results/hsw-st/provenance_20261124/fingerprints`，包含 `configuration.json`、`summary.json`、`predictions.jsonl`、`attribution_to_dropped_sources.json` 与 `source_baselines.png`。
