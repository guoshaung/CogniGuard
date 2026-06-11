"""
TPCS策略引擎 - 横向治理控制器

处理三层输入并输出TPCSDecision，包含5种核心策略规则
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

# 导入闭环接口定义
import sys
sys.path.insert(0, 'backend/app/contrasts')
from closed_loop import (
    MinimalContextCard, ResourceFeedback, AuditSignal,
    TPCSDecision, ReturnMode, PolicyDecision, RiskLevel
)


class TPCSPolicyEngine:
    """TPCS策略引擎 - 横向治理控制器"""
    
    def __init__(self, policy_log_path: Optional[str] = None):
        self.policy_log_path = policy_log_path or 'data/processed/tpcs_policy_decisions.jsonl'
        Path(self.policy_log_path).parent.mkdir(parents=True, exist_ok=True)
    
    def evaluate(
        self,
        context_card: Optional[MinimalContextCard] = None,
        resource_feedback: Optional[ResourceFeedback] = None,
        audit_signal: Optional[AuditSignal] = None,
        action: str = 'unknown',
        sender_layer: str = 'unknown',
        receiver_layer: str = 'unknown'
    ) -> TPCSDecision:
        """评估策略并返回决策"""
        
        decision_id = f'tpcs_{uuid.uuid4().hex[:12]}'
        
        # 初始化决策
        decision = TPCSDecision(
            decision_id=decision_id,
            sender_layer=sender_layer,
            receiver_layer=receiver_layer,
            action=action,
            allow=True,
            sanitize=False,
            degrade=False,
            refuse=False,
            encryption_required=False,
            reason=''
        )
        
        reasons = []
        
        # 规则1: 模态敏感度检查
        if context_card:
            result = self._check_modality_sensitivity(context_card)
            if result['triggered']:
                decision.audit_required = True
                reasons.append(result['reason'])
        
        # 规则2: 暴露度检查
        if resource_feedback:
            result = self._check_exposure_score(resource_feedback)
            if result['triggered']:
                decision.degrade = True
                reasons.append(result['reason'])
        
        # 规则3: 多轮重构风险检查
        if audit_signal:
            result = self._check_reconstruction_risk(audit_signal)
            if result['triggered']:
                if result['severity'] == 'critical':
                    decision.refuse = True
                    decision.allow = False
                else:
                    decision.degrade = True
                reasons.append(result['reason'])
        
        # 规则4: 画像更新冲突检查
        if context_card and resource_feedback:
            result = self._check_profile_update_conflict(context_card, resource_feedback)
            if result['triggered']:
                decision.quarantine = True
                reasons.append(result['reason'])
        
        # 规则5: 机器遗忘请求检查
        if action == 'machine_forgetting_requested':
            result = self._check_machine_forgetting()
            if result['triggered']:
                decision.revoke_records = True
                reasons.append(result['reason'])
        
        decision.reason = ' | '.join(reasons) if reasons else 'Policy check passed'
        
        # 记录决策日志
        self._log_decision(decision, context_card, resource_feedback, audit_signal)
        
        return decision
    
    def _check_modality_sensitivity(self, context_card: MinimalContextCard) -> Dict[str, Any]:
        """规则1: 如果modality_sensitivity高，则audit_scope降低粒度"""
        max_sensitivity = max(context_card.modality_sensitivity.values())
        
        if max_sensitivity > 0.8:
            return {
                'triggered': True,
                'reason': f'High modality sensitivity ({max_sensitivity:.2f}), audit scope reduced to hash/label only'
            }
        return {'triggered': False}
    
    def _check_exposure_score(self, feedback: ResourceFeedback) -> Dict[str, Any]:
        """规则2: 如果exposure_score高，则C2-RAG return_mode降级"""
        if feedback.exposure_score > 0.3:
            return {
                'triggered': True,
                'reason': f'High exposure score ({feedback.exposure_score:.2f}), degrading return mode'
            }
        return {'triggered': False}
    
    def _check_reconstruction_risk(self, signal: AuditSignal) -> Dict[str, Any]:
        """规则3: 如果multi_turn_reconstruction_risk高，则refuse或variant"""
        if signal.multi_turn_reconstruction_risk > 0.7:
            return {
                'triggered': True,
                'severity': 'critical',
                'reason': f'Critical reconstruction risk ({signal.multi_turn_reconstruction_risk:.2f}), refusing request'
            }
        elif signal.multi_turn_reconstruction_risk > 0.5:
            return {
                'triggered': True,
                'severity': 'high',
                'reason': f'High reconstruction risk ({signal.multi_turn_reconstruction_risk:.2f}), requiring variant'
            }
        return {'triggered': False}
    
    def _check_profile_update_conflict(
        self, context_card: MinimalContextCard, feedback: ResourceFeedback
    ) -> Dict[str, Any]:
        """规则4: 如果profile update与assessment evidence冲突，则quarantine"""
        # 简化检查：如果资源适配度很低但继续更新画像，则标记冲突
        if feedback.resource_fit_score < 0.3:
            return {
                'triggered': True,
                'reason': f'Profile update conflict: low resource fit ({feedback.resource_fit_score:.2f}), quarantining update'
            }
        return {'triggered': False}
    
    def _check_machine_forgetting(self) -> Dict[str, Any]:
        """规则5: 如果machine_forgetting_requested，则标记revoked/expired"""
        return {
            'triggered': True,
            'reason': 'Machine forgetting requested, marking records as revoked/expired'
        }
    
    def _log_decision(
        self,
        decision: TPCSDecision,
        context_card: Optional[MinimalContextCard],
        resource_feedback: Optional[ResourceFeedback],
        audit_signal: Optional[AuditSignal]
    ) -> None:
        """记录策略决策日志"""
        log_entry = {
            'decision': decision.to_dict(),
            'inputs': {
                'context_card': context_card.to_dict() if context_card else None,
                'resource_feedback': resource_feedback.to_dict() if resource_feedback else None,
                'audit_signal': audit_signal.to_dict() if audit_signal else None
            },
            'timestamp': datetime.now().isoformat()
        }
        
        with open(self.policy_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')


# 为TPCSDecision添加额外属性
TPCSDecision.audit_required = False
TPCSDecision.quarantine = False
TPCSDecision.revoke_records = False
