#!/usr/bin/env python3
"""X5 dev scan: one synthetic bit versus observable control signals.

No model calls. Content is a constant redaction. The attacker never
receives content or the server-side query record.
"""

from __future__ import annotations

import json
from pathlib import Path

# Frozen. Do not retune.
PASS_MIN_ABS_SAFETY_GAIN = 0.10
MAX_UTILITY_DROP = 0.10
MAX_OVERHEAD_RATIO = 10.0

N_SUBJECTS = 10
SEEDS = (0, 1, 2, 3, 4)
CHANCE = 0.5
DEV_SCAN = True
FORMAL = False
BASE_SHA = "893c6b3fe5e50d1526f2704ca3ae5ed555c4c609"

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"

# Signals a deployer can omit without changing the answer the caller uses.
# degradation is a numeric field. Content itself stays the constant redaction,
# so this model has no quality channel. replanned is planner telemetry.
OPTIONAL_DISPLAY = frozenset({"degradation", "replanned"})
VISIBLE_KEYS = ("decision", "degradation", "tool", "replanned", "conflict")
PRODUCTIVE_TOOL = "tutor_retrieve"
CONSTANT_DECISION = "allow"
CONSTANT_TOOL = PRODUCTIVE_TOOL


def secret_bit(seed: int, subject: int) -> int:
    return (subject + seed) & 1


def redact_content(secret: int) -> str:
    # Content defense: the bit is not copied into the payload.
    del secret
    return "REDACTED"


def raw_control(secret: int, meter: dict) -> dict:
    """Content-defense control plane. The bit still picks the signals."""
    meter["steps"] += 1  # branch on the protected bit
    if secret == 1:
        signals = {
            "decision": "refuse",
            "degradation": 2,
            "tool": "redacted_template",
            "replanned": True,
            "conflict": "policy_conflict:sensitive_attribute",
        }
    else:
        signals = {
            "decision": "allow",
            "degradation": 0,
            "tool": PRODUCTIVE_TOOL,
            "replanned": False,
            "conflict": "",
        }
    meter["steps"] += len(VISIBLE_KEYS)
    return signals


def observe(signals: dict, keys: tuple[str, ...]) -> dict:
    return {key: signals[key] for key in keys}


def c1_behavior(raw: dict) -> dict:
    """Enforced shape. Degradation and replan still follow the raw policy."""
    return {
        "decision": CONSTANT_DECISION,
        "degradation": raw["degradation"],
        "tool": CONSTANT_TOOL,
        "replanned": raw["replanned"],
        "conflict": "",
    }


def serve(mode: str, seed: int, subject: int, secret: int, meter: dict, server_log: list) -> tuple[dict, dict]:
    """Return (attacker_view, enforced_behavior). Behavior is never shown as-is."""
    meter["steps"] += 1  # content redaction, both modes
    content = redact_content(secret)
    if str(secret) in content or content != "REDACTED":
        raise RuntimeError("content defense failed")
    raw = raw_control(secret, meter)
    if mode == "C0":
        behavior = observe(raw, VISIBLE_KEYS)
        visible = dict(behavior)
    elif mode == "C1":
        # Traditional shape: same allow/deny, same tool, no conflict string.
        behavior = c1_behavior(raw)
        visible = dict(behavior)
        meter["steps"] += 3  # override decision, override tool, blank conflict
        server_log.append(
            {
                "seed": seed,
                "subject": subject,
                "secret": secret,
                "query": "summarize_record",
                "stored_decision": raw["decision"],
                "shown": False,
            }
        )
        meter["steps"] += 1  # server-side query record, not returned
    elif mode == "C1_hide_optional":
        # Sketch only: do not display the two fields C1 left untouched.
        behavior = c1_behavior(raw)
        visible = {
            "decision": behavior["decision"],
            "tool": behavior["tool"],
            "conflict": behavior["conflict"],
        }
        meter["steps"] += 3
        meter["steps"] += 2  # drop degradation and replanned from the client view
        server_log.append(
            {
                "seed": seed,
                "subject": subject,
                "secret": secret,
                "query": "summarize_record",
                "stored_decision": raw["decision"],
                "degradation": behavior["degradation"],
                "replanned": behavior["replanned"],
                "shown": False,
            }
        )
        meter["steps"] += 1
    else:
        raise ValueError(mode)
    if "secret" in visible or "content" in visible:
        raise RuntimeError("attacker view includes a forbidden field")
    return visible, behavior


