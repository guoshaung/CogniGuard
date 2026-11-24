"""X3 dev scan: does an ideal issuance watermark change the security decision?

Thresholds are frozen before the run. BGE is not downloaded.
The shared decision is fail-closed: every attributed issuance must authorize
the request. A watermark carries an issuance id only, never a hidden rule.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path

PASS_MIN_ABS_SAFETY_GAIN = 0.10
MAX_UTILITY_DROP = 0.10
MAX_OVERHEAD_RATIO = 10.0

ROOT = Path(__file__).resolve().parent


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _minhash(text: str, bands: int = 8) -> tuple[int, ...]:
    tokens = text.split()
    if not tokens:
        return tuple(0 for _ in range(bands))
    sketches = []
    for band in range(bands):
        sketches.append(min(hash((band, token)) for token in tokens))
    return tuple(sketches)


def _bow(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in text.split():
        counts[token] = counts.get(token, 0) + 1
    return counts


def _bm25_score(query: dict[str, int], doc: dict[str, int]) -> float:
    score = 0.0
    for token, weight in query.items():
        score += weight * doc.get(token, 0)
    return score


def _simhash(text: str) -> int:
    bits = [0] * 64
    for token in text.split():
        digest = int(_sha256(token), 16)
        for index in range(64):
            bits[index] += 1 if digest >> index & 1 else -1
    value = 0
    for index, bit in enumerate(bits):
        if bit > 0:
            value |= 1 << index
    return value


def _hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _corpus() -> list[dict]:
    text = "linear equations move terms and divide by the coefficient"
    other = "photosynthesis converts light into stored chemical energy"
    rows = []
    for index, body, allow in (
        (1, text, True),
        (2, text, False),
        (3, other, True),
    ):
        rows.append(
            {
                "id": f"I{index}",
                "text": body,
                "allow": allow,
                "sha": _sha256(body),
                "minhash": _minhash(body),
                "bow": _bow(body),
                "simhash": _simhash(body),
            }
        )
    return rows


def _authorize(issuance: dict, request: dict) -> bool:
    if issuance["allow"] is False:
        return False
    if request["purpose"] not in issuance.get("purposes", {"tutoring"}):
        return False
    if request["redistribute"] and not issuance.get("redistribute", False):
        return False
    return True


def decide(records: list[dict], request: dict, attributed: set[str]) -> bool:
    if not attributed:
        return False
    chosen = [row for row in records if row["id"] in attributed]
    if len(chosen) != len(attributed):
        return False
    return all(_authorize(row, request) for row in chosen)


def _requests(records: list[dict]) -> list[dict]:
    """S1-S6. true_id is the issuance of the copy in hand. Oracle uses only that id."""
    text = records[0]["text"]
    other = records[2]["text"]
    light = text + " note"
    shuffled = " ".join(reversed(text.split()))
    return [
        {"name": "S1-allow", "text": text, "true_id": "I1", "purpose": "tutoring", "redistribute": False, "metadata": "I1", "mark": True, "legitimate": True},
        {"name": "S1-other-same-rights", "text": other, "true_id": "I3", "purpose": "tutoring", "redistribute": False, "metadata": "I3", "mark": True, "legitimate": True},
        {"name": "S2-denied-copy", "text": text, "true_id": "I2", "purpose": "tutoring", "redistribute": False, "metadata": "I2", "mark": True, "legitimate": False},
        {"name": "S2-allowed-copy", "text": text, "true_id": "I1", "purpose": "tutoring", "redistribute": False, "metadata": "I1", "mark": True, "legitimate": True},
        {"name": "S3-revoked-copy", "text": text, "true_id": "I2", "purpose": "tutoring", "redistribute": False, "metadata": "I2", "mark": True, "legitimate": False},
        {"name": "S4-redistribute", "text": text, "true_id": "I1", "purpose": "tutoring", "redistribute": True, "metadata": "I1", "mark": True, "legitimate": False},
        {"name": "S5-mixed", "text": text + " " + other, "true_id": "I1", "purpose": "tutoring", "redistribute": False, "metadata": "I1", "mark": True, "legitimate": True},
        {"name": "S6-metadata-missing-allow", "text": text, "true_id": "I1", "purpose": "tutoring", "redistribute": False, "metadata": "", "mark": True, "legitimate": True},
        {"name": "S6-metadata-missing-deny", "text": text, "true_id": "I2", "purpose": "tutoring", "redistribute": False, "metadata": "", "mark": True, "legitimate": False},
        {"name": "light-edit", "text": light, "true_id": "I1", "purpose": "tutoring", "redistribute": False, "metadata": "I1", "mark": True, "legitimate": True},
        {"name": "paraphrase-mark-dead", "text": shuffled, "true_id": "I1", "purpose": "tutoring", "redistribute": False, "metadata": "", "mark": False, "legitimate": True},
    ]


def _attribute(method: str, request: dict, records: list[dict]) -> set[str]:
    if method == "F0":
        digest = _sha256(request["text"])
        return {row["id"] for row in records if row["sha"] == digest}
    if method == "F1":
        sketch = _minhash(request["text"])
        return {row["id"] for row in records if row["minhash"] == sketch}
    if method == "F2":
        query = _bow(request["text"])
        scored = [( _bm25_score(query, row["bow"]), row["id"]) for row in records]
        best = max(score for score, _id in scored)
        if best <= 0:
            return set()
        return {row_id for score, row_id in scored if score == best}
    if method == "F5":
        return _attribute("F0", request, records)
    if method == "F6":
        sketch = _simhash(request["text"])
        return {row["id"] for row in records if _hamming(sketch, row["simhash"]) <= 8}
    if method == "F7":
        if not request["metadata"]:
            return set()
        return {request["metadata"]}
    if method == "W0":
        if request["mark"]:
            return {request["true_id"]}
        return set()
    if method == "W1":
        found = _attribute("F6", request, records)
        if request["mark"]:
            found |= {request["true_id"]}
        return found
    if method == "Oracle":
        return {request["true_id"]}
    raise KeyError(method)


def _evaluate(method: str, records: list[dict], requests: list[dict]) -> dict:
    unauthorized = 0
    unauthorized_total = 0
    false_reject = 0
    legitimate = 0
    correct = 0
    for request in requests:
        oracle = decide(records, request, {request["true_id"]})
        attributed = _attribute(method, request, records)
        # Issuance records carry purpose and redistribution limits.
        enriched = []
        for row in records:
            item = dict(row)
            item["purposes"] = {"tutoring"}
            item["redistribute"] = False
            enriched.append(item)
        allowed = decide(enriched, request, attributed)
        if allowed == oracle:
            correct += 1
        if request["legitimate"]:
            legitimate += 1
            if not allowed:
                false_reject += 1
        else:
            unauthorized_total += 1
            if allowed:
                unauthorized += 1
    return {
        "unauthorized_success": unauthorized / unauthorized_total,
        "false_reject": false_reject / legitimate,
        "utility": 1.0 - (false_reject / legitimate),
        "correct": correct,
        "unauthorized_hits": unauthorized,
    }


def _timed(method: str, records, requests, repeats: int = 50) -> float:
    start = time.perf_counter()
    for _ in range(repeats):
        _evaluate(method, records, requests)
    return (time.perf_counter() - start) * 1000.0 / repeats


def main() -> None:
    try:
        import sentence_transformers  # noqa: F401
        bge_present = True
    except Exception:
        bge_present = False
    records = _corpus()
    for row in records:
        row["purposes"] = {"tutoring"}
        row["redistribute"] = False
    requests = _requests(records)
    methods = ["F0", "F1", "F2", "F5", "F6", "F7", "W0", "W1", "Oracle"]
    scores = {name: _evaluate(name, records, requests) for name in methods}
    latency = {name: _timed(name, records, requests) for name in methods}
    deployable = ["F0", "F1", "F2", "F5", "F6", "F7"]
    # Strongest deployable: lowest unauthorized success, then highest utility.
    strongest = min(
        deployable,
        key=lambda name: (scores[name]["unauthorized_success"], -scores[name]["utility"], latency[name]),
    )
    base = scores[strongest]
    watermark = scores["W0"]
    security_delta = base["unauthorized_success"] - watermark["unauthorized_success"]
    decision_flips = 0
    for request in requests:
        enriched = records
        base_ids = _attribute(strongest, request, records)
        mark_ids = _attribute("W0", request, records)
        if decide(enriched, request, base_ids) != decide(enriched, request, mark_ids):
            decision_flips += 1
    scans = []
    for seed in range(5):
        rng = random.Random(seed)
        subset = [request for request in requests if rng.random() < 0.8]
        if not subset:
            subset = requests[:1]
        scans.append(
            {
                "seed": seed,
                "f7_unauth": _evaluate("F7", records, subset)["unauthorized_success"],
                "w0_unauth": _evaluate("W0", records, subset)["unauthorized_success"],
            }
        )
    assert scores["Oracle"]["unauthorized_success"] == 0
    assert security_delta == 0
    verdict = "STOP"
    summary = {
        "experiment": "X3",
        "base_sha": "893c6b3fe5e50d1526f2704ca3ae5ed555c4c609",
        "verdict": verdict,
        "counterexample": "same bytes issued twice, one grant revoked; fail-closed exact match already denies; ideal watermark does not reduce unauthorized success",
        "strongest_baseline": strongest,
        "safety_gain": {
            "metric": "unauthorized_success",
            "baseline": base["unauthorized_success"],
            "ours": watermark["unauthorized_success"],
            "delta": security_delta,
        },
        "utility_change": {
            "metric": "legitimate_utility",
            "baseline": base["utility"],
            "ours": watermark["utility"],
            "delta": watermark["utility"] - base["utility"],
        },
        "false_reject_rate": {"baseline": base["false_reject"], "ours": watermark["false_reject"]},
        "compute_overhead": {"baseline_ms": latency[strongest], "ours_ms": latency["W0"]},
        "literature_overlap": "pending-worker-E",
        "code_reuse": [],
        "dev_scan": True,
        "formal": False,
        "deterministic_baseline_violations": base["unauthorized_hits"],
        "deterministic_ours_violations": watermark["unauthorized_hits"],
        "candidate_is_standard_mechanism": True,
        "missing_dependency": False,
        "bge_blocked": not bge_present,
        "decision_flips_vs_strongest_deployable": decision_flips,
        "additional_correct": watermark["correct"] - base["correct"],
        "paths": ["experiments/parallel_x_20261124/x3_issuance/run.py"],
        "notes": (
            "STOP for watermark development. F3 and F4 are BLOCKED because sentence-transformers/BGE is not installed; no weights were downloaded. "
            f"Shared decision is fail-closed. decision_flips={decision_flips}. "
            "Flips are legitimate requests recovered when metadata is absent, not blocked attacks. "
            f"dev_scan={scans}"
        ),
        "scores": scores,
        "latency_ms": latency,
    }
    results = ROOT / "results"
    results.mkdir(parents=True, exist_ok=True)
    (results / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# X3 dev scan",
        "",
        "Semantics. S1: identical rights, either issuance may be used. S2: same bytes, only one issuance grants this subject. S3: the revoked issuance must not be used even though another issuance of the same bytes remains valid for someone else. S4: redistribution is a separate condition and is off. S5: a mix is allowed only when every attributed issuance allows it. S6: missing metadata is not evidence of a grant.",
        "",
        "The watermark payload is an issuance id. The allow rule lives only in the shared table.",
        "",
        "F3/F4: BLOCKED, BGE is not installed. No download.",
        "",
        f"Strongest deployable baseline: {strongest}. Ideal watermark unauthorized-success delta: {security_delta}. Decision flips: {decision_flips}.",
        "",
        "Verdict: STOP. Do not start a real watermark pilot from this scan.",
        "",
        "| method | unauthorized success | false reject | utility | correct | ms |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in methods:
        row = scores[name]
        lines.append(
            f"| {name} | {row['unauthorized_success']:.3f} | {row['false_reject']:.3f} | {row['utility']:.3f} | {row['correct']} | {latency[name]:.4f} |"
        )
    lines.append("")
    lines.append(summary["notes"])
    (ROOT / "RESULT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(verdict, "flips", decision_flips, "strongest", strongest)
    print(json.dumps({name: scores[name]["unauthorized_success"] for name in methods}))


if __name__ == "__main__":
    main()
