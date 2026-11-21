# CG V3 Algorithm Specification

状态：研究设计冻结草案（仅文档，不代表生产代码已实现）。

## 1. 研究定位

CogniGuard 的正式保护架构仍是三层：

1. MM-FOPD：学生画像最小披露。
2. C²-RAG：教师资源版权、来源和累计暴露控制。
3. HSW-ST/SCE-LocGuard：生成内容水印、来源追踪和审计。

CG（Teaching Privacy and Copyright Shield）是横跨三层和四个正常教学 Agent 通信的统一策略控制器，不是第四个独立保护算法。四个生产 Agent 保持为 profile diagnosis、copyright-aware resource、pedagogical teaching、learning assessment；攻击者只出现在离线评估。

V3 的研究目标是：给定任务、最小学生上下文、受控教师资源、风险、信任、历史和剩余预算，输出可组合的防护动作计划，并把执行后的真实暴露和审计结果反馈到下一轮。

## 2. 六个内部子机制

### M1：消息与能力规范化

把每次 Agent 调用规范化为消息 `M_t`：

`M_t = (sender, receiver, task, requested_data, data_category, purpose, capability, student_context, teacher_resource, session_id, round_id, provenance, previous_audit_hash)`。

代码中最接近的正式基础是 `backend/app/protection/cg/protocol.py:30-48` 的 `MessageEnvelope`、`protocol.py:56-139` 的 `CapabilityRegistry`，以及 `backend/app/agents/agent_orchestrator.py:124-151` 的 `CGController.build_message`。当前字段 `payload` 承载多个业务字段，尚未形成 V3 的显式字段级输入结构。

能力校验必须同时检查：发送者能力、消息类型契约、最小权限接收者、目的和数据类别；未通过则不得把请求交给 Agent。

### M2：动态跨域策略组合

策略输入为学生隐私策略 `Pi_priv,t` 和教师版权策略 `Pi_copy,t`。V3 不规定固定优先级，不把“取最大风险”当作联合策略；联合策略由状态条件下的候选动作效用和残余风险共同决定：

`Pi_joint,t = Compose(Pi_priv,t, Pi_copy,t, q_t, C_u,t, CR_t, S_t, H_t, B_t, K_t, P_t)`

其中 `K_t` 是能力注册表，`P_t` 是来源可信度/溯源证据。策略至少决定字段级披露、资源范围、返回粒度、摘要/掩码、水印、再生成、拒绝和审计升级。

当前代码事实：`backend/app/protection/cg/policy_engine.py:29-102` 是五段固定规则；`backend/app/protection/cg/protocol.py:346-430` 也是 route → raw field → 风险阈值 → budget → sanitize/degrade → allow 的顺序规则。因此 V3 动态组合是目标定义，不应宣称已由现有 `policy_engine.py` 实现。

### M3：跨轮累计披露预算

V3 维持双域预算定义，不引入具体数值：

`E_priv,t = E_priv,t-1 + c_priv,t`

`E_copy,t = E_copy,t-1 + c_copy,t`

`B_priv,t = B_priv,max - E_priv,t`

`B_copy,t = B_copy,max - E_copy,t`

单轮成本分别表示学生字段披露和教师资源暴露，不允许用一个总成本替代两者。预算状态必须至少按 `student_id`、`session_id`、`round_id` 保存；版权预算还应按 `resource_id/chunk_id` 保存。

当前代码的可复用实现是 `protocol.py:255-330` 的 `BudgetManager`：它以一个 `incremental` disclosure score 在 round/session/student 三个作用域累计，`consume` 在通过动作后更新内存字典。它是真实跨轮累计，但只有隐私/通用 disclosure 预算，没有独立 `c_priv`/`c_copy`、`E_priv`/`E_copy` 和资源级预算。`CGController` 在 `agent_orchestrator.py:84-93` 使用它。

课堂 demo 的版权剩余值在 `backend/app/demo/classroom_session.py:687-703` 按 return mode 减少；隐私值在 `classroom_session.py:977-982` 每轮固定减 `0.012`。这两个值属于 demo 状态更新，尚未由同一 V3 预算对象统一计算。

### M4：联合风险、信任与历史状态

统一状态定义为：

