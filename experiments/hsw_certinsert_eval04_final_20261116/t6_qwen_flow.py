"""Use the spare Qwen slot for primary compression after Unigram."""
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from t6_sources import HERE, OUT, ROOT, load, sha, write
from t6_model_arms import EVAL, KGW_SOURCE, OLD, STUDY, Server, configure, file_hash, kgw, ordinary, tokenizer


def folder(stage):
    base=STUDY/stage
    for sub in ("records","outputs"):
        (base/sub).mkdir(exist_ok=True,parents=True)
    return base


def main():
    freeze,config=configure()
    sys.path.insert(0,str(KGW_SOURCE))
    for filename,digest in freeze["kgw_reference_sha256"].items():
        assert file_hash(KGW_SOURCE/"kgw_ref"/filename)==digest,filename
    key=(OLD/"frozen_comparison09/restricted/kgw_key.txt").read_text(encoding="utf-8")
    mask=load(EVAL/"restricted/UNIGRAM_GREEN.json")
    assert sha(key.encode())==freeze["kgw_key_sha256"]
    union=load(HERE/"T6_BASELINE_UNION.json")["sources"]
    assert len(union)==freeze["planned"]
    original=OUT/"stage_b_generation/outputs"
    registry=OUT/"score_registry_primary.json"
    assert file_hash(registry)==load(HERE/"T6_PRIMARY_VARIANT_FREEZE.json")["registry_sha256"]
    planned=load(registry)["items"]
    base=folder("baseline")
    compress=folder("compress")
    server=Server(config["model7b"],config["server"],base)
    try:
        from tokenizers import Tokenizer
        spec=load(EVAL/"PUBLIC_TOKENIZER_VALIDATION.json")
        assert file_hash(spec["path"])==spec["sha256"]
        probe="A value of 2 kg. The formula is F = ma."
        assert tokenizer(server,probe)==Tokenizer.from_file(spec["path"]).encode(probe,add_special_tokens=False).ids
        gate=base/"TOKENIZER_ADMISSION.json"
        if not gate.exists():
            write(gate,{"public_tokenization_match":True,"tokenizer_sha256":spec["sha256"]})

        def run(method):
            results=[]
            for row in union:
                ident=row["id"]
                text=(original/(ident+".txt")).read_bytes()
                assert sha(text)==row["source_output_sha256"]
                response=(kgw(server,base,ident,text.decode(),config["rewrite_prompt"],key) if method=="KGW"
                          else ordinary(server,base,ident,ident,text.decode(),config["rewrite_prompt"],method,"none",mask))
                results.append(response)
                print(method,len(results),len(union),response["status"],flush=True)
            status_path=base/(method+"_ROWS.json")
            if not status_path.exists():
                write(status_path,{"rows":results,"planned":len(union)})
            return results

        def slot1():
            rows=run("Unigram")
            compression=[]
            brief=config["attacks"]["concise"].format(ratio=70)
            for task in planned:
                text=(ROOT/task["path"]).read_bytes()
                assert sha(text)==task["sha256"]
                compression.append(ordinary(server,compress,task["record_id"],task["id"],text.decode(),
                                             brief,task["method"],"compress70"))
                if len(compression)%10==0:
                    print("primary compression",len(compression),len(planned),flush=True)
            if not (compress/"PRIMARY_RESULT.json").exists():
                write(compress/"PRIMARY_RESULT.json",{"planned":len(planned),"results":compression})
            return rows

        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(run,"KGW")
            second=pool.submit(slot1)
            results=first.result()+second.result()
    finally:
        server.close()
    write(base/"RESULT.json",{"results":results,"statuses":dict(Counter(r["status"] for r in results)),
                            "count":len(results),"server_stopped":True})


if __name__=="__main__":
    main()
