"""Decode actual relay outputs using thresholds frozen on controlled development chains."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from candidate import HERE, PILOT, Codec, dump, load_jsonl, metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hops", type=Path)
    parser.add_argument("annotations", type=Path, help="JSONL adjudication keyed by case_id and variant")
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    data = PILOT / "propagation"
    sources = json.loads((data/"sources.json").read_bytes())
    releases = json.loads((data/"releases.json").read_bytes())
    dev = [r for r in load_jsonl(data/"cases.jsonl") if r["partition"]=="calibration"]
    codec = Codec(sources,releases,dev)
    known = json.loads((HERE/"candidates/summary.json").read_bytes())
    annotations = {(r["case_id"],r["variant"]):r for r in load_jsonl(args.annotations)}
    predictions = []
    groups = defaultdict(list)
    for record in load_jsonl(args.hops):
        if record["depth"] not in (1,3,5):
            continue
        variant = record["variant"]
        for method in {"plain":("plain",),"M1":("M1","M1+source"),"M2":("M2",),"M3":("M3",)}[variant]:
            import time
            start = time.perf_counter()
            observed = codec.inspect(record["text"])
            decoded, facts = codec.decode("M2" if method=="plain" else method,observed,
                                          known.get(method,known["M2"])["thresholds"]["selected"],
                                          {} if method=="plain" else None)
            annotation = annotations.get((record["case_id"],variant))
            row = dict(case_id=record["case_id"],variant=variant,method=method,
                       transform=record["transform"],depth=record["depth"],
                       pred_release=sorted(decoded),pred_fact=sorted(facts),
                       pred_source=sorted({codec.releases[r]["source_id"] for r in decoded}),
                       seconds=time.perf_counter()-start)
            if annotation and not annotation.get("unknown_fact_ids"):
                gold = annotation["supported_release_ids"]
                row.update(gold_release=gold, gold_fact=annotation["retained_fact_ids"],
                           gold_source=annotation["compatible_source_ids"],eligible_release=gold if variant!="plain" else [],
                           input_release_ids=record["input_release_ids"],instruction_pass=annotation.get("instruction_pass"))
                groups[method].append(row)
            predictions.append(row)
    summary = {m:dict(total=metrics(rows), by_depth={str(d):metrics(selected) for d in (1,3,5)
                        if (selected := [r for r in rows if r["depth"]==d])},
                        by_transform={t:metrics([r for r in rows if r["transform"]==t])
                                      for t in sorted({r["transform"] for r in rows})},
                        unsupported_release_labels=sum(len(set(r["pred_release"])-set(r["gold_release"])) for r in rows))
               for m,rows in groups.items()}
    dump(args.out,dict(predictions=predictions,summary=summary,
                       coverage={m:dict(scored=len(groups[m]),planned=sum(r["method"]==m for r in predictions))
                                 for m in sorted({r["method"] for r in predictions})}))


if __name__=="__main__":
    main()
