"""Recompute and publish the development comparison from recorded outputs."""
import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE.parents[1]/"var/results/hsw-st/certinsert_eval04_matching_20261115"
METHODS=("GREEDY-dyn","GREEDY-fix","OPT")
GROUPS=("generated","textbook")
BANDS=("<100","100–200","201–400",">400")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def count(k,n):
    return {"k":k,"n":n}


def rate(k,n):
    return k/n if n else None


def display(row):
    k,n=row["k"],row["n"]
    return f"{k}/{n} ({k/n:.2%})" if n else "0/0 (N/A)"


def band(words):
    return BANDS[0 if words<100 else 1 if words<=200 else 2 if words<=400 else 3]


def distribution(values):
    if not values:
        return None
    s=sorted(values)
    quantiles={str(q):s[round(q*(len(s)-1))] for q in (0,.025,.25,.5,.75,.975,1)}
    return {"n":len(s),"mean":statistics.fmean(s),"quantiles":quantiles}


def interval(samples):
    if len(samples)<2:
        return None
    rng=random.Random(20261115)
    values=sorted(statistics.fmean(rng.choices(samples,k=len(samples))) for _ in range(2000))
    return [values[49],values[1949]]


def summarize(rows,method):
    arms=[r["arms"][method] for r in rows]
    good=[a for a in arms if a["success"]]
    audited=[a for a in arms if "certificate" in a]
    return {
        "coverage":count(len(good),len(rows)),
        "coverage_by_length":{
            label:count(sum(r["arms"][method]["success"] for r in rows if band(r["words"])==label),
                        sum(band(r["words"])==label for r in rows)) for label in BANDS},
        "statuses":dict(Counter(r["status"] for r in arms)),
        "insertions":dict(Counter(r["insertions"] for r in good)),
        "mean_insertions":statistics.fmean(r["insertions"] for r in good) if good else None,
        "certificate":count(sum(r["certificate"] for r in good),len(good)),
        "anchor_selection_invariance":count(sum(r["anchor_invariant"] and r["selection_invariant"] for r in good),len(good)),
        "attempted_certificate":count(sum(a["certificate"] for a in audited),len(audited)),
        "attempted_invariance":count(sum(a["anchor_invariant"] and a["selection_invariant"] and
                                         a["numeric_formula_intact"] for a in audited),len(audited)),
        "public_p_below_001":count(sum(r["p"]<.001 for r in good),len(good)),
        "unattacked":count(sum(r["p"]<.01 for r in good),len(good)),
        "crops":{name:count(sum(r.get(name+"_detected",False) for r in good),
                           sum(name+"_detected" in r for r in good)) for name in ("first100","middle100")},
        "seconds_excluding_model":distribution([r["seconds_without_scoring"] for r in arms]),
        "natural_positive":sum(r["insertions"]==0 for r in good),
        "dynamic_rescore_missing":sum(r["dynamic_rescore_status"]!="OK" for r in good),
    }


def paired(rows,baseline):
    pairs=[(r["arms"][baseline],r["arms"]["OPT"]) for r in rows]
    both=[(a,b) for a,b in pairs if a["success"] and b["success"]]
    scored=[(a,b) for a,b in both if "dynamic_total_cost" in a and "dynamic_total_cost" in b]
    baseline_costs=[a["dynamic_total_cost"] for a,_ in scored]
    changes=[a["dynamic_total_cost"]-b["dynamic_total_cost"] for a,b in scored]
    maxima=[a["dynamic_max_cost"]-b["dynamic_max_cost"] for a,b in scored
            if a["dynamic_max_cost"] is not None and b["dynamic_max_cost"] is not None]
    gap=[c/a for c,a in zip(changes,baseline_costs,strict=True) if a>0]
    baseline_mean=statistics.fmean(baseline_costs) if scored else None
    return {
        "both_success":len(both),"paired_rescores":len(scored),
        "absolute_saving":distribution(changes),"absolute_saving_ci95":interval(changes),
        "max_cost_saving":distribution(maxima),"max_cost_saving_ci95":interval(maxima),
        "baseline_total_dynamic_cost":distribution(baseline_costs),
        "opt_total_dynamic_cost":distribution([b["dynamic_total_cost"] for _,b in scored]),
        "baseline_max_dynamic_cost":distribution([a["dynamic_max_cost"] for a,_ in scored if a["dynamic_max_cost"] is not None]),
        "opt_max_dynamic_cost":distribution([b["dynamic_max_cost"] for _,b in scored if b["dynamic_max_cost"] is not None]),
        "relative_gap_by_document":distribution(gap),"relative_gap_undefined":len(scored)-len(gap),
        "relative_mean_saving":statistics.fmean(changes)/baseline_mean if baseline_mean and baseline_mean>0 else None,
        "only_opt":dict(Counter(a["failure_category"] for a,b in pairs if b["success"] and not a["success"])),
        "only_baseline":sum(a["success"] and not b["success"] for a,b in pairs),
    }


