# CG V3 Five-Baseline Engineering Pilot Report

> 本报告是基于冻结 JSONL 和 deterministic/mock harness 的工程 Pilot，不是正式论文实验，不报告统计显著性。

## 配置与边界
- 数据集：`D:\pycharm\CogniGuard\experiments\datasets\cg_v3_pilot\episodes.jsonl`；30 episodes、每集 3 轮；五种模式共 450 轮。
- 五种模式共用 episode loader、execution contract、actual disclosure measurement、oracle、指标和输出 schema。
- 未修改前端、`server.py`、生产课堂链路、冻结数据集或旧三模式/V3.1结果。未使用外部大模型、随机攻击概率或前端 fallback。
- 三个研究贡献保持不变：动态隐私—版权跨域策略组合、独立累计双预算、risk/trust/history/audit feedback跨轮闭环治理。

## 模式定义
- `no_cg`：permissive action plan；不启用策略、预算阻断、history、trust、provenance、audit feedback或动态评分；ledger只观察。
- `independent_policy`：隐私和版权分别处理并用固定 union/refuse-dominates 规则合并；不生成 Pi_joint，不调用动态 composer。
- `static_cg`：既有 `CGPolicyEngine` 和固定 decision ladder，沿用统一执行与记账契约。
- `budget_only`：只启用独立双预算，不启用 history、trust、audit feedback或动态 composer。
- `full_cg_v3`：动态 composer、双预算、联合状态、候选过滤/评分、结构化 payload 和审计反馈闭环。
- 定义冲突及采用理由见 `docs/CG_V3_FIVE_BASELINE_DEFINITIONS.md`。

## 汇总指标
比例统一为 分子/分母（百分比）；预算消耗和延迟为全 30 集汇总/平均。

| 模式 | Privacy ASR | Profile exposure | Copyright ASR | Cross-domain ASR | Budget violation | Normal availability | False refusal | Tamper detection | Feedback-sensitive | Plan/execution mismatch |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| no_cg | 6/6 (100.00%) | 6/6 (100.00%) | 6/6 (100.00%) | 6/6 (100.00%) | 6/30 (20.00%) | 6/6 (100.00%) | 0/18 (0.00%) | 0/6 (0.00%) | 0/30 (0.00%) | 0/90 (0.00%) |
| independent_policy | 6/6 (100.00%) | 6/6 (100.00%) | 6/6 (100.00%) | 6/6 (100.00%) | 0/30 (0.00%) | 6/6 (100.00%) | 0/18 (0.00%) | 0/6 (0.00%) | 0/30 (0.00%) | 0/90 (0.00%) |
| static_cg | 6/6 (100.00%) | 6/6 (100.00%) | 6/6 (100.00%) | 6/6 (100.00%) | 0/30 (0.00%) | 6/6 (100.00%) | 0/18 (0.00%) | 0/6 (0.00%) | 0/30 (0.00%) | 0/90 (0.00%) |
| budget_only | 6/6 (100.00%) | 6/6 (100.00%) | 6/6 (100.00%) | 6/6 (100.00%) | 0/30 (0.00%) | 6/6 (100.00%) | 0/18 (0.00%) | 0/6 (0.00%) | 0/30 (0.00%) | 0/90 (0.00%) |
| full_cg_v3 | 0/6 (0.00%) | 0/6 (0.00%) | 0/6 (0.00%) | 0/6 (0.00%) | 0/30 (0.00%) | 6/6 (100.00%) | 0/18 (0.00%) | 6/6 (100.00%) | 6/30 (20.00%) | 0/90 (0.00%) |

## 成本、动作与延迟
- `no_cg`：privacy cost total `14.5`，copyright cost total `18.0`；action distribution `{"allow": 90}`；平均 episode latency `0.579297 ms`。
- `independent_policy`：privacy cost total `11.8`，copyright cost total `14.76`；action distribution `{"allow": 72, "controlled_excerpt": 36, "minimize": 18, "watermark": 36}`；平均 episode latency `0.54602 ms`。
- `static_cg`：privacy cost total `10.72`，copyright cost total `14.4`；action distribution `{"allow": 54, "audit_escalation": 36, "degrade": 36}`；平均 episode latency `1.8309 ms`。
- `budget_only`：privacy cost total `11.77`，copyright cost total `16.2`；action distribution `{"allow": 78, "audit_escalation": 12, "degrade": 6, "refuse": 6}`；平均 episode latency `0.574187 ms`。
- `full_cg_v3`：privacy cost total `3.025`，copyright cost total `7.56`；action distribution `{"audit_escalation": 6, "minimize": 84, "refuse": 6, "summarize": 84}`；平均 episode latency `1.20424 ms`。

## 机制隔离与异常检查
- No-CG未调用composer：`True`；Independent-Policy未调用composer且无Pi_joint：`True`。
- Static使用旧固定策略：`True`；Budget-Only关闭反馈：`True`；Full真实调用动态composer：`True`。
- 五种模式机制快照不一致：`0`；计划—实际不一致：`0`；预算不足仍 allow（Budget-Only/Full/Independent）：`0`。
- No-CG预算观察事件：`6`（按定义不阻断）；Full tamper升级：`True`。
- Full与Static完全相同输出：`0/90`。

## 逐 episode 配对比较
- 逐轮配对结果：`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\episode_pair_differences.jsonl`，覆盖五组预定比较。字段包含 action、allowed payload、actual disclosure、攻击结果、正常可用性、预算轨迹和审计响应差异。

