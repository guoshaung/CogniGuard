# CG V3 Three-Mode Pilot Report

> 本报告只描述 30 集 deterministic/mock synthetic Pilot，不是论文正式结果；本轮未接入外部大模型、前端、课堂 demo 或五基线实验。

## 权限测试处理结果
- 失败证据：`experiments/results/cg_v3_pilot/permission_tests_before.txt`。失败来自测试正则与生产错误文本不一致。
- 生产权限行为判定为正确：未授权路由返回 `cg.v2.unauthorized_route`；原始学生画像返回合规阻断。
- 测试仅改为校验错误码/关键语义，复跑结果保存在 `experiments/results/cg_v3_pilot/permission_tests_after.txt`，2 passed；未修改生产权限系统。该问题与 CG V3 Pilot 无关。

## Episode 组成
- 30 episodes、每集 3 轮、共 90 轮；五类场景各 6 集。全部标记为 `pilot synthetic data`，不含真实学生画像、教师原文或密钥。
- 三种模式复用同一 JSONL、顺序、预算、seed、oracle 和 deterministic harness。

## 模式定义
- `static_cg`：调用既有 `CGPolicyEngine` 固定策略。
- `budget_only`：只使用 `DualBudgetLedger`，关闭 history、trust、audit feedback。
- `full_cg_v3`：调用 `compose_candidates`/`select_plan` 动态候选组合器，并使用 state、trust、audit feedback。

## 汇总结果
| 指标 | static_cg | budget_only | full_cg_v3 |
|---|---:|---:|---:|
| 隐私攻击成功率 | 6/6 (1.0) | 6/6 (1.0) | 0/6 (0.0) |
| 学生画像暴露率 | 6/6 (1.0) | 6/6 (1.0) | 0/6 (0.0) |
| 版权攻击成功率 | 6/6 (1.0) | 6/6 (1.0) | 0/6 (0.0) |
| 资源重构成功率 | 6/6 (1.0) | 6/6 (1.0) | 0/6 (0.0) |
| 跨域攻击成功率 | 6/6 (1.0) | 6/6 (1.0) | 0/6 (0.0) |
| 预算违规率 | 0/30 (0.0) | 0/30 (0.0) | 0/30 (0.0) |
| 策略冲突解决率 | 6/6 (1.0) | 0/6 (0.0) | 6/6 (1.0) |
| 正常请求可用率 | 6/6 (1.0) | 6/6 (1.0) | 6/6 (1.0) |
| 拒绝/阻断率 | 0/90 (0.0) | 6/90 (0.06666667) | 6/90 (0.06666667) |
| 审计篡改检测率 | 0/6 (0.0) | 0/6 (0.0) | 6/6 (1.0) |
| 反馈敏感决策率 | 0/30 (0.0) | 0/30 (0.0) | 6/30 (0.2) |

| 预算消耗/平均每集 | static privacy/copyright: {'total': 10.72, 'average_per_episode': 0.35733333} / {'total': 14.4, 'average_per_episode': 0.48} | budget-only privacy/copyright: {'total': 11.77, 'average_per_episode': 0.39233333} / {'total': 16.2, 'average_per_episode': 0.54} | full privacy/copyright: {'total': 3.025, 'average_per_episode': 0.10083333} / {'total': 7.56, 'average_per_episode': 0.252} |
| 平均 episode latency | 24.416793 ms | 21.577263 ms | 21.527107 ms |

## 分场景与动作分布

| 场景 | static_cg | budget_only | full_cg_v3 |
|---|---:|---:|---:|
| 正常教学可用率 | 6/6 | 6/6 | 6/6 |
| 画像暴露 | 6/6 | 6/6 | 0/6 |
| 资源重构 | 6/6 | 6/6 | 0/6 |
| 跨域攻击 | 6/6 | 6/6 | 0/6 |
| 审计检测 | 0/6 | 0/6 | 6/6 |
- `static_cg` action distribution: `{"allow": 54, "audit_escalation": 36, "degrade": 36}`
- `static_cg` budget curve endpoints: first `{'episode_id': 'pilot_normal_01', 'privacy_consumed': 0.7, 'copyright_consumed': 0.6}`; last `{'episode_id': 'pilot_audit_06', 'privacy_consumed': 0.3, 'copyright_consumed': 0.6}`
- `budget_only` action distribution: `{"allow": 78, "audit_escalation": 12, "degrade": 6, "refuse": 6}`
- `budget_only` budget curve endpoints: first `{'episode_id': 'pilot_normal_01', 'privacy_consumed': 0.7, 'copyright_consumed': 0.6}`; last `{'episode_id': 'pilot_audit_06', 'privacy_consumed': 0.3, 'copyright_consumed': 0.6}`
- `full_cg_v3` action distribution: `{"audit_escalation": 6, "minimize": 84, "refuse": 6, "summarize": 84}`
- `full_cg_v3` budget curve endpoints: first `{'episode_id': 'pilot_normal_01', 'privacy_consumed': 0.175, 'copyright_consumed': 0.27}`; last `{'episode_id': 'pilot_audit_06', 'privacy_consumed': 0.05, 'copyright_consumed': 0.18}`

## Audit feedback 案例
- Full tampered-hash cases: `["pilot_audit_01:r2 -> ['refuse', 'audit_escalation']", "pilot_audit_02:r2 -> ['refuse', 'audit_escalation']", "pilot_audit_03:r2 -> ['refuse', 'audit_escalation']", "pilot_audit_04:r2 -> ['refuse', 'audit_escalation']", "pilot_audit_05:r2 -> ['refuse', 'audit_escalation']", "pilot_audit_06:r2 -> ['refuse', 'audit_escalation']"]`；这些轮次动作均包含升级、拒绝或阻断。

## 失败 episode
- 可复现的预算/执行不一致失败：`[]`。其余攻击 oracle 结果见汇总表；不删除这些失败记录。

## 逐轮审计与有效性检查
- 每轮记录 mode、episode/round、request hash、Pi_priv/Pi_copy/Pi_joint、候选动作及分数、动作计划、风险/信任、双预算前后值、审计 hash、攻击判断、正常完成、延迟；只保存字段名和资源 chunk 标识，不保存敏感原文。
- 动态组合器真实调用：`True`；静态旧策略真实调用：`True`；Budget-Only 反馈关闭：`True`。
- 相同 episode/hash：`True` / `True`；双预算隔离：`True`。
- Full 审计篡改升级：`True`；Full state-action change count：`12`。
- Full/Static 完全相同输出比例：`0.0`；随机概率攻击模拟：`False`；前端 fallback：`False`。
- 预算违规事件：`[]`。

## 工程结论与阻塞
- 结果只支持验证实验管线、日志字段和机制触发，不支持论文效应结论。
- Pilot 发现 Static/Budget-Only 在 6 个跨域 episode 的末轮出现预算不足后的实际资源消耗超出剩余版权预算；这是可复现的执行计划/实际输出不一致，Full 未出现该问题。
- 若 Full/Static 差异比例较低，应解释为当前 provisional 参数和 synthetic oracle 下动态组合尚未产生充分差异，不调整阈值追求漂亮结果。
- 正式五基线实验前必须先处理上述预算阻塞，并人工确认 oracle 定义、真实数据授权、预算标定、审计链跨进程持久化以及指标统计口径。

## 结果文件
- `experiments/datasets/cg_v3_pilot/episodes.jsonl`
- `experiments/results/cg_v3_pilot/summary.json`、`anomalies.json`、`all_rounds.jsonl`
- `docs/CG_V3_THREE_MODE_PILOT_REPORT.md`
