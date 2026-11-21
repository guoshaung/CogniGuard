# CogniGuard Core 职责拆分

## 状态

本轮完成职责下沉，但尚未执行旧 `CG` 公共名称的全面重命名。旧 API 继续作为兼容入口，待新控制平面名称确定后统一迁移。

## 领域所有权

| 能力 | 新所有者 | 实现入口 |
|---|---|---|
| 隐私预算、选择成本、实际画像披露 | MM-FOPD | `protection/student_profile/src/fopd/privacy_budget.py` |
| 版权预算、重构历史、候选粒度与版权域选择 | C²-RAG | `experiments/c2rag_v3/core.py`、`policy_selector.py` |
| 水印强度、检测证据、关键内容恢复与来源恢复 | HSW-ST | `protection/audit_trace/src/watermark_policy.py` |
| Evidence Envelope、Capability、Principal/Purpose、Context Boundary、Trust、Audit、Rollback、Lifecycle Hooks | CogniGuard Core | `core/governance/` |

## CogniGuard Core 不再拥有的能力

```text
不计算画像暴露成本
不计算版权重构成本
不选择水印强度
不维护领域预算
不生成领域候选内容
```

Core 只读取三个领域模块提交的 `DomainEvidence`，处理能力路由、上下文边界、跨域冲突、信任、审计和安全回滚。

## 兼容策略

- `experiments/c2rag_v3/cg_bridge.py` 已降为 deprecated wrapper；主实现位于 `policy_selector.py`。
- 旧 `backend/app/protection/cg/` 与 `CGController` 暂时保留，防止生产 API、前端和历史实验失效。
- 旧实验结果和归档文档不会重写名称，以保证原始证据可追溯。
- 新名称确定后，再迁移公开类名、目录、前端标签和当前文档。

## 目标调用链

```text
Input Hook
    ↓
MM-FOPD → PrivacyEvidence
    ↓
C²-RAG → CopyrightEvidence + controlled content
    ↓
HSW-ST → WatermarkEvidence + provenance binding
    ↓
CogniGuard Core LifecycleGuard
    capability / context boundary / cross-domain conflict
    trust / audit / rollback
    ↓
Output Hook
```
