# CG V3 成本模型规范（人工冻结草案）

> 当前模型是 deterministic/mock engineering Pilot 的显式经验规则，属于 **provisional**，不是理论推导、最优解或由正式 development split 校准的参数。本轮不修改公式和参数。

## 实现位置

- 计划成本：`D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_policy_composer.py:_costs`
- 实际隐私成本：`D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_execution.py:_privacy_cost`
- 实际版权成本：`D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_execution.py:_copyright_cost`
- 双预算投影/提交：`D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_budget.py:DualBudgetLedger`
- 每轮 trace：`D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_pilot.py:_run_mode`
- 成本结果：`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\summary.json` 和各模式 `*_episodes.jsonl`

## 隐私成本 `c_priv`

当前计划公式可写为：

```text
c_priv_plan = |allowed_fields(C_u_t)| × 0.1 × m_priv(actions)
```

其中：

- `allowed_fields` 由 `Pi_priv.allowed_fields` 与 `forbidden_fields` 过滤后得到；缺省时使用 `C_u_t` 字段。
- 若动作含 `minimize` 或 `mask`，`m_priv *= 0.5`。
- 若动作含 `summarize`，`m_priv *= 0.5`。
- 若动作含 `degrade`，`m_priv *= 0.45`。
- 若动作含 `refuse` 或 `block`，成本为 0。
- 基础字段单价 `0.1` 来自 `ComposerConfig.privacy_field_cost`。

实际执行时使用实际返回 student payload 与 `C_u_t` 的字段交集，而不是计划允许字段数量：

```text
c_priv_actual = |actual_student_fields| × 0.1 × m_priv(actions)
```

`summary` 的执行测量按 `_allowed_fields(request)` 计字段数，并标记 `summary=true`；当前不按摘要字符数、字段敏感等级、重识别概率或摘要语义覆盖率继续细分。

## 版权成本 `c_copy`

当前计划公式为：

```text
c_copy_plan = max(|chunk_ids|, 1 if resource exists else 0) × 0.2 × m_copy(actions)
```

其中：

- 基础 chunk 单价 `0.2` 来自 `ComposerConfig.copyright_chunk_cost`。
- `summarize` 时 `m_copy *= 0.45`。
- `degrade` 时 `m_copy *= 0.5`。
- `controlled_excerpt` 时 `m_copy *= 0.55`。
- `refuse` 或 `block` 时成本为 0。
- 若资源有 `verbatim_ratio`，实际版权成本在 `_copyright_cost` 中还会采用返回资源的比例；summary 使用 0.45；无受控资源返回时按原始比例 1.0。

当前实际公式的重要限制是：`resource_count` 仍取请求中的 `chunk_ids` 数量，而不完全取实际返回的 chunk 数量。因此只返回一个 chunk 的 controlled excerpt 可能按请求包含的 chunk 数计费，再乘 verbatim ratio。这是保守的 provisional 记账，不等同于内容字节数或语义覆盖率。

## provenance、trust 与风险

- provenance confidence 影响 `derive_risks` 的 audit risk，但不直接乘入 `c_priv` 或 `c_copy`。
- trust、history、repetition 和 audit feedback 影响 Full 候选评分/动作，当前不直接改变成本单价。
- 版权风险 `exposure_score` 参与风险和 restriction 判断，但不直接成为成本系数。
- 因而“高敏字段”和“低敏字段”在相同动作下可能拥有相同字段成本；“不同版权内容”在相同 chunk 数和动作下可能拥有相同成本。

## projection、reservation、actual、commit

| 阶段 | 含义 | 当前实现 |
|---|---|---|
| projection | 在执行前用候选动作估算成本，并读取当前独立账本累计值 | `DualBudgetLedger.project_privacy/project_copyright`；无副作用。 |
| reservation | 表示计划成本在剩余预算内，可以为本轮保留的额度 | 当前 harness 将“计划成本不超过剩余值”记录为 `reserved_*_cost`；没有并发安全的独立 reservation store。 |
| actual | executor 返回 allowed payload 后，根据实际字段、chunks、return mode、verbatim ratio 重新测量 | `ExecutionMeasurement.actual_*`；输出违规或预算超限时为空并 rollback。 |
| commit | 只把 actual cost 写入各自 ledger，并更新跨轮累计值 | `commit_privacy` 与 `commit_copyright` 分开执行；trace 同时写 `committed_*_cost`。 |

验收约束是 `actual <= projected`、执行不超过剩余预算（No-CG 除外）且 `committed == actual`。五基线 Pilot 的计划—实际不一致为 0/450，但这证明的是执行一致性，不证明成本模型已校准。

## 多轮累计与 reset

- 隐私按 `(student_id, session_id)` 累计，并保留 round 使用量；版权按 `session_id` 累计，同时保留 `(resource_id, chunk_id, session_id)` 使用量。
- 每轮从当前累计值 projection，执行后 commit actual；同一 episode 的三轮不会自动清零。
- `reset_session` 清除该 session 的隐私和版权累计；`reset_student` 只清隐私；`reset_resource` 清资源版权累计并重算相关 session。
- 五基线 runner 为每个 episode 新建 harness，因此 episode 之间天然隔离；这不是生产会话 reset 语义的完整替代。
- 当前没有跨 episode 同一 student/resource 的正式连续性评估，也没有并发 reservation、重放幂等键或数据库持久化。

## 参数性质与正式实验要求

当前 `0.1`、`0.2`、`0.5`、`0.45`、`0.55` 等数值来自显式工程规则，状态为 `provisional_not_paper_calibrated`，可作为可复现实验配置，但不能描述为理论推导或经验最优。

正式实验前需在 development split 预先决定：按字段敏感度、字节/token 数、chunk 覆盖率、可恢复语义比例和版权授权等级是否重构成本；然后锁定公式，在 held-out test 上只执行、不回看调参。不得依据当前 Full 0/6 结果反向调整成本。