def useful(behavior: dict) -> bool:
    # Task utility of the enforced decision. Hiding a label does not change it.
    return (
        behavior["decision"] == "allow"
        and behavior["tool"] == PRODUCTIVE_TOOL
        and behavior["degradation"] == 0
    )


def worlds(mode: str, seed: int, subject: int) -> tuple[dict, dict]:
    """Attacker views for both secret values."""
    out = []
    for secret in (0, 1):
        visible, _behavior = serve(mode, seed, subject, secret, {"steps": 0}, [])
        out.append(visible)
    return out[0], out[1]


def leaking_fields(left: dict, right: dict) -> list[str]:
    keys = sorted(set(left) | set(right))
    return [key for key in keys if left.get(key) != right.get(key)]


def attack_success(mode: str, seed: int) -> float:
    """1.0 if the observation determines the bit, else 0.5 on ties.

    A subject whose two worlds differ is recovered by the matching template.
    A subject whose worlds match contributes a chance guess on a balanced bit.
    """
    recovered = 0
    guesses = 0
    for subject in range(N_SUBJECTS):
        low, high = worlds(mode, seed, subject)
        if low != high:
            recovered += 1
        else:
            guesses += 1
    return (recovered + CHANCE * guesses) / N_SUBJECTS


def condition_metrics(mode: str) -> dict:
    per_seed = []
    for seed in SEEDS:
        meter = {"steps": 0}
        server_log: list = []
        successes_bits = []
        utilities = []
        false_rejects = []
        for subject in range(N_SUBJECTS):
            secret = secret_bit(seed, subject)
            visible, behavior = serve(mode, seed, subject, secret, meter, server_log)
            successes_bits.append(secret)
            utilities.append(useful(behavior))
            false_rejects.append(secret == 0 and behavior["decision"] == "refuse")
            if mode == "C0":
                if server_log:
                    raise RuntimeError("C0 must not write the query record")
            else:
                if server_log[-1]["shown"] is not False:
                    raise RuntimeError("query record was shown")
                if "secret" in visible:
                    raise RuntimeError("secret returned to attacker")
        per_seed.append(
            {
                "seed": seed,
                "attack_success": attack_success(mode, seed),
                "utility": sum(utilities) / N_SUBJECTS,
                "false_reject_rate": sum(false_rejects) / max(1, sum(1 for b in successes_bits if b == 0)),
                "steps": meter["steps"],
                "n_secret_1": sum(successes_bits),
                "query_records": len(server_log),
            }
        )
    def mean(key: str) -> float:
        return sum(row[key] for row in per_seed) / len(per_seed)

    return {
        "per_seed": per_seed,
        "attack_success": mean("attack_success"),
        "utility": mean("utility"),
        "false_reject_rate": mean("false_reject_rate"),
        "steps": mean("steps"),
    }


def concrete_trace() -> dict:
    seed = 0
    rows = []
    for subject in (0, 1):
        secret = secret_bit(seed, subject)
        server_log: list = []
        visible, _behavior = serve("C1", seed, subject, secret, {"steps": 0}, server_log)
        rows.append(
            {
                "seed": seed,
                "subject": subject,
                "secret": secret,
                "attacker_sees": visible,
                "server_record_shown": server_log[0]["shown"],
                "server_record_has_secret": "secret" in server_log[0],
            }
        )
    low, high = worlds("C1", seed, 0)
    return {
        "gap": "GAP_OPTIONAL_DISPLAY_DEGRADATION_AND_REPLAN",
        "c1_fields_that_differ": leaking_fields(low, high),
        "rows": rows,
    }


def decide(c0: dict, c1: dict, leak_fields: list[str], utility_drop: float) -> str:
    if abs(c1["attack_success"] - CHANCE) <= 1e-12:
        return "STOP"
    safety_gain = c0["attack_success"] - c1["attack_success"]
    # Residual leak is only fields a deployer would not have to display.
    if leak_fields and set(leak_fields) <= OPTIONAL_DISPLAY:
        return "ANALYZE"
    if (
        safety_gain + 1e-12 >= PASS_MIN_ABS_SAFETY_GAIN
        and utility_drop <= MAX_UTILITY_DROP + 1e-12
    ):
        return "PASS"
    return "ANALYZE"


