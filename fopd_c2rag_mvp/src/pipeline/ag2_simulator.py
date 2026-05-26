from __future__ import annotations

import re

from src.common.schemas import ControlledResource, Task


def build_ag2_request(task: Task, context_card: str) -> dict[str, object]:
    return {
        "question": task.question,
        "knowledge": task.knowledge,
        "resource_type": "question_bank" if task.need_resource else "none",
        "difficulty": task.difficulty,
        "teaching_goal": "根据最小画像卡片给出针对性讲解，并避免请求完整教师资料原文。",
        "context_card_hint": context_card.splitlines()[:3],
    }


def _solve_quadratic_vertex(question: str) -> str | None:
    compact = question.replace(" ", "")
    m = re.search(r"y=\(x([+-])(\d+)\)\^?2([+-])(\d+)", compact)
    if not m:
        return None
    sign_h, raw_h, sign_k, raw_k = m.groups()
    h = int(raw_h) if sign_h == "-" else -int(raw_h)
    k = int(raw_k) if sign_k == "+" else -int(raw_k)
    left_right = f"向右平移 {h} 个单位" if h > 0 else (f"向左平移 {abs(h)} 个单位" if h < 0 else "水平方向不移动")
    up_down = f"向上平移 {k} 个单位" if k > 0 else (f"向下平移 {abs(k)} 个单位" if k < 0 else "竖直方向不移动")
    return f"这是一道顶点式问题。顶点是 ({h},{k})，对称轴是 x={h}。它可由 y=x^2 {left_right}，再{up_down}得到。"


def _solve_linear_equation(question: str) -> str | None:
    compact = question.replace(" ", "")
    m = re.search(r"([+-]?\d*)x([+-]\d+)=([+-]?\d+)", compact)
    if not m:
        return None
    a_raw, b_raw, c_raw = m.groups()
    if a_raw in {"", "+"}:
        a = 1
    elif a_raw == "-":
        a = -1
    else:
        a = int(a_raw)
    b = int(b_raw)
    c = int(c_raw)
    if a == 0:
        return None
    x = (c - b) / a
    return f"先把常数项移到等号右边，得到 {a}x={c - b}；再两边同时除以 {a}，所以 x={x:g}。"


def compose_final_answer(
    task: Task,
    context_card: str,
    controlled_resource: ControlledResource | None,
) -> str:
    base = _solve_quadratic_vertex(task.question) or _solve_linear_equation(task.question)
    if base is None:
        base = f"先识别本题知识点“{task.knowledge}”，再按条件、关系、结论三步处理。"
    strategy = "我会先提醒易错点，再给出步骤。"
    if "图像" in context_card:
        strategy = "我会先用图像和平移关系解释，再补代数结论。"
    parts = [strategy, base]
    if controlled_resource:
        if controlled_resource.mode == "variant":
            parts.append(f"补充变式练习：{controlled_resource.text}")
        elif controlled_resource.mode in {"summary", "outline"}:
            parts.append(f"受控资源提示：{controlled_resource.text}")
        elif controlled_resource.mode == "quote":
            parts.append(f"短引用提示：{controlled_resource.text}")
        else:
            parts.append(controlled_resource.text)
    return "\n".join(parts)
