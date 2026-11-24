"""Supplementary diagnostics after R1, with resampling at the source-family level."""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
import sys

from pilot import catalog, config, dump


def info(counts):
    n = sum(counts.values())
    by_sent, by_result = Counter(), Counter()
    for (sent, result), count in counts.items():
        by_sent[sent] += count
        by_result[result] += count
    return sum(count/n * math.log2(count*n/(by_sent[sent]*by_result[result]))
               for (sent, result), count in counts.items())


def percentile(values, low, high):
    ordered = sorted(values)
    return [ordered[low], ordered[high]]


def main(out):
    records = [json.loads(line) for line in (out / "channel_transitions.jsonl").read_bytes().splitlines()]
    grouped = defaultdict(list)
    for row in records:
        family = row["source"].rsplit("-", 1)[0]
        grouped[(row["op"], row["method"])].append((family, row))
    result = {}
    rng = random.Random(config()["seed"])
    for (op, method), rows in grouped.items():
        clusters = defaultdict(list)
        counts = Counter()
        for family, row in rows:
            clusters[family].append(row)
            reported = str(row["observed"])
            counts[row["sent"], reported] += 1
        by_cluster = list(clusters.values())
        n = len(rows)
        rates = {}
        for state in ("correct", "substitution", "erased", "conflict"):
            draws = []
            for _ in range(5000):
                sample = [row for cluster in rng.choices(by_cluster, k=len(by_cluster)) for row in cluster]
                draws.append(sum(row["state"] == state for row in sample) / len(sample))
            k = sum(row["state"] == state for _, row in rows)
            rates[state] = {"numerator": k, "denominator": n, "rate": k/n, "cluster_bootstrap_95": percentile(draws, 125, 4874)}
        result[f"{op}/{method}"] = {"states": rates, "pooled_mi_bits": info(counts),
                                    "counts": {f"{k[0]}->{k[1]}": v for k, v in counts.items()}}
    dump(out / "channel_diagnostics.json", result)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
