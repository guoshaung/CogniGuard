"""Pre-registered verdict rules. Empty data is 无法判定."""

from __future__ import annotations

import random

from experiments.ocelot_edu_20261122_real.ocelot_edu.constants import (
    ATTACKER_GAP,
    B_STAR,
    BOOTSTRAP_N,
    BOOTSTRAP_SEED,
    G3_RECALL_LOWER,
)


def g1_qualifies(cums: list[float], budget: float = B_STAR) -> bool:
    if len(cums) < 2:
        return False
    if any(item <= 1e-9 or item > budget + 1e-9 for item in cums):
        return False
    return sum(cums) > budget + 1e-9


def bootstrap_ci(values: list[float], seed: int = BOOTSTRAP_SEED, n: int = BOOTSTRAP_N) -> dict:
    if not values:
        return {"n": 0, "mean": None, "low": None, "high": None}
    rng = random.Random(seed)
    size = len(values)
    stats = []
    for _ in range(n):
        total = 0.0
        for _j in range(size):
            total += values[rng.randrange(size)]
        stats.append(total / size)
    stats.sort()
    return {
        "n": size,
        "mean": sum(values) / size,
        "low": stats[int(0.025 * n)],
        "high": stats[min(n - 1, int(0.975 * n))],
    }


def cluster_bootstrap(groups: list[list[float]], seed: int = BOOTSTRAP_SEED, n: int = BOOTSTRAP_N) -> dict:
    usable = [group for group in groups if group]
    if not usable:
        return {"n": 0, "n_clusters": 0, "mean": None, "low": None, "high": None}
    flat = [item for group in usable for item in group]
    rng = random.Random(seed)
    stats = []
    width = len(usable)
    for _ in range(n):
        drawn = []
        for _j in range(width):
            drawn.extend(usable[rng.randrange(width)])
        stats.append(sum(drawn) / len(drawn))
    stats.sort()
    return {
        "n": len(flat),
        "n_clusters": width,
        "mean": sum(flat) / len(flat),
        "low": stats[int(0.025 * n)],
        "high": stats[min(n - 1, int(0.975 * n))],
    }


def verdict_gt_zero(ci: dict) -> str:
    if ci.get("mean") is None:
        return "无法判定"
    if ci["low"] > 0:
        return "支持"
    if ci["high"] <= 0:
        return "不支持"
    return "无法判定"


def verdict_recall(ci: dict, threshold: float = G3_RECALL_LOWER) -> str:
    if ci.get("mean") is None:
        return "无法判定"
    if ci["low"] > threshold:
        return "支持"
    if ci["high"] <= threshold:
        return "不支持"
    return "无法判定"


def combine(verdicts: list[str]) -> str:
    if not verdicts:
        return "无法判定"
    if any(item == "支持" for item in verdicts):
        return "支持"
    if any(item == "无法判定" for item in verdicts):
        return "无法判定"
    return "不支持"


def gap_blocks(oracle_mean, attacker_mean, gap: float = ATTACKER_GAP) -> bool:
    if oracle_mean is None or attacker_mean is None:
        return False
    return (oracle_mean - attacker_mean) > gap


def contrast_ci(left: list[float], right: list[float], seed: int = BOOTSTRAP_SEED, n: int = BOOTSTRAP_N) -> dict:
    """Mean(left) - mean(right). The two groups are resampled independently."""
    if not left or not right:
        return {"n_left": len(left), "n_right": len(right), "mean": None, "low": None, "high": None}
    rng = random.Random(seed)
    stats = []
    for _ in range(n):
        a = sum(left[rng.randrange(len(left))] for _j in range(len(left))) / len(left)
        b = sum(right[rng.randrange(len(right))] for _j in range(len(right))) / len(right)
        stats.append(a - b)
    stats.sort()
    return {
        "n_left": len(left),
        "n_right": len(right),
        "mean": (sum(left) / len(left)) - (sum(right) / len(right)),
        "low": stats[int(0.025 * n)],
        "high": stats[min(n - 1, int(0.975 * n))],
    }
