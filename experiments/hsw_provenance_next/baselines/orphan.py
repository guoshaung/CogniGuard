"""Compare public content retrieval and explicit provenance evidence on controlled cases."""
import argparse
from collections import Counter, defaultdict
import hashlib
import hmac
import json
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
PILOT = HERE.parents[1] / "hsw_provenance"
sys.path.insert(0, str(PILOT / "fingerprints"))
from run import (chunks, digest, file_sha, load_semantic, precompute,
                 select, tokens, variants)

MARKER = re.compile(r"^\[release=([a-z0-9:-]+)(?:;fact=([a-z0-9:-]+);mac=([a-f0-9]{32}))?\] ", re.I)
FIXTURE_KEY = b"openstax-synthetic-orphan-pilot-v1"
GARBAGE = "The next class takes place in a different room."


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf8")


def mac(release, fact, text):
    return hmac.new(FIXTURE_KEY, f"{release}\n{fact}\n{text}".encode(), hashlib.sha256).hexdigest()[:32]


def label(release, fact, text, method, bound_body=None):
    if method == "embedded_signature":
        return f"[release={release};fact={fact};mac={mac(release,fact,bound_body or text)}] {text}"
    return f"[release={release}] {text}"


def scenarios(sources, releases):
    grouped = defaultdict(list)
    for release in releases:
        grouped[release["source_id"]].append(release)
    first, second = sources[:2]
    a, b = [r["release_id"] for r in grouped[first["source_id"]]]
    c = grouped[second["source_id"]][0]["release_id"]
    fa, fc = first["units"][0], second["units"][0]
    sa, sc = first["source_id"], second["source_id"]
    ta, tc = fa["text"], fc["text"]

    def build(method):
        marked = label(a,fa["fact_id"],ta,method)
        orphan = label(a,fa["fact_id"],GARBAGE,method,ta)
        other = label(c,fc["fact_id"],tc,method)
        swapped = label(a,fa["fact_id"],tc,method,ta)
        rows = [
            ("all_deleted","main",orphan,[a],[],[],[]),
            ("part_deleted","main",marked+"\n"+orphan,[a],[a],[sa],[fa["fact_id"]]),
            ("copied_unrelated","main",orphan,[],[],[],[]),
            ("mixed_markers","main",marked+"\n"+other,[a,c],[a,c],[sa,sc],[fa["fact_id"],fc["fact_id"]]),
            ("swapped_binding","main",swapped,[a,c],[c],[sc],[fc["fact_id"]]),
            ("identical_two_issues","main",marked,[a],[a],[sa],[fa["fact_id"]]),
            ("independent_same_fact","exact_replay",marked,[],[],[sa],[fa["fact_id"]]),
            ("independent_same_fact","unmarked_independent",fa["strong"],[],[],[sa],[fa["fact_id"]]),
            ("identical_two_issues","unmarked_ambiguous",ta,[b],[b],[sa],[fa["fact_id"]]),
        ]
        return [dict(case_id=name, scenario=scenario, text=text, history_release_ids=history,
                     supported_release_ids=support, compatible_source_ids=compat,
                     retained_fact_ids=facts, credential=method)
                for name,scenario,text,history,support,compat,facts in rows]
    return build("plain_marker"),build("embedded_signature")


def strip_marker(line):
    marker = MARKER.match(line)
    return line[marker.end():] if marker else line


def fact_match(text, sources):
    query = set(tokens(text))
    ranking = []
    for source in sources:
        values = []
        for fact in source["units"]:
            reference = set(tokens(fact["text"]))
            score = len(query & reference) / max(1,len(query | reference))
            values.append(score)
        ranking.append((max(values),source["source_id"]))
    first,second = sorted(ranking,reverse=True)[:2]
    return first[1] if first[0]>=.30 and first[0]-second[0]>=.07 else None


def predict(case, method, sources, releases, facts):
    start = time.perf_counter()
    source_ids, release_ids, accepted_facts = set(), set(), set()
    line_evidence = []
    for line in case["text"].splitlines():
        marker = MARKER.match(line)
        body = strip_marker(line)
        compatible = fact_match(body,sources)
        if compatible:
            source_ids.add(compatible)
        if not marker:
            continue
        release_id,fact_id,tag = marker.groups()
        indexed = releases.get(release_id)
        accepted = indexed is not None
        if method == "plain_marker_content":
            accepted = accepted and compatible == indexed["source_id"]
        elif method == "embedded_signature":
            accepted = (accepted and tag is not None and facts.get(fact_id) == indexed["source_id"]
                        and hmac.compare_digest(tag,mac(release_id,fact_id,body)))
        line_evidence.append(dict(release_id=release_id,fact_id=fact_id,
                                  compatible_source_id=compatible,accepted=bool(accepted)))
        if accepted:
            release_ids.add(release_id)
            if fact_id:
                accepted_facts.add(fact_id)
    return dict(method=method,source_ids=sorted(source_ids),release_ids=sorted(release_ids),
                signed_fact_ids=sorted(accepted_facts),line_evidence=line_evidence,
                seconds=time.perf_counter()-start)


