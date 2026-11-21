# CG V3 五基线定义冻结

## 研究边界

论文只保留三个主要贡献：动态隐私—版权跨域策略组合、隐私与版权独立累计双预算、以及 risk/trust/history/audit feedback 驱动的跨轮闭环治理。M1–M6、execution contract、harness、runner 和 oracle 修复是工程分解或实验正确性基础，不是新增贡献。

## 五种模式

| 模式 | 启用边界 | 明确关闭项 | 研究作用 |
|---|---|---|---|
| `no_cg` | permissive action plan；完整实验输入进入统一 execution contract；ledger 仅观察 | privacy/copyright policy、双预算阻断、composer、动态动作选择、history、trust、provenance、audit feedback | 无 CG 控制器的下界 |
| `independent_policy` | privacy 与 copyright 分别变换各自 payload；可使用各自独立预算；固定可解释冲突合并 | `Pi_joint`、跨域 composer、统一跨域评分、跨域反馈串线 | 检验分别保护是否足够 |
| `static_cg` | 既有 `CGPolicyEngine` 与固定 decision ladder；复用 V3.1 执行契约 | V3 动态 composer、Full 动态评分与 Full 反馈 | 固定规则对照 |
| `budget_only` | 独立 privacy/copyright 累计预算；预算不足不允许 `allow`；复用执行契约 | composer、联合风险、history、trust、audit feedback | 区分预算贡献与完整闭环贡献 |
| `full_cg_v3` | 同时组合 `Pi_priv`/`Pi_copy`，独立双预算，risk/trust/history/provenance/audit feedback，候选过滤和评分，结构化 allowed payload | 无额外关闭项 | 三个贡献点的完整工程组合 |

## 冲突与采用理由

1. `docs/CG_V3_EXPERIMENT_PLAN.md` 将 No-CG 描述为“三层原始接口”，但同时要求统一 harness、禁止前端 fallback；本 Pilot 采用本文件的 permissive payload 定义，保证五种模式使用同一个 loader、oracle、disclosure measurement 和 execution contract，并避免把生产旧链路误当作 V3 证据。
2. `docs/CG_V3_EXPERIMENT_PLAN.md` 允许 Static 在 `CGPolicyEngine` 与 `PolicyRouter` decision ladder 中二选一；本仓库现有 V3 harness 已固定调用 `CGPolicyEngine`，因此本 Pilot 继续使用它，不混入 Full 评分。
3. `docs/CG_V3_ALGORITHM_SPEC.md` 把 M1–M6列为内部子机制；本文件按研究约束将其视为三个贡献点的工程分解，不扩展论文创新点。
4. `docs/CG_V3_EXECUTION_CONTRACT.md` 要求所有模式共用计划到执行契约，同时允许 Static 记录基线预算现象；本 Pilot 采用严格 payload 和统一 actual disclosure measurement，Static 不继承 Full 的动态能力。

## 共同实验约束

五种模式使用同一个冻结数据集 `experiments/datasets/cg_v3_pilot/episodes.jsonl`、同一 round 顺序、seed、attack oracle、成本公式、normal completion 判定、超时/错误口径和 JSONL 输出 schema。结果只代表 deterministic/mock synthetic engineering Pilot，不代表正式论文实验。
