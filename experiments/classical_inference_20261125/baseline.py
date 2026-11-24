"""Disclosure rules compared with CA-PD on one shared knowledge map.

The quota is the collusion allocation in Woodruff and Staddon, Private
Inference Control (CCS 2004 / ePrint 2004/130): each user may take fewer
objects from a channel so that k users cannot finish it. The ePrint text
that could be read says this change depends on how many objects a user has
received, not on other users' objects, and that the private-retrieval
protocol is separate. A public summary of the talk states that c-collusion
resistance replaces an m-object channel by channels of length (m-1)/c.
The user-reviewed note of the paper gives the same cap, floor((|W|-1)/k).
The ePrint PDF itself returned HTTP 403 here, so this file does not claim
to quote Section 8. The PIR/SPIR protocol is not implemented: it hides the
query and does not change which releases satisfy the cap.

The union function is not Staddon's 2003 token scheme. That construction
was not available (the ACM PDF is closed). It is the global-union proxy
for the abstract's crowd-control property, and it enforces a stronger
condition than k-safety.
"""

from __future__ import annotations

from cogniguard.governance.reconstruction import check_release


def quota_cap(witness_size: int, k: int) -> int:
    """Most objects one user may hold from a channel of this size."""
    if k < 1:
        raise ValueError("k must be at least 1")
    if witness_size < 1:
        raise ValueError("witness size must be at least 1")
    return (witness_size - 1) // k


def _touched(targets, release):
    found = {}
    for unit in release:
        for target in targets.targets_for_unit(unit):
            found.setdefault(target.target_id, target)
    return tuple(found[target_id] for target_id in sorted(found))


def ws04_quota_allows(targets, recipient, release, knowledge, k: int) -> bool:
    """True when the recipient stays within the per-channel cap.

    Other principals are ignored. A state built only by releases that pass
    this test is k-safe for disjoint accounting per witness: k users hold
    at most k * floor((|W|-1)/k) <= |W|-1 objects of W. A state that already
    contains holdings above the cap does not inherit that guarantee.
    """
    held = knowledge.get(recipient, frozenset()) | frozenset(release)
    for target in _touched(targets, release):
        for witness in target.witness_sets:
            if len(held & witness) > quota_cap(len(witness), k):
                return False
    return True


def quota_state_within_cap(targets, knowledge, k: int) -> bool:
    """True when every principal is inside the cap on every witness."""
    for target in targets._by_id.values():
        for witness in target.witness_sets:
            cap = quota_cap(len(witness), k)
            for held in knowledge.values():
                if len(held & witness) > cap:
                    return False
    return True


def union_proxy_allows(targets, recipient, release, knowledge, k: int) -> bool:
    """Deny when every principal together can already finish a touched witness.

    `k` is accepted so the call shape matches the other rules. The decision
    does not use it. This is the stronger crowd-control proxy, not k-safety.
    """
    del recipient, k
    union = frozenset().union(*knowledge.values()) | frozenset(release)
    return not any(
        witness <= union
        for target in _touched(targets, release)
        for witness in target.witness_sets
    )


def capd_allows(targets, recipient, release, knowledge, k: int) -> bool:
    """CA-PD: no coalition of size at most k that contains the recipient covers a witness."""
    return check_release(targets, recipient, set(release), knowledge, k).safe
