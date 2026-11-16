"""Prepare blinded source reviews and run the frozen CPU-only T6 controls."""
import argparse
import csv
import hashlib
import html
import json
import random
import sys
from collections import Counter

import numpy as np

from stage_c_embed import B, C, HERE, OUT, ROOT, confirmed_sources, m
from t6_sources import load, rank, sha, write
from prepare_cpu import build_plan, word_count
from e1_v4r8_selector import selector
from structure_adapter import allowed_offset, split

OLD = ROOT/"var/results/hsw-st/english_replication_20261110_01/e1_guarded"
LEGACY = ROOT/"var/results/hsw-st/certinsert_eval03_lite_20261112/run01"
P6 = LEGACY/"batch02_adjusted/data/P6_BACKGROUND.json"
LEGACY_SOURCE = ROOT/"experiments/hsw_certinsert_eval03_lite_20261112"
FINAL = OUT/"cpu_controls"
FINAL.mkdir(exist_ok=True)
ALPHAS = (.001,.01,.05)


def n(k, denominator):
    return {"k":int(k),"n":int(denominator)}


def blinding(tasks):
    selected=sorted(tasks,key=lambda r:rank("human",r["source_id"]))[:40]
    assert len(selected)==40 and all(r["text"] is not None for r in selected)
    root=OUT/"human_review"
    root.mkdir(exist_ok=False)
    for review in range(1,3):
        folder=root/f"reviewer_{review}"
        folder.mkdir()
        ids={row["id"]:"R_"+sha(random.SystemRandom().getrandbits(128).to_bytes(16,"big"))[:10]
             for row in selected}
        order=sorted(selected,key=lambda r:rank(f"human_order_{review}",r["source_id"]))
        write(root/f"key_{review}.local.json",{ids[r["id"]]:r["id"] for r in order})
        with (folder/"review.csv").open("x",encoding="utf-8-sig",newline="") as f:
            writer=csv.writer(f)
            writer.writerow(["review_id","label","evidence_if_incorrect"])
            writer.writerows((ids[r["id"]],"","") for r in order)
        pages=["<!doctype html><meta charset='utf-8'><title>T6 source review</title>",
               "<style>body{margin:2rem auto;max-width:960px;font:16px/1.5 sans-serif} pre{white-space:pre-wrap} article{border-bottom:1px solid #aaa;margin-bottom:2rem}</style>",
               "<h1>T6 讲解知识正确性盲评</h1><p>逐条选择正确／有错／无法判断，有错请在表中记录证据。</p>"]
        for r in order:
            pages.extend([f"<article><h2>{ids[r['id']]}</h2>",
                          "<h3>题目</h3><pre>"+html.escape(r["question"])+"</pre>",
                          "<h3>讲解</h3><pre>"+html.escape(r["text"])+"</pre></article>"])
        (folder/"review.html").write_text("\n".join(pages),encoding="utf-8")
    write(FINAL/"human_review.json",{"invited_per_form":40,"forms":2,"completed_reviewers":0,
                                 "labels_collected":0,"status":"PACK_READY_FOR_REVIEWERS",
                                 "selection_sha256":sha(json.dumps([r["id"] for r in selected]).encode())})


