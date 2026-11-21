# CG V3 Code Map

状态：基于当前工作树的代码事实核验。本文不修改实现，也不把类名、README 或前端展示当作调用证据。

## 1. 当前正式主链候选

当前最接近新版 CG 主实现的是：

`backend/app/demo/run_demo.py:166`
→ `backend/app/agents/agent_orchestrator.py:AgentOrchestrator.run_protected_flow`
→ `CGController.pre_check_context_card`
→ `CGController.dispatch`
→ `PolicyRouter.evaluate`
→ Agent `validate_input/generate`
→ response 再次经 `_authorize_message`
→ `approve_profile_update_evidence`
→ `final_answer_audit`
→ `AuditChain` 和 `cg_budget_state`。

具体顺序见 `agent_orchestrator.py:789-910`：

1. 将多模态输入压缩成 `context_card`（803-810）。
2. 发送 MM-FOPD → profile diagnosis（812-823）。
3. 发送诊断结果 → copyright-aware resource（825-839）。
4. 发送最小上下文和受控资源 → pedagogical teaching（841-856）。
5. 发送答案和学生响应 → learning assessment（858-871）。
6. 提交 profile update evidence（873-876）。
7. 对最终答案审计（877-880）。

这条链证明 `CGController` 真实保护了 `AgentOrchestrator` 的 protected flow，但不证明根 `server.py` 的课堂 demo 每轮都走过该控制器。

## 2. 六个机制代码映射

| 子机制 | 目标定义 | 当前实现文件 | 关键类或函数 | 是否进入主流程 | 当前完成度 | 主要缺口 | 最小修改方案 |
|---|---|---|---|---|---|---|---|
| M1 消息与能力规范化 | 统一消息字段、目的、来源、前一审计哈希并做能力路由 | `backend/app/protection/cg/protocol.py`；`backend/app/agents/agent_orchestrator.py` | `MessageEnvelope:30-54`；`CapabilityRegistry:56-139`；`CGController.build_message:124-151` | 是，`AgentOrchestrator.run_protected_flow` 经 `dispatch` 调用 | 部分完成 | payload 中未显式拆出 task/requested_data/data_category/student_context/teacher_resource/provenance；接收/发送 capability 主要由静态映射 | 保留字段兼容，新增文档化 V3 adapter/schema 和 provenance/session/history 映射，不改现有类名 |
| M2 动态跨域策略组合 | 联合 `Pi_priv` 与 `Pi_copy`，根据状态输出组合策略 | `backend/app/protection/cg/policy_engine.py`；`backend/app/protection/cg/protocol.py`；`backend/app/demo/classroom_session.py` | `CGPolicyEngine.evaluate:29-102`；`PolicyRouter.evaluate:346-430`；`_return_mode:687` | `PolicyRouter` 进入 Agent protected flow；旧 `CGPolicyEngine` 由自身测试调用；课堂 return mode 独立执行 | 未完成/部分 | 两者都是固定顺序规则；没有跨域 policy object、组合动作、效用/残余风险；课堂有硬编码 return mode | 先冻结 `CGController + PolicyRouter` 为主证据；把 `CGPolicyEngine` 标为旧基线，未来只在新增 adapter 中实现动态组合 |
| M3 跨轮双预算 | 独立追踪隐私与版权单轮成本、累计暴露和剩余预算 | `protocol.py`；`agent_orchestrator.py`；`classroom_session.py`；`protection/teacher_resource/src/c2rag/exposure_budget.py` | `BudgetManager:255-330`；`CGController._authorize_message:564-580`；课堂 `exposure_budget` 更新 691-703；`ExposureBudget` | 单一 CG disclosure budget 进入 protected flow；版权预算进入 C²-RAG/demo；未统一 | 部分完成 | `BudgetManager` 只有一个 `incremental`，round/session/student 维度；没有 `c_priv/c_copy` 双累计和 resource/chunk scope；课堂隐私值固定减 0.012 | 实验层增加双预算观测/adapter，先不替换旧字段；在实验中分别报告真实 CG budget 与课堂 demo budget |
| M4 联合风险、信任、历史 | 形成 `S_t`，由历史、攻击、来源和信任影响联合风险 | `protocol.py`；`agent_orchestrator.py`；`classroom_session.py`；`backend/app/compliance/` | `RiskScorer:142-252`；`AuditChain:455-505`；课堂 `audit_trace/round_history/cg` | RiskScorer 和 audit chain 进入 protected flow；课堂历史进入自身动态逻辑 | 部分完成 | RiskScorer 不读取版权风险/历史/信任；信任没有统一状态；审计事件未自动反馈 RiskScorer/CapabilityRegistry | 在实验 harness 中构造显式 state snapshot 并把现有字段映射进去；不宣称线上闭环已完成 |
| M5 自适应动作规划 | 输出可组合动作、对象、参数、原因、风险和预算 | `protocol.py`；`agent_orchestrator.py`；`classroom_session.py` | `CGDecision`；`PolicyRouter.evaluate`；`sanitize_payload`/`degrade_payload`；`_run_attack_turn` | allow/sanitize/degrade/deny 进入 protected flow；课堂 attack/return mode 自己更新 | 部分完成 | 动作空间不统一；没有 `minimize/mask/summarize/watermark/regenerate/audit_escalation` 统一计划，也没有 expected risk after | 文档层先定义动作映射表；实验只统计现有动作，未实现动作标记 unavailable |
| M6 审计反馈闭环 | 用实际执行、链、信任和攻击结果更新下一轮 | `protocol.py`；`agent_orchestrator.py`；`classroom_session.py`；`protection/audit_trace/src/` | `AuditChain.append/verify`；`final_answer_audit`；课堂 `_build_semantic_audit_watermark`、`_run_attack_turn` | protected flow 有消息审计；课堂有独立水印链；实验有 source tracer/audit chain | 部分完成 | `AuditChain` 主要记录；下一轮风险/能力/信任未由统一更新器驱动；课堂部分攻击状态是手工分支 | 在实验中将 audit event 转成 state feature，先测反馈是否改变动作；生产接入留作最小后续改动 |

