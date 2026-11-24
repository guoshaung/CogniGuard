# Gate W0-Real · 2026-11-24

**STOP：冻结的 M2 不进入五词片段治理增益验证的下一阶段。** 在 Claude 的 K=16、32 各 30 个原始种子中，真实 M2 对 382 次有标记上游的观察检出 0 次。在相同带标记输入上，BM25 与 BM25∪M2 的三项治理指标在 60/60 个配对运行中相同。该结论适用于当前句首载体和 Gate W0 末五词规则。

## 与集成分支对齐

- GitHub 的 `codex/hsw-st` 从 `9be4d73` 快进到 `065bb82`，包含 `d7239c4`。治理分支钉在 `f65ebab`，双方共同祖先为 `d019532`。本交付独立分支从 `065bb82` 派生，回放时从独立检出导入 `f65ebab` 的实际对象。
- 使用固定生成器重建合成数据，按 `f65ebab` 的 sparse、coalition、f=8、k=2、末五词规则回放。未加标记的 BM25 对照在危险放行、正常效用、不必要拒绝率上复现原表 60/60。240 个运行共 910 条观察。原始 BM25 的危险放行合计 K16 为 20、K32 为 21，带标记文本上的 BM25 及并集分别为 24、33。这个差值包含发行文本及索引变化。真实 KBPW 的增量应以同带标记输入上的 BM25 与并集比较。
- 合成发行使用现有 M2 的公开码表、真实 `Codec.inspect/decode`、0.95 同句事实阈值和 0.05 margin。每张回执只有一条事实，写入一个载体，100 个码字用尽后如实记为未嵌入。未用检出概率或真实标签替代检测输出。此次实际治理回放仅覆盖合成控制层。Eedi 原归因层留待持有该数据的集成检出执行。Claude 的理想通道与此有限码表的结论各有适用范围。

## OpenStax 片段

1,240 个查询，288 个开发查询，952 个留出查询，六种方法共享十二来源登记和相同文本。连续裁剪以确定性均匀随机起点产生，句末取完整发行文档的末尾词，长度为 5、20、50、100。短于目标的发行文本跳过对应长度。摘要复用上一轮真实 Qwen 7B 输出，按词数上限截取并保留实际长度。没有重新推理。标记与无标记样本都保留。同源不同发行分别参与，另有独立同知识、无关文本和凭证复制对照。

来源正确归因要求当前文本有可核验事实。连续片段的分母以完整规范化事实句为保守口径。5 词裁剪无完整事实，Recall 记为 NA，KBPW 预测覆盖率为 0。现有摘要截短后事实边界未逐条重标，5/20 词各 18 条的支持标签均为 UNKNOWN，只报告原始覆盖。50 词档 12 条有全文判定，100 词档 18 条有全文判定，KBPW 均无预测。100 词摘要档的实际长度为 21–92 词。

- KBPW 随机片段的发行召回在 20、50、100 词分别为 4/15（26.7%）、49/111（44.1%）、65/144（45.1%）。末尾片段分别为 0/72、54/104（51.9%）、48/144（33.3%）。联合门槛得到相同计数。50 词随机组出现一条完整事实口径下的错误归因。
- 24 条标记和事实一起复制的反例全部触发发行 ID。它们兼容正确知识，当前传播关系无可信事件支持。实际继承的误归因率在该定向组为 24/24。
- 开发组对所有方法按长度实施相同的 5% 错误来源查询上限。测试 FPR 作为实测结果报告，多个内容基线在留出片段超过该上限。因此这里没有取得测试误报已匹配的排序。长片段个别组没有事实为空的样本，FPR 记 NA。无关文本留出控制为每档 9 条，所有方法在这些样本均为 0 误报。完整指标包括多来源集合 F1、Precision、Recall、FPR 和覆盖率。
- BGE 使用冻结的 English BGE-small，重排序使用 HSW 已冻结的 TinyBERT cross-encoder。该组与 Claude F5 的 BGE reranker checkpoint 不同。

## Claude 和 Grok 消费入口

治理入口只需 [provenance_evidence.jsonl](results/provenance_evidence.jsonl) 和 [gate_evidence.jsonl](results/gate/gate_evidence.jsonl)。评分文件 `scoring_cases.jsonl` 属于评估侧。所有 7,440 条 OpenStax 证据和治理回放的每条事件记录均用 `ProvenanceEvidence.from_dict` 验证。候选来源和各方法原始分数在 `extra`，发行候选进入审计。未确认的知识使用 `inconclusive` 与 `UNKNOWN`。所有记录标明 `text_inference` 且 `trusted_event_id=null`。回放中可信事件抵扣恒为 0。片段文件中的持有者和时间为模拟占位值，接入时以可信运行上下文绑定。

[长度曲线](results/fragment_length.png) · [完整指标](results/summary.json) · [逐样本检测](results/predictions.jsonl) · [治理回放程序](gate_replay.py) · [治理回放结果](results/gate/control.csv)

`pilot_assets/` 补齐此前仅存于本地结果目录的 38 来源受控传播、两批内容检索的逐端点预测、38 来源水印结果，以及 Chronology 第二轮原始诊断。仓库中的两个既有实验目录承载其余公开证据。大模型权重和环境缓存从运行时重建。

## 复现

从本分支运行 `evaluate.py --bge <冻结模型目录> --rerank <冻结 TinyBERT 目录> --out results`，然后运行 `evidence.py --contract <f65ebab 检出> --folder results`。合成控制使用 `f65ebab` 的 `experiments.datasets.synthetic.generate` 生成器默认参数，数据目录指向工作树外。运行 `gate_replay.py --contract <f65ebab 检出> --data <synthetic 目录> --out results/gate`。
