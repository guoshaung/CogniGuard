# Reconciliation of late Worker B and Worker C results

Dev scan only. Base SHA `893c6b3fe5e50d1526f2704ca3ae5ed555c4c609`. No production file was edited. Thresholds were not refit.

Worker B reported X1 PASS after the first table. Worker C reported X3 ANALYZE. Both scripts were re-executed against the contract: `check_release` is reused, not renamed, and every X3 method shares one decision function.

## X1

Worker script: `/Users/MBP/.grok/worktrees/cogniguard-cogniguard/subagent-01a20c49-29d2-7e30-b1ff-6dda8a04b8e5/experiments/parallel_x_20261124/x1_policy/run.py`.

Their pooled B4 violation rate is 0.1126 and their batch ban (`joint_commit`) reaches 0, with benign success 1.0000 to 0.9053 and overhead ratio 1.74 against B4. That comparison omits the in-repository gate.

Added baselines, same tasks and `check_release`:

- `serial_gate`: one request at a time, recipient history included, same predicate as `ReleaseGate._coalition_allows`.
- `snapshot_gate`: a parallel batch is judged against the pre-batch holdings, then committed together.

Deterministic schedules (simultaneous, sequential, multi-round, cross-principal), 4 sessions:

| method | violations | violation rate | benign success | joint sessions |
| --- | ---: | ---: | ---: | ---: |
| B4 | 8 | 0.1311 | 1.0000 | 4/4 |
| joint_commit | 0 | 0.0000 | 0.9000 | 0/4 |
| serial_gate | 0 | 0.0000 | 0.9000 | 0/4 |
| snapshot_gate | 1 | 0.0164 | 0.9250 | 1/4 |

`joint_commit` and `serial_gate` made the same delivery decisions on all 4 sessions.

Dev scan, 5 seeds, round order shuffled:

| method | violations | violation rate | benign success | joint seeds |
| --- | ---: | ---: | ---: | ---: |
| B4 | 9 | 0.1000 | 1.0000 | 5/5 |
| joint_commit | 0 | 0.0000 | 0.9091 | 0/5 |
| serial_gate | 0 | 0.0000 | 0.5455 | 0/5 |
| snapshot_gate | 0 | 0.0000 | 0.5455 | 0/5 |

Decisions matched the serial gate on 1 of 5 seeds. On seed 0 the batch ban misses only `u_test`. The serial gate had already released the test result, so it then refuses the aggregate asks (`u_agg`, `u_agg2`, `u_agg3`, `u_pair`, `u_pair2`, `u_pair3`). Both stay at zero reconstruction violations.

Safety gain against the serial gate is 0. The dev utility gap is which endorsed witness piece is withheld when the schedule order is known in advance. That is not a new safety coordinator. Verdict remains STOP. No upper-layer mechanism was added.

The one snapshot violation is the simultaneous batch committing three individually safe pieces. The in-process gate already serializes that case. Cross-process visibility stays with X4.

## X3

Worker script: `/Users/MBP/.grok/worktrees/cogniguard-cogniguard/subagent-01a20c49-29d2-7e30-b1ff-6de9760b7b95/experiments/parallel_x_20261124/x3_issuance/run.py`.

Their `decide` allows a request when any attributed issuance authorizes it. Under that rule F2 unauthorized success is 0.40 and W1 is 0.00, with overhead ratio 15.60 against F2, so their own gate is ANALYZE. F5 and F7 already have unauthorized success 0 in that run. F3 and F4 stay BLOCKED. No BGE weights were downloaded.

Re-scored with the shared fail-closed rule (every attributed issuance must authorize; empty attribution denies). Oracle labels did not move, because each request has one true issuance id.

Unauthorized success is 0 for F0, F1, F2, F5, F6, F7, W0, W1, and Oracle (120 requests, 5 seeds, 24 cases).

| method | utility | false reject | correct |
| --- | ---: | ---: | ---: |
| F5 | 0.4286 | 0.5714 | 80/120 |
| F7 | 0.3571 | 0.6429 | 75/120 |
| W0 | 0.7143 | 0.2857 | 100/120 |
| W1 | 0.7857 | 0.2143 | 105/120 |

W0 versus F7 flips five logical cases (`s1-same-perm-meta`, `s2-other-grantee`, `s4-teach-read`, `s3-live-copy`, `s6-external-copy`). Each oracle label is allow. The ideal mark still carries the true issuance id after metadata and the receipt are removed. That is a utility recovery on a channel the instruction does not treat as a watermark security gain. Real watermark tests were not started. Verdict remains STOP.
