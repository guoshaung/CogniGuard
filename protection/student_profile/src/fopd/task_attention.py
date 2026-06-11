"""任务相关注意力选择 + 信息瓶颈压缩"""
from __future__ import annotations
import math
from protection.common.schemas import Task, ProfileRecord

class TaskAttentionSelector:
    """任务相关注意力：动态选择最相关的画像维度"""
    
    def __init__(self, config: dict):
        cfg = config.get("fopd", {}).get("attention", {})
        self.temperature = float(cfg.get("temperature", 0.5))
        self.top_k = int(cfg.get("top_k_dimensions", 8))
    
    def compute_attention(self, task: Task, records: list[ProfileRecord]) -> list[tuple[int, float]]:
        """计算每个record对任务的注意力权重"""
        task_text = task.text().lower()
        scores: list[tuple[int, float]] = []
        
        for i, record in enumerate(records):
            # 任务相关性
            record_text = record.text().lower()
            relevance = self._text_overlap(task_text, record_text)
            
            # 知识点匹配
            knowledge_match = 1.0 if record.knowledge == task.knowledge else 0.3
            
            # 置信度
            confidence = record.confidence
            
            # 综合得分（softmax前）
            score = relevance * 0.5 + knowledge_match * 0.3 + confidence * 0.2
            scores.append((i, score))
        
        # Softmax归一化
        scores = self._softmax_scores(scores)
        
        # 返回top-k
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:self.top_k]
    
    def _text_overlap(self, text1: str, text2: str) -> float:
        """简单文本重叠度"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        if not words1 or not words2:
            return 0.0
        return len(words1 & words2) / len(words1 | words2)
    
    def _softmax_scores(self, scores: list[tuple[int, float]]) -> list[tuple[int, float]]:
        """Softmax归一化"""
        if not scores:
            return []
        max_score = max(s for _, s in scores)
        exp_scores = [(i, math.exp((s - max_score) / self.temperature)) for i, s in scores]
        total = sum(s for _, s in exp_scores)
        return [(i, s / total) for i, s in exp_scores]


class InformationBottleneck:
    """信息瓶颈：压缩画像到最小必要信息"""
    
    def __init__(self, config: dict):
        cfg = config.get("fopd", {}).get("bottleneck", {})
        self.max_bits = float(cfg.get("max_mutual_info_bits", 3.0))
        self.privacy_lambda = float(cfg.get("privacy_lambda", 0.5))
    
    def compress(self, selected_records: list[ProfileRecord], attention_weights: list[float]) -> list[ProfileRecord]:
        """信息瓶颈压缩：保留高权重、低敏感的记录"""
        compressed = []
        cumulative_info = 0.0
        
        for record, weight in zip(selected_records, attention_weights):
            # 计算信息量（简化：-log(p)）
            info_bits = -math.log2(weight + 1e-6)
            
            # 隐私代价
            privacy_cost = record.sensitivity * self.privacy_lambda
            
            # 决策：信息收益 vs 隐私代价
            if cumulative_info + info_bits <= self.max_bits and weight > privacy_cost:
                compressed.append(record)
                cumulative_info += info_bits
        
        return compressed