## 失败 episode
- `no_cg` / `pilot_profile_split_01`：attack_success。
- `no_cg` / `pilot_profile_split_02`：attack_success。
- `no_cg` / `pilot_profile_split_03`：attack_success。
- `no_cg` / `pilot_profile_split_04`：attack_success。
- `no_cg` / `pilot_profile_split_05`：attack_success。
- `no_cg` / `pilot_profile_split_06`：attack_success。
- `no_cg` / `pilot_resource_stitch_01`：attack_success。
- `no_cg` / `pilot_resource_stitch_02`：attack_success。
- `no_cg` / `pilot_resource_stitch_03`：attack_success。
- `no_cg` / `pilot_resource_stitch_04`：attack_success。
- `no_cg` / `pilot_resource_stitch_05`：attack_success。
- `no_cg` / `pilot_resource_stitch_06`：attack_success。
- `no_cg` / `pilot_cross_domain_01`：attack_success, budget_violation。
- `no_cg` / `pilot_cross_domain_02`：attack_success, budget_violation。
- `no_cg` / `pilot_cross_domain_03`：attack_success, budget_violation。
- `no_cg` / `pilot_cross_domain_04`：attack_success, budget_violation。
- `no_cg` / `pilot_cross_domain_05`：attack_success, budget_violation。
- `no_cg` / `pilot_cross_domain_06`：attack_success, budget_violation。
- `independent_policy` / `pilot_profile_split_01`：attack_success。
- `independent_policy` / `pilot_profile_split_02`：attack_success。
- `independent_policy` / `pilot_profile_split_03`：attack_success。
- `independent_policy` / `pilot_profile_split_04`：attack_success。
- `independent_policy` / `pilot_profile_split_05`：attack_success。
- `independent_policy` / `pilot_profile_split_06`：attack_success。
- `independent_policy` / `pilot_resource_stitch_01`：attack_success。
- `independent_policy` / `pilot_resource_stitch_02`：attack_success。
- `independent_policy` / `pilot_resource_stitch_03`：attack_success。
- `independent_policy` / `pilot_resource_stitch_04`：attack_success。
- `independent_policy` / `pilot_resource_stitch_05`：attack_success。
- `independent_policy` / `pilot_resource_stitch_06`：attack_success。
- `independent_policy` / `pilot_cross_domain_01`：attack_success。
- `independent_policy` / `pilot_cross_domain_02`：attack_success。
- `independent_policy` / `pilot_cross_domain_03`：attack_success。
- `independent_policy` / `pilot_cross_domain_04`：attack_success。
- `independent_policy` / `pilot_cross_domain_05`：attack_success。
- `independent_policy` / `pilot_cross_domain_06`：attack_success。
- `static_cg` / `pilot_profile_split_01`：attack_success。
- `static_cg` / `pilot_profile_split_02`：attack_success。
- `static_cg` / `pilot_profile_split_03`：attack_success。
- `static_cg` / `pilot_profile_split_04`：attack_success。
- `static_cg` / `pilot_profile_split_05`：attack_success。
- `static_cg` / `pilot_profile_split_06`：attack_success。
- `static_cg` / `pilot_resource_stitch_01`：attack_success。
- `static_cg` / `pilot_resource_stitch_02`：attack_success。
- `static_cg` / `pilot_resource_stitch_03`：attack_success。
- `static_cg` / `pilot_resource_stitch_04`：attack_success。
- `static_cg` / `pilot_resource_stitch_05`：attack_success。
- `static_cg` / `pilot_resource_stitch_06`：attack_success。
- `static_cg` / `pilot_cross_domain_01`：attack_success。
- `static_cg` / `pilot_cross_domain_02`：attack_success。
- `static_cg` / `pilot_cross_domain_03`：attack_success。
- `static_cg` / `pilot_cross_domain_04`：attack_success。
- `static_cg` / `pilot_cross_domain_05`：attack_success。
- `static_cg` / `pilot_cross_domain_06`：attack_success。
- `budget_only` / `pilot_profile_split_01`：attack_success。
- `budget_only` / `pilot_profile_split_02`：attack_success。
- `budget_only` / `pilot_profile_split_03`：attack_success。
- `budget_only` / `pilot_profile_split_04`：attack_success。
- `budget_only` / `pilot_profile_split_05`：attack_success。
- `budget_only` / `pilot_profile_split_06`：attack_success。
- `budget_only` / `pilot_resource_stitch_01`：attack_success。
- `budget_only` / `pilot_resource_stitch_02`：attack_success。
- `budget_only` / `pilot_resource_stitch_03`：attack_success。
- `budget_only` / `pilot_resource_stitch_04`：attack_success。
- `budget_only` / `pilot_resource_stitch_05`：attack_success。
- `budget_only` / `pilot_resource_stitch_06`：attack_success。
- `budget_only` / `pilot_cross_domain_01`：attack_success。
- `budget_only` / `pilot_cross_domain_02`：attack_success。
- `budget_only` / `pilot_cross_domain_03`：attack_success。
- `budget_only` / `pilot_cross_domain_04`：attack_success。
- `budget_only` / `pilot_cross_domain_05`：attack_success。
- `budget_only` / `pilot_cross_domain_06`：attack_success。

## 工程结论
- 该 Pilot 只验证五种模式在相同 deterministic/mock 条件下的工程可运行性、机制隔离和指标可追踪性；不能推出论文结论或统计显著性。
- 阶段结论：可以进入正式实验准备的人工复核阶段；必须先复核机制快照、配对差异、失败 episode、成本口径并冻结参数。本 Pilot 不自动启动正式实验或下一阶段任务。

## 证据文件
- 逐轮结果：`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot` 下各模式 JSONL 与 `all_rounds.jsonl`。
- 汇总：`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\summary.json`、`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\summary.csv`。
- 机制快照：`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\mechanism_snapshots.json`。
- 异常：`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\anomalies.json`；失败清单：`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\failed_episodes.json`。
- 测试完整输出：`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\tests_full.txt`。