## 3. 关键问题逐项回答

### `agent_orchestrator.py` 是否应作为正式 CG 主实现？

是，作为当前候选主实现。证据是：

- `AgentOrchestrator.__init__` 在 `agent_orchestrator.py:744-787` 构造 `CGController`。
- `run_protected_flow:810-880` 对四个 Agent 的请求和结果都通过 `pre_check/dispatch/profile_update/final_answer_audit` 处理。
- `CGController._authorize_message:477-621` 真实调用 `PolicyRouter.evaluate`、sanitize/degrade、budget consume、compliance、guardrail 和 audit append。
- `backend/app/agents/__init__.py` 导出 `CGController` 与 `AgentOrchestrator`。

限定：它是当前“受保护 Agent flow”的主实现候选，不是已完成 V3 动态跨域算法。

### `orchestrator.py` 是否属于旧实验路径？

是。`backend/app/agents/orchestrator.py:13-195` 的 `MultiAgentOrchestrator` 直接实例化 `ProfileSelector`、`DynamicBudgetAllocator`、`MultiGranularityVariantGenerator`、`HybridWatermarkSystem`、旧 `AuditChain`，在 `process_query` 中按固定分支执行 FOPD → C²-RAG → HSW-ST；它没有导入 `CGController`、`PolicyRouter`、`CapabilityRegistry` 或 `BudgetManager`。

实际调用证据：`experiments/evaluation/system_eval.py:9` 和 `experiments/demo_multiagent_system.py:6` 导入该旧 orchestrator；因此它必须保留为 legacy/experiment baseline，而不能与新版主链混称。

### `protocol.py` 中 budget 是否真正累计？

是，但范围有限。`BudgetManager.consume:306-330` 把相同 `incremental` 写入 `used_by_round`、`used_by_session`、`used_by_student`；`CGController._authorize_message:564-580` 在动作执行后消费，并在超限时记录审计并抛出 `AgentValidationError`。`backend/app/tests/test_cg_v2_protocol.py:85-92` 验证跨 round 的 session 超限，`164-181` 验证 protected flow 的预算失败。

