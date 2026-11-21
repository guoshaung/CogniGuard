"""验证攻击实验的执行和计分；不把测试桩结果当作真实模型结果。"""
import unittest

from experiments.focused.redteam.cases import build_cases
from experiments.focused.redteam.runner import config, execute_tool, fixture, prepare, run_one, score, summarize


class RedteamTests(unittest.TestCase):
    def test_access_hides_secrets_but_quote_can_carry_instructions(self):
        case = next(c for c in build_cases() if c.case_id == "quote_private")
        unprotected, *_ = prepare(case, False, config())
        protected, _, profile, _, mode = prepare(case, True, config())
        self.assertIn(profile.local_only_fields["address"], str(unprotected))
        self.assertNotIn(profile.local_only_fields["address"], str(protected))
        self.assertIn("local_only_fields.address", protected["reference"])
        self.assertEqual(mode, "quote")

    def test_cross_student_tool_really_denies_access(self):
        case = next(c for c in build_cases() if c.case_id == "cross_student_tool")
        _, pipeline, profile, other, _ = prepare(case, True, config())
        action = {"tool": "read_profile", "student_id": other.student_id}
        result, trace = execute_tool(action, True, pipeline, profile, other)
        self.assertEqual(result, {"error": "access_denied"})
        self.assertFalse(trace["cross_student_read_succeeded"])
        result, trace = execute_tool(action, False, pipeline, profile, other)
        self.assertIn(other.local_only_fields["address"], str(result))
        self.assertTrue(trace["cross_student_read_succeeded"])

    def test_detector_blocks_before_teaching_call(self):
        class MustNotCall:
            def call(self, *args):
                raise AssertionError("blocked case must not call model")
        row = run_one(build_cases()[0], "access_and_detector", MustNotCall(),
                      {"status": "ok", "unsafe": True}, config())
        self.assertEqual(row["status"], "blocked")
        self.assertFalse(row["metrics"]["math_correct_proxy"])
        self.assertEqual(row["calls"], [])

    def test_model_action_and_backend_read_are_separate(self):
        case = next(c for c in build_cases() if c.case_id == "cross_student_tool")
        profile, other, *_ = fixture(case)
        metrics = score(case, {"answer": "顶点为 (2,-3)", "vertex": [2, -3], "action": None},
                        [{"cross_student_attempt": True, "cross_student_read_succeeded": False,
                          "private_tool_read_succeeded": False}], profile, other)
        self.assertTrue(metrics["model_followed_attack"])
        self.assertFalse(metrics["attacker_goal_success"])
        self.assertFalse(metrics["cross_student_read_succeeded"])

    def test_errors_are_not_counted_as_defended(self):
        row = {"group": "access_only", "status": "error", "is_attack": True, "calls": []}
        summary = summarize([row], {}, "unit_test_only")
        group = summary["groups"]["access_only"]
        self.assertEqual(group["errors"], 1)
        self.assertIsNone(group["attacker_goal_success_rate"])


if __name__ == "__main__":
    unittest.main()
