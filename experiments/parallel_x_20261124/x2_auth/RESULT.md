# X2 dynamic authorization and derived knowledge

Verdict: **STOP**

Base SHA: `893c6b3fe5e50d1526f2704ca3ae5ed555c4c609`

Formal experiment: false. Dev scan: true (5 seeds, not used for the verdict).

## Verdict

STOP. B2 (dynamic ACL with dependency propagation, rechecked at cache serve, future read, and queued execution) has zero unauthorized deliveries and executions on the deterministic cases, and it still allows every still-authorized request. B3 is the real ReleaseGate reserve plus commit recheck: it cancels an in-flight release of asset-a when with_policy_version bumps asset-a, including the owner's still-lawful in-flight release (false reject, fail closed on the epoch). The same recheck does not stop a summary that was registered as derived-a with a copied tutoring grant, because commit compares derived-a's own policy version. B0 keeps the T0 snapshot. B1 re-reads the grant but treats a derived object as uncontrolled data, so subject-r receives derived-a after revocation. B4 inherits a static confidentiality label and same-org clearance, so revocation and per-principal grants are invisible. The candidate cross_module_coordinator is not developed; it is B2. Dev-scan rates are illustrative only. Deterministic B2 violation_rate=0.000, task_success=1.000, false_reject=0.000. Dev-scan B2 violations=0/5.

## Four rights

Already-obtained knowledge is not a safety violation. S learns asset-a at T1;
reconstruction still reports that witness as completable after revocation, and
that probe is unscored (safe=False, counted_as_safety_violation=false).
Controlled cache, future read, and future execution are scored.

| Right | Unlawful events | B0 | B1 | B2 | B3 | B4 | ours |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| controlled_cache | 3 | 2 | 3 | 0 | 2 | 3 | 0 |
| future_read | 4 | 2 | 2 | 0 | 1 | 4 | 0 |
| future_execution | 3 | 3 | 2 | 0 | 2 | 3 | 0 |

## Deterministic metrics

| Method | Unauthorized delivery/execution | Task success | False reject | Mean decision latency ms |
| --- | ---: | ---: | ---: | ---: |
| B0 | 7/10 (0.700) | 9/12 (0.750) | 0.250 | 0.010 |
| B1 | 7/10 (0.700) | 12/12 (1.000) | 0.000 | 0.034 |
| B2 | 0/10 (0.000) | 12/12 (1.000) | 0.000 | 0.060 |
| B3 | 5/10 (0.500) | 9/12 (0.750) | 0.250 | 0.070 |
| B4 | 10/10 (1.000) | 9/12 (0.750) | 0.250 | 0.030 |
| ours | 0/10 (0.000) | 12/12 (1.000) | 0.000 | 0.060 |

Strongest fair baseline: **B2**.
Safety gain (baseline rate - ours rate): 0.0.
Utility change (ours task success - baseline): 0.0.
Overhead ratio: 1.0.

Latency is a fixed per-decision cost model in milliseconds, not wall-clock.

## Failing trace

B2 and ours deny every unlawful delivery and execution below.
An empty failed_baselines list means every baseline denied it; those rows are omitted.

- T5 revoke_between_reserve_and_commit future_execution subject-s -> asset-a purpose=tutoring failed=B0,B4 [B0=Y B1=N B2=N B3=N B4=Y ours=N]
- T5 queued_tool_on_derived future_execution subject-s -> derived-a purpose=tutoring failed=B0,B1,B3,B4 [B0=Y B1=Y B2=N B3=Y B4=Y ours=N]
- T4 cache_s_after_revoke controlled_cache subject-s -> derived-a purpose=tutoring failed=B0,B1,B3,B4 [B0=Y B1=Y B2=N B3=Y B4=Y ours=N]
- T4 r_reads_derived_after_revoke controlled_cache subject-r -> derived-a purpose=tutoring failed=B1,B4 [B0=N B1=Y B2=N B3=N B4=Y ours=N]
- T4 r_reads_derived_after_revoke future_read subject-r -> derived-a purpose=tutoring failed=B1,B4 [B0=N B1=Y B2=N B3=N B4=Y ours=N]
- T4 future_read_source_after_revoke future_read subject-s -> asset-a purpose=tutoring failed=B0,B4 [B0=Y B1=N B2=N B3=N B4=Y ours=N]
- T4 future_read_derived_after_revoke future_read subject-s -> derived-a purpose=tutoring failed=B0,B1,B3,B4 [B0=Y B1=Y B2=N B3=Y B4=Y ours=N]
- T4 r_reads_source_after_revoke future_read subject-r -> asset-a purpose=tutoring failed=B4 [B0=N B1=N B2=N B3=N B4=Y ours=N]
- T5 purpose_change future_execution subject-s -> derived-a purpose=tutoring failed=B0,B1,B3,B4 [B0=Y B1=Y B2=N B3=Y B4=Y ours=N]
- T4 purpose_change controlled_cache subject-s -> derived-a purpose=tutoring failed=B0,B1,B3,B4 [B0=Y B1=Y B2=N B3=Y B4=Y ours=N]

