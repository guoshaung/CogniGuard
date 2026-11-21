from __future__ import annotations

import random

from protection.common.text_utils import lcs_length


def _reference_lcs(a: str, b: str) -> int:
    previous = [0] * (len(b) + 1)
    for left in a:
        current = [0]
        for index, right in enumerate(b, start=1):
            current.append(
                previous[index - 1] + 1
                if left == right
                else max(previous[index], current[-1])
            )
        previous = current
    return previous[-1]


def test_bit_parallel_lcs_matches_reference_dynamic_program() -> None:
    rng = random.Random(2026)
    for _ in range(200):
        left = "".join(rng.choice("abc123") for _ in range(rng.randrange(0, 35)))
        right = "".join(rng.choice("abc123") for _ in range(rng.randrange(0, 35)))
        assert lcs_length(left, right) == _reference_lcs(left, right)
