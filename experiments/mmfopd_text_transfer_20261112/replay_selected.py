"""Re-submit 4 fixed held-out examples in three selector arms."""
import json

from data_cases import HERE, RUN, dump, read_json
from experiment import TEACHER_SCHEMA, TEACHER_SYSTEM, current_prompt, safe_chat


def main():
    cases = read_json(RUN / "cases.local.json")
    traces = {r["case"]: r for r in map(json.loads, (RUN / "teaching_test.local.jsonl").read_text(encoding="utf-8").splitlines())}
    picks = [c for c in sorted(cases, key=lambda row: row["case"]) if c["split"] == "test"]
    picks = [c for c in picks if c["source"] == "PeerMathDial"][:3] + [c for c in picks if c["source"] == "Bridge"][:1]
    checks = []
    for case in picks:
        for arm in ("B4", "B5", "B6"):
            original = traces[case["case"]]["rows"][arm]
            prompt = current_prompt(case) + "\nEarlier evidence:\n" + (original["wire"] or "(none)")
            result = safe_chat(TEACHER_SYSTEM, prompt, TEACHER_SCHEMA, 152)
            checks.append({"case": case["case"], "method": arm, "status": result["status"],
                           "identical_parsed_output": result["status"] == "OK" and result["output"] == original["teacher"]["output"],
                           "latency_s": result["latency_s"]})
    dump(HERE / "replay_check.json", checks)
    print("Replay:", sum(x["identical_parsed_output"] for x in checks), "/", len(checks), flush=True)


if __name__ == "__main__":
    main()
