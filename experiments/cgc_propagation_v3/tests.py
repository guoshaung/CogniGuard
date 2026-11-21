"""Deterministic protocol regressions, no real model calls."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest

from .contract import FormatError, validate_wire, validate_report, validate_schema, REPORT_SCHEMA, format_addendum, validate_public_binding
from .reviewer import judge, node_states
from .score import aggregate
from .transport import StrictBudget, NodeContractStopped


def report_value(choice="A"):
    return {"task_id": "TEST", "choice": choice,
            "evidence": [{"source_id": "R1", "quote": "Copper is used for this object."}],
            "note": "A short explanation.", "tool_request": None}


def wire(value=None):
    value = report_value() if value is None else value
    return json.dumps({"answer": "<report>" + json.dumps(value) + "</report>"})


class FakeResponse:
    def __init__(self, body):
        self.body = body.encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self):
        return self.body


class FakeOpener:
    def __init__(self, make_content):
        self.make_content, self.count = make_content, 0
    def open(self, request, timeout):
        self.count += 1
        payload = json.loads(request.data)
        content = self.make_content(self.count, payload)
        if isinstance(content, Exception):
            raise content
        return FakeResponse(json.dumps({"model": "offline_http_fixture", "choices": [{"finish_reason": "stop",
            "message": {"content": content}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}))


class FakeClient:
    key, base_url, model, timeout = "unit-test-not-a-real-key", "https://invalid.test", "offline_http_fixture", 1
    def __init__(self, make_content):
        self.opener = FakeOpener(make_content)


class ContractTests(unittest.TestCase):
    def test_valid_answer(self):
        self.assertEqual(validate_wire(wire())[2], "valid_answer")

    def test_refusal(self):
        self.assertEqual(validate_wire(wire(report_value(None)))[2], "refusal")

    def test_no_answer_repair_or_reserialization(self):
        content = wire()
        outer, inner, status = validate_wire(content)
        self.assertEqual(outer["answer"], json.loads(content)["answer"])

    def test_yaml_inner_rejected(self):
        with self.assertRaises(FormatError):
            validate_wire(json.dumps({"answer": "<report>task_id: TEST, choice: A</report>"}))

    def test_outer_extra_field_rejected(self):
        value = json.loads(wire())
        value["tool_request"] = None
        with self.assertRaises(FormatError):
            validate_wire(json.dumps(value))

    def test_missing_close_tag_rejected(self):
        with self.assertRaises(FormatError):
            validate_wire(wire().replace("</report>", ""))

    def test_duplicate_inner_key_rejected(self):
        with self.assertRaises(FormatError):
            validate_wire(json.dumps({"answer": '<report>{"choice":null,"choice":"A"}</report>'}))

    def test_duplicate_outer_key_rejected(self):
        with self.assertRaises(FormatError):
            validate_wire('{"answer":"a", "answer":"b"}')

    def test_non_json_constants_rejected(self):
        with self.assertRaises(FormatError):
            validate_report('<report>{"choice": NaN}</report>')

    def test_all_required_fields(self):
        for key in report_value():
            value = report_value()
            del value[key]
            with self.subTest(field=key), self.assertRaises(FormatError):
                validate_wire(wire(value))

    def test_wrong_types_and_extra_fields(self):
        for key, bad in (("choice", False), ("task_id", 7), ("evidence", {}), ("note", None), ("tool_request", [])):
            value = report_value()
            value[key] = bad
            with self.subTest(field=key), self.assertRaises(FormatError):
                validate_wire(wire(value))
        value = report_value()
        value["evidence"][0]["score"] = 1
        with self.assertRaises(FormatError):
            validate_wire(wire(value))

    def test_evidence_and_tool_semantics_not_a_new_defense(self):
        value = report_value("A")
        value["evidence"][0]["quote"] = "A completely invented factual claim."
        value["tool_request"] = {"name": "read_profile", "student": "synthetic_other"}
        self.assertEqual(validate_wire(wire(value))[2], "valid_answer")

    def test_public_task_binding(self):
        with self.assertRaises(FormatError):
            validate_public_binding(report_value(), {"task_id": "OTHER", "choices": {"A": "x"}})

    def test_public_choice_enum(self):
        with self.assertRaises(FormatError):
            validate_public_binding(report_value("Z"), {"task_id": "TEST", "choices": {"A": "x"}})

    def test_wire_example_is_valid(self):
        line = next(s for s in format_addendum().splitlines() if s.startswith("Exact valid wire example: "))
        self.assertEqual(validate_wire(line.removeprefix("Exact valid wire example: "))[2], "refusal")

    def test_fail_closed_unknown_schema_keyword(self):
        schema = dict(REPORT_SCHEMA, not_implemented=True)
        with self.assertRaises(RuntimeError):
            validate_schema(report_value(), schema)

    def test_independent_reviewer_has_no_defense_or_gate_import(self):
        for name in ("reviewer.py", "score.py"):
            tree = ast.parse(Path(__file__).with_name(name).read_text())
            modules = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
            self.assertFalse(any(any(k in m for k in ("contract", "evidence_protocol", "fact_release", "defenses")) for m in modules))

    def test_unknown_and_not_executed_are_null(self):
        case = {"case_id": "x", "task_id": "TEST", "pair_index": 1, "condition": "normal", "family": "test", "hops": 2}
        missing = judge(None, case, {"answer_key": "A"}, [])
        self.assertEqual(missing["outcome"], "not_executed")
        self.assertIsNone(missing["correct"])
        for outcome in ("format_error", "transport_error"):
            row = judge({"status": "error", "method": "NoDefense"}, case, {"answer_key": "A"}, [{"status": outcome}])
            self.assertEqual(row["outcome"], outcome)
            self.assertIsNone(row["correct"])

    def test_partial_accuracy_and_asr_withheld(self):
        rows = [{"method": "NoDefense", "pair_index": 0, "condition": "normal", "known": False,
                 "outcome": "format_error", "correct": None, "attack_success": None}]
        item = aggregate(rows, 20, False)[0]
        self.assertIsNone(item["normal_accuracy"]["rate"])
        self.assertIsNone(item["final_asr"]["rate"])
        self.assertEqual(item["normal_accuracy"]["ci95"], [None, None])

    def test_transport_error_distinct_from_format(self):
        with tempfile.TemporaryDirectory() as directory:
            budget = StrictBudget(Path(directory)/"calls.jsonl", 1, FakeClient(lambda *_: TimeoutError()))
            with self.assertRaises(NodeContractStopped):
                budget.call("test", {})
            self.assertEqual(budget.records[0]["status"], "transport_error")

    def test_format_failure_response_preserved(self):
        bad = '{"answer":"<report>task_id: TEST</report>"}'
        with tempfile.TemporaryDirectory() as directory:
            budget = StrictBudget(Path(directory)/"calls.jsonl", 1, FakeClient(lambda *_: bad))
            with self.assertRaises(NodeContractStopped):
                budget.call("test", {})
            self.assertEqual(budget.records[0]["status"], "format_error")
            self.assertEqual(json.loads(budget.records[0]["raw_http_body"])["choices"][0]["message"]["content"], bad)


class RuntimeTests(unittest.TestCase):
    def run_mock(self, fail_at):
        from cogniguard.workflows.teachers.catalog import PromptLibrary
        from cogniguard.workflows.teachers.store import SQLiteTeacherAuditStore
        from experiments.cgc_propagation_v2.live import execute, EmptySkills
        from .runner import prompt_document, contract_cases
        case = contract_cases()[0]
        def content(index, body):
            value = report_value()
            value["task_id"] = case["task_id"]
            if index == fail_at:
                return '{"answer":"<report>task_id: broken</report>"}'
            return wire(value)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path/"prompts.yaml").write_text(json.dumps(prompt_document()), encoding="utf-8")
            library = PromptLibrary(path/"prompts.yaml")
            store = SQLiteTeacherAuditStore(path/"audit.sqlite3")
            store.sync_catalogs(library, EmptySkills())
            budget = StrictBudget(path/"calls.jsonl", 2, FakeClient(content))
            raw = execute(case, "NoDefense", library, store, budget)
            return raw, budget.records, case

    def test_first_node_failure_stops_second(self):
        raw, calls, case = self.run_mock(1)
        self.assertEqual(raw["status"], "error")
        self.assertEqual(len(calls), 1)
        self.assertEqual([s["outcome"] for s in node_states(case, calls)], ["format_error", "not_executed"])
        self.assertFalse(any(e["source"] == "agent_01" for e in raw["trace"]["edges"]))

    def test_later_node_failure_stops_before_delivery(self):
        raw, calls, case = self.run_mock(2)
        self.assertEqual(raw["status"], "error")
        self.assertEqual([s["outcome"] for s in node_states(case, calls)], ["valid_answer", "format_error"])
        self.assertEqual(raw["answer"], "")

    def test_all_nodes_valid(self):
        raw, calls, case = self.run_mock(99)
        self.assertEqual(raw["status"], "completed")
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(s["outcome"] == "valid_answer" for s in node_states(case, calls)))


def run_pure_tests(include_runtime=False, include_legacy=False):
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests)
    if include_runtime:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeTests))
    v3_count = suite.countTestCases()
    if include_legacy:
        from experiments.cgc_propagation_v2 import test_protocol, test_integration
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_protocol))
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_integration))
    result = unittest.TestResult()
    suite.run(result)
    return {"passed": result.wasSuccessful(), "test_count": result.testsRun,
            "v3_test_count": v3_count, "legacy_v2_test_count": result.testsRun-v3_count,
            "failure_count": len(result.failures), "error_count": len(result.errors),
            "execution": "offline_protocol_tests_not_model_performance"}


if __name__ == "__main__":
    unittest.main()
