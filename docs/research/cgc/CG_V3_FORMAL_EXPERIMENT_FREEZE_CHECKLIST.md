# CG V3 正式实验人工冻结清单

> 本表是人工签字材料，不代表已获准运行。当前默认状态全部为“待确认”；本轮没有启动正式实验。

## 状态定义

- **待确认**：尚无负责人签字，不得作为正式实验放行依据。
- **通过**：负责人已确认证据与理由，并填写姓名和日期。
- **拒绝**：发现阻塞，必须建立新版本或修复后重新审计。

## 冻结项目

| 人工确认项 | 状态 | 证据路径 | 决策理由/需确认内容 | 确认人 | 确认日期 |
|---|---|---|---|---|---|
| 五种模式定义 | 待确认 | `D:\pycharm\CogniGuard\docs\CG_V3_FIVE_BASELINE_DEFINITIONS.md` | 确认五种模式边界对应研究问题，且不为 Full 增加额外标签。 |  |  |
| Independent-Policy 公平性 | 待确认 | `D:\pycharm\CogniGuard\docs\CG_V3_BASELINE_FAIRNESS_AUDIT.md`；`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\independent_policy_episodes.jsonl` | 确认其是有效但当前偏弱的 fixed-rule adapter，6/6 结果不因定义冲突而删除。 |  |  |
| Static-CG 定义 | 待确认 | `D:\pycharm\CogniGuard\docs\CG_V3_FIVE_BASELINE_DEFINITIONS.md`；`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\static_cg_episodes.jsonl` | 确认使用旧 `CGPolicyEngine`，不混入 Full 动态评分。 |  |  |
| No-CG 下界语义 | 待确认 | `D:\pycharm\CogniGuard\docs\CG_V3_FIVE_BASELINE_DEFINITIONS.md`；`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\no_cg_episodes.jsonl` | 确认 ledger 只观察、允许预算违规，execution contract 仅保证可追踪。 |  |  |
| Budget-Only 语义 | 待确认 | `D:\pycharm\CogniGuard\docs\CG_V3_FIVE_BASELINE_DEFINITIONS.md`；`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\budget_only_episodes.jsonl` | 确认只启用独立双预算，不使用 history/trust/audit feedback。 |  |  |
| Full-CG V3 语义 | 待确认 | `D:\pycharm\CogniGuard\docs\CG_V3_FIVE_BASELINE_DEFINITIONS.md`；`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\full_cg_v3_episodes.jsonl` | 确认 dynamic composer、双预算和闭环状态均是工程实现，不等于六个创新点。 |  |  |
| oracle 定义 | 待确认 | `D:\pycharm\CogniGuard\docs\CG_V3_ORACLE_SPEC.md`；`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\anomalies.json` | 重点确认受控 excerpt、cross-domain OR/AND、摘要和重构相似度口径。 |  |  |
| 成本公式 | 待确认 | `D:\pycharm\CogniGuard\docs\CG_V3_COST_MODEL_SPEC.md`；`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\summary.json` | 确认 0.1/0.2 及动作 multiplier 仅为 provisional，正式前须 development 校准。 |  |  |
| 参数来源 | 待确认 | `D:\pycharm\CogniGuard\docs\CG_V3_PARAMETER_REGISTRY.md` | 确认哪些参数来自旧协议、哪些来自实验 adapter，禁止混称 V3 理论阈值。 |  |  |
| attack_indicators 运行时证据 | 待确认 | `D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_pilot.py:_run_mode`；`D:\pycharm\CogniGuard\docs\CG_V3_BASELINE_FAIRNESS_AUDIT.md` | 确认其来自独立 detector 而非 ground-truth label；否则正式实验不得放行。 |  |  |
| development/test 隔离 | 待确认 | `D:\pycharm\CogniGuard\docs\CG_V3_FORMAL_DATASET_DESIGN.md` | 确认按模板族/领域/资源/攻击策略整体切分，不随机拆同族改写。 |  |  |
| 正式数据规模 | 待确认 | `D:\pycharm\CogniGuard\docs\CG_V3_FORMAL_DATASET_DESIGN.md` | 建议 11 类×60 episodes，24 development/36 held-out test，需负责人批准。 |  |  |
| 随机 seed | 待确认 | `D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\run_manifest.json` | Pilot seed 可追溯；正式 seed 列表、生成器版本和重复运行数需预注册。 |  |  |
| 模型与推理配置 | 待确认 | `D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\run_manifest.json`；正式配置登记表待建 | 确认模型版本、temperature、服务、超时、token/GPU/CPU 预算。 |  |  |
| 结果目录 | 待确认 | `D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\` | 正式结果必须新建版本目录，禁止覆盖 Pilot/V3.1 结果。 |  |  |
| 禁止测试集调参 | 待确认 | `D:\pycharm\CogniGuard\docs\CG_V3_PARAMETER_REGISTRY.md` | 确认 test 运行后不看结果改参数、oracle、模板或模式定义。 |  |  |
| 禁止覆盖 Pilot 结果 | 待确认 | `D:\pycharm\CogniGuard\experiments\results\cg_v3_pilot\`；`D:\pycharm\CogniGuard\experiments\results\cg_v3_pilot_v3_1\`；`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\` | 确认所有版本只追加新目录，不改写既有数据/报告。 |  |  |
| Pilot 标题 | 通过（文档已写明） | `D:\pycharm\CogniGuard\docs\CG_V3_FIVE_BASELINE_PILOT_REPORT.md` | 标题必须为 **Five-baseline deterministic engineering Pilot**，不得称正式论文实验。 |  |  |
| 是否允许进入正式实验 | 待确认/当前不允许 | 本清单、`D:\pycharm\CogniGuard\docs\CG_V3_BASELINE_FAIRNESS_AUDIT.md` | 在 oracle、Independent 强度和潜在 label leakage 未确认前，不允许启动正式实验。 |  |  |

## 当前建议决策

**建议：允许进入“正式实验准备的人工复核阶段”，暂不允许运行正式实验。** 最小放行前置条件是：

1. 负责人签字确认五种模式定义和 Independent-Policy 公平性。
2. 冻结新的 oracle 口径，至少拆分受控版权摘录与未经授权重构，并明确跨域 AND/OR。
3. 证明运行时 `attack_indicators` 不含 ground-truth label leakage，或将其从正式决策路径隔离。
4. 在 development split 完成成本/阈值/评分校准，再锁定 held-out test。
5. 填写模型、推理、seed、数据版本和结果目录后，另行批准正式运行。
