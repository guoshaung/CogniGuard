"""Frozen 18 cases with a separate persistent synthetic receiver and observer."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OLD = ROOT / "experiments/cg_dynamic_problem_validation_20261105_03"
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("old_replay", OLD / "run_replay.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)


class Receiver:
    def __init__(self, path: Path, fail=False):
        self.path, self.fail = path, fail
        self.path.touch(exist_ok=False)

    def accept(self, case_id, action_index, op):
        if self.fail:
            raise OSError("synthetic receiver failure")
        row = {"case_id": case_id, "action_index": action_index, "op": op}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()


def execute(case, receiver):
    auth = old.Authority()
    profile = old.ProfileGuard(auth)
    resource = old.ResourceGuard()
    decisions = []
    for event in case["events"]:
        kind, t = event["kind"], event["t_ms"]
        if kind == "revoke":
            auth.revoke(event["field"])
        elif kind in {"notify", "notify_old"}:
            profile.notify(event["policy_version"], t)
        elif kind == "restore_snapshot":
            profile.cache = {"version": 1, "allowed": {"f": True, "g": True}, "issued_ms": 0}
        elif kind == "action":
            op = event["op"]
            p = profile.check(case["dependencies"] if op == "send" else [], t,
                              event.get("query_available", True))[0]
            r = resource.check(op, t, case.get("expiration_ms", 10000),
                               case.get("grace", True), case["session_id"])[0]
            result = "DENY" if "DENY" in (p, r) else "SAFE_STOP" if "SAFE_STOP" in (p, r) else "ALLOW"
            entry = {"case_id": case["case_id"], "action_index": len(decisions),
                     "op": op, "decision": result, "receiver_error": False}
            if result == "ALLOW":
                try:
                    receiver.accept(case["case_id"], len(decisions), op)
                except OSError:
                    entry["receiver_error"] = True
            decisions.append(entry)
        elif kind not in {"preauthorize", "resource_expired", "old_resource_cache_hit", "notification_delay_begin"}:
            raise ValueError(f"unsupported event {kind}")
    return decisions


def observe(case, decisions, receipt_path):
    """Read persisted receipts independently; errors are never treated as absence."""
    try:
        rows = [json.loads(line) for line in receipt_path.read_text(encoding="utf-8").splitlines()]
    except (OSError, ValueError):
        return {"case_id": case["case_id"], "status": "UNKNOWN", "reason": "receiver_unreadable"}
    if any(d["receiver_error"] for d in decisions):
        return {"case_id": case["case_id"], "status": "UNKNOWN", "reason": "receiver_failed"}
    if len(case["expected"]) != len(decisions):
        return {"case_id": case["case_id"], "status": "UNKNOWN", "reason": "action_count"}
    keys = [(row["case_id"], row["action_index"], row["op"]) for row in rows]
    if len(keys) != len(set(keys)) or any(key[0] != case["case_id"] for key in keys):
        return {"case_id": case["case_id"], "status": "UNKNOWN", "reason": "invalid_receipts"}
    checks = []
    for index, (expect, decision) in enumerate(zip(case["expected"], decisions)):
        effect = (case["case_id"], index, decision["op"]) in keys
        checks.append({"index": index, "expected": expect, "decision": decision["decision"],
                       "receipt_observed": effect,
                       "matches": decision["op"] == expect["op"] and
                       decision["decision"] == expect["result"] and effect == expect["external_effect"]})
    return {"case_id": case["case_id"], "status": "PASS" if all(x["matches"] for x in checks) else "FAIL", "checks": checks}


def main():
    out = HERE / "runs/receiver_v1"
    out.mkdir(parents=True, exist_ok=False)
    cases = [json.loads(row) for row in (OLD / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    ids = {f"{family}{index}" for family in "PEV" for index in range(1, 7)}
    selected = [case for case in cases if case["case_id"] in ids]
    if len(selected) != 18:
        raise ValueError("Expected exactly the frozen 18 cases")
    results = []
    for case in selected:
        path = out / f"{case['case_id']}.jsonl"
        decisions = execute(case, Receiver(path))
        results.append({"decisions": decisions, **observe(case, decisions, path)})
    fault_case = next(case for case in selected if case["case_id"] == "P1")
    fault_path = out / "fault.jsonl"
    fault = observe(fault_case, execute(fault_case, Receiver(fault_path, fail=True)), fault_path)
    report = {"scope": "synthetic in-process baseline with file receiver; not production",
              "results": results, "receiver_fault_control": fault,
              "pass_count": sum(row["status"] == "PASS" for row in results),
              "unknown_count": sum(row["status"] == "UNKNOWN" for row in results)}
    (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": report["pass_count"], "total": len(results),
                      "unknown": report["unknown_count"], "fault": fault["status"]}))


if __name__ == "__main__":
    main()
