"""
CogniGuard 三层闭环接口定义

本模块定义了三层保护机制之间的数据交互接口，确保：
1. 不直接传递原始学生画像或教师原文（隐私保护）
2. 只传递最小必要的上下文信息（最小化原则）
3. 支持审计追踪和策略决策（TPCS治理）

三层架构：
- 第1层（Student Profile）: 学生画像保护 → 输出 MinimalContextCard
- 第2层（Teacher Resource）: 教师资源保护 → 输出 ResourceFeedback + 答案
- 第3层（Audit Trace）: 审计追踪保护 → 输出 AuditSignal + AuditRecord
- 横向治理（TPCS Guardrails）: 跨层策略控制 → 输出 TPCSDecision
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ==================== 枚举类型定义 ====================

class ReturnMode(Enum):
    """资源返回模式"""
    ORIGINAL = "original"           # 原始文本
    PARAPHRASE = "paraphrase"       # 改写版本
    SUMMARY = "summary"             # 摘要版本
    REFERENCE = "reference"         # 仅引用


class PolicyDecision(Enum):
    """策略决策类型"""
    ALLOW = "allow"                 # 允许
    SANITIZE = "sanitize"           # 脱敏处理
    DEGRADE = "degrade"             # 降级服务
    REFUSE = "refuse"               # 拒绝请求


class AuditStatus(Enum):
    """审计状态"""
    PENDING = "pending"             # 待审计
    NORMAL = "normal"               # 正常
    WARNING = "warning"             # 警告
    ALERT = "alert"                 # 告警
    BLOCKED = "blocked"             # 已阻断


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ==================== 第1层：学生画像保护层 ====================

@dataclass
class MinimalContextCard:
    """
    最小化上下文卡片（第1层输出 → 第2层输入）
    
    功能：传递学生学习需求的最小必要信息，不包含原始画像
    来源：MM-FOPD算法处理后的隐私保护输出
    """
    # 必需字段
    card_id: str                                    # 卡片唯一标识
    student_hash: str                               # 学生ID的哈希值（隐私保护）
    task_id: str                                    # 任务ID
    knowledge_point: str                            # 知识点（如"高中数学-三角函数"）
    student_level: str                              # 学生水平（如"中等"）
    
    # 学习画像摘要（脱敏后）
    mastery_summary: str                            # 掌握度摘要（如"基础概念掌握70%"）
    ability_summary: str                            # 能力摘要（如"逻辑推理能力中等"）
    learning_behavior_summary: str                  # 学习行为摘要（如"偏好视频学习"）
    
    # 资源推荐参数
    recommended_strategy: str                       # 推荐策略（如"渐进式学习"）
    resource_need: str                              # 资源需求（如"需要基础例题"）
    modality_sensitivity: Dict[str, float]          # 模态敏感度 {"text": 0.8, "image": 0.6}
    
    # 隐私约束
    privacy_constraints: List[str] = field(default_factory=list)  # 隐私约束（如["不得暴露姓名", "不得暴露成绩"]）
    valid_scope: str = "current_task"               # 有效范围（如"current_task", "current_session"）
    
    # 元数据
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "card_id": self.card_id,
            "student_hash": self.student_hash,
            "task_id": self.task_id,
            "knowledge_point": self.knowledge_point,
            "student_level": self.student_level,
            "mastery_summary": self.mastery_summary,
            "ability_summary": self.ability_summary,
            "learning_behavior_summary": self.learning_behavior_summary,
            "recommended_strategy": self.recommended_strategy,
            "resource_need": self.resource_need,
            "modality_sensitivity": self.modality_sensitivity,
            "privacy_constraints": self.privacy_constraints,
            "valid_scope": self.valid_scope,
            "timestamp": self.timestamp.isoformat()
        }


# ==================== 第2层：教师资源保护层 ====================

@dataclass
class ResourceFeedback:
    """
    资源反馈信息（第2层输出 → 第1层/第3层输入）
    
    功能：记录资源检索和使用的质量信息，用于优化和审计
    来源：C2-RAG算法的版权保护输出
    """
    # 关联ID
    task_id: str                                    # 任务ID
    resource_id: str                                # 资源ID
    chunk_id: str                                   # 资源块ID
    
    # 资源质量评估
    resource_difficulty: str                        # 资源难度（如"medium"）
    knowledge_coverage: float                       # 知识覆盖度 [0, 1]
    return_mode: ReturnMode                         # 返回模式
    
    # 变体性能（版权保护）
    variant_performance: Dict[str, float]           # 变体性能 {"paraphrase_quality": 0.85, "similarity": 0.65}
    resource_fit_score: float                       # 资源适配度 [0, 1]
    exposure_score: float                           # 暴露度分数 [0, 1]（越低越安全）
    
    # 元数据
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "task_id": self.task_id,
            "resource_id": self.resource_id,
            "chunk_id": self.chunk_id,
            "resource_difficulty": self.resource_difficulty,
            "knowledge_coverage": self.knowledge_coverage,
            "return_mode": self.return_mode.value,
            "variant_performance": self.variant_performance,
            "resource_fit_score": self.resource_fit_score,
            "exposure_score": self.exposure_score,
            "timestamp": self.timestamp.isoformat()
        }


# ==================== 第3层：审计追踪保护层 ====================

@dataclass
class AuditSignal:
    """
    审计信号（第3层实时输出）
    
    功能：实时检测答案的风险信号，触发预警和阻断
    来源：HSW-ST水印检测和来源追踪算法
    """
    # 关联ID
    answer_id: str                                  # 答案ID
    watermark_id: str                               # 水印ID
    resource_trace_hash: str                        # 资源追踪哈希
    
    # 风险评估
    leakage_risk: RiskLevel                         # 泄露风险等级
    similarity_risk: float                          # 相似度风险 [0, 1]
    multi_turn_reconstruction_risk: float           # 多轮重构风险 [0, 1]
    
    # 决策和状态
    policy_decision: PolicyDecision                 # 策略决策
    audit_status: AuditStatus                       # 审计状态
    
    # 元数据
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "answer_id": self.answer_id,
            "watermark_id": self.watermark_id,
            "resource_trace_hash": self.resource_trace_hash,
            "leakage_risk": self.leakage_risk.value,
            "similarity_risk": self.similarity_risk,
            "multi_turn_reconstruction_risk": self.multi_turn_reconstruction_risk,
            "policy_decision": self.policy_decision.value,
            "audit_status": self.audit_status.value,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class AuditRecord:
    """
    审计记录（第3层持久化输出）
    
    功能：完整记录每次交互的审计信息，形成区块链式审计链
    来源：审计系统综合所有层的信息
    """
    # 唯一标识
    audit_id: str                                   # 审计记录ID
    
    # 关联信息
    answer_id: str                                  # 答案ID
    student_id_hash: str                            # 学生ID哈希
    resource_id: str                                # 资源ID
    chunk_id: str                                   # 资源块ID
    
    # 使用信息
    return_mode: ReturnMode                         # 返回模式
    copyright_level: str                            # 版权级别（如"high", "medium", "low"）
    exposure_score: float                           # 暴露度分数
    
    # 水印信息
    watermark_id: str                               # 水印ID
    
    # 策略决策
    policy_decision: PolicyDecision                 # 策略决策
    
    # 区块链式链接
    previous_hash: Optional[str] = None             # 前一条记录的哈希
    audit_hash: Optional[str] = None                # 当前记录的哈希
    
    # 元数据
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "audit_id": self.audit_id,
            "answer_id": self.answer_id,
            "student_id_hash": self.student_id_hash,
            "resource_id": self.resource_id,
            "chunk_id": self.chunk_id,
            "return_mode": self.return_mode.value,
            "copyright_level": self.copyright_level,
            "exposure_score": self.exposure_score,
            "watermark_id": self.watermark_id,
            "policy_decision": self.policy_decision.value,
            "previous_hash": self.previous_hash,
            "audit_hash": self.audit_hash,
            "timestamp": self.timestamp.isoformat()
        }
    
    def compute_hash(self) -> str:
        """计算当前记录的哈希值（用于区块链式链接）"""
        import hashlib
        import json
        
        # 排除 audit_hash 本身
        data = self.to_dict()
        data.pop("audit_hash", None)
        
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


# ==================== 横向治理：TPCS Guardrails ====================

@dataclass
class TPCSDecision:
    """
    TPCS策略决策（横向治理层输出）
    
    功能：控制层间数据流动和操作权限
    来源：NeMo Guardrails + TPCS策略引擎
    """
    # 唯一标识
    decision_id: str                                # 决策ID
    
    # 层间交互信息
    sender_layer: str                               # 发送层（如"layer1_student_profile"）
    receiver_layer: str                             # 接收层（如"layer2_teacher_resource"）
    action: str                                     # 动作（如"query_resource", "return_answer"）
    
    # 决策结果（可组合）
    allow: bool = True                              # 是否允许
    sanitize: bool = False                          # 是否需要脱敏
    degrade: bool = False                           # 是否降级
    refuse: bool = False                            # 是否拒绝
    encryption_required: bool = False               # 是否需要加密
    
    # 决策理由
    reason: str = ""                                # 决策理由
    
    # 元数据
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "decision_id": self.decision_id,
            "sender_layer": self.sender_layer,
            "receiver_layer": self.receiver_layer,
            "action": self.action,
            "allow": self.allow,
            "sanitize": self.sanitize,
            "degrade": self.degrade,
            "refuse": self.refuse,
            "encryption_required": self.encryption_required,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat()
        }
    
    @property
    def should_block(self) -> bool:
        """判断是否应该阻断"""
        return self.refuse or not self.allow


# ==================== 闭环交互接口 ====================

class ClosedLoopInterface:
    """
    三层闭环交互接口
    
    定义三层之间的标准交互流程和数据流向
    """
    
    @staticmethod
    def layer1_to_layer2(context_card: MinimalContextCard, tpcs_decision: TPCSDecision) -> Optional[Dict[str, Any]]:
        """
        第1层 → 第2层：传递学生上下文卡片
        
        Args:
            context_card: 最小化上下文卡片
            tpcs_decision: TPCS策略决策
            
        Returns:
            如果允许则返回卡片字典，否则返回None
        """
        if tpcs_decision.should_block:
            return None
        
        data = context_card.to_dict()
        
        # 如果需要脱敏，进一步处理
        if tpcs_decision.sanitize:
            data["mastery_summary"] = "[已脱敏]"
            data["ability_summary"] = "[已脱敏]"
            data["learning_behavior_summary"] = "[已脱敏]"
        
        return data
    
    @staticmethod
    def layer2_to_layer3(
        answer: str,
        resource_feedback: ResourceFeedback,
        tpcs_decision: TPCSDecision
    ) -> Optional[Dict[str, Any]]:
        """
        第2层 → 第3层：传递答案和资源反馈
        
        Args:
            answer: 生成的答案
            resource_feedback: 资源反馈
            tpcs_decision: TPCS策略决策
            
        Returns:
            如果允许则返回数据字典，否则返回None
        """
        if tpcs_decision.should_block:
            return None
        
        data = {
            "answer": answer,
            "resource_feedback": resource_feedback.to_dict()
        }
        
        # 如果需要降级，返回简化版本
        if tpcs_decision.degrade:
            data["answer"] = answer[:100] + "..."  # 截断答案
        
        return data
    
    @staticmethod
    def layer3_feedback_to_layer2(
        audit_signal: AuditSignal,
        tpcs_decision: TPCSDecision
    ) -> Optional[Dict[str, Any]]:
        """
        第3层 → 第2层：反馈审计信号（闭环）
        
        Args:
            audit_signal: 审计信号
            tpcs_decision: TPCS策略决策
            
        Returns:
            如果允许则返回审计信号字典，否则返回None
        """
        if tpcs_decision.should_block:
            return None
        
        return audit_signal.to_dict()
    
    @staticmethod
    def layer2_feedback_to_layer1(
        resource_feedback: ResourceFeedback,
        tpcs_decision: TPCSDecision
    ) -> Optional[Dict[str, Any]]:
        """
        第2层 → 第1层：反馈资源使用情况（闭环）
        
        Args:
            resource_feedback: 资源反馈
            tpcs_decision: TPCS策略决策
            
        Returns:
            如果允许则返回反馈字典，否则返回None
        """
        if tpcs_decision.should_block:
            return None
        
        # 只返回必要的优化信息
        return {
            "task_id": resource_feedback.task_id,
            "resource_fit_score": resource_feedback.resource_fit_score,
            "knowledge_coverage": resource_feedback.knowledge_coverage
        }


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 示例：完整的三层闭环流程
    
    # 1. 第1层生成最小化上下文卡片
    context_card = MinimalContextCard(
        card_id="card_001",
        student_hash="hash_student_123",
        task_id="task_001",
        knowledge_point="高中数学-三角函数",
        student_level="中等",
        mastery_summary="基础概念掌握70%，公式应用能力较弱",
        ability_summary="逻辑推理能力中等，空间想象力强",
        learning_behavior_summary="偏好视频学习，平均学习时长30分钟",
        recommended_strategy="渐进式学习，结合可视化",
        resource_need="需要基础例题和公式推导过程",
        modality_sensitivity={"text": 0.8, "image": 0.9, "video": 0.7},
        privacy_constraints=["不得暴露姓名", "不得暴露具体成绩"]
    )
    
    # 2. TPCS决策：第1层 → 第2层
    tpcs_decision_1to2 = TPCSDecision(
        decision_id="decision_001",
        sender_layer="layer1_student_profile",
        receiver_layer="layer2_teacher_resource",
        action="query_resource",
        allow=True,
        sanitize=False,
        reason="正常请求"
    )
    
    # 3. 第2层生成资源反馈
    resource_feedback = ResourceFeedback(
        task_id="task_001",
        resource_id="res_456",
        chunk_id="chunk_789",
        resource_difficulty="medium",
        knowledge_coverage=0.85,
        return_mode=ReturnMode.PARAPHRASE,
        variant_performance={"paraphrase_quality": 0.88, "similarity": 0.62},
        resource_fit_score=0.87,
        exposure_score=0.15
    )
    
    # 4. 第3层生成审计信号
    audit_signal = AuditSignal(
        answer_id="ans_001",
        watermark_id="wm_001",
        resource_trace_hash="trace_hash_xyz",
        leakage_risk=RiskLevel.LOW,
        similarity_risk=0.12,
        multi_turn_reconstruction_risk=0.08,
        policy_decision=PolicyDecision.ALLOW,
        audit_status=AuditStatus.NORMAL
    )
    
    # 5. 生成审计记录
    audit_record = AuditRecord(
        audit_id="audit_001",
        answer_id="ans_001",
        student_id_hash="hash_student_123",
        resource_id="res_456",
        chunk_id="chunk_789",
        return_mode=ReturnMode.PARAPHRASE,
        copyright_level="medium",
        exposure_score=0.15,
        watermark_id="wm_001",
        policy_decision=PolicyDecision.ALLOW
    )
    audit_record.audit_hash = audit_record.compute_hash()
    
    print("✅ 三层闭环接口示例运行成功！")
    print(f"上下文卡片: {context_card.card_id}")
    print(f"资源反馈: 适配度={resource_feedback.resource_fit_score:.2f}")
    print(f"审计状态: {audit_signal.audit_status.value}")