不是 V3 双预算：它没有分开隐私/版权成本，也没有资源维度；返回的是 used/limits/projection，不是显式 `E_priv/E_copy/B_priv/B_copy`。

### `policy_engine.py` 是否动态组合策略？

否。`CGPolicyEngine.evaluate:58-95` 顺序执行五个规则：模态敏感度、资源 exposure、多轮重构、画像更新冲突、machine forgetting，并设置 allow/sanitize/degrade/refuse/quarantine/revoke 等布尔字段。`policy_engine.py:104-157` 的 helper 都是固定阈值/固定动作；没有联合状态、候选动作计划、历史状态输入或效用优化。

### risk score 是否真实影响动作？

在新版 `protocol.py` 路径中是。`RiskScorer.score:218-238` 计算字段、接收者和 purpose 调整后的 score；`PolicyRouter.evaluate:377-421` 以 deny/degrade threshold 选择 DENY/DEGRADE，其结果由 `_authorize_message` 执行。

但它不是联合风险：不读取 C²-RAG exposure、来源可信度、会话历史、信任或前一攻击指标；课堂 `risk_level` 和 attack risk 也不是同一个 scorer 的输入。

### capability registry 是否真实阻止越权调用？

在 `CGController.dispatch` 路径中是。`CapabilityRegistry.route_allowed:113-139` 检查 sender capability、message contract、expected receiver 和 receiver capability；`PolicyRouter.evaluate:359-365` 失败返回 DENY，`_authorize_message:518-530` 抛出验证错误。`test_cg_v2_protocol.py:53-66` 覆盖错误 receiver。

边界：它是静态内存注册表，不是服务级身份、签名或外部 Agent Pool 权限系统；课堂 `_learning_route_logs`（`classroom_session.py:630-654`）只是生成 route log，未调用 `CapabilityRegistry`。

### audit chain 是否反馈到下一轮？

部分是，不能判定为 V3 闭环。`AuditChain` 会把 `previous_hash` 和 `event_hash` 接到下一事件；`CGController` 暴露 `audit_chain_head` 和 `verify_audit_chain`。课堂水印链也读取上轮 `hash_chain_head`（`classroom_session.py:719-729`）。

但没有统一的 `UpdateState`：链头不会自动改变 `RiskScorer` 的输入或 trust score；课堂对部分 attack type 以固定分支更新 `cg/audit_trace`（`classroom_session.py:1651-1667`）。因此审计目前能影响后续数据的地方是局部手工逻辑，不是一般化反馈闭环。

### `classroom_session.py` 是否绕过 CG？

是，课堂主路径至少部分绕过。`_run_learning_turn:658-715` 自己根据 round/degradation 选择 `return_mode`、`exposure_cost` 和资源预算；`_learning_route_logs:630-654` 用固定四条路线和 `_route_status` 生成“cg_mediated/bypass_observed”；`classroom_session.py:977-988` 手工递减隐私预算并设置 last decision。该函数没有实例化或调用 `CGController.dispatch`。

这不等于课堂没有安全逻辑：它有 sanitize、攻击状态、semantic watermark 和 hash chain；结论是它使用另一套 demo 状态机，不能作为新版 CG 主链的端到端证据。

### MM-FOPD 与 C²-RAG 是否都通过同一个 CG 入口？

在 `AgentOrchestrator.run_protected_flow` 中是：context card 先 pre-check，profile → resource 和 resource → teaching 都经 `CGController.dispatch`。这是当前最强的统一入口证据。

在旧 `MultiAgentOrchestrator.process_query`、Layer1/Layer2 pipeline、课堂 demo 和部分实验中不是；它们直接调用 FOPD/C²-RAG/watermark 组件或使用自己的 budget/route 字段。

### 前端 CG 状态来自真实计算还是 fallback？

