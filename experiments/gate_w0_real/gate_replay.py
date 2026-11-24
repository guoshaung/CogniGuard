"""Gate W0-Real synthetic control replay against the pinned governance checkout."""
import argparse
from collections import Counter
import csv
import hashlib
from pathlib import Path
import sys

from evaluate import HERE, Codec, jsonl, save
from candidate import VOCAB, tokens, tokens
from evidence import pe


def replay(w0, ev, secrets, predicates, seed, mode, marked):
    world = w0.make_world(secrets, seed=seed, graph="sparse", f=8, f_true=8, mode="coalition")
    truth = {a:{} for a in world.agents}
    belief = {a:frozenset() for a in world.agents}
    index = w0.Index()
    codec = object.__new__(Codec)
    codec.refs, codec.releases = {}, {}
    reverse, unit_map = {}, {}
    evidence, result = [], Counter()
    issued = 0
    vocabulary = sorted(VOCAB,key=lambda w:hashlib.sha256(("KBPW-v1|M2|"+w).encode()).digest())
    for turn,req in enumerate(world.stream.requests):
        for edge,(sender,receiver) in enumerate(world.events.get(turn,[])):
            content = dict(truth[sender])
            truth[receiver].update(content)
            event_records = []
            for number,(text,issue_id) in enumerate(content.values()):
                obs = w0.transform(text,"fragment")
                found = set()
                if mode in ("bm25","union"):
                    found |= {u for u,_ in index.bm25(obs)}
                detected = set()
                if mode in ("kbpw","union"):
                    detected,_ = codec.decode("M2",codec.inspect(obs),.95,reverse)
                    found |= {unit_map[r] for r in detected}
                artifact = hashlib.sha256(f"{secrets[0].K}|{seed}|{mode}|{marked}|{turn}|{edge}|{number}".encode()).hexdigest()[:24]
                record = pe(artifact,receiver,"kbpw" if mode=="kbpw" else "retrieval",[],detected,found,
                            {},False,observed=float(turn))
                if found:
                    # W0 treats all returned units as evidence. Retrieval matches
                    # remain unverified in the envelope, though the gate adds them.
                    record["verification_status"] = "unverified" if mode!="kbpw" else "content_verified"
                record["extra"].update(fragment_words=len(obs.split()),condition="frozen_W0_last_five",
                                       query_sha256=hashlib.sha256(obs.encode()).hexdigest(),mode=mode)
                event_records.append(ev.ProvenanceEvidence.from_dict(record))
                evidence.append(record)
                result["observations"] += 1
                result["observations_originally_marked"] += str(issue_id) in unit_map
                result["observations_with_kbpw"] += bool(detected)
            true_units = set(content)
            got = set().union(*(set(ev.holding_units(r)) for r in event_records))
            result.update(unit_tp=len(got&true_units),unit_fp=len(got-true_units),unit_fn=len(true_units-got))
            assert ev.trusted_event_credits(event_records)==0
            belief = ev.augment_knowledge(belief,event_records)
        recipient,unit = req.recipient_id,req.unit
        oracle = w0.check_release(world.registry,recipient,{unit},
                                   w0._frozen({a:set(v) for a,v in truth.items()}),w0.K_DEFENSE).safe
        ok = w0.check_release(world.registry,recipient,{unit},belief,w0.K_DEFENSE).safe
        if ok:
            issued += 1
            text = w0._issued_text(unit,predicates[unit],recipient,False)
            published = text
            if marked and issued<=len(vocabulary):
                issue, fact = str(issued),f"gate:{issued}"
                word,verb = vocabulary[issued-1].split()
                published = f"{word}, {verb} that {text[0].lower()+text[1:]}"
                reverse[vocabulary[issued-1].casefold()] = issue,fact
                codec.refs[fact] = [tokens(text)]
                codec.releases[issue] = {"source_id":str(unit[0])}
                unit_map[issue] = unit
                result["embedded"] += 1
            truth[recipient][unit] = published,issued
            belief[recipient] |= {unit}
            index.add(published,unit,issued)
            result["harmful_releases"] += not oracle
        if req.role=="normal":
            result["normal"] += 1
            result["normal_allowed"] += ok
            result["unneeded"] += not ok and oracle
    n=result["normal"]
    summary=dict(K=secrets[0].K,seed=seed,mode=mode,marked=marked,issued=issued,
                 harmful_releases=result["harmful_releases"],UR_normal=.4+.6*result["normal_allowed"]/n,
                 unneeded_refusal_rate=result["unneeded"]/n,
                 **{k:result[k] for k in ("observations","observations_originally_marked","observations_with_kbpw","embedded","unit_tp","unit_fp","unit_fn")})
    return summary,evidence


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("contract","data","out"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--seeds",type=int,default=30)
    a=p.parse_args()
    sys.path.insert(0,str(a.contract.resolve()))
    from experiments.capd_gatew0_20261124 import w0
    from experiments.capd_e5_20261123.data import load_secrets
    from cogniguard.governance import provenance_evidence as ev
    a.out.mkdir(parents=True,exist_ok=True)
    predictions, records=[],[]
    predicates = w0.load_predicates(a.data)
    for k in (16,32):
        pool=load_secrets(k,a.data)
        for seed in range(a.seeds):
            for mode,marked in (("bm25",False),("bm25",True),("kbpw",True),("union",True)):
                result, evidence = replay(w0,ev,pool,predicates,seed,mode,marked)
                predictions.append(result)
                records.extend(evidence)
    with (a.out/"control.csv").open("w",encoding="utf8",newline="") as dst:
        writer=csv.DictWriter(dst,fieldnames=predictions[0])
        writer.writeheader()
        writer.writerows(predictions)
    jsonl(a.out/"gate_evidence.jsonl",records)
    baseline = {(r["K"],r["seed"]):r for r in predictions if r["mode"]=="bm25" and r["marked"]}
    combo = [r for r in predictions if r["mode"]=="union"]
    fields = ("harmful_releases","UR_normal","unneeded_refusal_rate")
    frozen_path = a.contract/"experiments/capd_gatew0_20261124/results/control.csv"
    with frozen_path.open(encoding="utf8",newline="") as stream:
        frozen = {(int(r["K"]),int(r["seed"])):r for r in csv.DictReader(stream)
                  if r["method"]=="F3_bm25" and r["transform"]=="fragment"}
    regenerated = [r for r in predictions if r["mode"]=="bm25" and not r["marked"]]
    audit = sum(all(abs(r[x]-float(frozen[r["K"],r["seed"]][x]))<1e-9 for x in fields) for r in regenerated)
    summary=dict(runs=len(predictions), observations=len(records), frozen_w0_bm25_cells_matching=audit,
                 regenerated_baseline_cells=len(regenerated), actual_kbpw_hits=sum(r["observations_with_kbpw"] for r in predictions),
                 marked_observations_scored_by_kbpw=sum(r["observations_originally_marked"] for r in predictions
                                                       if r["mode"] in ("kbpw","union")),
                 decision_metric_changes=sum(any(r[x]!=baseline[r["K"],r["seed"]][x] for x in fields) for r in combo),
                 axes="Gate W0 synthetic K16/K32 last-five suffix, same world seeds; finite existing M2 vocabulary and 100 issuance cap",
                 per_K={k:{mode:sum(r["harmful_releases"] for r in predictions if r["K"]==k and r["mode"]==mode and r["marked"])
                           for mode in ("kbpw","bm25","union")} for k in (16,32)})
    save(a.out/"gate_summary.json",summary)
    print(summary)


if __name__=="__main__":
    main()
