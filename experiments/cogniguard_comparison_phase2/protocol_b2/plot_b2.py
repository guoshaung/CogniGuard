"""B2 figure: detector quality and offline downstream effect of each control (held-out-excluded view is
the same within 0.01; the 'all' view is plotted). Logs are DIAGNOSTIC data, not a held-out set."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
B2 = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/protocol_b2")
OUT = Path(__file__).resolve().parents[1] / "results" / "protocol_b2"
d = json.loads((B2 / "diagnosis.json").read_text())
fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw={"width_ratios": [1, 1.6]}, facecolor=SURFACE)
ax = axes[0]
names = [("raw", "raw match"), ("norm", "normalized"), ("sem", "BGE+NLI (frozen)"), ("joint", "norm ∪ sem")]
for i, (k, lab) in enumerate(names):
    q = d["detection"][k]
    for j, (m, c) in enumerate((("precision", "#2a78d6"), ("recall", "#eb6834"), ("f1", "#1baf7a"))):
        ax.bar(i + (j - 1) * 0.25, q[m], width=0.25, color=c, edgecolor=SURFACE, label=m if i == 0 else None, zorder=2)
ax.set_xticks(range(len(names)))
ax.set_xticklabels([n for _, n in names], fontsize=8)
ax.set_ylim(0, 1.05)
ax.set_title("Knowledge detection vs gold (576 answers)", fontsize=9, color=INK)
ax.legend(fontsize=7, frameon=False)
ax2 = axes[1]
ctr = [k for k in d["downstream"] if k.endswith("[all]")]
labels = [k.replace(" [all]", "") for k in ctr]
h = [d["downstream"][k]["harmful_rate"] for k in ctr]
o = [d["downstream"][k]["over_refusal"] for k in ctr]
y = range(len(ctr))
ax2.barh([i + 0.2 for i in y], h, height=0.38, color="#eb6834", label="harmful release (offline)", zorder=2)
ax2.barh([i - 0.2 for i in y], o, height=0.38, color="#2a78d6", label="over-refusal (offline)", zorder=2)
ax2.axvline(d["downstream"][ctr[0]]["harmful_rate_cot"], color=MUTED, linestyle="--", linewidth=1)
ax2.text(d["downstream"][ctr[0]]["harmful_rate_cot"] + 0.01, -0.55, "no defense (CoT)", fontsize=7, color=MUTED)
ax2.set_yticks(list(y))
ax2.set_yticklabels(labels, fontsize=7.5)
ax2.invert_yaxis()
ax2.set_xlim(0, 0.75)
ax2.set_title("Offline gate replay on ungated CoT trajectories (CA-PD kernel unchanged)", fontsize=9, color=INK)
ax2.legend(fontsize=7, frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.22), ncol=2)
for x in axes:
    x.set_facecolor(SURFACE)
    for s in ("top", "right"):
        x.spines[s].set_visible(False)
    x.tick_params(colors=MUTED, labelsize=7)
    x.set_axisbelow(True)
axes[0].yaxis.grid(True, color=GRID)
ax2.xaxis.grid(True, color=GRID)
fig.suptitle("Protocol B2: where the CogniGuard gate fails (diagnostic data, not held-out)", fontsize=10.5, color=INK,
             x=0.01, ha="left")
fig.tight_layout(rect=(0, 0, 1, 0.93))
OUT.mkdir(parents=True, exist_ok=True)
for ext in ("png", "svg"):
    fig.savefig(OUT / f"fig5_protocol_b2.{ext}", dpi=200, facecolor=SURFACE)
print(OUT)
