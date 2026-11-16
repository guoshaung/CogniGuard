"""Run and independently verify both frozen T6 CertInsert arms."""

import json
import subprocess
import sys
from collections import Counter

from t6_sources import HERE, OUT, ROOT, load, rank, sha, verify_prereg, write

MATCHING = ROOT / "experiments/hsw_certinsert_eval04_matching_20261115"
B = OUT / "stage_b_generation"
C = OUT / "stage_c_embedding"
ARMS = ("GREEDY-dyn", "OPT")
sys.path.insert(0, str(MATCHING))
import run_m as m
from check_outputs import reconstruct


def confirmed_sources():
    verify_prereg()
    addendum = load(HERE / "FINAL_PREREG_ADDENDUM_FREEZE.json")
    for path, checksum in addendum["files_sha256"].items():
        assert m.digest(ROOT/path)==checksum,path
    freeze = load(HERE/"T6_EMBED_FREEZE.json")
    for path, checksum in freeze["files_sha256"].items():
        assert m.digest(ROOT/path)==checksum,path
    tasks={x["id"]:x for x in load(OUT/"sources.local.json")}
    generation={x["id"]:x for x in load(B/"RESULT.json")["rows"]}
    assert len(tasks)==len(generation)==200 and tasks.keys()==generation.keys()
    for ident, task in tasks.items():
        row=generation[ident]
        assert sha(task["question"].encode())==task["question_sha256"]
        path=B/"outputs"/(ident+".txt")
        if row["status"]=="COMPLETED" and row["format_pass"]:
            assert m.digest(path)==row["output_sha256"]
            yield dict(task,text=path.read_text(encoding="utf-8"),
                       source_output_sha256=row["output_sha256"],generation_finish=row["finish_reason"])
        else:
            yield dict(task,text=None,generation_finish=row.get("finish_reason"))


def source_plan(task,det):
    return m.plan(task,det)


def summarize(cases):
    union=[]
    for row in cases:
        arms={name:row["arms"][name]["success"] for name in ARMS}
        if any(arms.values()):
            union.append({"id":row["id"],"subject":row["subject"],
                          "source_output_sha256":row["source_output_sha256"],"success":arms})
    union.sort(key=lambda x:rank("union_order",x["id"]))
    data={
        "planned":len(cases),"success":{name:sum(r["arms"][name]["success"] for r in cases) for name in ARMS},
        "common_success":sum(all(r["arms"][name]["success"] for name in ARMS) for r in cases),
        "union":len(union),"forward_tokens":sum(r["scoring_tokens"] for r in cases),
        "verify_failures":sum(r["arms"][name].get("independent_verified") is False for r in cases for name in ARMS),
        "status_by_arm":{name:dict(Counter(r["arms"][name]["status"] for r in cases)) for name in ARMS},
        "local_ledger_sha256":m.digest(C/"verified.local.jsonl"),
    }
    write(HERE/"T6_EMBED_RESULT.json",data)
    write(HERE/"T6_BASELINE_UNION.json",{"scope":"KGW and Unigram only","planned_per_method":len(union),
                                        "verifier_ledger_sha256":data["local_ledger_sha256"],"sources":union})
    print("C frozen outcome ready to commit",data,flush=True)


def main():
    tasks=list(confirmed_sources())
    assert m.selftest()==5
    C.mkdir(exist_ok=True)
    texts=C/"outputs"; texts.mkdir(exist_ok=True)
    ledger=C/"verified.local.jsonl"
    completed={x["id"]:x for x in map(json.loads,ledger.read_text(encoding="utf-8").splitlines())} if ledger.exists() else {}
    if len(completed)==200:
        summarize(list(completed.values()))
        return
    m.METHODS=ARMS
    det=m.SentenceDetector()
    dev_lock=load(MATCHING/"M_FREEZE.json")
    assert sha(det.key)==dev_lock["secret_commitment_sha256"]
    # Reconstruct and rescore independently of the embedder's acceptance calculation.
    sd=load(ROOT/"var/results/hsw-st/certinsert_eval03_lite_20261112/run01/prepared_batch1/SCALE.json")["sd"]
    gpu_mem=int(subprocess.check_output(
        ["nvidia-smi","--query-gpu=memory.free","--format=csv,noheader,nounits"],text=True
    ).splitlines()[0])
    if gpu_mem<3500:
        raise RuntimeError("INSUFFICIENT_GPU_MEMORY_FOR_FROZEN_SCORER")
    scorer=m.Scorer(ROOT,m.PRIMARY,C,m.CUDA_VISIBLE)
    try:
        with ledger.open("a",encoding="utf-8",newline="\n") as stream:
            for task in tasks:
                ident=task["id"]
                if ident in completed:
                    continue
                row={"id":ident,"subject":task["subject"],"scoring_tokens":0,
                     "generation_finish":task["generation_finish"],"arms":{}}
                source=task["text"]
                if source is None:
                    row["arms"]={name:{"success":False,"status":"NOT_RUN_SOURCE_FAILED"} for name in ARMS}
                else:
                    row["source_output_sha256"]=task["source_output_sha256"]
                    row["source_p"]=det.p(source)
                    scorer.cache.clear()
                    before=scorer.tokens
                    p=source_plan(task,det)
                    result=m.paired(p,det,scorer,False,sd)
                    row.update(words=p["explanation_words"],scoring_tokens=scorer.tokens-before,
                               candidate_edges=result["candidate_edges"],
                               fixed_cache_sha256=sha(json.dumps(result["static_cache"],sort_keys=True).encode()))
                    for name, arm in result["arms"].items():
                        if arm["success"]:
                            rendered=reconstruct(source,arm)
                            pv=det.p(rendered)
                            arm["independent_verified"]=(sha(rendered.encode())==arm["output_sha256"]
                                and pv<.001 and pv==arm["p"]
                                and m.anchors(source)==m.anchors(rendered) and det.select(source)==det.select(rendered))
                            arm["p"]=pv
                            if arm["independent_verified"]:
                                (texts/(ident+"__"+name+".txt")).write_bytes(rendered.encode())
                            else:
                                arm.update(success=False,status="INDEPENDENT_RECHECK_FAILED")
                        for k in ("spans","changes","dynamic_step_costs"):
                            arm.pop(k,None)
                        row["arms"][name]=arm
                stream.write(json.dumps(row,ensure_ascii=False)+"\n")
                stream.flush()
                completed[ident]=row
                if len(completed)%10==0:
                    print("T6 embed verified",len(completed),200,"tokens",scorer.tokens,flush=True)
    finally:
        scorer.close()
    summarize(list(completed.values()))


if __name__=="__main__":
    main()