def selection(summaries,comp,complete,verified):
    old,new=summaries["GREEDY-dyn"],summaries["OPT"]
    improvement=(new["coverage"]["k"]-old["coverage"]["k"])/300
    crop={}
    limits=[]
    for window in ("first100","middle100"):
        a,b=old["crops"][window],new["crops"][window]
        crop[window]=rate(**b)-rate(**a) if a["n"] and b["n"] else None
        limits.append(bool(a["n"] and b["n"] and
                           20*(b["k"]*a["n"]-a["k"]*b["n"])>=-a["n"]*b["n"]))
    ci=comp["absolute_saving_ci95"]
    relative=comp["relative_mean_saving"]
    criteria={"coverage_not_lower":improvement>=0,
              "coverage_at_least_3pp":improvement>=.03,
              "dynamic_cost":relative is not None and relative>=.10 and ci is not None and ci[0]>0,
              "two_crops":all(limits)}
    return dict(recommended=("OPT" if complete and verified and criteria["coverage_not_lower"] and
                              any(criteria[name] for name in ("coverage_at_least_3pp","dynamic_cost","two_crops"))
                              else "GREEDY-dyn"),coverage_delta=improvement,crop_delta=crop,
                criteria=criteria,complete=complete,oracle_verified=verified)


def publish_csv(rows):
    columns=["case_id","group","subject","words","candidate_edges","natural_hit_count","needed_hit_count",
             "structurally_feasible","fixed_scores_valid","score_tokens","brute","method","status","success",
             "insertions","attempted_insertions","fixed_table_cost","dynamic_rescore_status","dynamic_total_cost",
             "dynamic_max_cost","p","original_p","trial_p","certificate","anchor_invariant","selection_invariant","numeric_formula_intact",
             "first100_p","first100_detected","middle100_p","middle100_detected","seconds_without_scoring",
             "failure_category","context_cache_sha256","output_sha256"]
    with (HERE/"per_item.csv").open("x",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,lineterminator="\n",extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            for method in METHODS:
                writer.writerow({**row,**row["arms"][method],"case_id":row["id"],"group":row["cohort"],"method":method})


def lines_for_report(result):
    groups=result["groups"]
    proof=result["solver_checks"]
    decision=result["decision"]
    texts=[
        "# EVAL-04-M 开发结果","",
        f"**T6 建议采用 {decision['recommended']}。** 主口径为生成讲解上的 OPT 对 GREEDY-dyn。"
        "教材组和 GREEDY-fix 仅作为辅助对照。开发结果尚未启动 T6。",
        "", f"生成讲解与教材各 300 篇，打分前向 Token 共 {result['forward_tokens']:,}。"
        f"手算对照 {proof['hand_checks']}/5，真文档暴力枚举 {proof['brute_passed']}/50。",
        "",
        "## 实际覆盖与摘录","",
        "|文档组|方法|覆盖|<100|100–200|201–400|>400|全文检出|开头100|中段100|",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cohort,group in groups.items():
        for method,row in group["methods"].items():
            metrics=[row["coverage"],*row["coverage_by_length"].values(),row["unattacked"],*row["crops"].values()]
            texts.append(f"|{cohort}|{method}|"+"|".join(map(display,metrics))+"|")
    texts+=["","少于 100 词的成功输出不进入摘录分母。检测器、背景 q 和阈值沿用 EVAL-03，误报未重测。",
            "","## 插入、证书和求解","",
            "|组|方法|平均插入|插入数分布|预测达标尝试的证书|预测达标尝试的不变式|零插入成功|OPT超时|嵌入平均秒数|",
            "|---|---|---:|---|---:|---:|---:|---:|---:|"]
    def fmt(value):
        return f"{value:.6f}" if value is not None else "N/A"
    for cohort,group in groups.items():
        for method,row in group["methods"].items():
            texts.append(f"|{cohort}|{method}|{fmt(row['mean_insertions'])}|{row['insertions']}|"
                         f"{display(row['attempted_certificate'])}|{display(row['attempted_invariance'])}|"
                         f"{row['natural_positive']}|{row['statuses'].get('OPT_TIMEOUT',0)}|"
                         f"{fmt(row['seconds_excluding_model']['mean'])}|")
    texts+=["","耗时仅含选择和放置，独立复检、模型前向和缓存构建分开计算。覆盖只计逐字节恢复、公开 p 和原不变式均通过的结果。各状态分母见 JSON。",
            "","## 共同成功的原动态自然度复评","",
            "正差表示 OPT 成本更低。总代价与最大单处使用同一原文顺序和动态上下文。相对差只在冻结分母定义下使用。",
            "","|组|对照|完整配对/共同成功|平均总节省|95%区间|最大单处平均节省|相对平均节省|仅 OPT / 仅对照成功|",
            "|---|---|---:|---:|---|---:|---:|---:|"]
    for cohort,group in groups.items():
        for method,m in group["paired"].items():
            change=m["absolute_saving"]
            maxima=m["max_cost_saving"]
            rel=m["relative_mean_saving"]
            texts.append(f"|{cohort}|{method}|{m['paired_rescores']}/{m['both_success']}|{fmt(change['mean'] if change else None)}|"
                         f"{m['absolute_saving_ci95'] or 'N/A'}|{fmt(maxima['mean'] if maxima else None)}|"
                         f"{format(rel,'.2%') if rel is not None else 'N/A'}|{sum(m['only_opt'].values())}/{m['only_baseline']}|")
            if m["only_opt"]:
                texts.append(f"|{cohort}|{method} · 仅 OPT 成功的原因|—|—|—|—|—|{m['only_opt']}|")
    texts+=["","JSON 含逐篇相对差的分位数及不可定义的分母、两组各方法的成本分布、单处差的区间和失败分类。静态最优性与动态复评差异分别记录。",
            "", "## 选型门槛","",
            f"- OPT 相对 GREEDY-dyn 的覆盖差为 **{decision['coverage_delta']*100:+.2f} 个百分点**。",
            f"- 摘录差值（OPT 减原动态贪心）为 {decision['crop_delta']}。",
            f"- 冻结判定 {decision['criteria']}。",
            "- 原文、插入文本、逐边评分和密钥留在本机。发布表含实际 p 值、指标、求解状态和缓存哈希。",
            ""]
    return texts


def main():
    manifest=read(OUT/"run_manifest.json")
    run=read(OUT/"RUN.json")
    rows=list(map(json.loads,(OUT/"results.local.jsonl").read_text(encoding="utf-8").splitlines()))
    assert len(rows)==len({r["id"] for r in rows})==run["documents"]==600
    assert sum(r["score_tokens"] for r in rows)==run["forward_tokens"]
    checks={row["id"]:row for row in read(OUT/"output_check.json")}
    assert len(checks)==600
    for row in rows:
        replay=checks[row["id"]]
        row["original_p"]=replay["original_p"]
        for name in METHODS:
            arm=row["arms"][name]
            arm["trial_p"]=arm.get("p")
            arm["p"]=replay["outputs"][name]["p"]
            if arm["success"]:
                assert replay["outputs"][name]["replayed_certificate"] is True
    expected={r["id"]:r["cohort"] for r in manifest["ordered"]}
    assert {r["id"]:r["cohort"] for r in rows}==expected
    subsets={name:[r for r in rows if r["cohort"]==name] for name in GROUPS}
    assert all(len(data)==300 for data in subsets.values())
    groups={name:{"methods":{m:summarize(data,m) for m in METHODS},
                  "paired":{m:paired(data,m) for m in METHODS[:2]}} for name,data in subsets.items()}
    checks=[r.get("brute") for r in rows if r["id"] in manifest["brute_ids"]]
    assert len(checks)==50 and checks.count("PASS")==run["brute_verified"]
    static_pairs=0
    for r in rows:
        for m in METHODS:
            a=r["arms"][m]
            if a["success"]:
                assert a["p"]<.001 and a["certificate"] and a["anchor_invariant"] and a["selection_invariant"]
        fixed,opt=r["arms"]["GREEDY-fix"],r["arms"]["OPT"]
        if fixed["success"] and opt["success"]:
            assert opt.get("fixed_table_cost",0.)<=fixed.get("fixed_table_cost",0.)+1e-10
            static_pairs+=1
    main_result=groups["generated"]
    decision=selection(main_result["methods"],main_result["paired"]["GREEDY-dyn"],True,checks.count("PASS")==50)
    result={"groups":groups,"decision":decision,"forward_tokens":run["forward_tokens"],
            "solver_checks":{"hand_checks":manifest["hand_examples"],"brute_passed":checks.count("PASS"),
                             "brute_statuses":dict(Counter(checks)),"joint_static_cost_checks":static_pairs}}
    preserve={"meta":{"run_id":"EVAL04-M","prereg_sha256":manifest["prereg_sha256"],"opened_T1_T6":False,
                      "paid_API":0,"fpr_remeasured":False},"embedder_comparison":result}
    with (HERE/"figure_counts.json").open("x",encoding="utf-8",newline="\n") as f:
        json.dump(preserve,f,ensure_ascii=False,indent=2)
        f.write("\n")
    publish_csv(rows)
    with (HERE/"M_DEV_RESULT.md").open("x",encoding="utf-8",newline="\n") as f:
        f.write("\n".join(lines_for_report(result)))
    caches={
        "fixed_tables_sha256":hashlib.sha256(json.dumps(
            [(r["id"],r["static_cache"]) for r in rows],ensure_ascii=False,separators=(",",":")
        ).encode()).hexdigest(),
        "context_fingerprints_sha256":hashlib.sha256(json.dumps(
            [(r["id"],r["context_cache_sha256"]) for r in rows],ensure_ascii=False,separators=(",",":")
        ).encode()).hexdigest(),
        "fixed_scored_edge_rows":sum(len(r["static_cache"]) for r in rows),
        "forward_tokens":run["forward_tokens"],
    }
    with (HERE/"CACHE_SHA256.json").open("x",encoding="utf-8",newline="\n") as f:
        json.dump(caches,f,indent=2)
        f.write("\n")


if __name__=="__main__":
    main()
