# Interface contract for the 2026-11-24 parallel scan

Dev scan only. Formal thresholds are not frozen here. Base SHA `893c6b3fe5e50d1526f2704ca3ae5ed555c4c609` on `dev/confidential-secrets`.

## What already exists and must be reused, not renamed

- `AccessRegistry.is_authorized(principal, resource, purpose, acting_org, now)` allows the owner, or a grant whose purpose and `policy_version` match the current ownership. Expiry is `now >= expires_at`. `org_of` is not an authorization API. `with_policy_version` returns a new registry. `RegistryHolder.replace` publishes it.
- `ReleaseGate.evaluate_and_reserve` authorizes, runs `check_release` when a target registry and `coalition_k` are set, then reserves. `commit(decision, now)` cancels every receipt and returns false when the policy version changed or `is_authorized` fails. That is the versioned commit recheck (X2 B3, X4 L2).
- `check_release` fails closed when any witness can be finished by a coalition of size at most k that includes the recipient. Knowledge is `holders_of` on reserved and delivered receipts.
- Student attributes and teaching assets already share one `TargetRegistry` and one `ReleaseGate` (`protection/student_profile/src/fopd/secret_targets.py`).
- `DisclosureStore` is MySQL. This scan must not start a server. In-memory receipts are labeled as such.

## What this scan must not call a contribution

Global lock, SQLite transaction, optimistic version check, deny-overrides, label inheritance, and exact metadata lookup are baselines. A PASS requires a safety hole those baselines leave, closed by something that is not a rename of them.

## Frozen dev-scan rule

`PASS_MIN_ABS_SAFETY_GAIN = 0.10`, `MAX_UTILITY_DROP = 0.10`, `MAX_OVERHEAD_RATIO = 10`. A 0.01 drop is not PASS. Baseline already safe means STOP. Missing local dependency means BLOCKED, with no download and no paid call.

## Out of scope for this checkout

No frozen E9 or E10 protocol is in this checkout or in the local branch list (`exp/e5-synthetic`, `exp/e6-eedi`, `exp/e7-sumleaks`, `exp/e3b2-paraphrase`). Do not invent one. Do not edit CA-PD preregistrations, E3a results, or untracked E3b / OCELOT directories.

## Decision rights this scan separates

Already-obtained knowledge is not a violation. Controlled cache, future read, and future execution are. A watermark may identify an issuance. It must not be the only copy of a rule, and an attribution-only gain is not a security gain.
