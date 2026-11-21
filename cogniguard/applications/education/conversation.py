from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from cogniguard.protection.image_watermarking import generate_protected_teaching_images
from core.paths import PROJECT_ROOT

FREE_CHAT_SYSTEM_PROMPT = """
你是 CogniGuard 中的通用教育问答助手。
CogniGuard 确实包含受版权保护的教师素材、题库和原创课件资源，由 C2-RAG、
曝光预算、CG 和水印审计控制。不要声称系统没有素材库或文件系统。
自由问答不读取当前课堂案例、学生画像、掌握度或错误类型，也不能浏览、列出、
逐字输出或泄露受保护资源。用户提出具体学习需求时，可以建议其说明知识点，
再由受控课堂返回摘要、提示或等价变式。
回答应清晰、自然、简洁。返回一个 JSON 对象，格式为 {"answer": "你的回答"}。
""".strip()


def run_conversation(
    *,
    message: str,
    history: list[dict[str, Any]] | None = None,
    existing_image_count: int = 0,
    session_token: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    from cogniguard.runtime.gateway import get_gateway
    from cogniguard.workflows.education.conversation import run_free_chat_graph

    def execute(frame):
        used = frame.session.budget("images")
        return run_free_chat_graph(
            message,
            list(frame.state.get("history", [])),
            int(used["committed"] + used["reserved"]),
        )

    return get_gateway().run(
        "free_chat",
        {"message": message},
        execute,
        session_token=session_token,
        request_id=request_id,
    )


run_free_chat = run_conversation


def _messages(
    question: str,
    answer: str,
    *,
    guardrail: dict[str, Any] | None = None,
    controlled_summary: dict[str, Any] | None = None,
    teaching_images: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    timestamp = datetime.now(timezone.utc).isoformat()
    return [
        {
            "id": f"free_{uuid4().hex[:12]}",
            "role": "student",
            "content": question,
            "timestamp": timestamp,
            "payload": {
                "mode": "free_chat",
                "case_context_enabled": False,
            },
        },
        {
            "id": f"free_{uuid4().hex[:12]}",
            "role": "teacher",
            "content": answer,
            "timestamp": timestamp,
            "payload": {
                "mode": "free_chat",
                "case_context_enabled": False,
                "guardrail": guardrail,
                "controlled_resource_summary": controlled_summary,
                "teaching_images": teaching_images or [],
            },
        },
    ]


def _maybe_generate_free_chat_images(
    question: str, answer: str, existing_image_count: int = 0
) -> list[dict[str, Any]]:
    if not _has_visual_intent(question):
        return []
    if int(existing_image_count or 0) >= 2:
        return []
    answer_id = f"free_ans_{uuid4().hex[:12]}"
    resource_id = "free_chat_visual_teaching"
    visual_template = _visual_template_for_question(question)
    prompt = (
        "生成一张中学数学教学示意图，不要做海报，不要做流程卡。"
        "画面必须包含公式、方程或数学模型，并用箭头、标注、局部高亮解释概念。"
        f"使用通用教学模板：{visual_template}。"
        "如果问题涉及函数，请画坐标轴和函数图像；涉及分数，请画面积模型；"
        "涉及概率，请画树状图；涉及方程，请画等式变形和关键步骤。"
        "不要包含姓名、原始问答、学生画像、教师原文或其他隐私信息。"
    )
    images = generate_protected_teaching_images(
        prompt=prompt,
        answer_id=answer_id,
        resource_id=resource_id,
        count=1,
    )
    return [
        {
            "image_id": item.image_id,
            "url": item.public_url,
            "prompt": item.prompt,
            "source_url": item.source_url,
            "watermark": item.watermark,
        }
        for item in images
    ]


def _visual_template_for_question(question: str) -> str:
    lowered = question.lower()
    categories = (
        (("函数", "function", "抛物线", "坐标"), "函数坐标图"),
        (("分数", "fraction", "比例", "百分"), "分数面积模型"),
        (("概率", "probability", "随机"), "概率树状图"),
        (("几何", "geometry", "三角形", "圆"), "几何标注图"),
        (("方程", "equation", "等式"), "方程变形板书"),
    )
    for keywords, label in categories:
        if any(keyword in lowered for keyword in keywords):
            return label
    return "通用数学概念图"


def _free_chat_safety_block(question: str) -> dict[str, str] | None:
    lowered = question.lower()
    has_political_context = any(
        token in lowered
        for token in (
            "政治",
            "选举",
            "投票",
            "政党",
            "候选人",
            "political",
            "politics",
            "election",
            "voter",
            "campaign",
            "party",
            "candidate",
        )
    )
    has_profile_targeting = any(
        token in lowered
        for token in (
            "个人画像",
            "用户画像",
            "学生画像",
            "政治立场",
            "立场",
            "画像",
            "personal profile",
            "user profile",
            "student profile",
            "political stance",
            "profile",
        )
    )
    has_persuasion_intent = any(
        token in lowered
        for token in (
            "劝说",
            "说服",
            "动员",
            "定向",
            "针对性",
            "persuasion",
            "persuasive",
            "convince",
            "influence",
            "microtarget",
            "targeted",
        )
    )
    if has_political_context and has_profile_targeting and has_persuasion_intent:
        return {
            "matched_policy": "political_persuasion_profile_targeting",
            "reason": "The request asks for targeted political persuasion using a user or learner profile.",
            "safe_answer": (
                "我不能根据个人画像、政治立场或敏感属性生成定向政治劝说内容。"
                "如果你的目标是课堂安全测试，我可以改为提供中立的风险说明、合规拒答样例，"
                "或帮助设计不利用个人画像的公民教育讨论题。"
            ),
        }
    return None


def _deterministic_free_chat_answer(question: str) -> str:
    lowered = question.lower()
    if any(
        token in lowered
        for token in ("latex", "formula", "equation", "function", "公式", "方程", "函数")
    ):
        return (
            "可以。先把已知条件、目标量和约束条件分开写，再用公式承接推理。\n\n"
            "例如一元二次方程可以写成 $ax^2 + bx + c = 0$，判别式为 "
            "$\\Delta = b^2 - 4ac$。当 $\\Delta \\ge 0$ 时，解为 "
            "$$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$\n\n"
            "你把具体题目发来后，我会按步骤推导，并用 LaTeX 展示关键公式。"
        )
    if any(token in lowered for token in ("diagram", "visual", "illustration", "draw", "图", "画")):
        return (
            "可以。我会把它转成一个可视化教学解释：先给出核心概念，再用图例说明变量关系，"
            "最后给出可检查的结论。需要图像时，会生成带 CogniGuard 水印的教学图。"
        )
    return (
        "我可以继续帮你解释这个问题。建议按三步来：第一，确认题目给了哪些条件；"
        "第二，写出目标量；第三，选择对应规则或公式逐步推导。你可以把具体题目贴出来，"
        "我会给出清晰步骤和必要公式。"
    )


def _has_visual_intent(question: str) -> bool:
    lowered = question.lower()
    return any(
        token in lowered
        for token in (
            "图",
            "图例",
            "画",
            "示意图",
            "坐标",
            "图像",
            "树状图",
            "diagram",
            "visual",
            "illustration",
            "draw",
        )
    )


def _build_guardrail_text(
    question: str,
    history: list[dict[str, Any]] | None,
) -> str:
    recent_user_messages = [
        str(item.get("content", "")).strip()
        for item in (history or [])[-8:]
        if item.get("role") in {"student", "user"} and item.get("content")
    ][-3:]
    return "\n".join([*recent_user_messages, question])


def _protected_resource_summary() -> tuple[str, dict[str, Any]]:
    resource_file = (
        PROJECT_ROOT
        / "data"
        / "scenario_layers"
        / "teacher_resources"
        / "teacher_resources_v1.jsonl"
    )
    resources = []
    if resource_file.exists():
        for line in resource_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                resources.append(json.loads(line))

    knowledge_areas = sorted(
        {str(item.get("knowledge")) for item in resources if item.get("knowledge")}
    )
    coverage = sorted(
        {str(label) for item in resources for label in item.get("coverage", []) if label}
    )
    difficulty_counts = Counter(str(item.get("difficulty", "unknown")) for item in resources)
    return_modes = sorted(
        {str(item.get("return_mode")) for item in resources if item.get("return_mode")}
    )
    summary_data = {
        "resource_count": len(resources),
        "knowledge_areas": knowledge_areas,
        "coverage_tags": coverage,
        "difficulty_distribution": dict(difficulty_counts),
        "allowed_return_modes": return_modes,
        "excluded_fields": ["content", "resource_id", "chunk_id", "source", "file_path"],
    }
    summary = (
        f"可以。当前受控教师资源层包含 {len(resources)} 份资源样本，"
        f"覆盖 {('、'.join(knowledge_areas) or '多个教学主题')}。"
        f"难度分布为 easy {difficulty_counts.get('easy', 0)}、"
        f"medium {difficulty_counts.get('medium', 0)}、"
        f"hard {difficulty_counts.get('hard', 0)}。"
        f"可公开的基础标签包括：{('、'.join(coverage) or '暂无')}。"
        "系统只允许按策略返回摘要、净化摘要、等价变式或拒绝，"
        "不会展示资源目录、文件路径、资源标识和题目原文。"
    )
    return summary, summary_data
