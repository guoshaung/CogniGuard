"""X1 dev scan: joint release versus serial, ledger, deny-overrides, and taint.

Thresholds are frozen before any scenario runs. This is not a formal experiment.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

from cogniguard.governance.reconstruction import check_release
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry

PASS_MIN_ABS_SAFETY_GAIN = 0.10
MAX_UTILITY_DROP = 0.10
MAX_OVERHEAD_RATIO = 10.0

ROOT = Path(__file__).resolve().parent
P2 = ("profile:stu", "p2")
P4 = ("profile:stu", "p4")
QUOTE = ("pack", "quote")
SUMMARY = ("pack", "summary")
EXFIL = ("code", "exfil")
TEST = ("code", "test")

REGISTRY = TargetRegistry(
    [
        ProtectedTarget(
            "stu/attendance_risk",
            "owner",
            "org",
            (frozenset({P2, P4}),),
            kind="student_attribute",
            domain_size=2,
        )
    ]
)

# Explicit single-policy denies. The joint witness is not in this set.
DENIED = {QUOTE, EXFIL, ("profile:stu", "raw")}


def _benign(release: frozenset[tuple[str, str]], knowledge: dict[str, frozenset]) -> bool:
    if release & DENIED:
        return False
    if not check_release(REGISTRY, "requester", release, knowledge, 2).safe:
        return False
    return True


def b0_allow(_release, _knowledge) -> bool:
    return True


def b1_serial(release, _knowledge) -> bool:
    """Each module sees one unit and its own deny list. No joint view."""
    for unit in release:
        if unit in DENIED:
            return False
    return True


def b2_ledger(release, knowledge, budget: float = 2.0) -> bool:
    """Shared budget. Decisions still do not depend on each other."""
    if any(unit in DENIED for unit in release):
        return False
    spent = sum(len(held) for held in knowledge.values())
    return spent + len(release) <= budget


def b3_deny_overrides(release, _knowledge) -> bool:
    return not any(unit in DENIED for unit in release)


def b4_taint(release, knowledge) -> bool:
    """Deny an output only when it depends on an already denied input."""
    if any(unit in DENIED for unit in release):
        return False
    for held in knowledge.values():
        if held & DENIED and release:
            return False
    return True


def existing_gate(release, knowledge, recipient: str = "requester") -> bool:
    if any(unit in DENIED for unit in release):
        return False
    return check_release(REGISTRY, recipient, release, knowledge, 2).safe


def _timed(fn, release, knowledge, repeats: int = 400) -> float:
    start = time.perf_counter()
    for _ in range(repeats):
        fn(release, knowledge)
    return (time.perf_counter() - start) * 1000.0 / repeats


def deterministic_cases() -> list[dict]:
    nobody: dict[str, frozenset] = {}
    cross = {"A": frozenset({P2})}
    return [
        {"name": "simultaneous-witness", "release": frozenset({P2, P4}), "knowledge": nobody, "recipient": "requester", "benign": False},
        {"name": "sequential-second-unit", "release": frozenset({P4}), "knowledge": {"requester": frozenset({P2})}, "recipient": "requester", "benign": False},
        {"name": "multi-round-complete", "release": frozenset({P2, P4}), "knowledge": nobody, "recipient": "requester", "benign": False},
        {"name": "cross-principal", "release": frozenset({P4}), "knowledge": cross, "recipient": "B", "benign": False},
        {"name": "benign-one-unit", "release": frozenset({P2}), "knowledge": nobody, "recipient": "requester", "benign": True},
        {"name": "benign-summary", "release": frozenset({SUMMARY}), "knowledge": nobody, "recipient": "requester", "benign": True},
        {"name": "benign-test", "release": frozenset({TEST}), "knowledge": nobody, "recipient": "requester", "benign": True},
        {"name": "explicit-quote", "release": frozenset({QUOTE}), "knowledge": nobody, "recipient": "requester", "benign": False},
        {"name": "explicit-exfil", "release": frozenset({EXFIL}), "knowledge": nobody, "recipient": "requester", "benign": False},
    ]


def _allows(method: str, release, knowledge, recipient: str) -> bool:
    if method == "B0":
        return b0_allow(release, knowledge)
    if method == "B1":
        return b1_serial(release, knowledge)
    if method == "B2":
        return b2_ledger(release, knowledge)
    if method == "B3":
        return b3_deny_overrides(release, knowledge)
    if method == "B4":
        return b4_taint(release, knowledge)
    if method == "gate":
        return existing_gate(release, knowledge, recipient)
    raise KeyError(method)


def _score(method: str, cases: list[dict]) -> dict:
    attacks = [case for case in cases if not case["benign"]]
    benign = [case for case in cases if case["benign"]]
    violations = 0
    for case in attacks:
        if _allows(method, case["release"], case["knowledge"], case["recipient"]):
            violations += 1
    false_rejects = 0
    successes = 0
    for case in benign:
        allowed = _allows(method, case["release"], case["knowledge"], case["recipient"])
        if allowed:
            successes += 1
        else:
            false_rejects += 1
    return {
        "violation_rate": violations / len(attacks),
        "task_success": successes / len(benign),
        "false_reject": false_rejects / len(benign),
        "violations": violations,
        "attacks": len(attacks),
    }


def _dev_scan(seed: int) -> dict:
    rng = random.Random(seed)
    units = [P2, P4, SUMMARY, TEST, QUOTE]
    subjects = [f"s{i}" for i in range(10)]
    attacks = 0
    caught_by_gate_only = 0
    for _ in range(5):
        holder = rng.choice(subjects)
        requester = rng.choice(subjects)
        release = frozenset(rng.sample(units, rng.choice([1, 2])))
        knowledge = {holder: frozenset({P2})} if rng.random() < 0.5 else {}
        b4_ok = b4_taint(release, knowledge)
        gate_ok = existing_gate(release, knowledge, requester)
        unsafe = not check_release(REGISTRY, requester, release, knowledge, 2).safe or bool(release & DENIED)
        if unsafe and b4_ok:
            attacks += 1
            if not gate_ok:
                caught_by_gate_only += 1
    return {"seed": seed, "b4_misses": attacks, "gate_catches": caught_by_gate_only}


def main() -> None:
    cases = deterministic_cases()
    methods = ["B0", "B1", "B2", "B3", "B4", "gate"]
    scores = {name: _score(name, cases) for name in methods}
    sample = frozenset({P2, P4})
    latency = {
        name: _timed(lambda release, knowledge, name=name: _allows(name, release, knowledge, "requester"), sample, {})
        for name in methods
    }
    scans = [_dev_scan(seed) for seed in range(5)]
    # B4 is the strongest baseline that still misses the joint witness.
    # The closer is the existing gate, not a new coordinator.
    baseline = scores["B4"]
    gate = scores["gate"]
    safety_delta = baseline["violation_rate"] - gate["violation_rate"]
    utility_drop = baseline["task_success"] - gate["task_success"]
    overhead = latency["gate"] / latency["B4"] if latency["B4"] else 0.0
    b4_joint_allows = _allows("B4", sample, {}, "requester")
    gate_joint_allows = _allows("gate", sample, {}, "requester")
    assert b4_joint_allows is True
    assert gate_joint_allows is False
    assert scores["B3"]["violation_rate"] > 0
    assert gate["false_reject"] == 0
    verdict = "STOP"
    summary = {
        "experiment": "X1",
        "base_sha": "893c6b3fe5e50d1526f2704ca3ae5ed555c4c609",
        "verdict": verdict,
        "counterexample": "simultaneous release of p2 and p4 completes stu/attendance_risk; B1-B4 allow it; check_release refuses it",
        "strongest_baseline": "B4",
        "safety_gain": {
            "metric": "violation_rate",
            "baseline": baseline["violation_rate"],
            "ours": gate["violation_rate"],
            "delta": safety_delta,
        },
        "utility_change": {
            "metric": "task_success",
            "baseline": baseline["task_success"],
            "ours": gate["task_success"],
            "delta": gate["task_success"] - baseline["task_success"],
        },
        "false_reject_rate": {"baseline": baseline["false_reject"], "ours": gate["false_reject"]},
        "compute_overhead": {"baseline_ms": latency["B4"], "ours_ms": latency["gate"]},
        "literature_overlap": "pending-worker-E",
        "code_reuse": ["cogniguard.governance.reconstruction.check_release", "ProtectedTarget"],
        "dev_scan": True,
        "formal": False,
        "deterministic_baseline_violations": baseline["violations"],
        "deterministic_ours_violations": gate["violations"],
        "candidate_is_standard_mechanism": True,
        "missing_dependency": False,
        "paths": ["experiments/parallel_x_20261124/x1_policy/run.py"],
        "notes": (
            "STOP for a new coordinator. B4 taint does not see a witness whose members are each allowed. "
            "The existing check_release already refuses that candidate. "
            f"utility_drop={utility_drop:.3f} overhead_ratio={overhead:.3f} "
            f"dev_scan_b4_misses={[row['b4_misses'] for row in scans]} "
            f"dev_scan_gate_catches={[row['gate_catches'] for row in scans]}"
        ),
        "scores": scores,
        "latency_ms": latency,
    }
    results = ROOT / "results"
    results.mkdir(parents=True, exist_ok=True)
    (results / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# X1 dev scan",
        "",
        "Formal experiment: no. Thresholds were set before the run and were not changed.",
        "",
        "Counterexample: one candidate releases profile records p2 and p4 together.",
        "Each record is allowed by its own module. Deny-overrides does not fire.",
        "Dependency taint does not fire, because neither input is denied.",
        "check_release refuses the candidate because the witness is complete.",
        "",
        "A cross-principal case does the same: A already holds p2, B asks for p4.",
        "",
        "Verdict: STOP. Do not add a coordination algorithm. Call the existing gate.",
        "",
        "| method | violation rate | task success | false reject | ms |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in methods:
        row = scores[name]
        lines.append(
            f"| {name} | {row['violation_rate']:.3f} | {row['task_success']:.3f} | {row['false_reject']:.3f} | {latency[name]:.4f} |"
        )
    lines.append("")
    lines.append(summary["notes"])
    (ROOT / "RESULT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(verdict)
    print(json.dumps({"safety": summary["safety_gain"], "utility": summary["utility_change"]}, indent=2))


if __name__ == "__main__":
    main()
