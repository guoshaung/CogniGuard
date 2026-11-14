"""Publish the observed development evidence and the proved early stop."""
import csv
import json
import pickle
from collections import Counter

from shared import HERE, OUT, read, sources, verify, write


def count(k,n):
    return {"k":int(k),"n":int(n)}


def rate(row):
    return f"{row['k']:,}/{row['n']:,}（{row['k']/row['n']:.3%}）" if row and row["n"] else "N/A"


def words_bin(words):
    if words<100:
        return "<100"
    if words<=200:
        return "100–200"
    return "201–400" if words<=400 else ">400"


def per_type(slots):
    return {
        typ:{
            "slots":len(rows),
            "generation_success":{"k":sum(r["generated"]>0 for r in rows),"n":len(rows)},
            "proposals_validated":count(sum(len(r["alternates"]) for r in rows),sum(r["generated"] for r in rows)),
            "failures":dict(Counter(reason for r in rows for reason in r["failures"])),
        }
        for typ in ("equation","unit","number")
        for rows in [[r for r in slots if r["kind"]==typ]]
    }


def main():
    lock=verify()
    generated,calib=sources()
    with (OUT/"inventory.local.pickle").open("rb") as stream:
        inventory=pickle.load(stream)
    bound={r["id"]:r for r in read(OUT/"symbolic_bound.json")}
    assert len(bound)==len(generated)==300
    sentence={r["id"]:r for r in map(json.loads,(OUT/"sentence.local.jsonl").read_text(encoding="utf-8").splitlines())}
    assert set(sentence)<=set(bound)
    calibration=read(OUT/"calibration.json")
    historical=read(OUT/"near_miss.json")
    attacks=read(OUT/"attacks.json")
    gain_exposed=sum(r["discriminative"]>0 or r["natural_evidence"]>0 for r in bound.values())
    floor=min(r["best_case_p_symbol"] for r in bound.values())
    n=len(bound)
    assert gain_exposed/n < .10 and floor >= .001

    domains={}
    counters={}
    document_rows=[]
    failures=[]
    for source in generated:
        ident=source["id"]
        domain=source["subject"]
        slots=inventory[ident]["slots"]
        b=bound[ident]
        prior=sentence.get(ident)
        row={
            "kind":"generated_document","id":ident,"subject":domain,"symbol_slots":b["slots"],
            "keyed_slots":b["discriminative"],"natural_symbol_evidence":b["natural_evidence"],
            "min_p_f_bound":b["best_case_p_symbol"],"max_candidate_product":b["max_candidate_product"],
            "sentence_status":prior["status"] if prior else "NOT_RUN_EARLY_STOP",
            "sentence_success":prior["success"] if prior else None,
            "sentence_p":prior["p"] if prior else None,
            "sentence_certificate":prior["certificate"] if prior else None,
            "sentence_scoring_tokens":prior["scoring_tokens"] if prior else None,
            "sentence_insertions":prior["insertions"] if prior else None,
            "words":prior["words"] if prior else None,
            "combined_status":"NOT_RUN_EARLY_STOP","formula_status":"BOUND_EXCLUDES_TARGET",
        }
        document_rows.append(row)
        domains.setdefault(domain,[]).append(row)
        counters.setdefault(domain,[]).extend(slots)
        for slot in slots:
            if slot["failures"]:
                for reason in set(slot["failures"]):
                    if all(item["reason"]!=reason for item in failures):
                        failures.append({"id":ident,"kind":slot["kind"],"input":slot["raw"],"reason":reason})
            for key in ("equation","number","unit"):
                if slot["kind"]==key:
                    stem=f"{key}_"
                    for k,value in (("slots",1),("generated",slot["generated"]),("verified",len(slot["alternates"])),
                                    ("slots_with_proposal",int(slot["generated"]>0))):
                        row[stem+k]=row.get(stem+k,0)+value

    groups={}
    for domain,rows in sorted(domains.items()):
        groups[domain]={
            "documents":len(rows),
            "slot_distribution":dict(sorted(Counter(r["symbol_slots"] for r in rows).items())),
            "keyed_slot_distribution":dict(sorted(Counter(r["keyed_slots"] for r in rows).items())),
            "possible_additions_bound":count(sum(r["keyed_slots"]>0 or r["natural_symbol_evidence"]>0 for r in rows),len(rows)),
            "by_type":per_type(counters[domain]),
        }
    slots=[s for domain in counters.values() for s in domain]
    sample=list(sentence.values())
    bands={label:count(sum(r["success"] and words_bin(r["words"])==label for r in sample),
                       sum(words_bin(r["words"])==label for r in sample))
           for label in ("<100","100–200","201–400",">400")}
    random={}
    for cap in (1,2,3):
        attempt=[r for r in attacks["rows"] if r["kind"]=="random_forge" and r["requested"]==cap]
        actual=[r for r in attempt if r["actual"]==cap]
        assert len(attempt)==attacks["target_n"]
        random[str(cap)]={"available_target_count":attacks["target_n"],"planned_target_count":200,
                          "accepted_all":count(sum(r["accepted"] for r in attempt),len(attempt)),
                          "accepted_full":count(sum(r["accepted"] for r in actual),len(actual))}
    gates={
        "calibration":all(calibration["summary"][mode]["false_positive"][str(a)]["k"] <= a*893000
                          for mode in ("symbol","combined") for a in (.001,.01)),
        "minimum_coverage_gain":"FAIL_BY_UPPER_BOUND",
        "all_insertions_valid_and_reversible":"NOT_ESTABLISHED_PREMATURE_STOP",
        "learned_forge_N50":"NOT_RUN",
    }
    outcome={
        "meta":{"prereg_sha256":lock["prereg_sha256"],"R_only":True,"T1_T6_text_access":False,
                "GPU":0,"paid_API":0,"development_status":"STOPPED_BY_COVERAGE_UPPER_BOUND"},
        "symbolic_carrier":{
            "groups":groups,"overall_by_type":per_type(slots),
            "model_budget":{"sentence_completed_scoring_tokens":sum(r["scoring_tokens"] for r in sample),
                            "interrupted_next_case_excluded":True},
            "coverage":{"sentence":None,"formula":None,"combined":None},
            "sentence_partial":{"count":count(sum(r["success"] for r in sample),len(sample)),
                                "by_length":bands,"planned":n,"unscored":n-len(sample)},
            "coverage_gain_bound":count(gain_exposed,n),"minimum_p_f_bound":floor,
            "calibration":calibration["summary"],"random_forge":random,
            "erasure":None,"learning":None,"historical_near_miss":historical["summary"],
            "validation_failure_examples":failures,"gates":gates,"decision":"STOP",
        },
    }
    write(HERE/"figure_counts.json",outcome)
    per_item=document_rows+calibration["rows"]+historical["rows"]+attacks["rows"]
    columns=list(dict.fromkeys(k for r in per_item for k in r))
    with (HERE/"per_item.csv").open("x",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,lineterminator="\n")
        writer.writeheader()
        writer.writerows(per_item)

    lines=[
        "# HSW EVAL-04-F 开发测算",
        "",
        f"**STOP。** 按本轮保守识别与验证，{gain_exposed}/{n} 篇有可提供密钥证据的符号载体，覆盖率增益上界为 **{gain_exposed/n:.0%}**，低于冻结门槛 **10 个百分点**。句首基线完成 {len(sample)}/{n} 后提前停止。总体实际覆盖率、擦除和学习攻击均无完整分母，分别标记 NOT_RUN。T6 未使用本载体。",
        "",
        "在同一份句首尝试上加符号。原文没有可用符号位置或已存在的符号证据时，附带原式的合法插入不会提供 p_f<1。Fisher 此时为 p_s(1−ln p_s)≥p_s。因而新增成功只能来自表中的可用文档，且原句首成功与这些文档可以重叠。此上界限于本次有限解析器、候选家族及复用同一旧句首尝试的合并方式。",
        "",
        "## 2 · 零假设",
        "",
        f"893 篇 R_calib 中，按当前锚点与括号边界识别的天然后缀为 {calibration['summary']['natural_suffix_occurrences']} 处，有可计入符号检验的位置覆盖 {calibration['summary']['naturally_scorable_documents']} 篇。零误报主要对应无符号证据的语料。",
        "",
        "|口径|α=.001|α=.01|α=.05|p=1|",
        "|---|---:|---:|---:|---:|",
    ]
    for key in ("symbol","combined"):
        row=calibration["summary"][key]
        lines.append(f"|{key}|"+"|".join(rate(row["false_positive"][str(a)]) for a in (.001,.01,.05))+
                     f"|{rate(row['untested_p1'])}|")
    lines+=["","QQ 数据见 figure_counts.json。p_f 为离散概率。Fisher 名义分数按附件计算，未声称两种载体在一般语料独立。",
            "","## 3 · 容量","","冻结源含六个原样学科标签，化学 0 篇。两类数学分别保留，合计 100 篇。",
            "",
            "|学科|文档|全部符号槽位|可区分槽位|可新增篇数上界|",
            "|---|---:|---:|---:|---:|"]
    for domain,group in groups.items():
        lines.append(f"|{domain}|{group['documents']}|{sum(r['symbol_slots'] for r in domains[domain])}|"
                     f"{sum(r['keyed_slots'] for r in domains[domain])}|{rate(group['possible_additions_bound'])}|")
    lines+=["", "各学科的逐篇槽位数与可区分槽位数分布见 figure_counts.json。",
            "", "|学科|类型|至少生成一项／槽位|验证通过／生成候选|","|---|---|---:|---:|"]
    for label,values in [(k,v["by_type"]) for k,v in groups.items()]+[("总计",per_type(slots))]:
        for typ,row in values.items():
            lines.append(f"|{label}|{typ}|{rate(row['generation_success'])}|{rate(row['proposals_validated'])}|")
    lines+=["",f"即使取三个候选数最大的符号位置并且全部命中，300 篇中的最小名义 p_f 下界为 **{floor:.6f}**，不能达到 0.001。纯符号全量 3B 后验评分未执行，此处为容量下界推导对应的可达性结论。",
            "", "### 实际句首部分运行","",
            f"旧 3B 权重用 CPU 实跑 {len(sample)}/{n}，其中 {sum(r['success'] for r in sample)} 条达到原句首阈值并通过不变式。完整输出 {len(sample)} 条的逐字节恢复断言均通过。已完整记录的模型前向 token 为 {sum(r['scoring_tokens'] for r in sample):,}。剩余 {n-len(sample)} 篇和合并实际插入分布均未运行。",
            "", "|正文词数|句首已完成子集命中|符号及合并实际测算|","|---|---:|---|"]
    for label,row in bands.items():
        lines.append(f"|{label}|{rate(row)}|NOT_RUN|")
    lines+=["","### 验证失败例",""]
    for item in failures:
        example=item["input"][:110].replace("`","′").replace("\n"," ")
        lines.append(f"- `{example}` 得到 `{item['reason']}`。")
    lines+=["","## 4 · 历史近失","","区间依次为 [0.001,0.005)、[0.005,0.01)、[0.01,0.025)、[0.025,0.05]。实际末次与容量下界来自不同字段，两者不相加。T4 用同 ID 的恢复批记录覆盖旧失败。",
            "", "|来源|不可加水印|口径|近失数／有数值|四档计数|","|---|---:|---|---:|---|"]
    for domain,group in historical["summary"].items():
        for label,row in group["metrics"].items():
            lines.append(f"|{domain}|{group['unwatermarkable']}|{label}|{row['near']}/{row['available']}|{', '.join(map(str,row['distribution']))}|")
    lines+=["","## 5 · 随机插入、擦除及学习攻击","",
            f"冻结 R_calib 只有 {attacks['target_n']} 篇在本次提取器下有合法可插变体。按真实分母运行随机插入，另报满足请求次数的子集。",
            "", "|请求插入数|目标全部|实际插满子集|","|---:|---:|---:|"]
    for cap,row in random.items():
        lines.append(f"|{cap}|{rate(row['accepted_all'])}|{rate(row['accepted_full'])}|")
    lines+=["","擦除、学习 N=10/50 及 EVAL-03 同观察数比较为 NOT_RUN。停止时没有完整成功输出队列。",
            "", "## 6 · 冻结门槛","",
            f"1. 误报点估计两档{'达标' if gates['calibration'] else '未达标'}。天然可检验符号位置不足以证明一般校准。",
            f"2. +10 个百分点增益 **未通过**。最宽松新增计数 {gain_exposed}/{n}，上界 {gain_exposed/n:.0%}。",
            "3. 全量证书和改写恢复未建立。当前符号候选筛选、随机插入和句首部分复核分别报告。",
            "4. N=50 学习攻击比较未运行。沿用第 2 项失败的停止判据。",
            "", "per_item.csv 含 300 条开发容量记录、校准逐文档计数、历史近失及 R 随机攻击数值。figure_counts.json 的实际全量覆盖率、擦除与学习字段为 null。",
            ""]
    with (HERE/"F_DEV_RESULT.md").open("x",encoding="utf-8",newline="\n") as stream:
        stream.write("\n".join(lines))
    print("Verified STOP bound",gain_exposed,n,"p floor",floor,"per-item rows",len(per_item))


if __name__=="__main__":
    main()
