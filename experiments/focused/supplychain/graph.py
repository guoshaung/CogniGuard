"""Offline LangGraph: inventory → pin → tamper/drift probes → policy gate."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context

from .inventory import ROOT, build_inventory, collect_actual


class SupplyState(TypedDict, total=False):
    stage: str
    completed: bool


@dataclass
class SupplyFrame:
    output: Path | None
    inventory: list[Any] = field(default_factory=list)
    lock: dict[str, Any] = field(default_factory=dict)
    baseline: dict[str, Any] = field(default_factory=dict)
    scenarios: dict[str, dict] = field(default_factory=dict)
    tamper_detail: dict[str, Any] | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    output_path: Path | None = None


@dataclass
class SupplyContext:
    frame: SupplyFrame


def inventory(state: SupplyState, runtime: Runtime[SupplyContext]):
    f = runtime.context.frame
    f.inventory = build_inventory()
    f.baseline = collect_actual(f.inventory)
    return {"stage": "inventory"}


def pin_artifacts(state: SupplyState, runtime: Runtime[SupplyContext]):
    f = runtime.context.frame
    from .runner import pin
    f.lock = pin(f.inventory)
    return {"stage": "pin_artifacts"}


def build_probes(state: SupplyState, runtime: Runtime[SupplyContext]):
    f = runtime.context.frame
    f.scenarios["clean"] = deepcopy(f.baseline)
    tampered = deepcopy(f.baseline)
    dataset = next((item for item in f.inventory if item.name == "injecagent_dataset_cases"), None)
    if dataset and (ROOT / dataset.path).exists():
        raw = bytearray((ROOT / dataset.path).read_bytes())
        raw[0] ^= 0x01
        tampered[dataset.name] = {"sha256": hashlib.sha256(bytes(raw)).hexdigest(), "missing": False}
        f.tamper_detail = {"artifact": dataset.name, "note": "翻转首字节后重新哈希"}
    f.scenarios["tamper_dataset"] = tampered
    drift = deepcopy(f.baseline)
    drift["dep_numpy"] = {"version": (f.baseline["dep_numpy"].get("version") or "0") + "+evil",
                          "missing": False}
    f.scenarios["dependency_drift"] = drift
    return {"stage": "build_probes"}


def evaluate(state: SupplyState, runtime: Runtime[SupplyContext]):
    f = runtime.context.frame
    from .runner import cgc_gate, verify
    rows = {}
    for name, actual in f.scenarios.items():
        verification = verify(f.lock, actual)
        gate = cgc_gate(verification["provenance_valid"])
        rows[name] = {
            "provenance_valid": verification["provenance_valid"],
            "cgc_action": gate["action"],
            "allowed_to_load": gate["allowed_to_load"],
            "weak_pins": verification["weak_pins"],
            "failing_items": [item["name"] + ":" + item["status"] for item in verification["items"]
                              if item["status"] not in ("ok", "weak_pin_unpinned_revision")],
        }
    f.summary = {
        "status": "SUPPLY_CHAIN_INTEGRITY_GATE_LLM03", "execution_mode": "deterministic",
        "artifact_count": len(f.inventory), "scenarios": rows,
        "clean_loads": rows["clean"]["allowed_to_load"],
        "tamper_blocked": not rows["tamper_dataset"]["allowed_to_load"],
        "drift_blocked": not rows["dependency_drift"]["allowed_to_load"],
        "weak_pins": rows["clean"]["weak_pins"],
        "licenses": {item.name: item.license for item in f.inventory},
        "tamper_detail": f.tamper_detail,
        "findings": [
            "检测器 protectai/deepset 当前以 UNPINNED revision 使用，建议固定具体 HF commit 并记录权重哈希（弱固定）。",
            "基座模型为远程 API，只能按模型名+端点声明固定，无法做权重哈希校验（远程信任边界）。",
        ],
        "control": "pinned 清单(artifacts.lock) + 加载前 SHA256/版本/revision 校验 + 失败→CGC provenance refuse。",
        "limitations": [
            "确定性完整性校验，证明‘篡改/漂移→拒绝加载’的控制逻辑，不含真实后门模型或恶意依赖的攻防。",
            "远程 API 模型与 HF 权重未做逐字节哈希（体积/远程），以版本/revision 声明固定为主。",
            "license 字段为人工登记，需随依赖更新复核。",
        ],
    }
    return {"stage": "evaluate"}


def persist(state: SupplyState, runtime: Runtime[SupplyContext]):
    f = runtime.context.frame
    f.output_path = f.output or ROOT / "experiments/results/supplychain" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    f.output_path.mkdir(parents=True, exist_ok=False)
    (f.output_path / "artifacts.lock.json").write_text(json.dumps(f.lock, ensure_ascii=False, indent=2), encoding="utf-8")
    (f.output_path / "summary.json").write_text(json.dumps(f.summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (f.output_path / "manifest.json").write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "orchestrator": "langgraph", "synthetic_only": False,
        "note": "真实读取仓库内制品计算哈希/版本",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"stage": "persist", "completed": True}


def build_supplychain_graph():
    builder = StateGraph(SupplyState, context_schema=SupplyContext)
    nodes = (("inventory", inventory), ("pin_artifacts", pin_artifacts),
             ("build_probes", build_probes), ("evaluate", evaluate), ("persist", persist))
    for name, fn in nodes:
        builder.add_node(name, fn)
    builder.add_edge(START, nodes[0][0])
    for (left, _), (right, _) in zip(nodes, nodes[1:]):
        builder.add_edge(left, right)
    builder.add_edge(nodes[-1][0], END)
    return builder.compile(checkpointer=False, name="CogniGuardSupplyChain")


SUPPLYCHAIN_GRAPH = build_supplychain_graph()


def run_supplychain_graph(output=None):
    frame = SupplyFrame(Path(output) if output else None)
    with tracing_context(enabled=False):
        state = SUPPLYCHAIN_GRAPH.invoke({}, context=SupplyContext(frame))
    if not state.get("completed"):
        raise RuntimeError("Supply-chain graph did not complete")
    return frame.output_path, frame.summary
