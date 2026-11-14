"""Evaluate only frozen R development outputs and archived aggregate counts."""
import csv
import json
import pickle
from collections import Counter
from functools import lru_cache

import b2_core as b
from run_b2 import counts, inputs, order


WINDOWS = ((100,"first"),(100,"middle"),(100,"last"),(200,"first"),(200,"middle"))
ATTACK_COLUMNS = [
    "kind","id","gamma","m_max","policy","condition","eligible_slots","attackable_slots",
    "attackable_units","insertions","marked_insertions","p","accepted","S","M","N","X",
]


def test_target(p, slots, key, gamma, cap, parse):
    slots = [s for s in slots if b.compatible_insert(p,s)]
    all_slots = len(slots)
    all_units = len({slot["signature"] for slot in slots})
    chosen = [b.candidate(p,s,b.FRAMES[i%2]) for i,s in enumerate(slots[:cap])]
    if not chosen:
        return {"eligible_slots":len(p["slots"]),"attackable_slots":all_slots,"attackable_units":all_units,
                "insertions":0,"marked_insertions":0,"p":None,"accepted":False}
    changed = b.insert_plain(p,chosen)
    result = b.detect(parse(changed,p["question"]),key,gamma)
    return {"eligible_slots":len(p["slots"]),"attackable_slots":all_slots,"attackable_units":all_units,
            "insertions":len(chosen),
            "marked_insertions":sum(b.is_marked(b.mark_int(key,s["signature"]),gamma) for s in chosen),
            "accepted":result["p"] < .01,**result}


def summarize_attack(rows):
    return {
        "accepted":counts(sum(r["accepted"] for r in rows),len(rows)),
        "target_with_slot":counts(sum(r["attackable_slots"]>0 for r in rows),len(rows)),
        "target_slots":counts(sum(r["attackable_slots"] for r in rows),sum(r["eligible_slots"] for r in rows)),
        "insertion_histogram":{str(k):v for k,v in sorted(Counter(r["insertions"] for r in rows).items())},
        "insertions_at_marked_signatures":counts(sum(r["marked_insertions"] for r in rows),
                                                sum(r["insertions"] for r in rows)),
    }


def erase_frames(p):
    text = p["text"]
    for sent in reversed(p["sentences"]):
        offset = sent["offset"]
        if offset is None:
            continue
        match = b.FRAME.match(text[offset:sent["end"]])
        if match:
            end = offset+match.end()
            text = text[:offset]+text[end:end+1].upper()+text[end+1:]
    return text


def length_bin(n):
    if n<100:
        return "<100"
    if n<200:
        return "100–199"
    if n<=400:
        return "200–400"
    return ">400"


def format_rate(metric):
    return f"{metric['k']}/{metric['n']} ({metric['k']/metric['n']:.2%})" if metric["n"] else "N/A (n=0)"


def historical():
    rel = ("var/results/hsw-st/certinsert_eval03_lite_20261112/run01/"
           "batch02_adjusted/publication_FINAL/figure_counts.json")
    published = b.load(b.ROOT/rel)["detection"]
    return {label:{name:published[label]["CertInsert"][name]
                   for name in ("crop_first100","crop_middle100")} for label in ("T4_paired100","T5")}


