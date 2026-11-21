"""Synthetic-only adaptation of frozen cases to FlowReview's original commit gate."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OLD = ROOT / "experiments/cg_dynamic_problem_validation_20261105_03"
FR = ROOT / "var/tmp/flowreview-audit-20261105/src"
sys.path.insert(0, str(FR))
sys.path.insert(0, str(ROOT))
from flowreview import runners
from flowreview.instruments import policy_updates as pu

spec = importlib.util.spec_from_file_location(
    "receiver", ROOT / "experiments/cg_base_acceptance_20261105_01/replay_with_receiver.py"
)
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)


def flow_case(case, sink):
    authority = receiver.old.Authority()
    profile = receiver.old.ProfileGuard(authority)
    output = []
    for event in case["events"]:
        kind = event["kind"]
        if kind == "revoke":
            authority.revoke(event["field"])
        elif kind == "notify":
            profile.notify(event["policy_version"], event["t_ms"])
        elif kind == "action":
            policy, reason, version, _ = profile.check(
                case["dependencies"], event["t_ms"], event.get("query_available", True)
            )
            if policy not in {"ALLOW", "DENY"}:
                raise ValueError("safe stop cannot be encoded by this adapter")
            object_ref = hashlib.sha256(case["case_id"].encode()).hexdigest()
            graph = {"N": 1, "current_policy": policy, "read_mode": "stale_cache",
                     "observed_policy": "ALLOW", "observed_policy_version": "v1",
                     "scenario": {"canonical_object_sha256": object_ref,
                                  "destination": "synthetic_receiver", "operation": event["op"],
                                  "principal": "synthetic_teacher", "current_policy_version": f"v{version}",
                                  "case_id": case["case_id"]}}
            role = {"role_index": 0}
            artifact = {"artifact_sha256": "synthetic_parent"}
            mock = runners.policy_updates_fixture(graph, role, artifact, repair=True)
            parsed = pu.parse_repair(json.dumps(mock), graph, artifact["artifact_sha256"])
            action = pu.deterministic_commit(graph, parsed)
            entry = {"case_id":case["case_id"], "action_index":len(output), "op":event["op"],
                     "decision":"ALLOW" if action else "DENY", "receiver_error":False,
                     "policy_input":policy, "policy_version":version, "reason":reason,
                     "flowreview_protocol_valid":parsed["protocol_valid"]}
            if action:
                try:
                    sink.accept(case["case_id"], len(output), event["op"])
                except OSError:
                    entry["receiver_error"] = True
            output.append(entry)
    return output


def main():
    out = HERE / "runs/v1"
    out.mkdir(parents=True, exist_ok=False)
    cases = [json.loads(line) for line in (OLD / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    results = []
    for cid in ("P2", "P5"):
        case = next(c for c in cases if c["case_id"] == cid)
        for name, implementation in (("shared_rules", receiver.execute), ("flowreview_adapter", flow_case)):
            path = out / f"{cid}_{name}.jsonl"
            try:
                decisions = implementation(case, receiver.Receiver(path))
                observation = receiver.observe(case, decisions, path)
                results.append({"arm":name, "decisions":decisions, **observation})
            except Exception as exc:
                results.append({"arm":name, "case_id":cid, "status":"UNKNOWN", "error_type":type(exc).__name__})
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([{k:r[k] for k in ("case_id","arm","status")} for r in results]))


if __name__ == "__main__":
    main()
