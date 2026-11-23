"""Paraphrase every selected text once with each paraphrase model (P1, P2)."""

from __future__ import annotations

import argparse

from experiments.capd_e3b2_20261124 import prompts as P
from experiments.capd_e3b2_20261124.common import Client, out_dir, read_jsonl, write_jsonl

PARAPHRASERS = ("deepseek-flash", "qwen3.7-plus")


def run(items_name: str) -> None:
    items = read_jsonl(out_dir() / f"{items_name}.jsonl")
    texts = [(item["target_id"], v) for item in items for v in item["views"]]
    rows = []
    for model in PARAPHRASERS:
        client = Client(model)
        replies = client.map([
            dict(messages=P.paraphrase_messages(v["text"]), temperature=P.PARAPHRASE_TEMPERATURE,
                 sample=0, max_tokens=200)
            for _, v in texts
        ])
        for (tid, v), reply in zip(texts, replies):
            content = (reply["content"] or "").strip() if reply["ok"] else None
            rows.append({"target_id": tid, "text_id": v["text_id"], "role": v["role"],
                         "paraphraser": model, "ok": bool(content), "text": content,
                         "error": reply["error"]})
    write_jsonl(out_dir() / f"{items_name}_paraphrases.jsonl", rows)
    print(items_name, len(rows), "paraphrases,", sum(not r["ok"] for r in rows), "missing")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", default="items")
    args = parser.parse_args()
    run(args.items)


if __name__ == "__main__":
    main()
