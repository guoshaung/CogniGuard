"""多模态学生画像数据结构和处理"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class MultimodalProfile:
    """多模态学生画像"""
    student_id: str
    text_profile: dict[str, object]  # 文本画像（现有的profile_records）
    image_data: list[dict] = field(default_factory=list)  # 作业图片、手写识别
    audio_features: list[dict] = field(default_factory=list)  # 语音交互记录
    interaction_trace: list[dict] = field(default_factory=list)  # 操作轨迹
    timestamp: str = ""
    
    def to_dict(self) -> dict:
        return {
            "student_id": self.student_id,
            "text_profile": self.text_profile,
            "image_data": self.image_data,
            "audio_features": self.audio_features,
            "interaction_trace": self.interaction_trace,
            "timestamp": self.timestamp
        }

@dataclass
class OrthogonalRepresentation:
    """正交解耦表示：知识/策略/敏感"""
    knowledge_vector: list[float]  # 知识掌握度表示
    strategy_vector: list[float]  # 学习策略表示
    sensitive_vector: list[float]  # 敏感属性表示（需要压缩）
    
    def compress_sensitive(self, epsilon: float = 0.1) -> list[float]:
        """信息瓶颈压缩敏感表示"""
        # 简化版：仅保留低于阈值的维度
        return [v if abs(v) > epsilon else 0.0 for v in self.sensitive_vector]
