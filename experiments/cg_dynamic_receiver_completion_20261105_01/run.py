"""Replay frozen event cases with a separately persisted synthetic receiver."""
import importlib.util
import json
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SRC = ROOT / "experiments/cg_base_acceptance_20261105_01/replay_with_receiver.py"
CASES = ROOT / "experiments/cg_dynamic_problem_validation_20261105_03/cases.jsonl"
spec = importlib.util.spec_from_file_location("receiver_replay", SRC)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def main():
    out = HERE / "runs/v1"
    out.mkdir(parents=True, exist_ok=False)
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines()]
    assert len(cases) == 191 and sum(not bool(c.get("control_of")) for c in cases) == 96
    started = time.monotonic()
    results = []
    for index, case in enumerate(cases):
        if time.monotonic() - started > 1800:
            raise TimeoutError("pre-registered execution budget exceeded")
        path = out / f"receipt_{index:03}.jsonl"
        try:
            decisions = module.execute(case, module.Receiver(path))
            observed = module.observe(case, decisions, path)
            results.append({"case_id": case["case_id"], "family": case["family"],
                            "control_of": case.get("control_of"), "decisions": decisions,
                            "receipt": path.name, **observed})
        except Exception as exc:
            results.append({"case_id": case["case_id"], "family": case["family"],
                            "control_of": case.get("control_of"), "status": "UNKNOWN",
                            "error_type": type(exc).__name__})
    first = next(case for case in cases if case["case_id"] == "P1")
    fault_path = out / "receiver_fault.jsonl"
    fault = module.observe(first, module.execute(first, module.Receiver(fault_path, fail=True)), fault_path)
    counts = {}
    for row in results:
        key = ("control" if row.get("control_of") else "main") + "/" + row["family"]
        counts.setdefault(key, Counter())[row["status"]] += 1
    report = {"scope": "simulated controller, real synthetic local-file receiver; not production",
              "counts": {key:dict(value) for key,value in counts.items()},
              "elapsed_seconds": time.monotonic()-started, "fault_control": fault,
              "results": results}
    (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"counts":report["counts"], "fault":fault["status"], "seconds":report["elapsed_seconds"]}))

if __name__ == "__main__":
    main()
