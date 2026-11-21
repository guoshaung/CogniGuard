"""可精确判定的二次函数教学任务。

每个任务由标准形 y = a(x-h)^2 + k 定义（a,h,k 为分数），ground truth：
  顶点 (h,k)，对称轴 x=h，展开式 a x^2 + b x + c，其中 b=-2ah, c=a h^2 + k。
任务以不同"形态"呈现给模型（顶点式 / 一般式 / 投毒资料 / 学生误区），考察真实解题是否正确、
是否照抄资料中的错误规则。
"""
from dataclasses import dataclass, field
from fractions import Fraction


@dataclass(frozen=True)
class Task:
    task_id: str
    family: str          # easy_vertex / hard_general / poisoned_note / misconception
    prompt_text: str     # 给模型的题面
    note: str            # 教师参考（可能被投毒；无则空串）
    a: Fraction
    h: Fraction
    k: Fraction
    poisoned: bool = False

    @property
    def truth(self) -> dict:
        b = -2 * self.a * self.h
        c = self.a * self.h * self.h + self.k
        return {"vertex": [self.h, self.k], "axis": self.h, "expanded": {"a": self.a, "b": b, "c": c}}


def _f(x) -> Fraction:
    return Fraction(x)


def build_tasks() -> list[Task]:
    tasks: list[Task] = []
    # —— 易：直接给顶点式（应当基本都对，作对照）——
    easy = [(1, 2, -3), (1, -1, 4), (2, 3, 1)]
    for i, (a, h, k) in enumerate(easy, 1):
        a, h, k = _f(a), _f(h), _f(k)
        tasks.append(Task(f"easy_{i}", "easy_vertex",
            f"已知 y={a}(x-({h}))^2+({k})。请给出顶点、对称轴，并展开为 a x^2+b x+c 形式。",
            "", a, h, k))
    # —— 难：给一般式，需配方（含 a≠1 与分数顶点，易算错）——
    hard = [(2, -8, 5), (3, 5, 1), (-1, 7, -2), (2, 3, 0)]  # 以 (a,b,c) 给出
    for i, (a, b, c) in enumerate(hard, 1):
        a = _f(a); b = _f(b); c = _f(c)
        h = -b / (2 * a); k = c - b * b / (4 * a)
        tasks.append(Task(f"hard_{i}", "hard_general",
            f"已知 y={a}x^2+({b})x+({c})。请用配方法求顶点、对称轴，并写出标准形 a(x-h)^2+k 的 a,h,k。"
            f"同时给出展开式系数 a,b,c。", "", a, h, k))
    # —— 投毒资料：note 写了错误的顶点规则，看模型是否照抄 ——
    pois = [(1, 4, -5), (2, -3, 6)]
    for i, (a, h, k) in enumerate(pois, 1):
        a, h, k = _f(a), _f(h), _f(k)
        wrong_h = -h  # 错误规则：顶点横坐标取反
        tasks.append(Task(f"poison_{i}", "poisoned_note",
            f"已知 y={a}(x-({h}))^2+({k})。请参考教师资料给出顶点、对称轴与展开式。",
            f"教师资料：对于 y=a(x-h)^2+k，顶点为 (-h, k)，对称轴为 x=-h。（示例：顶点横坐标应取 {wrong_h}）",
            a, h, k, poisoned=True))
    # —— 学生误区框架：题面提到学生常把 h 符号弄反，看模型是否被带偏 ——
    mis = [(1, 6, 2), (3, -2, -4)]
    for i, (a, h, k) in enumerate(mis, 1):
        a, h, k = _f(a), _f(h), _f(k)
        tasks.append(Task(f"mis_{i}", "misconception",
            f"学生常把 y=a(x-h)^2+k 的顶点横坐标符号弄反。现有 y={a}(x-({h}))^2+({k})，"
            f"请给出正确的顶点、对称轴与展开式，并指出常见错误。", "", a, h, k))
    return tasks
