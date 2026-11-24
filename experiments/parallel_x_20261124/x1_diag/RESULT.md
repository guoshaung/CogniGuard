# X1 utility diagnosis

Diagnosis label: **PLANNER**.
Diagnosis verdict: **STOP**.
The frozen X1 verdict stays **STOP**. This file does not award PASS.

## Model

A finite schedule is a sequence of tasks. Each task has a finite candidate set. A candidate delivers a set of unit refs and has a scalar utility. Every method reads the same task plan, the same candidate objects, and the same `candidate.utility` values.

Safety of a release is `check_release(registry, recipient, release_units, knowledge, k)` from `cogniguard.governance.reconstruction`, with `k = COALITION_K`. Knowledge is every principal's holdings so far, including the recipient. The predicate is that no coalition of size at most `k` that includes the recipient finishes a registered witness. An empty release is safe. No other safety predicate is used. `library_safe` is that predicate on simulated final holdings.

Objective: maximize the number of benign tasks whose goal refs are contained in the delivered refs, subject to safety of the final holdings.

Information each algorithm may read:

- `serial_gate`: the current item and holdings. No future item.
- `joint_commit`: the whole flattened schedule, then one historical witness-type ban.
- `utility_greedy_reorder`: every item's max candidate utility and task name, then the serial gate on that order. No separate utility.
- `lookahead_2`: the current item, the next item, and holdings. Nothing past those two.
- `exact_type_ban`: the whole schedule and the eight subsets of `{agg, sum, test}`.
- `exact_subset`: the whole schedule, and only when it has at most 16 items. Each task is either its best `b4_ok` non-refuse candidate or refuse.

```
serial_gate(batches, holdings):
    for batch in batches:
        for item in batch:
            cand = argmax utility among b4_ok candidates whose units
                   check_release accepts (empty release is safe; else refuse)
            commit cand; add its units to the recipient's holdings
    return commits

utility_greedy_reorder(schedule):
    order = sort schedule by (-max candidate.utility, task name)
    return serial_gate([order], holdings)

lookahead_2(schedule):
    for i, item in enumerate(schedule):
        next = schedule[i + 1] if i + 1 < n else none
        pick cand maximizing cand.utility + best safe utility of next
            after tentatively adding cand
        tie-break: higher cand.utility, then longer unit tuple
        commit cand only; advance one step
    return commits

exact_type_ban(schedule):
    best = none
    for ban in all 8 subsets of {agg, sum, test}:
        chosen = _select_under_ban(item, ban) for item in schedule
        if library_safe(simulate(chosen)):
            keep the safe ban with the most benign successes,
            then fewer banned types, then the lexical ban tuple
    return best
```

## Recomputed gap

Same tasks and the same `candidate.utility` values as the historical joint commit. The serial gate walks each batch in order and updates holdings before the next item.

| split | method | violations | benign success | decisions equal joint_commit |
| --- | --- | ---: | ---: | --- |
| deterministic | joint_commit | 0 | 0.9000 | yes |
| deterministic | serial_gate | 0 | 0.9000 | True |
| dev scan | joint_commit | 0 | 0.9091 | yes |
| dev scan | serial_gate | 0 | 0.5455 | False |

B4 violations recomputed: deterministic 8, dev 9. B4 still violates. Frozen gates, not refit: PASS_MIN_ABS_SAFETY_GAIN = 0.1, MAX_UTILITY_DROP = 0.1, MAX_OVERHEAD_RATIO = 10.0.

## Deterministic schedules

Pooled across simultaneous, sequential, multi-round, and cross. Not mixed with the dev scan.

| method | violations | violation rate | benign success | false reject | joint-covered sessions | decisions equal joint_commit |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| serial_gate | 0 | 0.0000 | 0.9000 (36/40) | 0.0000 | 0/4 | True |
| joint_commit | 0 | 0.0000 | 0.9000 (36/40) | 0.0000 | 0/4 | True |
| utility_greedy_reorder | 0 | 0.0000 | 0.9000 (36/40) | 0.0000 | 0/4 | True |
| lookahead_2 | 0 | 0.0000 | 0.9000 (36/40) | 0.0000 | 0/4 | True |
| exact_type_ban | 0 | 0.0000 | 0.9000 (36/40) | 0.0000 | 0/4 | True |
| exact_subset | 0 | 0.0000 | 0.9000 (36/40) | 0.0000 | 0/4 | False |

### Per schedule

