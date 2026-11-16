"""Materialize the frozen, chapter-disjoint T6 question split."""
import ast
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/"var/results/hsw-st/certinsert_eval04_final_20261116"
STAGE=ROOT/"var/results/hsw-st/certinsert_eval04_20261113/stage0"
RENDERER=ROOT/"experiments/hsw_insertion_feasibility_20261109_01/run08_long_prepare.py"
HISTORY=ROOT/"var/results/hsw-st/certinsert_eval03_lite_20261112/run01"
SEED="EVAL04-FINAL-20261116"
FIELDS=("physics","chemistry","biology","mathematics")
WORD=re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def write(path,value):
    with path.open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2)
        stream.write("\n")


def rank(kind,identifier):
    return sha(f"{SEED}|{kind}|{identifier}".encode())


def canonical(text):
    return " ".join(unicodedata.normalize("NFKC",text).casefold().split())


def tag(node):
    return node.tag.split("}")[-1]


def verify_prereg():
    freeze=load(HERE/"FINAL_FREEZE.json")
    assert sha((HERE/"FINAL_PREREG.md").read_bytes())==freeze["prereg_sha256"]
    for path,expected in freeze["files_sha256"].items():
        assert sha((ROOT/path).read_bytes())==expected,path
    return freeze


def metadata():
    allocation=load(STAGE/"CHAPTER_ALLOCATION.json")
    assert allocation["T6_content_reads"]==allocation["R_T6_module_intersection"]==0
    jobs={}
    reserved=set()
    for chapter,metadata in allocation["T6_reserved_chapter_metadata"].items():
        raw=metadata["subject"]
        subject="mathematics" if raw=="contemporary-mathematics" else raw
        for module in metadata["modules"]:
            repository=metadata["repo"]
            reserved.add((repository,module))
            if subject not in FIELDS:
                continue
            identifier=f"{repository}|{module}"
            jobs.setdefault(identifier,{"id":identifier,"repo":repository,"module":module,
                                       "revision":metadata["revision"],"subject":subject,"chapters":[]})
            assert jobs[identifier]["revision"]==metadata["revision"]
            jobs[identifier]["chapters"].append(chapter)
    r_modules={(row["repo"],module) for row in allocation["R_chapters"].values() for module in row["modules"]}
    assert not reserved & r_modules
    return [jobs[k] for k in sorted(jobs)]


def renderer():
    parsed=ast.parse(RENDERER.read_text(encoding="utf-8"))
    nodes=[x for x in parsed.body if isinstance(x,ast.FunctionDef) and x.name in ("math","render")]
    scope={}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(RENDERER),"exec"),scope)
    return scope["render"]


def fetch(job):
    folder=OUT/"raw"
    raw=folder/(rank("module",job["id"])[:24]+".cnxml")
    url=f"https://raw.githubusercontent.com/openstax/{job['repo']}/{job['revision']}/modules/{job['module']}/index.cnxml"
    if not raw.exists():
        for attempt in range(2):
            try:
                response=requests.get(url,timeout=(12,30))
                response.raise_for_status()
                assert len(response.content)<=2097152
                ET.fromstring(response.content)
                raw.write_bytes(response.content)
                break
            except (requests.RequestException,ET.ParseError,AssertionError) as error:
                if attempt:
                    return dict(job,status="FETCH_FAILED",url=url,error=type(error).__name__)
    return dict(job,status="FETCHED",url=url,raw=str(raw),raw_sha256=sha(raw.read_bytes()))


def extract(ledger,historical_hashes):
    render=renderer()
    known=set(historical_hashes)
    visited=Counter()
    candidates=[]
    for source in ledger:
        if source["status"]!="FETCHED":
            continue
        root=ET.fromstring(Path(source["raw"]).read_bytes())
        parents={child:node for node in root.iter() for child in node}
        for index,node in enumerate(root.iter()):
            if tag(node)!="problem":
                continue
            parent=parents.get(node)
            path=[]
            while parent is not None:
                path.append(tag(parent))
                parent=parents.get(parent)
            if "solution" in path:
                continue
            if any(tag(child) in ("table","image","figure","solution") for child in node.iter()):
                visited["unsupported_structure"]+=1
                continue
            try:
                text=re.sub(r"\n{3,}","\n\n",re.sub(r"[ \t]+"," ",render(node))).strip()
            except (IndexError,TypeError,ValueError):
                visited["renderer_failure"]+=1
                continue
            if "\\unsupported{" in text or "[cross-reference " in text or "[image " in text:
                visited["incomplete"]+=1
                continue
            if not 8<=len(WORD.findall(text))<=500:
                visited["length"]+=1
                continue
            norm=sha(canonical(text).encode())
            if norm in known:
                visited["duplicate"]+=1
                continue
            known.add(norm)
            source_id=f"{source['id']}|{node.get('id',str(index))}"
            case_id="T6_"+rank("case",source_id)[:24]
            candidates.append({"id":case_id,"source_id":source_id,"subject":source["subject"],
                               "question":text,"source_url":source["url"],"chapter_ids":source["chapters"],
                               "normalized_sha256":norm,"question_sha256":sha(text.encode()),
                               "source_sha256":source["raw_sha256"]})
    return candidates,dict(visited)


def select(candidates):
    pools={name:deque(sorted((r for r in candidates if r["subject"]==name),
                            key=lambda r:rank("question",r["source_id"]))) for name in FIELDS}
    selected=[]
    while len(selected)<200 and any(pools.values()):
        for name in FIELDS:
            if pools[name] and len(selected)<200:
                selected.append(pools[name].popleft())
    return selected


def main():
    verify_prereg()
    assert not (OUT/"sources.local.json").exists()
    (OUT/"raw").mkdir(exist_ok=True)
    jobs=metadata()
    print("Frozen reserved modules",len(jobs),flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows=list(pool.map(fetch,jobs))
    write(OUT/"fetch.json",rows)
    # Only use frozen R normalization and textual-free saved metadata for
    # historical deduplication. The older source documents are never opened.
    old={row.get("normalized_sha256") for row in load(STAGE/"RAG_CORPUS_MANIFEST.json")["records"]}
    old.update(sha(canonical(r["text"]).encode()) for r in load(STAGE/"R_GENERATION_QUESTIONS.json"))
    candidates,excluded=extract(rows,old)
    selected=select(candidates)
    write(OUT/"sources.local.json",selected)
    safe=[{k:v for k,v in row.items() if k!="question"} for row in selected]
    write(HERE/"T6_INPUT_MANIFEST.json",{
        "requested":200,"admitted":len(selected),"counts":dict(Counter(r["subject"] for r in selected)),
        "candidates":dict(Counter(r["subject"] for r in candidates)),"format_rejections":excluded,
        "fetch_failures":[dict(id=r["id"],status=r["status"],reason=r.get("error"))
                          for r in rows if r["status"]!="FETCHED"],
        "local_input_sha256":sha((OUT/"sources.local.json").read_bytes()),"sources":safe,
    })
    print("Frozen questions",len(selected),dict(Counter(r["subject"] for r in selected)),flush=True)


if __name__=="__main__":
    main()
