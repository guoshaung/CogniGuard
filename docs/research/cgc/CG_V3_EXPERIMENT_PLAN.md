# CG V3 Experiment Plan

状态：冻结实验设计，不执行实验、不修改结果、不把 demo/fallback 当作结果。

## 1. 研究问题与假设

### RQ1：跨层策略是否降低联合风险？

比较 No-CG、Static-CG、Independent-Policy、Budget-Only 与 Full-CG，在相同任务、相同攻击、相同查询预算下的隐私、版权、审计和可用性。

**H1：** Full-CG 的跨域攻击成功率、预算违规率和联合残余风险低于独立策略；正常教学质量下降应处于可接受范围。

### RQ2：累计预算是否能防止多轮拆分攻击？

在每轮单独风险较低、总语义逐步重构的请求序列中，比较无累计、单域累计和双域累计。

**H2：** 双域累计预算能够比单轮阈值更早识别并限制画像/资源的累积重构。

### RQ3：历史、来源和审计反馈是否真正改变后续动作？

对相同后续请求，分别提供干净历史、重复意图、低来源可信度、链篡改和攻击证据。

**H3：** 反馈闭环应改变后续风险、剩余预算、动作强度或拒绝率，而不是只增加日志字段。

### RQ4：能力检查是否能阻断越权路由？

比较启用和去掉 capability contract 的路径，测错误 receiver、伪造 purpose 和直接 Agent 调用。

**H4：** 能力检查降低越权成功率，同时不影响合法四 Agent 路径。

### RQ5：跨层组合是否优于各自独立保护？

固定 MM-FOPD、C²-RAG、HSW-ST/SCE-LocGuard 的版本和参数，只改变 CG 控制条件。

**H5：** Full-CG 的跨域风险下降来自状态组合和反馈，而不能由前端静态数据或单一保护层解释。

## 2. 实现路径和数据集

### 首选 CG 实验入口

- 新版 controller 单元/攻击评估：`experiments/evaluation/attack_defense_eval.py`，实例化 `backend.app.agents.agent_orchestrator.CGController`。
- 新版协议测试：`backend/app/tests/test_cg_v2_protocol.py`、`backend/app/protection/cg/test_policy_engine.py`。
- 新版完整受保护 Agent flow：`backend/app/demo/run_demo.py` → `AgentOrchestrator.run_protected_flow`。
- episode 级攻击 API/runner：`backend/app/api/attack_eval_api.py`、`experiments/attacks/episode_attack_runner.py`；API 是否挂载需先确认，CLI/runner 可独立复用。

### 数据集和输入

| 数据用途 | 现有路径/入口 | 复用边界 |
|---|---|---|
| 基础学生画像、教师资源、攻击场景 | `data/datasets/education_scenarios/student_profiles.jsonl`、`teacher_resources.jsonl`、`attack_scenarios/attack_cases.jsonl` | 可用于 controller smoke/攻击回放；必须记录样本数和文件 hash |
| 场景层与 episode | `data/scenario_layers/`、`backend/app/scenario_loader.py`、`experiments/datasets/cogniguard_math_suite/` | 用于多轮、跨层和攻击组合；冻结 split 后再跑测试 |
| 数学任务 | `data/datasets/math/sample_problems.jsonl`、`data/datasets/gsm8k/`、`experiments/dataset_builders/` | 只作为任务载体，不把任务数据量当成安全结果 |
| FOPD/C²-RAG 专用数据 | `protection/student_profile/data/`、`protection/teacher_resource/data/`、`protection/audit_trace/data/` | 复用既有 pipeline 指标时标明其不是统一 CG 结果 |
| 图像/水印 | `data/image_watermark/`、`dfg_locguard/`、`scripts/server/` | 与文本 CG 结果分开报告；外部服务/权重必须记录环境 |

每次正式实验必须固定：数据版本/hash、split、样本数、随机种子、模型/服务配置、每 session 最大轮数、攻击 query budget、阈值来源和输出目录。

## 3. 基线

