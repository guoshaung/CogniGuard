"""Plot the controlled source and core-fact retention through relay depth."""
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt

from build import HERE, ROOT

LABELS = {
    "forward": ("Forward", "o", "#2363A6"),
    "light_rewrite": ("Light rewrite", "s", "#4A7085"),
    "strong_rewrite": ("Strong rewrite", "^", "#12725B"),
    "summary": ("Summary", "D", "#B25719"),
    "truncate": ("Truncate", "v", "#8D3257"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-dir", type=Path, default=HERE)
    parser.add_argument("--out", type=Path, default=ROOT/"var/results/hsw-st/provenance_20261124/controlled_retention.png")
    args = parser.parse_args()
    config = json.loads((args.in_dir/"config.json").read_bytes())
    rows = json.loads((args.in_dir/"retention.json").read_bytes())
    fig, axes = plt.subplots(1,2,figsize=(9.4,3.85),sharey=True)
    for transform, (label, marker, color) in LABELS.items():
        selected = sorted((row for row in rows if row["transform"] == transform), key=lambda row:row["depth"])
        depth = [row["depth"] for row in selected]
        for metric, axis in zip(("fact_fidelity","source_retention"),axes,strict=True):
            axis.plot(depth,[100*row[metric] for row in selected],label=label,marker=marker,
                      markersize=6,fillstyle="none",color=color,linewidth=1.5,
                      linestyle="--" if transform == "light_rewrite" else "-")
    axes[0].set_title("Core knowledge facts")
    axes[1].set_title("Sources with surviving facts")
    axes[0].set_ylabel("Mean retained (%)")
    for axis in axes:
        axis.set(xticks=[1,3,5],yticks=[0,25,50,75,100],ylim=(-4,105),xlabel="Relay depth")
        axis.grid(axis="y",alpha=.18)
        axis.spines[["top","right"]].set_visible(False)
    fig.suptitle(f"Controlled OpenStax propagation | {config['source_count']} sources")
    fig.legend(*axes[0].get_legend_handles_labels(),loc="lower center",ncol=5,frameon=False,
               bbox_to_anchor=(.5,.035))
    fig.subplots_adjust(bottom=.24,wspace=.18,top=.80)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(args.out,dpi=200,bbox_inches="tight",facecolor="white")
    print(args.out)


if __name__ == "__main__":
    main()
