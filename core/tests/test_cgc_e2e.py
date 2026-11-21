"""CGC 端到端统一控制的关键性质离线校验。"""
import tempfile
import unittest
from pathlib import Path

from experiments.focused.cgc_e2e.runner import cgc_decision, run, siloed_decision
from experiments.focused.cgc_e2e.scenarios import build_scenarios


class CgcE2ETests(unittest.TestCase):
    def setUp(self):
        self.cases = {s.scenario_id: s for s in build_scenarios()}

    def test_cross_domain_fusion_caught_by_cgc_not_siloed(self):
        sc = self.cases["cross_domain_moderate"]
        self.assertFalse(siloed_decision(sc)["reacted"])   # 各域 0.5 < 0.85，siloed 放行
        self.assertTrue(cgc_decision(sc)["reacted"])        # CGC 融合后有反应

    def test_capability_denied_blocked_only_by_cgc(self):
        sc = self.cases["capability_denied"]
        self.assertFalse(siloed_decision(sc)["reacted"])
        self.assertEqual(cgc_decision(sc)["action"], "block")

    def test_provenance_and_audit_caught_only_by_cgc(self):
        for cid in ("provenance_invalid", "audit_tampered"):
            sc = self.cases[cid]
            self.assertFalse(siloed_decision(sc)["reacted"], cid)
            self.assertEqual(cgc_decision(sc)["action"], "refuse", cid)

    def test_budget_exhausted_triggers_rollback(self):
        c = cgc_decision(self.cases["budget_exhausted"])
        self.assertEqual(c["action"], "quarantine")
        self.assertTrue(c["rollback"])
        self.assertFalse(c["payload_delivered"])

    def test_clean_not_overblocked(self):
        self.assertFalse(cgc_decision(self.cases["clean_low"])["hard_stop"])
        self.assertFalse(cgc_decision(self.cases["untrusted_data_ok"])["hard_stop"])

    def test_run_summary_shows_cgc_advantage_and_audit_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, summary = run(Path(tmp) / "run")
            self.assertGreater(len(summary["caught_by_cgc_only"]), 0)
            self.assertEqual(summary["safe_overblocked_by_cgc"], [])
            self.assertGreater(summary["cgc_accuracy"], summary["siloed_accuracy"])
            self.assertTrue(summary["audit_verify_clean"])
            self.assertFalse(summary["audit_verify_after_tamper"])
            # 信任分随连续违规下降
            self.assertEqual(summary["trust_trajectory"], sorted(summary["trust_trajectory"], reverse=True))
            self.assertLess(summary["trust_trajectory"][-1], 1.0)


if __name__ == "__main__":
    unittest.main()
