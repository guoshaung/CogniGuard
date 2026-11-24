"""Measure frozen M2 and content retrieval on shared fragment queries."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import re
import sys

HERE = Path(__file__).resolve().parent
P = HERE.parent/"hsw_provenance"
N = HERE.parent/"hsw_provenance_next"
sys.path[:0] = [str(N),str(P/"fingerprints")]
from candidate import Codec, PREFIX
from run import chunks, load_semantic, precompute

LENGTHS = (5,20,50,100)
METHODS = ("minhash","bm25","bge","bge_rerank","kbpw","joint")


def read(path):
    return json.loads(path.read_bytes())


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]


def save(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf8")


def jsonl(path,data):
    with path.open("w",encoding="utf8") as stream:
        for row in data:
            stream.write(json.dumps(row,ensure_ascii=False,separators=(",",":"))+"\n")


def norm(text):
    return " ".join(re.findall(r"\w+",text.casefold()))


def corpora():
    return read(P/"propagation/sources.json"),read(P/"propagation/releases.json")


def sample_cases(sources,releases,marked):
    units = {s["source_id"]:s["units"] for s in sources}
    ledger = {r["release_id"]:r for r in releases}
    ids = list(units)
    cases = []
    def add(key,text,kind,n,facts,issuances,dev=False,unknown=False):
        cases.append(dict(artifact_id=hashlib.sha256(key.encode()).hexdigest()[:24],
                          text=text,kind=kind,length=n,actual_words=len(text.split()),
                          facts=sorted(facts),sources=sorted({f.rsplit(":f",1)[0] for f in facts}),
                          releases=sorted(issuances),dev=dev,unknown=unknown))
    for i,sid in enumerate(ids):
        group = ids[i//3*3:i//3*3+3]
        dev = i//3==0
        for fusion in (1,2,3):
            members = [sid]+[s for s in group if s!=sid][:fusion-1]
            for issuer in ("issuer-a","issuer-b"):
                issued = [f"{s}:issue:{issuer}" for s in members]
                for variant,catalog in (("marked",marked),("unmarked",ledger)):
                    body = "\n".join(catalog[r]["text"] for r in issued)
                    words = list(re.finditer(r"\S+",body))
                    for n in LENGTHS:
                        if len(words)<n:
                            continue
                        for kind in ("random","sentence_end"):
                            key = f"{i}|{fusion}|{issuer}|{kind}|{n}"
                            start = random.Random(key).randrange(len(words)-n+1) if kind=="random" else len(words)-n
                            text = body[words[start].start():words[start+n-1].end()]
                            haystack = " "+norm(text)+" "
                            facts = [u["fact_id"] for s in members for u in units[s] if " "+norm(u["text"])+" " in haystack]
                            supported = [r for r in issued if any(f.startswith(ledger[r]["source_id"]+":f") for f in facts)]
                            add(key+"|"+variant,text,kind,n,facts,supported,dev)
        for n in LENGTHS:
            null_words = f"The library is closed tomorrow. Room {i+11} has chairs available.".split()
            add(f"null|{i}|{n}"," ".join((null_words*(n//len(null_words)+1))[:n]),
                "unrelated",n,[],[],dev)
            u = units[sid][0]
            independent_words = u["strong"].split()
            text = " ".join((independent_words + null_words*(n//len(null_words)+1))[:n])
            complete = len(independent_words)<=n
            add(f"independent|{i}|{n}",text,"independent",n,[u["fact_id"]] if complete else [],[],dev,not complete)
    annotations = {(r["case_id"],r["variant"]):r for r in rows(N/"real/pilot/annotations.jsonl")}
    for r in rows(N/"real/pilot/cases.jsonl"):
        if r["transform"]!="summary" or r["variant"] not in ("plain","M2"):
            continue
        label = annotations[r["case_id"],r["variant"]]
        words = list(re.finditer(r"\S+",r["text"]))
        for n in LENGTHS:
            full = len(words)<=n
            text = r["text"] if full else r["text"][:words[n-1].end()]
            facts = label["retained_fact_ids"] if full else []
            add(f'{r["case_id"]}|{r["variant"]}|{n}',text,"model_summary",n,facts,
                label["supported_release_ids"] if full else [],unknown=not full)
    for r in releases:
        line=marked[r["release_id"]]["text"].splitlines()[0]
        add("copy|"+r["release_id"],line,"credential_copy",len(line.split()),
            [units[r["source_id"]][0]["fact_id"]],[])
    return cases


def watermark(codec,text,ledger):
    observed = codec.inspect(text)
    known = {w.casefold():label for label,w in codec.codebook("M2").items()}
    decoded,_ = codec.decode("M2",observed,.95,known)
    bound = {}
    for code,scores in observed:
        if code in known:
            release,fact = known[code]
            if release in decoded and scores[fact]>=.95 and scores[fact]-max(v for k,v in scores.items() if k!=fact)>=.05:
                bound[release,fact] = max(scores[fact],bound.get((release,fact),0))
    return bound,any(code in known for code,_ in observed)


def metric(pairs,target):
    tp=fp=fn=covered=negatives=false=wrong=known=0
    multi=[]
    for c,p in pairs:
        if c["unknown"]:
            continue
        known+=1
        gold,got=set(c[target]),set(p[target])
        tp+=len(gold&got)
        fp+=len(got-gold)
        fn+=len(gold-got)
        covered+=bool(got)
        negatives+=not gold
        false+=not gold and bool(got)
        wrong+=bool(got-gold)
        if len(gold)>1:
            multi.append(2*len(gold&got)/(len(gold)+len(got)))
    return dict(tp=tp,fp=fp,fn=fn,precision=tp/max(1,tp+fp),recall=tp/(tp+fn) if tp+fn else None,
                coverage=covered/max(1,known),raw_coverage=sum(bool(p[target]) for _,p in pairs)/len(pairs),
                fpr=false/negatives if negatives else None, negatives=negatives,wrong_query_rate=wrong/max(1,known),
                multi_set_f1=sum(multi)/len(multi) if multi else None,n=len(pairs),unknown=len(pairs)-known)


def main():
    p=argparse.ArgumentParser()
    for name in ("bge","rerank","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    sources,releases=corpora()
    ledger={r["release_id"]:r for r in releases}
    marked={r["release_id"]:r for r in read(N/"candidates/M2_releases.json")}
    codec=Codec(sources,releases,[r for r in rows(P/"propagation/cases.jsonl") if r["partition"]=="calibration"])
    assert all(codec.encode("M2",r)["text"]==marked[r["release_id"]]["text"] for r in releases)
    cases=sample_cases(sources,releases,marked)
    assert len(cases)==len({c["artifact_id"] for c in cases})
    jsonl(a.out/"scoring_cases.jsonl",cases)
    jsonl(a.out/"public_fragments.jsonl",
          [dict(artifact_id=c["artifact_id"],text=c["text"]) for c in cases])
    docs=list(dict.fromkeys((s["source_id"],d) for s in sources for d in chunks(s["text"])))
    raw,_,_,_=precompute([dict(case_id=c["artifact_id"],text=c["text"]) for c in cases],sources,docs,docs,releases,
                         load_semantic(a.bge,a.rerank,4))
    observations={}
    for c in cases:
        aid=c["artifact_id"]
        bound,carrier=watermark(codec,c["text"],ledger)
        marked_sources={}
        for (rid,_),score in bound.items():
            sid=ledger[rid]["source_id"]
            marked_sources[sid]=max(score,marked_sources.get(sid,0))
        for method in METHODS:
            src=marked_sources if method=="kbpw" else dict(raw["bge" if method=="joint" else method][aid])
            if method=="joint":
                src={s:v for s,v in src.items() if s in marked_sources}
            observations[method,aid]=src,bound,carrier
    cutoffs={}
    # Empirical shared ceiling on development wrong-source queries, strict >.
    for method in METHODS:
        for n in LENGTHS:
            wrong=sorted((max((v for s,v in observations[method,c["artifact_id"]][0].items() if s not in c["sources"]),
                            default=-1e9) for c in cases if c["dev"] and c["length"]==n and not c["unknown"]),reverse=True)
            cutoffs[method,n]=wrong[int(.05*len(wrong))]
    predictions=[]
    groups=defaultdict(list)
    for method in METHODS:
        for c in cases:
            aid=c["artifact_id"]
            src,bound,carrier=observations[method,aid]
            n=min(LENGTHS,key=lambda x:abs(x-c["length"]))
            ranked=sorted(((s,v) for s,v in src.items() if v>cutoffs[method,n]),key=lambda z:(-z[1],z[0]))[:3]
            selected=dict(ranked)
            matched={(rid,f):v for (rid,f),v in bound.items() if ledger[rid]["source_id"] in selected} if method in ("joint","kbpw") else {}
            actual=sorted({r for r,_ in matched})
            candidate_ids=actual if method in ("kbpw","joint") else sorted(r for r,z in ledger.items() if z["source_id"] in selected)
            row=dict(artifact_id=aid,method=method,sources=sorted(selected),scores=selected,releases=actual,
                     facts=sorted({f for _,f in matched}),candidate_issuance_ids=candidate_ids,
                     release_scores={r:max(v for (x,_),v in matched.items() if x==r) for r in actual},
                     conflict=carrier and not actual if method in ("joint","kbpw") else False)
            predictions.append(row)
            if not c["dev"]:
                groups[method,c["kind"],c["length"]].append((c,row))
    jsonl(a.out/"predictions.jsonl",predictions)
    save(a.out/"summary.json",[dict(method=m,kind=k,length=n,asset=metric(g,"sources"),issuance=metric(g,"releases"))
                               for (m,k,n),g in sorted(groups.items())])
    save(a.out/"thresholds.json",{m:{n:cutoffs[m,n] for n in LENGTHS} for m in METHODS})
    print(len(cases),len(predictions))


if __name__=="__main__":
    main()
