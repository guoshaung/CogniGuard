"""多智能体协同编排器：统一调度FOPD + C²-RAG + HSW-ST"""
from __future__ import annotations

from protection.audit_trace.src.audit_chain import AuditChain
from protection.audit_trace.src.hybrid_watermark import HybridWatermarkSystem
from protection.common.schemas import StudentProfile, TeacherResource
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
from protection.teacher_resource.src.c2rag.dynamic_budget import DynamicBudgetAllocator
from protection.teacher_resource.src.c2rag.multi_granularity_variant import (
    MultiGranularityVariantGenerator,
)


class MultiAgentOrchestrator:
    """多智能体编排器：协调三层保护机制"""
    
    def __init__(self, config: dict):
        self.config = config
        
        # Agent 1: FOPD - 学生画像保护
        self.profile_selector = ProfileSelector(config)
        
        # Agent 2: C²-RAG - 教师资源版权保护
        self.budget_allocator = DynamicBudgetAllocator(config)
        self.variant_generator = MultiGranularityVariantGenerator(config)
        
        # Agent 3: HSW-ST - 水印审计
        self.watermark_system = HybridWatermarkSystem(config)
        self.audit_chain = AuditChain()
        
        # 协同策略
        self.enable_fopd = config.get("agents", {}).get("enable_fopd", True)
        self.enable_c2rag = config.get("agents", {}).get("enable_c2rag", True)
        self.enable_audit = config.get("agents", {}).get("enable_audit", True)
    
    def process_query(
        self,
        query: str,
        student_profile: StudentProfile,
        teacher_resources: list[TeacherResource],
        teaching_phase: str = "practice"
    ) -> dict:
        """Route every research turn through the compiled graph."""
        from cogniguard.workflows.education.research import run_research_flow
        return run_research_flow(self, query, student_profile, teacher_resources, teaching_phase)
    
    def verify_answer(self, answer_text: str, claimed_chain_id: str) -> dict:
        """验证答案的审计链"""
        if not self.enable_audit:
            return {"valid": False, "reason": "Audit disabled"}
        
        return self.audit_chain.verify_chain(answer_text, claimed_chain_id)
    
    def get_audit_report(self, answer_id: str) -> dict:
        """获取审计报告"""
        if not self.enable_audit:
            return {"error": "Audit disabled"}
        
        return self.audit_chain.get_audit_report(answer_id)
    
    def _extract_knowledge(self, query: str) -> str:
        """提取知识点（简化）"""
        keywords = ["方程", "函数", "几何", "概率", "统计"]
        for kw in keywords:
            if kw in query:
                return kw
        return "通用"
    
    def _generate_answer(self, query: str, fopd_ctx: list, c2rag_ctx: list) -> str:
        """生成答案（简化，实际应调用LLM）"""
        context_text = "\n".join([
            f"画像: {ctx['record'].get('value', '')}" for ctx in fopd_ctx[:2]
        ] + [
            f"资源: {ctx['content']}" for ctx in c2rag_ctx[:2]
        ])
        
        return f"根据您的问题「{query}」和相关背景，建议如下：\n{context_text}\n请参考以上内容进行学习。"
