# CG V3 参数登记表（人工冻结草案）

> 本表登记当前 Pilot 实际影响结果的参数。除数据集固定字段外，算法/成本数值均标记为 provisional；本轮没有调参。

## 实验 adapter 参数

| 参数 | 当前值 | 代码位置 | 使用模式 | 来源/状态 | 对主要结论的影响 |
|---|---:|---|---|---|---|
| `privacy_field_cost` | 0.1 | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_policy_composer.py:ComposerConfig` | Independent/Budget/Full及共同记账 | 工程经验；provisional，需 development 校准 | 高；改变隐私预算耗尽和成本比较。 |
| `copyright_chunk_cost` | 0.2 | 同上 | Independent/Budget/Full及共同记账 | 工程经验；provisional，需 development 校准 | 高；改变版权累计和 budget-only 行为。 |
| `privacy_penalty` | 1.0 | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_policy_composer.py:ComposerConfig` | Full | 工程评分权重；provisional | 高；影响 Full 动作排序。 |
| `copyright_penalty` | 1.0 | 同上 | Full | 工程评分权重；provisional | 高；影响 Full 版权动作排序。 |
| `audit_penalty` | 0.8 | 同上 | Full | 工程评分权重；provisional | 中高；影响审计风险下的动作。 |
| `execution_cost` | 0.04 | 同上 | Full | 工程评分权重；provisional | 中；影响动作数量偏好。 |
| `repetition_penalty` | 0.05 | 同上 | Full | 工程评分权重；provisional | 高；影响多轮闭环。 |
| `low_trust_penalty` | 0.2 | 同上 | Full | 工程评分权重；provisional | 高；影响低 trust 和潜在标签泄漏。 |
| `config_version` | `cg-v3-provisional-1` | 同上 | Full/trace manifest | 工程版本标记 | 影响可复现性，不是科学阈值。 |
| `strict_execution_contract` | Pilot=true | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_five_baseline_pilot.py:run_five_baseline_pilot` | 五种模式 | 工程正确性配置 | 高；关闭会允许 legacy override，不得用于正式结果。 |

## 动作与执行参数

| 参数 | 当前值 | 代码位置 | 使用模式 | 状态/备注 |
|---|---:|---|---|---|
| `PLAN_LIBRARY` | 11 个动作组合 | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_policy_composer.py:PLAN_LIBRARY` | Full | provisional 候选集合；决定 Full 可表达能力。 |
| privacy minimize/mask multiplier | 0.5 | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_policy_composer.py:_costs`、`D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_execution.py:_privacy_cost` | Independent/Full/共同执行 | provisional；不是理论比例。 |
| privacy summarize multiplier | 0.5 | 同上 | Full | provisional。 |
| privacy degrade multiplier | 0.45 | 同上 | Budget/Full | provisional。 |
| copyright summarize multiplier | 0.45 | 同上 | Full | provisional。 |
| copyright controlled-excerpt multiplier | 0.55 | 同上 | Independent/Full | provisional；当前与 verbatim ratio 还存在双重口径风险。 |
| copyright degrade multiplier | 0.5 | 同上 | Static/Budget/Full | provisional。 |
| excerpt 最大 chunk | 1 | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_policy_composer.py:_allowed_outputs` | Independent/Full | 工程限制；需 development 校准。 |
| summary 最大长度 | 280 chars | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_policy_composer.py:_parameters`、`D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_policy_composer.py:_allowed_outputs` | Full | 工程限制；需与正式内容单位确认。 |
| watermark | `watermark_applied=true` 元数据 | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_policy_composer.py:_allowed_outputs` | Independent/Full | 当前是 mock 标记，不是生产水印检测证明。 |
| raw field 集合 | 代码中的 `RAW_FIELDS` | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_policy_composer.py:_raw_fields` | Full/静态风险 | provisional 字段分类；需人工覆盖审核。 |

## 风险、trust、history 与 audit 参数

| 参数 | 当前值 | 代码位置 | 使用模式 | 是否需 development 校准 |
|---|---:|---|---|---|
| repeated risk increment | 0.12 × repetition | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_state.py:derive_risks` | Static/Full state | 是 |
| provenance audit factor | `(1-confidence)×0.5` | 同上 | Full风险 | 是 |
| invalid previous hash risk | 0.85/0.9/0.95 多处 | `cg_v3_state.py`、`cg_v3_harness.py` | Full审计闭环 | 是；当前存在多处口径，正式前需统一。 |
| attack trust penalty | `min(0.35, 0.08×count)` | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_state.py:update_state` | 全部 state 更新，Full决策间接受影响 | 是；当前是标签泄漏重点。 |
| invalid audit trust penalty | 0.2 | 同上 | Full/共同 state | 是 |
| trust provenance update | `(confidence-0.5)×0.08` | 同上 | Full | 是 |
| previous action window | 最近 8 | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_harness.py:CGV3Harness.run`、`D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_state.py:update_state` | Static/Full | 是 |
| previous attack indicator window | 最近 16 | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_state.py:update_state` | state记录 | 是；正式运行不得注入 ground-truth label。 |
| Full audit escalation | invalid hash 后 `refuse + audit_escalation` | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_harness.py:CGV3Harness.run` | Full | 机制规则，需人工确认。 |

