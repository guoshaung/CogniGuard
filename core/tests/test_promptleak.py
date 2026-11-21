"""系统提示泄露实验的离线性质校验；不调用模型。"""
import re
import unittest

from experiments.focused.promptleak.runner import (
    SECRET_PATTERNS, build_system, hygiene_scan,
)


class PromptLeakTests(unittest.TestCase):
    def test_secret_only_in_bad_variant(self):
        bad = build_system("secret_in_prompt", "CANARY_x", "ADDR_x", "KEY_x")
        good = build_system("cogniguard", "CANARY_x", "ADDR_x", "KEY_x")
        self.assertIn("ADDR_x", bad)
        self.assertIn("KEY_x", bad)
        self.assertNotIn("ADDR_x", good)   # cogniguard 提示里没有数据/凭证
        self.assertNotIn("KEY_x", good)
        self.assertIn("CANARY_x", good)     # 但有 canary 标记

    def test_hygiene_scan_detects_planted_secret(self):
        # 正则确实能抓到常见密钥/口令形态
        self.assertTrue(re.search(SECRET_PATTERNS["api_key_sk"], "config sk-ABCD1234567890"))
        self.assertTrue(re.search(SECRET_PATTERNS["password_kv"], "管理员口令=hunter2"))

    def test_real_project_prompts_are_clean(self):
        result = hygiene_scan()
        self.assertGreater(len(result["scanned_prompts"]), 0)
        self.assertTrue(result["clean"], f"系统提示卫生发现: {result['secret_findings']}")


if __name__ == "__main__":
    unittest.main()
