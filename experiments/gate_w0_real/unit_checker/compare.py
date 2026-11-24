"""Offline unit-checker ablation on frozen endpoint bytes and requests."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time

from fixtures import DEV, STRESS, cases

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CLOSE = HERE.parent / "closeout"
PILOT = ROOT / "experiments/hsw_provenance_next"
METHODS = ("containment", "bge_unit", "nli", "nli_consistency")
SEMANTIC = METHODS[1:]
NUMBER = re.compile(r"(?<![\w.])[-+]?(?:\d+/\d+|\d+(?:\.\d+)?)")
UNITS = {
    "seconds": "s", "second": "s", "s": "s", "minutes": "min", "minute": "min", "min": "min",
    "meters": "m", "metres": "m", "meter": "m", "metre": "m", "m": "m",
    "centimeters": "cm", "centimeter": "cm", "cm": "cm", "millimeters": "mm", "mm": "mm",
    "joules": "j", "joule": "j", "j": "j", "kilojoules": "kj", "kj": "kj",
    "volts": "v", "volt": "v", "v": "v", "millifarads": "mf", "mf": "mf",
    "microfarads": "µf", "µf": "µf", "μf": "µf", "ohm": "ohm", "ohms": "ohm", "ω": "ohm",
    "newtons": "n", "newton": "n", "n": "n", "kilograms": "kg", "kg": "kg", "grams": "g", "g": "g",
    "percent": "%", "%": "%", "m/s": "m/s", "m/s²": "m/s²",
}
UNIT = re.compile(r"^\s*(?:-|\s)?("+"|".join(map(re.escape, sorted(UNITS,key=len,reverse=True)))+r")(?![\w/²])")
CUES = {
    "outside_focal": r"\b(?:outside|beyond) (?:its |the )?focal",
    "constant_temperature": r"constant temperature|temperature stays fixed|isothermal",
    "constant_pressure": r"constant pressure|pressure (?:stays fixed|held constant)",
    "linear_range": r"linear (?:range|regime)",
    "right_triangle": r"right triangle|perpendicular (?:legs|sides)",
    "completed_survey": r"completed (?:the survey|responses)|finished the survey",
    "independent": r"\bindependent\b|\bseparate fair\b",
    "uniform": r"\buniform\b",
    "exponential": r"\bexponential\b",
    "horizontal": r"\bhorizontal(?:ly)?\b",
    "uncharged": r"\buncharged\b|charg(?:ing|ed) from zero",
    "series": r"\bseries\b",
    "closed": r"\bclosed\b",
}
NEG = re.compile(r"\b(?:not|never|no|cannot|without)\b|n't\b")


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]


def write(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf8")


def jsonl(path, values):
    with path.open("w",encoding="utf8") as dst:
        for value in values:
            dst.write(json.dumps(value,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n")


def sha(path):
    with path.open("rb") as src:
        return hashlib.file_digest(src,"sha256").hexdigest()


def windows(text):
    parts = [part.strip() for part in re.split(r"\n+|(?<=[.!?])\s+",text) if part.strip()]
    return list(dict.fromkeys(parts + [a+" "+b for a,b in zip(parts,parts[1:])]))


def profile(text):
    text = text.casefold().replace("μ","µ").replace("−","-")
    text = re.sub(r"(?<=\d),(?=\d{3}\b)","",text)
    for word,value in (("zero","0"),("one","1"),("two","2"),("three","3")):
        text = re.sub(r"\b"+word+r"\b",value,text)
    numbers, quantities = set(), set()
    for match in NUMBER.finditer(text):
        try:
            number = Fraction(match[0])
        except ZeroDivisionError:
            continue
        numbers.add(number)
        unit = UNIT.match(text[match.end():])
        if unit:
            quantities.add((number,UNITS[unit[1]]))
    return numbers, quantities, {name for name,rx in CUES.items() if re.search(rx,text)}, bool(NEG.search(text))


def guard(premise, reference):
    pnum,punits,pconditions,pneg = profile(premise)
    rnum,runits,rconditions,rneg = profile(reference)
    return [name for name,good in (
        ("number",rnum <= pnum),("unit",runits <= punits),
        ("condition",rconditions <= pconditions),("negation",rneg == pneg),
    ) if not good]


def pairs_for(text, refs):
    return [(window,ref) for window in windows(text) for ref in refs]


class Models:
    def __init__(self, bge, nli, device):
        import torch
        from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.device = device
        torch.set_num_threads(4)
        self.btok = AutoTokenizer.from_pretrained(bge,local_files_only=True)
        self.ntok = AutoTokenizer.from_pretrained(nli,local_files_only=True)
        self.bge = AutoModel.from_pretrained(bge,local_files_only=True).eval().to(device)
        self.nli = AutoModelForSequenceClassification.from_pretrained(nli,local_files_only=True).eval().to(device)
        self.entail = next(i for i,label in self.nli.config.id2label.items() if label.lower()=="entailment")

    def score(self, groups):
        torch = self.torch
        pairs = list(dict.fromkeys(pair for group in groups for pair in group))
        strings = list(dict.fromkeys(s for pair in pairs for s in pair))
        vectors, probabilities = {}, {}
        clock = time.perf_counter()
        with torch.inference_mode():
            for start in range(0,len(strings),32):
                batch = strings[start:start+32]
                inputs = self.btok(batch,padding=True,truncation=True,max_length=384,return_tensors="pt").to(self.device)
                values = torch.nn.functional.normalize(self.bge(**inputs).last_hidden_state[:,0],dim=1).cpu().numpy()
                vectors.update(zip(batch,values,strict=True))
            cosine = {(p,h):float(vectors[p]@vectors[h]) for p,h in pairs}
            bge_seconds = time.perf_counter()-clock
            clock = time.perf_counter()
            for start in range(0,len(pairs),32):
                batch = pairs[start:start+32]
                p,h = zip(*batch)
                inputs = self.ntok(list(p),list(h),padding=True,truncation=True,max_length=384,return_tensors="pt").to(self.device)
                values = self.nli(**inputs).logits.softmax(dim=1)[:,self.entail].cpu().tolist()
                probabilities.update(zip(batch,values,strict=True))
        nli_seconds = time.perf_counter()-clock
        clock = time.perf_counter()
        failures = {pair:guard(*pair) for pair in pairs}
        output = []
        for group in groups:
            values = {"bge_unit":cosine, "nli":probabilities}
            row = {}
            for method, mapping in values.items():
                best = max(group,key=mapping.__getitem__,default=None)
                row[method] = {"score":mapping[best] if best else None,"pair":best}
            passing = [pair for pair in group if not failures[pair]]
            best = max(passing,key=probabilities.__getitem__,default=None)
            row["nli_consistency"] = {"score":probabilities[best] if best else None,"pair":best,
                                      "veto_at_nli_best":failures.get(row["nli"]["pair"],[])}
            output.append(row)
        return output,dict(bge_seconds=bge_seconds,nli_seconds=nli_seconds,
                           consistency_seconds=time.perf_counter()-clock,unique_pairs=len(pairs))


def accepts(record, threshold):
    return record["score"] is not None and record["score"] >= threshold


def summarize(counter):
    tp,fp,fn,tn = (counter[k] for k in ("tp","fp","fn","tn"))
    def div(a,b):
        return a/b if b else None
    return dict(tp=tp,fp=fp,fn=fn,tn=tn,precision=div(tp,tp+fp),recall=div(tp,tp+fn),
                f1=div(2*tp,2*tp+fp+fn),false_confirmation_rate=div(fp,fp+tn),
                false_discovery_rate=div(fp,tp+fp))


def update(counter, expected, predicted, candidates):
    counter.update(tp=len(expected&predicted), fp=len(predicted-expected),fn=len(expected-predicted),
                   tn=len(candidates-expected-predicted))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("contract","bge","nli","out"):
        parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--device",default="cpu")
    args = parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(args.contract.resolve()))
    from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
    from cogniguard.governance.principals import AssetOwnership, Membership
    from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
    from cogniguard.provenance.decision import CapdPolicy
    from cogniguard.provenance.interfaces import Artifact
    from cogniguard.provenance.schema import DisclosureRequest, Observation, Presence
    from cogniguard.provenance.state import SecurityState
    from cogniguard.provenance.verify import RuleVerifier, TextUnitChecker

    dev = list(cases(DEV,"dev"))
    jsonl(args.out/"development.jsonl",dev)
    start = time.perf_counter()
    engine = Models(args.bge,args.nli,args.device)
    load_seconds = time.perf_counter()-start
    dev_scores,dev_time = engine.score([pairs_for(r["text"],[r["fact"]]) for r in dev])
    thresholds = {}
    for method in SEMANTIC:
        negatives = [s[method]["score"] for r,s in zip(dev,dev_scores,strict=True)
                     if not r["present"] and s[method]["score"] is not None]
        assert negatives
        thresholds[method] = math.nextafter(max(negatives),math.inf)
    lock = dict(thresholds=thresholds,development_sha256=sha(args.out/"development.jsonl"),
                protocol_sha256=sha(HERE/"PROTOCOL.md"),implementation_sha256=sha(Path(__file__)),
                models={name:{"directory":folder.name,"weights_sha256":sha(folder/"model.safetensors"),
                              "config_sha256":sha(folder/"config.json"),"tokenizer_sha256":sha(folder/"tokenizer.json")}
                        for name,folder in (("bge",args.bge),("nli",args.nli))},device=args.device)
    write(args.out/"threshold_lock.json",lock)
    jsonl(args.out/"dev_scores.jsonl",[dict(r,scores=s) for r,s in zip(dev,dev_scores,strict=True)])
    print("Thresholds frozen",thresholds,flush=True)

    stress = list(cases(STRESS,"stress"))
    catalog = json.loads((ROOT/"experiments/hsw_provenance/propagation/sources.json").read_bytes())
    assert not ({r["source"] for r in dev}&({r["source"] for r in stress}|{s["source_id"] for s in catalog}))
    phrasings = {(s["source_id"],u["fact_id"]):tuple(u[k] for k in ("text","light","strong"))
                 for s in catalog for u in s["units"]}
    artifacts = {r["artifact_id"]:Artifact(**r) for r in rows(CLOSE/"artifacts.jsonl")}
    observations = [Observation.from_dict(r) for r in rows(CLOSE/"observations.jsonl")
                    if r["method_version"]=="065bb82/bge/frozen-pilot"]
    assert len(observations)==len(artifacts)==180
    requests = defaultdict(list)
    for r in rows(CLOSE/"decisions.jsonl"):
        if r["method"]=="bge":
            requests[r["case_id"],r["variant"]].append(r)
    verified = {r["artifact_id"]:r for r in rows(CLOSE/"verified.jsonl") if r["method"]=="bge"}
    endpoints = {(r["case_id"],r["variant"]):r for r in rows(PILOT/"real/pilot/cases.jsonl")}
    assert {r["chain_id"] for r in dev}.isdisjoint(r["chain_id"] for r in endpoints.values())
    assert {r["chain_id"] for r in dev}.isdisjoint(r["chain_id"] for r in stress)
    keys = [(o.artifact_id,c.unit) for o in observations for c in o.unit_claims]
    test_scores,test_time = engine.score([pairs_for(artifacts[aid].text,phrasings[u]) for aid,u in keys])
    cache = dict(zip(keys,test_scores,strict=True))
    stress_scores,stress_time = engine.score([pairs_for(r["text"],[r["fact"]]) for r in stress])

    baseline = TextUnitChecker(phrasings)
    containment_seconds = 0.
    def timed_containment(artifact,unit):
        nonlocal containment_seconds
        tick = time.perf_counter()
        result = baseline(artifact,unit)
        containment_seconds += time.perf_counter()-tick
        return result

    def checker(method):
        def check(artifact,unit):
            if artifact is None or unit not in phrasings:
                return Presence.UNKNOWN
            if not artifact.text.strip():
                return Presence.ABSENT
            value = cache[artifact.artifact_id,unit][method]
            return Presence.PRESENT if accepts(value,thresholds[method]) else Presence.UNKNOWN
        return check

    universe = {s["source_id"]:sorted(u for u in phrasings if u[0]==s["source_id"]) for s in catalog}
    holder,requester,school = "replay-holder","replay-requester","replay-org"
    access = AccessRegistry([AssetOwnership(s,"teacher",school) for s in universe],
                            [Membership(requester,school,"student")],
                            [AccessGrant(requester,s,"study",1) for s in universe])
    target = TargetRegistry([ProtectedTarget(s,"teacher",school,(frozenset(u),)) for s,u in universe.items()])
    static = CapdPolicy(access,target,2,0,"static")
    dynamic = CapdPolicy(access,target,2,0,"dyn_knowledge")
    outputs,decisions = [], []
    for method in METHODS:
        verifier = RuleVerifier(b"",b"",timed_containment if method=="containment" else checker(method))
        for o in observations:
            key = (verified[o.artifact_id]["case_id"],verified[o.artifact_id]["variant"])
            confirmed = verifier.verify(o,artifacts[o.artifact_id])
            assert confirmed.verified_event is None and not confirmed.verified_issuance_ids
            if method=="containment":
                assert sorted(confirmed.confirmed_units)==sorted(map(tuple,verified[o.artifact_id]["confirmed"]))
            outputs.append(dict(artifact_id=o.artifact_id,case_id=key[0],variant=key[1],method=method,
                                confirmed=sorted(confirmed.confirmed_units),suspected=sorted(confirmed.suspected_units)))
            original = iter(requests[key])
            for sid,units in universe.items():
                for i,released in enumerate(units):
                    state = SecurityState({requester:frozenset({units[(i+1)%3]})},enforced_budget_f=0)
                    state.apply(confirmed)
                    req = DisclosureRequest(f"{o.artifact_id}:{sid}:{i}",requester,"study",school,(released,),0.)
                    before,after = static.decide(req,state),dynamic.decide(req,state)
                    frozen = next(original)
                    assert before.allowed==frozen["static"] and tuple(frozen["needed"])==units[(i+2)%3]
                    assert after.trusted_event_credits==0
                    if method=="containment":
                        assert after.allowed==frozen["dynamic"]
                    decisions.append(dict(frozen,method=method,dynamic=after.allowed,reason=after.reason))
            assert next(original,None) is None
    jsonl(args.out/"verified.jsonl",outputs)
    jsonl(args.out/"decisions.jsonl",decisions)

    # Test labels enter only after model configuration, verification and actual decisions.
    annotations = {(r["case_id"],r["variant"]):r for r in rows(PILOT/"real/pilot/annotations.jsonl")}
    by_candidate = {o.artifact_id:{c.unit for c in o.unit_claims} for o in observations}
    errors = []
    summary = {}
    scopes = {"all":set(endpoints),"model":{k for k,r in endpoints.items() if r["batch_id"] is not None},
              "plain_model":{k for k,r in endpoints.items() if k[1]=="plain" and r["batch_id"] is not None}}
    def expected(key):
        a = annotations[key]
        assert not a["unknown_fact_ids"]
        return {(f.rsplit(":f",1)[0],f) for f in a["retained_fact_ids"]}

    for scope, members in scopes.items():
        for method in (*METHODS,"candidate_ideal"):
            count, governance = Counter(),Counter()
            for r in outputs:
                key = r["case_id"],r["variant"]
                if key not in members or r["method"]!=(method if method!="candidate_ideal" else "containment"):
                    continue
                gold = expected(key)
                candidates = by_candidate[r["artifact_id"]]
                got = gold & candidates if method=="candidate_ideal" else set(map(tuple,r["confirmed"]))
                update(count,gold,got,candidates)
                if scope=="all" and method!="candidate_ideal":
                    for unit in sorted((got-gold)|((gold&candidates)-got)):
                        errors.append(dict(case_id=key[0],variant=key[1],artifact_id=r["artifact_id"],unit=unit,
                            method=method,error="false_confirm" if unit in got else "missed_candidate",
                            diagnostic=cache[r["artifact_id"],unit].get(method),endpoint=endpoints[key]["text"]))
            for d in decisions:
                key = d["case_id"],d["variant"]
                if key not in members or d["method"]!=(method if method!="candidate_ideal" else "containment"):
                    continue
                need = tuple(d["needed"])
                hazard = need in expected(key)
                aid = hashlib.sha256("|".join(key).encode()).hexdigest()[:24]
                allow = d["dynamic"] if method!="candidate_ideal" else not (hazard and need in by_candidate[aid])
                governance.update(requests=1,hazard=hazard,safe=not hazard,
                                  dangerous_allow=hazard and allow,over_refusal=not hazard and not allow)
            summary[f"{scope}/{method}"] = dict(units=summarize(count),governance=dict(governance,
                dangerous_allow_rate=governance["dangerous_allow"]/governance["hazard"],
                over_refusal_rate=governance["over_refusal"]/governance["safe"]))
    stress_rows = []
    stress_report = defaultdict(Counter)
    for r,s in zip(stress,stress_scores,strict=True):
        unit = (r["source"],r["id"])
        lexical = TextUnitChecker({unit:(r["fact"],)})
        for method in METHODS:
            ok = (lexical(Artifact(r["id"],holder,r["text"],0),unit) is Presence.PRESENT if method=="containment"
                  else accepts(s[method],thresholds[method]))
            fact = {unit} if r["present"] else set()
            update(stress_report[method,r["kind"]],fact,{unit} if ok else set(),{unit})
            stress_rows.append(dict(r,method=method,confirmed=ok,diagnostic=s.get(method)))
    jsonl(args.out/"stress.jsonl",stress_rows)
    jsonl(args.out/"errors.jsonl",errors)
    write(args.out/"summary.json",dict(comparison=summary,stress={f"{m}/{k}":summarize(c) for (m,k),c in stress_report.items()},
        timing=dict(load_seconds=load_seconds,development=dev_time,test=test_time,stress=stress_time,
                    containment_test_seconds=containment_seconds,candidate_unit_checks=len(keys))))
    print("Completed",len(observations),"endpoints,",len(keys),"candidate units,",len(decisions),"decisions",flush=True)


if __name__=="__main__":
    main()
