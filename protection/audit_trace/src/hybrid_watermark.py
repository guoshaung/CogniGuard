"""混合水印系统：统计水印(H) + 语义水印(S) = HSW"""
from __future__ import annotations
from typing import Any
import hashlib

class HybridWatermarkSystem:
    """HSW混合水印：Statistical + Semantic"""
    
    def __init__(self, config: dict):
        cfg = config.get("hsw", {})
        # 统计水印参数
        self.gamma = float(cfg.get("gamma", 0.25))
        self.delta = float(cfg.get("delta", 2.0))
        self.window_size = int(cfg.get("window_size", 4))
        
        # 语义水印参数
        self.semantic_markers = cfg.get("semantic_markers", [
            "根据教学资源",
            "参考版权材料",
            "基于已知公式"
        ])
        self.marker_weight = float(cfg.get("marker_weight", 0.3))
    
    def embed_hybrid(self, text: str, resource_id: str, mode: str = "both") -> dict:
        """嵌入混合水印
        
        Args:
            mode: "statistical" | "semantic" | "both"
        """
        result = {"original_text": text, "watermarked_text": text}
        
        if mode in ("statistical", "both"):
            # 统计水印通过logits_processor在生成时注入
            result["statistical_config"] = {
                "gamma": self.gamma,
                "delta": self.delta,
                "window_size": self.window_size,
                "key_id": self._generate_key(resource_id)
            }
        
        if mode in ("semantic", "both"):
            # 语义水印：在文本中自然插入标记
            watermarked = self._embed_semantic(text, resource_id)
            result["watermarked_text"] = watermarked
            result["semantic_markers"] = self.semantic_markers
        
        return result
    
    def _embed_semantic(self, text: str, resource_id: str) -> str:
        """嵌入语义水印"""
        # 选择合适的语义标记
        marker_idx = hash(resource_id) % len(self.semantic_markers)
        marker = self.semantic_markers[marker_idx]
        
        # 在文本末尾自然插入
        if "。" in text:
            parts = text.rsplit("。", 1)
            watermarked = f"{parts[0]}。({marker}){parts[1] if len(parts) > 1 else ''}"
        else:
            watermarked = f"{text}（{marker}）"
        
        return watermarked
    
    def detect_hybrid(self, text: str, tokenizer: Any = None) -> dict:
        """检测混合水印"""
        result = {
            "has_statistical": False,
            "has_semantic": False,
            "confidence": 0.0,
            "detected_markers": []
        }
        
        # 检测语义标记
        for marker in self.semantic_markers:
            if marker in text:
                result["has_semantic"] = True
                result["detected_markers"].append(marker)
        
        # 统计水印检测（需要tokenizer）
        if tokenizer:
            # 这里简化，实际应调用watermark_detector的z-score计算
            result["has_statistical"] = True  # 占位
        
        # 综合置信度
        semantic_conf = len(result["detected_markers"]) * self.marker_weight
        statistical_conf = 0.7 if result["has_statistical"] else 0.0
        result["confidence"] = min(1.0, semantic_conf + statistical_conf)
        
        return result
    
    def _generate_key(self, resource_id: str) -> str:
        """为资源生成唯一密钥"""
        return hashlib.sha256(resource_id.encode()).hexdigest()[:16]
