"""Six frozen cases through native NeMo + real CGController after synthetic gate."""
import importlib.util
import json
import os
from pathlib import Path

os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", CUDA_VISIBLE_DEVICES="",
                  LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false")
from cogniguard.agents.protected_orchestrator import CGController
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


class FixtureAgent:
    agent_id = "profile_diagnosis_agent"
    def validate_input(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("invalid payload")
    def generate(self, payload):
        return {"diagnosis_result": {"knowledge_point": "fractions"}}


def main():
    out = HERE / "runs/attempt_02"
    out.mkdir(parents=True, exist_ok=False)
    cases = [json.loads(line) for line in (OLD / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    results = []
    native = NativeNeMoGuard()
    try:
        for cid in ("P1", "P2", "E2", "E5", "V2", "V3"):
            case = next(c for c in cases if c["case_id"] == cid)
            probe = out / f"{cid}_policy_probe.jsonl"
            path = out / f"{cid}_receipt.jsonl"
            try:
                decisions = rec.execute(case, rec.Receiver(probe))
                assert len(decisions) == 1
                decision = decisions[0]["decision"]
                sink = rec.Receiver(path)
                gateway = ProtectionGateway(
                    store=SessionStore(out / f"{cid}.sqlite"),
                    provenance=TextProvenanceService(b"synthetic-testing-key" * 4, required=True),
                    native_guard=native,
                )
                ran = False
                if decision == "ALLOW":
                    controller = CGController()
                    def operation(frame):
                        nonlocal ran
                        _, answer, _ = controller.dispatch(
                            "MM-FOPD", FixtureAgent(), "diagnosis_request",
                            {"context_card":{"knowledge_point":"fractions"}}, "minimum_context", cid,
                        )
                        ran = True
                        return {"answer":"Synthetic approved teaching action."}
                    result = gateway.run("synthetic_framework_probe", {"message":"Explain fractions."}, operation)
                    assert result["output_validation"]["allowed"] and result["protection"]["nemo_base_backend"] == "iorails"
                    assert controller.verify_audit_chain()
                    sink.accept(cid, 0, decisions[0]["op"])
                observed = rec.observe(case, decisions, path)
                results.append({"case_id":cid, "dynamic_policy":decision, "real_agent_called":ran,
                                "receiver":path.name, **observed})
            except Exception as exc:
                results.append({"case_id":cid, "status":"UNKNOWN", "error_type":type(exc).__name__,
                                "error":str(exc)})
    finally:
        native.close()
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([{k:r.get(k) for k in ("case_id","status","dynamic_policy","real_agent_called","error_type")} for r in results]))


if __name__ == "__main__":
    main()
