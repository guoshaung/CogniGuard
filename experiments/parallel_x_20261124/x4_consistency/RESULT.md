# X4 state consistency

Verdict: **ANALYZE**.
Base SHA: `893c6b3fe5e50d1526f2704ca3ae5ed555c4c609`.
dev_scan: true. formal: false.
Strongest baseline: `L1`.
Counterexample (unsafe under L0, L1, and L2): `duplicate_event, retry_after_commit`.

L0, L1, and L2 are standard controls, not a new mechanism.
L0 is a process-global lock around decide-and-commit.
L1 is one stdlib sqlite3 transaction (`BEGIN IMMEDIATE`, rollback).
L2 is optimistic concurrency control on a monotonic policy version.
The candidate `event_key` only adds a unique event identity to L1.
It is a small variant of L1, so it is not claimed as a new mechanism.

## Deterministic cases

| Method | Case | Safety violation | Detail |
| --- | --- | --- | --- |
| L0 | witness_race | no | delivered_requests=1 |
| L0 | stale_policy_version | no | unauthorized |
| L0 | revoke_commit_race | no | revoke_first_wrote=False;commit_first_wrote=True |
| L0 | duplicate_event | yes | delivered_rows=2 |
| L0 | retry_after_commit | yes | first=ok;second=ok;rows=2 |
| L0 | partial_commit | yes | delivered_after_abort=1 |
| L0 | divergent_grant | yes | two stale caches committed |
| L1 | witness_race | no | delivered_requests=1 |
| L1 | stale_policy_version | no | unauthorized |
| L1 | revoke_commit_race | no | revoke_first_wrote=False;commit_first_wrote=True |
| L1 | duplicate_event | yes | delivered_rows=2 |
| L1 | retry_after_commit | yes | first=ok;second=ok;rows=2 |
| L1 | partial_commit | no | delivered_after_abort=0 |
| L1 | divergent_grant | no | left=unauthorized;right=unauthorized |
| L2 | witness_race | yes | both delivered |
| L2 | stale_policy_version | no | version_mismatch |
| L2 | revoke_commit_race | no | revoke_first_wrote=False;commit_first_wrote=True |
| L2 | duplicate_event | yes | delivered_rows=2 |
| L2 | retry_after_commit | yes | first=ok;second=ok;rows=2 |
| L2 | partial_commit | yes | delivered_after_abort=1 |
| L2 | divergent_grant | no | left=version_mismatch;right=version_mismatch |
| event_key | witness_race | no | delivered_requests=1 |
| event_key | stale_policy_version | no | unauthorized |
| event_key | revoke_commit_race | no | revoke_first_wrote=False;commit_first_wrote=True |
| event_key | duplicate_event | no | delivered_rows=1 |
| event_key | retry_after_commit | no | first=ok;second=replay;rows=1 |
| event_key | partial_commit | no | delivered_after_abort=0 |
| event_key | divergent_grant | no | left=unauthorized;right=unauthorized |

## Metrics

| Method | Violation rate | False-reject rate | Mean latency (s) | Dev witness violation rate |
| --- | --- | --- | --- | --- |
| L0 | 0.571 | 0.000 | 0.000026 | 0.000 |
| L1 | 0.286 | 0.000 | 0.002017 | 0.000 |
| L2 | 0.571 | 0.000 | 0.000029 | 1.000 |
| event_key | 0.000 | 0.000 | 0.001919 | 0.000 |

Safety gain of event_key over L1: 0.286.
Utility change (serial delivery rate): 0.000.
False-reject rate reported in summary.json: 0.000.
Compute overhead (event_key / strongest, or strongest / fastest if STOP): 0.951.
Numeric PASS gates met: True.
PASS also requires the candidate not be a standard lock, transaction, or small variant of L0-L2.

Safety gain uses the seven deterministic cases. A case counts once.
False-reject rate is the share of serial authorized single-unit releases that were denied.
Those serial releases do not complete a witness. Duplicate replay that keeps one delivered row is not a false reject.
Dev scan: 5 seeds, 8 subjects, 4 assets, one complementary pair per asset.
The L2 pair reads both snapshots before either commit, so the version check is not saved by an accidental serial order.

## ReleaseGate observation

The gate ran on the in-memory store. It is not scored as L0, L1, or L2.

```json
{
  "import": "ok",
  "partial_commit": {
    "allowed": true,
    "delivered_rows": 1,
    "raised": true
  },
  "ran": true,
  "retry_delivered_rows": 2,
  "stale_policy_version_commit_returned": false,
  "store": "in-memory",
  "two_stores": {
    "both_committed": true,
    "logical_authorized": false
  },
  "witness_race": {
    "both_committed": false,
    "final_unsafe": false,
    "outcomes": [
      {
        "allowed": false,
        "committed": false,
        "reason": "reconstruction"
      },
      {
        "allowed": true,
        "committed": true,
        "reason": "ok"
      }
    ]
  }
}
```

## E9/E10

BLOCKED: no frozen E9/E10 definition in this checkout.

## Notes

Receipt state for L0, L2, and the ReleaseGate observation is an in-memory store with reserve/commit/cancel/holders_of/release_section. DisclosureStore was not opened and MySQL was not started. L0 is one process lock around decide-and-commit, with no rollback and no event identity; the two case-6 processes do not share that lock. L1 is one stdlib sqlite3 BEGIN IMMEDIATE transaction that re-reads policy and receipts, then commits or rolls back. Its receipt identity is a surrogate receipt_id, the same kind of identity DisclosureStore uses, not an event key. L2 checks one shared monotonic policy version at commit and does not lock or roll back a multi-receipt write. Shared failures: ['duplicate_event', 'retry_after_commit']. Candidate event_key is L1 plus UNIQUE(event_id, resource_id, unit_id) and an in-transaction replay check. That is a small variant of L1, not a new mechanism, so the verdict is ANALYZE when that residual is real. numeric_thresholds_met=True. dev scan 5 seeds, 8 subjects, 4 assets. formal=false. E9/E10: no frozen definition in this checkout.
