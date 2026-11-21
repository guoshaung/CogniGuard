"""Domain objects and services for the LangGraph execution layer.

This module does not orchestrate requests. The supported runner is the graph
exposed as ``core.pipeline.ProtectionPipeline``.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.access import ProfileReadPolicy
from core.teaching import TeachingInput
from protection.common.schemas import ControlledResource, Task, TeacherResource
from protection.student_profile.src.fopd.profile_selector import ProfileSelector, ScoredProfileRecord
from protection.student_profile.src.fopd.privacy_budget import PrivacyBudgetLedger
from protection.teacher_resource.src.c2rag.exposure_budget import ExposureBudget
from protection.teacher_resource.src.c2rag.retriever import CopyrightAwareRetriever


@dataclass
class ProtectionResult:
    task: Task
    context_card: str
    selected: list[ScoredProfileRecord]
    controlled: ControlledResource | None
    answer: str
    privacy_evidence: dict
    teaching_input: TeachingInput

    def to_dict(self):
        return {
            "request_id": self.task.request_id,
            "question": self.task.question,
            "context_card": self.context_card,
            "selected_record_ids": [item.record.record_id for item in self.selected],
            "return_mode": self.controlled.mode if self.controlled else "none",
            "controlled_resource": self.controlled.text if self.controlled else "",
            "answer": self.answer,
            "source_trace": self.controlled.source_trace if self.controlled else {},
            "execution_mode": "offline_rule_based",
            "privacy_evidence": self.privacy_evidence,
            "teaching_input": self.teaching_input.to_dict(),
        }


class DomainServices:
    """Initialize selectors and ledgers; graph nodes own their ordering."""

    def __init__(self, config: dict, resources: list[TeacherResource]):
        self.config = config
        self.selector = ProfileSelector(config)
        self.profile_policy = ProfileReadPolicy(config)
        privacy_max = float(config.get("fopd", {}).get("privacy_budget", 1.0))
        self.privacy_ledger = PrivacyBudgetLedger(privacy_max)
        self.budget = ExposureBudget(config)
        self.resources = tuple(resources)
        self.retriever = CopyrightAwareRetriever(resources, self.budget, config)