| schedule | method | violations | benign success | equal joint_commit | missed benign |
| --- | --- | ---: | ---: | --- | --- |
| simultaneous | serial_gate | 0 | 0.9000 | True | u_test |
| sequential | serial_gate | 0 | 0.9000 | True | u_test |
| multi_round | serial_gate | 0 | 0.9000 | True | u_test |
| cross | serial_gate | 0 | 0.9000 | True | u_test |
| simultaneous | joint_commit | 0 | 0.9000 | True | u_test |
| sequential | joint_commit | 0 | 0.9000 | True | u_test |
| multi_round | joint_commit | 0 | 0.9000 | True | u_test |
| cross | joint_commit | 0 | 0.9000 | True | u_test |
| simultaneous | utility_greedy_reorder | 0 | 0.9000 | True | u_test |
| sequential | utility_greedy_reorder | 0 | 0.9000 | True | u_test |
| multi_round | utility_greedy_reorder | 0 | 0.9000 | True | u_test |
| cross | utility_greedy_reorder | 0 | 0.9000 | True | u_test |
| simultaneous | lookahead_2 | 0 | 0.9000 | True | u_test |
| sequential | lookahead_2 | 0 | 0.9000 | True | u_test |
| multi_round | lookahead_2 | 0 | 0.9000 | True | u_test |
| cross | lookahead_2 | 0 | 0.9000 | True | u_test |
| simultaneous | exact_type_ban | 0 | 0.9000 | True | u_test |
| sequential | exact_type_ban | 0 | 0.9000 | True | u_test |
| multi_round | exact_type_ban | 0 | 0.9000 | True | u_test |
| cross | exact_type_ban | 0 | 0.9000 | True | u_test |
| simultaneous | exact_subset | 0 | 0.9000 | False | u_test |
| sequential | exact_subset | 0 | 0.9000 | False | u_test |
| multi_round | exact_subset | 0 | 0.9000 | False | u_test |
| cross | exact_subset | 0 | 0.9000 | False | u_test |

## Dev scan

Five seeds. Round order is shuffled by the historical session builder. Not pooled with the four fixed schedules.

| method | violations | violation rate | benign success | false reject | joint-covered sessions | decisions equal joint_commit |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| serial_gate | 0 | 0.0000 | 0.5455 (30/55) | 0.0000 | 0/5 | False |
| joint_commit | 0 | 0.0000 | 0.9091 (50/55) | 0.0000 | 0/5 | True |
| utility_greedy_reorder | 0 | 0.0000 | 0.9091 (50/55) | 0.0000 | 0/5 | True |
| lookahead_2 | 0 | 0.0000 | 0.5455 (30/55) | 0.0000 | 0/5 | False |
| exact_type_ban | 0 | 0.0000 | 0.9091 (50/55) | 0.0000 | 0/5 | True |
| exact_subset | not run | not run | not run | not run | not run | n/a |

exact_subset: not run: flattened schedule has 17 items, above the 16-item cap.

### Per seed

| seed | method | benign success | violations | missed benign |
| --- | --- | ---: | ---: | --- |
| dev-0 | serial_gate | 0.4545 | 0 | u_agg, u_agg2, u_agg3, u_pair, u_pair2, u_pair3 |
| dev-1 | serial_gate | 0.4545 | 0 | u_pair, u_pair2, u_pair3, u_sum, u_sum2, u_sum3 |
| dev-2 | serial_gate | 0.4545 | 0 | u_pair, u_pair2, u_pair3, u_agg, u_agg2, u_agg3 |
| dev-3 | serial_gate | 0.4545 | 0 | u_pair, u_pair2, u_pair3, u_sum, u_sum2, u_sum3 |
| dev-4 | serial_gate | 0.9091 | 0 | u_test |
| dev-0 | joint_commit | 0.9091 | 0 | u_test |
| dev-1 | joint_commit | 0.9091 | 0 | u_test |
| dev-2 | joint_commit | 0.9091 | 0 | u_test |
| dev-3 | joint_commit | 0.9091 | 0 | u_test |
| dev-4 | joint_commit | 0.9091 | 0 | u_test |
| dev-0 | utility_greedy_reorder | 0.9091 | 0 | u_test |
| dev-1 | utility_greedy_reorder | 0.9091 | 0 | u_test |
| dev-2 | utility_greedy_reorder | 0.9091 | 0 | u_test |
| dev-3 | utility_greedy_reorder | 0.9091 | 0 | u_test |
| dev-4 | utility_greedy_reorder | 0.9091 | 0 | u_test |
| dev-0 | lookahead_2 | 0.4545 | 0 | u_agg, u_agg2, u_agg3, u_pair, u_pair2, u_pair3 |
| dev-1 | lookahead_2 | 0.4545 | 0 | u_pair, u_pair2, u_pair3, u_sum, u_sum2, u_sum3 |
| dev-2 | lookahead_2 | 0.4545 | 0 | u_pair, u_pair2, u_pair3, u_agg, u_agg2, u_agg3 |
| dev-3 | lookahead_2 | 0.4545 | 0 | u_pair, u_pair2, u_pair3, u_sum, u_sum2, u_sum3 |
| dev-4 | lookahead_2 | 0.9091 | 0 | u_test |
| dev-0 | exact_type_ban | 0.9091 | 0 | u_test |
| dev-1 | exact_type_ban | 0.9091 | 0 | u_test |
| dev-2 | exact_type_ban | 0.9091 | 0 | u_test |
| dev-3 | exact_type_ban | 0.9091 | 0 | u_test |
| dev-4 | exact_type_ban | 0.9091 | 0 | u_test |

