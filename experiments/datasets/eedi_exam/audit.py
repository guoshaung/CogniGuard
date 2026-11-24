"""Summarize the Eedi competition CSVs without exporting question-level data."""
import csv
import random
import re
from collections import Counter, defaultdict
from fractions import Fraction
from itertools import combinations

from experiments.datasets.audit_io import digest, raw_dir, save

NUMBERS = re.compile(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)")
MIS = [f"Misconception{option}Id" for option in "ABCD"]


def normalized(text):
    return re.sub(r"\s+", "", text.replace(r"\(", "").replace(r"\)", ""))


def misconception_id(text):
    # Kaggle nullable numeric columns can serialize integer IDs with a .0 suffix.
    return re.sub(r"(?<=\d)\.0+$", "", text.strip())


def numeric(text):
    s = re.sub(r"^\\(?:d?frac)\{([+-]?\d+)\}\{(\d+)\}$", r"\1/\2", text)
    try:
        Fraction(s)
    except (ValueError, ZeroDivisionError):
        return False
    return True


def histogram(counter):
    return dict(Counter(counter.values()))


def trial(target, features, by_unit, by_subject, k, rng):
    units = features[target]
    # A distractor must share a clue while failing at least one of the target's clues.
    pools = {u: by_unit[u] - {target} for u in units}
    identical_on_target = set.intersection(*pools.values())
    group = {target}
    order = sorted(units)
    rng.shuffle(order)
    for u in sorted(order, key=lambda u: len(pools[u])):
        options = pools[u] - identical_on_target
        if group & options:
            continue
        if not options or len(group) == k:
            return "neighbor_coverage"
        group.add(rng.choice(sorted(options)))
    subject = next(v for f, v in units if f == "subject")
    fill = sorted(by_subject[subject] - group)
    if len(fill) < k - len(group):
        return "insufficient_same_subject_fill"
    group.update(rng.sample(fill, k - len(group)))
    retained = sorted(((len(by_unit[u] & group), u) for u in units))[:12]
    supports = [by_unit[u] & group for _, u in retained]
    if any(len(s) < 2 for s in supports):
        return "single_clue"
    # If any 2-4-way intersection is unique and all singletons are safe,
    # at least one minimal witness in that size range exists.
    for n in range(2, 5):
        if any(len(set.intersection(*c)) == 1 for c in combinations(supports, n)):
            return "accepted"
    return "no_2_to_4_witness"


def feasibility(features, seed=2026):
    index, subjects = defaultdict(set), defaultdict(set)
    for q, units in features.items():
        for f, v in units:
            index[f, v].add(q)
            if f == "subject":
                subjects[v].add(q)
    out = {}
    for k in (8, 16, 32):
        rng = random.Random(f"{seed}/{k}")
        targets = rng.sample(sorted(features), min(len(features), 30))
        attempts, first = Counter(), Counter()
        accepted = 0
        for q in targets:
            for i in range(51):
                status = trial(q, features, index, subjects, k, rng)
                attempts[status] += 1
                if i == 0:
                    first[status] += 1
                if status == "accepted":
                    accepted += 1
                    break
        out[k] = {"targets": len(targets), "accepted": accepted, "first_draw": dict(first),
                  "failed_slots": len(targets)-accepted, "all_draws": dict(attempts),
                  "acceptance_rate": accepted / len(targets) if targets else None}
    return out


def audit(folder):
    files = sorted(folder.glob("*.csv"))
    hashes = {p.name: digest(p) for p in files}
    tables, features = {}, {}
    counts, token_counts, subjects, constructs = (Counter() for _ in range(4))
    annotated = num_answers = eligible_numeric = 0
    ids, used, mappings = set(), set(), set()
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            missing = dict.fromkeys(reader.fieldnames, 0)
            n = 0
            for row in reader:
                n += 1
                for col in missing:
                    missing[col] += int(not (row[col] or "").strip())
                if path.name == "misconception_mapping.csv":
                    mappings.add(misconception_id(row["MisconceptionId"]))
                if path.name != "train.csv":
                    continue
                q = row["QuestionId"]
                if q in ids:
                    raise ValueError("duplicate train QuestionId")
                ids.add(q)
                labels = {misconception_id(row[c]) for c in MIS if row[c].strip()}
                used.update(labels)
                counts[len(labels)] += 1
                ans = normalized(row[f"Answer{row['CorrectAnswer']}Text"])
                numbers = NUMBERS.findall(row["QuestionText"])
                num_answers += numeric(ans)
                token_counts[len(numbers)] += 1
                subject, construct = row["SubjectId"], row["ConstructId"]
                subjects[subject] += 1
                constructs[construct] += 1
                if labels:
                    annotated += 1
                    eligible_numeric += numeric(ans)
                    features[q] = {("subject", subject), ("construct", construct), ("answer", ans)}
                    features[q].update(("misconception", x) for x in labels)
                    features[q].update(("number", x) for x in numbers)
            tables[path.name] = {"rows": n, "missing_fraction": {c: v/n if n else None for c,v in missing.items()}}
    if not {"train.csv", "misconception_mapping.csv"} <= hashes.keys():
        raise FileNotFoundError("train.csv and misconception_mapping.csv required")
    return {"csv": tables, "annotated_train_questions": annotated,
            "unmapped_used_ids": len(used-mappings), "unique_mapping_ids": len(mappings),
            "distinct_misconceptions_per_question": dict(counts), "number_tokens_per_stem": dict(token_counts),
            "numeric_correct_answers": num_answers, "numeric_fraction": num_answers/len(ids),
            "numeric_fraction_annotated": eligible_numeric/annotated if annotated else None,
            "question_counts_by_subject_id": dict(subjects), "question_counts_by_construct_id": dict(constructs),
            "subject_group_size_histogram": histogram(subjects), "construct_group_size_histogram": histogram(constructs),
            "seed": 2026, "feasibility": feasibility(features)}, hashes


if __name__ == "__main__":
    save("eedi_exam", *audit(raw_dir() / "eedi"))
