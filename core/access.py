"""可信调用方授予范围；文本输入不能修改这些权限。"""
from dataclasses import dataclass
import math

from protection.common.schemas import StudentProfile, Task


@dataclass(frozen=True)
class AccessScope:
    """由后端会话构建，不能从用户问题、资源正文或模型输出反序列化。"""

    student_id: str
    allow_resources: bool = True
    resource_ids: frozenset[str] | None = None

    def __post_init__(self):
        if self.resource_ids is not None:
            object.__setattr__(self, "resource_ids", frozenset(self.resource_ids))

    def authorize(self, profile: StudentProfile, task: Task) -> None:
        if task.student_id != profile.student_id:
            raise ValueError("任务与学生画像不匹配")
        if self.student_id != profile.student_id:
            raise PermissionError("当前会话无权读取该学生画像")
        if task.need_resource and not self.allow_resources:
            raise PermissionError("当前会话无权读取教师资源")
        if task.need_resource and self.resource_ids == frozenset():
            raise PermissionError("当前会话没有获准读取的教师资源")


class ProfileReadPolicy:
    """先执行硬性字段白名单和敏感度门限，再交给相关性算法。"""

    ALLOWED_TYPES = frozenset({"mastery", "error_pattern", "preference"})

    def __init__(self, config: dict):
        self.max_sensitivity = float(config.get("access", {}).get("max_profile_sensitivity", 0.70))
        if not math.isfinite(self.max_sensitivity) or not 0 <= self.max_sensitivity <= 1:
            raise ValueError("max_profile_sensitivity 必须在 0 到 1 之间")

    def filter(self, profile: StudentProfile) -> StudentProfile:
        records = []
        for record in profile.profile_records:
            if record.type not in self.ALLOWED_TYPES:
                continue
            if not math.isfinite(record.sensitivity) or not 0 <= record.sensitivity <= self.max_sensitivity:
                continue
            # mastery 只接受有效数值，避免任意指令通过回退字符串进入卡片。
            if record.type == "mastery":
                try:
                    value = float(record.value)
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(value) or not 0 <= value <= 1:
                    continue
            records.append(record)
        # 选择算法无须接触 local_only_fields。
        return StudentProfile(profile.student_id, {}, records)
