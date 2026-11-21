"""Registered uncertainty estimates; no third-party statistics dependency."""
import math
import random


def binomial(success, n):
    if n == 0:
        return {"success": success, "n": n, "rate": None, "ci95": [None, None]}
    z = 1.959963984540054
    p = success / n
    center = (p + z*z/(2*n)) / (1+z*z/n)
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1+z*z/n)
    return {"success": success, "n": n, "rate": p, "ci95": [max(0., center-half), min(1., center+half)]}


def bootstrap(values, statistic=None, seed=20261017, draws=2000):
    if not values or any(v is None for v in values):
        return {"mean": None, "n": len(values), "ci95": [None, None]}
    statistic = statistic or (lambda x: sum(x)/len(x))
    rng = random.Random(seed)
    sims = sorted(statistic(rng.choices(values, k=len(values))) for _ in range(draws))
    return {"mean": statistic(values), "n": len(values), "ci95": [sims[int(.025*draws)], sims[int(.975*draws)]]}


def exposure_ci(rows):
    # Cluster resampling by independent task/attack chain, not by hop.
    pairs = [(r["polluted_deliveries"], r["planned_edges"]) for r in rows]
    def ratio(samples):
        return sum(x[0] for x in samples) / sum(x[1] for x in samples)
    return bootstrap(pairs, statistic=ratio)
