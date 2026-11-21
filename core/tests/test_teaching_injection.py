"""教学注入 A/B 的结构性防御离线校验；不调用网络模型。

这些断言是实验结论的确定性基础：无论模型是否被骗，数据最小化与访问控制在代码层
已经决定了敏感字段能否进入模型输入、跨学生读取能否成功。
"""
import json
import unittest

from experiments.focused.teaching_injection.cases import build_cases
from experiments.focused.teaching_injection.runner import (
    config, execute_tool, fixture, prepare,
)


class TeachingInjectionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.settings = config()
        self.cases = {c.case_id: c for c in build_cases()}

    def test_own_secret_enters_unprotected_input_but_not_protected(self):
        """数据最小化：无保护把私密字段交给模型，CogniGuard 结构上不会。"""
        for case in build_cases():
            if case.goal != "own":
                continue
            with self.subTest(case=case.case_id):
                _, _, _, _, _, secrets = fixture(case)
                unprotected, *_ = prepare(case, False, self.settings)
                protected, *_ = prepare(case, True, self.settings)
                un_text = json.dumps(unprotected, ensure_ascii=False)
                pr_text = json.dumps(protected, ensure_ascii=False)
                self.assertTrue(any(s in un_text for s in secrets["own"]),
                                "无保护组应当把私密字段直接放进模型输入")
                self.assertFalse(any(s in pr_text for s in secrets["own"]),
                                 "CogniGuard 组不得让私密字段进入模型输入")

    def test_protected_card_still_carries_teaching_signal(self):
        """最小化不能把画像抹成空：个性化教学需要的掌握/错误/偏好信号应保留。"""
        case = self.cases["clean_resource"]
        protected, *_ = prepare(case, True, self.settings)
        card = protected["student_record"]
        self.assertIsInstance(card, str)
        self.assertIn(KNOWLEDGE_HINT, card)

    def test_cross_student_tool_denied_only_when_protected(self):
        """访问控制：跨学生读取在无保护下成功、在 CogniGuard 下被拒。"""
        case = self.cases["cross_student_compare"]
        _, _, _, _, _, secrets = fixture(case)
        other_secret = secrets["other"][0]
        action = {"tool": "read_profile", "student_id": "synthetic_other"}

        _, pipeline, profile, other, _, _ = prepare(case, False, self.settings)
        data, trace = execute_tool(action, False, pipeline, profile, other)
        self.assertTrue(trace["cross_student_read_succeeded"])
        self.assertIn(other_secret, json.dumps(data, ensure_ascii=False))

        _, pipeline, profile, other, _, _ = prepare(case, True, self.settings)
        data, trace = execute_tool(action, True, pipeline, profile, other)
        self.assertFalse(trace["cross_student_read_succeeded"])
        self.assertEqual(data, {"error": "access_denied"})

    def test_own_student_tool_returns_minimal_card_without_secret(self):
        """读取本人也只拿到最小卡片，不含本地私密字段原值。"""
        case = self.cases["cross_student_compare"]
        _, _, _, _, _, secrets = fixture(case)
        _, pipeline, profile, other, _, _ = prepare(case, True, self.settings)
        data, trace = execute_tool({"tool": "read_profile", "student_id": "synthetic_self"},
                                   True, pipeline, profile, other)
        self.assertEqual(trace["decision"], "allow_minimal_card")
        self.assertNotIn(secrets["own"][0], json.dumps(data, ensure_ascii=False))

    def test_verbatim_resource_is_not_quoted_whole_when_protected(self):
        """受版权资料：无保护把原文整段交给模型，CogniGuard 按策略摘要/拒绝，marker 不整段出现。"""
        case = self.cases["resource_verbatim_quote"]
        _, _, _, _, _, secrets = fixture(case)
        marker = secrets["verbatim"]
        unprotected, *_ = prepare(case, False, self.settings)
        protected, _, _, _, mode, _ = prepare(case, True, self.settings)
        self.assertIn(marker, unprotected["reference"])
        self.assertNotEqual(mode, "quote")
        self.assertNotIn(marker, protected["reference"])

    def test_clean_cases_have_no_injection(self):
        for case in build_cases():
            if case.family == "clean":
                self.assertEqual(case.goal, "none")


KNOWLEDGE_HINT = "顶点"


if __name__ == "__main__":
    unittest.main()