LITERATURE = [
    {
        "title": "Denials leak information: Simulatable auditing",
        "url": "https://cs.stanford.edu/people/kngk/papers/denialsLeakInformation-JCSS2013.pdf",
        "year": 2013,
        "overlaps": {
            "X1": {"level": "partial", "mechanism": "auditor decision depends on the composed query-answer history"},
            "X2": {"level": "partial", "mechanism": "prior exact answers, not revocation, change what a later denial reveals"},
            "X3": {"level": "low", "mechanism": "none; no watermark-versus-metadata result"},
            "X4": {"level": "low", "mechanism": "online query sequence, not a concurrent transaction"},
            "X5": {"level": "high", "mechanism": "simulatable auditing: allow/deny must be predictable without the secret"},
        },
    },
    {
        "title": "QuerySnout: Automating the Discovery of Attribute Inference Attacks against Query-Based Systems",
        "url": "https://arxiv.org/abs/2211.05249",
        "year": 2022,
        "overlaps": {
            "X1": {"level": "low", "mechanism": "attacks one QBS, not policy composition"},
            "X2": {"level": "low", "mechanism": "infers an attribute; no revocation of derived copies"},
            "X3": {"level": "low", "mechanism": "none; no watermark-versus-metadata result"},
            "X4": {"level": "low", "mechanism": "non-interactive query sets"},
            "X5": {"level": "partial", "mechanism": "attribute inference from answers; error text is noted only as a possible extension"},
        },
    },
    {
        "title": "Privacy Side Channels in Machine Learning Systems",
        "url": "https://arxiv.org/abs/2309.05610",
        "year": 2024,
        "overlaps": {
            "X1": {"level": "partial", "mechanism": "composing DP with deduplication or output filters can worsen privacy"},
            "X2": {"level": "low", "mechanism": "no revocation mechanism"},
            "X3": {"level": "low", "mechanism": "output filtering blocks verbatim text; not a watermark-versus-metadata comparison"},
            "X4": {"level": "partial", "mechanism": "shared cross-user query-filter state, not a transaction protocol"},
            "X5": {"level": "high", "mechanism": "output-filter and query-filter allow/block as a membership side channel"},
        },
    },
    {
        "title": "Security Policies and Security Models",
        "url": "https://cs.purdue.edu/homes/ninghui/readings/AccessControl/goguen_meseguer_82.pdf",
        "year": 1982,
        "overlaps": {
            "X1": {"level": "partial", "mechanism": "a policy is a set of noninterference assertions, including capability passing"},
            "X2": {"level": "partial", "mechanism": "capability dynamics are in the model; the opened text has no derived-data revocation theorem"},
            "X3": {"level": "low", "mechanism": "none; no watermark-versus-metadata result"},
            "X4": {"level": "low", "mechanism": "not a concurrency or transaction paper"},
            "X5": {"level": "high", "mechanism": "noninterference: high inputs must not change what another user sees"},
        },
    },
    {
        "title": "Language-Based Information-Flow Security",
        "url": "https://www.cs.cornell.edu/andru/papers/jsac/sm-jsac03.pdf",
        "year": 2003,
        "overlaps": {
            "X1": {"level": "high", "mechanism": "security-type checking composes when external signatures agree"},
            "X2": {"level": "partial", "mechanism": "declassification and downgrading; not revocation of derived copies"},
            "X3": {"level": "low", "mechanism": "none; no watermark-versus-metadata result"},
            "X4": {"level": "partial", "mechanism": "concurrent schedulers as covert channels, surveyed rather than a transaction design"},
            "X5": {"level": "high", "mechanism": "end-to-end noninterference and covert channels, including control flow"},
        },
    },
    {
        "title": "Dynamic Updating of Information-Flow Policies",
        "url": "http://www.cis.upenn.edu/~stevez/papers/HTHZ05.pdf",
        "year": 2005,
        "overlaps": {
            "X1": {"level": "partial", "mechanism": "a runtime hierarchy update changes which flows the composed policy allows"},
            "X2": {"level": "partial", "mechanism": "noninterference between updates under hierarchy revocation; history is forgotten rather than derivatives tracked"},
            "X3": {"level": "low", "mechanism": "none; no watermark-versus-metadata result"},
            "X4": {"level": "low", "mechanism": "tag-delayed policy update, not a data transaction"},
            "X5": {"level": "partial", "mechanism": "a policy test selects a visible branch; not tool-choice leakage"},
        },
    },
    {
        "title": "Logs and side channels",
        "url": "https://www.ideals.illinois.edu/items/128641",
        "year": 2023,
        "overlaps": {
            "X1": {"level": "low", "mechanism": "not a policy-composition result"},
            "X2": {"level": "low", "mechanism": "no derived-data revocation mechanism"},
            "X3": {"level": "low", "mechanism": "data-oblivious transcripts decouple secrets from logs; not watermark versus metadata"},
            "X4": {"level": "partial", "mechanism": "Termite concurrency side channel through audit-log order and timing"},
            "X5": {"level": "high", "mechanism": "Termite: implicit audit-log content supports membership inference after explicit redaction"},
        },
    },
    {
        "title": "Auditing without Leaks Despite Curiosity",
        "url": "https://arxiv.org/abs/2505.00665",
        "year": 2025,
        "overlaps": {
            "X1": {"level": "low", "mechanism": "one object semantics, not policy composition"},
            "X2": {"level": "partial", "mechanism": "max-register readers can learn prior values without an explicit read; the paper tries to block that"},
            "X3": {"level": "low", "mechanism": "none; no watermark-versus-metadata result"},
            "X4": {"level": "high", "mechanism": "wait-free auditable register: effective read and access log in one atomic step"},
            "X5": {"level": "partial", "mechanism": "one-time pad so readers cannot see other readers' audit records"},
        },
    },
    {
        "title": "AgentTell: Behavioural Side-Channel Leakage in Browser-Use Agents",
        "url": "https://arxiv.org/abs/2609.32915",
        "year": 2026,
        "overlaps": {
            "X1": {"level": "low", "mechanism": "not a policy-composition result"},
            "X2": {"level": "partial", "mechanism": "a secret retained from an earlier site changes a later action; no revocation"},
            "X3": {"level": "low", "mechanism": "none; no watermark-versus-metadata result"},
            "X4": {"level": "low", "mechanism": "sequential two-site tasks, not transactions"},
            "X5": {"level": "high", "mechanism": "secret-specific action versus a general action leaks the bit without content disclosure"},
        },
    },
    {
        "title": "AgentLeak: A Benchmark for Internal-Channel Privacy Leakage in Multi-Agent LLM Systems",
        "url": "https://arxiv.org/abs/2602.11510",
        "year": 2026,
        "overlaps": {
            "X1": {"level": "partial", "mechanism": "coordinator-worker composition adds channels an output audit misses"},
            "X2": {"level": "low", "mechanism": "no revocation mechanism"},
            "X3": {"level": "low", "mechanism": "none; no watermark-versus-metadata result"},
            "X4": {"level": "partial", "mechanism": "shared memory across agents, not a transaction protocol"},
            "X5": {"level": "high", "mechanism": "internal messages and memory leak after final-output sanitization"},
        },
    },
]


