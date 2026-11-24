# Issue #16 NLI 交接

数据文件为 [judgments.jsonl](results/judgments.jsonl)。180 个冻结端点共 1,254 条端点–单元预测，按接口键（UTF-8 正文 SHA-256、单元）合并后为 891 条测试记录。重复出现的键逐条核对原判定一致。另含 36 条校准记录，对应六个手写来源族，每族一个登记事实，导出编号为该来源的 `f1`。压力测试单独保存在 [stress.jsonl](results/stress.jsonl)。

## 阈值、模型与留出

- 固定 NLI 模型为 MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli。模型选择依据是现成本地 NLI 权重及其蕴含标签，未在这 180 个 Pilot 端点上比较模型或择优选权重。实验前已知 Pilot 上原词面方法的诊断结果。模型版本字段以实际权重完整 SHA-256 标识，配置与 tokenizer 哈希见 [threshold_lock.json](results/threshold_lock.json)。
- 阈值 **0.9642181396484376** 取独立开发集中最高负例分数的下一个可表示浮点数。模型配置下标签 0 是 entailment、1 是 neutral、2 是 contradiction。原版核验使用单句及相邻两句窗口对登记表达的最大蕴含概率，达到阈值确认，其余留在疑似。阈值和映射均未用 Pilot 端点选择。[开发原例](results/development.jsonl) · [开发实测分数](results/dev_scores.jsonl)
- 候选沿用 `065bb82` 的冻结 BGE 资产检索和 `631409e` 的登记单元扩展。检索器对 Pilot 文本打分生成候选，候选选择规则及本轮候选规模未依据 Pilot 核验结果调整。每个检索命中的资产提交其全部登记单元，资产检索使用原阈值 0.7535702586174011、距最高分 0.1 的范围、最多 3 个资产（每资产 3 个登记单元）。端点候选数随资产数量变化。校准用 6 条来源隔离的手写链，额外 4 条手写链仅做压力测试，Pilot 的 15 条传播链全作测试。报告中的 99/137 来自其中 9 条链的 27 个无水印模型端点。[实际划分](results/splits.json)
- 导出把原确认映射为 `entailment`，疑似统一映射为 `neutral`。这个字段表达阈值后的回放决定。历史记录未保存逐条三分类预测，无法还原 `contradiction`。测试去重记录中 98 条有当时留存的最大蕴含分数，793 条填 `null`。Claude 的加载器按 `judgment` 消费，校准分数 36 条齐全。原 [逐端点预测](results/verified.jsonl)、[错误诊断](results/errors.jsonl) 和 [治理决策](results/decisions.jsonl) 保持原样。

## 离线复现

在结果分支的仓库根目录，用独立的 `b23c42c` 检出运行。

```sh
python experiments/gate_w0_real/unit_checker/export_judgments.py --contract /path/to/pe10-b23c42c
```

脚本调用集成侧的实际 `NliReplayChecker` 和 CA-PD，对照原预测和 6,480 条 NLI 决策。评分在回放结束后进行，预期为 99/137、F1=0.825、危险放行 38/137、过拒 4/835。固定见证中 137−38 等于正确确认数 99，两者是同一结果。需要从保存数据重新导出时可加 `--export`。两种操作都只读原始预测，不需要模型。

Claude 集成网格命令在 `b23c42c` 检出根目录执行。Windows 上给 `nli-replay:` 使用相对路径，避免盘符冒号被解析成 split。

```sh
python -m experiments.x3_e2e_integration.grid --repo ../gate-w0-real --codex-ref 065bb82 --data ./x3_nli_data --seeds 0-29 --unit-checker nli-replay:../gate-w0-real/experiments/gate_w0_real/unit_checker/results/judgments.jsonl:test
```

集成网格默认使用全部传播链。此处验证的是冻结 Pilot 固定见证回放，网格结论由集成侧独立计算。
