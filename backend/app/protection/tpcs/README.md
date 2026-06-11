# TPCS策略引擎

## 概述

TPCS（跨层策略控制系统）策略引擎是CogniGuard三层保护机制的横向治理层，负责：

1. **跨层策略决策**：控制三层之间的数据流动
2. **风险评估与响应**：实时评估风险并做出策略决策
3. **策略日志记录**：记录所有策略决策用于审计追踪

## 架构位置

```
┌──────────────────────────────────────────────────────┐
│                  TPCS Guardrails                      │
│              (横向治理层 - 本模块)                     │
│                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ 策略引擎    │  │  NeMo         │  │  策略日志   │ │
│  │PolicyEngine │  │  Guardrails  │  │  Logging    │ │
│  └─────────────┘  └──────────────┘  └─────────────┘ │
└──────────────────────────────────────────────────────┘
         ↓                ↓                ↓
┌────────────────────────────────────────────────────┐
│              三层保护机制                           │
├────────────────────────────────────────────────────┤
│ 第1层: Student Profile (学生画像保护)              │
│ 第2层: Teacher Resource (教师资源保护)             │
│ 第3层: Audit Trace (审计追踪保护)                  │
└────────────────────────────────────────────────────┘
```

## 核心功能

### 1. 策略规则

策略引擎实现了5条核心规则：

#### 规则1: 高模态敏感度监控
- **触发条件**：`modality_sensitivity` 中任何模态 > 0.8
- **响应**：`audit_required = True`
- **目的**：对高敏感度模态（如手写、音频）进行额外审计

#### 规则2: 资源暴露度控制
- **触发条件**：`exposure_score > 0.4`
- **响应**：`degrade = True`
- **目的**：降低资源暴露风险，保护版权

#### 规则3: 重构风险防护
- **触发条件**：
  - Critical: `multi_turn_reconstruction_risk >= 0.8` → `refuse = True`
  - High: `multi_turn_reconstruction_risk >= 0.5` → `degrade = True`
- **目的**：防止多轮对话重构原始资源

#### 规则4: 画像更新冲突检测
- **触发条件**：`resource_fit_score < 0.3`（资源与学生画像不匹配）
- **响应**：`quarantine = True`
- **目的**：隔离可能污染学生画像的低质量数据

#### 规则5: 机器遗忘
- **触发条件**：`action == "machine_forgetting_requested"`
- **响应**：`revoke_records = True`
- **目的**：支持用户的数据删除权

### 2. 策略决策输出

策略引擎返回 `TPCSPolicyDecision` 对象，包含：

```python
@dataclass
class TPCSPolicyDecision:
    decision_id: str              # 决策唯一标识
    allow: bool                   # 是否允许操作
    audit_required: bool          # 是否需要审计
    degrade: bool                 # 是否降级服务
    quarantine: bool              # 是否隔离数据
    refuse: bool                  # 是否拒绝请求
    revoke_records: bool          # 是否撤销记录
    reason: str                   # 决策理由
    timestamp: datetime           # 决策时间戳
```

## 使用方法

### 基本使用

```python
from backend.app.protection.tpcs.policy_engine import TPCSPolicyEngine
from backend.app.contrasts.closed_loop import MinimalContextCard

# 初始化策略引擎
engine = TPCSPolicyEngine(
    policy_log_path='data/logs/tpcs_policy.jsonl'
)

# 评估上下文卡片
context_card = MinimalContextCard(
    card_id='card_001',
    student_hash='student_hash_123',
    task_id='task_001',
    knowledge_point='math.algebra',
    student_level='medium',
    mastery_summary='掌握基础概念',
    ability_summary='中等逻辑能力',
    learning_behavior_summary='偏好文本学习',
    recommended_strategy='循序渐进',
    resource_need='基础例题',
    modality_sensitivity={'handwriting': 0.9, 'audio': 0.5}
)

# 执行策略评估
decision = engine.evaluate(
    context_card=context_card,
    sender_layer='student_profile',
    receiver_layer='teacher_resource',
    action='query_resource'
)

# 根据决策采取行动
if decision.refuse:
    # 拒绝请求
    return {"error": "Request refused", "reason": decision.reason}
elif decision.degrade:
    # 降级服务
    return get_degraded_response()
elif decision.audit_required:
    # 标记需要审计
    mark_for_audit(decision)
```

### 综合评估

策略引擎可以同时评估多个层的数据：

```python
from backend.app.contrasts.closed_loop import (
    MinimalContextCard, ResourceFeedback, AuditSignal
)

# 综合评估三层数据
decision = engine.evaluate(
    context_card=context_card,        # 第1层
    resource_feedback=feedback,       # 第2层
    audit_signal=signal,              # 第3层
    sender_layer='orchestrator',
    receiver_layer='user',
    action='return_answer'
)

# 决策会考虑所有层的风险因素
if decision.refuse:
    # 阻止答案返回
    block_response()
elif decision.degrade:
    # 返回降级版本
    return degraded_answer()
elif decision.quarantine:
    # 隔离数据，不更新画像
    save_without_profile_update()
```

