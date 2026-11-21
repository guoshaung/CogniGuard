"""单次实验图：装配 → 教师 DAG → 模拟工具授权 → 独立评分 → 留证。"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
from pathlib import Path
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context

from core.teaching import TeachingInput
from cogniguard.workflows.teachers.catalog import TeamCatalog
from cogniguard.workflows.teachers.dag import TeacherDAGGenerator, TeacherDeliveryBlocked, JsonTeacherBackend
from .attacks import build_payloads
from .backends import ROOT, LastMessageFixture, ScriptedSources
from .defenses import Defense, dispatch_tool
from .protocol import PublicTaskFallback, parse, render, verify_public_question
from .scoring import score
from .tasks import Task


class TrialState(TypedDict, total=False):
    stage: str
    completed: bool


@dataclass
class Frame:
    task: Task
    case: dict
    defense: Defense
    prompts: object
    skills: object
    store: object
    output: Path
    budget: object = None
    templates: dict | None = None
    generator: object = None
    answer: str = ""
    status: str = "completed"
    tool: dict = field(default_factory=dict)
    row: dict = field(default_factory=dict)
    started: float = field(default_factory=time.monotonic)
    calls_before: int = 0
    team_override: object = None


@dataclass
class Context:
    frame: Frame


def prepare(state, runtime: Runtime[Context]):
    f = runtime.context.frame
    payloads, tamper = build_payloads(f.task, f.case, f.templates)
    team = f.team_override or TeamCatalog(ROOT / "configs/teacher-teams.yaml", f.prompts).get("dual_teachers")
    team = replace(team, nodes=tuple(replace(n, backend="sources") if n.id in payloads else n for n in team.nodes))
    transform = None
    if tamper:
        poisoned = payloads["concept"]
        payloads["concept"] = render(f.task.task_id, verify_public_question(f.task.public_question), "合法原消息。")
        def transform(source, target, message):
            return replace(message, text=poisoned) if source == "concept" else message
    f.calls_before = f.budget.calls if f.budget else 0
    sink = JsonTeacherBackend(f.budget) if f.budget else LastMessageFixture()
    f.generator = TeacherDAGGenerator(
        team, f.prompts, skills=f.skills, max_workers=1,
        backends={"sources": ScriptedSources(payloads), "default": sink},
        trust_mode="enforce" if f.defense.signature else "observe_only",
        delivery_transform=transform, content_assessor=f.defense.assess,
        handoff_guard_mode="enforce", on_blocked="fallback" if f.defense.recovery else "block",
        fallback_backend=PublicTaskFallback(), audit_store=f.store)
    return {"stage": "prepare"}


def teach(state, runtime: Runtime[Context]):
    f = runtime.context.frame
    view = TeachingInput(f.task.public_question, "二次函数" if f.task.kind == "quadratic" else "一元一次方程",
                         "basic", "合成任务卡：需要一步自检。", "none", "")
    if f.defense.rule_only:
        from types import SimpleNamespace
        f.answer = PublicTaskFallback()(SimpleNamespace(base_view=view.to_dict()))
    else:
        try:f.answer = f.generator(view)
        except TeacherDeliveryBlocked:f.status = "blocked"
        except Exception as error:
            f.status = "error"
            f.row["error_class"] = type(error).__name__
    return {"stage": "teach"}


def execute_tools(state, runtime: Runtime[Context]):
    f = runtime.context.frame
    request = None
    if f.status == "completed":
        try:request = parse(f.answer)["tool_request"]
        except (ValueError, TypeError):pass
    f.tool = dispatch_tool(request, enforce_scope=f.defense.scope)
    return {"stage": "tools"}


def evaluate(state, runtime: Runtime[Context]):
    f = runtime.context.frame
    report = f.generator.last_run if not f.defense.rule_only else {}
    f.row.update(case_id=f.case["case_id"], task_id=f.task.task_id, kind=f.task.kind,
                 condition=f.case["condition"], family=f.case["family"], method=f.defense.name,
                 status=f.status, fallback_used=bool(report.get("metrics", {}).get("teachers_degraded")),
                 rule_only=f.defense.rule_only,
                 model_calls=(f.budget.calls - f.calls_before) if f.budget else 0,
                 latency_ms=round((time.monotonic() - f.started)*1000, 2),
                 metrics=score(f.task, f.answer, status=f.status, tool_event=f.tool,
                               attack_family=f.case["family"] if f.case["condition"] == "attack" else None),
                 tool_event=f.tool)
    if f.team_override is not None:
        from experiments.communication_security.metrics import communication_metrics
        f.row["communication"] = communication_metrics(f.task, report)
    return {"stage": "evaluate"}


def persist(state, runtime: Runtime[Context]):
    f = runtime.context.frame
    # 只针对全合成实验保留教师生成文本供人工复核。原始学生、密钥和签名密钥不在这里。
    report = f.generator.last_run if not f.defense.rule_only else {}
    record = {"case_id": f.case["case_id"], "method": f.defense.name,
              "final_answer": f.answer, "nodes": [{"node": n["node"], "status": n["status"], "text": n["text"],
                  "parent_ids": n.get("parent_ids", []), "message_id": n.get("message_id"),
                  "hop": n.get("hop"), "real_model": n.get("real_model", False)}
                for n in report.get("nodes", [])], "edges": report.get("edges", []),
              "final_guard": report.get("final_guard", {})}
    with (f.output / "synthetic-review.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"stage": "persist", "completed": True}


def build_graph():
    graph = StateGraph(TrialState, context_schema=Context)
    nodes = (("prepare", prepare), ("teach", teach), ("tools", execute_tools),
             ("evaluate", evaluate), ("persist", persist))
    for name, fn in nodes:graph.add_node(name, fn)
    graph.add_edge(START, "prepare")
    for (left, _), (right, _) in zip(nodes, nodes[1:]):graph.add_edge(left, right)
    graph.add_edge("persist", END)
    return graph.compile(checkpointer=False, name="TeacherSecurityTrial")


GRAPH = build_graph()


def run_trial(task, case, defense, prompts, skills, store, output, *, budget=None, templates=None, team=None):
    frame = Frame(task, case, defense, prompts, skills, store, output,
                  budget=budget, templates=templates, team_override=team)
    with tracing_context(enabled=False):GRAPH.invoke({}, context=Context(frame))
    return frame.row
