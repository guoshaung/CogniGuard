"""多粒度变体生成：数值/结构/语义三层变换"""
from __future__ import annotations
import random
from protection.common.schemas import TeacherResource

class MultiGranularityVariantGenerator:
    """多粒度变体生成器"""
    
    def __init__(self, config: dict):
        cfg = config.get("c2rag", {}).get("variant", {})
        self.numeric_range = cfg.get("numeric_shift_range", (1, 5))
        self.structure_templates = cfg.get("structure_templates", [
            "请计算：{expr}",
            "已知条件：{expr}，求解结果",
            "设{expr}，分析其性质"
        ])
    
    def generate(self, resource: TeacherResource, granularity: str = "numeric") -> dict:
        """生成变体
        
        Args:
            granularity: "numeric" | "structural" | "semantic"
        """
        if granularity == "numeric":
            return self._numeric_variant(resource)
        elif granularity == "structural":
            return self._structural_variant(resource)
        else:
            return self._semantic_variant(resource)
    
    def _numeric_variant(self, resource: TeacherResource) -> dict:
        """数值变体：仅改变数字"""
        content = resource.content
        import re
        
        def replace_number(match):
            num = int(match.group())
            shift = random.randint(*self.numeric_range)
            return str(num + shift)
        
        variant = re.sub(r'\d+', replace_number, content)
        
        return {
            "variant_text": variant,
            "granularity": "numeric",
            "surface_similarity": 0.9,  # 高相似度
            "semantic_distance": 0.1    # 低语义距离
        }
    
    def _structural_variant(self, resource: TeacherResource) -> dict:
        """结构变体：改变表达方式"""
        # 提取核心表达式（简化）
        import re
        expr_match = re.search(r'[xy]=.*?\d+', resource.content)
        expr = expr_match.group() if expr_match else resource.knowledge
        
        # 随机选择模板
        template = random.choice(self.structure_templates)
        variant = template.format(expr=expr)
        
        return {
            "variant_text": variant,
            "granularity": "structural",
            "surface_similarity": 0.5,
            "semantic_distance": 0.3
        }
    
    def _semantic_variant(self, resource: TeacherResource) -> dict:
        """语义变体：改变问题背景"""
        # 知识点相同，但应用场景不同
        knowledge = resource.knowledge
        
        scenarios = [
            f"在实际应用中，{knowledge}可用于解决以下问题：",
            f"某个{knowledge}的实例如下：",
            f"请构造一个关于{knowledge}的新问题："
        ]
        
        variant = random.choice(scenarios)
        
        return {
            "variant_text": variant,
            "granularity": "semantic",
            "surface_similarity": 0.2,
            "semantic_distance": 0.6
        }
    
    def adaptive_select(self, resource: TeacherResource, copyright_level: float) -> dict:
        """自适应选择变体粒度：版权越高，粒度越粗"""
        if copyright_level < 0.3:
            return self.generate(resource, "numeric")
        elif copyright_level < 0.7:
            return self.generate(resource, "structural")
        else:
            return self.generate(resource, "semantic")