`S_t = (r_priv,t, r_copy,t, r_audit,t, E_priv,t, E_copy,t, f_t, i_t, p_t, k_t, trust_t, D_t, G_t, A_t)`

- `r_priv`：当前学生画像隐私风险。
- `r_copy`：当前资源版权/重构风险。
- `r_audit`：水印、来源或审计链风险。
- `f_t`：请求频率/资源重复频率。
- `i_t`：重复语义意图或跨轮重构信号。
- `p_t`：来源可信度。
- `k_t`：当前 Agent 能力/权限状态。
- `trust_t`：会话/来源/Agent 信任状态。
- `D_t`：上一轮策略决策。
- `G_t`：上一轮攻击指标。
- `A_t`：上一轮审计结果。

V3 不冻结未经校准的固定权重。联合风险的正式接口应允许以下形式之一，并在实验中选择：

`R_joint,t = F(r_priv,t, r_copy,t, r_audit,t, exposure_t, history_t, provenance_t, trust_t)`。

候选形式包括可解释的规则状态机、单调风险聚合或在开发集校准的约束优化。最终论文必须报告形式、参数来源、校准集、阈值和敏感性分析。不能只把风险写入日志而不影响动作。

当前 `RiskScorer`（`protocol.py:208-252`）按字段平均值乘接收者风险和 purpose factor；它真实影响 `PolicyRouter` 的 degrade/deny，但不读取版权风险、历史请求、信任或上一轮攻击结果。`classroom_session.py` 维护 `audit_trace`、`round_history` 和攻击状态，但不是统一 `S_t`。

### M5：自适应防护动作规划

统一动作空间：

`{allow, minimize, mask, summarize, controlled_excerpt, watermark, regenerate, degrade, refuse, block, audit_escalation}`。

输出是动作计划 `A_t`，而不是单个布尔值：

```text
A_t = {
  selected_actions,
  affected_fields,
  affected_resources,
  parameters,
  decision_reason,
  risk_before,
  expected_risk_after,
  consumed_privacy_budget,
  consumed_copyright_budget,
  remaining_privacy_budget,
  remaining_copyright_budget,
  audit_evidence_required
}
```

允许组合动作，例如 `minimize + summarize`、`controlled_excerpt + watermark`、`regenerate + watermark + audit_escalation`、`refuse + audit_escalation`。

当前 `CGDecision`/`PolicyRouter` 只有 `allow/degrade/sanitize/deny/defer` 等离散结果，`CGController._authorize_message`（`agent_orchestrator.py:477-621`）将 sanitize/degrade 执行到 payload，但没有统一动作计划、expected residual risk 或双预算字段。`classroom_session.py` 另有 return mode 和固定攻击决策，形成第二套动作语义。

### M6：审计反馈和闭环更新

每轮执行后记录：

`I_t = (actual_fields, actual_resources, actual_costs, A_t, watermark_id, provenance_result, attack_suspicion, previous_hash, current_hash, trust_update, execution_result)`。

然后：

`H_t = Hash(H_t-1 || canonical(I_t))`

`S_t+1 = UpdateState(S_t, I_t)`。

审计结果必须进入下一轮风险、信任、预算和动作规划；链不能只作为 UI 展示。

当前 `AuditChain`（`protocol.py:455-505`）真实维护 hash chain；`CGController` 将每次消息决策写入链，`agent_orchestrator.py:613-621` 完成成功消息审计。`classroom_session.py:719-787`、`966-982` 也维护教学答案水印与 hash head，并更新 demo budget。然而，当前链事件不会回写 `RiskScorer` 或 `CapabilityRegistry`，课堂状态只在若干攻击分支中手工提高风险/降级；因此 M6 只有部分闭环。

## 3. 统一输入与输出

### 输入 `CGInput_t`

```text
CGInput_t = {
  q_t,                  # 当前教学任务
  C_u,t,                # MM-FOPD 最小上下文卡
  Pi_priv,t,            # 学生隐私策略
  CR_t,                 # C²-RAG 受控资源结果
  Pi_copy,t,            # 教师版权策略
  B_priv,t-1,
  B_copy,t-1,
  S_t-1,
  H_t-1,
  capability_registry,
  provenance_evidence,
  session_history
}
```

