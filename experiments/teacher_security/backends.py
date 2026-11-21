"""模型接口和实验固定件。全部模型调用共用一个硬预算；从不自动重试。"""
from __future__ import annotations

import json
from pathlib import Path
import time

from cogniguard.workflows.teachers.catalog import PromptLibrary, PromptSpec, digest
from cogniguard.workflows.teachers.store import DatabasePromptLibrary, SQLiteTeacherAuditStore
from cogniguard.workflows.teachers.skills import SkillLibrary
from experiments.focused.redteam.model import JsonModel
from .protocol import PROTOCOL_INSTRUCTIONS, PublicTaskFallback


ROOT = Path(__file__).resolve().parents[2]


def database_catalogs(store: SQLiteTeacherAuditStore):
    source = PromptLibrary(ROOT / "configs/teacher-prompts.yaml")
    prompts = {}
    for item in source.inventory():
        old = source.get(item["teacher"], item["version"])
        prompts[old.teacher, old.version] = PromptSpec(old.teacher, old.display_name, old.version,
                                                     old.system + PROTOCOL_INSTRUCTIONS)
    overlay = DatabasePromptLibrary(digest({"source": source.sha256, "protocol": PROTOCOL_INSTRUCTIONS}), prompts)
    skills = SkillLibrary(ROOT / "configs/teacher-skills.yaml")
    store.sync_catalogs(overlay, skills)
    return (store.load_prompt_catalog(overlay.sha256, expected_count=len(prompts)),
            store.load_skill_catalog(skills.sha256, expected_count=len(skills.inventory())))


class CallLimitReached(RuntimeError):
    pass


class ModelBudget:
    def __init__(self, path: Path, *, limit=60, transport=None):
        if not 1 <= limit <= 60:raise ValueError("Model limit must be 1..60")
        self.transport = transport or JsonModel(ROOT, max_completion_tokens=1200)
        self.path, self.limit, self.calls = path, limit, 0
        self.prompt_tokens = self.completion_tokens = 0

    def invoke(self, system: str, payload: dict, *, role="defender"):
        if self.calls >= self.limit:raise CallLimitReached("Shared model call budget reached")
        self.calls += 1
        started = time.monotonic()
        row = {"call": self.calls, "role": role, "status": "error"}
        try:
            response = self.transport.call(system, payload)
            usage = response.get("usage") or {}
            self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
            self.completion_tokens += int(usage.get("completion_tokens") or 0)
            row.update(status="ok", prompt_tokens=int(usage.get("prompt_tokens") or 0),
                       completion_tokens=int(usage.get("completion_tokens") or 0))
            return response
        except Exception as error:
            row["error_class"] = type(error).__name__
            raise
        finally:
            row["latency_ms"] = round((time.monotonic() - started) * 1000, 2)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row) + "\n")

    def call(self, system: str, payload: dict):
        return self.invoke(system, payload)


class ScriptedSources:
    real_model = False

    def __init__(self, payloads: dict[str, str]):self.payloads = payloads

    def __call__(self, request):return self.payloads[request.node_id]


class LastMessageFixture:
    """专门用于离线接线的易受污染固定件，其结果不计作真实模型性能。"""
    real_model = False

    def __call__(self, request):
        if request.upstream:return request.upstream[-1].text
        return PublicTaskFallback()(request)
