"""Validate preparation/annotation isolation. Never infer leakage labels."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.paths import RESULTS_DIR  # noqa: E402

OUT = RESULTS_DIR / Path(__file__).resolve().parent.name


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def validate(folder=OUT):
    checks = []

    def require(condition, name):
        checks.append({"check": name, "passed": bool(condition)})

    register = read(folder / "SOURCE_REGISTER.json")
    for source in register["assets"] + register["history"]:
        require(sha((ROOT / source["path"]).read_bytes()) == source["sha256"],
                "unchanged_source:" + source["path"])
    require(sha((folder / "PROTOCOL.md").read_bytes()) == register["protocol_sha256"],
            "protocol_copy_matches_registered_hash")
    cases = read(folder / "method_inputs.json")
    constructions = read(folder / "researcher_only/case_construction.json")
    require(len(cases) == 24 and len(constructions) == 24, "exactly_24_histories")
    require(Counter(c["asset_id"] for c in cases) == {"C01": 8, "M02": 8, "E01": 8},
            "three_original_assets_eight_each")
    require(len({c["internal_id"] for c in constructions}) == 24, "unique_construction_ids")
    require(len({c["case_id"] for c in cases}) == 24, "unique_visible_ids")
    require(all(c["expected_leak_label"] is None and c["annotation_status"] == "PENDING_HUMAN_REVIEW"
                for c in constructions), "no_pretend_human_or_construction_gold")
    for a in ("C01", "M02", "E01"):
        require(len({c["construction_condition"] for c in constructions if c["visible"]["asset_id"] == a}) == 8,
                "eight_construction_conditions:" + a)
        public = read(folder / "public_contexts" / f"{a}.json")
        original = read(ROOT / "data/benchmarks/karc_pilot_20261025_v3/public" / f"{a}.json")
        require(public == original, "public_prior_and_original_permissions_unchanged:" + a)
        require(public["actual_selected_world"] == "NOT_PRESENT", "no_selected_world:" + a)
    for c in constructions:
        a = c["visible"]["asset_id"]
        doc = ROOT / "data/benchmarks/karc_pilot_20261025_v3/documents" / f"{a}.md"
        lines = doc.read_text(encoding="utf-8").splitlines()
        for evidence in c["source_evidence"]:
            for span in evidence["source_spans"]:
                # U0 has no copied text in its source object; still require a real line.
                require(0 < span["line"] <= len(lines), "source_line_exists:" + c["internal_id"])
                if "text" in span:
                    require(lines[span["line"] - 1] == span["text"], "source_quote_exact:" + c["internal_id"])
    for case in cases:
        require(1 <= len(case["turns"]) <= 3, "bounded_turns:" + case["case_id"])
        for i, t in enumerate(case["turns"], 1):
            require(t["turn"] == i and t["asset_id"] == case["asset_id"], "bound_turn:" + case["case_id"])
            require(t["recipient"] == "student-01" and t["verified_recipient_role"] == "student",
                    "fixed_recipient:" + case["case_id"])
            require(len(t["query"].encode()) <= 512 and len(t["reply"].encode()) <= 512,
                    "no_silent_truncation:" + case["case_id"])
    xwalk = read(folder / "researcher_only/blind_crosswalk.json")
    original_hashes = Counter(sha(canonical({k: v for k, v in c.items() if k != "case_id"})) for c in cases)
    aliases = {}
    orders = []
    for packet in ("A", "B"):
        pack = read(folder / f"annotation_{packet}/packet.json")
        require(len(pack) == 24, "blind_size:" + packet)
        require(Counter(sha(canonical({k: v for k, v in c.items() if k != "case_id"})) for c in pack)
                == original_hashes, "blind_identical_content_multiset:" + packet)
        aliases[packet] = {c["case_id"] for c in pack}
        mapping = {c["blind_id"]: c for c in xwalk if c["packet"] == packet}
        orders.append([mapping[c["case_id"]]["internal_id"] for c in pack])
        require(all(mapping[c["case_id"]]["content_sha256_without_id"] == sha(canonical({k: v for k, v in c.items() if k != "case_id"}))
                    for c in pack), "blind_crosswalk_integrity:" + packet)
        require(all(set(c) == set(cases[0]) for c in pack), "no_extra_blind_metadata:" + packet)
        encoded = json.dumps(pack, ensure_ascii=False)
        require(all(marker not in encoded for marker in ("construction_condition", "expected_leak_label", "source_target", "selected_hypothesis", "source_evidence", "internal_id")),
                "no_construction_or_private_keys:" + packet)
        with (folder / f"annotation_{packet}/annotations.csv").open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        require(len(rows) == sum(len(c["turns"]) for c in pack), "one_empty_row_per_prefix:" + packet)
        expected_rows = {(c["case_id"], str(t["turn"])) for c in pack for t in c["turns"]}
        require({(r["case_id"], r["prefix_turn"]) for r in rows} == expected_rows,
                "annotation_rows_match_prefixes:" + packet)
        require(all(r["annotation_status"] == "PENDING_HUMAN_REVIEW" and
                    all(v == "" for k, v in r.items() if k not in ("case_id", "prefix_turn", "annotation_status"))
                    for r in rows), "all_truth_and_reviewer_fields_blank:" + packet)
        for a in ("C01", "M02", "E01"):
            require(read(folder / f"annotation_{packet}/public_contexts/{a}.json")
                    == read(folder / f"public_contexts/{a}.json"), "blind_public_prior_matches:" + packet + a)
    require(not aliases["A"] & aliases["B"], "independent_blind_aliases")
    require(orders[0] != orders[1], "independent_blind_order")
    require(read(folder / "researcher_only/adjudication_template.json")["gold_frozen"] is False,
            "no_frozen_gold")
    require(read(folder / "construction_manifest.json")["model_calls"] == 0, "zero_model_calls_recorded")
    return {"status": "PASS_PREPARATION_ONLY" if all(x["passed"] for x in checks) else "FAIL",
            "check_count": len(checks), "failed_checks": [x for x in checks if not x["passed"]],
            "checks": checks, "semantic_correctness_established": False,
            "human_gold_frozen": False, "baseline_performance_evaluated": False}


if __name__ == "__main__":
    result = validate()
    path = OUT / "VALIDATION.json"
    with path.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "checks"}))
    raise SystemExit(0 if result["status"] == "PASS_PREPARATION_ONLY" else 1)
