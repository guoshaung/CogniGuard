"""供应链制品完整性门的离线校验。"""
import tempfile
import unittest
from pathlib import Path

from experiments.focused.supplychain.inventory import build_inventory, collect_actual
from experiments.focused.supplychain.runner import cgc_gate, pin, run, verify


class SupplyChainTests(unittest.TestCase):
    def test_clean_verifies_and_loads(self):
        inv = build_inventory()
        lock = pin(inv)
        v = verify(lock, collect_actual(inv))
        self.assertTrue(v["provenance_valid"])
        self.assertTrue(cgc_gate(True)["allowed_to_load"])

    def test_hash_mismatch_blocks(self):
        inv = build_inventory()
        lock = pin(inv)
        actual = collect_actual(inv)
        # 篡改一个可哈希制品
        name = "config_focused"
        actual[name] = {"sha256": "0" * 64, "missing": False}
        v = verify(lock, actual)
        self.assertFalse(v["provenance_valid"])
        self.assertFalse(cgc_gate(v["provenance_valid"])["allowed_to_load"])

    def test_cgc_refuses_on_invalid_provenance(self):
        self.assertEqual(cgc_gate(False)["action"], "refuse")
        self.assertEqual(cgc_gate(True)["action"], "allow")

    def test_run_scenarios(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, summary = run(Path(tmp) / "run")
            self.assertTrue(summary["clean_loads"])
            self.assertTrue(summary["tamper_blocked"])
            self.assertTrue(summary["drift_blocked"])
            # 检测器未 pin revision 应被标记为弱固定
            self.assertIn("detector_protectai", summary["weak_pins"])


if __name__ == "__main__":
    unittest.main()