## 协议/旧固定策略参数（不得混称为 V3 参数）

| 参数 | 当前值 | 代码位置 | 用途 | 状态 |
|---|---:|---|---|---|
| `RiskScorer.degrade_threshold` | harness controller 为 0.9 | `D:\pycharm\CogniGuard\backend\app\agents\agent_orchestrator.py:CGController`、`protocol.py:RiskScorer` | protocol risk score | 旧/兼容实现，不是 Full V3 阈值。 |
| `RiskScorer.deny_threshold` | harness controller 为 1.0 | 同上 | protocol risk score | 旧/兼容实现，不是 Full V3 阈值。 |
| `unknown_field_risk` | 0.25 | `D:\pycharm\CogniGuard\backend\app\protection\cg\protocol.py:RiskScorer` | 未知字段风险 | 旧协议默认，需单独登记。 |
| field sensitivities | 0.05–1.0 | `D:\pycharm\CogniGuard\backend\app\protection\cg\protocol.py:RiskScorer.FIELD_SENSITIVITY` | 旧协议字段评分 | 旧协议，不应作为正式 V3 成本权重。 |
| receiver risk / purpose factor | 0.1–0.8 / 0.3–1.0 | 同上 | 旧协议风险评分 | 旧协议，需确认是否进入正式主实现。 |
| static exposure threshold | `exposure_score > 0.4` | `D:\pycharm\CogniGuard\backend\app\protection\cg\README.md`、policy engine | Static旧规则 | 旧基线参数，不能用于 Full。 |
| static reconstruction high threshold | `>=0.5` | 同上 | Static旧规则 | 旧基线参数。 |
| static resource fit threshold | `0.3` | 同上 | Static旧规则 | 旧基线参数。 |

## 数据与 oracle 参数

| 参数 | Pilot 值 | 代码/数据位置 | 状态 |
|---|---:|---|---|
| episodes per scenario | 6 | `D:\pycharm\CogniGuard\experiments\datasets\cg_v3_pilot\episodes.jsonl` | synthetic Pilot，不是正式规模。 |
| rounds per episode | 3 | 同上 `maximum_rounds`/`round_sequence` | 过短，正式需扩展。 |
| episode budget | privacy=1.0, copyright=1.0 | 同上 | 固定 Pilot 配置，需 development 预注册。 |
| resource target chunks | teacher=3, cross=1 | `success_oracle.target_chunks` | oracle provisional；cross 当前未使用该阈值。 |
| sensitive fields | 场景字段列表 | `success_oracle.sensitive_fields` | ground truth only; 不得进入运行时决策。 |
| normal denominator | 6 episodes / 18 rounds | `cg_v3_metrics.py` | 需人工确认 episode/round 双口径。 |
| feedback-sensitive denominator | 30 episodes | 同上 | 当前标记型指标，需因果 paired test。 |
| action fallback | `refuse + audit_escalation` | `cg_v3_execution.py` | 工程安全 fallback，需正式规则确认。 |

## 调参污染判断

当前 trace 和 manifest 将配置标为 `provisional_not_paper_calibrated`，Pilot 没有 development/test split，也没有在冻结 30 episode 外登记校准集。因此不能证明当前阈值不存在 test-set tuning；只能确认没有发现本轮运行后修改数据或输出目录的证据。正式实验必须先建立独立 development split、记录每次候选配置及选择理由，再冻结 held-out test。
