"""Score public endpoint predictions with observed retained-fact annotations."""
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from real_content import jsonl
from orphan import HERE, read, scores, write


def combined(observed, prediction):
    assert prediction["text_sha256"] == observed["output_sha256"]
    return dict(observed, **prediction)


def report(rows):
    data = scores(rows)
    data["n"] = len(rows)
    data["median_cpu_seconds"] = statistics.median(r["seconds"] for r in rows)
    data["positive_issue_exact_n"] = sum(bool(r["supported_release_ids"]) for r in rows)
    data["positive_issue_exact"] = sum(bool(r["supported_release_ids"])
                                        and set(r["release_ids"]) == set(r["supported_release_ids"]) for r in rows)
    data["multi_source_n"] = sum(len(r["compatible_source_ids"]) > 1 for r in rows)
    data["multi_source_exact"] = sum(len(r["compatible_source_ids"]) > 1
                                     and set(r["source_ids"]) == set(r["compatible_source_ids"]) for r in rows)
    return data


def draw(data, controlled):
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(11.2,4.4),layout="constrained")
    labels = ["MinHash","BGE","BGE + rerank","M1","M1 ∩ BGE","M2","M3"]
    methods = ["minhash","bge","bge_rerank","M1","M1_bge_intersection","M2","M3"]
    indices = list(range(len(methods)))
    values = []
    for name in methods:
        variant = "M1" if name in ("minhash","bge","bge_rerank") else (
            "M1" if name=="M1_bge_intersection" else name)
        values.append(data[name][variant])
    for offset,label,key,color in ((-.18,"Source", "source","#285a7c"),
                                   (.18,"Release","release","#a75937")):
        ys = [row[key]["f1"] for row in values]
        ax.bar([i+offset for i in indices],ys,width=.34,color=color,label=label)
    ax.set(ylim=(0,1.02), xticks=indices,xticklabels=labels,ylabel="Micro-F1",
           title="Real relay pilot · 45 endpoints per variant")
    ax.tick_params(axis="x",rotation=23,labelsize=8)
    ax.legend()
    ax.text(.01,.98,"Content baselines use the same raw endpoints as M1",transform=ax.transAxes,va="top",fontsize=8)
    gold = controlled["metrics"]["release"]
    labels = ["Supported\nrecovered","Supported\nmissed","Unsupported\nattributed"]
    bars = bx.bar(labels,[gold["tp"],gold["fn"],gold["fp"]],color=["#285a7c","#a75937","#747474"])
    bx.bar_label(bars,padding=4)
    bx.set(title="Visible signature · 414 controlled endpoints",ylabel="Release labels",ylim=(0,520))
    bx.text(.01,.98,"2 carrier events per release · 184 added UTF-8 bytes\nOriginal-line transport",transform=bx.transAxes,va="top",fontsize=8)
    for axis in (ax,bx):
        axis.spines[["right","top"]].set_visible(False)
        axis.grid(axis="y",alpha=.17)
        axis.set_axisbelow(True)
    fig.savefig(HERE / "real_and_signed_comparison.png",dpi=175)


def main():
    real = HERE.parent / "real/pilot"
    annotations = {(r["case_id"],r["variant"]):r for r in jsonl(real / "annotations.jsonl")}
    assert len(annotations) == 180
    rows = [combined(annotations[r["case_id"],r["variant"]], r)
            for r in jsonl(HERE / "real_content_predictions.jsonl")]
    m1_bge = {r["case_id"]:r for r in rows if r["method"]=="bge" and r["variant"]=="M1"}
    release_source = {r["release_id"]:r["source_id"]
                      for r in read(HERE.parents[1]/"hsw_provenance/propagation/releases.json")}
    for result in read(HERE.parent / "real_decode_results.json")["predictions"]:
        case_id,variant = result["case_id"],result["variant"]
        gold = annotations[case_id,variant]
        assert set(result["gold_release"]) == set(gold["supported_release_ids"])
        rows.append(dict(gold,method=result["method"],seconds=result["seconds"],
                         source_ids=result["pred_source"],release_ids=result["pred_release"]))
        if result["method"]=="M1" and variant=="M1":
            baseline = m1_bge[case_id]
            compatible = set(baseline["source_ids"])
            supported = [release for release in result["pred_release"]
                         if release_source[release] in compatible]
            rows.append(dict(gold,method="M1_bge_intersection",seconds=result["seconds"]+baseline["seconds"],
                             source_ids=sorted({release_source[r] for r in supported}),release_ids=supported))
    summaries = {}
    unique = set()
    for row in rows:
        key = (row["method"],row["case_id"],row["variant"])
        assert key not in unique,key
        unique.add(key)
    for method in sorted({r["method"] for r in rows}):
        method_rows = [r for r in rows if r["method"]==method]
        summaries[method] = {}
        for variant in sorted({r["variant"] for r in method_rows}):
            group = [r for r in method_rows if r["variant"]==variant]
            summaries[method][variant] = dict(report(group),by_transform={
                transform:report([r for r in group if r["transform"]==transform])
                for transform in sorted({r["transform"] for r in group})},by_depth={
                depth:report([r for r in group if r["depth"]==depth])
                for depth in sorted({r["depth"] for r in group})})
    write(HERE / "real_comparison_metrics.json",summaries)
    controlled = read(HERE / "signed_controlled_summary.json")
    draw(summaries, controlled)
    for method in ("minhash","bge","bge_rerank","M1","M1_bge_intersection","M2","M3"):
        selected = summaries[method]["plain" if method in ("minhash","bge","bge_rerank") else (
            "M1" if method=="M1_bge_intersection" else method)]
        print(method,selected["n"],selected["source"],selected["release"])


if __name__ == "__main__":
    main()
