"""模型反演攻击实现"""
from __future__ import annotations
from typing import Dict
import random
from protection.common.text_utils import cosine_text

class ModelInversionAttacker:
    """模型反演攻击器：尝试从模型输出反推敏感输入"""
    
    def __init__(self):
        self.sensitive_keywords = [
            "成绩", "家庭", "隐私", "错误", "弱点", 
            "grade", "family", "weakness", "mistake"
        ]
    
    def attack(self, sample: dict, system_response: str = None) -> float:
        """
        执行模型反演攻击
        
        Args:
            sample: 包含敏感信息的样本
            system_response: 系统的响应（如果有保护机制会被过滤）
        
        Returns:
            泄漏程度 [0-1]，越高表示反演越成功
        """
        if system_response is None:
            # 模拟系统响应
            system_response = self._simulate_system_response(sample)
        
        # 计算信息泄漏程度
        leakage = self._calculate_leakage(sample, system_response)
        return leakage
    
    def _simulate_system_response(self, sample: dict) -> str:
        """模拟系统响应（有/无保护）"""
        # 这里简化：从sample提取敏感内容
        sensitive_content = str(sample.get("content", ""))
        
        # 模拟有保护的情况：部分脱敏
        if random.random() < 0.8:  # 80%概率有保护
            return self._apply_protection(sensitive_content)
        else:
            return sensitive_content
    
    def _apply_protection(self, text: str) -> str:
        """应用保护机制（FOPD正交解耦）"""
        # 简化：移除敏感关键词
        protected = text
        for keyword in self.sensitive_keywords:
            protected = protected.replace(keyword, "[MASKED]")
        return protected[:len(text)//3]  # 只返回部分信息
    
    def _calculate_leakage(self, original: dict, response: str) -> float:
        """计算信息泄漏程度"""
        original_text = str(original.get("content", ""))
        
        # 使用余弦相似度衡量泄漏
        similarity = cosine_text(original_text, response)
        
        # 检查是否包含敏感关键词
        keyword_leakage = sum(
            1 for kw in self.sensitive_keywords 
            if kw in response.lower()
        ) / len(self.sensitive_keywords)
        
        # 综合评分
        leakage = 0.7 * similarity + 0.3 * keyword_leakage
        return min(1.0, leakage)
