"""Render the provenance comparison used in the group meeting."""
import json
from pathlib import Path

import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent


def main():
    pilot = json.loads((HERE/"evaluation.json").read_bytes())
    expanded = json.loads((HERE/"evaluation_38.json").read_bytes())
    fig, (source, release) = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    categories = ("MinHash", "BGE", "Same lexical\nretrieval")
    methods = ("minhash", "bge", "Same lexical retrieval, unmarked")
    positions = range(len(methods))
    for index, (batch, label, color) in enumerate(((pilot, "12 sources", "#21618C"),
                                                  (expanded, "38 sources", "#758494"))):
        source.bar([i+(.33*index-.165) for i in positions],
                   [batch[k]["total"]["source"]["f1"] for k in methods], .30,
                   label=label, color=color)
        depths = (1, 3, 5)
        recall = [100*batch["BGE + HSW-prefix"]["depth"][str(d)]["release"]["recall"] for d in depths]
        release.plot(depths, recall, "o-", color=color, label=label)
        for d, y in zip(depths, recall, strict=True):
            release.annotate(f"{y:.1f}", (d, y), xytext=(0, 6 if index==0 else -14),
                             textcoords="offset points", ha="center", fontsize=8)
    source.set(xticks=list(positions), xticklabels=categories, ylim=(0, 1.05), ylabel="Micro-F1",
               title="Source identification")
    release.set(xticks=(1, 3, 5), xlabel="Relay hops", ylabel="Release recall (%)",
                ylim=(-3, 54), title="Issuance recovery with a marker")
    release.axhline(0, ls=":", color="black", label="Content only")
    for ax in (source, release):
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False, fontsize=8)
    fig.suptitle("Knowledge provenance · controlled held-out relays")
    fig.supxlabel("414 / 1,288 test endpoints · recall is conditional on retained facts", fontsize=9)
    fig.savefig(HERE/"provenance_pilot.png", dpi=190)


if __name__ == "__main__":
    main()
