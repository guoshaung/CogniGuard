"""Score provenance on the held-out controlled endpoints."""
import json
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]


def evaluate(pairs):
    pairs = list(pairs)
    measures = {}
    for kind in ("source", "release", "issuer"):
        tp = fp = fn = exact = lost = nonempty = nonempty_exact = 0
        for case, pred in pairs:
            actual = set(case["retained_" + kind + "_ids"])
            guessed = set(pred[kind + "_ids"])
            tp += len(actual & guessed)
            fp += len(guessed - actual)
            fn += len(actual - guessed)
            exact += actual == guessed
            nonempty += bool(actual)
            nonempty_exact += bool(actual) and actual == guessed
            lost += len(guessed & (set(case["input_" + kind + "_ids"]) - actual))
        measures[kind] = dict(precision=tp/max(1,tp+fp), recall=tp/max(1,tp+fn),
                              f1=2*tp/max(1,2*tp+fp+fn), exact_set=exact/len(pairs),
                              erroneous_attribution=fp/max(1,tp+fp), lost_input_attributions=lost,
                              tp=tp,fp=fp,fn=fn)
        measures[kind]["exact_nonempty"] = nonempty_exact/nonempty if nonempty else None
    multi = [(case,pred) for case,pred in pairs if len(case["retained_source_ids"]) >= 2]
    measures["multi_source_exact"] = (sum(set(c["retained_source_ids"])==set(p["source_ids"])
                                          for c,p in multi)/len(multi)) if multi else None
    measures["multi_source_n"] = len(multi)
    measures["n"] = len(pairs)
    measures["seconds_per_sample_median"] = statistics.median(p["seconds"] for _,p in pairs)
    return measures


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("predictions",nargs="*",type=Path)
    parser.add_argument("--data",type=Path,default=HERE/"propagation")
    parser.add_argument("--out",type=Path,default=HERE/"evaluation.json")
    args = parser.parse_args()
    cases = {row["case_id"]:row for row in read_jsonl(args.data/"cases.jsonl") if row["partition"]!="calibration"}
    ledger = json.loads((args.data/"releases.json").read_bytes())
    releases = {r["release_id"]:r["issuer_id"] for r in ledger}
    for case in cases.values():
        case["retained_issuer_ids"] = sorted({releases[r] for r in case["retained_release_ids"]})
    groups = defaultdict(dict)
    for path in args.predictions or [HERE/"watermark/predictions.jsonl"]:
        for row in read_jsonl(Path(path)):
            if row["case_id"] in cases:
                assert row["case_id"] not in groups[row["method"]]
                groups[row["method"]][row["case_id"]] = row
    tagged = groups.get("HSW-prefix + lexical retrieval")
    if tagged and groups.get("bge"):
        by_issue = {r["release_id"]:r["source_id"] for r in ledger}
        for case_id, bge in groups["bge"].items():
            pilot = tagged[case_id]
            accepted = [r for r in pilot["release_ids"] if by_issue[r] in bge["source_ids"]]
            groups["BGE + HSW-prefix"][case_id] = dict(
                bge, release_ids=accepted, issuer_ids=sorted({releases[r] for r in accepted}),
                seconds=bge["seconds"]+pilot["seconds"])
    summary = {}
    for method, predictions in groups.items():
        if set(predictions) != set(cases):
            raise ValueError((method, len(predictions), len(cases)))
        pairs = [(cases[k],p) for k,p in predictions.items()]
        by_transform, by_depth = defaultdict(list), defaultdict(list)
        for item in pairs:
            by_transform[item[0]["transform"]].append(item)
            by_depth[item[0]["depth"]].append(item)
        summary[method] = dict(total=evaluate(pairs),
                               transform={k:evaluate(v) for k,v in by_transform.items()},
                               depth={k:evaluate(v) for k,v in by_depth.items()})
    args.out.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    for method, result in summary.items():
        print(method, json.dumps(result["total"]))


if __name__=="__main__":
    main()
