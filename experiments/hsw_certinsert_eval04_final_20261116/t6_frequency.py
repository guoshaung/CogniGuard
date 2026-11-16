"""Construct preregistered offline P1 lexical robustness cases."""
import argparse
import ast
import collections
import json
import re
import sys

from t6_sources import HERE, OUT, ROOT, load, rank, sha, write

LEGACY=ROOT/"experiments/hsw_certinsert_eval03_batch2_adjusted_20261112/prepare_attacks.py"
BASE=ROOT/"var/results/hsw-st/certinsert_eval03_lite_20261112/run01/batch02_adjusted/data"
P1=OUT/"frequency"
sys.path.insert(0,str(ROOT/"experiments/hsw_english_replication_20261110_01"))
from capacity_shared_v32 import nlp


def read_text(task):
    data=(ROOT/task["path"]).read_bytes()
    assert sha(data)==task["sha256"]
    return data.decode()


def generate_spoof(reference,target,terms,spans,block):
    tokens=list(re.finditer(r"[A-Za-z]+(?:['’-][A-Za-z]+)*",target))
    budget=int(.06*len(tokens))
    slots=[]
    for a,z in spans(target):
        start=re.search("[A-Za-z]",target[a:z])
        if not start:
            continue
        a+=start.start()
        first=re.match("[A-Za-z]+",target[a:])[0].lower()
        if first not in block and a>=reference.get("body_start",0):
            slots.append(a)
    slots.sort(key=lambda a:rank("spoof_position",f"{reference['id']}|{a}"))
    chosen=[]
    group=set()
    used=0
    for term in terms:
        word_cost=len(term.split())
        category=" ".join(term.split()[:2])
        if category in group or used+word_cost>budget:
            continue
        pos=next((a for a in slots if all(sum(min(a,b)<=w.start()<max(a,b) for w in tokens)>=8 for b,_ in chosen)),None)
        if pos is None:
            continue
        chosen.append((pos,term[0].upper()+term[1:]+", "))
        slots.remove(pos)
        group.add(category)
        used+=word_cost
    for i,text in sorted(chosen,reverse=True):
        target=target[:i]+text+target[i:]
    return target,len(chosen)


def erase(text,terms,spans):
    edits=[]
    for a,z in spans(text):
        here=text[a:z]
        start=a+len(here)-len(here.lstrip())
        for w in terms:
            match=re.match(re.escape(w)+r",\s*",text[start:z],re.I)
            if match:
                edits.append((start,start+match.end()))
                break
    for a,z in sorted(edits,reverse=True):
        text=text[:a]+text[z:]
    return text,len(edits)


def main():
    args=argparse.ArgumentParser(description=__doc__)
    args.add_argument("--primary",action="store_true")
    opt=args.parse_args()
    registry=OUT/("score_registry_primary.json" if opt.primary else "score_registry.json")
    freeze=load(HERE/("T6_PRIMARY_VARIANT_FREEZE.json" if opt.primary else "T6_VARIANT_FREEZE.json"))
    assert sha(registry.read_bytes())==freeze["registry_sha256"]
    tree=ast.parse(LEGACY.read_text(encoding="utf-8"))
    module=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in ("spans","prefixes")]
    scope={"nlp":nlp,"re":re}
    exec(compile(ast.Module(body=module,type_ignores=[]),str(LEGACY),"exec"),scope)
    spans=scope["spans"]
    prefixes=scope["prefixes"]
    block=set("then thus so therefore hence however next now first finally".split())
    b=load(BASE/"LEARNING_BACKGROUND.json")
    targets=load(BASE/"SPOOF_TARGETS.json")
    assert len(b)==100 and len(targets)==200 and not {r["id"] for r in b}&{r["id"] for r in targets}
    bp=collections.Counter(w for r in b for w in prefixes(r["text"]))
    items=load(registry)["items"]
    pool=collections.defaultdict(list)
    admission={}
    source_ids={x["id"]:x["source_id"] for x in load(OUT/"sources.local.json")}
    medium=load(HERE/"FINAL_PREREG_ADDENDUM_FREEZE.json")
    for path,digest in medium["files_sha256"].items():
        assert sha((ROOT/path).read_bytes())==digest,path
    embed=[json.loads(l) for l in (OUT/"stage_c_embedding/verified.local.jsonl").read_text(encoding="utf-8").splitlines()]
    not_inserted={(row["id"],name) for row in embed for name,arm in row["arms"].items() if arm.get("insertions",0)==0}
    rc=[json.loads(l) for l in (OUT/"cpu_controls/rc/per_source.jsonl").read_text(encoding="utf-8").splitlines()]
    not_inserted.update((row["id"],"RC") for row in rc if row.get("insertions",0)==0)
    for x in items:
        if x["method"]!="Fingerprint" and (x["id"],x["method"]) not in not_inserted:
            # For rewriting baselines the registry records execution; admission
            # follows a separately generated public score freeze when available.
            if x["method"] in ("KGW","Unigram","PostMark"):
                score=OUT/"baseline_public_gate.json"
                if not score.exists() or x["record_id"] not in load(score)["passing"]:
                    continue
            pool[x["method"]].append(x)
    P1.mkdir(exist_ok=True)
    folder=P1/("primary" if opt.primary else "all")
    folder.mkdir(exist_ok=False)
    cases=[]
    for method in sorted({r["method"] for r in items if r["method"]!="Fingerprint"}):
        group=sorted(pool[method],key=lambda r:rank("observe",source_ids[r["id"]]))
        cached={r["id"]:read_text(r) for r in group}
        seen={i:prefixes(text) for i,text in cached.items()}
        admission[method]={}
        for observed in (10,50,200):
            info={"available":len(group),"requested":observed}
            admission[method][str(observed)] = info
            if len(group)<observed:
                info["status"]="NOT_AVAILABLE"
                continue
            info["status"]="AVAILABLE"
            ids={r["id"] for r in group[:observed]}
            info["observe_sha256"]=sha(json.dumps([r["sha256"] for r in group[:observed]]).encode())
            exposed=collections.Counter(w for i in ids for w in seen[i])
            ordered=sorted(exposed,key=lambda w:(-(exposed[w]/observed-bp[w]/100),w))
            for width in (4,8):
                lexicon=ordered[:width]
                for attack in ("spoof","scrub"):
                    queue=targets if attack=="spoof" else [r for r in group if r["id"] not in ids]
                    for record in queue:
                        identifier=record["id"]
                        outcome,edits=(generate_spoof(record,record["text"],lexicon,spans,block)
                                       if attack=="spoof" else erase(cached[identifier],lexicon,spans))
                        task_id=rank("p1",f"{method}|{observed}|{width}|{attack}|{identifier}")[:24]
                        cases.append({"id":task_id,"source_id":identifier,"method":method,"N":observed,"m":width,
                                      "attack":attack,"edits":edits,"learned":len(lexicon),
                                      "sha256":sha(outcome.encode()),"text":outcome})
        print("Generated P1 cases",method,len(cases),flush=True)
    write(folder/"inputs.local.json",cases)
    write(folder/"manifest.json",{"planned":len(cases),"conditions":admission,
                                  "inputs_sha256":sha((folder/"inputs.local.json").read_bytes())})


if __name__=="__main__":
    main()
