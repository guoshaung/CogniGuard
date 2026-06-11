"""动态曝光预算分配：基于教学目标和版权级别"""
from __future__ import annotations
from collections import defaultdict

class DynamicBudgetAllocator:
    """动态预算分配器：根据教学阶段调整"""
    
    def __init__(self, config: dict):
        cfg = config.get("c2rag", {}).get("dynamic_budget", {})
        self.base_budget = float(cfg.get("base_budget_per_chunk", 0.3))
        self.high_copyright_penalty = float(cfg.get("high_copyright_penalty", 0.5))
        self.teaching_phase_multiplier = cfg.get("teaching_phase_multiplier", {
            "introduction": 0.8,  # 引入阶段：少量曝光
            "practice": 1.2,      # 练习阶段：适度曝光
            "review": 0.5         # 复习阶段：最小曝光
        })
        self.exposure_history: dict[str, float] = defaultdict(float)
    
    def allocate(self, chunk_id: str, copyright_level: float, teaching_phase: str = "practice") -> float:
        """分配单个资源的预算"""
        # 基础预算
        budget = self.base_budget
        
        # 版权惩罚
        if copyright_level > 0.7:
            budget *= (1 - self.high_copyright_penalty)
        
        # 教学阶段调整
        phase_mult = self.teaching_phase_multiplier.get(teaching_phase, 1.0)
        budget *= phase_mult
        
        # 历史曝光折扣
        history = self.exposure_history.get(chunk_id, 0.0)
        budget *= max(0.1, 1.0 - history)
        
        return budget
    
    def record_exposure(self, chunk_id: str, amount: float):
        """记录曝光"""
        self.exposure_history[chunk_id] += amount
    
    def get_remaining_budget(self, chunk_id: str) -> float:
        """获取剩余预算"""
        return max(0.0, self.base_budget - self.exposure_history.get(chunk_id, 0.0))