def rc(tasks,det):
    folder=FINAL/"rc"
    folder.mkdir(exist_ok=True)
    out=folder/"outputs";out.mkdir(exist_ok=True)
    dst=folder/"per_source.jsonl"
    done={r["id"] for r in map(json.loads,dst.read_text(encoding="utf8").splitlines())} if dst.exists() else set()
    global_words=det.select("")
    with dst.open("a",encoding="utf-8") as f:
        for i, task in enumerate(tasks,1):
            identifier=task["id"]
            if identifier in done:
                continue
            text=task["text"]
            row={"id":identifier,"subject":task["subject"],"success":False}
            if text is None:
                row["status"]="NOT_RUN_SOURCE_FAILED"
            else:
                section=split(text,task["question"])
                words=word_count("".join(text[a:b] for a,b in section["body_intervals"]))
                plan=build_plan(dict(task,explanation_words=words),"T6","A4",lambda _:global_words)
                cap=m.capacity(plan,det.vocab,det.frequencies)
                edges=m.graph(plan,det)
                hits=set(cap["natural_hits"])
                chosen=[]
                rng=random.Random(int(rank("rc",identifier),16))
                status=cap["status"]
                while status=="ELIGIBLE":
                    if det.p(text,global_words)<.001 or m.pb_tail([det.frequencies[w] for w in global_words],
                                                len(hits|{c["word"] for c in chosen}))<.001:
                        status="PREDICTED_TARGET_REACHED"
                        break
                    pool=[e for e in edges if m.within(e,chosen,plan["budget"])]
                    if not pool:
                        status="UNWATERMARKABLE_GREEDY_EXHAUSTED"
                        break
                    chosen.append(rng.choice(pool))
                result,spans,changes,_=m.assemble(plan,chosen)
                cert=m.restore(result,spans,changes).encode()==text.encode()
                numeric=set(m.numbers(text))<=set(m.numbers(result)) and set(m.forms(text))<=set(m.forms(result))
                invariant=m.anchors(text)==m.anchors(result)
                pp=det.p(result,global_words)
                success=status=="PREDICTED_TARGET_REACHED" and cert and numeric and invariant and pp<.001
                if not success and status=="PREDICTED_TARGET_REACHED":
                    status="FAILED_PUBLIC_OR_INVARIANCE"
                if success:
                    (out/(identifier+".txt")).write_bytes(result.encode())
                row.update(status=status,success=success,p=pp,words=words,insertions=len(chosen),certificate=cert,
                           numeric_formula_intact=numeric,anchor_invariant=invariant,
                           protected_edits=sum(not allowed_offset(section,e["offset"]) for e in chosen),
                           output_sha256=sha(result.encode()) if success else None)
            f.write(json.dumps(row,ensure_ascii=False)+"\n")
            f.flush()
            if i%25==0: print("RC",i,200,flush=True)
    rows=[json.loads(line) for line in dst.read_text(encoding="utf-8").splitlines()]
    assert len(rows)==200
    write(FINAL/"rc.json",{"coverage":n(sum(r["success"] for r in rows),len(tasks)),
                         "statuses":dict(Counter(r["status"] for r in rows)), "ledger_sha256":m.digest(dst)})


