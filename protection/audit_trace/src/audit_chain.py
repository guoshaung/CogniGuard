"""审计链路追踪：HSW-ST (Hybrid Watermark + Source Tracing)"""
from __future__ import annotations
from typing import Any
from datetime import datetime
import hashlib

class AuditChain:
    """审计链：从学生输出追溯到教师资源"""
    
    def __init__(self):
        self.chain_records: list[dict] = []
    
    def create_link(
        self,
        student_answer_id: str,
        teacher_resources: list[dict],
        watermark_info: dict,
        context_type: str  # "fopd_profile" | "c2rag_resource"
    ) -> str:
        """创建审计链接
        
        返回: chain_id
        """
        chain_id = self._generate_chain_id(student_answer_id, watermark_info)
        
        record = {
            "chain_id": chain_id,
            "student_answer_id": student_answer_id,
            "context_type": context_type,
            "sources": [],
            "watermark": watermark_info,
            "timestamp": datetime.now().isoformat(),
            "verifiable": True
        }
        
        # 绑定每个教师资源
        for resource in teacher_resources:
            source_link = {
                "resource_id": resource.get("resource_id"),
                "chunk_id": resource.get("chunk_id"),
                "copyright_level": resource.get("copyright_level", 0.0),
                "exposure_amount": resource.get("exposure_after", 0.0) - resource.get("exposure_before", 0.0),
                "return_mode": resource.get("return_mode", "unknown"),
                "binding_hash": self._hash_binding(chain_id, resource.get("resource_id"))
            }
            record["sources"].append(source_link)
        
        self.chain_records.append(record)
        return chain_id
    
    def verify_chain(self, student_output: str, claimed_chain_id: str) -> dict:
        """验证审计链的完整性"""
        # 查找链记录
        chain = next((c for c in self.chain_records if c["chain_id"] == claimed_chain_id), None)
        
        if not chain:
            return {
                "valid": False,
                "reason": "Chain not found",
                "confidence": 0.0
            }
        
        # 验证水印
        watermark_valid = self._verify_watermark(student_output, chain["watermark"])
        
        # 验证源绑定
        sources_valid = all(
            self._verify_source_binding(s["binding_hash"], claimed_chain_id, s["resource_id"])
            for s in chain["sources"]
        )
        
        confidence = 1.0 if (watermark_valid and sources_valid) else 0.5
        
        return {
            "valid": watermark_valid and sources_valid,
            "chain_id": claimed_chain_id,
            "sources": chain["sources"],
            "watermark_confidence": chain["watermark"].get("confidence", 0.0),
            "confidence": confidence,
            "timestamp": chain["timestamp"]
        }
    
    def trace_backwards(self, student_answer_id: str) -> list[dict]:
        """反向追溯：从学生输出找到所有教师资源"""
        matching_chains = [c for c in self.chain_records if c["student_answer_id"] == student_answer_id]
        
        all_sources = []
        for chain in matching_chains:
            for source in chain["sources"]:
                all_sources.append({
                    "chain_id": chain["chain_id"],
                    "resource_id": source["resource_id"],
                    "copyright_level": source["copyright_level"],
                    "exposure": source["exposure_amount"],
                    "context_type": chain["context_type"]
                })
        
        return all_sources
    
    def trace_forward(self, resource_id: str) -> list[dict]:
        """正向追踪：查看某个教师资源被哪些学生使用"""
        usages = []
        
        for chain in self.chain_records:
            for source in chain["sources"]:
                if source["resource_id"] == resource_id:
                    usages.append({
                        "student_answer_id": chain["student_answer_id"],
                        "chain_id": chain["chain_id"],
                        "timestamp": chain["timestamp"],
                        "exposure": source["exposure_amount"]
                    })
        
        return usages
    
    def get_audit_report(self, answer_id: str) -> dict:
        """生成审计报告"""
        sources = self.trace_backwards(answer_id)
        
        report = {
            "answer_id": answer_id,
            "total_sources": len(sources),
            "high_copyright_sources": len([s for s in sources if s["copyright_level"] > 0.7]),
            "total_exposure": sum(s["exposure"] for s in sources),
            "sources_by_type": {},
            "compliance_score": 0.0
        }
        
        # 按类型分组
        for source in sources:
            ctx_type = source["context_type"]
            if ctx_type not in report["sources_by_type"]:
                report["sources_by_type"][ctx_type] = []
            report["sources_by_type"][ctx_type].append(source)
        
        # 合规性评分（exposure越低越好）
        if sources:
            avg_exposure = report["total_exposure"] / len(sources)
            report["compliance_score"] = max(0.0, 1.0 - avg_exposure)
        
        return report
    
    def _generate_chain_id(self, answer_id: str, watermark_info: dict) -> str:
        """生成唯一链ID"""
        content = f"{answer_id}_{watermark_info.get('key_id', '')}_{datetime.now().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:24]
    
    def _hash_binding(self, chain_id: str, resource_id: str) -> str:
        """生成源绑定哈希"""
        content = f"{chain_id}_{resource_id}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _verify_watermark(self, text: str, watermark_info: dict) -> bool:
        """验证水印存在性（简化）"""
        # 实际应该调用hybrid_watermark的detect方法
        return watermark_info.get("confidence", 0.0) > 0.5
    
    def _verify_source_binding(self, binding_hash: str, chain_id: str, resource_id: str) -> bool:
        """验证源绑定哈希"""
        expected_hash = self._hash_binding(chain_id, resource_id)
        return binding_hash == expected_hash
