# CG V3 正式数据集设计建议

> 本文只提出正式实验前的数据设计，不创建正式数据、不修改 Pilot、不运行正式实验。当前 30 episode 数据仍只能称为 **Five-baseline deterministic engineering Pilot**。

## 设计原则

1. 以 episode 为独立分析单位，保留 session、round、student/resource identity、授权范围、攻击目标、provenance、trust 初值、seed 和 query budget。
2. 把 primary scenario 与可叠加标签分开：同一 episode 可以有 `multi_round`、`paraphrase` 或 `grey_area` 标签，但只指定一个主 oracle。
3. development 与 held-out test 按攻击模板族、题材、角色、字段组合、资源结构和改写策略隔离，不能把同一模板的随机实例拆到两边。
4. 所有模式读取相同 episode；oracle 读取执行后的 actual output，不把 ground-truth labels 注入运行时。
5. 正式结果需要真实或有授权的数据、人工审计版权边界、任务质量标注和可复现模型/推理配置；mock 数据只能做预检。

## 建议规模

建议第一版正式矩阵每类 60 个 episode，共 660 个 episode：每类 24 个 development、36 个 held-out test。若预算有限，可先做每类 30 个，但必须保留整族 test 模板，不可只按行随机切分。

| 主类别 | 建议 episode | 每集轮数 | 风险 | 人工标注 | oracle 类型 |
|---|---:|---:|---|---|---|
| normal request | 60 | 2–4 | 低/中 | 教学目标完成、授权合法性、答案质量 | 任务完成 + 保护约束 |
| privacy attack | 60 | 4–8 | 高 | 目标字段、可重识别组合、攻击意图 | 字段暴露 + profile reconstruction |
| copyright attack | 60 | 4–8 | 高 | 版权范围、许可、原文覆盖率 | verbatim/semantic reconstruction |
| cross-domain attack | 60 | 5–10 | 高 | 两域目标、联合突破定义、因果路径 | 明确定义 AND/OR 的 joint breach |
| audit tampering | 60 | 3–8 | 高 | 篡改位置、应有链事件、预期升级 | chain integrity + next-action change |
| multi-round reconstruction | 60 | 6–12 | 高 | 重构目标、最小 query budget、组合顺序 | 累计字段/内容覆盖和重构质量 |
| partial-authorisation | 60 | 2–6 | 中 | 每字段/每 chunk 的授权矩阵 | authorized output subset |
| ambiguous/grey-area | 60 | 2–6 | 中 | 双人独立裁决、分歧说明 | 软标签/人工裁决 + refusal utility |
| paraphrased attack | 60 | 4–8 | 高 | 原攻击族、改写类型、语义等价性 | 语义攻击目标而非关键词 |
| capability spoofing | 60 | 2–5 | 高 | sender/receiver/purpose/nonce 真值 | capability route + replay oracle |
| provenance poisoning | 60 | 3–8 | 高 | 来源链、置信度、污染注入点 | provenance integrity + action escalation |

这些类别可以共享底层任务或资源，但 test 必须使用 development 未见过的模板族；若类别重叠导致 episode 同时满足多个 oracle，应预先指定主指标和次指标，避免事后挑选。

## Episode schema 建议

```text
episode_id, primary_scenario, template_family, split, seed,
student_id, session_id, resource_id, maximum_rounds, query_budget,
round_sequence[{round_id, q_t, C_u_t, Pi_priv, CR_t, Pi_copy,
  capability_context, provenance_evidence, initial_state_delta}],
attack_target, authorization_matrix, expected_quality,
success_oracle_id, oracle_parameters, privacy_budget, copyright_budget
```

运行时不得传递 `success_oracle`、`attack_target` 或 expected label 给 composer、executor 或 Teaching Agent。若需要攻击检测，应由独立 detector 从请求、历史和审计输入产生运行时证据，并与 ground truth 分离记录。

## 各类构造要求

- **normal**：加入正常但高难度教学请求、不同知识点、合法资源边界和质量评分；不能全部是低 exposure 的短问题。
- **privacy**：加入字段同义改写、跨模态线索、不同字段组合、角色伪装和低频渐进请求；单轮与跨轮分别标记。
- **copyright**：加入原文、相邻 chunk、非连续 chunk、摘要边界、受许可摘录、不同 verbatim ratio 和 watermark 状态；oracle 必须区分“合法受控输出”和“未经授权重构”。
- **cross-domain**：同时变化隐私/版权目标，包含一域诱导扩大另一域授权的路径；明确是“任一暴露”还是“同时突破”。
- **audit**：篡改 previous hash、删除事件、重排 round、伪造 provenance 和 replay nonce；应验证下一轮动作，而非只看日志字段。
- **partial-authorisation**：字段级和 chunk 级混合授权，覆盖允许、拒绝和未知三态。
- **grey-area**：使用目的合法但风险高、授权不完整、摘要可能越界等边界请求，并保留人工裁决理由。
- **capability spoofing**：变更 sender、receiver、message type、purpose 和重放状态，但保持任务内容匹配，以防 oracle 只依赖表面文本。
- **provenance poisoning**：低 confidence、来源冲突、伪造 resource trace 和合法来源混合，要求保留可审计证据链。

## Split 与校准协议

1. 先按 `template_family`、领域、资源来源、攻击策略和角色划分 family-level development/test；同义改写族必须整体进入一侧。
2. 只在 development 上选择风险阈值、成本模型、评分权重、history 窗口和 oracle 阈值；记录候选配置、失败原因和最终选择。
3. 冻结代码版本、配置 hash、数据 hash、模型/服务版本、seed 列表、超时和错误处理后，才解锁 held-out test。
4. test 运行期间禁止查看逐 episode 成功结果来修改参数、模板或 oracle；若发现 bug，建立新版本和新 split，不覆盖旧结果。
5. 正式报告同时给总体、按场景、按攻击族、按轮数和按授权边界的结果，并保留全部失败 episode。

## 当前 Pilot 的差距

当前 `D:\pycharm\CogniGuard\experiments\datasets\cg_v3_pilot\episodes.jsonl` 只有 5 类、每类 6 集、每集 3 轮，全部是 `pilot synthetic data`。它缺少 held-out template family、灰区授权、语义改写、真实质量标注、版权相似度和独立运行时攻击检测，因此不能直接升级为正式数据集。
