"""A2 control (PREREG_E3B2C.md): the same attack on the ORIGINAL template texts.

Same secrets, attack order, attacker (glm-5.2, temperature 0.7), prompt and
N = 5 samples as the main A2 run. Only the view text differs: the dataset's
own template sentence instead of the P1 paraphrase. V0 is shared with the
main run and is not repeated.
"""

from __future__ import annotations

import argparse

from experiments.capd_e3b2_20261124 import prompts as P
from experiments.capd_e3b2_20261124.attack import ATTACKER, ATTACKER_TEMPERATURE, attack_order
from experiments.capd_e3b2_20261124.common import Client, out_dir, read_jsonl, write_jsonl


def run(items_name: str) -> None:
    items = {i["target_id"]: i for i in read_jsonl(out_dir() / f"{items_name}.jsonl")}
    client = Client(ATTACKER)
    rows = []
    for tid in attack_order(items.values()):
        item = items[tid]
        views = item["views"]
        jobs = [dict(messages=P.attack_messages(item["candidates"], v["text"]),
                     temperature=ATTACKER_TEMPERATURE, sample=s, max_tokens=200)
                for v in views for s in range(P.ATTACK_SAMPLES)]
        replies = client.map(jobs)
        pairs = [(v, s) for v in views for s in range(P.ATTACK_SAMPLES)]
        for (v, sample), reply in zip(pairs, replies):
            parsed = P.parse_attack(reply["content"]) if reply["ok"] else None
            rows.append({
                "target_id": tid, "view_id": v["text_id"], "view_type": v["role"],
                "sample": sample, "valid": parsed is not None,
                "choice": parsed["choice"] if parsed else "",
                "hit": int(parsed["choice"] == item["truth_index"]) if parsed else "",
                "p_true": round(parsed["probs"][item["truth_index"] - 1], 6) if parsed else "",
                "consistent": v["consistent"],
            })
    write_jsonl(out_dir() / f"{items_name}_control_attack.jsonl", rows)
    print(f"{items_name}: {len(rows)} control samples, {sum(not r['valid'] for r in rows)} invalid")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", default="items")
    run(parser.parse_args().items)


if __name__ == "__main__":
    main()
