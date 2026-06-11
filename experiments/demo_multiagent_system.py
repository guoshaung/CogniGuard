"""多智能体系统演示：展示FOPD + C²-RAG + HSW-ST协同工作"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.agents.orchestrator import MultiAgentOrchestrator
from protection.common.schemas import StudentProfile, ProfileRecord, TeacherResource

def create_demo_config() -> dict:
    """创建演示配置"""
    return {
        "fopd": {
            "top_k_profile_records": 3,
            "relevance_threshold": 0.15,
            "sensitivity_threshold": 0.70,
            "use_enhanced_fopd": True,
            "attention": {
                "temperature": 0.5,
                "top_k_dimensions": 8
            },
            "bottleneck": {
                "max_mutual_info_bits": 3.0,
                "privacy_lambda": 0.5
            },
            "weights": {
                "rel": 0.50,
                "tag": 0.25,
                "confidence": 0.15,
                "recency": 0.10,
                "sens_gate": 0.20
            }
        },
        "c2rag": {
            "dynamic_budget": {
                "base_budget_per_chunk": 0.3,
                "high_copyright_penalty": 0.5,
                "teaching_phase_multiplier": {
                    "introduction": 0.8,
                    "practice": 1.2,
                    "review": 0.5
                }
            },
            "variant": {
                "numeric_shift_range": (1, 5),
                "structure_templates": [
                    "请计算：{expr}",
                    "已知条件：{expr}，求解结果"
                ]
            }
        },
        "hsw": {
            "gamma": 0.25,
            "delta": 2.0,
            "window_size": 4,
            "semantic_markers": [
                "根据教学资源",
                "参考版权材料",
                "基于已知公式"
            ],
            "marker_weight": 0.3
        },
        "agents": {
            "enable_fopd": True,
            "enable_c2rag": True,
            "enable_audit": True
        }
    }

def create_demo_student_profile() -> StudentProfile:
    """创建演示学生画像"""
    records = [
        ProfileRecord(
            knowledge="一元二次方程",
            content="学生擅长使用判别式求解",
            confidence=0.85,
            sensitivity=0.60,
            updated_at="2026-06-01T10:00:00"
        ),
        ProfileRecord(
            knowledge="函数图像",
            content="对二次函数顶点式理解较好",
            confidence=0.75,
            sensitivity=0.45,
            updated_at="2026-06-05T14:30:00"
        ),
        ProfileRecord(
            knowledge="几何证明",
            content="学生经常在辅助线构造上遇到困难",
            confidence=0.65,
            sensitivity=0.80,  # 高敏感：暴露弱点
            updated_at="2026-05-20T09:15:00"
        )
    ]
    return StudentProfile(student_id="demo_student_001", profile_records=records)

def create_demo_teacher_resources() -> list[TeacherResource]:
    """创建演示教师资源"""
    return [
        TeacherResource(
            resource_id="res_001",
            knowledge="一元二次方程",
            content="对于方程 ax²+bx+c=0，判别式 Δ=b²-4ac 决定根的性质",
            copyright_level=0.3,  # 低版权：公式
            chunk_text="判别式公式及应用"
        ),
        TeacherResource(
            resource_id="res_002",
            knowledge="一元二次方程",
            content="【名师精讲】某知名教辅中的例题：已知方程 x²-5x+6=0，求解并分析...",
            copyright_level=0.9,  # 高版权：名师内容
            chunk_text="版权例题"
        ),
        TeacherResource(
            resource_id="res_003",
            knowledge="函数",
            content="二次函数 y=a(x-h)²+k 的顶点坐标为 (h,k)",
            copyright_level=0.4,
            chunk_text="顶点式公式"
        )
    ]

def main():
    print("=" * 80)
    print("CogniGuard多智能体系统演示")
    print("=" * 80)
    
    # 初始化系统
    config = create_demo_config()
    orchestrator = MultiAgentOrchestrator(config)
    
    # 准备数据
    student_profile = create_demo_student_profile()
    teacher_resources = create_demo_teacher_resources()
    
    # 学生查询
    query = "请帮我解一元二次方程 x²-5x+6=0"
    
    print(f"\n【学生查询】{query}\n")
    
    # 处理查询
    result = orchestrator.process_query(
        query=query,
        student_profile=student_profile,
        teacher_resources=teacher_resources,
        teaching_phase="practice"
    )
    
    # 展示结果
    print("=" * 80)
    print("【Agent 1: FOPD - 学生画像保护】")
    print(f"选中画像数量: {result['metadata'].get('fopd_used', 0)}")
    for i, ctx in enumerate(result['fopd_context'], 1):
        print(f"  {i}. 知识点: {ctx['record'].get('knowledge')}")
        print(f"     相关性得分: {ctx['score']:.3f}")
        print(f"     是否高敏感: {'是' if ctx['protected'] else '否'}")
    
    print("\n" + "=" * 80)
    print("【Agent 2: C²-RAG - 版权保护】")
    print(f"使用资源数量: {result['metadata'].get('c2rag_resources', 0)}")
    for i, ctx in enumerate(result['c2rag_context'], 1):
        print(f"  {i}. 资源ID: {ctx['resource_id']}")
        print(f"     版权级别: {ctx['copyright_level']:.2f}")
        print(f"     返回模式: {ctx['return_mode']}")
        print(f"     预算使用: {ctx['budget_used']:.3f}")
        if ctx['return_mode'] == 'variant':
            print(f"     变体粒度: {ctx.get('granularity', 'N/A')}")
    
    print("\n" + "=" * 80)
    print("【Agent 3: HSW-ST - 水印审计】")
    print(f"审计链ID: {result['audit_chain_id']}")
    print(f"水印置信度: {result['metadata'].get('watermark_confidence', 0.0):.3f}")
    
    print("\n" + "=" * 80)
    print("【生成答案】")
    print(result['answer'])
    
    # 验证审计链
    print("\n" + "=" * 80)
    print("【审计验证】")
    verification = orchestrator.verify_answer(result['answer'], result['audit_chain_id'])
    print(f"链有效性: {'✓ 有效' if verification['valid'] else '✗ 无效'}")
    print(f"验证置信度: {verification.get('confidence', 0.0):.3f}")
    print(f"追溯到的资源数: {len(verification.get('sources', []))}")
    
    # 生成审计报告
    print("\n" + "=" * 80)
    print("【审计报告】")
    report = orchestrator.get_audit_report(result['audit_chain_id'])
    print(f"总曝光量: {report.get('total_exposure', 0.0):.3f}")
    print(f"高版权资源数: {report.get('high_copyright_sources', 0)}")
    print(f"合规性得分: {report.get('compliance_score', 0.0):.3f}")
    
    print("\n" + "=" * 80)
    print("演示完成！")
    print("=" * 80)

if __name__ == "__main__":
    main()
