"""Spend so far, from the usage recorded in the call caches.

Prices in yuan per million tokens, the conservative end of what was found on
2026-11-24: Bailian price page (kimi-k3 20 / 100; qwen3.7-plus list price 2 / 8,
ignoring the time-limited discount); DeepSeek peak price for deepseek-flash
($0.30 / $1.20) at 7.2 yuan per dollar. Calls that failed are not billed.
"""

from __future__ import annotations

import json

from experiments.capd_e3b2_20261124.common import out_dir

CAP_YUAN = 50.0
PRICES = {
    "deepseek-flash": (0.30 * 7.2, 1.20 * 7.2),
    "qwen3.7-plus": (2.0, 8.0),
    "qwen3.7-flash": (0.5, 5.0),
    "glm-5.3": (8.0, 32.0),
    "kimi-k3": (20.0, 100.0),
    "glm-5.2": (0.0, 0.0),  # token plan: prepaid package, no per-call charge against the cap
}


def call_cost(model: str, usage: dict) -> float:
    price_in, price_out = PRICES[model]
    return (int(usage.get("prompt_tokens") or 0) * price_in
            + int(usage.get("completion_tokens") or 0) * price_out) / 1e6


def spent() -> dict:
    totals = {}
    for path in (out_dir() / "calls").glob("*.jsonl"):
        model = path.stem
        total = 0.0
        calls = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["ok"]:
                total += call_cost(model, row.get("usage") or {})
                calls += 1
        totals[model] = {"calls": calls, "yuan": round(total, 4)}
    return totals


def total_spent() -> float:
    return sum(v["yuan"] for v in spent().values())


if __name__ == "__main__":
    print(json.dumps(spent(), indent=2), round(total_spent(), 3))
