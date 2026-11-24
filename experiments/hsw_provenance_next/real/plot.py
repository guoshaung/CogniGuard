"""Plot independently reviewed core-fact retention for the 5090 pilot."""
import json
from pathlib import Path
from statistics import mean

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

HERE = Path(__file__).resolve().parent
COLORS = {"plain":"#333333", "M1":"#B25719", "M2":"#2463A6", "M3":"#12725B"}
TRANSFORMS = ("summary", "light_rewrite", "strong_rewrite")


def main():
    rows = [json.loads(line) for line in (HERE/"pilot/annotations.jsonl").read_text(encoding="utf8").splitlines()]
    fig, axes = plt.subplots(1,3,figsize=(10,3.6),sharey=True)
    for transform, axis in zip(TRANSFORMS,axes,strict=True):
        for variant, color in COLORS.items():
            scores = [
                mean(row["fact_fidelity"] for row in rows
                     if (row["transform"],row["variant"],row["depth"])==(transform,variant,depth))
                for depth in (1,3,5)
            ]
            axis.plot((1,3,5),scores,color=color,label=variant,marker="o",markersize=4,linewidth=1.25,
                      linestyle="--" if variant=="plain" else "-")
        axis.set_title(transform.replace("_"," ").title())
        axis.set(xticks=[1,3,5],ylim=(0,1.05),xlabel="Relay depth")
        axis.grid(axis="y",alpha=.2)
        axis.spines[["top","right"]].set_visible(False)
    axes[0].set_ylabel("Mean core facts retained")
    axes[0].yaxis.set_major_formatter(PercentFormatter(1.0))
    fig.suptitle("Qwen2.5-7B paired relay pilot | three paths per operation")
    fig.legend(*axes[0].get_legend_handles_labels(),loc="lower center",ncol=4,frameon=False)
    fig.subplots_adjust(bottom=.24,top=.76)
    fig.savefig(HERE/"pilot/fact_retention.png",dpi=200,bbox_inches="tight",facecolor="white")


if __name__=="__main__":
    main()
