#!/usr/bin/env python3
"""Extrapolate phase-1 cost from a smoke run. Does not call any API.

Prices are the 2026-11-20 official lists recorded in R_PREREG.md.
DeepSeek-V4.1-Flash-1017 (deepseek-flash), RMB per 1M tokens.
DashScope text-embedding-v4 Beijing sync price, RMB per 1M input tokens.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


# RMB per 1,000,000 tokens.
FLASH = {
    "offpeak": {"hit": 0.02, "miss": 1.0, "output": 4.0},
    "peak": {"hit": 0.04, "miss": 2.0, "output": 8.0},
}
# 0.0005 RMB / 1,000 tokens.
EMBED_PER_MILLION = 0.50
TARGET_PER_ENV = 50
ENVS = ("gorilla_fs", "vehicle_control", "trading_bot", "travel_api")


def load_usage(path: Path) -> dict:
    hit = miss = prompt = completion = reasoning = calls = bad = 0
    reasoning_above_completion = 0
    if not path.is_file():
        return {"missing": True, "path": str(path)}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        calls += 1
        prompt += int(row.get("prompt_tokens") or 0)
        completion += int(row.get("completion_tokens") or 0)
        hit += int(row.get("prompt_cache_hit_tokens") or 0)
        miss += int(row.get("prompt_cache_miss_tokens") or 0)
        extra = int(row.get("reasoning_tokens") or 0)
        reasoning += extra
        if extra > int(row.get("completion_tokens") or 0):
            reasoning_above_completion += extra - int(row.get("completion_tokens") or 0)
    uncovered = max(prompt - hit - miss, 0)
    return {
        "missing": False,
        "path": str(path),
        "calls": calls,
        "bad_lines": bad,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "cache_hit_tokens": hit,
        "cache_miss_tokens": miss,
        "uncovered_prompt_tokens": uncovered,
        "reasoning_tokens": reasoning,
        "reasoning_above_completion": reasoning_above_completion,
    }


def load_samples(path: Path) -> list[dict]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def scale_arm(samples: list[dict], usage: dict) -> dict:
    by_env: dict[str, list[dict]] = {name: [] for name in ENVS}
    for row in samples:
        setting = row.get("setting") or row.get("category") or ""
        if setting in by_env:
            by_env[setting].append(row)
    embed = 0
    scale_notes = []
    for name in ENVS:
        rows = by_env[name]
        if not rows:
            scale_notes.append(f"{name}: missing")
            continue
        embed_sum = sum(int(float(row.get("embedding_tokens") or 0)) for row in rows)
        embed += embed_sum * (TARGET_PER_ENV / len(rows))
        scale_notes.append(f"{name}: n={len(rows)} x{TARGET_PER_ENV / len(rows):.4g}")
    n = len(samples)
    factor = (TARGET_PER_ENV * len(ENVS) / n) if n else 0
    output_tokens = usage["completion_tokens"] + usage["reasoning_above_completion"]
    # Tokens the API did not split are billed as cache misses.
    miss = usage["cache_miss_tokens"] + usage["uncovered_prompt_tokens"]
    hit = usage["cache_hit_tokens"]
    return {
        "n": n,
        "factor": factor,
        "scale_notes": scale_notes,
        "hit": hit * factor,
        "miss": miss * factor,
        "output": output_tokens * factor,
        "embed": embed,
        "calls": usage["calls"] * factor,
    }


def price_llm(arm: dict, band: str) -> float:
    rate = FLASH[band]
    return (
        arm["hit"] / 1_000_000 * rate["hit"]
        + arm["miss"] / 1_000_000 * rate["miss"]
        + arm["output"] / 1_000_000 * rate["output"]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--usage-nomem", type=Path, required=True)
    parser.add_argument("--usage-rb", type=Path, required=True)
    parser.add_argument("--samples-nomem", type=Path, required=True)
    parser.add_argument("--samples-rb", type=Path, required=True)
    args = parser.parse_args()

    arms = {}
    for label, usage_path, sample_path in (
        ("no_memory", args.usage_nomem, args.samples_nomem),
        ("reasoning_bank", args.usage_rb, args.samples_rb),
    ):
        usage = load_usage(usage_path)
        if usage.get("missing"):
            raise SystemExit(f"missing usage log: {usage_path}")
        samples = load_samples(sample_path)
        arm = scale_arm(samples, usage)
        arm["usage"] = usage
        arms[label] = arm

    print("target_samples_per_arm", TARGET_PER_ENV * len(ENVS))
    total = {"offpeak": 0.0, "peak": 0.0, "embed": 0.0}
    for label, arm in arms.items():
        usage = arm["usage"]
        print(f"[{label}] smoke_n={arm['n']} scale={arm['factor']:.6g} calls_scaled={arm['calls']:.1f}")
        print(f"[{label}] " + "; ".join(arm["scale_notes"]))
        print(
            f"[{label}] smoke_prompt={usage['prompt_tokens']}"
            f" hit={usage['cache_hit_tokens']} miss={usage['cache_miss_tokens']}"
            f" uncovered={usage['uncovered_prompt_tokens']}"
            f" completion={usage['completion_tokens']}"
            f" reasoning={usage['reasoning_tokens']}"
            f" reasoning_above_completion={usage['reasoning_above_completion']}"
            f" bad_lines={usage['bad_lines']}"
        )
        off = price_llm(arm, "offpeak")
        peak = price_llm(arm, "peak")
        embed_cost = arm["embed"] / 1_000_000 * EMBED_PER_MILLION
        total["offpeak"] += off
        total["peak"] += peak
        total["embed"] += embed_cost
        print(
            f"[{label}] deepseek_offpeak_rmb={off:.4f}"
            f" deepseek_peak_rmb={peak:.4f}"
            f" dashscope_rmb={embed_cost:.4f}"
            f" embed_tokens_scaled={arm['embed']:.1f}"
        )
    print(f"deepseek_offpeak_rmb={total['offpeak']:.4f}")
    print(f"deepseek_peak_rmb={total['peak']:.4f}")
    print(f"dashscope_rmb={total['embed']:.4f}")
    print(f"total_offpeak_rmb={total['offpeak'] + total['embed']:.4f}")
    print(f"total_peak_rmb={total['peak'] + total['embed']:.4f}")


if __name__ == "__main__":
    main()