| 基线 | 配置定义 | 复用现有代码 | 不能声称的内容 |
|---|---|---|---|
| No-CG | 不调用 `CGController`；三层保护按各自原始接口执行 | `backend/app/agents/orchestrator.py:MultiAgentOrchestrator` 可作旧系统载体，但需确认其 FOPD/C²-RAG/HSW-ST 全部开关 | 不能使用前端 fallback 代替运行结果 |
| Static-CG | 使用 `backend/app/protection/cg/policy_engine.py:CGPolicyEngine` 的固定规则，或冻结当前 `PolicyRouter` decision ladder；二者必须二选一并写明 | `backend/app/protection/cg/test_policy_engine.py`、`protocol.py` | 不可把固定阈值叫动态 V3 |
| Independent-Policy | privacy 走 MM-FOPD，copyright 走 C²-RAG，各自决定，不读取对方状态 | `protection/student_profile/`、`protection/teacher_resource/` | 不可把两者最后拼接称为跨域组合 |
| Budget-Only | 保留跨轮预算检查，关闭动态历史/信任/动作选择；如现有实现只有单预算，明确标记为 single-budget | `protocol.py:BudgetManager` | 不可宣称已验证双域预算 |
| Full-CG | M1–M6 全部启用；只有实际完成的机制进入当前版本，未实现部分用实验开关标记 | `CGController` + 实验 harness | 需区分“controller v2 baseline”和“V3 target” |

当前仓库已有 `experiments/evaluation/system_eval.py` 的 `Baseline`、`Full System` 和去除 HSW-ST 的 ablation，但它导入旧 `backend.app.agents.orchestrator.MultiAgentOrchestrator`，并且攻击模拟 `_simulate_attack` 使用随机概率；因此只能作为 legacy comparison，不能直接充当 V3 五基线结果。

## 4. 消融实验

| 消融 | 关闭项/模块 | 预期影响指标 | 现有代码可否直接完成 | 新增需求 |
|---|---|---|---|---|
| w/o dynamic cross-domain composition | 使用 Static-CG 或独立 `CGPolicyEngine` | 冲突解决率下降、跨域攻击成功率上升 | 部分可用 | 需要固定统一 harness 和策略标签 |
| w/o cumulative privacy budget | 不调用 privacy 侧累计消费，只保留单轮 score | 多轮画像重构成功率、隐私暴露率上升 | `BudgetManager` 可做近似，但需按域隔离 | 需要 privacy-only 开关 |
| w/o cumulative copyright budget | 每轮重置资源 exposure 或只看当前返回 | 资源重构成功率、版权泄露率上升 | C²-RAG 有资源 budget，但需冻结 reset 方式 | 需要 resource/session reset 开关 |
| w/o history | 不输入 session history、重复意图和 round history | 长期低风险攻击识别下降 | 课堂已有 history，但不是 CG state | 需要 state snapshot adapter |
| w/o trust/provenance | 固定或移除来源可信度、trust update | 伪造来源、retrieval poisoning、审计逃逸上升 | attack 数据已有相关场景；统一 trust 尚无 | 需要可复现实来源信号 |
| w/o adaptive action planning | 只返回 allow/deny 或固定 degrade | 正常可用性与风险下降的 trade-off 变差 | 当前实现本来是离散动作 | 需要记录 action plan schema |
| w/o audit feedback | 保留 hash 记录但不把结果传给下一轮 | 链篡改后续动作不升级，攻击累积成功率上升 | 当前链与状态分离，适合做对照 | 需要确保两组只差反馈通道 |
| w/o capability check | 跳过 `CapabilityRegistry.route_allowed` | 越权路由成功率上升 | `protocol.py` 有真实检查 | 需要保持其它风险/预算相同 |

每项消融都要报告关闭项是否只影响实验 harness，不能把“删除生产代码”当作消融方式。

## 5. 攻击评估

Attacker Agent 只作为离线输入生成器/攻击 runner，不加入四 Agent 生产链。优先复用 `experiments/attacks/`、`data/datasets/attack_scenarios/`、`data/scenario_layers/attack_templates/` 和 `episode_attack_runner.py`。

| 攻击 | 构造方式 | 主要观察 |
|---|---|---|
| 多轮学生画像重构 | 多轮请求分别索取 mastery、错误类型、历史/原始模态线索 | `E_priv`、画像暴露率、privacy ASR、后续动作 |
| 完整画像拆分请求 | 每轮请求一个低敏字段，保持单轮风险低 | 累计预算触发轮次、重构成功率 |
| 教师课件原文抽取 | 请求原文、连续片段、特定 chunk 和 source ID | 教师资源泄露率、版权 ASR、return mode |
| 多轮资源拼接 | 以不同教学目的索取相邻/同义 chunk | reconstruction success、exposure budget |
| 伪造教学目的 | 改写 purpose、sender 或请求描述 | capability/purpose 违规率、误放行率 |
| 隐私+版权跨域组合 | 用资源请求反推学生画像，或用画像请求扩大资源范围 | cross-domain attack success、冲突解决率 |
| 水印移除/篡改 | paraphrase、marker removal、source ID replacement、局部图像编辑 | detection rate、semantic preservation、audit result |
| 审计链篡改 | 修改 previous hash、event hash、删除 round、跨轮拼接 | chain completeness、tamper detection、后续拒绝/升级 |
| 长期低风险耗尽 | 重复低风险请求直到 budget exhaustion | 预算违规率、耗尽轮次、正常请求可用性 |
| 越权/重放 | 错 receiver、伪造 route、重用 nonce/message | capability block rate、replay rejection |

