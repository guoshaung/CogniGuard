"""合成学生群体：敏感属性 A（family_support）与非敏感画像信号相关。

相关性让“最小卡片”里残留可被推断的信号：
  A=low（弱支持）→ 掌握偏低、错误偏“对称轴/符号”、偏好图像；
  A=high（强支持）→ 掌握偏高、错误偏“公式/边界”、偏好分步。
A 的显式取值只放在 local_only_fields（MM-FOPD 永不选择；FullProfile 才包含）。
"""
from __future__ import annotations

import random

from protection.common.schemas import ProfileRecord, StudentProfile

KNOWLEDGE = "二次函数顶点式"
# A 条件下的分布（错误原始措辞含 context_card 可识别的概念词）。
_ERROR_BY_A = {
    "low": ["忽略对称轴导致顶点错误", "代数符号容易写反"],
    "high": ["公式选择不当", "边界条件考虑不全"],
}
_PREF_BY_A = {
    "low": ["适合图像化解释"],
    "high": ["适合分步列式推导"],
}


def _mastery(a: str, rng: random.Random) -> float:
    mean = 0.42 if a == "low" else 0.70
    return max(0.0, min(1.0, round(rng.gauss(mean, 0.10), 3)))


def make_population(n: int = 300, seed: int = 20261012) -> list[tuple[StudentProfile, str]]:
    rng = random.Random(seed)
    people = []
    for i in range(n):
        a = "low" if i % 2 == 0 else "high"   # 平衡 base rate=0.5
        # 适度混入噪声：10% 个体用“另一类”的错误/偏好，削弱相关性，制造残留而非完美可分。
        noisy = rng.random() < 0.10
        src = ("high" if a == "low" else "low") if noisy else a
        records = [
            ProfileRecord(f"m{i}", "mastery", KNOWLEDGE, _mastery(a, rng), 0.85, 0.30),
            ProfileRecord(f"e{i}", "error_pattern", KNOWLEDGE, rng.choice(_ERROR_BY_A[src]), 0.80, 0.40),
            ProfileRecord(f"p{i}", "preference", KNOWLEDGE, rng.choice(_PREF_BY_A[src]), 0.75, 0.30),
        ]
        profile = StudentProfile(
            student_id=f"stu_{i:04d}",
            local_only_fields={"family_support": a, "address": f"合成地址_{i:04d}"},
            profile_records=records,
        )
        people.append((profile, a))
    return people
