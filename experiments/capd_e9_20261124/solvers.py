"""E9 solvers for: does some coalition of <= k agents that includes the recipient cover W?
DP = production code; NAIVE = plain coalition enumeration; BNB = exact branch-and-bound set cover."""

from __future__ import annotations

import itertools

from cogniguard.governance.reconstruction import _minimum_helpers, _masks


def dp(missing, knowledge, recipient, k):
    need, helpers = _minimum_helpers(missing, knowledge, recipient)
    return (need is not None and need <= k - 1), need, helpers


def naive(missing, knowledge, recipient, k):
    """Enumerate helper sets of size 0..k-1 over all other agents, no pruning."""
    others = sorted(a for a in knowledge if a != recipient)
    if not missing:
        return True, 0
    for size in range(1, k):
        for combo in itertools.combinations(others, size):
            covered = set()
            for a in combo:
                covered |= knowledge[a]
            if missing <= covered:
                return True, size
    return False, None


def bnb(missing, knowledge, recipient, k):
    """Exact minimum number of helpers (distinct non-empty masks), branch and bound."""
    ordered, masks = _masks(missing, knowledge, recipient)
    full = (1 << len(ordered)) - 1
    if full == 0:
        return True, 0
    best = [len(masks) + 1]
    bits_by = {b: [m for m, _ in masks if m >> b & 1] for b in range(len(ordered))}

    def go(covered, used):
        if used >= best[0]:
            return
        if covered == full:
            best[0] = used
            return
        low = (~covered & full) & -(~covered & full)
        b = low.bit_length() - 1
        for m in bits_by[b]:
            go(covered | m, used + 1)

    go(0, 0)
    need = best[0] if best[0] <= len(masks) else None
    return (need is not None and need <= k - 1), need


def quota_check(held_count, w, k):
    return held_count + 1 <= (w - 1) // k
