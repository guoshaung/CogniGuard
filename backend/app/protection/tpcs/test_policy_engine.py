"""
TPCS策略引擎单元测试
"""
import unittest
import sys
import os
from pathlib import Path

# 添加路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.app.contrasts.closed_loop import (
    MinimalContextCard, ResourceFeedback, AuditSignal,
    TPCSDecision, ReturnMode, RiskLevel, PolicyDecision, AuditStatus
)
from backend.app.protection.tpcs.policy_engine import TPCSPolicyEngine


class TestTPCSPolicyEngine(unittest.TestCase):
    """测试TPCS策略引擎"""
    
    def setUp(self):
        """设置测试环境"""
        self.engine = TPCSPolicyEngine(policy_log_path='data/test/tpcs_test_log.jsonl')
    
    def test_rule1_high_modality_sensitivity(self):
        """测试规则1: 高模态敏感度触发audit_required"""
        context_card = MinimalContextCard(
            card_id='card_001',
            student_hash='student_001',
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
        
        decision = self.engine.evaluate(
            context_card=context_card,
            sender_layer='student_profile',
            receiver_layer='tpcs',
            action='request_context'
        )
        
        self.assertTrue(decision.allow)
        self.assertTrue(decision.audit_required)
        self.assertIn('High modality sensitivity', decision.reason)
    
    def test_rule1_low_modality_sensitivity(self):
        """测试规则1: 低模态敏感度不触发"""
        context_card = MinimalContextCard(
            card_id='card_002',
            student_hash='student_002',
            task_id='task_002',
            knowledge_point='math.geometry',
            student_level='medium',
            mastery_summary='掌握基础概念',
            ability_summary='中等逻辑能力',
            learning_behavior_summary='偏好视频学习',
            recommended_strategy='可视化学习',
            resource_need='图形例题',
            modality_sensitivity={'handwriting': 0.3, 'audio': 0.2}
        )
        
        decision = self.engine.evaluate(
            context_card=context_card,
            sender_layer='student_profile',
            receiver_layer='tpcs',
            action='request_context'
        )
        
        self.assertTrue(decision.allow)
        self.assertFalse(decision.audit_required)
    
    def test_rule2_high_exposure_score(self):
        """测试规则2: 高暴露度触发degrade"""
        feedback = ResourceFeedback(
            task_id='task_001',
            resource_id='res_001',
            chunk_id='chunk_001',
            resource_difficulty='medium',
            knowledge_coverage=0.8,
            return_mode=ReturnMode.ORIGINAL,
            variant_performance={'quality': 0.9},
            resource_fit_score=0.8,
            exposure_score=0.5
        )
        
        decision = self.engine.evaluate(
            resource_feedback=feedback,
            sender_layer='teacher_resource',
            receiver_layer='tpcs',
            action='return_resource'
        )
        
        self.assertTrue(decision.allow)
        self.assertTrue(decision.degrade)
        self.assertIn('High exposure score', decision.reason)
    
    def test_rule3_critical_reconstruction_risk(self):
        """测试规则3: 严重重构风险触发refuse"""
        signal = AuditSignal(
            answer_id='ans_001',
            watermark_id='wm_001',
            resource_trace_hash='trace_001',
            leakage_risk=RiskLevel.CRITICAL,
            similarity_risk=0.9,
            multi_turn_reconstruction_risk=0.85,
            policy_decision=PolicyDecision.REFUSE,
            audit_status=AuditStatus.BLOCKED
        )
        
        decision = self.engine.evaluate(
            audit_signal=signal,
            sender_layer='audit_trace',
            receiver_layer='tpcs',
            action='audit_check'
        )
        
        self.assertFalse(decision.allow)
        self.assertTrue(decision.refuse)
        self.assertIn('Critical reconstruction risk', decision.reason)
    
    def test_rule3_high_reconstruction_risk(self):
        """测试规则3: 高重构风险触发degrade"""
        signal = AuditSignal(
            answer_id='ans_002',
            watermark_id='wm_002',
            resource_trace_hash='trace_002',
            leakage_risk=RiskLevel.HIGH,
            similarity_risk=0.7,
            multi_turn_reconstruction_risk=0.6,
            policy_decision=PolicyDecision.DEGRADE,
            audit_status=AuditStatus.WARNING
        )
        
        decision = self.engine.evaluate(
            audit_signal=signal,
            sender_layer='audit_trace',
            receiver_layer='tpcs',
            action='audit_check'
        )
        
        self.assertTrue(decision.allow)
        self.assertTrue(decision.degrade)
        self.assertIn('High reconstruction risk', decision.reason)
    
    def test_rule4_profile_update_conflict(self):
        """测试规则4: 画像更新冲突触发quarantine"""
        context_card = MinimalContextCard(
            card_id='card_003',
            student_hash='student_003',
            task_id='task_003',
            knowledge_point='physics.mechanics',
            student_level='medium',
            mastery_summary='基础薄弱',
            ability_summary='需要加强',
            learning_behavior_summary='学习时间不足',
            recommended_strategy='强化训练',
            resource_need='基础讲解',
            modality_sensitivity={'handwriting': 0.5}
        )
        
        feedback = ResourceFeedback(
            task_id='task_003',
            resource_id='res_002',
            chunk_id='chunk_002',
            resource_difficulty='easy',
            knowledge_coverage=0.5,
            return_mode=ReturnMode.SUMMARY,
            variant_performance={'quality': 0.7},
            resource_fit_score=0.1,  # 很低的适配度
            exposure_score=0.2
        )
        
        decision = self.engine.evaluate(
            context_card=context_card,
            resource_feedback=feedback,
            sender_layer='student_profile',
            receiver_layer='tpcs',
            action='update_profile'
        )
        
        self.assertTrue(decision.allow)
        self.assertTrue(decision.quarantine)
        self.assertIn('Profile update conflict', decision.reason)
    
    def test_rule5_machine_forgetting(self):
        """测试规则5: 机器遗忘请求触发revoke_records"""
        decision = self.engine.evaluate(
            sender_layer='user',
            receiver_layer='tpcs',
            action='machine_forgetting_requested'
        )
        
        self.assertTrue(decision.allow)
        self.assertTrue(decision.revoke_records)
        self.assertIn('Machine forgetting requested', decision.reason)
    
    def test_combined_rules(self):
        """测试多规则组合"""
        context_card = MinimalContextCard(
            card_id='card_004',
            student_hash='student_004',
            task_id='task_004',
            knowledge_point='chemistry.reactions',
            student_level='advanced',
            mastery_summary='掌握较好',
            ability_summary='分析能力强',
            learning_behavior_summary='自主学习',
            recommended_strategy='深度学习',
            resource_need='高级习题',
            modality_sensitivity={'handwriting': 0.95, 'audio': 0.85}
        )
        
        feedback = ResourceFeedback(
            task_id='task_004',
            resource_id='res_003',
            chunk_id='chunk_003',
            resource_difficulty='hard',
            knowledge_coverage=0.9,
            return_mode=ReturnMode.ORIGINAL,
            variant_performance={'quality': 0.85},
            resource_fit_score=0.15,
            exposure_score=0.45
        )
        
        signal = AuditSignal(
            answer_id='ans_003',
            watermark_id='wm_003',
            resource_trace_hash='trace_003',
            leakage_risk=RiskLevel.HIGH,
            similarity_risk=0.75,
            multi_turn_reconstruction_risk=0.65,
            policy_decision=PolicyDecision.DEGRADE,
            audit_status=AuditStatus.WARNING
        )
        
        decision = self.engine.evaluate(
            context_card=context_card,
            resource_feedback=feedback,
            audit_signal=signal,
            sender_layer='orchestrator',
            receiver_layer='tpcs',
            action='full_check'
        )
        
        # 应该触发多个规则
        self.assertTrue(decision.allow)  # 没有达到critical级别
        self.assertTrue(decision.audit_required)  # 规则1
        self.assertTrue(decision.degrade)  # 规则2和3
        self.assertTrue(decision.quarantine)  # 规则4
        
        # 原因应该包含多个规则的描述
        self.assertIn('modality sensitivity', decision.reason)
        self.assertIn('exposure score', decision.reason)
        self.assertIn('reconstruction risk', decision.reason)
        self.assertIn('Profile update conflict', decision.reason)
    
    def test_no_triggers(self):
        """测试无触发情况"""
        context_card = MinimalContextCard(
            card_id='card_005',
            student_hash='student_005',
            task_id='task_005',
            knowledge_point='english.grammar',
            student_level='beginner',
            mastery_summary='开始学习',
            ability_summary='基础能力',
            learning_behavior_summary='积极学习',
            recommended_strategy='入门引导',
            resource_need='基础知识',
            modality_sensitivity={'handwriting': 0.2, 'audio': 0.1}
        )
        
        feedback = ResourceFeedback(
            task_id='task_005',
            resource_id='res_004',
            chunk_id='chunk_004',
            resource_difficulty='easy',
            knowledge_coverage=0.95,
            return_mode=ReturnMode.SUMMARY,
            variant_performance={'quality': 0.95},
            resource_fit_score=0.9,
            exposure_score=0.15
        )
        
        signal = AuditSignal(
            answer_id='ans_004',
            watermark_id='wm_004',
            resource_trace_hash='trace_004',
            leakage_risk=RiskLevel.LOW,
            similarity_risk=0.1,
            multi_turn_reconstruction_risk=0.2,
            policy_decision=PolicyDecision.ALLOW,
            audit_status=AuditStatus.NORMAL
        )
        
        decision = self.engine.evaluate(
            context_card=context_card,
            resource_feedback=feedback,
            audit_signal=signal,
            sender_layer='orchestrator',
            receiver_layer='tpcs',
            action='routine_check'
        )
        
        # 应该全部通过
        self.assertTrue(decision.allow)
        self.assertFalse(decision.audit_required)
        self.assertFalse(decision.degrade)
        self.assertFalse(decision.quarantine)
        self.assertFalse(decision.refuse)
        self.assertEqual(decision.reason, 'Policy check passed')


if __name__ == '__main__':
    unittest.main()
