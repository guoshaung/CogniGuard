# CogniGuard 三层闭环API接口文档

## 概述

本文档说明如何使用 `backend/app/contrasts/closed_loop.py` 中定义的三层闭环接口，实现学生画像保护、教师资源保护和审计追踪之间的安全数据交互。

## 核心设计原则

1. **隐私保护**：不直接传递原始学生画像或教师原文
2. **最小化原则**：只传递完成任务所需的最小必要信息
3. **策略治理**：通过TPCS决策控制层间数据流动
4. **可审计性**：所有交互均可追踪和审计

## 数据流向

```
用户请求
  ↓
[第1层] Student Profile (MM-FOPD) 
  ↓ MinimalContextCard
[TPCS] 策略决策 (allow/sanitize/degrade/refuse)
  ↓
[第2层] Teacher Resource (C2-RAG)
  ↓ Answer + ResourceFeedback
[TPCS] 策略决策
  ↓
[第3层] Audit Trace (HSW-ST)
  ↓ AuditSignal + AuditRecord
返回用户
  ↑
闭环反馈（第3层 → 第2层 → 第1层）
```

## 核心数据结构

### 1. MinimalContextCard (第1层输出)

最小化上下文卡片，传递学生学习需求的最小必要信息。

```python
from backend.app.contrasts.closed_loop import MinimalContextCard

context_card = MinimalContextCard(
    card_id="card_001",
    student_hash="hash_abc123",  # 学生ID的哈希值
    task_id="task_001",
    knowledge_point="高中数学-三角函数",
    student_level="中等",
    mastery_summary="基础概念掌握70%",
    ability_summary="逻辑推理能力中等",
    learning_behavior_summary="偏好视频学习",
    recommended_strategy="渐进式学习",
    resource_need="需要基础例题",
    modality_sensitivity={"text": 0.8, "image": 0.9},
    privacy_constraints=["不得暴露姓名"]
)
```

### 2. ResourceFeedback (第2层输出)

资源反馈信息，记录资源使用质量。

```python
from backend.app.contrasts.closed_loop import ResourceFeedback, ReturnMode

feedback = ResourceFeedback(
    task_id="task_001",
    resource_id="res_456",
    chunk_id="chunk_789",
    resource_difficulty="medium",
    knowledge_coverage=0.85,
    return_mode=ReturnMode.PARAPHRASE,
    variant_performance={"paraphrase_quality": 0.88},
    resource_fit_score=0.87,
    exposure_score=0.15  # 越低越安全
)
```

### 3. AuditSignal (第3层实时输出)

审计信号，实时检测风险。

```python
from backend.app.contrasts.closed_loop import (
    AuditSignal, RiskLevel, PolicyDecision, AuditStatus
)

signal = AuditSignal(
    answer_id="ans_001",
    watermark_id="wm_001",
    resource_trace_hash="trace_xyz",
    leakage_risk=RiskLevel.LOW,
    similarity_risk=0.12,
    multi_turn_reconstruction_risk=0.08,
    policy_decision=PolicyDecision.ALLOW,
    audit_status=AuditStatus.NORMAL
)
```

### 4. AuditRecord (第3层持久化输出)

审计记录，形成区块链式审计链。

```python
from backend.app.contrasts.closed_loop import AuditRecord

record = AuditRecord(
    audit_id="audit_001",
    answer_id="ans_001",
    student_id_hash="hash_abc123",
    resource_id="res_456",
    chunk_id="chunk_789",
    return_mode=ReturnMode.PARAPHRASE,
    copyright_level="medium",
    exposure_score=0.15,
    watermark_id="wm_001",
    policy_decision=PolicyDecision.ALLOW,
    previous_hash="prev_hash_xyz"  # 前一条记录的哈希
)
record.audit_hash = record.compute_hash()
```

### 5. TPCSDecision (横向治理层)

TPCS策略决策，控制层间数据流动。

```python
from backend.app.contrasts.closed_loop import TPCSDecision

decision = TPCSDecision(
    decision_id="decision_001",
    sender_layer="layer1_student_profile",
    receiver_layer="layer2_teacher_resource",
    action="query_resource",
    allow=True,
    sanitize=False,
    degrade=False,
    refuse=False,
    encryption_required=False,
    reason="正常请求"
)
```