### 输出 `CGOutput_t`

```text
CGOutput_t = {
  Pi_joint,t,
  A_t,
  allowed_student_context,
  allowed_teacher_resource,
  c_priv,t,
  c_copy,t,
  B_priv,t,
  B_copy,t,
  S_t,
  I_t,
  H_t,
  execution_result       # allow/degrade/refuse/block 等最终结果
}
```

### 变量映射表

| V3 变量 | 当前代码近似字段/对象 | 证据与差异 |
|---|---|---|
| `q_t` | `teaching_request`、`knowledge_point` | `agent_orchestrator.py:825-830`；未作为统一 CG 输入对象传递 |
| `C_u,t` | `context_card` | `agent_orchestrator.py:803-810`；实际已由 MM-FOPD 预处理 |
| `Pi_priv,t` | compliance policy、`privacy_level`、`COMMON_FORBIDDEN_INPUTS` | `agent_orchestrator.py:489-512`；没有显式策略对象 |
| `CR_t` | `controlled_resource_snippets` | `agent_orchestrator.py:832-846`；来源于资源 Agent 输出 |
| `Pi_copy,t` | `return_mode`、`exposure_budget`、resource policy | `classroom_session.py:687-703`、`protection/teacher_resource/src/c2rag/return_policy.py` |
| `B_priv,t` | `BudgetManager` session/student used/limits；demo `privacy_budget_remaining` | 前者是通用单预算，后者是课堂手工字段 |
| `B_copy,t` | resource `exposure_budget` | 真实在 C²-RAG/demo 中递减，但未和 CG BudgetManager 合并 |
| `S_t` | `risk_breakdown`、compliance state、课堂 `cg/audit_trace` | 分散保存，没有统一状态结构 |
| `H_t` | `AuditChain.head_hash`、课堂 `hash_chain_head` | 有两套链实现/状态 |
| `Pi_joint,t` | `policy_decision` | `PolicyRouter` 输出的是单域顺序规则，不是跨域组合策略 |
| `A_t` | `cg_action`、`decision`、`return_mode` | 只有零散动作字段，无统一动作计划 |
| `I_t` | audit event、watermark package、communication log | 有实际记录，但字段不统一、未完整反馈 |

## 4. 状态转移和边界

```text
State S_t-1, history H_t-1, request q_t
  -> normalize M_t
  -> capability/purpose/provenance pre-check
  -> estimate c_priv,t and c_copy,t
  -> project E_priv,t and E_copy,t
  -> estimate joint risk and trust
  -> compose Pi_priv,t with Pi_copy,t
  -> choose a composable A_t under budget and utility constraints
  -> execute only allowed fields/resources/actions
  -> measure actual exposure and audit evidence
  -> append I_t and H_t
  -> update S_t and persist session/resource state
```

边界判断允许直接拒绝：未知接收者、能力不足、raw identifier/raw multimodal field、来源失效、预算已耗尽、审计链断裂或高风险攻击证据。但正常策略选择不能只通过一串固定优先级 if/else 完成。

## 5. 完整但简洁的 V3 伪代码

