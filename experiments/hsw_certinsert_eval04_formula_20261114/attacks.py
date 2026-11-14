"""Evaluate random and observation-based symbolic watermarks on R."""
import json
import pickle
import random
import re
from collections import Counter
from functools import lru_cache

from shared import OUT, keys, rank, sources, write
from carrier import Carrier, Renderer, assemble_symbol, detection, edit, erase
from measure_formula import fisher
from sentence import SentenceDetector
from capacity_shared_v32 import nlp
from structure_adapter import split

BLOCK = set("then thus so therefore hence however next now first finally".split())


def article_starts(text):
    masked=re.sub(r"\\\(.*?\\\)",lambda m:" "*(m.end()-m.start()),text,flags=re.S)
    return [s.start_char for s in nlp(masked).sents]


def prefixes(text, start):
    result=set()
    for off in start:
        match=re.match(r"\s*((?:[A-Za-z]+(?:['’-][A-Za-z]+)*\s+){0,4}[A-Za-z]+),",text[off:])
        if match:
            result.add(" ".join(match[1].lower().split()))
    return result


def legacy_spoof(source, phrases, starts):
    text=source["text"]
    spans=split(text,source.get("question",""))["body_intervals"]
    words=list(re.finditer(r"[A-Za-z]+(?:['’-][A-Za-z]+)*",text))
    budget=int(.06*len(words))
    sites=[]
    for a,z in zip(starts,starts[1:]+[len(text)],strict=True):
        m=re.search(r"[A-Za-z]+",text[a:z])
        if m and m[0].casefold() not in BLOCK and any(lo<=a+m.start()<hi for lo,hi in spans):
            sites.append(a+m.start())
    sites.sort(key=lambda a:rank("legacy_spoof_position",f"{source['id']}|{a}"))
    chosen=[]
    groups=set()
    cost=0
    for phrase in phrases:
        tokens=phrase.split()
        group=" ".join(tokens[:2])
        if group in groups or cost+len(tokens)>budget:
            continue
        offset=next((a for a in sites if all(sum(min(a,b)<=w.start()<max(a,b) for w in words)>=8
                                             for b,_ in chosen)),None)
        if offset is None:
            continue
        sites.remove(offset)
        chosen.append((offset,phrase.capitalize()+", "))
        groups.add(group)
        cost+=len(tokens)
    out=text
    for offset,raw in sorted(chosen,reverse=True):
        out=out[:offset]+raw+out[offset:]
    return out,len(chosen)


