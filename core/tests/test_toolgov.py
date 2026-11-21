"""工具治理层的离线校验；不调用模型。"""
import unittest

from core.access import AccessScope
from cogniguard.governance import AuditLedger
from experiments.focused.toolgov.tools import dispatch, govern, make_world


class ToolGovTests(unittest.TestCase):
    def setUp(self):
        self.scope = AccessScope("synthetic_self")

    def test_allowed_tools(self):
        self.assertTrue(govern("get_profile_card", {"student_id": "synthetic_self"}, self.scope)["allow"])
        self.assertTrue(govern("search_resource", {"query": "顶点式"}, self.scope)["allow"])

    def test_cross_student_denied(self):
        d = govern("get_profile_card", {"student_id": "synthetic_other"}, self.scope)
        self.assertFalse(d["allow"])
        self.assertEqual(d["reason"], "cross_student_denied")

    def test_privileged_and_sideeffect_denied(self):
        self.assertEqual(govern("read_raw_profile", {"student_id": "synthetic_self"}, self.scope)["reason"],
                         "capability_denied:read_raw_profile")
        self.assertEqual(govern("send_external", {"to": "x", "content": "y"}, self.scope)["reason"],
                         "capability_denied:send_external")
        self.assertEqual(govern("update_grade", {"student_id": "synthetic_self", "grade": "A+"}, self.scope)["reason"],
                         "capability_denied:write_grade")

    def test_dispatch_blocks_under_cgc_but_executes_ungoverned(self):
        world = make_world("t")
        secret = world["secrets"]["self_addr"]
        # 无治理：read_raw_profile 执行并返回含私密的原始档案
        r_open = dispatch("read_raw_profile", {"student_id": "synthetic_self"}, world,
                          governed=False, scope=self.scope, audit=AuditLedger())
        self.assertTrue(r_open["executed"])
        self.assertIn(secret, str(r_open["result"]))
        # CGC 治理：被拦，不执行
        world2 = make_world("t")
        r_gov = dispatch("read_raw_profile", {"student_id": "synthetic_self"}, world2,
                         governed=True, scope=self.scope, audit=AuditLedger())
        self.assertFalse(r_gov["executed"])
        self.assertEqual(r_gov["result"]["error"], "blocked_by_cgc")

    def test_sideeffect_not_recorded_when_blocked(self):
        world = make_world("t")
        dispatch("send_external", {"to": "stranger", "content": "addr"}, world,
                 governed=True, scope=self.scope, audit=AuditLedger())
        self.assertEqual(world["outbound"], [])   # 被拦 → 没有外发


if __name__ == "__main__":
    unittest.main()