## API集成示例

### 在FastAPI中使用

```python
from fastapi import APIRouter, HTTPException
from backend.app.protection.tpcs.policy_engine import TPCSPolicyEngine

router = APIRouter()
tpcs_engine = TPCSPolicyEngine()

@router.post("/query")
async def query_with_protection(
    student_id: str,
    question: str
):
    # 1. 获取学生上下文卡片
    context_card = get_student_context(student_id, question)
    
    # 2. TPCS策略检查
    decision = tpcs_engine.evaluate(
        context_card=context_card,
        sender_layer='student_profile',
        receiver_layer='teacher_resource',
        action='query_resource'
    )
    
    if decision.refuse:
        raise HTTPException(
            status_code=403,
            detail=f"Request refused: {decision.reason}"
        )
    
    # 3. 查询资源
    resources = query_resources(context_card)
    
    # 4. 根据决策调整返回
    if decision.degrade:
        resources = degrade_resources(resources)
    
    if decision.audit_required:
        log_for_audit(decision)
    
    return {"resources": resources}
```

## 策略日志

所有策略决策都会记录到日志文件中，格式为JSONL：

```json
{
  "decision_id": "dec_20260609_001",
  "timestamp": "2026-06-09T18:45:00",
  "sender_layer": "student_profile",
  "receiver_layer": "teacher_resource",
  "action": "query_resource",
  "context_summary": {
    "student_hash": "hash_123",
    "knowledge_point": "math.algebra",
    "modality_sensitivity": {"handwriting": 0.9}
  },
  "decision": {
    "allow": true,
    "audit_required": true,
    "degrade": false,
    "refuse": false
  },
  "reason": "High modality sensitivity detected: handwriting=0.90 > 0.80"
}
```

日志可用于：
- **审计追溯**：追踪每个决策的依据
- **策略优化**：分析决策模式，优化规则
- **合规证明**：证明系统遵守隐私和版权规则

## 测试

运行单元测试：

```bash
# 运行所有测试
python backend/app/protection/tpcs/test_policy_engine.py

# 使用pytest（推荐）
pytest backend/app/protection/tpcs/test_policy_engine.py -v

# 运行特定测试
pytest backend/app/protection/tpcs/test_policy_engine.py::TestTPCSPolicyEngine::test_rule1_high_modality_sensitivity -v
```

测试覆盖：
- ✅ 规则1: 高模态敏感度监控
- ✅ 规则2: 资源暴露度控制
- ✅ 规则3: 重构风险防护（Critical & High）
- ✅ 规则4: 画像更新冲突检测
- ✅ 规则5: 机器遗忘
- ✅ 多规则组合场景
- ✅ 无触发正常流程

## 配置

策略引擎支持自定义阈值：

```python
engine = TPCSPolicyEngine(
    policy_log_path='data/logs/tpcs.jsonl',
    config={
        'modality_sensitivity_threshold': 0.8,
        'exposure_score_threshold': 0.4,
        'reconstruction_risk_critical': 0.8,
        'reconstruction_risk_high': 0.5,
        'resource_fit_threshold': 0.3
    }
)
```

## 与NeMo Guardrails集成

TPCS策略引擎可以与NVIDIA NeMo Guardrails集成，提供更强大的对话安全保护：

```python
from nemoguardrails import RailsConfig, LLMRails
from backend.app.protection.tpcs.policy_engine import TPCSPolicyEngine

# 加载NeMo配置
config = RailsConfig.from_path("./guardrails/cogniguard/config")
rails = LLMRails(config)

# 结合TPCS策略
tpcs_engine = TPCSPolicyEngine()

# 在对话流程中使用
async def protected_query(user_message: str):
    # 1. NeMo Guardrails检查输入
    safe_input = await rails.execute_action("check_input", user_message)
    
    # 2. TPCS策略检查
    decision = tpcs_engine.evaluate(...)
    
    if decision.refuse:
        return "抱歉，无法处理该请求"
    
    # 3. 处理请求
    response = await process_query(safe_input)
    
    # 4. NeMo Guardrails检查输出
    safe_output = await rails.execute_action("check_output", response)
    
    return safe_output
```

## 未来扩展

计划中的功能：
1. **动态策略学习**：基于反馈自动调整阈值
2. **联邦策略共享**：多机构间共享匿名化的策略模式
3. **可解释性增强**：提供更详细的决策解释
4. **A/B测试支持**：对比不同策略配置的效果

## 相关文档

- [三层闭环接口文档](../../../docs/三层闭环API接口文档.md)
- [NeMo Guardrails配置](../../../guardrails/cogniguard/README.md)
- [审计追踪系统](../audit/README.md)

## 联系与贡献

有问题或建议？欢迎提Issue或PR！
