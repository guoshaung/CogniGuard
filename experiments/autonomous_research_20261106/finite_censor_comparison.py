"""Exhaustive finite-denial analogue of static/intersection and dynamic censors.

The experiment is not an implementation of SC/IC or MC-CQE for DL-Lite.
It operates on an explicitly bounded, synthetic, two-atom propositional model.
History is public and irreversible. Policies are evaluated against *every*
dependency in the explicitly supplied family; coverage is an assumption.
"""
from itertools import combinations
import json

ATOMS = frozenset({"a", "b"})
FAMILY = (frozenset(), frozenset({"a", "b"}))  # empty means no forbidden set


def subsets(items):
    ordered = sorted(items)
    return [frozenset(p) for n in range(len(ordered) + 1) for p in combinations(ordered, n)]


def safe(view, family):
    return all(not (constraint and constraint <= view) for constraint in family)


def maximal_views(history, family):
    feasible = [view for view in subsets(ATOMS) if history <= view and safe(view, family)]
    return [view for view in feasible if not any(view < other for other in feasible)]


def intersection(views):
    return set.intersection(*(set(v) for v in views)) if views else set()


def main():
    empty = maximal_views(frozenset(), FAMILY)
    after_a = maximal_views(frozenset({"a"}), FAMILY)
    oracle_after_a = maximal_views(frozenset({"a"}), FAMILY[:1])
    # Static skeptical intersection refuses either singleton. Dynamic maximal
    # continuation may admit a singleton, then must refuse its complement.
    assert set(empty) == {frozenset({"a"}), frozenset({"b"})}
    assert intersection(empty) == set()
    assert intersection(after_a) == {"a"}
    assert intersection(oracle_after_a) == {"a", "b"}
    print(json.dumps({"classification": "FINITE_DENIAL_ANALOGUE_NOT_PUBLISHED_CQE_IMPL",
                      "maximal_views_initial": [sorted(v) for v in empty],
                      "initial_static_intersection": sorted(intersection(empty)),
                      "after_a_maximal_views": [sorted(v) for v in after_a],
                      "after_a_safe_to_release_b": "b" in intersection(after_a),
                      "full_rule_oracle_allows_b_in_no_rule_world": "b" in intersection(oracle_after_a),
                      "limitations": ["synthetic two atoms", "known uncertainty family",
                                      "truthful positive releases only", "no secret action channel here"]}, indent=2))


if __name__ == "__main__":
    main()
