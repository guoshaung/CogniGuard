"""Actual public graph; counterfactual edge weights are explicitly hypothetical."""
import json
import itertools
from pathlib import Path

graph = json.loads(Path(__file__).with_name('justhink_network.json').read_text(encoding='utf-8'))
nodes = {node['id'] for node in graph['nodes']}
edges = graph['links']
assert not graph['directed'] and not graph['multigraph']
assert len(nodes) == 10 and len(edges) == 20

def mst_cost(changed=None):
    parent = {v: v for v in nodes}
    def root(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v
    weighted = []
    for i, e in enumerate(edges):
        w = changed[1] if changed is not None and i == changed[0] else e['cost']
        weighted.append((w, i, e['source'], e['target']))
    cost = used = 0
    for w, _, a, b in sorted(weighted):
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[ra] = rb
            cost += w
            used += 1
    if used != len(nodes) - 1:
        raise ValueError('graph is disconnected')
    return cost

base = mst_cost()
def exhaustive_cost():
    best, winners = None, 0
    for combo in itertools.combinations(edges, len(nodes) - 1):
        parent = {v: v for v in nodes}
        def root(v):
            while parent[v] != v:
                v = parent[v]
            return v
        for edge in combo:
            a, b = root(edge['source']), root(edge['target'])
            if a == b:
                break
            parent[a] = b
        else:
            total = sum(edge['cost'] for edge in combo)
            if best is None or total < best:
                best, winners = total, 1
            elif total == best:
                winners += 1
    return best, winners

brute_cost, winner_count = exhaustive_cost()
assert brute_cost == base
tests = [(i, w, mst_cost((i, w))) for i, e in enumerate(edges) for w in range(1, 6) if w != e['cost']]
affected = {i for i, _, cost in tests if cost != base}
print(json.dumps({'nodes': len(nodes), 'edges': len(edges), 'mst_cost': base,
                  'exhaustive_mst_cost': brute_cost, 'optimal_trees': winner_count,
                  'single_edge_counterfactuals': len(tests),
                  'counterfactuals_changing_optimum': sum(cost != base for _, _, cost in tests),
                  'edges_with_at_least_one_cost_changing_counterfactual': len(affected)}, indent=2))
