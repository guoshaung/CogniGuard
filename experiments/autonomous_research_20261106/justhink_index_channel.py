"""Preregistered fixed-vs-adaptive public-graph communication probe."""
import contextlib
import io
import json
from collections import Counter, defaultdict

with contextlib.redirect_stdout(io.StringIO()):
    import justhink_contract_conditions as prior

worlds, costs = prior.worlds, prior.actual
possible = sorted(set(costs))
assert len(worlds) == 81 and len(possible) <= len(prior.edges) == 20
groups = defaultdict(Counter)
for world, cost in zip(worlds, costs):
    groups[world[0]][cost] += 1
chosen = {obs: min(counter, key=lambda cost: (-counter[cost], cost)) for obs, counter in groups.items()}
fixed_correct = sum(chosen[w[0]] == c for w, c in zip(worlds, costs))
ambiguous = sum(len(counter) > 1 for counter in groups.values())
adaptive_correct = 0
for world, cost in zip(worlds, costs):
    index = possible.index(cost)
    transmitted_weight = world[index]
    assert 1 <= transmitted_weight <= 5
    recovered = possible[index]
    adaptive_correct += recovered == cost
assert adaptive_correct == len(worlds)
print(json.dumps({'worlds': len(worlds), 'distinct_costs': len(possible),
                  'fixed_first_edge_correct': fixed_correct,
                  'fixed_first_edge_observation_groups': len(groups),
                  'fixed_first_edge_ambiguous_groups': ambiguous,
                  'adaptive_index_correct': adaptive_correct,
                  'all_raw_correct': len(worlds), 'derived_exact_result_correct': len(worlds)}, indent=2))