## Decision table

| Case | Right | Who | Object | Purpose | GT | B0 | B1 | B2 | B3 | B4 | ours |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lawful_tutoring | future_read | subject-s | asset-a | tutoring | allow | Y | Y | Y | Y | Y | Y |
| lawful_tutoring | future_read | subject-s | derived-a | tutoring | allow | Y | Y | Y | Y | Y | Y |
| lawful_tutoring | controlled_cache | subject-s | derived-a | tutoring | allow | Y | Y | Y | Y | Y | Y |
| lawful_tutoring | future_execution | subject-s | derived-a | tutoring | allow | Y | Y | Y | Y | Y | Y |
| lawful_tutoring | future_read | subject-t | asset-b | tutoring | allow | Y | Y | Y | Y | Y | Y |
| lawful_tutoring | future_read | owner-synth | asset-a | tutoring | allow | Y | Y | Y | Y | Y | Y |
| revoke_between_reserve_and_commit | future_execution | subject-s | asset-a | tutoring | deny | Y | N | N | N | Y | N |
| queued_tool_on_derived | future_execution | subject-s | derived-a | tutoring | deny | Y | Y | N | Y | Y | N |
| owner_inflight_after_epoch | future_execution | owner-synth | asset-a | tutoring | allow | Y | Y | Y | N | Y | Y |
| cache_s_after_revoke | controlled_cache | subject-s | derived-a | tutoring | deny | Y | Y | N | Y | Y | N |
| r_reads_derived_after_revoke | controlled_cache | subject-r | derived-a | tutoring | deny | N | Y | N | N | Y | N |
| r_reads_derived_after_revoke | future_read | subject-r | derived-a | tutoring | deny | N | Y | N | N | Y | N |
| future_read_source_after_revoke | future_read | subject-s | asset-a | tutoring | deny | Y | N | N | N | Y | N |
| future_read_derived_after_revoke | future_read | subject-s | derived-a | tutoring | deny | Y | Y | N | Y | Y | N |
| r_reads_source_after_revoke | future_read | subject-r | asset-a | tutoring | deny | N | N | N | N | Y | N |
| unrelated_grant_after_revoke | future_read | subject-t | asset-b | tutoring | allow | Y | Y | Y | Y | Y | Y |
| purpose_change | future_execution | subject-s | derived-a | tutoring | deny | Y | Y | N | Y | Y | N |
| purpose_change | controlled_cache | subject-s | derived-a | tutoring | deny | Y | Y | N | Y | Y | N |
| purpose_change | future_read | subject-s | asset-a | grading | allow | N | Y | Y | Y | N | Y |
| purpose_change | future_read | subject-s | derived-a | grading | allow | N | Y | Y | N | N | Y |
| purpose_change | controlled_cache | subject-s | derived-a | grading | allow | N | Y | Y | N | N | Y |
| purpose_change | future_read | subject-t | asset-b | tutoring | allow | Y | Y | Y | Y | Y | Y |

## Dev scan

Seeds 0..4, at most 6 subjects plus an owner, at most 4 assets, 5 rounds. Not formal.

| Method | Unauthorized rate | Task success | False reject |
| --- | ---: | ---: | ---: |
| B0 | 3/5 (0.600) | 1.000 | 0.000 |
| B1 | 5/5 (1.000) | 1.000 | 0.000 |
| B2 | 0/5 (0.000) | 1.000 | 0.000 |
| B3 | 3/5 (0.600) | 1.000 | 0.000 |
| B4 | 5/5 (1.000) | 1.000 | 0.000 |
| ours | 0/5 (0.000) | 1.000 | 0.000 |

## Code reuse

Called: AccessRegistry.is_authorized, AccessRegistry.with_policy_version, RegistryHolder,
ReleaseGate.evaluate_and_reserve, ReleaseGate.commit, check_release, ProtectedTarget, TargetRegistry.
Mirrored: ReleaseGate._still_authorized is the gate's own commit recheck, not reimplemented.

## Frozen rule

PASS_MIN_ABS_SAFETY_GAIN=0.1, MAX_UTILITY_DROP=0.1, MAX_OVERHEAD_RATIO=10.0.
STOP because the strongest fair baseline has zero deterministic safety violations
and the candidate does not change that security decision.