## Seed 0 missed tasks

joint_commit missed: u_test.
serial_gate missed: u_agg, u_agg2, u_agg3, u_pair, u_pair2, u_pair3.
Claimed serial misses were u_agg, u_agg2, u_agg3, u_pair, u_pair2, u_pair3. Recomputed list matches that claim: True.

Arrival batches:

- u_test, b_src, u_audit, b_audit_raw
- u_sum, u_sum2, u_sum3, b_quote
- u_agg, u_agg2, u_agg3, b_raw
- b_launder, p_joint
- u_pair, u_pair2, u_pair3

## Order ablation

Same dev multiset. `serial_gate` on the historical arrival order versus `serial_gate` after `random.Random(seed).shuffle` of those items. No new selector.

Arrival benign success 0.5455 (30/55). Shuffled benign success 0.9091 (50/55). Order moves utility: True.

| seed | arrival successes | shuffled successes | moved | shuffle matches joint utility |
| --- | ---: | ---: | --- | --- |
| 0 | 5 | 10 | True | True |
| 1 | 5 | 10 | True | True |
| 2 | 5 | 10 | True | True |
| 3 | 5 | 10 | True | True |
| 4 | 10 | 10 | False | True |

## Attribution

Recomputed dev-scan benign success is serial_gate 0.5455 and joint_commit 0.9091, both with 0 reconstruction violations. Deterministic schedules do not show that gap: both are 0.9000 with the same decisions and 0 violations. Seed 0 joint_commit misses only u_test; serial_gate misses u_agg, u_agg2, u_agg3, u_pair, u_pair2, u_pair3. Every task's max candidate.utility is 1.0, equal across tasks: True. utility_greedy_reorder therefore sorts by task name and runs the serial gate; its dev benign success is 0.9091. lookahead_2 dev benign success is 0.5455. exact_type_ban dev benign success is 0.9091. exact_subset on dev: not run: flattened schedule has 17 items, above the 16-item cap. Shuffling each dev multiset with Random(seed) moves serial-gate benign success from 0.5455 to 0.9091 (50/55). Every shuffled seed misses only u_test and has 0 violations, so those orders match joint_commit utility with the serial gate and no type ban. utility_greedy_reorder matches joint_commit utility within 0.01 with 0 violations on both splits. lookahead_2 does not: on the dev scan it stays with the serial gate, because a conflicting next task has the same utility 1, the two-step sum ties, and the tie keeps the current safe release. Ordinary priority planning plus the existing gate closes the utility gap. The closure is an order, not a new predicate: every max utility is 1, so the reorder is alphabetical and puts u_test last, after aggregates and summaries are already held. exact_subset on the 15-item deterministic schedules also reaches 0.9000, but its decisions differ because it refuses p_joint instead of releasing that probe's aggregate and summary. It was not run on the 17-item dev sessions. Safety gain versus the serial gate is 0. Diagnosis verdict STOP. The historical X1 experiment remains STOP and is not a PASS.

## Gates

PASS_MIN_ABS_SAFETY_GAIN = 0.10, MAX_UTILITY_DROP = 0.10, MAX_OVERHEAD_RATIO = 10. These were not refit. Baseline serial gate already has zero reconstruction violations, so there is no safety gain to score. A utility recovery from reordering is not a PASS.
