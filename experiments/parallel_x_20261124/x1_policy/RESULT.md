# X1 dev scan

Formal experiment: no. Thresholds were set before the run and were not changed.

Counterexample: one candidate releases profile records p2 and p4 together.
Each record is allowed by its own module. Deny-overrides does not fire.
Dependency taint does not fire, because neither input is denied.
check_release refuses the candidate because the witness is complete.

A cross-principal case does the same: A already holds p2, B asks for p4.

Verdict: STOP. Do not add a coordination algorithm. Call the existing gate.

| method | violation rate | task success | false reject | ms |
|---|---:|---:|---:|---:|
| B0 | 1.000 | 1.000 | 0.000 | 0.0001 |
| B1 | 0.667 | 1.000 | 0.000 | 0.0001 |
| B2 | 0.667 | 1.000 | 0.000 | 0.0005 |
| B3 | 0.667 | 1.000 | 0.000 | 0.0003 |
| B4 | 0.667 | 1.000 | 0.000 | 0.0003 |
| gate | 0.000 | 1.000 | 0.000 | 0.0022 |

STOP for a new coordinator. B4 taint does not see a witness whose members are each allowed. The existing check_release already refuses that candidate. utility_drop=0.000 overhead_ratio=6.246 dev_scan_b4_misses=[0, 1, 0, 1, 0] dev_scan_gate_catches=[0, 1, 0, 1, 0]
