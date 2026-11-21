"""教学端只接收不可变文本视图，不接收原始画像或资源对象。"""
from dataclasses import asdict, dataclass

from protection.common.schemas import ControlledResource, Task
from protection.student_profile.src.pipeline.ag2_simulator import compose_final_answer


@dataclass(frozen=True)
class TeachingInput:
    question: str
    knowledge: str
    difficulty: str
    context_card: str
    resource_mode: str
    resource_text: str

    def to_dict(self) -> dict[str, str]:
        """未来模型适配器的唯一数据入口；其中的文本仍是不可信内容。"""
        return asdict(self)


def build_teaching_input(task: Task, card: str, controlled: ControlledResource | None,
                         local_only_fields: dict) -> TeachingInput:
    def redact(text: str) -> str:
        # 最后一道本地已知值检查，覆盖问题和资源也包含秘密的情况。
        for value in local_only_fields.values():
            value_text = str(value)
            if value_text:
                text = text.replace(value_text, "[REDACTED]")
        return text

    return TeachingInput(
        question=redact(task.question), knowledge=redact(task.knowledge),
        difficulty=redact(task.difficulty), context_card=redact(card),
        resource_mode=controlled.mode if controlled else "none",
        resource_text=redact(controlled.text) if controlled else "",
    )


def generate_offline_answer(data: TeachingInput) -> str:
    """复用历史纯函数；适配对象中没有身份、原始资源或策略元数据。"""
    task = Task("", "", data.question, data.knowledge, data.difficulty, data.resource_mode != "none")
    resource = None
    if data.resource_mode != "none":
        resource = ControlledResource(data.resource_mode, data.resource_text, None, 0.0, 0.0, {})
    return compose_final_answer(task, data.context_card, resource)
