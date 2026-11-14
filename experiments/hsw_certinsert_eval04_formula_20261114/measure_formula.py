"""Measure the symbolic development carrier using the frozen R corpus only."""
import hashlib
import json
import math
import pickle
from collections import Counter

from shared import HISTORY, OUT, keys, rank, read, sources, verify, write
from carrier import Carrier, Renderer, assemble_symbol, detection, edit, erase, pick
from sentence import SentenceDetector, restore
from score_cpu import CPUScore
from e1_v4r3_core import exact, pb_tail
from e1_v4r8_selector import selector
from e1_v4r7f_anchors import anchors
from e1_long_context_run import context_pair
import numpy as np

ALPHAS = (.001,.01,.05)


def count(k,n):
    return {"k":int(k),"n":int(n)}


def fisher(ps,pf):
    product=ps*pf
    return product*(1-math.log(product)) if product else 0.0


def inventory(generated,calib):
    lookup={}
    originals={s["id"]:s for s in generated+calib}
    with Renderer() as renderer:
        carrier=Carrier(renderer)
        for i,(key,row) in enumerate(originals.items(),1):
            inv=carrier.inventory(row["text"],row.get("question",""))
            lookup[key]=inv
            if i%100==0:
                print("symbol inventory",i,len(originals),flush=True)
    return lookup


def near_miss():
    paths=(
        ("T4",HISTORY/"INSERT_T4_all_RESULT.json",HISTORY/"prepared_batch1/CAPACITY.json"),
        ("T4",HISTORY/"scoring_recovery01/INSERT_T4_all_RESULT.json",None),
        ("T5",HISTORY/"batch02_adjusted/T5_insertion/INSERT_T5_all_RESULT.json",
         HISTORY/"batch02_adjusted/T5_prepared/CAPACITY.json")
    )
    recorded={}
    best={}
    for dataset, rec, cap in paths:
        for row in read(rec)["rows"]:
            if row["method"]=="CertInsert":
                recorded[dataset,row["id"]]={
                    "recorded_p":row.get("predicted_p"),"status":row["status"],"dataset":dataset,
                    "id":row["source_id"],
                }
        if cap:
            for row in read(cap):
                best[dataset,row["id"]]=row.get("predicted_min_p")
    patients=[]
    totals={}
    for ds in ("T4","T5"):
        group=[]
        for (name,identifier),row in recorded.items():
            if name==ds:
                group.append(dict(row,capacity_bound=best.get((ds,identifier))))
        failed=[r for r in group if r["status"].startswith("UNWATERMARKABLE")]
        totals[ds] = {
            "archived":len(group),"unwatermarkable":len(failed),
            "metrics":{metric:{ "available":sum(r[metric] is not None for r in failed),
                                "near":sum(r[metric] is not None and .001<=r[metric]<=.05 for r in failed),
                                "distribution":[sum(r[metric] is not None and lo<=r[metric]
                                                    and (r[metric]<hi if hi<.05 else r[metric]<=hi)
                                                    for r in failed)
                                                for lo,hi in ((.001,.005),(.005,.01),(.01,.025),(.025,.05))]}
                       for metric in ("recorded_p","capacity_bound")}
        }
        patients.extend(dict(r,kind="historical_near_miss") for r in failed)
    return totals,patients


