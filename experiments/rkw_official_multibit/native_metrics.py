"""Evaluate fixed-prefix and document detection from the staged native Qwen run."""
import argparse
from itertools import product
import json
from pathlib import Path
from statistics import mean


def signed(scores, code):
    return mean(score * (2 * bit - 1) for score, bit in zip(scores, code)) if scores else None


def accepted(scores, code, threshold):
    return (len(scores) >= 4 and [int(value > 0) for value in scores[:4]] == code[:4]
            and signed(scores, code) > threshold)


def summarize(rows):
    calibration = [signed(row["scores"], row["key"]) for row in rows
                   if row["split"] == "calibration" and not row["marked"] and row["fraction"] == 0]
    assert len(calibration) == 8 and all(value is not None for value in calibration)
    threshold = max(calibration)
    metrics = {}
    for fraction in (0.0, .05, .1, .2):
        test = [row for row in rows if row["split"] == "test" and row["fraction"] == fraction]
        positives = [row for row in test if row["marked"]]
        negatives = [row for row in test if not row["marked"]]
        assert len(positives) == len(negatives) == 16
        pos_scores = [value for row in positives if (value := signed(row["scores"], row["key"])) is not None]
        neg_scores = [value for row in negatives if (value := signed(row["scores"], row["key"])) is not None]
        auc = mean(float(a > b) + .5 * (a == b) for a in pos_scores for b in neg_scores) if pos_scores and neg_scores else None
        bit_counts = [sum((value > 0) == expect for value, expect in zip(row["scores"], row["key"]))
                      for row in positives]
        candidates = [(row, [*key, *row["key"][4:]]) for row in positives
                      for key in product((0, 1), repeat=4) if list(key) != row["key"][:4]]
        metrics[str(fraction)] = {
            "auc": auc,
            "auc_positives": len(pos_scores),
            "auc_negatives": len(neg_scores),
            "bit_accuracy": [sum(bit_counts), sum(len(row["scores"]) for row in positives)],
            "four_bit_exact": [sum(len(row["scores"]) >= 4 and
                                   [int(value > 0) for value in row["scores"][:4]] == row["key"][:4]
                                   for row in positives), len(positives)],
            "complete_and_accepted": [sum(accepted(row["scores"], row["key"], threshold)
                                          for row in positives), len(positives)],
            "false_accept_unmarked": [sum(accepted(row["scores"], row["key"], threshold)
                                          for row in negatives), len(negatives)],
            "false_accept_wrong_code": [sum(accepted(row["scores"], other, threshold)
                                            for row, other in candidates), len(candidates)],
        }
    return {"calibration_threshold": threshold, "perturbation_rates": metrics}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    path = args.directory
    with (path / "native_metrics.json").open("x", encoding="utf-8") as output:
        rows = [json.loads(line) for line in (path / "native_scores.jsonl").read_bytes().splitlines()]
        json.dump(summarize(rows), output, indent=2)
        output.write("\n")
