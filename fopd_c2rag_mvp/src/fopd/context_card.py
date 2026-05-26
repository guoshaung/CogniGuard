from __future__ import annotations

from src.common.schemas import StudentProfile, Task
from src.fopd.profile_selector import ScoredProfileRecord


def _mastery_phrase(value: object) -> str:
    try:
        v = float(value)
    except Exception:
        return str(value)
    if v < 0.5:
        return "理解不稳定"
    if v < 0.75:
        return "基本掌握但需要巩固"
    return "掌握较稳定"


def build_context_card(
    profile: StudentProfile,
    task: Task,
    selected_records: list[ScoredProfileRecord],
) -> tuple[str, list[str]]:
    mastery: list[str] = []
    errors: list[str] = []
    preferences: list[str] = []
    other: list[str] = []

    for item in selected_records:
        record = item.record
        if record.type == "mastery":
            mastery.append(_mastery_phrase(record.value))
        elif record.type == "error_pattern":
            errors.append(str(record.value))
        elif record.type == "preference":
            preferences.append(str(record.value))
        else:
            other.append(f"{record.type}:{record.knowledge}")

    lines = [
        f"当前知识点：{task.knowledge}",
        f"任务难度：{task.difficulty}",
    ]
    if mastery:
        lines.append("相关掌握状态：" + "；".join(mastery[:2]))
    if errors:
        lines.append("常见错误：" + "；".join(errors[:2]))
    if preferences:
        lines.append("推荐策略：" + "；".join(preferences[:2]))
    elif task.knowledge == "二次函数顶点式":
        lines.append("推荐策略：先用图像解释，再进行代数推导")
    if other:
        lines.append("其他任务相关提示：" + "；".join(other[:1]))
    lines.append("隐私说明：不包含学校、家庭、完整历史记录，仅本轮有效")

    card = "\n".join(lines)
    redaction_log: list[str] = []
    for key, value in profile.local_only_fields.items():
        value_text = str(value)
        if value_text and value_text in card:
            card = card.replace(value_text, "[REDACTED]")
            redaction_log.append(key)
    return card, redaction_log