def calibration(calib,inv,random_keys,detector):
    out={}
    modes=("symbol","combined")
    count_doc=[]
    n=len(random_keys)
    # Frozen EVAL-03 first-stage key permutation. Group equivalent permutations
    # to avoid recomputing the same detector selection for every document.
    original_table=detector.det.table.copy()
    from shared import OLD
    table=detector.det.embed([x["text"] for x in read(OLD/"development_round01/SECTABLE_CORPUS.json")[:len(detector.vocab)]])
    features=[anchors(r["text"]) for r in calib]
    words=detector.det.words
    enough=np.array([len(f)>=5 for f in features])
    ids=np.flatnonzero(enough)
    encoded=detector.det.embed(["\n".join(features[i]) for i in ids])
    lex_order=np.stack([np.argsort(-(detector.det.lexical@x),kind="stable") for x in encoded])
    hits=np.array([[exact(r["text"],word) for word in words] for r in calib],dtype=np.int32)
    unconditional=np.array([detector.by_word[w]["function"] in ("location","example") for w in words])
    # k=4 and the vocabulary has seven terms. Thus the prior top min(3*k,V)
    # includes all rows; its order matters only for exact lexical ties.
    assert len(words)==7 and sum(unconditional)==4
    lexical_scores=np.stack([detector.det.lexical@x for x in encoded])
    sorted_scores=np.take_along_axis(lexical_scores,lex_order,axis=1)
    ties=(np.diff(sorted_scores,axis=1)==0).any(axis=1)
    assert not ties.any() or ties.sum()<100
    upper=np.ones((1<<len(words),len(words)+1))
    for mask in range(1<<len(words)):
        p=[detector.frequencies[w] for i,w in enumerate(words) if mask & (1<<i)]
        if len(p)==4:
            upper[mask,:]=[pb_tail(p,k) for k in range(len(words)+1)]
    probability={k:np.ones((len(calib),n),dtype=np.float64) for k in modes}
    evidence=[(i,row) for i,r in enumerate(calib) for row in inv[r["id"]]["slots"]
              if row["observed"] is not None and len(row["alternates"])>=2]
    evidence_docs={i for i,_ in evidence}
    index_by_word={word:i for i,word in enumerate(words)}
    for j,key in enumerate(random_keys):
        fallback=sorted(range(len(words)),key=lambda i:hashlib.sha256(
            key+b"|anchor-global-v1|"+words[i].encode()).digest())
        choice=np.tile(fallback[:4],(len(calib),1))
        choice[ids]=lex_order[:,:4]
        missing=3-unconditional[choice].sum(axis=1)
        for idx in (x for x in fallback if unconditional[x]):
            add=(missing>0)&~(choice==idx).any(axis=1)
            selected=choice[add]
            last_non=3-(~unconditional[selected[:,::-1]]).argmax(axis=1)
            choice[add,last_non]=idx
            missing[add]-=1
        if ties.any() or j in (0,n-1):
            key_order=sorted(range(len(words)),key=lambda i:hashlib.sha256(
                key+b"|sectable|"+str(i).encode()).digest())
            detector.det.table=table[key_order]
            select=selector(detector.det,key,4,detector.vocab)
            for i in ids[ties]:
                choice[i]=[index_by_word[w] for w in select(calib[i]["text"])]
            if j in (0,n-1):
                for i in range(len(calib)):
                    assert sorted(words[x] for x in choice[i])==select(calib[i]["text"]),i
        mask=(1<<choice).sum(axis=1)
        hit=np.take_along_axis(hits,choice,axis=1).sum(axis=1)
        ps=upper[mask,hit]
        for i in evidence_docs:
            probability["symbol"][i,j]=detection(inv[calib[i]["id"]],key)[0]
        product=ps*probability["symbol"][:,j]
        positive=product>0
        probability["combined"][positive,j]=product[positive]*(1-np.log(product[positive]))
        probability["combined"][~positive,j]=0.
        if (j+1)%100==0:
            print("calibration keys",j+1,n,flush=True)
    detector.det.table=original_table
    for name,matrix in probability.items():
        p=matrix.ravel()
        out[name]={"false_positive":{str(alpha):count((p<alpha).sum(),len(p)) for alpha in ALPHAS},
                   "qq":[float(x) for x in np.quantile(p,np.arange(1001)/1000)],
                   "untested_p1":count((p==1.).sum(),len(p))}
        for i,row in enumerate(calib):
            count_doc.append({"kind":"calibration","id":row["id"],"mode":name,"n":n,
                              **{f"fp_{a}":int((matrix[i]<a).sum()) for a in ALPHAS}})
    out["natural_suffix_occurrences"]=sum(inv[r["id"]]["natural_suffix"] for r in calib)
    out["naturally_scorable_documents"]=len(evidence_docs)
    return out,count_doc


def series(carrier, text, question, inv, det, scorer, key, combined, source_slots=None):
    initial_pf,n,_=detection(inv,key)
    ps=det.p(text) if combined else None
    current=fisher(ps,initial_pf) if combined else initial_pf
    if current<.001:
        return dict(status="ALREADY_TARGET",success=True,p=current,p_s=ps,p_f=initial_pf,cert=[],
                    matched_locations=n,output=text,natural_zero_insert=True)
    valid=[r for r in inv["slots"] if len(r["alternates"])>=2 and not r["natural_suffix"]
           and (source_slots is None or (r["offset"], r["signature"]) in source_slots)]
    if not valid:
        return dict(status="NO_KEYED_SLOT",success=False,p=current,p_s=ps,p_f=initial_pf,
                    cert=[],output=text,natural_zero_insert=False)
    if not combined:
        upper=sorted([len(r["alternates"]) for r in valid],reverse=True)[:3]
        natural=[r for r in inv["slots"] if len(r["alternates"])>=2 and r["observed"] is not None]
        upper.extend(len(r["alternates"]) for r in natural)
        lower=math.prod(1/k for k in upper)
        if lower>=.001:
            return dict(status="UNWATERMARKABLE_PROBABILITY_BOUND",success=False,p=current,p_s=ps,
                        p_f=initial_pf,minimum_possible_p=lower,cert=[],output=text,natural_zero_insert=False)
    plan={"text":text,"sentences":inv["sentences"]}
    scored=[]
    for row in valid:
        item=dict(edit(row,pick(key,row)),sentence=row["sentence"],case_adjust=False)
        old,new,_=context_pair(plan,[],item)
        a,b=scorer.get(old),scorer.get(new)
        if a is not None and b is not None:
            scored.append((a-b,item["offset"],item))
    best={"status":"NO_SCORABLE_CONTEXT" if not scored else "TARGET_NOT_REACHED",
          "success":False,"p":current,"p_s":ps,"p_f":initial_pf,"cert":[],"output":text,
          "natural_zero_insert":False}
    chosen=[]
    for _,_,item in sorted(scored,key=lambda x:x[:2])[:3]:
        chosen.append(item)
        out,cert=assemble_symbol(text,chosen)
        cur=carrier.inventory(out,question)
        pf,n,_=detection(cur,key)
        ps=det.p(out) if combined else None
        p=fisher(ps,pf) if combined else pf
        best.update(p=p,p_s=ps,p_f=pf,attempted=len(chosen),matched_locations=n)
        if p<.001:
            best.update(status="TARGET_REACHED",success=True,cert=cert,output=out)
            break
    return best