两者都有。`frontend/src/components/AgentCommunicationGraph.jsx` 能渲染后端 `communication_logs`，`frontend/src/components/AttackTestPanel.jsx` 说明要显示实际后端决策；但 `frontend/src/components/AcademicFigurePanel.jsx:36-49` 内含静态 demo rounds/attacks，`App.jsx` 和多个 panel 对缺失字段使用 fallback。前端展示不能单独作为 CG 实际计算证据。

## 4. 旧/新重复实现清单

| 实现 | 定位 | 证据 |
|---|---|---|
| `backend/app/protection/cg/protocol.py` | 新版协议组件候选 | `MessageEnvelope`、能力、RiskScorer、BudgetManager、PolicyRouter、AuditChain |
| `backend/app/agents/agent_orchestrator.py` | 当前受保护 Agent 主链候选 | `CGController` + `AgentOrchestrator.run_protected_flow` |
| `backend/app/protection/cg/policy_engine.py` | 旧固定策略引擎/基线候选 | 五条固定规则，写 JSONL 决策日志 |
| `backend/app/agents/orchestrator.py` | 旧实验编排器 | 直接串联三层，无 CG protocol imports |
| `backend/app/demo/classroom_session.py` | 课堂展示状态机 | 自有 cg/audit/budget 字段和攻击分支，不调用 controller |
| `protection/teacher_resource/src/c2rag/exposure_budget.py` | C²-RAG 资源预算 | resource/chunk 侧独立预算，不是 CG 双预算 |
| `protection/audit_trace/src/audit_chain.py` | 旧/实验审计链 | 被旧 `orchestrator.py` 使用，与 protocol `AuditChain` 并存 |
| `frontend/src/components/AcademicFigurePanel.jsx` | 前端图示/fallback | 静态 audit rounds 和 attack rows 可在无真实数据时显示 |

## 5. 当前明确不处理的目录

本轮不修改、不移动、不合并：

- `protection/student_profile/`、`protection/teacher_resource/`、`protection/audit_trace/` 的算法实现。
- `code/`、`dfg_locguard/`、`deploy/`、`scripts/server/` 的旧模型/图像服务链。
- `frontend/`、`server.py`、`backend/app/demo/` 的生产/展示逻辑。
- `experiments/results/`、`data/`、`.tmp/`、`frontend/dist/` 等数据和生成物。
- 两套 orchestrator 及所有测试/旧结果。

## 6. 最小修改顺序（仅建议）

1. 以 `CGController + protocol.py` 作为唯一论文主实现引用，并把 `policy_engine.py`、旧 `orchestrator.py` 标为 baseline/legacy。
2. 在不改变现有字段的前提下增加实验级 V3 input/output adapter，记录 `Pi_priv/Pi_copy`、双预算、state snapshot 和 action plan。
3. 先在受控实验 harness 中把 audit 结果映射为下一轮 state feature，验证动作是否实际变化。
4. 仅在实验结果证明必要后，再考虑把课堂 demo 接到同一 controller；本轮不做该接入。
5. 等变量、阈值和基线冻结后，再决定是否修改生产代码。

## 7. 本轮代码事实结论

- 旧版固定 if/else 仍然存在：`policy_engine.py` 明确存在，`protocol.py` 也仍是固定 decision ladder。
- 累计 privacy budget 在 `protocol.py` 的 round/session/student scope 跨轮生效；累计 copyright budget 在 C²-RAG/课堂资源字段中生效；二者没有通过同一 V3 双预算状态统一。
- 当前主实现建议为 `backend/app/agents/agent_orchestrator.py:CGController`，不是 `backend/app/agents/orchestrator.py:MultiAgentOrchestrator`。
- 六个机制中 M1、M3、M5、M6 有部分真实基础；M4 有风险/审计基础但非统一状态；M2 仍是固定规则，完整 V3 未实现。
- 最小实现缺口按机制计为 6 项：统一 V3 schema、动态跨域组合、双域预算、统一 state/trust、统一 action plan、审计反馈更新。它们是机制级缺口，不是建议现在直接修复的任务清单。