def main():
    import argparse

    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--random-only",action="store_true")
    args=parser.parse_args()
    from measure_formula import init
    _,calib,key,_=init()
    with (OUT/"inventory.local.pickle").open("rb") as f:
        inventories=pickle.load(f)
    base=[]
    arms=[]
    if not args.random_only:
        base=list(map(json.loads,(OUT/"sentence.local.jsonl").read_text(encoding="utf-8").splitlines()))
        arms=list(map(json.loads,(OUT/"formula.local.jsonl").read_text(encoding="utf-8").splitlines()))
        assert len(base)==len(arms)==300
    targets=sorted((r for r in calib if any(v["alternates"] and not v["natural_suffix"]
                                         for v in inventories[r["id"]]["slots"])),
                   key=lambda r:rank("attack_target",r["id"]))[:200]
    legacy_refs=sorted((r for r in calib if r["id"] not in {t["id"] for t in targets}),
                       key=lambda r:rank("attack_background",r["id"]))
    det=SentenceDetector()
    results=[]
    with Renderer() as renderer:
        c=Carrier(renderer)
        q=lambda row:row.get("question","")

        @lru_cache(maxsize=2000)
        def p_combined(text,question):
            pf,_,_=detection(c.inventory(text,question),key)
            return fisher(det.p(text),pf)

        for i,target in enumerate(targets,1):
            ident=target["id"]
            slots=[r for r in inventories[ident]["slots"] if r["alternates"] and not r["natural_suffix"]]
            seed=int(rank("random_slots",ident),16)
            rng=random.Random(seed)
            rng.shuffle(slots)
            chosen=[edit(r,rng.randrange(len(r["alternates"]))) for r in slots[:3]]
            for cap in (1,2,3):
                out,_=assemble_symbol(target["text"],chosen[:cap])
                p=p_combined(out,q(target))
                results.append({"id":ident,"kind":"random_forge","requested":cap,
                                "actual":min(cap,len(chosen)),"p":p,"accepted":p<.01})
            if i%50==0:print("random targets",i,len(targets),flush=True)

        erase_results=[]
        marked=[r for r in arms if r["combined"]["success"]]
        for row in marked:
            arm=row["combined"]
            stripped=erase(arm["output"])
            # Source questions are used only for original coverage and extraction;
            # the observed text remains the attacker input.
            question=questions[row["id"]]
            p=p_combined(stripped,question)
            erase_results.append({"id":row["id"],"kind":"erasure","p":p,"accepted":p<.01,
                                  "had_symbols":bool(arm["cert"]),"p_s_after":det.p(stripped)})
        results.extend(erase_results)

        marked=sorted((r for r in marked if r["combined"]["cert"]),key=lambda r:rank("observe",r["id"]))
        baseline=sorted((r for r in base if r["success"] and r["insertions"]),key=lambda r:rank("observe",r["id"]))
        eligibility={}
        for n in (10,50):
            eligibility[str(n)]={"combined_observable":len(marked),"sentence_observable":len(baseline),
                                 "combined_status":"AVAILABLE" if len(marked)>=n else "NOT_RUN_LOW_OBSERVATIONS",
                                 "sentence_status":"AVAILABLE" if len(baseline)>=n else "NOT_RUN_LOW_OBSERVATIONS"}
            if len(marked)>=n:
                learned={}
                for row in marked[:n]:
                    for slot in c.inventory(row["combined"]["output"],questions[row["id"]])["slots"]:
                        if slot["observed"] is not None:
                            winner=slot["alternates"][slot["observed"]]["text"]
                            learned.setdefault(slot["signature"],Counter())[winner]+=1
                preferred={s:min(variants,key=lambda v:(-variants[v],v)) for s,variants in learned.items()}
                for target in targets:
                    ident=target["id"]
                    known=[r for r in inventories[ident]["slots"] if r["signature"] in preferred]
                    chosen=[]
                    for row in known:
                        if row["natural_suffix"]:
                            continue
                        idx=next((i for i,v in enumerate(row["alternates"])
                                  if v["text"]==preferred[row["signature"]]),None)
                        if idx is not None:
                            chosen.append(edit(row,idx))
                    out,_=assemble_symbol(target["text"],chosen)
                    p=p_combined(out,q(target))
                    results.append({"kind":"learn_formula","n_observed":n,"id":ident,"p":p,
                                    "accepted":p<.01,"actual":len(chosen),"observed_signature_slots":len(known)})
            if len(baseline)>=n:
                freq=Counter(w for x in baseline[:n] for w in prefixes(x["trial"],article_starts(x["trial"])))
                starts={r["id"]:article_starts(r["text"]) for r in targets+legacy_refs}
                bg=Counter(w for x in legacy_refs for w in prefixes(x["text"],starts[x["id"]]))
                ranked=sorted(freq,key=lambda w:(-(freq[w]/n-bg[w]/len(legacy_refs)),w))
                for cap in (4,8):
                    for target in targets:
                        ident=target["id"]
                        out,actual=legacy_spoof(target,ranked[:cap],starts[ident])
                        p=det.p(out)
                        results.append({"kind":"learn_sentence","n_observed":n,"requested":cap,"id":ident,
                                        "p":p,"accepted":p<.01,"actual":actual})
    if args.random_only:
        eligibility={str(n):{"combined_status":"NOT_RUN_DEVELOPMENT_STOP",
                            "sentence_status":"NOT_RUN_DEVELOPMENT_STOP"} for n in (10,50)}
    write(OUT/"attacks.json",{"target_n":len(targets),"eligibility":eligibility,"rows":results,
                              "random_only":args.random_only})


if __name__=="__main__":
    generated,_=sources()
    questions={r["id"]:r.get("question","") for r in generated}
    main()
