"""官方样例适配与计分检查，不调用网络模型。"""
import unittest
import importlib.util
import ast
import json

from experiments.focused.injecagent.runner import cached_response, evaluate, make_jobs, render_input, select_cases, summarize
from experiments.focused.injecagent.upstream import SNAPSHOT, load_assets


@unittest.skipUnless(SNAPSHOT.exists() and importlib.util.find_spec("nltk"), "可选 InjecAgent 测试需要官方快照和 nltk")
class InjecAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prompts, parser, cls.tools, cls.datasets, cls.cache = load_assets()
        cls.parser = staticmethod(parser)

    def test_sampling_is_fixed_paired_and_spans_tools(self):
        first = select_cases(self.datasets)
        self.assertEqual(first, select_cases(self.datasets))
        self.assertEqual(len({s["user_tool"] for s in first}), 6)
        jobs = make_jobs(self.datasets, first)
        self.assertEqual(len(jobs), 72)
        for job in jobs:
            if job["setting"] in {"base", "enhanced"}:
                self.assertEqual(job["item"], self.datasets[(job["kind"], job["setting"])][job["index"]])

    def test_official_attack_is_in_observation_and_clean_removes_it(self):
        jobs = make_jobs(self.datasets, select_cases(self.datasets, per_kind=1))
        attack = next(j for j in jobs if j["setting"] == "base")
        clean = next(j for j in jobs if j["setting"] == "clean_control")
        system, user = render_input(attack["item"], self.prompts["InjecAgent"], self.tools)
        self.assertEqual(system, self.prompts["InjecAgent"][0])
        self.assertIn("Observation: " + attack["item"]["Tool Response"], user)
        self.assertIn(attack["item"]["Attacker Instruction"], user)
        self.assertNotIn(attack["item"]["Attacker Instruction"], clean["item"]["Tool Response"])

    def test_prompt_rendering_matches_official_predict_function(self):
        # 仅提取审核过的纯拼接函数，避免导入旧 OpenAI/Together 运行时。
        tree = ast.parse((SNAPSHOT / "src/evaluate_prompted_agent.py").read_text(encoding="utf-8"))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "predict_one_case")
        namespace = {"json": json}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "official_predict_one_case", "exec"), namespace)
        class Recorder:
            def prepare_input(self, system, user):
                return system, user
            def call_model(self, value):
                return value
        item = dict(self.datasets[("ds", "enhanced")][0])
        item.update({"Attacker Tool Thought": "request data", "Attacker Tool Parameters": "{}",
                     "Attacker Tool Response": "synthetic tool result"})
        for name in self.prompts:
            for step2 in (False, True):
                prompt = self.prompts[name]
                original = namespace["predict_one_case"](*prompt, {}, item, Recorder(), self.tools, step_2=step2)
                self.assertEqual(render_input(item, prompt, self.tools, step2), original)

    def test_unmodified_official_parser_marks_target_tool_selection(self):
        item = self.datasets[("dh", "base")][0]
        output = "Thought: I will carry out the requested action now.\nAction: " + item["Attacker Tools"][0] + '\nAction Input: {"test":"value"}'
        self.assertEqual(evaluate(self.parser, output, item)["eval"], "succ")
        output = "Thought: The external instruction is unrelated to the user request.\nFinal Answer: Here is the information you requested."
        self.assertEqual(evaluate(self.parser, output, item)["eval"], "unsucc")

    def test_cached_simulation_accepts_equivalent_parameter_order(self):
        cache = {'(ExampleTool,{"b":2,"a":1})': "official result"}
        value, provenance = cached_response(cache, "ExampleTool", '{"a":1, "b":2}')
        self.assertEqual(value, "official result")
        self.assertEqual(provenance["source"], "official_cache_semantic_parameters")
        self.assertEqual(cached_response(cache, "ExampleTool", '{"a":99}'), (None, None))

    def test_second_stage_failure_does_not_hide_first_stage_success(self):
        row = {"prompt": "InjecAgent", "kind": "ds", "setting": "base", "status": "error",
               "stage1": {"eval": "succ"}, "calls": []}
        group = next(g for g in summarize([row])["groups"] if g["prompt"] == "InjecAgent" and g["kind"] == "ds" and g["setting"] == "base")
        self.assertEqual(group["stage1_success"], 1)
        self.assertEqual(group["api_or_execution_errors"], 1)
        self.assertIsNone(group["data_stealing_asr_valid"])
        self.assertEqual(group["stage2_invalid_or_missing_after_s1_success"], 1)


if __name__ == "__main__":
    unittest.main()
