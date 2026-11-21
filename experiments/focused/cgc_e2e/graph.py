"""Graph execution for the deterministic cross-domain CGC comparison."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context

from cogniguard.governance import AuditLedger, LifecycleGuard
from .scenarios import build_scenarios, trust_session_scenarios


class CgcState(TypedDict, total=False):
    stage: str
    scenario_index: int
    scenario_count: int
    completed: bool


@dataclass
class CgcFrame:
    output: Path | None
    scenarios: list[Any] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    trust_trajectory: list[float] = field(default_factory=list)
    audit_ok_after_session: bool = False
    verify_clean: bool = False
    verify_tampered: bool = False
    summary: dict[str, Any] = field(default_factory=dict)
    output_path: Path | None = None


@dataclass
class CgcContext:
    frame: CgcFrame


def prepare(state: CgcState, runtime: Runtime[CgcContext]):
    frame = runtime.context.frame
    frame.scenarios = build_scenarios()
    return {"stage": "prepare", "scenario_index": 0, "scenario_count": len(frame.scenarios)}


def compare_case(state: CgcState, runtime: Runtime[CgcContext]):
    frame = runtime.context.frame
    scenario = frame.scenarios[state["scenario_index"]]
    from .runner import cgc_decision, judge, siloed_decision
    siloed = siloed_decision(scenario)
    cgc = cgc_decision(scenario)
    frame.rows.append({
        "scenario_id": scenario.scenario_id, "desc": scenario.desc,
        "differentiator": scenario.differentiator, "intended": scenario.intended,
        "siloed": siloed, "cgc": cgc,
        "siloed_correct": judge(scenario.intended, siloed["reacted"], siloed["hard_stop"]),
        "cgc_correct": judge(scenario.intended, cgc["reacted"], cgc["hard_stop"]),
    })
    return {"stage": "compare_case", "scenario_index": state["scenario_index"] + 1}


def trust_sequence(state: CgcState, runtime: Runtime[CgcContext]):
    frame = runtime.context.frame
    from .runner import _capabilities, build_envelope
    guard = LifecycleGuard(_capabilities(), AuditLedger())
    for index, scenario in enumerate(trust_session_scenarios(), 1):
        guard.evaluate(build_envelope(scenario, session_id="trust_sess", round_id=f"r{index}"))
        frame.trust_trajectory.append(round(guard.trust_by_session["trust_sess"].score, 3))
    frame.audit_ok_after_session = guard.audit.verify()
    return {"stage": "trust_sequence"}


def tamper_audit(state: CgcState, runtime: Runtime[CgcContext]):
    frame = runtime.context.frame
    ledger = AuditLedger()
    for index in range(3):
        ledger.append({"request_id": f"req{index}", "session_id": "audit_demo",
                       "round_id": f"r{index}", "action": "allow"})
    frame.verify_clean = ledger.verify()
    ledger.records[1]["action"] = "block"
    frame.verify_tampered = ledger.verify()
    return {"stage": "tamper_audit"}


def aggregate(state: CgcState, runtime: Runtime[CgcContext]):
    f = runtime.context.frame
    unsafe = [row for row in f.rows if row["intended"] == "unsafe"]
    safe = [row for row in f.rows if row["intended"] == "safe"]
    f.summary = {
        "status": "CGC_UNIFIED_CONTROL_E2E", "execution_mode": "deterministic_control_layer",
        "scenario_count": len(f.scenarios), "unsafe_total": len(unsafe), "safe_total": len(safe),
        "unsafe_missed_by_siloed": [r["scenario_id"] for r in unsafe if not r["siloed"]["reacted"]],
        "unsafe_missed_by_cgc": [r["scenario_id"] for r in unsafe if not r["cgc"]["reacted"]],
        "caught_by_cgc_only": [r["scenario_id"] for r in unsafe
                               if not r["siloed"]["reacted"] and r["cgc"]["reacted"]],
        "safe_overblocked_by_siloed": [r["scenario_id"] for r in safe if r["siloed"]["hard_stop"]],
        "safe_overblocked_by_cgc": [r["scenario_id"] for r in safe if r["cgc"]["hard_stop"]],
        "siloed_accuracy": round(sum(r["siloed_correct"] for r in f.rows) / len(f.rows), 3),
        "cgc_accuracy": round(sum(r["cgc_correct"] for r in f.rows) / len(f.rows), 3),
        "trust_trajectory": f.trust_trajectory,
        "audit_verify_after_trust_session": f.audit_ok_after_session,
        "audit_verify_clean": f.verify_clean, "audit_verify_after_tamper": f.verify_tampered,
        "notes": {
            "siloed": "每个模块只按自己域的风险/预算本地决策；无能力、上下文边界、provenance、审计链、跨域融合、跨轮信任。",
            "caught_by_cgc_only": "siloed 放行但 CGC 处理的 unsafe 场景——这是统一控制层的增量价值。",
            "trust_trajectory": "同一会话连续违规时信任分逐次下降。",
            "audit": "审计链为哈希链，篡改任一历史记录会使 verify() 变为 False。",
        },
        "limitations": [
            "合成场景、确定性规则实验，证明控制层逻辑与统一价值，不含真实模型行为或统计显著性。",
            "siloed 基线为机制级对照（模块各自本地检查），非某一具体已发表系统的忠实复现。",
            "风险分值为场景设定值，用于触发各控制分支；真实系统由各领域模块产出。",
        ],
    }
    return {"stage": "aggregate"}


def persist(state: CgcState, runtime: Runtime[CgcContext]):
    f = runtime.context.frame
    from .runner import ROOT, SILOED_RISK_THRESHOLD
    f.output_path = f.output or ROOT / "experiments/results/cgc_e2e" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    f.output_path.mkdir(parents=True, exist_ok=False)
    (f.output_path / "rows.json").write_text(json.dumps(f.rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (f.output_path / "summary.json").write_text(json.dumps(f.summary, ensure_ascii=False, indent=2), encoding="utf-8")
    files = [Path(__file__), Path(__file__).with_name("runner.py"),
             Path(__file__).with_name("scenarios.py"), ROOT / "cogniguard/governance/lifecycle.py",
             ROOT / "cogniguard/governance/audit.py", ROOT / "cogniguard/governance/capability.py"]
    (f.output_path / "manifest.json").write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(), "synthetic_only": True,
        "orchestrator": "langgraph", "siloed_risk_threshold": SILOED_RISK_THRESHOLD,
        "files_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in files},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"stage": "persist", "completed": True}


def build_cgc_graph():
    builder = StateGraph(CgcState, context_schema=CgcContext)
    nodes = (("prepare", prepare), ("compare_case", compare_case),
             ("trust_sequence", trust_sequence), ("tamper_audit", tamper_audit),
             ("aggregate", aggregate), ("persist", persist))
    for name, fn in nodes:
        builder.add_node(name, fn)
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "compare_case")
    builder.add_conditional_edges("compare_case",
                                  lambda state: "again" if state["scenario_index"] < state["scenario_count"] else "done",
                                  {"again": "compare_case", "done": "trust_sequence"})
    builder.add_edge("trust_sequence", "tamper_audit")
    builder.add_edge("tamper_audit", "aggregate")
    builder.add_edge("aggregate", "persist")
    builder.add_edge("persist", END)
    return builder.compile(checkpointer=False, name="CogniGuardCgcE2E")


CGC_GRAPH = build_cgc_graph()


def run_cgc_graph(output=None):
    frame = CgcFrame(Path(output) if output else None)
    with tracing_context(enabled=False):
        state = CGC_GRAPH.invoke({}, context=CgcContext(frame))
    if not state.get("completed"):
        raise RuntimeError("CGC graph did not complete")
    return frame.output_path, frame.summary
