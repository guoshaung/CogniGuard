"""Plot held-out retrieval results and quantify attribution to dropped sources."""
import argparse
from collections import Counter
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from run import jsonl, save_json

LABELS = {
    "sha256":"SHA-256", "minhash":"MinHash", "bm25":"BM25",
    "bge":"BGE", "bge_rerank":"BGE + rerank", "issuance_lookup":"Issuance lookup",
    "active_variants":"Active variants",
}


def dropped_sources(rows, cases):
    counts = Counter()
    for row in rows:
        case = cases[row["case_id"]]
        present = set(case["retained_source_ids"])
        upstream = set(case["input_source_ids"])
        predicted = set(row["source_ids"])
        counts["known_source_labels_dropped"] += len(upstream-present)
        counts["dropped_labels_attributed"] += len(predicted & (upstream-present))
        counts["unrelated_labels_attributed"] += len(predicted-upstream)
        counts["labels_attributed"] += len(predicted)
    counts["dropped_label_reattribution_rate"] = counts["dropped_labels_attributed"]/max(
        1, counts["known_source_labels_dropped"])
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args = parser.parse_args()
    summary = json.loads((args.out/"summary.json").read_bytes())
    cases = {case["case_id"]:case for case in jsonl(args.data/"cases.jsonl")}
    heldout = [row for row in jsonl(args.out/"predictions.jsonl") if row["split"]=="test"]
    audit = {method:dropped_sources([row for row in heldout if row["method"]==method],cases) for method in summary}
    save_json(args.out/"attribution_to_dropped_sources.json",audit)

    fig, axes = plt.subplots(1,2,figsize=(11,4.4),layout="constrained")
    ordered = sorted(summary,key=lambda m:summary[m]["test"]["source"]["f1"])
    x = [summary[m]["test"]["source"]["f1"] for m in ordered]
    axes[0].barh([LABELS[m] for m in ordered],x,color="#4b72a1")
    axes[0].set(xlim=(0,1),xlabel="Micro-F1",title="Sources with retained teaching facts")
    for line,score in enumerate(x):
        axes[0].text(score+.015,line,f"{score:.3f}",va="center",fontsize=8)
    for method, color in (("minhash","#21618c"),("bge","#14866d"),("bm25","#934b28"),
                          ("active_variants","#7656a0"),("bge_rerank","#737373")):
        series = summary[method]["by_depth"]
        depth = sorted(map(int,series))
        axes[1].plot(depth, [series[str(d)]["source"]["recall"] for d in depth],
                     marker="o",color=color,label=LABELS[method])
    axes[1].set(xlabel="Relay depth (hops)",ylabel="Source recall",ylim=(.5,1.03),
                xticks=[1,3,5],title="Source recall after propagation")
    axes[1].legend(fontsize=8, loc="lower left")
    for ax in axes:
        ax.spines[["top","right"]].set_visible(False)
        ax.grid(axis="x" if ax==axes[0] else "y",alpha=.22)
        ax.set_axisbelow(True)
    fig.suptitle("OpenStax controlled provenance pilot  |  414 held-out endpoints",fontsize=13,weight="bold")
    fig.savefig(args.out/"source_baselines.png",dpi=190)
    fig.savefig(args.out/"source_baselines.svg")


if __name__ == "__main__":
    main()
