"""教学事实正确性校验器的离线校验；不调用模型。"""
import unittest
from fractions import Fraction

from experiments.focused.factuality.tasks import build_tasks
from experiments.focused.factuality.runner import verify


class FactualityTests(unittest.TestCase):
    def setUp(self):
        self.tasks = {t.task_id: t for t in build_tasks()}

    def test_truth_computation(self):
        t = self.tasks["easy_1"]  # a=1,h=2,k=-3 -> b=-4, c=1
        self.assertEqual(t.truth["vertex"], [Fraction(2), Fraction(-3)])
        self.assertEqual(t.truth["axis"], Fraction(2))
        self.assertEqual(t.truth["expanded"], {"a": Fraction(1), "b": Fraction(-4), "c": Fraction(1)})

    def test_verifier_accepts_correct_and_decimal_fraction(self):
        t = self.tasks["easy_1"]
        out = {"vertex": [2, -3], "axis": 2, "expanded": {"a": 1, "b": -4, "c": 1}, "answer": "..."}
        self.assertTrue(verify(t, out)["correct"])
        # 分数的两位小数近似也应通过（容差）
        hard = self.tasks["hard_2"]  # 可能是分数顶点
        tr = hard.truth
        approx = {"vertex": [round(float(tr["vertex"][0]), 2), round(float(tr["vertex"][1]), 2)],
                  "axis": round(float(tr["axis"]), 2),
                  "expanded": {"a": float(tr["expanded"]["a"]), "b": float(tr["expanded"]["b"]), "c": float(tr["expanded"]["c"])}}
        self.assertTrue(verify(hard, approx)["correct"])

    def test_verifier_catches_wrong_vertex(self):
        t = self.tasks["easy_1"]
        out = {"vertex": [-2, -3], "axis": -2, "expanded": {"a": 1, "b": -4, "c": 1}, "answer": "..."}
        self.assertFalse(verify(t, out)["correct"])

    def test_poison_propagation_flagged(self):
        t = self.tasks["poison_1"]  # a=1,h=4,k=-5 ; 错误规则顶点横坐标 -4
        # 模型输出用普通 JSON 数字（与真实情况一致），顶点横坐标取了错误规则的 -4
        out = {"vertex": [-4, -5], "axis": -4, "expanded": {"a": 1, "b": -8, "c": 11}, "answer": ".."}
        v = verify(t, out)
        self.assertTrue(v["followed_poison"])
        self.assertFalse(v["correct"])


if __name__ == "__main__":
    unittest.main()
