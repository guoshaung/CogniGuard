"""MM-FOPD 属性推断攻击的关键性质离线校验（需要 sklearn）。"""
import importlib.util
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec("sklearn"), "需要 sklearn")
class PrivacyAttackTests(unittest.TestCase):
    def test_explicit_exposure_and_mmfopd_card_drops_sensitive_field(self):
        from experiments.focused.privacy_attack.population import make_population
        from experiments.focused.privacy_attack.runner import config, release
        settings = config()
        (profile, a) = make_population(n=4, seed=1)[0]
        full = release(profile, "FullProfile", settings)
        card = release(profile, "MM-FOPD", settings)
        self.assertIn("family_support=", full)           # FullProfile 泄露显式敏感字段
        self.assertNotIn("family_support=", card)         # MM-FOPD 卡片不含显式字段
        self.assertEqual(release(profile, "NoProfile", settings), "")

    def test_attack_accuracy_ordering(self):
        from experiments.focused.privacy_attack.runner import run
        with tempfile.TemporaryDirectory() as tmp:
            _, summary = run(Path(tmp) / "run", n=300, seeds=(1, 2, 3))
            m = summary["mechanisms"]
            # 显式暴露率：FullProfile=1，MM-FOPD/NoProfile=0。
            self.assertEqual(m["FullProfile"]["explicit_exposure_rate"], 1.0)
            self.assertEqual(m["MM-FOPD"]["explicit_exposure_rate"], 0.0)
            # 攻击准确率：FullProfile（显式）> MM-FOPD（残留）；NoProfile ≈ base rate。
            self.assertGreater(m["FullProfile"]["attack_accuracy_mean"], m["MM-FOPD"]["attack_accuracy_mean"])
            self.assertLessEqual(m["NoProfile"]["attack_accuracy_mean"], m["NoProfile"]["base_rate"] + 0.05)
            # MM-FOPD 显式暴露为 0，但残留推断仍 > base rate（“选择率≠隐私”的量化证据）。
            self.assertGreater(m["MM-FOPD"]["attack_accuracy_mean"], m["MM-FOPD"]["base_rate"] + 0.02)


if __name__ == "__main__":
    unittest.main()
