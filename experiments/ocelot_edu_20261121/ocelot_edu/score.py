"""Recovery scoring and the pre-registered verdict rule."""

from __future__ import annotations

import random

from experiments.ocelot_edu_20261121.ocelot_edu.assets import Unit
from experiments.ocelot_edu_20261121.ocelot_edu.constants import BOOTSTRAP_N, BOOTSTRAP_SEED


def contains_markers(text: str, unit: Unit) -> bool:
    return all(marker in (text or "") for marker in unit.markers)


def bootstrap_ci(values: list[float], seed: int = BOOTSTRAP_SEED, n: int = BOOTSTRAP_N) -> dict:
    if not values:
        return {"n": 0, "mean": None, "low": None, "high": None}
    rng = random.Random(seed)
    m = len(values)
    stats = []
    for _ in range(n):
        draw = 0.0
        for _j in range(m):
            draw += values[rng.randrange(m)]
        stats.append(draw / m)
    stats.sort()
    mean = sum(values) / m
    return {
        "n": m,
        "mean": mean,
        "low": stats[int(0.025 * n)],
        "high": stats[min(n - 1, int(0.975 * n))],
    }


def verdict_gt_zero(ci: dict) -> str:
    """支持 if the 95% interval lies entirely above 0; 不支持 if it lies at or below 0."""
    if ci["mean"] is None:
        return "无法判定"
    if ci["low"] > 0:
        return "支持"
    if ci["high"] <= 0:
        return "不支持"
    return "无法判定"


def verdict_recall(ci: dict, threshold: float) -> str:
    if ci["mean"] is None:
        return "无法判定"
    if ci["low"] > threshold:
        return "支持"
    if ci["high"] <= threshold:
        return "不支持"
    return "无法判定"
