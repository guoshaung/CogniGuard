"""任务定义。parameters 只供事后评分；Agent 只能看到 public_question。"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Task:
    task_id: str
    kind: str
    parameters: tuple[int, ...]
    public_question: str

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        return cls(value["task_id"], value["kind"], tuple(value["parameters"]), value["public_question"])

    def expected_result(self) -> dict:
        # 评分真值直接来自冻结任务参数，不调用防护侧的公式解析器。
        if self.kind == "quadratic":
            h, k = self.parameters
            return {"vertex": [h, k], "axis": h}
        a, b, c = self.parameters
        return {"x": (c - b) / a}


def quadratic(task_id: str, h: int, k: int) -> Task:
    expression = f"y=(x{-h:+d})^2{k:+d}"
    return Task(task_id, "quadratic", (h, k), f"任务ID={task_id}。求 {expression} 的顶点、对称轴，解释平移并给一次自检。")


def linear(task_id: str, a: int, b: int, c: int) -> Task:
    return Task(task_id, "linear", (a, b, c), f"任务ID={task_id}。解方程 {a}x{b:+d}={c}，说明步骤并代回验证。")