def background(tasks,det):
    """Same frozen selector, with a vectorized exact seven-word candidate path."""
    original=load(P6)
    assert len(original)==500
    r_manifest=load(OUT.parent/"certinsert_eval04_20261113/stage0/RAG_CORPUS_MANIFEST.json")
    r_hashes={row.get("normalized_sha256") for row in r_manifest["records"]}
    rows=([dict(id=r["id"],text=r["text"],group="EVAL03_in_domain",original=r) for r in original]
         +[dict(id=r["id"],text=r["text"],group="T6_source",original=r) for r in tasks if r["text"] is not None])
    r_overlap=sum(row.get("normalized_sha256") in r_hashes for row in original)
    commitment=load(LEGACY_SOURCE/"KEY_STRESS_FREEZE.json")
    data=(LEGACY/"restricted/diagnostic_keys.bin").read_bytes()
    assert sha(data)==commitment["aggregate_sha256"] and len(data)==32000
    words=det.det.words
    assert len(words)==7
    term_id={term:i for i,term in enumerate(words)}
    lexical=det.det.lexical
    table=det.det.embed([x["text"] for x in load(OLD/"development_round01/SECTABLE_CORPUS.json")[:len(words)]])
    features=[m.anchors(row["text"]) for row in rows]
    ids=np.array([i for i,fs in enumerate(features) if len(fs)>=5],dtype=int)
    texts=["\n".join(features[i]) for i in ids]
    encoded=[]
    for j in range(0,len(texts),16):
        encoded.extend(det.det.embed(texts[j:j+16]))
    lex_scores=np.stack([lexical@x for x in encoded])
    preference=np.argsort(-lex_scores,axis=1,kind="stable")
    ties=(np.diff(np.take_along_axis(lex_scores,preference,axis=1),axis=1)==0).any(axis=1)
    hits=np.array([[m.exact(row["text"],w) for w in words] for row in rows],dtype=int)
    uncond=np.array([det.by_word[w]["function"] in ("location","example") for w in words])
    upper=np.ones((1<<7,8))
    for mask in range(1<<7):
        ps=[det.frequencies[w] for i,w in enumerate(words) if mask&(1<<i)]
        if len(ps)==4:
            upper[mask,:]=[m.pb_tail(ps,j) for j in range(8)]
    exposure={name:np.zeros((len(rows),len(ALPHAS)),dtype=int) for name in ("CertInsert","RC")}
    real_key=det.key
    real_p={}
    for seq,key in enumerate([real_key]+[data[i:i+32] for i in range(0,len(data),32)]):
        order=sorted(range(7),key=lambda i:hashlib.sha256(key+b"|anchor-global-v1|"+words[i].encode()).digest())
        choice=np.tile(order[:4],(len(rows),1))
        choice[ids]=preference[:,:4]
        missing=3-uncond[choice].sum(axis=1)
        for k in (x for x in order if uncond[x]):
            replace=(missing>0)&~(choice==k).any(axis=1)
            selected=choice[replace]
            last=3-(~uncond[selected[:,::-1]]).argmax(axis=1)
            choice[replace,last]=k
            missing[replace]-=1
        perm=sorted(range(7),key=lambda i:hashlib.sha256(key+b"|sectable|"+str(i).encode()).digest())
        det.det.table=table[perm]
        choose=selector(det.det,key,4,det.vocab)
        for i in ids[ties]:
            choice[i]=[term_id[w] for w in choose(rows[i]["text"])]
        if seq in (0,1,1000):
            assert all(sorted(words[x] for x in choice[i])==choose(row["text"]) for i,row in enumerate(rows))
        rc_cols=[term_id[w] for w in choose("")]
        p={
            "CertInsert":upper[(1<<choice).sum(axis=1),np.take_along_axis(hits,choice,axis=1).sum(axis=1)],
            "RC":upper[sum(1<<x for x in rc_cols),hits[:,rc_cols].sum(axis=1)],
        }
        for name,values in p.items():
            if seq==0:real_p[name]=values.tolist()
            else:exposure[name]+=(values[:,None]<np.array(ALPHAS))
        if seq%250==0: print("FPR random keys",seq,1000,flush=True)
    totals={}
    for group in ("EVAL03_in_domain","T6_source"):
        indices=[i for i,row in enumerate(rows) if row["group"]==group]
        totals[group]={name:{"production":{str(a):n(sum(real_p[name][i]<a for i in indices),len(indices))
                                           for a in ALPHAS},
                              "random_keys":{str(a):n(exposure[name][indices,j].sum(),len(indices)*1000)
                                             for j,a in enumerate(ALPHAS)}} for name in exposure}
    evidence=[{"id":row["id"],"group":row["group"],"detector":name,"production_p":real_p[name][i],
               "random_fp":dict(zip(map(str,ALPHAS),map(int,exposure[name][i]),strict=True))}
              for i,row in enumerate(rows) for name in exposure]
    write(FINAL/"fpr.json",{"counts":totals,"rows":evidence,"document_key_trials_correlated":True,
                          "keys_commitment_sha256":commitment["aggregate_sha256"],
                          "exact_R_background_normalized_matches":r_overlap})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage",choices=("human","rc","background"))
    stage=p.parse_args().stage
    tasks=list(confirmed_sources())
    if stage=="human":
        blinding(tasks)
    else:
        (rc if stage=="rc" else background)(tasks,m.SentenceDetector())


if __name__=="__main__":
    main()
