"""Verify completed evidence boundaries and the fixed selection replay."""
import json
from collections import Counter

from data_cases import HERE, RUN, bridge_cases, dump, peer_cases, read_json


def main():
    cases = read_json(RUN / "cases.local.json")
    peer, _ = peer_cases()
    bridge, _ = bridge_cases()
    assert cases == [case for case, _ in peer + bridge]
    assert read_json(RUN / "gold.local.json") == {case["case"]: gold for case, gold in peer + bridge}
    source = {case["case"]: case for case in cases}
    traces = [json.loads(line) for line in (RUN / "teaching_traces.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(traces) == len(source) == 104
    assert set(source) == {t["case"] for t in traces}
    valid_rows = 0
    all_fingerprints = set()
    for trace in traces:
        case = source[trace["case"]]
        assert all(f["position"] < case["source_position"] for f in case["candidates"])
        for arm, row in trace["rows"].items():
            indices = row["indices"]
            expected = "\n".join(
                f"[{f['role']} earlier turn {f['position']}] {f['text']}"
                for f in (case["candidates"][index] for index in sorted(indices))
            )
            assert row["wire"] == expected
            if arm != "B1":
                assert len(indices) <= 3 and row["history_tokens"] <= 192
            if arm in ("B0", "B8"):
                assert not indices
            if row["teacher"]["status"] == "OK":
                all_fingerprints.add(row["teacher"]["fingerprint"])
            valid_rows += 1
        assert trace["rows"]["B1"]["teacher"] == trace["rows"]["B8"]["teacher"]
    shared = [json.loads(line) for line in (HERE / "teaching_traces.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(shared) == valid_rows
    assert all("wire" not in row and "request" not in row and "response_text" not in row for row in shared)
    report = {
        "cases": len(cases), "logical_rows": valid_rows, "case_and_gold_rebuild_equal": True,
        "budget_and_original_fragment_checks": "PASS", "release_artifact_contains_text_free_derived_rows": True,
        "model_fingerprints": sorted(all_fingerprints),
        "teacher_status": dict(Counter(row["teacher"]["status"] for t in traces for row in t["rows"].values())),
    }
    dump(HERE / "run_checks.json", report)
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
