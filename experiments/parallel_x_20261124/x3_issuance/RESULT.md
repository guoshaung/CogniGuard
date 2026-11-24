# X3 dev scan

Semantics. S1: identical rights, either issuance may be used. S2: same bytes, only one issuance grants this subject. S3: the revoked issuance must not be used even though another issuance of the same bytes remains valid for someone else. S4: redistribution is a separate condition and is off. S5: a mix is allowed only when every attributed issuance allows it. S6: missing metadata is not evidence of a grant.

The watermark payload is an issuance id. The allow rule lives only in the shared table.

F3/F4: BLOCKED, BGE is not installed. No download.

Strongest deployable baseline: F7. Ideal watermark unauthorized-success delta: 0.0. Decision flips: 1.

Verdict: STOP. Do not start a real watermark pilot from this scan.

| method | unauthorized success | false reject | utility | correct | ms |
|---|---:|---:|---:|---:|---:|
| F0 | 0.000 | 0.857 | 0.143 | 5 | 0.0217 |
| F1 | 0.000 | 0.857 | 0.143 | 5 | 0.1019 |
| F2 | 0.000 | 0.857 | 0.143 | 5 | 0.0523 |
| F5 | 0.000 | 0.857 | 0.143 | 5 | 0.0231 |
| F6 | 0.000 | 0.857 | 0.143 | 5 | 0.6211 |
| F7 | 0.000 | 0.286 | 0.714 | 9 | 0.0159 |
| W0 | 0.000 | 0.143 | 0.857 | 10 | 0.0173 |
| W1 | 0.000 | 0.714 | 0.286 | 6 | 0.6278 |
| Oracle | 0.000 | 0.000 | 1.000 | 11 | 0.0176 |

STOP for watermark development. F3 and F4 are BLOCKED because sentence-transformers/BGE is not installed; no weights were downloaded. Shared decision is fail-closed. decision_flips=1. Flips are legitimate requests recovered when metadata is absent, not blocked attacks. dev_scan=[{'seed': 0, 'f7_unauth': 0.0, 'w0_unauth': 0.0}, {'seed': 1, 'f7_unauth': 0.0, 'w0_unauth': 0.0}, {'seed': 2, 'f7_unauth': 0.0, 'w0_unauth': 0.0}, {'seed': 3, 'f7_unauth': 0.0, 'w0_unauth': 0.0}, {'seed': 4, 'f7_unauth': 0.0, 'w0_unauth': 0.0}]
