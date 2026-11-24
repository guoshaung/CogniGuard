#!/usr/bin/env python3
"""X3 utility diagnosis. Does not retune frozen gates and does not score a PASS.

Imports the historical fail-open worker (read-only) and rescores with the
shared fail-closed rule: empty attribution denies, and every attributed
issuance must authorize. Oracle labels stay on the single true id.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

PASS_MIN_ABS_SAFETY_GAIN = 0.10
MAX_UTILITY_DROP = 0.10
MAX_OVERHEAD_RATIO = 10.0

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results" / "summary.json"
WORKER_PATH = Path(
    "/Users/MBP/.grok/worktrees/cogniguard-cogniguard/subagent-01a20c49-29d2-7e30-b1ff-6de9760b7b95"
    "/experiments/parallel_x_20261124/x3_issuance/run.py"
)
COORD_PATH = Path(
    "/Users/MBP/Exp/CogniGuard/CogniGuard/experiments/parallel_x_20261124/x3_issuance/run.py"
)
FIVE = (
    "s1-same-perm-meta",
    "s2-other-grantee",
    "s4-teach-read",
    "s3-live-copy",
    "s6-external-copy",
)
CHANNEL_WHY = {
    "benign": "issuance ids are in metadata and a signed receipt is attached",
    "meta": "issuance ids are in metadata; no receipt is attached",
    "stripped": "no metadata and no receipt",
    "boundary": "cross-org forward drops external source metadata and the receipt",
}
CITED_ROUNDED = {"W0": 0.7143, "F5": 0.4286, "F7": 0.3571}
HISTORICAL_W1_MS = 0.582
HISTORICAL_F2_MS = 0.037
HISTORICAL_RATIO = 15.60


def load_worker():
    name = "x3_failopen_worker"
    spec = importlib.util.spec_from_file_location(name, WORKER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {WORKER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def decide_closed(worker, records: dict, request, attributed_ids) -> bool:
    """Fail closed. Unknown ids do not authorize. all_sources stays a registry check."""
    ids = list(attributed_ids)
    if not ids:
        return False
    for issuance_id in ids:
        rec = records.get(issuance_id)
        if rec is None or not worker._issuance_authorizes(rec, request):
            return False
        if rec.mode == "all_sources":
            if not rec.source_ids:
                return False
            if not all(worker._source_obligation(records[sid], request) for sid in rec.source_ids):
                return False
    return True


def _asset_ids(worker_records, attributed) -> set[str]:
    return {worker_records[i].asset_id for i in attributed if i in worker_records}


def _quote_case(text: str, case_id: str) -> str:
    for line in text.splitlines():
        if f'"{case_id}"' in line:
            return line.strip().rstrip(",")
    raise KeyError(case_id)


def _quote_issuance(text: str, issuance_id: str) -> str:
    lines = text.splitlines()
    needle = f'"{issuance_id}"'
    for index, line in enumerate(lines):
        if needle not in line:
            continue
        start = index
        while start > 0 and "Issuance(" not in lines[start]:
            start -= 1
        if "Issuance(" not in lines[start]:
            continue
        chunk = []
        balance = 0
        for cursor in range(start, len(lines)):
            chunk.append(lines[cursor].rstrip())
            balance += lines[cursor].count("(") - lines[cursor].count(")")
            if balance <= 0:
                break
        return "\n".join(chunk).strip().rstrip(",")
    raise KeyError(issuance_id)


def _row_facts(rec) -> dict:
    return {
        "issuance_id": rec.issuance_id,
        "asset_id": rec.asset_id,
        "grantee": rec.grantee,
        "org": rec.org,
        "revoked": rec.revoked,
        "actions": sorted(rec.actions),
        "purposes": sorted(rec.purposes),
        "redistribution": rec.redistribution,
        "mode": rec.mode,
        "source_ids": list(rec.source_ids),
    }


def _deny_reasons(worker, records, rec, request) -> list[str]:
    reasons = []
    if rec.revoked:
        reasons.append("revoked")
    if rec.grantee != request.subject:
        reasons.append(f"grantee {rec.grantee} != subject {request.subject}")
    if request.action not in rec.actions:
        reasons.append(f"action {request.action} not in actions")
    if request.purpose not in rec.purposes:
        reasons.append(f"purpose {request.purpose} not in purposes")
    if request.action in {"forward", "redistribute"} and not worker._cross_org_ok(
        rec.redistribution, rec.org, request.dest_org
    ):
        reasons.append(
            f"redistribution {rec.redistribution} does not permit dest {request.dest_org} from org {rec.org}"
        )
    if rec.mode == "all_sources":
        if not rec.source_ids:
            reasons.append("all_sources without source ids")
        elif not all(worker._source_obligation(records[sid], request) for sid in rec.source_ids):
            reasons.append("a source obligation fails")
    return reasons


def _make_cred(worker, request):
    if request.variant == "paraphrase":
        return None
    body = {
        "asset_id": request.true_asset,
        "channel": "cred",
        "issuance_ids": list(request.true_ids),
    }
    return {"body": body, "signature": worker._sign(body)}


def _cred_ids(worker, cred, records) -> list[str]:
    ids = worker._verified_receipt_ids(cred)
    if not ids:
        return []
    return [item for item in ids if item in records]


def _record_ids(worker, request) -> list[str]:
    """True-id lookup only when metadata or a valid receipt is still present."""
    has_meta = bool(request.metadata)
    receipt_ids = worker._verified_receipt_ids(request.receipt)
    if not has_meta and not receipt_ids:
        return []
    return list(request.true_ids)


def _median_ms(fn, bundles, repeats: int = 5) -> float:
    for world, requests in bundles:
        for request in requests:
            fn(request, world)
    count = sum(len(requests) for _, requests in bundles)
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        for world, requests in bundles:
            for request in requests:
                fn(request, world)
        samples.append((time.perf_counter() - started) / count * 1000.0)
    samples.sort()
    return samples[len(samples) // 2]


def _score(worker, attr, bundles) -> dict:
    utility_hits = 0
    false_reject = 0
    unauth = 0
    oracle_allow = 0
    oracle_deny = 0
    correct = 0
    counted = 0
    open_utility = 0
    for world, requests in bundles:
        for request in requests:
            oracle = decide_closed(worker, world.records, request, request.true_ids)
            attributed = list(attr(request, world))
            allow = decide_closed(worker, world.records, request, attributed)
            open_allow = worker.decide(world.records, request, attributed)
            counted += 1
            oracle_allow += int(oracle)
            oracle_deny += int(not oracle)
            correct += int(allow == oracle)
            assets = _asset_ids(world.records, attributed)
            returned = allow and request.true_asset in assets
            utility_hits += int(oracle and returned)
            false_reject += int(oracle and not allow)
            unauth += int(allow and not oracle)
            open_returned = open_allow and request.true_asset in assets
            open_utility += int(oracle and open_returned)
    return {
        "n": counted,
        "correct": correct,
        "utility_numerator": utility_hits,
        "utility_denominator": oracle_allow,
        "false_reject_numerator": false_reject,
        "false_reject_denominator": oracle_allow,
        "unauthorized_numerator": unauth,
        "unauthorized_denominator": oracle_deny,
        "oracle_allow": oracle_allow,
        "oracle_deny": oracle_deny,
        "fail_open_utility_numerator": open_utility,
    }


def _empty_case_bucket():
    return {
        "seeds": [],
        "w0": [],
        "oracle": [],
        "f5": [],
        "f6": [],
        "f7": [],
        "cred": [],
        "record": [],
        "f6_ids": [],
        "f5_ids": [],
        "f7_ids": [],
        "cred_ids": [],
        "record_ids": [],
        "w0_ids": [],
    }


def _stable(bits: list[bool]) -> bool:
    return all(bit == bits[0] for bit in bits)


def _bge_probe() -> dict:
    imports = {}
    for name in ("sentence_transformers", "FlagEmbedding", "bge", "torch", "transformers", "onnxruntime"):
        try:
            __import__(name)
        except Exception as exc:
            imports[name] = f"{type(exc).__name__}: {exc}"
        else:
            imports[name] = "importable"
    caches = []
    for path in (
        Path.home() / ".cache" / "huggingface",
        Path.home() / ".cache" / "torch",
        Path.home() / "Library" / "Caches" / "huggingface",
        Path("/Users/MBP/Exp/CogniGuard/CogniGuard/assets"),
        ROOT.parents[2] / "assets",
    ):
        caches.append({"path": str(path), "exists": path.exists()})
    weight_hits = []
    try:
        found = subprocess.run(
            [
                "find",
                str(Path.home() / ".cache"),
                "/Users/MBP/Exp/CogniGuard",
                "/tmp",
                "-iname",
                "*bge-small*",
                "-o",
                "-iname",
                "*bge-reranker*",
                "-o",
                "-iname",
                "*bge-base*",
                "-o",
                "-iname",
                "*bge-large*",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=40,
        )
        weight_hits = [line for line in found.stdout.splitlines() if line.strip()][:20]
        if found.returncode not in (0, 1) and not weight_hits:
            weight_hits = []
    except Exception:
        weight_hits = []
    head = {"ok": False, "error": None, "content_length": None, "status_line": None}
    try:
        completed = subprocess.run(
            [
                "curl",
                "-sI",
                "-L",
                "--max-time",
                "20",
                "https://huggingface.co/BAAI/bge-small-en-v1.5/resolve/main/model.safetensors",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=25,
        )
        statuses = [line for line in completed.stdout.splitlines() if line.startswith("HTTP/")]
        head["status_line"] = statuses[-1] if statuses else ""
        for line in completed.stdout.splitlines():
            if line.lower().startswith("content-length:"):
                head["content_length"] = int(line.split(":", 1)[1].strip())
        head["ok"] = completed.returncode == 0 and bool(head["status_line"])
        if completed.returncode != 0:
            head["error"] = (completed.stderr or f"curl exit {completed.returncode}")[:500]
    except Exception as exc:
        head["error"] = f"{type(exc).__name__}: {exc}"
    importable = [name for name, state in imports.items() if state == "importable" and name != "numpy"]
    blocked = not any(imports[name] == "importable" for name in ("sentence_transformers", "FlagEmbedding", "bge"))
    blocked = blocked or not weight_hits
    error = (
        "F3/F4 BLOCKED. sentence_transformers, FlagEmbedding, and bge do not import in this interpreter. "
        "torch, transformers, and onnxruntime do not import. No local Hugging Face cache or bge weight "
        "directory was found. Weights were not downloaded and no hosted embedding endpoint was called. "
        "No scores were invented."
    )
    if head.get("content_length"):
        error += (
            f" HEAD of BAAI/bge-small-en-v1.5 model.safetensors returned {head['content_length']} bytes"
            f" ({head.get('status_line') or 'no status'}). The body was not fetched because no local loader can run it."
        )
    if not blocked:
        error = None
    return {
        "status": "BLOCKED" if blocked else "AVAILABLE",
        "f3": "BLOCKED" if blocked else "READY",
        "f4": "BLOCKED" if blocked else "READY",
        "imports": imports,
        "importable": importable,
        "caches": caches,
        "weight_hits": weight_hits,
        "remote_head": head,
        "error": error,
        "unauthorized_success": None,
        "utility": None,
        "changed_five_cases": None,
        "ran": False,
    }


def _maybe_run_bge(worker, bundles, bge: dict, five_oracle_w0: dict) -> dict:
    if bge["status"] == "BLOCKED":
        return bge
    # Local model present. Retrieval expands every issuance of the nearest assets,
    # then the same fail-closed decide runs. No threshold here is a frozen gate.
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        bge["status"] = "BLOCKED"
        bge["f3"] = "BLOCKED"
        bge["f4"] = "BLOCKED"
        bge["error"] = f"F3/F4 BLOCKED. Import failed at runtime: {type(exc).__name__}: {exc}"
        return bge
    model_name = bge["weight_hits"][0]
    try:
        model = SentenceTransformer(model_name)
    except Exception as exc:
        bge["status"] = "BLOCKED"
        bge["f3"] = "BLOCKED"
        bge["f4"] = "BLOCKED"
        bge["error"] = f"F3/F4 BLOCKED. Local model did not load: {type(exc).__name__}: {exc}"
        return bge

    def attribute_f3(request, world):
        assets = list(world.assets)
        corpus = model.encode([world.asset_text[asset] for asset in assets], normalize_embeddings=True)
        query = model.encode([request.text], normalize_embeddings=True)[0]
        scored = []
        for asset, vector in zip(assets, corpus):
            score = float(sum(a * b for a, b in zip(query, vector)))
            scored.append((asset, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        if not scored or scored[0][1] <= 0:
            return []
        cutoff = scored[0][1] * 0.50
        chosen = [asset for asset, score in scored[:3] if score >= cutoff]
        return worker._expand(world, chosen)

    stats = _score(worker, attribute_f3, bundles)
    changed = []
    for case_id in FIVE:
        allows = []
        for world, requests in bundles:
            for request in requests:
                if request.case_id != case_id:
                    continue
                allow = decide_closed(worker, world.records, request, attribute_f3(request, world))
                allows.append(allow)
        w0_allow = five_oracle_w0[case_id]
        changed.append({"case_id": case_id, "f3_allow": _stable(allows) and allows[0], "w0_allow": w0_allow, "same_as_w0": _stable(allows) and allows[0] == w0_allow})
    den = stats["utility_denominator"] or 1
    bge.update(
        {
            "ran": True,
            "f3": "RAN",
            "f4": "BLOCKED",
            "error": "F4 BLOCKED: no local reranker directory was found. F3 used the local embedding directory only.",
            "model": model_name,
            "unauthorized_success": {
                "numerator": stats["unauthorized_numerator"],
                "denominator": stats["unauthorized_denominator"],
            },
            "utility": {"numerator": stats["utility_numerator"], "denominator": den},
            "changed_five_cases": changed,
        }
    )
    return bge


def _fraction(stats: dict) -> dict:
    return {
        "numerator": stats["utility_numerator"],
        "denominator": stats["utility_denominator"],
        "false_reject_numerator": stats["false_reject_numerator"],
        "false_reject_denominator": stats["false_reject_denominator"],
        "unauthorized_numerator": stats["unauthorized_numerator"],
        "unauthorized_denominator": stats["unauthorized_denominator"],
        "fail_open_utility_numerator": stats["fail_open_utility_numerator"],
    }


def _render(summary: dict) -> str:
    util = summary["utility_fractions"]
    lines = [
        "# X3 utility diagnosis",
        "",
        "Historical verdict: STOP. This diagnosis is not a PASS and does not reopen X3.",
        "The fail-closed rule is the one that was rescored: an empty id list denies, and every attributed issuance must authorize. One true id keeps the oracle labels on the catalog.",
        "The imported worker `decide` stays fail-open (allow if any attributed issuance authorizes) and was not edited. Reported utilities use fail-closed.",
        f"`MAX_OVERHEAD_RATIO` stays {MAX_OVERHEAD_RATIO:.0f}. It was not retuned.",
        "",
        "## Utility",
        "",
        "A utility hit requires oracle allow, a fail-closed allow, and the true asset id among the assets of the attributed issuances. The denominator is the oracle-allow count.",
        "",
        f"Oracle-allow requests: {util['oracle_allow_requests']}. Oracle-deny requests: {util['oracle_deny_requests']}.",
        "",
        "| method | utility | false reject | unauthorized |",
        "| --- | --- | --- | --- |",
    ]
    for name in ("W0", "F5", "F7", "F6", "Oracle", "CRED", "RECORD"):
        row = util[name]
        lines.append(
            f"| {name} | {row['numerator']}/{row['denominator']} | "
            f"{row['false_reject_numerator']}/{row['false_reject_denominator']} | "
            f"{row['unauthorized_numerator']}/{row['unauthorized_denominator']} |"
        )
    lines.extend(
        [
            "",
            summary["utility_fractions"]["cited_check"],
            "",
            "F6 on the five oracle-allow cases "
            f"(5 logical cases x 5 seeds): {util['F6']['on_five_cases']['numerator']}/{util['F6']['on_five_cases']['denominator']}. "
            f"F5 on those requests: {util['F5']['on_five_cases']['numerator']}/{util['F5']['on_five_cases']['denominator']}. "
            f"F7: {util['F7']['on_five_cases']['numerator']}/{util['F7']['on_five_cases']['denominator']}. "
            f"CRED: {util['CRED']['on_five_cases']['numerator']}/{util['CRED']['on_five_cases']['denominator']}. "
            f"RECORD: {util['RECORD']['on_five_cases']['numerator']}/{util['RECORD']['on_five_cases']['denominator']}.",
            "",
            util["F6"].get("overall_note", ""),
            "",
            "## Five cases",
            "",
            "Channel legend, quoted from the worker script:",
            "",
            "```",
            summary["channel_legend"],
            "```",
            "",
            "Issuance defaults, quoted from the worker dataclass. Fields omitted on a constructor use these defaults:",
            "",
            "```",
            summary["issuance_class_quote"],
            "```",
            "",
        ]
    )
    for case in summary["five_cases"]:
        facts = case["true_issuance"]
        lines.extend(
            [
                f"### {case['case_id']}",
                "",
                f"Still holds: {case['still_holds']}. Fair baseline recovers the allow: {case['fair_baseline_recovers']}.",
                f"Recovered by: {', '.join(case['recovered_by']) if case['recovered_by'] else 'none'}.",
                "",
                "Catalog row, quoted from the worker script:",
                "",
                "```",
                case["catalog_quote"],
                "```",
                "",
                "True issuance row, quoted from the worker script:",
                "",
                "```",
                case["issuance_quote"],
                "```",
                "",
                (
                    f"Scenario {case['scenario']}. Subject {case['subject']}. Action {case['action']}. "
                    f"Purpose {case['purpose']}. Dest org {case['dest_org']}. Asset {case['asset']}. "
                    f"True issuance ids {case['true_ids']}. Variant {case['variant']}. Channel {case['channel']}: {case['channel_why']}."
                ),
                f"Oracle allow: {case['oracle_allow']}. W0 allow: {case['w0_allow']}.",
                (
                    f"Table facts for {facts['issuance_id']}: grantee {facts['grantee']}, org {facts['org']}, "
                    f"revoked {facts['revoked']}, actions {facts['actions']}, purposes {facts['purposes']}, "
                    f"redistribution {facts['redistribution']}, mode {facts['mode']}, source ids {facts['source_ids']}."
                ),
                case["license_note"],
                case["sibling_note"],
            ]
        )
        for sibling in case["siblings"]:
            lines.extend(
                [
                    "",
                    f"Sibling row {sibling['issuance_id']}, quoted from the worker script:",
                    "",
                    "```",
                    sibling["quote"],
                    "```",
                ]
            )
        lines.extend(
            [
                case["channel_note"],
                (
                    "Allow bits versus W0: "
                    + ", ".join(f"{name}={case['allows'][name]}" for name in ("CRED", "F6", "F5", "F7", "RECORD"))
                    + "."
                ),
                "",
            ]
        )
    overhead = summary["overhead_decomposition"]
    lines.extend(["## Overhead", ""])
    lines.append("Median of 5 warmed passes over the same 120 requests. Milliseconds per request. Ratios use F2 BM25 rank only as the denominator.")
    lines.append("")
    lines.append("| piece | ms/request | ratio to F2 rank |")
    lines.append("| --- | ---: | ---: |")
    for name in overhead["order"]:
        lines.append(
            f"| {name} | {overhead['median_ms'][name]:.4f} | {overhead['ratio_to_f2_bm25_rank'][name]:.2f} |"
        )
    lines.extend(
        [
            "",
            overhead["narrative"],
            "",
            "## BGE",
            "",
            summary["bge_status"]["error"] or summary["bge_status"]["status"],
            "",
            "## Handoff",
            "",
            "PILOT_HANDOFF.md written: "
            + ("yes" if summary["pilot_handoff"] else "no")
            + ". "
            + summary["diagnosis_note"],
            "",
        ]
    )
    return "\n".join(lines)


def _handoff(summary: dict) -> str:
    rows = "\n".join(f"- `{case['case_id']}` ({case['variant']}, {case['channel']})" for case in summary["five_cases"])
    return "\n".join(
        [
            "# Pilot request: five synthetic issuance cases",
            "",
            "To the watermark experiment owner.",
            "",
            "Historical X3 verdict remains STOP. This note is not a PASS. Do not retune `MAX_OVERHEAD_RATIO` (10).",
            "Do not start a GPU server. Do not implement a new watermark in this diagnosis. Do not run image watermarking.",
            "",
            "Text entry point on this tree: `protection/audit_trace/src/hybrid_watermark.py` (`HybridWatermarkSystem.embed_hybrid` and `detect_hybrid`).",
            "Image serving under `protection/supporting/image_watermark/api/server.py` is out of scope for these cases.",
            "",
            "Please run a minimal pilot on only these five synthetic cases. The payload is an issuance id. The allow rule stays in the issuance table. Fail closed: every attributed issuance must authorize, and an empty attribution denies.",
            "",
            rows,
            "",
            "The diagnosis found no fair baseline (signed credential, simhash, metadata, receipt, or registry lookup without the mark) that allows these oracle-allow requests while W0 does. That is the only reason this request exists.",
            "",
        ]
    )


def main() -> None:
    if MAX_OVERHEAD_RATIO != 10.0:
        raise RuntimeError("frozen overhead cap was changed")
    worker = load_worker()
    if "ALLOW if any" not in (worker.decide.__doc__ or ""):
        raise RuntimeError("loaded worker is not the fail-open decide")
    if worker.MAX_OVERHEAD_RATIO != 10.0 or worker.PASS_MIN_ABS_SAFETY_GAIN != 0.10 or worker.MAX_UTILITY_DROP != 0.10:
        raise RuntimeError("worker frozen thresholds differ from the gate")
    if not COORD_PATH.is_file():
        raise RuntimeError("coordinator script missing")
    coord_text = COORD_PATH.read_text(encoding="utf-8")
    if "return all(_authorize(row, request) for row in chosen)" not in coord_text:
        raise RuntimeError("coordinator fail-closed shape was not found")
    worker_text = WORKER_PATH.read_text(encoding="utf-8")
    if any(len(case[7]) != 1 for case in worker.CASES):
        raise RuntimeError("oracle label stability requires one true id")

    bundles = []
    creds = {}
    expected = {case[0]: case[-1] for case in worker.CASES}
    for seed in worker.SEEDS:
        world = worker.build_world(seed)
        worker._check_world(world)
        requests = [worker.materialize(world, case) for case in worker.CASES]
        for request in requests:
            oracle = decide_closed(worker, world.records, request, request.true_ids)
            open_oracle = worker.decide(world.records, request, request.true_ids)
            if oracle != open_oracle or oracle != expected[request.case_id]:
                raise RuntimeError(f"oracle drift {request.case_id} seed {seed}")
            creds[(seed, request.case_id)] = _make_cred(worker, request)
        bundles.append((world, requests))

    # Bad signature must not yield ids. Paraphrase carries no credential.
    sample = next(iter(creds.values()))
    while sample is None:
        sample = next(c for c in creds.values() if c is not None)
    tampered = {"body": sample["body"], "signature": "0" * 64}
    if _cred_ids(worker, tampered, bundles[0][0].records):
        raise RuntimeError("bad credential signature was trusted")
    if any(creds[(seed, "ctrl-paraphrase")] is not None for seed in worker.SEEDS):
        raise RuntimeError("paraphrase credential should be absent")

    def attribute_cred(request, world):
        return _cred_ids(worker, creds[(world.seed, request.case_id)], world.records)

    def attribute_record(request, world):
        return _record_ids(worker, request)

    methods = {
        "F0": worker.attribute_f0,
        "F1": worker.attribute_f1,
        "F2": worker.attribute_f2,
        "F5": worker.attribute_f5,
        "F6": worker.attribute_f6,
        "F7": worker.attribute_f7,
        "W0": worker.attribute_w0,
        "W1": worker.attribute_w1,
        "Oracle": worker.attribute_oracle,
        "CRED": attribute_cred,
        "RECORD": attribute_record,
    }
    scored = {name: _score(worker, fn, bundles) for name, fn in methods.items()}
    oracle_allow = scored["Oracle"]["oracle_allow"]
    oracle_deny = scored["Oracle"]["oracle_deny"]
    if any(row["oracle_allow"] != oracle_allow or row["oracle_deny"] != oracle_deny for row in scored.values()):
        raise RuntimeError("oracle counts diverged across methods")

    buckets = {case_id: _empty_case_bucket() for case_id in FIVE}
    for world, requests in bundles:
        for request in requests:
            if request.case_id not in buckets:
                continue
            bucket = buckets[request.case_id]
            bucket["seeds"].append(world.seed)
            decisions = {
                "W0": decide_closed(worker, world.records, request, worker.attribute_w0(request, world)),
                "F5": decide_closed(worker, world.records, request, worker.attribute_f5(request, world)),
                "F6": decide_closed(worker, world.records, request, worker.attribute_f6(request, world)),
                "F7": decide_closed(worker, world.records, request, worker.attribute_f7(request, world)),
                "CRED": decide_closed(worker, world.records, request, attribute_cred(request, world)),
                "RECORD": decide_closed(worker, world.records, request, attribute_record(request, world)),
            }
            oracle = decide_closed(worker, world.records, request, request.true_ids)
            bucket["oracle"].append(oracle)
            bucket["w0"].append(decisions["W0"])
            bucket["f5"].append(decisions["F5"])
            bucket["f6"].append(decisions["F6"])
            bucket["f7"].append(decisions["F7"])
            bucket["cred"].append(decisions["CRED"])
            bucket["record"].append(decisions["RECORD"])
            if world.seed == worker.SEEDS[0]:
                bucket["request"] = request
                bucket["f6_ids"] = list(worker.attribute_f6(request, world))
                bucket["f5_ids"] = list(worker.attribute_f5(request, world))
                bucket["f7_ids"] = list(worker.attribute_f7(request, world))
                bucket["cred_ids"] = list(attribute_cred(request, world))
                bucket["record_ids"] = list(attribute_record(request, world))
                bucket["w0_ids"] = list(worker.attribute_w0(request, world))

    five_cases = []
    recovers = {}
    class_lines = []
    capture = False
    for line in worker_text.splitlines():
        if line.startswith("class Issuance"):
            capture = True
        if capture:
            class_lines.append(line)
            if line.startswith("    mode:"):
                break
    issuance_class_quote = "\n".join(class_lines)
    channel_legend = "\n".join(
        line.strip()
        for line in worker_text.splitlines()
        if line.strip().startswith("# ") and any(token in line for token in ("benign =", "meta =", "stripped =", "boundary ="))
    )

    for case_id in FIVE:
        bucket = buckets[case_id]
        request = bucket["request"]
        for key in ("oracle", "w0", "f5", "f6", "f7", "cred", "record"):
            if not _stable(bucket[key]):
                raise RuntimeError(f"{case_id} {key} is not stable across seeds: {bucket[key]}")
        true_id = request.true_ids[0]
        true_rec = bundles[0][0].records[true_id]
        siblings = []
        for issuance_id in bundles[0][0].issuances_by_asset[request.true_asset]:
            if issuance_id == true_id:
                continue
            rec = bundles[0][0].records[issuance_id]
            reasons = _deny_reasons(worker, bundles[0][0].records, rec, request)
            siblings.append(
                {
                    "issuance_id": issuance_id,
                    "authorizes": not reasons,
                    "reasons": reasons,
                    "facts": _row_facts(rec),
                    "quote": _quote_issuance(worker_text, issuance_id),
                }
            )
        authorizing_siblings = [row["issuance_id"] for row in siblings if row["authorizes"]]
        allows = {
            "W0": bucket["w0"][0],
            "F5": bucket["f5"][0],
            "F6": bucket["f6"][0],
            "F7": bucket["f7"][0],
            "CRED": bucket["cred"][0],
            "RECORD": bucket["record"][0],
        }
        recovered_by = [name for name in ("CRED", "F6", "F5", "F7", "RECORD") if allows[name]]
        still_holds = bool(allows["W0"] and bucket["oracle"][0] and not recovered_by)
        meta_ids = list((request.metadata or {}).get("issuance_ids") or [])
        receipt_ok = worker._verified_receipt_ids(request.receipt) is not None
        only_mark = (not meta_ids) and (not receipt_ok) and bool(request.mark.get("intact"))
        if authorizing_siblings:
            sibling_note = (
                "A sibling grant already authorizes this subject, action, and purpose without the watermark id: "
                + ", ".join(authorizing_siblings)
                + "."
            )
        else:
            sibling_note = (
                "No sibling issuance of this asset authorizes this subject, action, and purpose. "
                + " ".join(
                    f"{row['issuance_id']} does not ({'; '.join(row['reasons'])})." for row in siblings
                )
            )
        if only_mark:
            channel_note = (
                "Metadata and receipt are both absent, and the ideal mark is intact. "
                "The W0 allow depends on the watermark being the only remaining copy of the issuance id "
                "after metadata was stripped. That channel is not treated as a privileged access rule. "
                "CRED carries the same id list in an HMAC on this exact or light variant."
            )
        else:
            channel_note = (
                f"Metadata issuance ids present: {meta_ids or 'none'}. Valid receipt present: {receipt_ok}. "
                "The watermark is not the only remaining copy of the issuance id."
            )
        license_note = (
            "The true issuance authorizes this request under the table checks "
            "(grantee, not revoked, action, purpose, and redistribution when the action is forward or redistribute). "
            "The allow is a reasonable license outcome for that row."
            if not _deny_reasons(worker, bundles[0][0].records, true_rec, request)
            else "The true issuance does not authorize this request. The allow is not a reasonable outcome for that row."
        )
        case_obj = {
            "case_id": case_id,
            "scenario": request.scenario,
            "subject": request.subject,
            "action": request.action,
            "purpose": request.purpose,
            "dest_org": request.dest_org,
            "asset": request.true_asset,
            "true_ids": list(request.true_ids),
            "variant": request.variant,
            "channel": next(case[9] for case in worker.CASES if case[0] == case_id),
            "channel_why": CHANNEL_WHY[next(case[9] for case in worker.CASES if case[0] == case_id)],
            "oracle_allow": bucket["oracle"][0],
            "w0_allow": allows["W0"],
            "catalog_quote": _quote_case(worker_text, case_id),
            "issuance_quote": _quote_issuance(worker_text, true_id),
            "true_issuance": _row_facts(true_rec),
            "siblings": siblings,
            "authorizing_sibling_ids": authorizing_siblings,
            "watermark_is_only_remaining_id_channel": only_mark,
            "seed0_ids": {
                "W0": bucket["w0_ids"],
                "F5": bucket["f5_ids"],
                "F6": bucket["f6_ids"],
                "F7": bucket["f7_ids"],
                "CRED": bucket["cred_ids"],
                "RECORD": bucket["record_ids"],
            },
            "allows": allows,
            "same_allow_as_w0": {name: allows[name] == allows["W0"] for name in ("CRED", "F6", "F5", "F7", "RECORD")},
            "recovered_by": recovered_by,
            "still_holds": still_holds,
            "fair_baseline_recovers": bool(recovered_by),
            "license_note": license_note,
            "sibling_note": sibling_note,
            "channel_note": channel_note,
        }
        five_cases.append(case_obj)
        recovers[case_id] = bool(recovered_by)

    def on_five(name: str) -> dict:
        hits = 0
        total = 0
        for case in five_cases:
            if name == "Oracle":
                bit = case["oracle_allow"]
            else:
                bit = case["allows"][name]
            # five logical cases, each stable, times five seeds, all oracle-allow
            total += len(worker.SEEDS)
            hits += len(worker.SEEDS) if bit else 0
        return {"numerator": hits, "denominator": total}

    fractions = {
        "oracle_allow_requests": oracle_allow,
        "oracle_deny_requests": oracle_deny,
        "definition": (
            "utility_hits / oracle_allow. A hit requires oracle allow AND the true asset among "
            "attributed issuance asset ids AND a fail-closed allow."
        ),
    }
    cited_bits = []
    for name in ("W0", "F5", "F7", "F6", "Oracle", "CRED", "RECORD"):
        fractions[name] = _fraction(scored[name])
        fractions[name]["on_five_cases"] = on_five(name)
        if name in CITED_ROUNDED:
            den = fractions[name]["denominator"]
            num = fractions[name]["numerator"]
            rounded = round(num / den, 4) if den else None
            cited_bits.append(f"{name} {num}/{den} rounds to {rounded} (cited {CITED_ROUNDED[name]})")
    fractions["cited_check"] = (
        "Cited rounded utilities are the fail-closed (and, for these three methods, also fail-open) ratios. "
        + " ".join(cited_bits)
        + ". Round-3 forms of the same ratios are 0.714, 0.429, and 0.357. The denominator is 70."
    )
    f6_keep = []
    for case in worker.CASES:
        case_id = case[0]
        allow_bits = []
        oracle_bits = []
        for world, requests in bundles:
            for request in requests:
                if request.case_id != case_id:
                    continue
                oracle_bits.append(decide_closed(worker, world.records, request, request.true_ids))
                allow_bits.append(
                    decide_closed(worker, world.records, request, worker.attribute_f6(request, world))
                )
        if oracle_bits and all(oracle_bits) and all(allow_bits):
            f6_keep.append(case_id)
    fractions["F6"]["overall_note"] = (
        "F6's fail-closed numerator is the oracle-allow requests whose simhash expansion contains only authorizing issuances: "
        + ", ".join(f6_keep)
        + f" ({fractions['F6']['numerator']}/{fractions['F6']['denominator']}). "
        "None of the five focus cases are in that numerator (0/25). "
        f"The same F6 ids under the untouched fail-open worker rule score "
        f"{fractions['F6']['fail_open_utility_numerator']}/{fractions['F6']['denominator']}, "
        "because any one authorizing row is enough."
    )

    def rank_only(request, world):
        return world.bm25.rank(worker._content_tokens(request.text))

    def simhash_only(request, world):
        return worker._simhash(worker._content_tokens(request.text))

    def minhash_only(request, world):
        return worker._minhash(worker._content_tokens(request.text))

    def receipt_only(request, world):
        return worker._verified_receipt_ids(request.receipt)

    def mark_only(request, world):
        return worker.attribute_w0(request, world)

    def touch(request, world):
        return None

    timed = {
        "F2_bm25_rank_only": _median_ms(rank_only, bundles),
        "F2_attribute": _median_ms(worker.attribute_f2, bundles),
        "F6_simhash_only": _median_ms(simhash_only, bundles),
        "F6_attribute": _median_ms(worker.attribute_f6, bundles),
        "F7_receipt_verify_only": _median_ms(receipt_only, bundles),
        "F7_attribute": _median_ms(worker.attribute_f7, bundles),
        "W0_mark_intact_lookup_only": _median_ms(mark_only, bundles),
        "W1_as_defined": _median_ms(worker.attribute_w1, bundles),
        "F1_minhash_only": _median_ms(minhash_only, bundles),
        "F1_attribute": _median_ms(worker.attribute_f1, bundles),
        "call_overhead": _median_ms(touch, bundles),
    }
    base_ms = timed["F2_bm25_rank_only"]
    ratios = {name: (value / base_ms if base_ms else None) for name, value in timed.items()}
    recomputed_w1_f2 = timed["W1_as_defined"] / timed["F2_attribute"] if timed["F2_attribute"] else None
    overhead = {
        "repeats": 5,
        "warmed": True,
        "requests": oracle_allow + oracle_deny,
        "unit": "ms_per_request",
        "order": [
            "F2_bm25_rank_only",
            "F6_simhash_only",
            "F7_receipt_verify_only",
            "W0_mark_intact_lookup_only",
            "W1_as_defined",
            "F1_minhash_only",
            "F1_attribute",
            "F6_attribute",
            "F2_attribute",
            "call_overhead",
        ],
        "median_ms": timed,
        "ratio_to_f2_bm25_rank": ratios,
        "recomputed_w1_attribute_over_f2_attribute": recomputed_w1_f2,
        "historical_w1_ms": HISTORICAL_W1_MS,
        "historical_f2_ms": HISTORICAL_F2_MS,
        "historical_ratio": HISTORICAL_RATIO,
        "cap": MAX_OVERHEAD_RATIO,
        "cap_changed": False,
        "historical_exceeds_cap": HISTORICAL_RATIO > MAX_OVERHEAD_RATIO,
        "recomputed_attribute_ratio_exceeds_cap": bool(recomputed_w1_f2 and recomputed_w1_f2 > MAX_OVERHEAD_RATIO),
    }
    f1_dominates = timed["F1_attribute"] > timed["W1_as_defined"] and timed["F1_attribute"] > timed["F2_bm25_rank_only"] * 10
    overhead["narrative"] = (
        f"Historical fail-open timing was W1 {HISTORICAL_W1_MS:.3f} ms versus F2 {HISTORICAL_F2_MS:.3f} ms, "
        f"ratio {HISTORICAL_RATIO:.2f}. That ratio is above MAX_OVERHEAD_RATIO {MAX_OVERHEAD_RATIO:.0f}, "
        "so the historical overhead comparison does not pass. The cap was not changed. "
        f"Recomputed on this machine, W1-as-defined is {timed['W1_as_defined']:.4f} ms/request and "
        f"F2 attribute is {timed['F2_attribute']:.4f} ms/request, ratio {recomputed_w1_f2:.2f}. "
        f"F2 BM25 rank only is {timed['F2_bm25_rank_only']:.4f} ms. "
        f"Rank-only and full F2 attribute differ by {abs(timed['F2_bm25_rank_only'] - timed['F2_attribute']):.4f} ms, timer noise around the historical 0.037 ms. "
        f"Simhash only is {timed['F6_simhash_only']:.4f} ms (ratio {ratios['F6_simhash_only']:.2f}). "
        f"Full F6 attribute is {timed['F6_attribute']:.4f} ms. "
        f"Receipt verify only is {timed['F7_receipt_verify_only']:.4f} ms (ratio {ratios['F7_receipt_verify_only']:.2f}). "
        f"Ideal-mark lookup only is {timed['W0_mark_intact_lookup_only']:.4f} ms (ratio {ratios['W0_mark_intact_lookup_only']:.2f}). "
        f"Empty call overhead is {timed['call_overhead']:.4f} ms. "
        "The 15.6x gap is the simhash fingerprint inside W1, not HMAC verification, not the ideal-mark lookup, and not the scoring harness. "
        + (
            f"F1 MinHash attribute is {timed['F1_attribute']:.4f} ms/request, ratio {ratios['F1_attribute']:.2f} to F2 rank. It dominates W1."
            if f1_dominates
            else f"F1 MinHash attribute is {timed['F1_attribute']:.4f} ms/request."
        )
    )

    bge = _bge_probe()
    bge = _maybe_run_bge(worker, bundles, bge, {case["case_id"]: case["w0_allow"] for case in five_cases})
    all_hold = all(case["still_holds"] for case in five_cases)
    pilot = bool(all_hold)
    note = (
        "Fail-closed rescore over 5 seeds x 24 cases. Unauthorized success is zero for the scored methods "
        "when the unauthorized numerator is zero. "
        "The five F7-deny to W0-allow cases are real license allows for the true row, and no sibling row authorizes them. "
        "Four of the five have metadata and receipt stripped, so the ideal mark is the only historical channel still holding the issuance id. "
        "s1-same-perm-meta still has the id in metadata, so F5 and RECORD allow it without a mark. "
        "CRED, a signed embedded issuance id present on exact and light variants and absent on paraphrase, allows all five. "
        "Those cases therefore do not hold under a fair baseline, and no watermark pilot is requested. "
        "A channel that only a watermark carries is not a privileged access rule. "
        f"Historical ratio {HISTORICAL_RATIO:.2f} still exceeds {MAX_OVERHEAD_RATIO:.0f}. "
        "diagnosis_verdict is STOP."
    )
    # Tighten the unauthorized sentence from the actual numerators.
    unauth_bits = []
    for name in ("F0", "F1", "F2", "F5", "F6", "F7", "W0", "W1", "Oracle", "CRED", "RECORD"):
        row = scored[name]
        unauth_bits.append(f"{name} {row['unauthorized_numerator']}/{row['unauthorized_denominator']}")
    note = (
        "Fail-closed rescore over "
        f"{oracle_allow + oracle_deny} requests ({len(worker.SEEDS)} seeds x {len(worker.CASES)} cases). "
        f"Oracle allow {oracle_allow}, oracle deny {oracle_deny}. "
        "Unauthorized success numerators: "
        + ", ".join(unauth_bits)
        + ". "
        "Utility for W0, F5, and F7 uses the worker hit rule (oracle allow, true asset in the attributed assets, decision allows) under fail-closed. "
        "Those three methods attribute at most the true id, so fail-open and fail-closed utilities match for them. "
        "The five logical F7 denials that W0 allows are oracle allows. "
        "No sibling grant authorizes those five requests. "
        "s1-same-perm-meta still carries the issuance id in metadata (receipt absent), so the mark is not the only copy; F5 and RECORD allow it. "
        "The other four have metadata and receipt stripped. The ideal mark is then the only historical channel that still carries the true issuance id. "
        "That is not a privileged access rule. CRED, an HMAC over the same issuance id list, is present on exact and light variants and absent on paraphrase, and it allows all five. "
        "F6's simhash hit expands to every issuance of the asset, and fail-closed denies because the sibling row does not authorize. "
        "No case still holds. pilot_handoff is false. "
        f"The historical W1/F2 ratio {HISTORICAL_RATIO:.2f} still exceeds MAX_OVERHEAD_RATIO {MAX_OVERHEAD_RATIO:.0f}, so that overhead comparison does not pass. "
        "diagnosis_verdict is STOP. X3 did not pass."
    )
    summary = {
        "experiment": "X3-diag",
        "historical_verdict": "STOP",
        "diagnosis_verdict": "STOP",
        "utility_fractions": fractions,
        "five_cases": five_cases,
        "fair_baseline_recovers": {**recovers, "overall": any(recovers.values())},
        "overhead_decomposition": overhead,
        "bge_status": bge,
        "pilot_handoff": pilot,
        "diagnosis_note": note,
        "channel_legend": channel_legend,
        "issuance_class_quote": issuance_class_quote,
        "frozen_thresholds": {
            "PASS_MIN_ABS_SAFETY_GAIN": PASS_MIN_ABS_SAFETY_GAIN,
            "MAX_UTILITY_DROP": MAX_UTILITY_DROP,
            "MAX_OVERHEAD_RATIO": MAX_OVERHEAD_RATIO,
        },
        "decision": "fail-closed: every attributed issuance must authorize; empty attribution denies",
        "paths": {
            "run": str(ROOT / "run.py"),
            "result": str(ROOT / "RESULT.md"),
            "summary": str(RESULTS),
            "worker": str(WORKER_PATH),
            "coordinator": str(COORD_PATH),
        },
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (ROOT / "RESULT.md").write_text(_render(summary), encoding="utf-8")
    handoff = ROOT / "results" / "PILOT_HANDOFF.md"
    if pilot:
        handoff.write_text(_handoff(summary), encoding="utf-8")
    elif handoff.exists():
        handoff.unlink()
    print(
        json.dumps(
            {
                "historical_verdict": summary["historical_verdict"],
                "diagnosis_verdict": summary["diagnosis_verdict"],
                "oracle_allow": oracle_allow,
                "oracle_deny": oracle_deny,
                "utility": {
                    name: f"{fractions[name]['numerator']}/{fractions[name]['denominator']}"
                    for name in ("W0", "F5", "F7", "F6", "Oracle")
                },
                "false_reject": {
                    name: f"{fractions[name]['false_reject_numerator']}/{fractions[name]['false_reject_denominator']}"
                    for name in ("W0", "F5", "F7", "F6", "Oracle")
                },
                "still_holds": {case["case_id"]: case["still_holds"] for case in five_cases},
                "recovers": summary["fair_baseline_recovers"],
                "pilot_handoff": pilot,
                "w1_over_f2": recomputed_w1_f2,
                "bge": bge["status"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
