# CG V3.1 Three-Mode Pilot Report

> 使用冻结的 V3 Pilot JSONL；30 episodes、每模式 90 轮、总计 270 轮。结果为 deterministic/mock synthetic Pilot，不是论文正式结果。

## 阻塞根因
- Full 旧版权/跨域 6/6 的主因是旧 adapter 将无 `allowed_chunks` 的摘要 fallback 成请求 chunk，属于 oracle/观测错误；并非简单调阈值。
- Static/Budget-Only 旧跨域末轮的主因是 `degrade` 保留完整 `CR_t`，造成 execution 与 accounting 不一致。
- 诊断 trace：`D:\pycharm\CogniGuard\experiments\results\cg_v3_pilot_v3_1\diagnostic_traces.jsonl`；旧/新逐 episode 差异：`D:\pycharm\CogniGuard\experiments\results\cg_v3_pilot_v3_1\episode_differences.jsonl`。

## V3.1 核心指标
| 指标 | static_cg | budget_only | full_cg_v3 |
|---|---:|---:|---:|
| 隐私攻击成功率 | 6/6 (1.0) | 6/6 (1.0) | 0/6 (0.0) |
| 画像暴露率 | 6/6 (1.0) | 6/6 (1.0) | 0/6 (0.0) |
| 版权攻击成功率 | 6/6 (1.0) | 6/6 (1.0) | 0/6 (0.0) |
| 资源重构成功率 | 6/6 (1.0) | 6/6 (1.0) | 0/6 (0.0) |
| 跨域攻击成功率 | 6/6 (1.0) | 6/6 (1.0) | 0/6 (0.0) |
| 预算违规率 | 0/30 (0.0) | 0/30 (0.0) | 0/30 (0.0) |
| 策略冲突解决率 | 6/6 (1.0) | 0/6 (0.0) | 6/6 (1.0) |
| 正常请求可用率 | 6/6 (1.0) | 6/6 (1.0) | 6/6 (1.0) |
| 拒绝/阻断率 | 0/90 (0.0) | 6/90 (0.06666667) | 6/90 (0.06666667) |
| 审计篡改检测率 | 0/6 (0.0) | 0/6 (0.0) | 6/6 (1.0) |
| 反馈敏感决策率 | 0/30 (0.0) | 0/30 (0.0) | 6/30 (0.2) |

## 执行一致性验收
- 计划/实际不一致事件：`[]`。
- Strict payload violation：`[]`；rollback：`[]`。
- Budget-Only 预算不足仍 allow：`[]`；Full：同一检查结果为空。
- 双预算独立累计：`True`；随机攻击概率：`False`；前端 fallback：`False`。
- Full 动态 composer：`True`；Static 旧策略：`True`；Budget-Only feedback 关闭：`True`。

## 失败分层统计（旧 Pilot）
- `execution_failure+accounting_failure`：72 条逐轮 trace。
- `oracle_failure`：36 条逐轮 trace。

## 版权闭环结论
- V3.1 的 `Pi_copy → joint constraints → action plan → allowed payload → disclosure measurement → ledger commit` 已形成单一执行链。
- Full 版权和跨域攻击应以显式 chunk disclosure 统计，不再把摘要或元数据 fallback 为原始资源。
- Static 可保留预算违规作为基线现象，但其实际输出、实际消耗和 commit 必须准确记录。

## 五基线结论
- 本轮没有开始 No-CG 或 Independent-Policy，也没有覆盖旧 Pilot。
- 若上述验收字段保持为空且人工确认 Static 的预期预算违规可接受，则可以进入五基线 Pilot 准备；不应把本报告称为正式论文结果。

## 输出文件
- `D:\pycharm\CogniGuard\experiments\results\cg_v3_pilot_v3_1\diagnostic_traces.jsonl`
- `D:\pycharm\CogniGuard\experiments\results\cg_v3_pilot_v3_1\episode_differences.jsonl`
- `D:\pycharm\CogniGuard\docs\CG_V3_THREE_MODE_PILOT_REPORT_V3_1.md`
- `D:\pycharm\CogniGuard\experiments\results\cg_v3_pilot_v3_1\summary.json`、`D:\pycharm\CogniGuard\experiments\results\cg_v3_pilot_v3_1\anomalies.json`、`D:\pycharm\CogniGuard\experiments\results\cg_v3_pilot_v3_1\all_rounds.jsonl`
