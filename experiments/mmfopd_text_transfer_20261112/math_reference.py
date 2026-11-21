"""Independent arithmetic checks. Imported by the offline judge only."""
from collections import Counter
from fractions import Fraction
from functools import lru_cache


def tax_maximum():
    factors = [sum(1 << (d - 1) for d in range(1, n) if n % d == 0) for n in range(1, 13)]

    @lru_cache(None)
    def best(remaining):
        outcomes = [0]
        for i, mask in enumerate(factors):
            eligible_factors = remaining & mask
            if remaining & (1 << i) and eligible_factors:
                outcomes.append(i + 1 + best(remaining & ~(eligible_factors | (1 << i))))
        return max(outcomes)

    return best((1 << 12) - 1)


def offline_math_reference(task):
    if task == "one_thousand_one_pennies":
        counts = Counter(25 if i % 4 == 0 else 10 if i % 3 == 0 else 5 if i % 2 == 0 else 1
                         for i in range(1, 1002))
        total = sum(denomination * count for denomination, count in counts.items())
        return f"Index 1 through 1001. Later replacements override earlier ones. Coin counts by cents: {dict(sorted(counts.items()))}; total {total} cents."
    if task == "traffic_jam":
        hours = Fraction(3, 2) / Fraction(2, 3)
        return f"Time is distance divided by speed: {hours} hours (2 hours 15 minutes)."
    if task == "ice_cream":
        servings = [30, 75, 45, 150]
        tubs = [(value + 9) // 10 for value in servings]
        cost = 2 * sum(tubs) + 300 * .05
        return f"Mint, strawberry, chocolate chip, vanilla: servings {servings}, whole tubs {tubs}; if each flavor bought separately, cost ${cost:.0f}, revenue $240, profit ${240 - cost:.0f}."
    if task == "znorlian":
        return "The public clues imply A=1, B=2, C=4, E=8, D=16. 21 is DCA in any order, using three symbols. No pair of allowed values adds to 21."
    if task == "tax_collector":
        return f"Under the stated rules for 1 through 12, exhaustive remaining-paycheck search gives maximum player total {tax_maximum()} and tax collector total {78 - tax_maximum()}."
    return ""
