"""Run frozen dynamic CertInsert and the two fixed-score comparators on R."""
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT/"var/results/hsw-st/certinsert_eval04_matching_20261115"
PRIMARY = ROOT.parents[1]/"CogniGuard"
sys.path.insert(0,str(ROOT/"experiments/hsw_certinsert_eval04_formula_20261114"))
sys.path.insert(0,str(OUT/"deps"))
CUDA_VISIBLE=os.environ.get("CUDA_VISIBLE_DEVICES")

from shared import STAGE, digest, read, sha, write
from sentence import SentenceDetector, plan, restore
from e1_v4r8_capacity import capacity
from e1_v4r7f_prepare import allowed
from e1_v4r7f_anchors import anchors, forms, numbers
from e1_v4r3_core import exact, pb_tail
from e1_long_context_run import context_pair
from e1_register_core import assemble
from optimizer import brute, quality, selftest, solve
from gpu import Scorer

METHODS = ("GREEDY-dyn","GREEDY-fix","OPT")
ALPHA = .001
WORDS = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
SEED = "EVAL04-M-20261115"


def rank(label, ident):
    return sha(f"{SEED}|{label}|{ident}".encode())


def inputs():
    lock=read(HERE/"M_FREEZE.json")
    assert digest(HERE/"M_PREREG.md")==lock["prereg_sha256"]
    for root,section in ((ROOT,"worktree_files_sha256"),(PRIMARY,"primary_files_sha256")):
        for name,h in lock[section].items():
            assert digest(root/name)==h,name
    corpus = read(STAGE/"R_CORPUS.json")
    generated = [dict(r,cohort="generated") for r in corpus if r["kind"]=="generated"]
    pool = [r for r in corpus if r["split"]=="build" and r["kind"] in ("para","solution")]
    textbook = [dict(r,cohort="textbook") for r in sorted(pool,key=lambda r:rank("textbook",r["id"]))[:300]]
    batch=sorted(generated+textbook,key=lambda r:rank("process",r["id"]))
    assert len(generated)==len(textbook)==300 and len({r["id"] for r in batch})==600
    sample={r["id"] for r in sorted(batch,key=lambda r:rank("brute",r["id"]))[:50]}
    return lock,batch,sample,len(pool)


def graph(p, det):
    edges=[]
    for site in p["candidates"]:
        for w in p["selected"]:
            v=det.by_word[w]
            if v["word_cost"]<=p["budget"] and allowed(site,v):
                edges.append(dict(site,word=w,group=v["group"],word_cost=v["word_cost"],
                                  inserted=w.capitalize()+", ",case_adjust=site["offset"] in p["case_eligibility"]))
    return edges


def within(edge,chosen,budget):
    return edge["word_cost"]+sum(c["word_cost"] for c in chosen)<=budget and all(
        edge["group"]!=c["group"] and edge["sentence"]!=c["sentence"] and
        abs(edge["word_index"]-c["word_index"])>=8 for c in chosen)


def costs(p, chosen, edges, scorer, limit=None):
    if not edges:
        return []
    pairs=[context_pair(p,chosen,e)[:2] for e in edges]
    scored = scorer.get([t for a,b in pairs for t in (a,b)],limit)
    return [None if a is None or b is None else a-b for a,b in zip(scored[::2],scored[1::2],strict=True)]


def greedy(p, edges, natural, needed, scorer=None, sd=1.):
    chosen=[]
    limit=(time.perf_counter()+300,scorer.tokens+250000) if scorer is not None else None
    while len(natural|{e["word"] for e in chosen})<needed:
        legal=[e for e in edges if within(e,chosen,p["budget"])]
        if not legal:
            return chosen,"UNWATERMARKABLE_GREEDY_EXHAUSTED"
        values=[e["cost"] for e in legal] if scorer is None else costs(p,chosen,legal,scorer,limit)
        if any(x is None for x in values):
            return chosen,"CONTEXT_LIMIT"
        selected=min(range(len(values)),key=lambda i:(values[i]/sd,legal[i]["offset"],legal[i]["word"]))
        chosen.append(legal[selected])
    return chosen,"PREDICTED_TARGET_REACHED"


