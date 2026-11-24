"""Summarize completed chronological decoding chains and plot the smoke trial."""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    directory = parser.parse_args().run
    config = json.loads((directory / "config.json").read_text(encoding="utf8"))
    rows = [json.loads(line) for line in (directory / "results.jsonl").read_text(encoding="utf8").splitlines()]
    assert len(rows) == len(config["bias"]) * config["hops"] * config["trials"]
    by_setting = defaultdict(list)
    for row in rows:
        by_setting[(row["delta"],row["hop"])].append(row)
    summary = []
    for (delta, hop), subset in sorted(by_setting.items()):
        summary.append(dict(delta=delta, hop=hop, trials=len(subset),
                            prefix_exact=sum(r["prefix_exact"] for r in subset),
                            symbol_accuracy=mean(r["accuracy"] for r in subset),
                            mean_hop_seconds=mean(r["hop_seconds"] for r in subset)))
    fig, ax = plt.subplots(figsize=(6.5, 3.7))
    for delta in config["bias"]:
        points = [p for p in summary if p["delta"]==delta]
        ax.plot([p["hop"] for p in points], [p["symbol_accuracy"] for p in points],
                marker="o", label=f"Logit bias {delta:g}")
    ax.set(title=f"Chronicle feedback smoke · {config['trials']} chains per setting",
           xlabel="Generation hop", ylabel="Prefix symbol accuracy",
           xticks=range(1, config["hops"]+1), ylim=(-.05,1.05))
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(directory / "chronology_smoke.png",dpi=160)
    with (directory / "summary.json").open("x",encoding="utf8") as stream:
        json.dump(dict(cells=summary, model=config["model"], hardware=config["device"],
                       gpu_hours=0 if config["device"]=="cpu" else None,
                       total_generation_seconds=sum(r["hop_seconds"] for r in rows)),
                  stream, indent=2)


if __name__ == "__main__":
    main()
