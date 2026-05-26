from __future__ import annotations

import re
from typing import Any

from src.common.schemas import Task


def infer_knowledge(question: str) -> str:
    q = question or ""
    if re.search(r"y\s*=\s*\(\s*x\s*[+-]\s*\d+\s*\)\s*\^?2", q):
        return "二次函数顶点式"
    if "方程" in q and "x" in q:
        return "一元一次方程"
    if "配方" in q:
        return "配方法"
    return "通用数学问题"


def parse_task(row: dict[str, Any]) -> Task:
    question = str(row.get("question", ""))
    return Task(
        request_id=str(row.get("request_id", "")),
        student_id=str(row.get("student_id", "")),
        question=question,
        knowledge=str(row.get("expected_knowledge") or infer_knowledge(question)),
        difficulty=str(row.get("difficulty", "basic")),
        need_resource=bool(row.get("need_resource", False)),
    )