def evaluate(p, det, chosen, alpha):
    text,spans,changes,_ = assemble(p,chosen)
    restored = restore(text,spans,changes).encode()==p["text"].encode()
    anchor_equal=anchors(text)==tuple(p["anchors"])
    selected=det.select(text)
    word_equal=selected==p["selected"]
    intact=set(numbers(p["text"]))<=set(numbers(text)) and set(forms(p["text"]))<=set(forms(text))
    p_value=det.p(text,selected)
    return dict(p=p_value,certificate=restored,anchor_invariant=anchor_equal,
                selection_invariant=word_equal,numeric_formula_intact=intact,
                valid=restored and anchor_equal and word_equal and intact and p_value<alpha,
                text=text,spans=spans,changes=changes)


def final_row(p, det, chosen, status, elapsed, scorer):
    result = evaluate(p,det,chosen,ALPHA) if status=="PREDICTED_TARGET_REACHED" else None
    if result is not None and not result["valid"]:
        status = "FAIL_INVARIANCE_OR_PUBLIC_P"
    row=dict(status=status,success=result is not None and result["valid"],
             attempted_insertions=len(chosen),insertions=0,seconds_without_scoring=elapsed)
    if result is not None:
        row.update({key:value for key,value in result.items() if key not in ("text","valid")})
    if not row["success"]:
        row["output_sha256"]=p["source_sha256"]
        return row
    row.update(insertions=len(chosen),output_sha256=sha(result["text"].encode()))
    chosen=sorted(chosen,key=lambda e:e["offset"])
    values=[costs(p,chosen[:i],[e],scorer)[0] for i,e in enumerate(chosen)]
    row["dynamic_rescore_status"]="OK" if all(v is not None for v in values) else "CONTEXT_LIMIT"
    if row["dynamic_rescore_status"]=="OK":
        row["dynamic_total_cost"]=sum(values)
        row["dynamic_max_cost"]=max(values,default=None)
        row["dynamic_step_costs"]=values
    words=list(WORDS.finditer(result["text"]))
    if len(words)>=100:
        for name,start in (("first100",0),("middle100",(len(words)-100)//2)):
            snippet=result["text"][words[start].start():words[start+99].end()]
            pv=det.p(snippet)
            row[name+"_p"]=pv
            row[name+"_detected"]=pv<.01
    return row


def failure_reason(p, edges, natural, needed, chosen, status):
    if status!="UNWATERMARKABLE_GREEDY_EXHAUSTED":
        return status
    if any(e["word"] in natural for e in chosen):
        return "INSERTED_EXISTING_DISTINCT_HIT"
    unseen=[e for e in edges if e["word"] not in natural|{e["word"] for e in chosen}]
    allowed_except_position=[e for e in unseen if sum(c["word_cost"] for c in chosen)+e["word_cost"]<=p["budget"]
                             and all(e["group"]!=c["group"] for c in chosen)]
    return "SENTENCE_OR_SPACING_COLLISION" if allowed_except_position else "PATTERN_GROUP_OR_WORD_BUDGET"


def paired(p, det, scorer, brute_check, sd):
    natural={w for w in p["selected"] if exact(p["text"],w)}
    pv=[det.frequencies[w] for w in p["selected"]]
    needed=next((k for k in range(len(pv)+1) if pb_tail(pv,k)<ALPHA),len(pv)+1)
    edges=graph(p,det)
    # A mathematically infeasible document has no useful model-scored edges.
    try:
        possible=solve(edges,natural,needed,p["budget"],lambda _:True,existence=True)
        feasible="NO" if possible is None else "YES"
    except TimeoutError:
        feasible="UNKNOWN"
    values=costs(p,[],edges,scorer) if feasible!="NO" and len(natural)<needed else []
    if values:
        for edge,value in zip(edges,values,strict=True):
            edge["cost"]=value
    score_complete=not any(e.get("cost")==None for e in edges) if values else True
    dyn_cap=capacity(p,list(det.by_word.values()),det.frequencies)
    legacy_admission=dyn_cap["status"]
    fixed_valid=score_complete and (bool(values) or len(natural)>=needed or feasible=="NO")
    output={"static_cache":[{"offset":e["offset"],"word":e["word"],"cost":e.get("cost")}
                            for e in edges if "cost" in e],
            "fixed_scores_valid":fixed_valid,"candidate_edges":len(edges),
            "natural_hit_count":len(natural),"needed_hit_count":needed,
            "structurally_feasible":feasible,"arms":{}}
    for method in METHODS:
        tick=time.perf_counter()
        score_begin=scorer.seconds
        chosen=[]
        if method=="OPT":
            if feasible=="NO":
                status="UNWATERMARKABLE_EXACT"
                if brute_check:
                    oracle=brute([dict(e,cost=0.) for e in edges],natural,needed,p["budget"],lambda _:True)
                    assert oracle is None
                    output["brute"]="PASS"
            elif not fixed_valid:
                status="CONTEXT_LIMIT"
            else:
                def valid(items):
                    return evaluate(p,det,items,ALPHA)["valid"]
                try:
                    optimum=solve(edges,natural,needed,p["budget"],valid)
                    chosen=optimum or []
                    status="UNWATERMARKABLE_EXACT" if optimum is None else "PREDICTED_TARGET_REACHED"
                    if brute_check:
                        oracle=brute(edges,natural,needed,p["budget"],valid)
                        assert quality(optimum)==quality(oracle)
                        output["brute"]="PASS"
                except TimeoutError:
                    status="OPT_TIMEOUT"
                except ValueError as error:
                    status=str(error)
        elif legacy_admission!="ELIGIBLE":
            status=legacy_admission
        elif method=="GREEDY-fix" and not fixed_valid:
            status="CONTEXT_LIMIT"
        else:
            try:
                chosen,status=greedy(p,edges,natural,needed,scorer if method=="GREEDY-dyn" else None,sd=sd)
            except TimeoutError:
                status="RESOURCE_LIMIT"
        elapsed=time.perf_counter()-tick-(scorer.seconds-score_begin)
        row=final_row(p,det,chosen,status,max(0.,elapsed),scorer)
        row["failure_category"]=None if row["success"] else failure_reason(p,edges,natural,needed,chosen,row["status"])
        if chosen and all(e.get("cost") is not None for e in chosen):
            row["fixed_table_cost"]=sum(e["cost"] for e in chosen)
        output["arms"][method]=row
    if brute_check and "brute" not in output:
        output["brute"]="NOT_RUN_"+output["arms"]["OPT"]["status"]
    return output


def main():
    test_count=selftest()
    lock,batch,oracle,pool=inputs()
    manifest=OUT/"run_manifest.json"
    if not manifest.exists():
        write(manifest,{"prereg_sha256":lock["prereg_sha256"],"hand_examples":test_count,
                        "textbook_pool":pool,"ordered":[dict(id=r["id"],cohort=r["cohort"]) for r in batch],
                        "brute_ids":sorted(oracle)})
    det=SentenceDetector()
    assert sha(det.key)==lock["secret_commitment_sha256"]
    sd=read(ROOT/"var/results/hsw-st/certinsert_eval03_lite_20261112/run01/prepared_batch1/SCALE.json")["sd"]
    scorer=Scorer(ROOT,PRIMARY,OUT,CUDA_VISIBLE)
    target=OUT/"results.local.jsonl"
    done={}
    if target.exists():
        done={r["id"]:r for r in map(json.loads,target.read_text(encoding="utf-8").splitlines())}
    resources=OUT/"scoring_usage.jsonl"
    try:
        with target.open("a",encoding="utf-8",newline="\n") as stream, resources.open("a",encoding="utf-8") as usage:
            for source in batch:
                key=source["id"]
                if key in done:
                    continue
                p=plan(source,det)
                scorer.cache.clear()
                pre=scorer.tokens
                stats=paired(p,det,scorer,key in oracle,sd)
                record={"id":key,"cohort":source["cohort"],"subject":source["subject"],"words":p["explanation_words"],
                        "score_tokens":scorer.tokens-pre,**stats}
                # Local artifact retains cost values and reversible certificates.
                score_fingerprints=sorted((sha(t.encode()),v) for t,v in scorer.cache.items())
                record["context_cache_sha256"]=sha(json.dumps(score_fingerprints,separators=(",",":")).encode())
                stream.write(json.dumps(record,ensure_ascii=False)+"\n")
                stream.flush()
                usage.write(json.dumps({"id":key,"tokens":record["score_tokens"],"contexts":len(score_fingerprints)})+"\n")
                usage.flush()
                done[key]=record
                if len(done)%10==0:
                    counts=Counter(m for row in done.values() for m,arm in row["arms"].items() if arm["success"])
                    print("completed",len(done),600,"tokens",scorer.tokens,"successful",dict(counts),flush=True)
    finally:
        scorer.close()
    write(OUT/"RUN.json",{"documents":len(done),"forward_tokens":sum(r["score_tokens"] for r in done.values()),
                          "brute_verified":sum(r.get("brute")=="PASS" for r in done.values())})


if __name__=="__main__":
    main()
