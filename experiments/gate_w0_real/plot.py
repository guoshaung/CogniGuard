"""Draw held-out fragment coverage and supported issuance recall."""
from pathlib import Path
import json
import matplotlib.pyplot as plt

here = Path(__file__).resolve().parent / "results"
rows = json.loads((here/"summary.json").read_bytes())
methods = ["minhash","bm25","bge","bge_rerank","kbpw","joint"]
labels = ["MinHash","BM25","BGE","BGE + TinyBERT","KBPW","Joint"]
fig, axes = plt.subplots(2, 3, figsize=(12, 6), layout="constrained")
for column, kind in enumerate(("random","sentence_end","model_summary")):
    for method,label in zip(methods,labels,strict=True):
        points = [r for r in rows if r["method"]==method and r["kind"]==kind]
        xs = [r["length"] for r in points]
        axes[0,column].plot(xs,[r["asset"]["raw_coverage"] for r in points],"o-",label=label)
        if method in ("kbpw","joint"):
            axes[1,column].plot(xs,[r["issuance"]["recall"] for r in points],
                                "o-" if method=="kbpw" else "x--",label=label)
    axes[0,column].set_title(kind.replace("_"," ").title())
    for ax in axes[:,column]:
        ax.set(xticks=[5,20,50,100],ylim=(-.04,1.04),xlabel="Word budget")
        ax.grid(axis="y", alpha=.2)
axes[0,0].set_ylabel("Asset prediction coverage")
axes[1,0].set_ylabel("Supported issuance recall")
axes[0,2].legend(fontsize=7)
axes[1,2].legend(fontsize=8)
fig.suptitle("Frozen KBPW detector on held-out fragments")
fig.savefig(here/"fragment_length.png", dpi=180)