def label_failure(parts):
    return Counter(f for row in parts for f in row["failures"])


def symbolic_bound(generated, inventories):
    checks=[]
    for source in generated:
        ident=source["id"]
        slots=inventories[ident]["slots"]
        natural=[len(r["alternates"]) for r in slots if r["observed"] is not None and len(r["alternates"])>=2]
        prospective=[len(r["alternates"]) for r in slots if not r["natural_suffix"] and len(r["alternates"])>=2]
        counts=natural+sorted(prospective,reverse=True)[:3]
        checks.append({"id":ident,"subject":source["subject"],"slots":len(slots),
                       "discriminative":len(prospective),"natural_evidence":len(natural),
                       "best_case_p_symbol":math.prod(1/x for x in counts),
                       "max_candidate_product":math.prod(counts)})
    return checks


def wait_sentence():
    completed=OUT/"sentence_run.json"
    if not completed.exists():
        raise RuntimeError("Sentence baseline output is incomplete")
    rows={r["id"]:r for r in map(json.loads,(OUT/"sentence.local.jsonl").read_text(encoding="utf-8").splitlines())}
    assert len(rows)==300
    return rows


def cases(generated,inv,det,key):
    sent=wait_sentence()
    matrix=[]
    with Renderer() as renderer:
        carrier=Carrier(renderer)
        scorer=CPUScore(OUT/"formula_native.log")
        try:
            with (OUT/"formula.local.jsonl").open("x",encoding="utf-8") as stream:
                for i,row in enumerate(generated,1):
                    ident,text=row["id"],row["text"]
                    question=row.get("question","")
                    s=sent[ident]
                    assert restore(s["trial"],s["spans"],s["case_changes"]).encode()==text.encode()
                    use_sentence_trial = s["anchor_and_selection_invariant"] and s["original_numeric_intact"]
                    start=s["trial"] if use_sentence_trial else text
                    permitted = set()
                    for slot in inv[ident]["slots"]:
                        if len(slot["alternates"])<2 or slot["natural_suffix"]:
                            continue
                        offset=slot["offset"]
                        if use_sentence_trial:
                            for span in s["spans"]:
                                if span["start"]<=offset:
                                    offset+=len(span["inserted"])
                        permitted.add((offset,slot["signature"]))
                    left=series(carrier,text,question,inv[ident],det,scorer,key,False)
                    right=series(carrier,start,question,carrier.inventory(start,question),det,scorer,key,True,
                                 source_slots=permitted)
                    if right["success"]:
                        returned=right["output"]
                        for edit_ in reversed(right["cert"]):
                            a,z=edit_["start"],edit_["end"]
                            assert returned[a:z]==edit_["inserted"]
                            returned=returned[:a]+returned[z:]
                        restored = restore(returned,s["spans"],s["case_changes"]) if use_sentence_trial else returned
                        assert restored.encode()==text.encode()
                    output={"id":ident,"subject":row["subject"],"words":s["words"],
                            "sentence":s,"formula":left,"combined":right}
                    stream.write(json.dumps(output,ensure_ascii=False)+"\n")
                    stream.flush()
                    matrix.append(output)
                    if i%15==0:
                        print("symbol arms",i,len(generated),scorer.tokens,flush=True)
        finally:
            scorer.close()
    write(OUT/"formula_run.json",{"forward_tokens":scorer.tokens,"score_calls":scorer.calls,"GPU":0})
    return matrix


def init():
    verify()
    _,formula,random_keys=keys()
    generated,calib=sources()
    return generated,calib,formula,random_keys


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=("inventory","calibration","cases","bound"))
    stage=parser.parse_args().stage
    generated,calib,key,random_keys=init()
    cached=OUT/"inventory.local.pickle"
    if stage=="inventory":
        raw=inventory(generated,calib)
        with cached.open("xb") as f:
            pickle.dump(raw,f)
        history,rows=near_miss()
        write(OUT/"near_miss.json",{"summary":history,"rows":rows})
        return
    with cached.open("rb") as f:
        raw=pickle.load(f)
    if stage=="bound":
        write(OUT/"symbolic_bound.json",symbolic_bound(generated,raw))
        return
    detector=SentenceDetector()
    if stage=="calibration":
        result,rows=calibration(calib,raw,random_keys,detector)
        write(OUT/"calibration.json",{"summary":result,"rows":rows})
    else:
        cases(generated,raw,detector,key)


if __name__=="__main__":
    main()