攻击结果必须以每个 session/episode 为单位保存，而不是只保存聚合数字；每个结果应含输入 hash、round、policy/action、budget before/after、audit hash 和成功判定依据。

## 6. 评价指标定义和证据要求

| 指标 | 建议定义 | 必须绑定的证据 |
|---|---|---|
| 学生画像暴露率 | 实际披露敏感/受保护字段量 ÷ 目标字段量 | message payload、allowed fields、样本数 |
| 隐私攻击成功率 | 攻击者重构目标画像达到预设 oracle 的 episode 比例 | 攻击 oracle、轮数、query budget |
| 教师资源泄露率 | 实际返回受限原文/版权片段量 ÷ 受保护资源量 | resource/chunk/source trace |
| 教师资源重构成功率 | 多轮输出拼接达到相似度/内容 oracle 的比例 | similarity threshold 来源、拼接规则 |
| 版权越权成功率 | 未满足 policy 却返回受限内容的比例 | policy、license、decision、returned range |
| 跨域攻击成功率 | 同时突破 privacy/copyright 或通过一域放大另一域的比例 | 双域攻击标签、两个预算状态 |
| 预算违规率 | 实际成本超过剩余预算仍执行的比例 | before/after、limit、执行结果 |
| 策略冲突解决率 | privacy/copyright 约束冲突样本中输出合法联合动作的比例 | 冲突标注、Pi_joint、action plan |
| 拒绝率 | 被 refuse/block 的请求 ÷ 请求总数 | 区分攻击与正常请求 |
| 正常请求可用性 | 合法请求成功完成且满足保护约束的比例 | 任务完成、动作、审计记录 |
| 教学回答质量 | 既有任务正确性/学习改善指标，单独报告 | 数据集、评估器、人工/模型判定 |
| 防护后风险下降 | `(risk_before - risk_after) / risk_before`，保留分域结果 | 风险计算版本、动作前后快照 |
| 审计链完整率 | 可验证链事件 ÷ 应有链事件 | event hash、previous hash、删除/篡改协议 |
| 水印检测率 | 攻击后仍检测到有效水印的比例 | watermark version、攻击类型、检测器 |
| 延迟/计算开销 | P50/P95 latency、token/API/GPU/CPU 成本 | runtime mode、模型和服务配置 |

已有 MM-FOPD/C²-RAG 指标可以复用，但必须在结果中同时写：数据集、split、样本数、代码入口和结果文件。`frontend/src/components/AcademicFigurePanel.jsx` 的 fallback 行、`experiments/results/` 的旧 JSON 和 README 数字都不能单独作为 V3 证据。

## 7. 实验矩阵

### 主矩阵

| 维度 | 水平 |
|---|---|
| Controller | No-CG / Static-CG / Independent-Policy / Budget-Only / Full-CG |
| Scenario | 正常教学 / privacy attack / copyright attack / cross-domain attack / audit attack |
| Horizon | 单轮 / 中等多轮 / 长期低风险累计 |
| Protection layer | MM-FOPD / C²-RAG / HSW-ST/SCE-LocGuard / full three-layer |
| Runtime | deterministic/mock（仅工程回归）/ real service or model（正式结果） |
| Split | development（阈值/策略校准）/ held-out test（只评估） |

所有 controller 使用相同场景、相同随机种子、相同 query budget 和相同资源版本。不得测试集选最优基线、阈值或动作组合。

### 反馈专项矩阵

固定同一个后续请求 `q_t`，仅改变：

1. 无历史 vs 重复语义历史。
2. 正常审计 vs 链篡改记录。
3. 高 provenance confidence vs 低 confidence。
4. 正常 trust vs trust 被攻击证据降低。
5. 预算充足 vs 预算接近耗尽。

