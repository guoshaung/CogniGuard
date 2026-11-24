# Acceptance rubric

This is the dev-scan rule. Formal experiments are not frozen by this file. Practical effect is required.

`score.py` screens one candidate summary during development. It does not preregister a formal experiment, freeze a paper threshold, or score any other run. Do not retune the constants from measured summaries, reported p-values, or `verdict_claimed`.

## Frozen constants

These assignments in `score.py` sit above every scoring function:

- `PASS_MIN_ABS_SAFETY_GAIN = 0.10`
- `MAX_UTILITY_DROP = 0.10`
- `MAX_OVERHEAD_RATIO = 10.0`

A statistically significant but tiny effect is not a pass. A caller claim of `p<0.05` does not change the verdict.

## Inputs

The summary carries `verdict_claimed` (ignored), `safety_gain` (`baseline`, `ours`, `delta`), `utility_change` (`baseline`, `ours`, `delta`), `compute_overhead` (`baseline_ms`, `ours_ms`), `deterministic_baseline_violations`, `deterministic_ours_violations`, `candidate_is_standard_mechanism`, and `missing_dependency`.

Utility drop is `utility_change.baseline - utility_change.ours`. Higher utility is better, so an improvement is not a drop. The safety gate reads `safety_gain.delta`, not a p-value. Overhead ratio is `ours_ms / baseline_ms` and must be strictly under 10. If `baseline_ms` is not positive, a positive `ours_ms` has no finite ratio and misses the cap; zero over zero does not.

## Decision order

1. **BLOCKED** if `missing_dependency` is true. This wins over STOP.
2. **STOP** if deterministic baseline violations are 0, or if the safety-gain delta is 0 and our violation count equals the baseline count. An unreproduced baseline stops even when the caller reports a rate gain.
3. **PASS** if baseline violations are positive, the candidate is not a standard mechanism, the utility drop is at most 0.10, and the overhead ratio is strictly under 10, and either reproduced violations fall to 0 or the safety-gain delta is at least 0.10.
4. **ANALYZE** is the residual: a real violation remains unsolved, the gain is below 0.10, a utility or overhead limit is missed, or novelty fails. A standard lock or database transaction that fixes a race is not PASS.

Wiping out every reproduced deterministic violation can PASS even when the reported rate delta is below 0.10. A violation-rate drop of 0.01 that leaves violations, including one labeled `p<0.05`, cannot PASS. A real safety fix with a utility drop of 0.40 cannot PASS.

## Scope

This file is only the dev scan. Formal experiment protocols and their results are not frozen here.