def main():
    lock,keys,_,connectives = inputs()
    key = keys[0]

    @lru_cache(maxsize=4096)
    def parse(text, question):
        return b.plan(text,question,connectives)

    with (b.OUT/"plans.local.pickle").open("rb") as f:
        plans = pickle.load(f)
    with (b.OUT/"watermarked.local.pickle").open("rb") as f:
        texts = pickle.load(f)
    rows = [json.loads(line) for line in (b.OUT/"embedding.local.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows)==2700
    calibration = b.load(b.OUT/"calibration.json")
    resources = b.load(b.OUT/"embedding_run.json")
    seed = lock["seed"]
    target_ids = sorted((i for i,p in plans.items() if p["split"]=="calib" and p["kind"]!="generated"),
                        key=lambda i:order(seed,"target",i))[:200]
    assert len(target_ids)==200
    configs = {}
    eligible = []
    for g in b.GAMMAS:
        fp = calibration[str(g)]["signature"]["false_positive"]
        eligible_gamma = all(fp[str(a)]["k"]<=fp[str(a)]["n"]*a for a in (.001,.01))
        for m in b.BUDGETS:
            subset = [r for r in rows if r["gamma"]==g and r["m_max"]==m]
            success = [r for r in subset if r["status"]=="WATERMARKED"]
            label = f"{g}/{m}"
            assert len(subset)==300
            assert all(r.get("restore_ok") for r in success)
            by_length = {bin_:counts(sum(length_bin(r["words"])==bin_ for r in success),
                                     sum(length_bin(r["words"])==bin_ for r in subset))
                         for bin_ in ("<100","100–199","200–400",">400")}
            configs[label] = {
                "coverage":counts(len(success),300),"by_length":by_length,
                "certificates":counts(sum(r["restore_ok"] for r in success),len(success)),
                "mean_insertions":sum(r["insertions"] for r in success)/len(success) if success else None,
                "max_frame_repeat":max((r["max_frame_repeat"] for r in success),default=None),
                "statuses":dict(Counter(r["status"] for r in subset)),
                "minimum_trial_p":min((r.get("posted_p",r.get("last_trial_p",1.0))
                                       for r in subset),default=None),
                "maximum_attempted_insertions":max(r.get("attempted",r["insertions"]) for r in subset),
                "alpha_pass":eligible_gamma,
                "rankable":eligible_gamma and len(success)>=10,
            }
            if configs[label]["rankable"]:
                eligible.append(len(success))
    n_rank = min(50,min(eligible)) if eligible else None
    out_rows = []
    for row in rows:
        out_rows.append({"kind":"embedding",**{k:v for k,v in row.items() if k!="steps"}})

    observed_signatures = {}
    for g in b.GAMMAS:
        for m in b.BUDGETS:
            label = f"{g}/{m}"
            cfg = configs[label]
            success_ids = sorted((ident for gg,mm,ident in texts if (g,m)==(gg,mm)),
                                 key=lambda i:order(seed,"observation",i))
            checked = {}
            excerpt = {f"crop_{pos}{n}":[] for n,pos in WINDOWS}
            originals = []
            for ident in success_ids:
                p = plans[ident]
                y = texts[g,m,ident]["text"]
                parsed = parse(y,p["question"])
                result = b.detect(parsed,key,g)
                assert result["p"] < .001
                originals.append(True)
                checked[ident] = {s["signature"] for s in parsed["slots"] if s["frame"]}
                for n,pos in WINDOWS:
                    cropped = b.crop(y,n,pos)
                    crop_result = b.detect(parse(cropped,p["question"]),key,g)
                    window = f"crop_{pos}{n}"
                    excerpt[window].append(crop_result["p"]<.01)
                    out_rows.append({"kind":"excerpt","id":ident,"gamma":g,"m_max":m,"condition":window,
                                     "accepted":crop_result["p"]<.01,**crop_result})
            cfg["unattacked"] = counts(sum(originals),len(originals))
            cfg["excerpts"] = {k:counts(sum(v),len(v)) for k,v in excerpt.items()}
            observed_signatures[g,m] = checked

    for g in b.GAMMAS:
        for m in b.BUDGETS:
            label = f"{g}/{m}"
            cfg = configs[label]
            checked = observed_signatures[g,m]
            success_ids = list(checked)
            cfg["random"] = {}
            for cap in (3,4,5):
                metrics=[]
                for ident in target_ids:
                    p = plans[ident]
                    slots = sorted(p["slots"],key=lambda s:order(seed,"random",f"{ident}|{s['offset']}"))
                    row = test_target(p,slots,key,g,cap,parse)
                    metrics.append({"kind":"attack","id":ident,"gamma":g,"m_max":m,
                                    "policy":"random","condition":str(cap),**row})
                out_rows.extend(metrics)
                cfg["random"][str(cap)] = summarize_attack(metrics)

            erase = []
            for ident in success_ids:
                p = plans[ident]
                parsed = parse(texts[g,m,ident]["text"],p["question"])
                erased = b.detect(parse(erase_frames(parsed),p["question"]),key,g)
                erase.append(erased["p"]<.01)
                out_rows.append({"kind":"erase","id":ident,"gamma":g,"m_max":m,"accepted":erase[-1],**erased})
            cfg["erasure"] = counts(sum(erase),len(erase))
            cfg["learning"] = {}
            observations = [10,50] + ([n_rank] if n_rank not in (None,10,50) and cfg["rankable"] else [])
            for n in observations:
                if len(success_ids)<n:
                    cfg["learning"][str(n)] = None
                    continue
                learned = set.union(*(checked[ident] for ident in success_ids[:n]))
                cfg["learning"][str(n)] = {}
                for policy,cap in (("unlimited",None),("capped",m)):
                    metrics=[]
                    for ident in target_ids:
                        p = plans[ident]
                        matches = [s for s in p["slots"] if s["signature"] in learned and b.compatible_insert(p,s)]
                        candidates = [ss[0] for ss in b.units(matches).values()]
                        res = test_target(p,candidates,key,g,cap,parse)
                        res["attackable_slots"] = len(matches)
                        metrics.append({"kind":"attack","id":ident,"gamma":g,"m_max":m,
                                        "policy":"learned_"+policy,"condition":str(n),**res})
                    out_rows.extend(metrics)
                    cfg["learning"][str(n)][policy] = {"observed":n,"learned_signature_count":len(learned),
                                                      **summarize_attack(metrics)}
            cfg["rank_J"] = (cfg["coverage"]["k"]/300-
                             cfg["learning"][str(n_rank)]["unlimited"]["accepted"]["k"]/200
                             if cfg["rankable"] else None)
            print("Evaluation complete",label,"watermarked",len(success_ids),flush=True)

    ranked = [(label,cfg["rank_J"]) for label,cfg in configs.items() if cfg["rankable"]]
    winner = None
    if ranked:
        best = max(j for _,j in ranked)
        winner = min((label for label,j in ranked if best-j<.02),
                     key=lambda label:tuple(map(int,label.split("/")))[::-1])
    headers = list(dict.fromkeys(ATTACK_COLUMNS+[k for row in out_rows for k in row]))
    with (b.HERE/"per_item.csv").open("x",encoding="utf-8",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=headers,lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)
    figure = {
        "meta":{"run_id":"EVAL04-B2-DEV","freeze_sha256":lock["prereg_sha256"],
                "calibration":"R_calib","opened_T1_T6":False,"paid_api_calls":0},
        "zero_hypothesis":calibration,
        "configs":configs,"N_rank":n_rank,"selected_gamma_m_max":winner,
        "historical_excerpt_aggregate_only":historical(),"resources":resources,"target_n":len(target_ids),
    }
    write_result(figure)


def write_result(figure):
    with (b.HERE/"figure_counts.json").open("x",encoding="utf-8",newline="\n") as f:
        json.dump(figure,f,ensure_ascii=False,indent=2)
        f.write("\n")
    f = b.HERE/"B2_DEV_RESULT.md"
    total_calib = next(iter(figure["zero_hypothesis"].values()))["signature"]
    natural_units = total_calib["marked_frame_fraction"]["n"] // 1000
    max_coverage = max(cfg["coverage"]["k"] for cfg in figure["configs"].values())
    ranking_summary = (
        f"最高覆盖为 {max_coverage}/300。全部配置的成功数均不足 10，因而没有共同观察数和可计算的 J。"
        if max_coverage < 10 else
        f"最高覆盖为 {max_coverage}/300。排名分母与资格见第 6 节。"
    )
    lines = [
        "# EVAL-04-B2 开发验证",
        "",
        f"第 6 节结论为 **{'无合格配置' if figure['selected_gamma_m_max'] is None else figure['selected_gamma_m_max']}**。",
        "执行范围为 893 篇 R_calib、300 篇生成讲解和固定 200 篇攻击目标。T1–T6 原文未参与。",
        ranking_summary,
        "",
        "## 2. 零假设",
        "",
        "三档 α 误报以每档 893,000 个文档×密钥为分母。没有检验时计为未检出，QQ 取 1。独立口径是文档内不同签名，槽位口径只作探索。",
        f"893 篇原文共提供 {natural_units} 个天然含框架词的签名单元。全分母的低误报主要反映本语料中可检验情况很少。",
        "",
        "|γ|单元|α=.001|α=.01|α=.05|无检验|框架命中被标记比例|",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for g,modes in figure["zero_hypothesis"].items():
        for mode,row in modes.items():
            fp = [format_rate(row["false_positive"][str(a)]) for a in (.001,.01,.05)]
            lines.append(f"|{int(g)/100:.2f}|{mode}|{'|'.join(fp)}|{format_rate(row['not_testable'])}|"
                         f"{format_rate(row['marked_frame_fraction'])}|")
    lines.extend(["","QQ 百分位在 figure_counts.json，每篇文档的重复签名比例和误报计数在 calibration_by_doc.csv。",
                  "","## 3. 嵌入模拟","",
                  "|γ%/m_max|覆盖|<100|100–199|200–400|>400|平均插入|最大重复|证书恢复|无攻击检出|",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for label,cfg in figure["configs"].items():
        rates = "|".join(format_rate(x) for x in cfg["by_length"].values())
        mean = f"{cfg['mean_insertions']:.2f}" if cfg["mean_insertions"] is not None else "N/A"
        lines.append(f"|{label}|{format_rate(cfg['coverage'])}|{rates}|{mean}|{cfg['max_frame_repeat'] if cfg['max_frame_repeat'] is not None else 'N/A'}|"
                     f"{format_rate(cfg['certificates'])}|{format_rate(cfg['unattacked'])}|")
    lines.extend(["",f"实际前向 token 为 {figure['resources']['forward_tokens']:,}。详细不可加标状态见 figure_counts.json。",
                  "", "|γ%/m_max|尝试中最小 p|最多尝试插入|无标记候选|插入后仍未达标|",
                  "|---|---:|---:|---:|---:|"])
    for label,cfg in figure["configs"].items():
        state=cfg["statuses"]
        lines.append(f"|{label}|{cfg['minimum_trial_p']:.8f}|{cfg['maximum_attempted_insertions']}|"
                     f"{state.get('INSUFFICIENT_MARKED_SLOTS',0)}|{state.get('TARGET_NOT_REACHED',0)}|")
    lines.extend([
                  "","## 4. 摘录检出","",
                  "|γ%/m_max 或历史参照|开头100|中段100|结尾100|开头200|中段200|",
                  "|---|---:|---:|---:|---:|---:|"])
    for label,cfg in figure["configs"].items():
        lines.append(f"|{label}|"+"|".join(format_rate(x) if x["n"] else "NOT_RUN (无水印输出)" for x in cfg["excerpts"].values())+"|")
    for label,historical_counts in figure["historical_excerpt_aggregate_only"].items():
        lines.append(f"|EVAL-03 {label}·不同数据和方法|"+"|".join(format_rate(x) for x in historical_counts.values())+
                     "|N/A|N/A|N/A|")
    lines.extend(["","## 5. 随机插入与擦除","",
                  "|γ%/m_max|随机3|随机4|随机5|擦除后检测|","|---|---:|---:|---:|---:|"])
    for label,cfg in figure["configs"].items():
        random_rates="|".join(format_rate(r["accepted"]) for r in cfg["random"].values())
        erasure=format_rate(cfg["erasure"]) if cfg["erasure"]["n"] else "NOT_RUN (无水印输出)"
        lines.append(f"|{label}|{random_rates}|{erasure}|")
    lines.extend(["","### 学习攻击","",
                  "|γ%/m_max|观察N|口径|伪造接受|可攻击目标|槽位比例|真正标记比例|实际插入次数分布|",
                  "|---|---:|---|---:|---:|---:|---:|---|"])
    for label,cfg in figure["configs"].items():
        for n,modes in cfg["learning"].items():
            if modes is None:
                lines.append(f"|{label}|{n}|NOT_RUN，成功水印数不足|—|—|—|—|—|")
                continue
            for mode,data in modes.items():
                dist = ", ".join(f"{k} 次→{v} 篇" for k,v in data["insertion_histogram"].items())
                metrics = "|".join(format_rate(data[x]) for x in
                                   ("accepted","target_with_slot","target_slots","insertions_at_marked_signatures"))
                lines.append(f"|{label}|{n}|{mode}|{metrics}|{dist}|")
    lines.extend(["","## 6. 参数选择","",
                  f"统一 N_rank 为 {figure['N_rank'] if figure['N_rank'] is not None else 'N/A'}。",
                  "","|γ%/m_max|两档 α 均通过|排名状态|J|","|---|---|---|---:|"])
    for label,cfg in figure["configs"].items():
        j = f"{cfg['rank_J']:.4f}" if cfg["rank_J"] is not None else "N/A"
        state = "可排名" if cfg["rankable"] else ("NOT_RANKABLE_LOW_COVERAGE" if cfg["coverage"]["k"]<10 else "误报超标")
        lines.append(f"|{label}|{str(cfg['alpha_pass']).lower()}|{state}|{j}|")
    lines.extend(["","## 计数字段","",
                  "新增 zero_hypothesis 按 γ 和计数单位记录误报、无检验及 QQ。configs 按 γ%/m_max 记录覆盖、恢复、摘录、擦除和随机/学习攻击。可评估格为 k/n，未运行的学习格为 null。per_item.csv 每行对应嵌入、摘录、擦除或目标攻击。校准逐文档表是独立聚合来源。"])
    with f.open("x",encoding="utf-8",newline="\n") as stream:
        stream.write("\n".join(lines)+"\n")


if __name__=="__main__":
    main()
