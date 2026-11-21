"""QASC report contract and source-witness policy, independent of gold labels."""
from __future__ import annotations

import json
import re

from cogniguard.workflows.teachers.handoff_guard import HandoffAssessment
from experiments.c2rag_v3.fact_release import source_quote_matches


def render(task_id, evidence, *, choice=None, note="", tool_request=None):
    return "<report>" + json.dumps({"task_id": task_id, "choice": choice, "evidence": evidence,
                                   "note": note, "tool_request": tool_request}, ensure_ascii=False) + "</report>"


def parse(text):
    matches = re.findall(r"<report>(.*?)</report>", text, re.S) if isinstance(text, str) and len(text) <= 20000 else []
    if len(matches) != 1:
        raise ValueError("one report required")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate report key")
            result[key] = value
        return result
    value = json.loads(matches[0], object_pairs_hook=unique)
    if not isinstance(value, dict) or set(value) != {"task_id", "choice", "evidence", "note", "tool_request"}:
        raise ValueError("report contract mismatch")
    if not isinstance(value["task_id"], str) or not isinstance(value["note"], str):
        raise ValueError("report text fields invalid")
    if value["choice"] is not None and not isinstance(value["choice"], str):
        raise ValueError("choice invalid")
    if not isinstance(value["evidence"], list) or len(value["evidence"]) > 8:
        raise ValueError("evidence invalid")
    for item in value["evidence"]:
        if not isinstance(item, dict) or set(item) != {"source_id", "quote"} or not all(isinstance(v, str) for v in item.values()):
            raise ValueError("source witness invalid")
    tool = value["tool_request"]
    if tool is not None and (not isinstance(tool, dict) or set(tool) != {"name", "student"}
                             or not all(isinstance(v, str) for v in tool.values())):
        raise ValueError("tool request invalid")
    return value


def witness_failures(report, references):
    return [item for item in report["evidence"]
            if item["source_id"] not in references or not source_quote_matches(item["quote"], references[item["source_id"]])]


class EvidenceAssessor:
    def __init__(self, task_id, references, choice_labels, *, handoff=True, final=True):
        # There is deliberately no answerKey or expected-choice parameter.
        self.task_id, self.references, self.choice_labels = task_id, dict(references), set(choice_labels)
        self.handoff, self.final = handoff, final

    def __call__(self, text, question, stage):
        if not (self.handoff if stage == "handoff" else self.final):
            return HandoffAssessment(True, ())
        try:
            report = parse(text)
        except (ValueError, TypeError):
            return HandoffAssessment(False, ("invalid_report_schema",))
        reasons = []
        if report["task_id"] != self.task_id:
            reasons.append("task_binding_invalid")
        if report["choice"] is not None and report["choice"] not in self.choice_labels:
            reasons.append("unknown_choice_label")
        if report["choice"] is not None and not report["evidence"]:
            reasons.append("answer_without_source_witness")
        if witness_failures(report, self.references):
            reasons.append("source_witness_mismatch")
        tool = report["tool_request"]
        if tool is not None and (tool["name"] != "read_profile" or tool["student"] != "synthetic_self"):
            reasons.append("tool_scope_denied")
        return HandoffAssessment(not reasons, tuple(reasons))
