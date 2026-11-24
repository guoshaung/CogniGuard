"""Frozen dev-scan acceptance rule.

The three thresholds below are the only cutoffs. They are not fit from
summaries, p-values, or a caller verdict. Formal experiments are out of
scope; see RUBRIC.md.
"""

PASS_MIN_ABS_SAFETY_GAIN = 0.10
MAX_UTILITY_DROP = 0.10
MAX_OVERHEAD_RATIO = 10.0


def _utility_drop(utility_change: dict) -> float:
    # Higher utility is better. A negative value is a gain, not a drop.
    baseline = float(utility_change["baseline"])
    ours = float(utility_change["ours"])
    return baseline - ours


def _overhead_ratio(compute_overhead: dict) -> float:
    baseline_ms = float(compute_overhead["baseline_ms"])
    ours_ms = float(compute_overhead["ours_ms"])
    # A non-positive baseline time does not form a finite ratio.
    if baseline_ms <= 0:
        return float("inf") if ours_ms > 0 else 0.0
    return ours_ms / baseline_ms


def score(summary: dict) -> str:
    """Return PASS, ANALYZE, STOP, or BLOCKED.

    Order is BLOCKED, then STOP, then PASS, else ANALYZE.
    ``verdict_claimed`` is ignored. A p-value cannot grant PASS.
    """
    if summary["missing_dependency"]:
        return "BLOCKED"

    baseline_violations = summary["deterministic_baseline_violations"]
    ours_violations = summary["deterministic_ours_violations"]
    safety_delta = float(summary["safety_gain"]["delta"])
    no_reproduced_violation = baseline_violations == 0
    no_movement = safety_delta == 0 and ours_violations == baseline_violations
    if no_reproduced_violation or no_movement:
        return "STOP"

    drop = _utility_drop(summary["utility_change"])
    ratio = _overhead_ratio(summary["compute_overhead"])
    within_limits = drop <= MAX_UTILITY_DROP and ratio < MAX_OVERHEAD_RATIO
    novel = summary["candidate_is_standard_mechanism"] is False
    eliminated = baseline_violations > 0 and ours_violations == 0
    practical_gain = safety_delta >= PASS_MIN_ABS_SAFETY_GAIN
    if baseline_violations > 0 and novel and within_limits and (eliminated or practical_gain):
        return "PASS"
    return "ANALYZE"
