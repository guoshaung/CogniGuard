# CG V3.1 Execution Contract

## Contract boundary

`ActionPlan.allowed_payload` is the only payload that the experimental executor may return. It contains separate `student_context` and `teacher_resource` objects plus the authorized actions and projected costs. The executor does not receive a second path to the complete student context or teacher resource.

## Deterministic sequence

1. Composer or baseline policy creates an `ActionPlan`.
2. The adapter materializes a structured allowed payload from the selected actions.
3. The ledger projects both independent budgets; the adapter records a reservation equal to the projection when it fits the remaining budget.
4. The executor returns only the allowed payload. A supplied payload with unapproved fields, raw resource keys, or unapproved chunks is rejected.
5. The adapter measures actual disclosed student fields, resource chunks, return mode, verbatim ratio, and watermark state.
6. Actual cost is checked against projected cost and remaining budget. Budget-Only and Full fall back deterministically to `refuse + audit_escalation` when the output cannot fit; Static may record its baseline budget violation but still receives a bounded payload.
7. Only actual measured cost is committed to the corresponding ledger. Privacy and copyright are committed independently.
8. Output violation or deterministic fallback produces an empty rolled-back disclosure and is recorded in the audit record.

## Accounting fields

Every V3.1 audit record contains `projected_*_cost`, `reserved_*_cost`, `actual_*_disclosure`, `privacy_cost`/`copyright_cost`, and `committed_*_cost`. The old V3.0 result directory is never rewritten.

## Copyright enforcement

- `original` exposes explicit request chunks with `verbatim_ratio=1.0`.
- `controlled_excerpt` exposes at most the first chunk and a bounded verbatim ratio.
- `summary` exposes no chunks and carries only a bounded summary field.
- `degrade` exposes a bounded metadata/chunk payload, never the complete `CR_t` object.
- Watermark actions record `watermark_applied`; the executor does not silently return an unmarked original resource.

This contract is an experiment adapter. It does not replace the production classroom path, `server.py`, the old orchestrator, or the formal Teaching Agent.