def main() -> None:
    if redact_content(0) != redact_content(1):
        raise RuntimeError("content depends on the bit")
    c0 = condition_metrics("C0")
    c1 = condition_metrics("C1")
    hidden = condition_metrics("C1_hide_optional")
    trace = concrete_trace()
    leak_fields = trace["c1_fields_that_differ"]
    utility_change = c1["utility"] - c0["utility"]
    utility_drop = max(0.0, -utility_change)
    overhead = c1["steps"] / c0["steps"]
    hide_overhead = hidden["steps"] / c0["steps"]
    safety_gain = c0["attack_success"] - c1["attack_success"]
    if overhead > MAX_OVERHEAD_RATIO or hide_overhead > MAX_OVERHEAD_RATIO:
        raise RuntimeError("overhead exceeded the frozen cap")
    verdict = decide(c0, c1, leak_fields, utility_drop)
    if verdict == "STOP":
        raise RuntimeError("STOP forbids a new algorithm, but a leak was still measured")
    # ANALYZE blocks PASS. The hide sketch is measured, not promoted.
    if verdict == "PASS":
        raise RuntimeError("PASS is not available for an optional-display leak")
    for row in c0["per_seed"] + c1["per_seed"] + hidden["per_seed"]:
        if row["n_secret_1"] != N_SUBJECTS // 2:
            raise RuntimeError("unbalanced secret bit")
    summary = {
        "experiment": "X5",
        "base_sha": BASE_SHA,
        "verdict": verdict,
        "counterexample": (
            "seed 0 subject 0 secret 0 C1 sees "
            "{decision:allow, degradation:0, tool:tutor_retrieve, replanned:false, conflict:''}; "
            "subject 1 secret 1 C1 sees "
            "{decision:allow, degradation:2, tool:tutor_retrieve, replanned:true, conflict:''}; "
            "allow/deny, tool, and conflict match, so the bit is read from degradation and replanned; "
            "the query record stays server-side with shown=false"
        ),
        "strongest_baseline": "C1_constant_allow_and_tool_no_conflict_hidden_query_record",
        "safety_gain": safety_gain,
        "utility_change": utility_change,
        "false_reject_rate": c1["false_reject_rate"],
        "compute_overhead": overhead,
        "literature_overlap": (
            "X5 high (simulatable auditing; filter allow/block; AgentTell action choice); "
            "X1 partial-to-high (security-type composition; filter composition side effects); "
            "X2 partial (noninterference between updates, not derived-copy revocation); "
            "X3 low (no watermark-versus-metadata source opened); "
            "X4 partial (auditable concurrent registers; Termite log ordering)"
        ),
        "code_reuse": "none",
        "dev_scan": DEV_SCAN,
        "formal": FORMAL,
        "paths": [
            "experiments/parallel_x_20261124/x5_behavior/run.py",
            "experiments/parallel_x_20261124/x5_behavior/RESULT.md",
            "experiments/parallel_x_20261124/x5_behavior/results/summary.json",
            "experiments/parallel_x_20261124/x5_behavior/results/literature.json",
        ],
        "notes": (
            "dev_scan only, 10 subjects, seeds 0-4, formal false. "
            f"C0 attack_success={c0['attack_success']} utility={c0['utility']} "
            f"false_reject={c0['false_reject_rate']} steps={c0['steps']}. "
            f"C1 attack_success={c1['attack_success']} utility={c1['utility']} "
            f"false_reject={c1['false_reject_rate']} steps={c1['steps']}. "
            f"C1 does not stop the leak. Differing fields={leak_fields}. "
            f"Hide-optional sketch attack_success={hidden['attack_success']} "
            f"utility_drop_vs_C1={c1['utility'] - hidden['utility']} "
            f"overhead_vs_C0={hide_overhead}. "
            "That sketch meets the numeric bar "
            f"(gain vs C1={c1['attack_success'] - hidden['attack_success']}, "
            f"utility drop 0 <= {MAX_UTILITY_DROP}) but is not PASS: "
            "the residual signals are fields a deployer would simply not display. "
            f"Frozen caps gain>={PASS_MIN_ABS_SAFETY_GAIN} drop<={MAX_UTILITY_DROP} "
            f"overhead<={MAX_OVERHEAD_RATIO}. "
            "Content is the constant REDACTED in every cell. "
            "No cogniguard or protection import. No model call. "
            "IEEE S&P 1988 composability page and the 2025 HOST Termite page did not return body text, so they are not cited. "
            "docs/literature_baseline_matrix.md RAG extraction rows were read in-repo and not re-opened; they are content-channel baselines, low overlap with X5."
        ),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (RESULTS / "literature.json").write_text(json.dumps(LITERATURE, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": verdict,
        "c1_stops_leak": abs(c1["attack_success"] - CHANCE) <= 1e-12,
        "citations": len(LITERATURE),
        "safety_gain": safety_gain,
        "utility_change": utility_change,
        "false_reject_rate": c1["false_reject_rate"],
        "compute_overhead": overhead,
        "c0_attack": c0["attack_success"],
        "c1_attack": c1["attack_success"],
        "hide_attack": hidden["attack_success"],
        "leak_fields": leak_fields,
    }, indent=2))


if __name__ == "__main__":
    main()
