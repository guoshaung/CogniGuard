"""Gate 0-2 implementation checks (no data needed except where marked)."""

from __future__ import annotations

import random

from experiments.capd_gate012_20261124.sim import _steiner_costs, all_pairs


def _path_graph(n):
    agents = [f"a{i}" for i in range(n)]
    adj = {a: set() for a in agents}
    for i in range(n - 1):
        adj[agents[i]].add(agents[i + 1])
        adj[agents[i + 1]].add(agents[i])
    return agents, adj


def test_steiner_on_a_path_counts_edges_between_extremes():
    agents, adj = _path_graph(6)
    cost = _steiner_costs([agents[0], agents[3], agents[5]], adj, all_pairs(adj), budget=10)
    assert cost[0b111] == 5 and cost[0b001] == 0 and cost[0b011] == 3


def test_steiner_on_complete_graph_is_terminals_minus_one():
    agents = [f"a{i}" for i in range(7)]
    adj = {a: set(agents) - {a} for a in agents}
    rng = random.Random(0)
    terms = rng.sample(agents, 4)
    cost = _steiner_costs(terms, adj, all_pairs(adj), budget=10)
    for mask, c in cost.items():
        assert c == bin(mask).count("1") - 1


def test_budget_window_does_not_change_costs_within_budget():
    agents, adj = _path_graph(8)
    dist = all_pairs(adj)
    terms = [agents[1], agents[4], agents[6]]
    full = _steiner_costs(terms, adj, dist, budget=20)
    cut = _steiner_costs(terms, adj, dist, budget=3)
    for mask in full:
        if full[mask] <= 3:
            assert cut[mask] == full[mask]