def scores(rows):
    counters = {target:Counter() for target in ("source","release")}
    for row in rows:
        historical = set(row["history_release_ids"])
        supported = set(row["supported_release_ids"])
        released = set(row["release_ids"])
        for target,gold,pred in (
            ("source",set(row["compatible_source_ids"]),set(row["source_ids"])),
            ("release",supported,released),
        ):
            counters[target].update(tp=len(gold & pred),fp=len(pred-gold),fn=len(gold-pred))
        counters["release"].update(orphan_labels=len(released & (historical-supported)),
                                   non_inherited_labels=len(released-historical),
                                   case_exact=int(released==supported))
    for count in counters.values():
        tp,fp,fn = (count[x] for x in ("tp","fp","fn"))
        count.update(precision=tp/max(1,tp+fp),recall=tp/max(1,tp+fn),f1=2*tp/max(1,2*tp+fp+fn))
    return {target:dict(count) for target,count in counters.items()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data",type=Path,default=PILOT/"propagation")
    p.add_argument("--prior-config",type=Path,default=PILOT/"fingerprints/configuration.json")
    p.add_argument("--bge",type=Path,required=True)
    p.add_argument("--rerank",type=Path,required=True)
    p.add_argument("--out",type=Path,default=HERE)
    args = p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    sources = read(args.data/"sources.json")
    releases = read(args.data/"releases.json")
    prior = read(args.prior_config)
    orig = prior["data_sha256"]
    for name in ("sources.json","releases.json"):
        assert orig[name] == file_sha(args.data/name), name
    for name,path in (("bge",args.bge),("rerank",args.rerank)):
        assert prior["model_sha256"][name] == file_sha(path/"model.safetensors"), name
    plain,signed = scenarios(sources,releases)
    clean = []
    for case in plain:
        row = dict(case,text="\n".join(strip_marker(line) for line in case["text"].splitlines()),
                   credential="none")
        clean.append(dict(row,key=f'{row["case_id"]}|{row["scenario"]}'))
    docs = list(dict.fromkeys((s["source_id"],text) for s in sources for text in chunks(s["text"])))
    active = list(dict.fromkeys([*docs,*[(s["source_id"],text) for s in sources for text in variants(s["text"])]]))
    corpus = [dict(case,case_id=case["key"]) for case in clean]
    models = load_semantic(args.bge,args.rerank,prior["cpu_threads"])
    raw,elapsed,_,preprocess = precompute(corpus,sources,docs,active,releases,models)
    predictions = []
    for method,rows in (("plain_marker",plain),("plain_marker_content",plain),("embedded_signature",signed)):
        table = {r["release_id"]:r for r in releases}
        facts = {f["fact_id"]:s["source_id"] for s in sources for f in s["units"]}
        predictions.extend(dict(case,**predict(case,method,sources,table,facts)) for case in rows)
    for method,ranks in raw.items():
        config = prior[method]
        for case in clean:
            key = case["key"]
            selected = select(ranks[key],config["threshold"],config["margin"])
            candidates = sorted(r["release_id"] for r in releases if r["source_id"] in selected)
            predictions.append(dict(case,method=method,source_ids=selected,
                                    release_ids=[],candidate_release_ids=candidates,
                                    seconds=elapsed[method][key], ranked_sources=ranks[key]))
    summaries = {}
    for method in sorted({row["method"] for row in predictions}):
        rows = [r for r in predictions if r["method"]==method]
        primary = [r for r in rows if r["scenario"] in ("main","exact_replay")]
        assert len(primary)==7
        summaries[method] = dict(primary=scores(primary),n=len(primary),controls=[
            dict(case_id=r["case_id"],scenario=r["scenario"],source_ids=r["source_ids"],release_ids=r["release_ids"])
            for r in rows if r not in primary])
    write(args.out/"orphan_cases.json",dict(plain=plain,signed=signed,content=clean))
    write(args.out/"orphan_predictions.json",predictions)
    write(args.out/"orphan_summary.json",dict(
        reused_prior_thresholds_sha256=file_sha(args.prior_config), semantic_preprocessing_seconds=preprocess,
        signed_method="Visible synthetic 128-bit HMAC of issue, fact id and exact fact text; not a robust concealed watermark",
        public_fixture_key=True, gpu_hours=0, paid_api_calls=0, methods=summaries))
    for method,result in summaries.items():
        print(method, result["primary"])


if __name__ == "__main__":
    main()
