"""Evaluate frozen outputs without running the model or feeding labels to the decoder."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import re

from pilot import catalog, codebook, config, decode, dump, ids, render, sight, words

CHECKS = {
    "sequence": (r"\b7\b|\bseven\b", r"\b5\b|\bfive\b", r"\b12\b|\btwelve\b", r"sequence|term"),
    "resistance": (r"3\s*(ohms?|Ω)", r"6\s*(volts?|v\b)", r"2\s*(amperes?|amps?|a\b)"),
    "area": (r"\b9\b|\bnine\b", r"\b4\b|\bfour\b", r"36\s*(square m|m²|m\^2)", r"rectangle"),
    "density": (r"18\s*(grams?|g\b)", r"6\s*(cubic c|cm³|cm\^3)", r"3\s*(grams?|g\b).{0,20}(cubic c|cm³|cm\^3)"),
    "probability": (r"fair", r"independen", r"one quarter|one fourth|1\s*/\s*4|25%|0\.25"),
    "speed": (r"120\s*(meters?|metres?|m\b)", r"20\s*(seconds?|s\b)", r"6\s*(meters?|metres?|m\b).{0,5}(second|/\s*s\b)"),
}


def assess(text, family):
    return all(re.search(pattern, text, re.I) for pattern in CHECKS[family])


def assess_rows(records, families, book):
    by_family = {f["family"]: f for f in families}
    for row in records:
        text = row["output"]
        method = "prefix" if row["method"] == "prefix" else "rkw"
        decoded = decode(text, families, book, method)
        expected = row["source"]
        carriers = []
        for source in expected:
            name = source.rsplit("-", 1)[0]
            bits = book[source]
            seen = decoded["symbols"][name]
            loose = sight(text, by_family[name], method, loose=True)
            carriers.append({
                "source": source, "observed": seen, "loose": loose,
                "states": ["erased" if not opts else "conflict" if len(opts) > 1 else
                           "correct" if bit in opts else "substitution" for opts, bit in zip(seen, bits)],
                "loose_compatible": all(bit in opts for opts, bit in zip(loose, bits)),
                "knowledge_proxy": assess(text, name),
            })
        yield {"case": row["case"], "op": row["op"], "method": row["method"],
               "expected": expected, "predicted": decoded["sources"], "status": decoded["status"],
               "exact": sorted(expected) == decoded["sources"], "carriers": carriers,
               "copied": bool(text) and words(text) == words(row["input"]), "error": row.get("error")}


def diagnostics(families, book, seed):
    rng = random.Random(seed)
    for i, family in enumerate(families):
        source = ids(family)[0]
        marked = render(family, book[source], "rkw")
        plain = render(family)
        yield "forward", family["family"], [source], marked
        for length in (5, 20, 50, 100):
            tokens = marked.split()
            start = rng.randint(0, max(0, len(tokens) - length))
            yield f"excerpt_{length}", family["family"], [source], " ".join(tokens[start:start + length])
        other = families[(i + 1) % len(families)]
        yield "copied_phrases_unrelated", family["family"], [], (
            render(other) + " " + " ".join(site["symbols"][bit] for site, bit in zip(family["sites"], book[source]))
        )
        yield "copied_whole", family["family"], [], marked
        yield "independent_same_knowledge_fixture", family["family"], [], plain
        yield "removed_knowledge_sites", family["family"], [], " ".join(marked.split(". ")[:-2])
        yield "wrong_source_code", family["family"], [source], render(family, book[ids(family)[1]], "rkw")


def summarize(rows, seed):
    result = {}
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["op"], row["method"]].append(row)
    for (op, method), records in grouped.items():
        carriers = [c for row in records for c in row["carriers"]]
        counts = Counter(state for c in carriers for state in c["states"])
        transition = Counter()
        for c in carriers:
            for index, observed in enumerate(c["observed"]):
                incoming = c["source"], index
                transition[incoming + (str(observed),)] += 1
        confirmed = sum(c["knowledge_proxy"] for c in carriers)
        correct = sum(len(set(r["expected"]) & set(r["predicted"])) for r in records)
        predicted = sum(len(r["predicted"]) for r in records)
        n = len(records)
        values = dict(n=n, exact=sum(r["exact"] for r in records), predicted=predicted, correct=correct,
                      errors=sum(r["error"] is not None for r in records), copies=sum(r["copied"] for r in records),
                      any_prediction=sum(bool(r["predicted"]) for r in records),
                      knowledge_proxy=confirmed, source_instances=len(carriers),
                      loose=sum(c["loose_compatible"] for c in carriers), states=counts,
                      eligible_knowledge_symbols=5 * confirmed,
                      correct_given_knowledge=sum(c["states"].count("correct") for c in carriers if c["knowledge_proxy"]),
                      precision=correct/predicted if predicted else None, recall=correct/len(carriers),
                      f1=2*correct/(predicted+len(carriers)))
        result[f"{op}/{method}"] = values
    rng = random.Random(seed)
    for op in ("summary", "strong"):
        pairs = defaultdict(dict)
        for row in grouped[op, "rkw"] + grouped[op, "plain"]:
            pairs[row["expected"][0]][row["method"]] = row["exact"]
        if len(pairs) != 12 or any(set(values) != {"rkw", "plain"} for values in pairs.values()):
            continue
        clusters = defaultdict(list)
        for source, values in pairs.items():
            clusters[source.rsplit("-", 1)[0]].append(int(values["rkw"]) - int(values["plain"]))
        means = [sum(values) / len(values) for values in clusters.values()]
        boot = sorted(sum(rng.choices(means, k=len(means))) / len(means) for _ in range(5000))
        result[f"{op}/paired_development_ci"] = [boot[125], boot[4874]]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    options = parser.parse_args()
    out = options.out
    settings = config()
    families = catalog()
    book = codebook(families, settings["seed"])
    records = [json.loads(line) for line in (out / "propagation_outputs.jsonl").read_bytes().splitlines()]
    rows = list(assess_rows(records, families, book))
    metrics = summarize(rows, settings["seed"])
    complete = len(rows) == settings["max_calls"] and all(not r["error"] for r in rows)
    prim = [metrics.get(f"{op}/rkw", {}) for op in ("summary", "strong")]
    negative_rates = [metrics.get(f"{op}/plain", {}) for op in ("summary", "strong")]
    meets_all = complete and all(
        p["exact"]/p["n"] >= settings["min_primary_exact"]
        and p["exact"]/p["n"] > max(1/len(book), neg["exact"]/neg["n"])
        and p["knowledge_proxy"]/p["source_instances"] >= settings["min_primary_knowledge"]
        and neg["any_prediction"]/neg["n"] <= settings["max_negative_rate"]
        for p, neg in zip(prim, negative_rates)
    )
    stop = complete and all(p["exact"]/p["n"] < settings["min_primary_exact"]
                            and p["loose"]/p["source_instances"] <= settings["max_primary_exact_oracle_for_stop"]
                            for p in prim)
    simulations = [
        {"operation": op, "family": family, "expected": expected, "text": text,
         "predicted": decode(text, families, book, "rkw")["sources"]}
        for op, family, expected, text in diagnostics(families, book, settings["seed"])
    ]
    dump(out / "predictions.json", rows)
    dump(out / "diagnostics.json", simulations)
    dump(out / "metrics.json", {"calls": len(records), "complete": complete, "groups": metrics,
                               "decision": "R1_PASS_PENDING_FIDELITY" if meets_all else "STOP" if stop else "INCONCLUSIVE",
                               "aggregate_model_eval_seconds": sum(row.get("eval_ns", 0) for row in records)/1e9,
                               "aggregate_request_seconds": sum(row["seconds"] for row in records)})
    with (out / "channel_transitions.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            if row["method"] == "plain":
                continue
            for entry in row["carriers"]:
                for site, observed in enumerate(entry["observed"]):
                    transition = {"case": row["case"], "op": row["op"], "method": row["method"],
                                  "source": entry["source"], "position": site, "sent": book[entry["source"]][site],
                                  "observed": observed, "state": entry["states"][site],
                                  "knowledge_proxy": entry["knowledge_proxy"]}
                    stream.write(json.dumps(transition) + "\n")
    print("Gate", "R1_PASS_PENDING_FIDELITY" if meets_all else "STOP" if stop else "INCONCLUSIVE")


if __name__ == "__main__":
    main()

