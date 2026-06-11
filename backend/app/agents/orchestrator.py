"""多智能体协同编排器：统一调度FOPD + C²-RAG + HSW-ST"""
from __future__ import annotations
from typing import Any

from protection.common.schemas import Task, StudentProfile, TeacherResource
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
from protection.teacher_resource.src.c2rag.dynamic_budget import DynamicBudgetAllocator
from protection.teacher_resource.src.c2rag.multi_granularity_variant import MultiGranularityVariantGenerator
from protection.audit_trace.src.hybrid_watermark import HybridWatermarkSystem
from protection.audit_trace.src.audit_chain import AuditChain


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
        """处理学生查询的完整流程
        
        Returns:
            {
                "answer": str,
                "fopd_context": list,
                "c2rag_context": list,
                "audit_chain_id": str,
                "metadata": dict
            }
        """
        result = {
            "answer": "",
            "fopd_context": [],
            "c2rag_context": [],
            "audit_chain_id": None,
            "metadata": {}
        }
        
        # 创建任务对象
        task = Task(
            question=query,
            knowledge=self._extract_knowledge(query),
            task_type="practice"
        )
        
        # === Agent 1: FOPD画像保护 ===
        if self.enable_fopd:
            selected_profiles = self.profile_selector.select(student_profile, task)
            result["fopd_context"] = [
                {
                    "record": sp.record.to_dict(),
                    "score": sp.score,
                    "protected": sp.record.sensitivity > 0.7
                }
                for sp in selected_profiles
            ]
            result["metadata"]["fopd_used"] = len(selected_profiles)
        
        # === Agent 2: C²-RAG版权保护 ===
        if self.enable_c2rag:
            protected_resources = []
            for resource in teacher_resources:
                # 预算分配
                budget = self.budget_allocator.allocate(
                    chunk_id=resource.resource_id,
                    copyright_level=resource.copyright_level,
                    teaching_phase=teaching_phase
                )
                
                # 根据版权级别选择返回策略
                if resource.copyright_level > 0.8:
                    # 高版权：语义变体
                    variant = self.variant_generator.adaptive_select(resource, resource.copyright_level)
                    protected_resources.append({
                        "resource_id": resource.resource_id,
                        "content": variant["variant_text"],
                        "return_mode": "variant",
                        "copyright_level": resource.copyright_level,
                        "budget_used": budget,
                        "granularity": variant["granularity"]
                    })
                elif resource.copyright_level > 0.5:
                    # 中版权：部分曝光
                    protected_resources.append({
                        "resource_id": resource.resource_id,
                        "content": resource.content[:int(len(resource.content) * budget)],
                        "return_mode": "partial",
                        "copyright_level": resource.copyright_level,
                        "budget_used": budget
                    })
                else:
                    # 低版权：直接曝光
                    protected_resources.append({
                        "resource_id": resource.resource_id,
                        "content": resource.content,
                        "return_mode": "direct",
                        "copyright_level": resource.copyright_level,
                        "budget_used": budget
                    })
                
                # 记录曝光
                self.budget_allocator.record_exposure(resource.resource_id, budget)
            
            result["c2rag_context"] = protected_resources
            result["metadata"]["c2rag_resources"] = len(protected_resources)
        
        # === Agent 3: HSW-ST审计 ===
        if self.enable_audit:
            # 生成答案（这里简化，实际应调用LLM）
            answer_text = self._generate_answer(query, result["fopd_context"], result["c2rag_context"])
            
            # 嵌入混合水印
            watermark_result = self.watermark_system.embed_hybrid(
                text=answer_text,
                resource_id=f"answer_{hash(query)}",
                mode="both"
            )
            result["answer"] = watermark_result["watermarked_text"]
            
            # 创建审计链
            audit_sources = []
            for ctx in result["c2rag_context"]:
                audit_sources.append({
                    "resource_id": ctx["resource_id"],
                    "chunk_id": ctx["resource_id"],
                    "copyright_level": ctx["copyright_level"],
                    "exposure_before": 0.0,
                    "exposure_after": ctx["budget_used"],
                    "return_mode": ctx["return_mode"]
                })
            
            chain_id = self.audit_chain.create_link(
                student_answer_id=f"answer_{hash(query)}",
                teacher_resources=audit_sources,
                watermark_info=watermark_result.get("statistical_config", ),
                context_type="c2rag_resource"
            )
            result["audit_chain_id"] = chain_id
            result["metadata"]["watermark_confidence"] = watermark_result.get("statistical_config", {}).get("gamma", 0.0)
        
        return result
    
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
            f"画像: {ctx['record'].get('content', '')}" for ctx in fopd_ctx[:2]
        ] + [
            f"资源: {ctx['content']}" for ctx in c2rag_ctx[:2]
        ])
        
        return f"根据您的问题「{query}」和相关背景，建议如下：\n{context_text}\n请参考以上内容进行学习。"
