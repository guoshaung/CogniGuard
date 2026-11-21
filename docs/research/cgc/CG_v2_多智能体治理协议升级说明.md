# CG v2 多智能体治理协议升级说明

## 定位

CG v2 将原来的 `CGController` 中间层升级为显式的多智能体策略控制协议。核心变化是：

> Agent 负责教学任务，CG 负责治理 agent 的通信、输入、输出、预算、记忆写回和审计。

CG 不是第四个并列保护层，而是 MM-FOPD、C2-RAG、HSW-ST 的横向 policy control plane。

## 1-8 个升级点与实现位置

| 升级点 | 实现 | 说明 |
|---|---|---|
| 1. Message Envelope | `backend/app/protection/cg/protocol.py::MessageEnvelope` | 每条消息包含 `message_id`、`trace_id`、`round_id`、purpose、privacy level、risk、capability、parent message 等字段 |
| 2. Agent Capability Registry | `CapabilityRegistry` | 每个 agent 显式声明最小权限能力；发送方和接收方都必须满足 message contract |
| 3. Policy-based Routing | `PolicyRouter` | 从硬编码边白名单升级为 route + capability + expected receiver + payload policy 的组合判断 |
| 4. 字段级风险评估 | `RiskScorer` | 按字段敏感度、接收方风险、用途因子计算披露风险，替代单纯字符串长度打分 |
| 5. 多级累计披露预算 | `BudgetManager` | 同时维护 round / session / student 三层预算，防止单轮、多轮和长期画像重建 |
| 6. Profile Update Governance | `CGController.approve_profile_update_evidence` | propose -> CG review -> teacher defer / evidence log，不允许 agent 直接 commit |
| 7. 失败与降级机制 | `CGDecision` + `_authorize_message` | 统一 `allow / sanitize / degrade / defer / deny` 五类治理动作 |
| 8. Tamper-evident Audit Chain | `AuditChain` | 每个 CG 决策写入 payload hash + previous hash + event hash，可验证篡改 |

## 核心文件

- `backend/app/protection/cg/protocol.py`
  - `MessageEnvelope`
  - `CapabilityRegistry`
  - `RiskScorer`
  - `BudgetManager`
  - `PolicyRouter`
  - `CGDecision`
  - `AuditChain`
- `backend/app/agents/agent_orchestrator.py`
  - `CGController` 接入 CG v2
  - agent request/response 均经过 envelope 和 policy router
  - `run_protected_flow` 返回 CG audit chain 与三层预算状态
- `backend/app/tests/test_cg_v2_protocol.py`
  - 覆盖 8 个升级点的核心行为

## 决策语义

```text
allow    : 放行
sanitize : 移除可净化的非传输字段后放行
degrade  : 降低上下文粒度，仅保留 bounded teaching fields
defer    : 进入教师或治理审核队列
deny     : 拒绝并记录审计事件
```

## Profile Update 生命周期

```text
LearningAssessmentAgent propose
        |
CG validate / risk / pollution check
        |
        +--> reject
        |
        +--> deferred_teacher_review
        |
        +--> evidence_logged_for_review
        |
Versioned profile commit  # 目前强制 direct_profile_update_performed=False
```

低置信度 update（默认 confidence < 0.6）会进入 `teacher_review_queue`，不允许直接写入画像。

## 预算机制

```text
round budget   : 单轮聚合披露
session budget : 同一会话多轮累计披露
student budget : 同一学生长期累计披露
```

`run_protected_flow(..., session_id=..., student_id=...)` 会返回：

```json
{
  "round": 0.0,
  "session": 0.0,
  "student": 0.0,
  "limits": {
    "round": 0.75,
    "session": 2.0,
    "student": 3.0
  }
}
```

## 审计链

每个事件包含：

```text
event_id
trace_id
message_id
round_id
sender
receiver
message_type
event_type
decision
policy_id
reason
risk_score
payload_hash
previous_hash
event_hash
timestamp
```

可通过：

```python
controller.verify_audit_chain()
```

验证链是否被篡改。

## 论文表述

可以写成：

> CG v2 introduces a protocol-level governance plane for multi-agent educational AI. Each inter-agent message is wrapped in a signed-structure envelope, authorized by a least-privilege capability registry, scored with field-level disclosure risk, constrained by round/session/student-level budgets, and bound to a tamper-evident audit chain. The policy router returns one of five governance actions: allow, sanitize, degrade, defer, or deny.

## 测试

```powershell
pytest backend/app/tests/test_cg_v2_protocol.py -q
pytest backend/app/tests -q --ignore=backend/app/tests/test_frontend_api_endpoints.py --ignore=backend/app/tests/test_classroom_dialogue_modes.py
```

当前结果：

```text
9 passed
39 passed
```
