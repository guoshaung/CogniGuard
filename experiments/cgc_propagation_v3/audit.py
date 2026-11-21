"""Read-only v2 forensic audit plus byte-level immutable baseline."""
import json
import os
from pathlib import Path

from experiments.cgc_propagation_v2.dataset import ROOT, PRUNE, read_lines, sha, write_json, now
from .contract import validate_wire, FormatError

V2_BUNDLE = ROOT / "experiments/results/cgc_propagation_v2_bundle_20261017_01"
V2_REAL = ROOT / "experiments/results/cgc_propagation_v2_real_20261017_01"
V2_OFFLINE = ROOT / "experiments/results/cgc_propagation_v2_offline_20261017_01"


def protected_files():
    # Preserve existing code including v2; exclude only NEW v3 and generated trees.
    records = {}
    prune = (PRUNE - {"cgc_propagation_v2"}) | {"cgc_propagation_v3"}
    for directory, dirs, files in os.walk(ROOT, followlinks=False):
        base = Path(directory)
        dirs[:] = [d for d in dirs if d.lower() not in prune and not d.lower().startswith((".venv", "venv"))
                   and not (base/d).is_symlink() and not getattr(base/d, "is_junction", lambda: False)()]
        for name in files:
            path = base/name
            if path.suffix.lower() in {".py", ".yaml", ".yml", ".toml", ".cmd", ".ps1"} and not path.is_symlink():
                records[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    for folder in (V2_BUNDLE, V2_REAL, V2_OFFLINE):
        for path in folder.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                records[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    return dict(sorted(records.items()))


def audit_v2(output):
    previous = json.loads((V2_BUNDLE / "frozen_config.json").read_text(encoding="utf-8"))
    for name, expected in previous["preexisting_source_sha256"].items():
        if sha((ROOT/name).read_bytes()) != expected:
            raise RuntimeError("original_core_or_existing_source_changed")
    for name, expected in previous["implementation_sha256"].items():
        if sha((ROOT/"experiments/cgc_propagation_v2"/name).read_bytes()) != expected:
            raise RuntimeError("frozen_v2_implementation_changed")
    for manifest in (V2_REAL/"pilot/evidence-manifest.json", V2_REAL/"review/review-evidence.json"):
        for name, expected in json.loads(manifest.read_text(encoding="utf-8")).items():
            path = ROOT/name if name.startswith("experiments/") else manifest.parent/name
            if sha(path.read_bytes()) != expected:
                raise RuntimeError("historical_evidence_changed")
    calls = read_lines(V2_REAL / "pilot/raw-model-calls.jsonl")
    judgments = read_lines(V2_REAL / "pilot/independent-scores.jsonl")
    replay = []
    for call in calls:
        content = call["response"]["choices"][0]["message"]["content"]
        outer = json.loads(content)
        old_outer_accept = set(outer) == {"answer"} and isinstance(outer.get("answer"), str)
        try:
            validate_wire(content)
            category, error = "valid_answer", None
        except FormatError as exc:
            category, error = "format_error", str(exc)
        replay.append({"attempt": call["attempt"], "method": call["method"], "node_id": call["node_id"],
                       "old_outer_only_accept": old_outer_accept, "v3_strict_outcome": category, "error_code": error,
                       "evidence_path": "pilot/raw-model-calls.jsonl", "response_content_sha256": sha(content.encode())})
    write_json(output / "v2-audit-summary.json", {
        "status": "COMPLETED_READ_ONLY_V2_AUDIT", "created_at": now(),
        "real_api_calls": len(calls), "old_outer_accept_count": sum(r["old_outer_only_accept"] for r in replay),
        "strict_valid_count": sum(r["v3_strict_outcome"] == "valid_answer" for r in replay),
        "strict_format_error_count": sum(r["v3_strict_outcome"] == "format_error" for r in replay),
        "known_trial_count": sum(r["known"] for r in judgments), "unknown_trial_count": sum(not r["known"] for r in judgments),
        "original_661_source_files_unchanged": True, "frozen_v2_implementation_unchanged": True,
        "historical_evidence_manifest_verified": True,
        "before_after_test": "Replay only, not new model performance; v3 would stop at attempt 3 before forwarding.",
        "failures": [
            {"method": "FinalOnly", "attempts": [3, 4], "reason": "Inner report is YAML-like task_id: ... without a JSON object. First invalid message was signed and forwarded because only the outer object was checked."},
            {"method": "NoDefense", "attempts": [5, 6], "reason": "Same inner JSON failure; final answer and intermediate delivery cannot be independently scored."},
            {"method": "FullCGC", "attempts": [7, 8], "reason": "First inner report invalid; existing guard blocked it, then second call had extra outer tool_request plus missing report close tag. Outer-contract ValueError ended the run."}],
        "summary_bug": "v2 evaluate initialized correct/refused=False on unknown outputs; score summed these booleans over normal_n without excluding unknown. v3 withholds whole-phase performance if any error or missing trial.",
        "shared_logic_review": "Live defense imports original EvidenceAssessor. Independent reviewer imports only frozen v2 oracle (json/re); no defense parser, quote matcher or tool-dispatch function is reused. New wire gate checks syntax/types only, not evidence safety or answers.",
        "provider_doc": "https://mimo.mi.com/docs/en-US/quick-start/usage-guide/text-generation/structured-output",
        "provider_support": "Official documentation verifies json_object only; it does not promise field/schema enforcement. Use documented JSON mode and strict local validation, no unsupported json_schema assumption.",
        "raw_evidence_root": V2_REAL.relative_to(ROOT).as_posix(), "replay": replay})
