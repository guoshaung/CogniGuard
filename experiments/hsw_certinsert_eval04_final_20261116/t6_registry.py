"""Construct exact score inputs for verified T6 outputs."""
import argparse
import json
from pathlib import Path

from t6_sources import HERE, OUT, ROOT, load, sha, write

B=OUT/"stage_b_generation"
C=OUT/"stage_c_embedding"
D=OUT/"stage_d_model_arms"
CONTROL=OUT/"cpu_controls"
POST=OUT/"postmark"


def jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def item(identifier,method,location,expected=None):
    data=location.read_bytes()
    actual=sha(data)
    assert not expected or expected==actual,identifier
    return {"record_id":identifier+"__"+method,"id":identifier,"method":method,"sha256":actual,
            "path":location.relative_to(ROOT).as_posix()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--primary",action="store_true")
    args=p.parse_args()
    found=[]
    stages={}
    for source in load(B/"RESULT.json")["rows"]:
        if source["status"]=="COMPLETED" and source["format_pass"]:
            found.append(item(source["id"],"Fingerprint",B/"outputs"/(source["id"]+".txt"),source["output_sha256"]))
    evidence=jsonl(C/"verified.local.jsonl")
    assert len(evidence)==load(HERE/"T6_EMBED_RESULT.json")["planned"]==200
    for row in evidence:
        for name,a in row["arms"].items():
            if a["success"]:
                found.append(item(row["id"],name,C/"outputs"/(row["id"]+"__"+name+".txt"),a["output_sha256"]))
    for rc in jsonl(CONTROL/"rc/per_source.jsonl"):
        if rc["success"]:
            found.append(item(rc["id"],"RC",CONTROL/"rc/outputs"/(rc["id"]+".txt"),rc["output_sha256"]))
    baselines=(D/"baseline/RESULT.json")
    if not args.primary:
        if baselines.exists():
            for row in load(baselines)["results"]:
                if row["status"]=="COMPLETED":
                    found.append(item(row["source_id"],row["method"],D/"baseline/outputs"/(row["id"]+".txt"),
                                      row["output_sha256"]))
            stages["KGW_Unigram"]="COMPLETED"
        else:
            stages["KGW_Unigram"]="PENDING"
        if (POST/"RESULT.json").exists():
            for row in load(POST/"RESULT.json")["rows"]:
                if row["status"]=="COMPLETED":
                    found.append(item(row["id"],"PostMark",POST/"outputs"/(row["id"]+".txt"),row["output_sha256"]))
            stages["PostMark"]="COMPLETED"
        else:
            stages["PostMark"]="PENDING"
    tasks=sorted(found,key=lambda r:(r["method"],r["id"]))
    assert len({r["record_id"] for r in tasks})==len(tasks)
    out=OUT/("score_registry_primary.json" if args.primary else "score_registry.json")
    write(out,{"items":tasks,"stages":stages})
    print("registry",len(tasks),sha(out.read_bytes()))


if __name__=="__main__":
    main()