```text
function CG_V3(CGInput_t):
    M_t <- NormalizeMessage(
        q_t, C_u,t, CR_t, Pi_priv,t, Pi_copy,t,
        session_id, round_id, provenance, H_t-1
    )

    contract <- CapabilityRegistry.validate(
        sender=M_t.sender, receiver=M_t.receiver,
        purpose=M_t.purpose, requested_data=M_t.requested_data
    )
    if not contract.allowed:
        return CommitRefusal(M_t, reason=contract.reason, state=S_t-1, hash=H_t-1)

    candidate_priv <- MinimizeAndScorePrivacy(C_u,t, Pi_priv,t, M_t)
    candidate_copy <- RetrieveAndScoreControlledResource(CR_t, Pi_copy,t, q_t)
    c_priv,t <- EstimatePrivacyCost(candidate_priv, provenance_evidence)
    c_copy,t <- EstimateCopyrightCost(candidate_copy, provenance_evidence)

    projected_budget <- {
        E_priv,t = E_priv,t-1 + c_priv,t,
        E_copy,t = E_copy,t-1 + c_copy,t,
        B_priv,t = B_priv,max - E_priv,t,
        B_copy,t = B_copy,max - E_copy,t
    }

    state_features <- BuildStateFeatures(
        S_t-1, H_t-1, session_history, projected_budget,
        request_frequency, repeated_semantic_intent,
        provenance_confidence, capability_registry
    )
    risk <- EstimateJointRisk(state_features)
    trust <- UpdateOrCarryTrustBeforeAction(state_features)

    Pi_joint,t <- ComposePolicies(
        Pi_priv,t, Pi_copy,t, q_t, candidate_priv,
        candidate_copy, risk, trust, projected_budget,
        provenance_evidence, capability_registry
    )

    plans <- EnumerateActionPlans(
        actions={allow, minimize, mask, summarize, controlled_excerpt,
                 watermark, regenerate, degrade, refuse, block,
                 audit_escalation},
        policy=Pi_joint,t
    )
    A_t <- SelectPlan(plans,
        objective=utility - residual_risk,
        constraints=budget_and_capability_constraints,
        calibration=development_set_only
    )

    result <- ExecutePlan(A_t,
        allowed_student_context=candidate_priv,
        allowed_teacher_resource=candidate_copy
    )
    actual <- MeasureActualDisclosureAndReturn(result)
    c_priv_actual <- CostPrivacy(actual)
    c_copy_actual <- CostCopyright(actual)
    I_t <- BuildAuditRecord(M_t, A_t, actual, c_priv_actual,
        c_copy_actual, provenance_evidence, result)
    H_t <- AppendHashChain(H_t-1, I_t)
    trust_next <- UpdateTrust(trust, I_t)
    S_t <- UpdateState(S_t-1, I_t, trust_next,
        E_priv,t-1 + c_priv_actual,
        E_copy,t-1 + c_copy_actual)
    PersistSessionResourceHistory(S_t, I_t, H_t)

    return {
        Pi_joint,t, A_t, result.allowed_student_context,
        result.allowed_teacher_resource,
        c_priv_actual, c_copy_actual,
        B_priv,max - E_priv,t, B_copy,max - E_copy,t,
        S_t, I_t, H_t, result.execution_result
    }
```

`SelectPlan` 的候选计划、效用和约束必须在开发集校准；不得把当前代码中的 `0.65`、`0.85`、`0.012`、`0.08` 等实现值直接宣称为 V3 的论文阈值。它们分别来自 `RiskScorer` 和 classroom demo，需通过实验决定是否保留、拆分或替换。

## 6. 与旧 CG 的区别

| 方面 | 当前旧/并行实现 | V3 冻结定义 |
|---|---|---|
| 决策单位 | 单消息、单域 disclosure score | 跨隐私/版权/审计的状态决策 |
| 策略 | 固定路由、raw field、阈值、budget 顺序 | `Pi_priv` 与 `Pi_copy` 的动态组合 |
| 预算 | 单一 disclosure score；课堂另有两个手工剩余值 | 独立 `c/E/B_priv` 与 `c/E/B_copy` |
| 风险 | 字段平均 × receiver × purpose | 风险、历史、信任、来源、攻击证据联合状态 |
| 动作 | allow/degrade/sanitize/deny/defer | 可组合动作计划及参数/预期残余风险 |
| 审计 | hash chain 记录决策 | 记录真实执行并更新下一轮状态 |
| 主入口 | `CGController` 已用于 Agent dispatch | V3 目标是统一课堂、MM-FOPD、C²-RAG 和审计输入输出 |
| 训练/攻击者 | 生产代码有攻击分支/实验攻击 | Attacker 仅作为离线评估输入 |

## 7. 冻结结论

- V3 的正式主实现候选是 `backend/app/agents/agent_orchestrator.py:CGController` 加 `backend/app/protection/cg/protocol.py` 的协议组件。
- `policy_engine.py` 保留为旧固定规则实现，不能作为 V3 动态组合证据。
- `backend/app/agents/orchestrator.py:MultiAgentOrchestrator` 保留为旧实验路径，不能作为当前 CG 主入口。
- V3 算法、双预算和闭环状态是研究规范；当前代码完成度由 `docs/CG_V3_CODE_MAP.md` 逐项记录。
