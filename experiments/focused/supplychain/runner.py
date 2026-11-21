"""制品完整性/来源门：pin → verify → 不匹配判 provenance 失效 → CGC 拒绝加载。

场景：clean（校验通过，允许加载）/ tamper_dataset（数据集被篡改一个字节）/
dependency_drift（依赖版本漂移）。另报告弱固定项（检测器 revision 未 pin）作为供应链卫生发现。
确定性，不调用模型。
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from cogniguard.governance import (
    AuditLedger, CapabilityGrant, CapabilityPolicy, ContextBoundary,
    DomainEvidence, EvidenceEnvelope, LifecycleGuard, Principal, Purpose,
)
from .inventory import ROOT, build_inventory, collect_actual


def pin(inv) -> dict:
    """生成 pinned 清单（lock）：记录每个制品的固定值与许可证。"""
    actual = collect_actual(inv)
    return {a.name: {"kind": a.kind, "license": a.license, "pin_by": a.pin_by,
                     "path": a.path, "expected": actual[a.name], "declared": a.declared} for a in inv}


def verify(lock: dict, actual: dict) -> dict:
    """逐制品比对 actual 与 lock；返回状态与整体 provenance 是否有效。"""
    items = []
    provenance_valid = True
    weak = []
    for name, locked in lock.items():
        exp, act = locked["expected"], actual.get(name, {})
        status = "ok"
        if act.get("missing"):
            status, provenance_valid = "missing", False
        elif locked["pin_by"] == "sha256":
            if exp.get("sha256") != act.get("sha256"):
                status, provenance_valid = "hash_mismatch", False
        elif locked["pin_by"] == "version":
            if exp.get("version") != act.get("version"):
                status, provenance_valid = "version_drift", False
        elif locked["pin_by"] == "revision":
            if exp.get("revision") == "UNPINNED" or act.get("revision") == "UNPINNED":
                status = "weak_pin_unpinned_revision"
                weak.append(name)
            elif exp.get("revision") != act.get("revision"):
                status, provenance_valid = "revision_mismatch", False
        items.append({"name": name, "kind": locked["kind"], "license": locked["license"],
                      "pin_by": locked["pin_by"], "status": status,
                      "expected": exp, "actual": act})
    return {"provenance_valid": provenance_valid, "items": items, "weak_pins": weak}


def cgc_gate(provenance_valid: bool) -> dict:
    """把来源校验结果交给 CGC：provenance 失效 → refuse（拒绝加载该制品链）。"""
    caps = CapabilityPolicy([CapabilityGrant("service", "model_loader", frozenset({"load_artifact"}))])
    guard = LifecycleGuard(caps, AuditLedger())
    env = EvidenceEnvelope(
        request_id="load", session_id="supplychain", round_id="verify",
        principal=Principal("model_loader", "service"), destination="model_loader",
        purpose=Purpose("load_artifact"),
        boundary=ContextBoundary(source="artifact_registry", trust_level="authenticated", instruction_permission=False),
        payload={"load": "artifacts"},
        evidence={"provenance": DomainEvidence("provenance", 0.0 if provenance_valid else 0.9,
                                               provenance={"valid": provenance_valid})},
    )
    decision = guard.evaluate(env)
    return {"action": decision.action, "reasons": decision.reasons, "allowed_to_load": decision.action == "allow"}


def run(output=None):
    from .graph import run_supplychain_graph
    return run_supplychain_graph(output)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="供应链制品完整性/来源门（LLM03）")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    out, summary = run(args.output)
    print(json.dumps({k: summary[k] for k in ("clean_loads", "tamper_blocked", "drift_blocked", "weak_pins")}, ensure_ascii=False, indent=2))
    print(out)