若后续 `A_t`、risk、budget 或 execution result 完全不变，应判定“反馈没有进入决策”，不能把日志字段写入算作闭环成功。

## 8. 最小可发表结果组合

第一阶段只需要冻结一组可复现、可解释的结果：

1. **协议正确性**：M1 capability route、M3 累计 budget、M6 audit tamper 的单元测试和小规模端到端日志。
2. **主比较**：五个基线 × 正常/隐私/版权/跨域攻击，报告风险、ASR、可用性和延迟。
3. **反馈证据**：至少一个多轮拆分攻击和一个审计篡改后续请求，证明下一轮动作发生改变；如果当前代码做不到，结果应标为目标/缺口，而非伪造 Full-CG。
4. **消融**：优先做累计 privacy budget、累计 copyright budget、history/audit feedback、capability check 四项；动态组合和统一 action plan 只有在 harness 实现后再纳入正式 Full。
5. **稳健性**：固定开发/测试 split，报告阈值或策略在少量配置变化下的敏感性，不使用前端 demo 数据。

当前最小可信结论可以是“新版 CG 的协议、能力、单一累计预算和哈希审计组件可复用”；不能提前写成“六机制已全部实现并完成闭环”。

## 9. 预计需要新增的脚本（只规划，不本轮创建）

- `experiments/evaluation/cg_v3_harness.py`：统一五基线、V3 input/output adapter、session reset 和结果 schema。
- `experiments/evaluation/cg_v3_metrics.py`：按字段/资源/审计/预算计算指标，禁止读取前端 fallback。
- `experiments/evaluation/cg_v3_ablation.py`：统一六机制开关和四项优先消融。
- `experiments/attacks/cg_v3_multiturn_attacks.py`：拆分画像、资源拼接、跨域和长期耗尽序列；优先封装现有 attack runner。
- `experiments/evaluation/cg_v3_replay.py`：读取固定 JSONL episode，重放 session history 和 audit feedback。
- `experiments/evaluation/cg_v3_manifest.py`：记录数据/配置/代码 commit/hash、样本数和运行环境。

新增脚本应调用当前 `CGController` 或明确标注 legacy orchestrator，不应复制一套新的生产 CG。

## 10. 现有结果可复用范围

### 可以作为背景或方法对照

- `experiments/results/evaluation/`、`experiments/results/expanded_pipeline*/` 的 FOPD/C²-RAG 结果：可作为三层组件背景，前提是重新标注入口、数据集和是否经过 CG。
- `experiments/results/attacks/`、`experiments/results/baselines*/`、`experiments/results/ablation*/`：可作为旧实验/方法设计参考，不自动转换为 V3 结果。
- `experiments/results/current_validation_20260812/`：可作为验证记录索引，需逐个确认 commit、配置和实际入口。
- `docs/组会伪代码与实验方案-2026-07-11.md`、`docs/组会伪代码_综合与分块_含图像水印_2026-08-02.md`：可作为研究叙事和指标候选，但其中关于 CG 完整反馈的表述要以代码核验为准。

### 不能直接复用为 V3 正式结果

- 前端静态 fallback：`frontend/src/components/AcademicFigurePanel.jsx`。
- 旧 `system_eval.py` 的随机攻击模拟和 `backend/app/agents/orchestrator.py` 结果，除非重新标为 legacy baseline。
- 任何没有记录 data/config/commit/入口/运行模式的 `experiments/results/*`。
- mock、fallback、deterministic demo 输出；它们只用于工程回归或 UI 演示。

## 11. 实验冻结检查表

- [ ] 选定唯一 CG 主入口：`agent_orchestrator.py:CGController` 或明确声明 legacy。
- [ ] 记录 `protocol.py` 当前阈值来源，不把它们称为论文 V3 阈值。
- [ ] 分开统计 `c_priv/E_priv/B_priv` 与 `c_copy/E_copy/B_copy`；若未实现，结果标明 single-budget。
- [ ] 固定四 Agent 生产架构，Attacker 只在 offline runner。
- [ ] 固定数据集、split、样本数、hash、随机种子和 query budget。
- [ ] 每轮输出含 policy/action/budget/audit hash/actual disclosure。
- [ ] 验证 audit feedback 真的改变下一轮决策。
- [ ] 把前端 fallback 与实验结果目录排除出指标计算。
- [ ] 用 held-out test 只做最终评估，不回看调参。
- [ ] 报告当前未实现机制，不用 Full-CG 名称覆盖缺口。
