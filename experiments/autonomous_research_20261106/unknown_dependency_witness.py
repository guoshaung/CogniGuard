"""Finite impossibility witness, not an evaluation of production C²-RAG.

Run: python -B experiments/autonomous_research_20261106/unknown_dependency_witness.py
No external packages, data, models, network, or generated files.
"""
from itertools import product
import json


def closure(facts, rules):
    known = set(facts)
    while True:
        more = {head for body, head in rules if set(body) <= known}
        updated = known | more
        if updated == known:
            return known
        known = updated


def main():
    # Same observable initial state and request in both worlds. World 1 has an
    # unobserved dependency; the attacker knows it while the controller does not.
    history = {"a"}
    candidate = "b"
    worlds = {"no_dependency": [], "hidden_dependency": [("ab", "secret")]}
    known_rule_decision = "allow" if "secret" not in closure(history | {candidate}, []) else "block"
    cases = []
    for name, rules in worlds.items():
        full = closure(history | {candidate}, rules)
        complete_rule_oracle = "block" if "secret" in full else "allow"
        cases.append({"world": name, "observed_history": sorted(history),
                      "candidate": candidate, "observed_rule_decision": known_rule_decision,
                      "complete_rule_oracle": complete_rule_oracle,
                      "secret_after_allow": "secret" in full})

    # Any deterministic policy sees identical inputs and hence chooses the same
    # action in both worlds: allowing leaks in one, blocking sacrifices one safe
    # action in the other. Randomization changes probabilities, not the tradeoff.
    outcomes = []
    for action in ("allow", "block"):
        outcomes.append({"shared_action": action,
                         "leaks_by_world": [c["world"] for c in cases
                                            if action == "allow" and c["secret_after_allow"]],
                         "unnecessary_blocks_by_world": [c["world"] for c in cases
                                                         if action == "block" and c["complete_rule_oracle"] == "allow"]})
    assert cases[0]["complete_rule_oracle"] == "allow"
    assert cases[1]["complete_rule_oracle"] == "block"
    assert outcomes[0]["leaks_by_world"] == ["hidden_dependency"]
    assert outcomes[1]["unnecessary_blocks_by_world"] == ["no_dependency"]
    assert all(closure(set(x), [("ab", "secret")]) >= set(x)
               for size in (0, 1, 2) for x in product("ab", repeat=size))
    print(json.dumps({"classification": "SYNTHETIC_MECHANISM_WITNESS_NOT_REAL_PERFORMANCE",
                      "assumptions": ["irreversible release", "same controller observation",
                                      "attacker knows hidden rule", "deterministic action"],
                      "cases": cases, "outcomes": outcomes}, indent=2))


if __name__ == "__main__":
    main()
