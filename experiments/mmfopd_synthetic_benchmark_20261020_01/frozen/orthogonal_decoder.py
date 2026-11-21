"""正交解耦机制：将画像分解为知识、策略、敏感三个正交子空间"""
from __future__ import annotations
import math
from protection.common.schemas import ProfileRecord
from protection.student_profile.src.fopd.multimodal_profile import OrthogonalRepresentation

class OrthogonalDecoder:
    """正交解耦器：knowledge ⊥ strategy ⊥ sensitive"""
    
    def __init__(self, config: dict):
        cfg = config.get("fopd", {}).get("orthogonal", {})
        self.dim = int(cfg.get("vector_dim", 32))
        self.sensitive_keywords = set(cfg.get("sensitive_keywords", [
            "家庭", "父母", "收入", "地址", "学校名", "姓名", "身份证"
        ]))
    
    def decompose(self, records: list[ProfileRecord]) -> OrthogonalRepresentation:
        """将profile_records分解为三个正交向量"""
        knowledge_vec = [0.0] * self.dim
        strategy_vec = [0.0] * self.dim
        sensitive_vec = [0.0] * self.dim
        
        for i, record in enumerate(records[:self.dim]):
            idx = i % self.dim
            
            # 知识维度：mastery类型
            if record.type == "mastery":
                try:
                    knowledge_vec[idx] = float(record.value)
                except:
                    knowledge_vec[idx] = 0.5
            
            # 策略维度：preference和error_pattern
            if record.type in ("preference", "error_pattern"):
                strategy_vec[idx] = record.confidence
            
            # 敏感维度：检测敏感信息
            if self._is_sensitive(record):
                sensitive_vec[idx] = record.sensitivity
        
        # 归一化
        knowledge_vec = self._normalize(knowledge_vec)
        strategy_vec = self._normalize(strategy_vec)
        sensitive_vec = self._normalize(sensitive_vec)
        
        return OrthogonalRepresentation(
            knowledge_vector=knowledge_vec,
            strategy_vector=strategy_vec,
            sensitive_vector=sensitive_vec
        )
    
    def _is_sensitive(self, record: ProfileRecord) -> bool:
        """判断是否包含敏感信息"""
        text = record.text().lower()
        return any(kw in text for kw in self.sensitive_keywords) or record.sensitivity > 0.7
    
    def _normalize(self, vec: list[float]) -> list[float]:
        """L2归一化"""
        norm = math.sqrt(sum(x*x for x in vec))
        return [x / norm if norm > 0 else 0.0 for x in vec]
    
    def project_to_task(self, ortho: OrthogonalRepresentation, task_embedding: list[float]) -> list[float]:
        """任务相关投影：仅保留与任务相关的知识+策略"""
        # 简化版：加权组合知识和策略，忽略敏感
        if len(task_embedding) != self.dim:
            task_embedding = task_embedding[:self.dim] + [0.0] * (self.dim - len(task_embedding))
        
        result = []
        for i in range(self.dim):
            task_weight = abs(task_embedding[i]) if i < len(task_embedding) else 0.0
            combined = 0.7 * ortho.knowledge_vector[i] + 0.3 * ortho.strategy_vector[i]
            result.append(combined * task_weight)
        
        return self._normalize(result)
