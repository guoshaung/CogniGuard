"""Attacker A on V0 and on the P1 paraphrases, N samples per (secret, view).

Secrets are attacked in a fixed, pre-registered order (seeded shuffle). Before
each secret the projected spend is checked; the run stops before the first
secret that would push the total over the cap.
"""

from __future__ import annotations

import argparse
import random

from experiments.capd_e3b2_20261124 import prompts as P
from experiments.capd_e3b2_20261124.budget import CAP_YUAN, call_cost, total_spent
from experiments.capd_e3b2_20261124.common import Client, out_dir, read_jsonl, write_jsonl

ATTACKER = "kimi-k3"
ATTACKER_TEMPERATURE = None  # kimi-k3 rejects 0.7 on Bailian; the platform default is used
VIEW_SOURCE = "deepseek-flash"  # P1 paraphrases are the attacked views
ORDER_SEED = "2026/attack-order"
SAFETY_YUAN = 1.0


def attack_order(items) -> list[str]:
    ids = sorted(item["target_id"] for item in items)
    random.Random(ORDER_SEED).shuffle(ids)
    return ids


def views_for(item, paraphrases) -> list[dict]:
    views = [{"view_id": f"{item['target_id']}-V0", "view_type": "V0", "text": None,
              "consistent": 8, "gold_units": []}]
    for v in item["views"]:
        para = paraphrases.get((v["text_id"], VIEW_SOURCE))
        if para is None:
            continue  # a missing paraphrase stays missing; no other model fills it
        views.append({"view_id": v["text_id"], "view_type": v["role"], "text": para,
                      "consistent": v["consistent"], "gold_units": v["gold_units"]})
    return views


RETRY_ERROR = "Access denied, please make sure your account is in good standing"


def run(items_name: str, cap: float, retry_denied: bool = False) -> None:
    items = {i["target_id"]: i for i in read_jsonl(out_dir() / f"{items_name}.jsonl")}
    paraphrases = {(r["text_id"], r["paraphraser"]): r["text"]
                   for r in read_jsonl(out_dir() / f"{items_name}_paraphrases.jsonl") if r["ok"]}
    client = Client(ATTACKER, retry_error=RETRY_ERROR if retry_denied else None)
    rows, done, stopped = [], [], None
    per_call = None
    for tid in attack_order(items.values()):
        item = items[tid]
        views = views_for(item, paraphrases)
        jobs = [dict(messages=P.attack_messages(item["candidates"], view["text"]),
                     temperature=ATTACKER_TEMPERATURE, sample=s, max_tokens=200)
                for view in views for s in range(P.ATTACK_SAMPLES)]
        fresh = sum(client.key(j["messages"], j["temperature"], j["sample"]) not in client.cache
                    for j in jobs)
        estimate = fresh * (per_call or 0.025)
        if total_spent() + estimate + SAFETY_YUAN > cap:
            stopped = tid
            break
        replies = client.map(jobs)
        costs = [call_cost(ATTACKER, r["usage"]) for r in replies if r["ok"]]
        if costs:
            per_call = max(per_call or 0, sum(costs) / len(costs))
        for (view, sample), reply in zip(
            [(view, s) for view in views for s in range(P.ATTACK_SAMPLES)], replies
        ):
            parsed = P.parse_attack(reply["content"]) if reply["ok"] else None
            rows.append({
                "target_id": tid, "view_id": view["view_id"], "view_type": view["view_type"],
                "sample": sample, "valid": parsed is not None,
                "choice": parsed["choice"] if parsed else "",
                "hit": int(parsed["choice"] == item["truth_index"]) if parsed else "",
                "p_true": round(parsed["probs"][item["truth_index"] - 1], 6) if parsed else "",
                "consistent": view["consistent"],
            })
        done.append(tid)
    write_jsonl(out_dir() / f"{items_name}_attack.jsonl", rows)
    print(f"{items_name}: attacked {len(done)} secrets, {len(rows)} samples, "
          f"{sum(not r['valid'] for r in rows)} invalid; stopped before {stopped}; "
          f"spent {total_spent():.2f} yuan")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", default="items")
    parser.add_argument("--cap", type=float, default=CAP_YUAN)
    parser.add_argument("--retry-denied", action="store_true",
                        help="call again only where the account was suspended (overdue)")
    args = parser.parse_args()
    run(args.items, args.cap, args.retry_denied)


if __name__ == "__main__":
    main()
