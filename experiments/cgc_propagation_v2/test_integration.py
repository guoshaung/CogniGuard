"""Real unchanged LangGraph runtime with deterministic test backends, no API."""
import json
from pathlib import Path
import tempfile
import unittest

from .dataset import METHODS, public_pair, report
from .live import execute, prompt_document, EmptySkills
from .oracle import inspect
from .test_protocol import sample


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        from cogniguard.workflows.teachers.catalog import PromptLibrary
        from cogniguard.workflows.teachers.store import SQLiteTeacherAuditStore
        self.directory = tempfile.TemporaryDirectory(prefix="cgc-independent-test-")
        path = Path(self.directory.name)
        (path / "prompts.yaml").write_text(json.dumps(prompt_document()), encoding="utf-8")
        self.library = PromptLibrary(path / "prompts.yaml")
        self.store = SQLiteTeacherAuditStore(path / "audit.sqlite3")
        self.store.sync_catalogs(self.library, EmptySkills())

    def tearDown(self):
        self.directory.cleanup()

    def trial(self, case, method):
        raw = execute(case, method, self.library, self.store)
        self.assertFalse(raw["audit_errors"])
        self.assertNotEqual(raw["status"], "error")
        return raw

    def test_signed_forged_source_passes_signature_not_full(self):
        _, case = public_pair(sample(), 0, 3, "forged_citation", "pilot")
        signature = self.trial(case, "SignatureOnly")
        full = self.trial(case, "FullCGC")
        self.assertTrue(any(inspect(m["text"], case)["hazard"] for m in signature["receiver_inputs"]))
        self.assertFalse(any(inspect(m["text"], case)["hazard"] for m in full["receiver_inputs"]))
        self.assertEqual(len([n for n in signature["trace"]["nodes"] if n.get("status") == "ok"]), 5)

    def test_unsigned_tamper_observed_only_in_nodefense(self):
        _, case = public_pair(sample(), 1, 2, "forged_citation", "pilot")
        none = self.trial(case, "NoDefense")
        signature = self.trial(case, "SignatureOnly")
        self.assertTrue(any(not m["chain_valid"] for m in none["receiver_inputs"]))
        self.assertTrue(all(m["chain_valid"] for m in signature["receiver_inputs"]))
        self.assertEqual(len(none["receiver_inputs"]), 3)
        self.assertEqual(len(signature["receiver_inputs"]), 2)

    def test_finalonly_pre_release_pollution_is_not_final_delivery(self):
        _, case = public_pair(sample(), 0, 2, "forged_citation", "pilot")
        raw = self.trial(case, "FinalOnly")
        self.assertEqual(raw["status"], "blocked")
        self.assertEqual(raw["answer"], "")
        self.assertTrue(any(inspect(m["text"], case)["hazard"] for m in raw["receiver_inputs"]))

    def test_context_genuine_quotes_are_existing_guard_blind_spot(self):
        _, case = public_pair(sample(), 0, 5, "context_pollution", "pilot")
        raw = self.trial(case, "FullCGC")
        self.assertEqual(raw["status"], "completed")
        self.assertTrue(inspect(raw["answer"], case)["context_directive_exposure"])

    def test_tool_request_blocked_without_real_execution(self):
        _, case = public_pair(sample(), 0, 2, "tool_injection", "pilot")
        raw = self.trial(case, "FullCGC")
        self.assertFalse(any(inspect(m["text"], case)["unsafe_tool_request"] for m in raw["receiver_inputs"]))

    def test_clean_benign_quoted_cue_not_blocked(self):
        normal, _ = public_pair(sample(), 0, 5, "context_pollution", "pilot")
        for method in METHODS:
            raw = self.trial(normal, method)
            self.assertEqual(raw["status"], "completed")
            self.assertEqual(len(raw["receiver_inputs"]), 6)


if __name__ == "__main__":
    unittest.main()
