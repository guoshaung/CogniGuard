"""Publish T6 results with distinct planned, completed, and scored denominators."""
import argparse
import csv
import json
import random
import statistics
from collections import Counter
from pathlib import Path

from t6_sources import HERE, OUT, ROOT, load, write

C=OUT/"stage_c_embedding"
B=OUT/"stage_b_generation"
D=OUT/"stage_d_model_arms"
A=OUT/"cpu_controls"
S=OUT/"scores"
P=OUT/"postmark"
METHODS=("OPT","GREEDY-dyn","RC","Fingerprint","KGW","Unigram","PostMark")
CONDITIONS=("none","ocr","crop_first100","crop_middle100","crop_last100","crop_first200","crop_middle200","compress70")


def lines(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


def optional(path,default=None):
    return load(path) if path.exists() else default


def k_n(k,n):
    return {"k":k,"n":n}


def pct(cell):
    if cell is None:
        return "NOT_RUN"
    k,n=cell["k"],cell["n"]
    return f"{k}/{n}（{k/n:.2%}）" if n else "N/A"


def paired_cost(arms):
    rows=[(r["arms"]["GREEDY-dyn"],r["arms"]["OPT"]) for r in arms
          if all(a["success"] and a.get("dynamic_total_cost") is not None for a in r["arms"].values())]
    changes=[a["dynamic_total_cost"]-b["dynamic_total_cost"] for a,b in rows]
    if not rows:
        return None
    rng=random.Random(20261116)
    bootstrap=sorted(statistics.fmean(rng.choices(changes,k=len(rows))) for _ in range(2000))
    reference=statistics.fmean(a["dynamic_total_cost"] for a,_ in rows)
    return {"n":len(rows),"mean_saving":statistics.fmean(changes),
            "relative_saving":statistics.fmean(changes)/reference if reference>0 else None,
            "ci95":[bootstrap[49],bootstrap[1949]],
            "mean_insertions":dict(zip(("GREEDY-dyn","OPT"),
                (statistics.fmean(pair[i]["insertions"] for pair in rows) for i in (0,1)),strict=True))}


def coverage(rows,method):
    values=[r["arms"][method] for r in rows]
    return {"coverage":k_n(sum(a["success"] for a in values),len(values)),
            "statuses":dict(Counter(a["status"] for a in values)),
            "certificate":k_n(sum(a.get("certificate") is True for a in values),
                              sum(a.get("certificate") is not None for a in values)),
            "independent_verified":k_n(sum(a.get("independent_verified") is True for a in values),
                                       sum(a.get("independent_verified") is not None for a in values))}


def score_counts(rows,method,planned):
    result={}
    for condition in CONDITIONS:
        values=[r for r in rows if r["method"]==method and r["condition"]==condition]
        if not values:
            result[condition]=None
            continue
        usable=[r for r in values if isinstance(r.get("detected"),bool)]
        rec=[r for r in values if r.get("fingerprint_status")]
        intact=[r for r in values if isinstance(r.get("number_formula_intact"),bool)]
        result[condition]={
            "detected":k_n(sum(r["detected"] for r in usable),len(usable)),
            "predicted_sources":dict(Counter(r["fingerprint_status"] for r in rec)),
            "fingerprint_total":len(rec),"planned":planned,"scored_rows":len(values),
            "failure_states":dict(Counter(r["status"] for r in values if r["status"]!="SCORED")),
            "intact":k_n(sum(r["number_formula_intact"] for r in intact),len(intact)),
        }
    return result


def frequency(data):
    groups={}
    for r in data["rows"]:
        key=(r["method"],r["N"],r["m"],r["attack"])
        if key not in groups:
            groups[key]=[]
        groups[key].append(r)
    return {"conditions":data["conditions"],"counts":{
        "|".join(map(str,key)):{"accepted":k_n(sum(r.get("detected") is True for r in rows),
                                              sum(isinstance(r.get("detected"),bool) for r in rows)),
                                "planned":len(rows),"total_edits":sum(r["edits"] for r in rows)}
        for key,rows in sorted(groups.items())}}


def result_doc(x):
    cov=x["coverage"]
    lines=[
        "# EVAL-04-FINAL T6","",
        f"本件运行状态 **{x['run_status']}**。原始讲解计划 200 篇，终止方式为 {x['generation']['finish_reasons']}。",
        f"OPT 成功 {pct(cov['OPT']['coverage'])}，GREEDY-dyn 成功 {pct(cov['GREEDY-dyn']['coverage'])}。"
        f"共同成功 {x['success_overlap']['common']} 篇，成功并集 {x['success_overlap']['union']} 篇。",
        "",
        "|方法|计划运行|完成的生成或已复检输出|无攻击检出|首100|中100|OCR|压缩70%|",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        info=x["method_status"][method]
        metrics=x["detection"][method]
        cells=[pct(metrics[tag]["detected"] if metrics.get(tag) else None) for tag in
               ("none","crop_first100","crop_middle100","ocr","compress70")]
        lines.append(f"|{method}|{info['planned']}|{info['completed'] or 0}|"+"|".join(cells)+"|")
    lines+=["",
            "检测分母是相应扰动下实际可计分文本。指纹统一按正确归属、错归属、并列和拒识记录在 JSON，按来源归属定义解释。",
            "",
            f"人审准备状态为 {x['human_review']['status']}，两份各 40 篇，收到标签 {x['human_review']['labels_collected']} 条。",
            "对照、盲评、误报和频率学习沿用冻结的补充协议。词表规模曲线和 D-multi 的状态为 NOT_AVAILABLE。",
            "",
            "逐项记录包含真实检测分数、插入证书检查、自然度分数、失败状态与来源分母。缺失指标保留空值。"]
    if x["paired_dynamic_cost"]:
        a=x["paired_dynamic_cost"]
        share=f"{a['relative_saving']:.2%}" if a['relative_saving'] is not None else "N/A"
        lines+=["",f"共同成功的 {a['n']} 篇中，OPT 的动态复评代价平均降低 {a['mean_saving']:.3f} log-prob 单位"
                     f"（相对降幅 {share}，差值 95% 区间 [{a['ci95'][0]:.3f}, {a['ci95'][1]:.3f}]）。"]
    if x["pending"]:
        lines+=["","## 待完成项",""]
        lines+=["- "+item for item in x["pending"]]
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint",action="store_true")
    args=p.parse_args()
    primary_manifest=load(HERE/"T6_EMBED_RESULT.json")
    arms=lines(C/"verified.local.jsonl")
    assert len(arms)==primary_manifest["planned"]==200
    b=load(B/"RESULT.json")
    v=optional(S/"all_variants.json") or optional(S/"primary_variants.json",{"rows":[]})
    fpr=optional(A/"fpr.json")
    baselines_fpr=optional(S/"baseline_fpr.json")
    p1=optional(S/"all_frequency.json") or optional(S/"primary_frequency.json")
    baselines=optional(D/"baseline/RESULT.json")
    post=optional(P/"RESULT.json")
    human=optional(A/"human_review.json",{"status":"NOT_RUN","labels_collected":0})
    rc=optional(A/"rc.json",{"coverage":k_n(0,0)})
    known=load(HERE/"T6_BASELINE_UNION.json")
    by_method={
        method:{"planned":200,"completed":primary_manifest["success"][method]} for method in ("OPT","GREEDY-dyn")
    }
    by_method["RC"]={"planned":200,"completed":rc["coverage"]["k"]}
    by_method["Fingerprint"]={"planned":200,"completed":sum(x["status"]=="COMPLETED" for x in b["rows"])}
    for m in ("KGW","Unigram"):
        recorded=(baselines or {"results":[]})["results"]
        by_method[m]={"planned":known["planned_per_method"],
                      "completed":sum(r.get("method")==m and r["status"]=="COMPLETED" for r in recorded)}
    by_method["PostMark"]={"planned":200,"completed":sum(r["status"]=="COMPLETED"
                                                       for r in (post or {"rows":[]})["rows"])}
    source_counts={}
    for subject in sorted({r["subject"] for r in arms}):
        selected=[r for r in arms if r["subject"]==subject]
        source_counts[subject]={m:coverage(selected,m)["coverage"] for m in ("OPT","GREEDY-dyn")}
    coverage_by_length={}
    for label,low,high in (("<100",0,99),("100–200",100,200),("201–400",201,400),(">400",401,100000)):
        chosen=[r for r in arms if low<=r.get("words",-1)<=high]
        coverage_by_length[label]={m:coverage(chosen,m)["coverage"] for m in ("OPT","GREEDY-dyn")}
    actual=optional(OUT/"score_registry.json") or optional(OUT/"score_registry_primary.json",{"items":[]})
    registry_counts=Counter(r["method"] for r in actual["items"])
    metrics={m:score_counts(v["rows"],m,registry_counts[m]) for m in METHODS}
    missing=[]
    for required,path in (
        ("KGW 和 Unigram 的完整执行记录",D/"baseline/RESULT.json"),
        ("PostMark 的完整执行记录",P/"RESULT.json"),
        ("全部变体的计分",S/"all_variants.json"),
        ("冻结频率学习的完整计分",S/"all_frequency.json"),
        ("随机密钥误报",A/"fpr.json"),
        ("基线固定阈值误报",S/"baseline_fpr.json"),
        ("OCR 执行记录",OUT/"ocr/RESULT.json"),
        ("70% 压缩执行记录",D/"compress/RESULT.json"),
    ):
        if not path.exists():missing.append(required)
    if not args.checkpoint and missing:
        raise RuntimeError("Unfinished required stages: "+", ".join(missing))
    formal={
        "run_status":"CHECKPOINT" if missing else "EVALUATED",
        "generation":{"planned":200,"finish_reasons":dict(Counter(str(r.get("finish_reason")) for r in b["rows"]))},
        "coverage":{m:coverage(arms,m) for m in ("OPT","GREEDY-dyn")},
        "coverage_by_subject":source_counts,"coverage_by_length":coverage_by_length,
        "paired_dynamic_cost":paired_cost(arms),
        "success_overlap":{"common":primary_manifest["common_success"],"union":primary_manifest["union"]},
        "method_status":by_method,"detection":metrics,"human_review":human,"pending":missing,
        "fpr":fpr["counts"] if fpr else None,
        "baseline_fpr":dict(Counter((r["dataset"]+"|"+r["method"]) for r in baselines_fpr["rows"] if r["detected"]))
          if baselines_fpr else None,"frequency":frequency(p1) if p1 else None,
        "lexicon_size_curve":"NOT_AVAILABLE","detection_multi":"NOT_AVAILABLE",
    }
    suffix="_CHECKPOINT" if args.checkpoint else ""
    write(HERE/f"figure_counts{suffix}.json",{"evaluation":"T6","T6":formal})
    out=[]
    for row in arms:
        for method,a in row["arms"].items():
            out.append({"kind":"embed","id":row["id"],"subject":row["subject"],"words":row.get("words"),
                        "method":method,"source_p":row.get("source_p"),**a})
    out += [dict(r,kind="variant") for r in v["rows"]]
    if p1:out += [dict(r,kind="frequency") for r in p1["rows"]]
    if fpr:out += [dict(r,kind="random_key_fpr") for r in fpr["rows"]]
    if baselines_fpr:out += [dict(r,kind="fixed_baseline_fpr") for r in baselines_fpr["rows"]]
    headers=list(dict.fromkeys(k for r in out for k in r))
    with (HERE/f"per_item{suffix}.csv").open("x",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=headers,lineterminator="\n")
        writer.writeheader()
        writer.writerows(out)
    with (HERE/f"RESULT{suffix}.md").open("x",encoding="utf-8",newline="\n") as f:
        f.write(result_doc(formal))
    print("T6",formal["run_status"],"evidence rows",len(out),"pending",missing,flush=True)


if __name__=="__main__":
    main()