## 闭环交互接口

### 接口1: 第1层 → 第2层

```python
from backend.app.contrasts.closed_loop import ClosedLoopInterface

# TPCS决策
tpcs_decision = TPCSDecision(...)

# 传递上下文卡片
data = ClosedLoopInterface.layer1_to_layer2(
    context_card=context_card,
    tpcs_decision=tpcs_decision
)

if data is None:
    # 请求被阻断
    print("请求被TPCS策略阻断")
else:
    # 第2层可以使用这些数据进行资源检索
    print(f"知识点: {data['knowledge_point']}")
```

### 接口2: 第2层 → 第3层

```python
# 传递答案和资源反馈
data = ClosedLoopInterface.layer2_to_layer3(
    answer="这是生成的答案...",
    resource_feedback=feedback,
    tpcs_decision=tpcs_decision
)

if data:
    # 第3层进行审计
    answer = data['answer']
    feedback_info = data['resource_feedback']
```

### 接口3: 第3层 → 第2层 (闭环反馈)

```python
# 审计结果反馈到第2层
data = ClosedLoopInterface.layer3_feedback_to_layer2(
    audit_signal=signal,
    tpcs_decision=tpcs_decision
)

if data:
    # 第2层根据审计信号调整策略
    if data['audit_status'] == 'warning':
        print("需要调整资源生成策略")
```

### 接口4: 第2层 → 第1层 (闭环反馈)

```python
# 资源使用反馈到第1层
data = ClosedLoopInterface.layer2_feedback_to_layer1(
    resource_feedback=feedback,
    tpcs_decision=tpcs_decision
)

if data:
    # 第1层根据反馈优化画像
    fit_score = data['resource_fit_score']
    print(f"资源适配度: {fit_score}")
```

## 完整使用流程

```python
from backend.app.contrasts.closed_loop import *

# 步骤1: 第1层生成最小化上下文卡片
context_card = MinimalContextCard(...)

# 步骤2: TPCS决策 (第1层 → 第2层)
tpcs_decision_1to2 = TPCSDecision(
    decision_id="dec_001",
    sender_layer="layer1_student_profile",
    receiver_layer="layer2_teacher_resource",
    action="query_resource",
    allow=True
)

# 步骤3: 传递到第2层
layer2_input = ClosedLoopInterface.layer1_to_layer2(
    context_card, tpcs_decision_1to2
)

if layer2_input:
    # 步骤4: 第2层处理并生成反馈
    answer = "生成的答案..."
    feedback = ResourceFeedback(...)
    
    # 步骤5: TPCS决策 (第2层 → 第3层)
    tpcs_decision_2to3 = TPCSDecision(
        decision_id="dec_002",
        sender_layer="layer2_teacher_resource",
        receiver_layer="layer3_audit_trace",
        action="submit_answer",
        allow=True
    )
    
    # 步骤6: 传递到第3层
    layer3_input = ClosedLoopInterface.layer2_to_layer3(
        answer, feedback, tpcs_decision_2to3
    )
    
    if layer3_input:
        # 步骤7: 第3层审计
        signal = AuditSignal(...)
        record = AuditRecord(...)
        record.audit_hash = record.compute_hash()
        
        # 步骤8: 闭环反馈
        # 第3层 → 第2层
        audit_feedback = ClosedLoopInterface.layer3_feedback_to_layer2(
            signal, tpcs_decision
        )
        
        # 第2层 → 第1层
        resource_feedback_to_layer1 = ClosedLoopInterface.layer2_feedback_to_layer1(
            feedback, tpcs_decision
        )
```

## TPCS策略决策场景

### 场景1: 正常通过
```python
decision = TPCSDecision(
    decision_id="dec_001",
    sender_layer="layer1",
    receiver_layer="layer2",
    action="query_resource",
    allow=True,
    reason="正常请求"
)
```

### 场景2: 需要脱敏
```python
decision = TPCSDecision(
    decision_id="dec_002",
    sender_layer="layer1",
    receiver_layer="layer2",
    action="query_resource",
    allow=True,
    sanitize=True,  # 触发脱敏
    reason="包含敏感信息，需要脱敏处理"
)
```

