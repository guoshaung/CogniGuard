"""Exhaustive two-world action audit; NOT a reproduction of MC-CQE.

Two threat models are intentionally kept separate. Under target secrecy the
adversary knows the applicable dependency; under policy secrecy the observer
does not know which rule world holds, but knows the policy mapping. The only
new observable event is the public allow/block response. The input state and
request are common, and no data source, model, randomness or output file is used.
"""
from itertools import product
import json

WORLDS = ("no_rule", "a_and_b_implies_secret")
ACTIONS = ("allow", "block")


def audit(mapping):
    """Prior release is a, proposed truthful release is b in both worlds."""
    target_leak = [w for w in WORLDS
                   if mapping[w] == "allow" and w == "a_and_b_implies_secret"]
    blocked_safe = [w for w in WORLDS if mapping[w] == "block" and w == "no_rule"]
    # Under the policy-secrecy threat model, decisions are observable and the
    # deterministic mapping is common knowledge; identify surviving worlds.
    possible_by_world = {w: [v for v in WORLDS if mapping[v] == mapping[w]] for w in WORLDS}
    identified_rule_world = [w for w in WORLDS if len(possible_by_world[w]) == 1]
    return {"mapping": mapping, "target_leak": target_leak,
            "blocked_safe": blocked_safe, "policy_identity_disclosed": identified_rule_world,
            "possible_worlds_after_action": possible_by_world}


def main():
    rows = [audit(dict(zip(WORLDS, decisions))) for decisions in product(ACTIONS, repeat=2)]
    robust = next(r for r in rows if list(r["mapping"].values()) == ["block", "block"])
    full_rule_oracle = next(r for r in rows if list(r["mapping"].values()) == ["allow", "block"])
    optimistic = next(r for r in rows if list(r["mapping"].values()) == ["allow", "allow"])
    assert not robust["target_leak"] and not robust["policy_identity_disclosed"]
    assert robust["blocked_safe"] == ["no_rule"]
    assert not full_rule_oracle["target_leak"] and not full_rule_oracle["blocked_safe"]
    assert len(full_rule_oracle["policy_identity_disclosed"]) == 2
    assert optimistic["target_leak"] == ["a_and_b_implies_secret"]
    print(json.dumps({"status": "FINITE_SYNTHETIC_EXHAUSTIVE_NOT_MC_CQE_REPRODUCTION",
                      "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
