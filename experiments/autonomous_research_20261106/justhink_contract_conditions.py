"""Evaluate the preregistered public-graph contracts; no participant data."""
import itertools
import json
from pathlib import Path

g = json.loads(Path(__file__).with_name('justhink_network.json').read_text(encoding='utf-8'))
nodes = {n['id'] for n in g['nodes']}
edges = g['links']
assert len(nodes) == 10 and len(edges) == 20 and not g['directed'] and not g['multigraph']
base = tuple(e['cost'] for e in edges)
worlds = [base]
for i, old in enumerate(base):
    for value in range(1, 6):
        if value != old:
            alt = list(base)
            alt[i] = value
            worlds.append(tuple(alt))
assert len(worlds) == len(set(worlds)) == 81

def kruskal(weights):
    parent = {v: v for v in nodes}
    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v
    cost = used = 0
    for _, i in sorted((w, i) for i, w in enumerate(weights)):
        e = edges[i]
        a, b = find(e['source']), find(e['target'])
        if a != b:
            parent[a] = b
            cost += weights[i]
            used += 1
    assert used == len(nodes) - 1
    return cost

def exhaustive_original():
    best = None
    for indices in itertools.combinations(range(len(edges)), len(nodes) - 1):
        parent = {v: v for v in nodes}
        def find(v):
            while parent[v] != v:
                v = parent[v]
            return v
        for i in indices:
            e = edges[i]
            a, b = find(e['source']), find(e['target'])
            if a == b:
                break
            parent[a] = b
        else:
            cost = sum(base[i] for i in indices)
            best = cost if best is None else min(cost, best)
    return best

actual = [kruskal(w) for w in worlds]
assert actual[0] == exhaustive_original() == 22
output = {'world_count': len(worlds), 'original_cost': actual[0], 'conditions': []}
for knowledge, eligible in [('known_original', [0]), ('unknown_instance', list(range(len(worlds))) )]:
    for strategy in ('none', 'all_raw', 'exact_result'):
        decisions = []
        for i in eligible:
            if strategy == 'none':
                answer = kruskal(base)
            elif strategy == 'all_raw':
                answer = kruskal(worlds[i])
            else:
                answer = actual[i]
            decisions.append(answer == actual[i])
        output['conditions'].append({'knowledge': knowledge, 'strategy': strategy,
                                     'correct': sum(decisions), 'total': len(decisions),
                                     'raw_edge_values_sent': 20 if strategy == 'all_raw' else 0,
                                     'derived_result_values_sent': 1 if strategy == 'exact_result' else 0})
    
witnesses = 0
for excluded in range(len(edges)):
    found = any(all(w[j] == base[j] for j in range(len(edges)) if j != excluded)
                and actual[i] != actual[0] for i, w in enumerate(worlds[1:], 1))
    witnesses += found
output['fixed_one_field_omission_witnesses'] = witnesses
assert all(row['correct'] == row['total'] for row in output['conditions'] if row['strategy'] != 'none')
print(json.dumps(output, indent=2))