### 场景3: 降级服务
```python
decision = TPCSDecision(
    decision_id="dec_003",
    sender_layer="layer2",
    receiver_layer="layer3",
    action="return_answer",
    allow=True,
    degrade=True,  # 触发降级
    reason="检测到高风险，降级返回"
)
```

### 场景4: 拒绝请求
```python
decision = TPCSDecision(
    decision_id="dec_004",
    sender_layer="layer1",
    receiver_layer="layer2",
    action="query_resource",
    allow=False,
    refuse=True,  # 拒绝
    reason="违反隐私策略"
)
```

## 枚举类型说明

### ReturnMode (资源返回模式)
- `ORIGINAL`: 原始文本
- `PARAPHRASE`: 改写版本（推荐）
- `SUMMARY`: 摘要版本
- `REFERENCE`: 仅引用

### PolicyDecision (策略决策)
- `ALLOW`: 允许
- `SANITIZE`: 脱敏处理
- `DEGRADE`: 降级服务
- `REFUSE`: 拒绝请求

### AuditStatus (审计状态)
- `PENDING`: 待审计
- `NORMAL`: 正常
- `WARNING`: 警告
- `ALERT`: 告警
- `BLOCKED`: 已阻断

### RiskLevel (风险等级)
- `LOW`: 低风险
- `MEDIUM`: 中风险
- `HIGH`: 高风险
- `CRITICAL`: 严重风险

## 最佳实践

### 1. 隐私保护
- 始终使用 `student_hash` 而非原始学生ID
- 在 `MinimalContextCard` 中只包含必要的摘要信息
- 设置合理的 `privacy_constraints`

### 2. 版权保护
- 优先使用 `ReturnMode.PARAPHRASE` 或 `SUMMARY`
- 监控 `exposure_score`，保持在低水平 (< 0.3)
- 根据 `copyright_level` 选择合适的返回模式

### 3. 审计追踪
- 为每条记录计算 `audit_hash`
- 使用 `previous_hash` 形成区块链式审计链
- 持久化存储所有 `AuditRecord`

### 4. TPCS策略
- 在每次层间交互前都要进行TPCS决策
- 根据决策结果进行相应的处理（脱敏/降级/拒绝）
- 记录决策理由便于审计

## 集成到现有系统

### 在第1层 (protection/student_profile/) 中使用

```python
# 在你的学生画像保护模块中
from backend.app.contrasts.closed_loop import MinimalContextCard

def generate_minimal_context(student_profile, task):
    """从完整学生画像生成最小化上下文卡片"""
    return MinimalContextCard(
        card_id=f"card_{task.id}",
        student_hash=hash_student_id(student_profile.id),
        task_id=task.id,
        # ... 填充其他字段
    )
```

### 在第2层 (protection/teacher_resource/) 中使用

```python
# 在你的资源保护模块中
from backend.app.contrasts.closed_loop import ResourceFeedback, ReturnMode

def generate_resource_feedback(resource, variant):
    """生成资源反馈"""
    return ResourceFeedback(
        task_id=resource.task_id,
        resource_id=resource.id,
        chunk_id=resource.chunk_id,
        return_mode=ReturnMode.PARAPHRASE,
        # ... 填充其他字段
    )
```

### 在第3层 (protection/audit_trace/) 中使用

```python
# 在你的审计追踪模块中
from backend.app.contrasts.closed_loop import AuditSignal, AuditRecord

def create_audit_record(answer, resource, watermark):
    """创建审计记录"""
    record = AuditRecord(
        audit_id=generate_audit_id(),
        answer_id=answer.id,
        # ... 填充其他字段
    )
    record.audit_hash = record.compute_hash()
    return record
```

## 测试

运行示例代码测试接口：

```bash
python backend/app/contrasts/closed_loop.py
```

预期输出：
```
✅ 三层闭环接口示例运行成功！
上下文卡片: card_001
资源反馈: 适配度=0.87
审计状态: normal
```

## 相关文档

- [架构重构建议](./架构重构建议.md) - 整体架构设计
- `protection/student_profile/` - 第1层实现
- `protection/teacher_resource/` - 第2层实现
- `protection/audit_trace/` - 第3层实现
- `protection/tpcs_guardrails/` - TPCS治理层实现
