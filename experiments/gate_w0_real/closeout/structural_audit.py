"""Read-only diagnostics for the frozen 180 endpoints and W0 suffix replay."""
import argparse
from collections import Counter, defaultdict
import hashlib
import re
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from evaluate import N, P, Codec, PREFIX, corpora, read, rows, save
from candidate import VOCAB


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract",type=Path,required=True)
    parser.add_argument("--data",type=Path,required=True)
    args = parser.parse_args()
    sources, releases = corpora()
    dev = [r for r in rows(P/"propagation/cases.jsonl") if r["partition"]=="calibration"]
    codec = Codec(sources,releases,dev)
    known = read(N/"candidates/summary.json")
    endpoints = rows(N/"real/pilot/cases.jsonl")
    annotations = {(r["case_id"],r["variant"]):r for r in rows(N/"real/pilot/annotations.jsonl")}
    previous = {(r["case_id"],r["method"]):r["pred_release"] for r in read(N/"real_decode_results.json")["predictions"]}
    assert len(endpoints)==len(annotations)==180
    events = {}
    for method in ("M1","M2","M3"):
        encoded = read(N/"candidates"/f"{method}_releases.json")
        events[method] = {}
        for r in encoded:
            assert codec.encode(method,codec.releases[r["release_id"]])["text"]==r["text"]
            events[method][r["release_id"]] = [(PREFIX.match(r["text"].splitlines()[i]).group(1,2),
                codec.units[r["source_id"]][i]["fact_id"], i+1) for i,_ in r["cert_inverse"]]
    grouped = defaultdict(Counter)
    survival = defaultdict(Counter)
    detail = []
    for row in endpoints:
        mid = row["variant"]
        label = annotations[row["case_id"],mid]
        body = row["text"]
        assert hashlib.sha256(body.encode()).hexdigest()==row["text_sha256"]==label["output_sha256"]
        observed = codec.inspect(body)
        reverse = ({c.casefold():k for k,c in codec.codebook(mid).items()} if mid!="plain" else {})
        tau = known.get(mid,known["M2"])["thresholds"]["selected"]
        frozen,_ = codec.decode("M2" if mid=="plain" else mid,observed,tau,reverse)
        assert sorted(frozen)==previous[row["case_id"],mid]
        stages = defaultdict(set)
        retained = set(label["retained_fact_ids"])
        supported = set(label["supported_release_ids"])
        by_event = []
        for rid in row["input_release_ids"]:
            for (a,b), fact, rank in events.get(mid,{}).get(rid,[]):
                # Same ordered adjacent code words, allowing punctuation and
                # whitespace changes. No semantic substitutions or word reorder.
                loose = bool(re.search(r"\b"+re.escape(a)+r"[\W_]+"+re.escape(b)+r"\b",body,re.I))
                literal = f"{a}, {b} that ".casefold() in body.casefold()
                code = f"{a} {b}".casefold()
                decoded_rows = [s for c,s in observed if c==code]
                threshold = any(s[fact]>=tau for s in decoded_rows) if mid!="M1" else bool(decoded_rows)
                passed = any(s[fact]>=tau and s[fact]-max(v for k,v in s.items() if k!=fact)>=.05
                             for s in decoded_rows) if mid!="M1" else bool(decoded_rows)
                state = dict(loose=loose,literal=literal,regex=bool(decoded_rows),threshold=threshold,margin=passed)
                for key,value in state.items():
                    if value:
                        stages[key].add(rid)
                if loose and (fact in retained if mid!="M1" else rid in supported):
                    stages["ideal_bound"].add(rid)
                if decoded_rows and (fact in retained if mid!="M1" else rid in supported):
                    stages["ideal_with_regex"].add(rid)
                by_event.append(dict(release=rid,fact=fact,rank=rank,retained=fact in retained,
                                     matching_scores=[dict(jaccard=s[fact], margin=s[fact]-max(
                                         v for k,v in s.items() if k!=fact)) for s in decoded_rows], **state))
                # M1 repeats the same codeword, so individual M1 copies
                # cannot be localized by these events. M2/M3 have distinct codes.
                if mid=="M3":
                    for g in ("all","model" if row["batch_id"] else "control",row["transform"]):
                        survival[g,rank].update(exposed=1,loose=loose,literal=literal,retained=fact in retained)
        for g in ("all","model" if row["batch_id"] else "control",row["transform"],f'depth{row["depth"]}'):
            c = grouped[mid,g]
            c.update(endpoints=1,input=len(row["input_release_ids"]),supported=len(supported),actual=len(frozen&supported))
            for k in ("loose","literal","regex","threshold","margin","ideal_bound","ideal_with_regex"):
                c[k] += len(stages[k]&supported)
            remaining = supported & stages["loose"]
            c["missing_code"] += len(supported-remaining)
            for stage,loss in (("regex","format_loss"),("threshold","threshold_loss"),("margin","margin_loss")):
                c[loss] += len(remaining-stages[stage])
                remaining &= stages[stage]
        detail.append(dict(case_id=row["case_id"],variant=mid,transform=row["transform"],depth=row["depth"],
                           supported=sorted(supported),actual=sorted(frozen), events=by_event,
                           stages={k:sorted(v) for k,v in stages.items()}))
    sys.path.insert(0,str(args.contract))
    from experiments.capd_gatew0_20261124 import w0
    from experiments.capd_e5_20261123.data import load_secrets
    from cogniguard.governance import provenance_evidence
    from gate_replay import replay
    suffix = Counter()
    suffix["own_adjacent_code"] = 0
    original = w0.transform
    valid = {tuple(w.casefold().split()) for w in VOCAB}

    def observe(text,kind):
        observed = original(text,kind)
        parts = text.split()
        prefix = PREFIX.match(text)
        if prefix and tuple(x.casefold() for x in prefix.group(1,2)) in valid:
            suffix["marked"] += 1
            suffix["prefix_disjoint"] += len(parts)-len(observed.split())>=3
            words = re.findall(r"\w+",observed.casefold())
            expected = tuple(x.casefold() for x in prefix.group(1,2))
            suffix["own_adjacent_code"] += expected in set(zip(words,words[1:]))
        return observed

    w0.transform = observe
    predicates=w0.load_predicates(args.data)
    for k in (16,32):
        pool=load_secrets(k,args.data)
        for seed in range(30):
            for mode in ("kbpw","union"):
                replay(w0,provenance_evidence,pool,predicates,seed,mode,True)
    assert suffix["marked"]==382
    result=dict(groups={f"{m}/{g}":dict(c) for (m,g),c in grouped.items()},
                m3={f"{g}/f{i}":dict(c,predicted=codec.survival[str(i)]) for (g,i),c in survival.items()},
                suffix=dict(suffix),detail=detail)
    save(HERE/"structural_counts.json",result)
    for k,v in result["groups"].items():
        if k.endswith(("/all","/model")):
            print(k,v)
    print(result["m3"],result["suffix"])


if __name__=="__main__":
    main()
