"""新入口的关键边界：隐私、会话状态、独立环境和结果保护。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.pipeline import ProtectionPipeline, load_inputs
from core.access import AccessScope
from experiments.focused.evaluate import evaluate

ROOT = Path(__file__).resolve().parents[2]
INPUTS = (
    ROOT / "configs/focused.yaml",
    ROOT / "protection/student_profile/data/profiles.jsonl",
    ROOT / "protection/student_profile/data/student_questions.jsonl",
    ROOT / "protection/teacher_resource/data/teacher_resources.jsonl",
)


class FocusedBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.config, self.profiles, self.questions, self.resources = load_inputs(*INPUTS)

    def test_local_secret_does_not_enter_output(self):
        question = self.questions[0]
        profile = self.profiles[question["student_id"]]
        profile.local_only_fields["address"] = "PRIVATE_ADDRESS_SENTINEL_8821"
        result = ProtectionPipeline(self.config, self.resources).run(profile, question, access=AccessScope(profile.student_id))
        self.assertNotIn("PRIVATE_ADDRESS_SENTINEL_8821", json.dumps(result.to_dict()))

    def test_budget_is_session_local(self):
        question = self.questions[0]
        profile = self.profiles[question["student_id"]]
        pipeline = ProtectionPipeline(self.config, self.resources)
        first = pipeline.run(profile, question, access=AccessScope(profile.student_id))
        chunk = first.controlled.resource.chunk_id
        self.assertGreater(pipeline.budget.get(chunk), 0)
        fresh = ProtectionPipeline(self.config, self.resources)
        self.assertEqual(fresh.budget.get(chunk), 0)
        self.assertEqual(fresh.run(profile, question, access=AccessScope(profile.student_id)).controlled.exposure_before, 0)

    def test_no_resource_and_wrong_profile(self):
        question = next(q for q in self.questions if not q["need_resource"])
        pipeline = ProtectionPipeline(self.config, self.resources)
        self.assertIsNone(pipeline.run(self.profiles[question["student_id"]], question, access=AccessScope(question["student_id"])).controlled)
        wrong = next(p for p in self.profiles.values() if p.student_id != question["student_id"])
        with self.assertRaises(ValueError):
            pipeline.run(wrong, question, access=AccessScope(question["student_id"]))

    def test_evaluation_cannot_overwrite_results(self):
        with tempfile.TemporaryDirectory() as temp:
            output = evaluate(*INPUTS, Path(temp) / "run")
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["num_requests"], len(self.questions))
            self.assertEqual(summary["status"], "SMOKE_ONLY")
            with self.assertRaises(FileExistsError):
                evaluate(*INPUTS, output)

    def test_demo_has_no_backend_experiment_or_model_imports(self):
        script = """
import runpy, sys
sys.argv = ['cogniguard', 'demo']
runpy.run_module('cogniguard', run_name='__main__')
blocked = ('backend', 'experiments', 'torch', 'transformers')
assert not [name for name in sys.modules if name.split('.')[0] in blocked]
"""
        subprocess.run([sys.executable, "-c", script], cwd=ROOT, check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
