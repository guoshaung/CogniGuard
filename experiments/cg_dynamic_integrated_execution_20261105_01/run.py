"""Synthetic dynamic gate wired to real NeMo, CGC and education graph."""
import importlib.util
import json
import os
import threading
from pathlib import Path

os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", CUDA_VISIBLE_DEVICES="",
                  LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false")
from cogniguard.agents.protected_orchestrator import CGController
from cogniguard.integrations.education import AccessScope, ProfileRecord, ProtectionPipeline, StudentProfile, TeacherResource
from cogniguard.integrations.nemo.native import NativeNeMoGuard
from cogniguard.protection.text_provenance import TextProvenanceService
from cogniguard.runtime.gateway import ProtectionGateway
from cogniguard.runtime.sessions import SessionStore

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OLD = ROOT / "experiments/cg_dynamic_problem_validation_20261105_03"
spec = importlib.util.spec_from_file_location("rec", ROOT / "experiments/cg_base_acceptance_20261105_01/replay_with_receiver.py")
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)


class Agent:
    agent_id = "profile_diagnosis_agent"
    def validate_input(self, payload):
        assert isinstance(payload, dict)
    def generate(self, payload):
        return {"diagnosis_result": {"knowledge_point": "fractions"}}


class PolicyBoundary:
    def __init__(self, case):
        self.case = case
        self.authority = rec.old.Authority()
        self.profile = rec.old.ProfileGuard(self.authority)
        self.resource = rec.old.ResourceGuard()
        self.lock = threading.RLock()
        self.checks = []
    def event(self, event):
        if event["kind"] == "revoke":
            self.authority.revoke(event["field"])
        elif event["kind"] in {"notify", "notify_old"}:
            self.profile.notify(event["policy_version"], event["t_ms"])
    def check(self, event, stage):
        op, t = event["op"], event["t_ms"]
        p, reason, version, age = self.profile.check(
            self.case["dependencies"] if op == "send" else [], t, event.get("query_available", True))
        r, resource_reason = self.resource.check(op, t, self.case.get("expiration_ms", 10000),
                                                  self.case.get("grace", True), self.case["session_id"])
        decision = "DENY" if "DENY" in (p, r) else "SAFE_STOP" if "SAFE_STOP" in (p, r) else "ALLOW"
        self.checks.append({"stage":stage, "decision":decision, "version":version,
                            "age_ms":age, "profile_reason":reason, "resource_reason":resource_reason})
        return decision


def pipeline():
    profile = StudentProfile("synthetic-student", {}, [ProfileRecord("m", "mastery", "fractions", 0.4, 1, 0.1)])
    resource = TeacherResource.from_dict({"resource_id":"synthetic-resource", "chunk_id":"c1",
        "content":"Compare fractions using a common denominator.", "knowledge":"fractions",
        "difficulty":"basic", "resource_type":"question_bank", "copyright_level":0.5,
        "policy":{"allow_quote":False, "allow_summary":True}})
    flow = ProtectionPipeline({"fopd":{"use_enhanced_fopd":False}}, [resource],
                              generator=lambda _: "A common denominator helps compare fractions.")
    return flow, profile


def main():
    out = HERE / "runs/v2"
    out.mkdir(parents=True, exist_ok=False)
    cases = [json.loads(s) for s in (OLD / "cases.jsonl").read_text(encoding="utf8").splitlines()]
    native = NativeNeMoGuard()
    results = []
    try:
        for cid in ("P1","P2","E2","E5","V2","V3"):
            case = next(c for c in cases if c["case_id"] == cid)
            sink_path = out / f"{cid}_receipt.jsonl"
            sink = rec.Receiver(sink_path)
            policy = PolicyBoundary(case)
            stage = {"agent":False,"pipeline":False,"delivery":False,"nemo":False}
            decisions = []
            try:
                gateway = ProtectionGateway(store=SessionStore(out / f"{cid}.sqlite"),
                    provenance=TextProvenanceService(b"synthetic-key-only" * 4, required=True), native_guard=native)
                for event in case["events"]:
                    if event["kind"] != "action":
                        policy.event(event)
                        continue
                    entry = {"case_id":cid,"action_index":len(decisions),"op":event["op"],"receiver_error":False}
                    with policy.lock:
                        def operation(frame):
                            d = policy.check(event, "before_agent")
                            if d != "ALLOW":
                                return {"answer":"Synthetic action blocked.","dynamic_decision":d}
                            controller = CGController()
                            controller.dispatch("MM-FOPD", Agent(), "diagnosis_request",
                                {"context_card":{"knowledge_point":"fractions"}}, "minimum_context", cid)
                            stage["agent"] = True
                            d = policy.check(event, "before_teaching_pipeline")
                            if d != "ALLOW":
                                return {"answer":"Synthetic action blocked.","dynamic_decision":d}
                            flow, profile = pipeline()
                            flow.run(profile, {"student_id":"synthetic-student","question":"Explain fractions",
                                "expected_knowledge":"fractions","need_resource":True}, access=AccessScope("synthetic-student"))
                            stage["pipeline"] = True
                            return {"answer":"Synthetic approved teaching action.","dynamic_decision":"ALLOW"}
                        result = gateway.run("dynamic_probe", {"message":"Explain fractions."}, operation)
                        stage["nemo"] = result["protection"]["nemo_base_backend"] == "iorails"
                        decision = result["dynamic_decision"]
                        if decision == "ALLOW":
                            decision = policy.check(event, "before_external_effect")
                            if decision == "ALLOW" and result["output_validation"]["allowed"]:
                                sink.accept(cid, len(decisions), event["op"])
                                stage["delivery"] = True
                        entry["decision"] = decision
                        decisions.append(entry)
                observed = rec.observe(case, decisions, sink_path)
                results.append({"case_id":cid,"stages":stage,"policy_checks":policy.checks,"decisions":decisions,**observed})
            except Exception as exc:
                results.append({"case_id":cid,"status":"UNKNOWN","error_type":type(exc).__name__,"error":str(exc),"policy_checks":policy.checks})
    finally:
        native.close()
    (out / "results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps([{k:r.get(k) for k in ("case_id","status","stages","error_type")} for r in results]))


if __name__ == "__main__":
    main()
