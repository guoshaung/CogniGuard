"""Controlled comparison of three issuance codebooks with matched carrier budgets."""
import argparse
import hashlib
import itertools
import json
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent / "hsw_provenance"
sys.path.insert(0, str(PILOT))
from propagation.build import replay_marked

METHODS = ("M1", "M2", "M3", "M1+source")
# Two variable words plus "that" per event. Public research codebook.
VOCAB = tuple(f"{a} {b}" for a, b in itertools.product(
    ("Specifically","Notably","Indeed","Here","Thus","Accordingly","Overall","Conceptually","Mathematically","Practically"),
    ("consider","note","observe","recall","recognize","remember","see","check","verify","notice")))
PREFIX = re.compile(r"^(\w+), (\w+) that (.*)$", re.I)
WORD = re.compile(r"\w+")


def tokens(text):
    return set(WORD.findall(text.casefold()))


def overlap(text, reference):
    return len(text & reference) / max(1, len(text | reference))


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]


def dump(path, obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf8")


class Codec:
    def __init__(self, sources, releases, calibration):
        self.releases = {r["release_id"]:r for r in releases}
        self.units = {s["source_id"]:s["units"] for s in sources}
        self.refs = {u["fact_id"]:[tokens(u[k]) for k in ("text","light","strong")]
                     for units in self.units.values() for u in units}
        # Fixed domain rubric: the final answer usually takes precedence.
        self.weights = {u["fact_id"]: (1,1,2)[i] for units in self.units.values() for i,u in enumerate(units)}
        survived = Counter(u["fact_id"].rsplit(":f",1)[1] for c in calibration
                           for u in c["units"] if u["rendering"]=="original" and u["fact_id"])
        exposed = Counter(f.rsplit(":f",1)[1] for c in calibration for f in c["input_fact_ids"])
        self.survival = {rank:(survived[rank]+1)/(n+2) for rank,n in exposed.items()}
        self.book = {}
        for mode in ("M1","M2"):
            labels = [(rid,None) if mode=="M1" else (rid,u["fact_id"])
                      for rid,r in self.releases.items()
                      for u in ([None] if mode=="M1" else self.units[r["source_id"]])]
            codewords = sorted(VOCAB,key=lambda word:hashlib.sha256(("KBPW-v1|"+mode+"|"+word).encode()).digest())
            self.book[mode] = dict(zip(sorted(labels),codewords,strict=False))
            if len(labels)>len(codewords):
                raise ValueError("Codebook exhausted. This pilot is limited to 24 releases.")

    def codebook(self, method):
        return self.book["M1" if method.startswith("M1") else "M2"]

    def encode(self, method, release):
        lines = release["text"].splitlines()
        units = self.units[release["source_id"]]
        assert lines == [u["text"] for u in units]
        eligible = [i for i,line in enumerate(lines) if re.match(r"^[A-Z][a-z]+ ",line)]
        if method=="M3":
            eligible.sort(key=lambda i:(-self.weights[units[i]["fact_id"]]
                                       * self.survival.get(str(i+1),.5),i))
        inverse = []
        for i in eligible[:2]:
            fact = units[i]["fact_id"] if method in ("M2","M3") else None
            a,b = self.codebook(method)[release["release_id"],fact].split()
            inverse.append((i,lines[i][0]))
            lines[i] = f"{a}, {b} that {lines[i][0].lower()}{lines[i][1:]}"
        restored = lines[:]
        for idx, capital in inverse:
            body = PREFIX.match(lines[idx])[3]
            restored[idx] = capital+body[1:]
        assert "\n".join(restored)==release["text"]
        return dict(release,text="\n".join(lines),carrier_events=len(inverse),
                    inserted_words=3*len(inverse),cert_inverse=inverse)

    def inspect(self, text):
        rows = []
        for line in re.split(r"\n+|(?<=[.!?])\s+(?=[A-Z])",text.strip()):
            match = PREFIX.match(line)
            code = " ".join(match.groups()[:2]).casefold() if match else ""
            query = tokens(match[3] if match else line)
            fact_scores = {fact:max(overlap(query,r) for r in refs) for fact,refs in self.refs.items()}
            rows.append((code,fact_scores))
        return rows

    def decode(self, method, observed, threshold, reverse=None):
        if reverse is None:
            reverse = {word.casefold():label for label,word in self.codebook(method).items()}
        releases, facts = set(), set()
        for code, scores in observed:
            for fact, score in scores.items():
                if score >= .75:
                    facts.add(fact)
            if code not in reverse:
                continue
            rid, fact = reverse[code]
            source = self.releases[rid]["source_id"]
            if method=="M1":
                releases.add(rid)
            elif method=="M1+source" and max(scores[u["fact_id"]] for u in self.units[source]) >= threshold:
                releases.add(rid)
            elif fact is not None:
                other = max(score for name,score in scores.items() if name!=fact)
                if scores[fact]>=threshold and scores[fact]-other>=.05:
                    releases.add(rid)
        return releases, facts


def metrics(rows):
    result = {}
    for target in ("release","source","fact"):
        tp = fp = fn = exact_multi = multi = 0
        for p in rows:
            x,y = set(p[f"gold_{target}"]),set(p[f"pred_{target}"])
            tp += len(x & y)
            fp += len(y-x)
            fn += len(x-y)
            multi += len(x)>1
            exact_multi += len(x)>1 and x==y
        result[target] = dict(tp=tp,fp=fp,fn=fn,precision=tp/max(1,tp+fp),recall=tp/max(1,tp+fn),
                              f1=2*tp/max(1,2*tp+fp+fn),multi_exact=exact_multi/multi if multi else None)
    eligible = sum(len(p["eligible_release"]) for p in rows)
    recovered = sum(len(set(p["pred_release"]) & set(p["eligible_release"])) for p in rows)
    result["conditional_recall"] = recovered/max(1,eligible)
    result["seconds_median"] = statistics.median(r["seconds"] for r in rows)
    result["n"] = len(rows)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data",type=Path,default=PILOT/"propagation")
    parser.add_argument("--out",type=Path,default=HERE/"candidates")
    args = parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    sources = json.loads((args.data/"sources.json").read_bytes())
    releases = json.loads((args.data/"releases.json").read_bytes())
    cases = load_jsonl(args.data/"cases.jsonl")
    calibration = [c for c in cases if c["partition"]=="calibration"]
    codec = Codec(sources,releases,calibration)
    summary = {}
    for method in METHODS:
        start = time.perf_counter()
        encoded = [codec.encode(method,r) for r in releases]
        dump(args.out/f"{method}_releases.json",encoded)
        tagged = {r["release_id"] for r in encoded if r["carrier_events"]>0}
        reverse = {word.casefold():label for label,word in codec.codebook(method).items()}
        observations = []
        for c in replay_marked(cases,releases,encoded):
            tick = time.perf_counter()
            observed = codec.inspect(c["text"])
            observations.append((c, observed, time.perf_counter()-tick))
        dev = [(c,x) for c,x,_ in observations if c["partition"]=="calibration"]
        # Calibrate only against non-owners of facts in dev. Include a mismatched
        # carrier paired with each dev passage as a negative for the gate.
        thresholds = (.35,.45,.55,.65,.75,.85,.95)
        negatives = []
        for c,obs in dev:
            negatives.extend((rid,fact,score) for _,scores in obs
                             for (rid,fact),word in codec.codebook(method).items()
                             if rid not in c["retained_release_ids"] and fact is not None
                             for score in [scores[fact]])
        def calibrate(t):
            tp=fp=fn=0
            for c,obs in dev:
                pred,_=codec.decode(method,obs,t,reverse)
                gold=set(c["retained_release_ids"])
                tp+=len(pred&gold)
                fp+=len(pred-gold)
                fn+=len(gold-pred)
            return (2*tp/max(1,2*tp+fp+fn),t)
        threshold = max(map(calibrate,thresholds))[1]
        rows=[]
        for c,obs,inspection_seconds in observations:
            if c["partition"]=="calibration":
                continue
            start_decode=time.perf_counter()
            pred,facts=codec.decode(method,obs,threshold,reverse)
            rows.append(dict(case_id=c["case_id"],depth=c["depth"],transform=c["transform"],
                             pred_release=sorted(pred),gold_release=c["retained_release_ids"],
                             pred_source=sorted({codec.releases[r]["source_id"] for r in pred}),
                             gold_source=c["retained_source_ids"],pred_fact=sorted(facts),gold_fact=c["retained_fact_ids"],
                             eligible_release=sorted(tagged&set(c["retained_release_ids"])),
                             seconds=inspection_seconds+time.perf_counter()-start_decode))
        stress = orphan_cases(codec,method,threshold,reverse)
        dump(args.out/f"{method}_stress.json",stress)
        summary[method] = dict(total=metrics(rows), thresholds=dict(selected=threshold,candidates=thresholds,
                               objective="calibration partition release micro-F1, ties higher",
                               synthetic_wrong_release_fact_pairs=len(negatives),
                               wrong_pair_fraction_at_threshold=sum(s>=threshold for _,_,s in negatives)/max(1,len(negatives))),
                               by_depth={d:metrics([r for r in rows if r["depth"]==d]) for d in (1,3,5)},
                               strong=metrics([r for r in rows if r["transform"]=="strong_rewrite"]),
                               tagged_releases=len(tagged), release_count=len(releases),
                               carrier_events=sum(r["carrier_events"] for r in encoded),
                               inserted_words=sum(r["inserted_words"] for r in encoded),
                               orphan_supported_fp=sum(len(set(r["pred_release"])-set(r["supported_release_ids"])) for r in stress),
                               elapsed_seconds=time.perf_counter()-start,gpu_hours=0)
        with (args.out/f"{method}_predictions.jsonl").open("w",encoding="utf8") as stream:
            for row in rows:
                stream.write(json.dumps(row)+"\n")
    dump(args.out/"summary.json",summary)
    dump(args.out/"config.json",dict(max_events=2,words_per_event=3,salience=[1,1,2],
                                    calibrated_survival=codec.survival,calibration_n=len(calibration),
                                    corpus_sha256=hashlib.sha256((args.data/"cases.jsonl").read_bytes()).hexdigest(),
                                    label_matching="public experimental codebook",rewrite_replay="original-line transport"))
    for method,row in summary.items():
        print(method,row["tagged_releases"],row["total"]["release"],row["orphan_supported_fp"],flush=True)


def orphan_cases(codec, method, threshold, reverse):
    by_source=defaultdict(list)
    for r in codec.releases.values():
        by_source[r["source_id"]].append(r)
    a,b = next(iter(by_source.values()))
    c = list(by_source.values())[1][0]
    marked=codec.encode(method,a)["text"].splitlines()
    other=codec.encode(method,c)["text"].splitlines()
    tagged=[line for line in marked if PREFIX.match(line)]
    tagged_other=[line for line in other if PREFIX.match(line)]
    line=tagged[0]
    prefix=PREFIX.match(line)
    orphan=prefix[1]+", "+prefix[2]+" that the next class takes place in a different room."
    a_id,b_id,c_id=(r["release_id"] for r in (a,b,c))
    fact_a=codec.units[a["source_id"]][marked.index(line)]["fact_id"]
    fact_c=codec.units[c["source_id"]][other.index(tagged_other[0])]["fact_id"]
    # Distinct histories, support (retained and causally inherited) and compatibility.
    cases=[
        ("all_deleted",orphan,[a_id],[],[],[]),
        ("part_deleted",line+"\n"+orphan,[a_id],[a_id],[a["source_id"]],[fact_a]),
        ("copied_unrelated",orphan,[],[],[],[]),
        ("mixed_markers",line+"\n"+tagged_other[0],[a_id,c_id],[a_id,c_id],[a["source_id"],c["source_id"]],[fact_a,fact_c]),
        ("swapped_binding",prefix[1]+", "+prefix[2]+" that "+PREFIX.match(tagged_other[0])[3],
         [a_id,c_id],[c_id],[c["source_id"]],[fact_c]),
        ("identical_two_issues",line,[a_id],[a_id],[a["source_id"]],[fact_a]),
        ("independent_same_fact",line,[],[],[a["source_id"]],[fact_a]),
    ]
    rows=[]
    for name,text,history,support,sources,facts in cases:
        pred,compatible=codec.decode(method,codec.inspect(text),threshold,reverse)
        rows.append(dict(case_id=name,text=text,history_release_ids=history,supported_release_ids=support,
                         compatible_source_ids=sources,retained_fact_ids=facts,
                         identical_candidate_release_ids=sorted({a_id,b_id}) if a["source_id"] in sources else [],
                         pred_release=sorted(pred),pred_fact=sorted(compatible)))
    return rows


if __name__=="__main__":
    main()
