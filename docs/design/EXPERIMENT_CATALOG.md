# CogniGuard 实验目录与统一入口

从项目根目录运行：

```bat
run.cmd experiments list
run.cmd experiments list --all
run.cmd experiments list --all --family image-watermark
run.cmd experiments show --name mmfopd-uci
run.cmd experiments show --name experiments.evaluation.cg_v3_pilot
```

目录按 `privacy`、`copyright`、`text-watermark`、`image-watermark`、`safety-control`、`datasets`、`cross-module` 和 `operations` 分层。分类是浏览结构，不改变算法、数据集或论文评价口径。每个可发现的第一方 CLI 恰好出现一次；`comparison-matrix` 是额外的版本化矩阵入口。`--json` 可取得机器可读清单。

2026-10-16 的目录快照（以后以命令实时输出为准）：

```text
CogniGuard 实验（167）
├─ 画像隐私 privacy（12）
├─ 版权检索 copyright（14）
├─ 文本水印 text-watermark（7）
├─ 图像水印 image-watermark（73）
├─ 统一安全控制 safety-control（46）
├─ 数据集 datasets（6）
└─ 跨模块/矩阵 cross-module（9）
```

## 三种托管等级

- `managed`：已核对输出参数的常用实验；统一的 `--output` 是调度目录，脚本结果自动进入其 `artifacts/` 子目录。
- `compatible`：已有 CLI 纳入同一目录、图调度与结果索引，但自身输出参数尚未逐项标准化。执行时须在 `--` 后传脚本自己的输出参数，或显式接受其历史默认位置。标为 `unreviewed` 的还须三项风险许可，不能因为出现在目录中就视为安全或可复现。
- `unavailable`：原项目缺少包、配置或数据的归档入口；可查看和生成计划，不允许执行。不能用新算法结果冒充历史复现。

当前为 14 个 `managed`、148 个 `compatible`、5 个 `unavailable`。最新主线为 `teacher-security-offline` / `teacher-security-real`，包含冻结数据、独立评分、组件消融和开发集中的两攻击角色协作；先读 [源码地图](../code-map.md)。`teacher-pollution-lab` / `teacher-pollution-real` 保留前一版先导口径，不能混合统计。

## 计划与执行

```bat
run.cmd experiments plan --name comparison-matrix --output experiments\results\matrix-plan-new
run.cmd experiments plan --name mmfopd-uci --output experiments\results\langgraph_tool_jobs\uci-plan-new
run.cmd experiments run --name rag-pair-audit --output experiments\results\langgraph_tool_jobs\rag-audit-new
run.cmd experiments plan --name experiments.evaluation.cg_v3_pilot --output experiments\results\langgraph_tool_jobs\cg-plan-new
```

输出目录必须是全新的；非矩阵实验需放在 `experiments/results/langgraph_tool_jobs/` 下。`plan` 只验证并保存计划，不执行脚本、下载或调用模型。`run` 会实际运行：模型、网络和未审核脚本仍按原有图策略分别要求 `--allow-model-calls`、`--allow-network`、`--allow-unreviewed`；未审核项的三重许可不会自动放宽。模型调用可能产生费用，先检查 `show`、计划和脚本参数。

兼容项示意：

```bat
run.cmd experiments plan --name dfg_locguard.scripts.run_stage7_semantic_structured_template --output experiments\results\langgraph_tool_jobs\stage7-plan-new -- --output_dir experiments\results\stage7-new
```

新运行均生成 `experiment-index.json`、底层 `manifest.json` 和 `node-trace.json`。索引使用同一 schema，说明领域、风险、托管等级、输出模式、状态与 manifest 哈希。兼容项的 `script_defined` 输出模式意味着其脚本可能写入另一指定位置；统一索引并不等于历史输出文件被迁移或归一化。原始 stdout/stderr 仅保存在本地，不上传 LangSmith。

`run.cmd tools ...`、`run.cmd <旧实验名> ...` 和直接 `python -m` 继续作为兼容路径，新的实验清单和命令说明以本页及 `run.cmd experiments` 为准。源码没有按视觉分组强行移动：大量相对导入与冻结结果依赖旧路径，导航层统一避免了破坏这些依赖。
