"""Generate the Eedi "which question will be set" secrets (task book v2 section 4.2, revision 2.1).

The questions are real Eedi questions; which one is "set" is sampled by us.
Revision 2.1 (approved after the field audit):
  1. A unit whose value occurs in only one question of the whole bank is a
     direct identifier. It is left out of the universe and counted per secret.
  2. Candidates are filled in tiers: same subject, then questions sharing at
     least one retained unit with the target, then the whole bank.
Standard library only. Inputs: $COGNIGUARD_RAW_DIR/eedi; output:
$COGNIGUARD_DATA_DIR/eedi_exam (both outside the checkout).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import math
import os
import random
import re
import secrets
import tempfile
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path

from experiments.datasets.audit_io import digest, raw_dir
from experiments.datasets.eedi_exam.audit import MIS, NUMBERS, misconception_id, normalized
from experiments.datasets.synthetic.generate import subsets

REPO = Path(__file__).resolve().parents[3]
FILES = ("targets", "units", "leakage", "witness_sets", "texts", "secrets_private")
MAX_UNITS = 12
TEMPLATES = {
    "subject": ("The question comes from the topic {v}.", "It belongs to {v}.",
                "Expect something on {v}."),
    "construct": ("It tests the skill: {v}.", "The skill assessed is {v}.",
                  "Practise this skill: {v}."),
    "misconception": ("A common wrong idea here is: {v}.", "Watch out for this misconception: {v}.",
                      "The trap is: {v}."),
    "answer": ("The correct answer is {v}.", "The answer works out to {v}.",
               "You should end up with {v}."),
    "number": ("The question mentions the number {v}.", "The number {v} appears in the question.",
               "Look for {v} in the question."),
}


def load_bank(folder: Path):
    """Return {question_id: set of (feature, value)} and display names. Annotated questions only."""
    names = {"misconception": {}, "subject": {}, "construct": {}}
    with (folder / "misconception_mapping.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            names["misconception"][misconception_id(row["MisconceptionId"])] = row["MisconceptionName"]
    features = {}
    with (folder / "train.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            labels = {misconception_id(row[c]) for c in MIS if row[c].strip()}
            if not labels:
                continue
            q = f"eedi:{row['QuestionId']}"
            names["subject"][row["SubjectId"]] = row["SubjectName"]
            names["construct"][row["ConstructId"]] = row["ConstructName"]
            units = {("subject", row["SubjectId"]), ("construct", row["ConstructId"]),
                     ("answer", normalized(row[f"Answer{row['CorrectAnswer']}Text"]))}
            units.update(("misconception", x) for x in labels)
            units.update(("number", x) for x in NUMBERS.findall(row["QuestionText"]))
            features[q] = units
    return features, names


class Bank:
    def __init__(self, features):
        self.features = features
        self.ids = sorted(features)
        self.index = defaultdict(set)
        for q, units in features.items():
            for u in units:
                self.index[u].add(q)

    def shared(self, target):
        return sorted(u for u in self.features[target] if len(self.index[u]) > 1)


def build_group(bank: Bank, target, units, k, rng):
    """Neighbour cover, then tiered fill. Returns (group, tier counts) or a failure reason."""
    pools = {u: bank.index[u] - {target} for u in units}
    same = set.intersection(*pools.values())
    group = {target}
    order = list(units)
    rng.shuffle(order)
    for u in sorted(order, key=lambda u: len(pools[u])):
        options = pools[u] - same
        if group & options:
            continue
        if not options or len(group) == k:
            return "neighbor_coverage"
        group.add(rng.choice(sorted(options)))
    subject = next(v for f, v in bank.features[target] if f == "subject")
    tier_subject = bank.index[("subject", subject)]
    near = set().union(*(bank.index[u] for u in units)) - tier_subject
    tiers = (tier_subject, near, set(bank.ids) - near - tier_subject)
    used = [0, 0, 0]
    for i, tier in enumerate(tiers):
        need = k - len(group)
        if need <= 0:
            break
        pool = sorted(tier - group)
        take = rng.sample(pool, min(need, len(pool)))
        group.update(take)
        used[i] = len(take)
    if len(group) < k:
        return "insufficient_fill"
    return group, used


def draw(bank: Bank, names, seed, k, slot, attempt, target):
    rng = random.Random(f"{seed}/{k}/{slot}/{attempt}")
    target_id = f"eedi-K{k}-{slot:04d}"
    units_all = bank.shared(target)
    dropped = len(bank.features[target]) - len(units_all)
    if len(units_all) < 2:
        return "too_few_units"
    built = build_group(bank, target, units_all, k, rng)
    if isinstance(built, str):
        return built
    group, tiers = built
    domain = sorted(group)
    ranked = sorted(units_all, key=lambda u: (len(bank.index[u] & group), u))
    truncated = max(0, len(ranked) - MAX_UNITS)
    retained = sorted(ranked[:MAX_UNITS])
    units = []
    for i, (feature, value) in enumerate(retained):
        units.append(dict(target_id=target_id, unit_id=f"{target_id}.{i}", unit_type="attribute",
                          predicate=dict(feature=feature, value=value),
                          satisfied_by=sorted(bank.index[(feature, value)] & group),
                          is_public=False))
    counts, leakage, closure, witnesses = subsets(domain, units)
    bad_a = any(len(u["satisfied_by"]) < 2 for u in units)
    bad_b = not any(2 <= m.bit_count() <= 4 for m in witnesses)
    if bad_a or bad_b:
        return "a+b" if bad_a and bad_b else ("a" if bad_a else "b")
    batch = records(target_id, domain, target, units, counts, leakage, closure, witnesses,
                    bank, names, rng)
    return batch, dict(dropped_unique=dropped, truncated=truncated, fill_tiers=tiers)


def phrase(names, feature, value, rng):
    shown = names[feature].get(value, value) if feature in names else value
    t = rng.randrange(3)
    return f"{feature}_{t}", TEMPLATES[feature][t].format(v=shown)


def records(target_id, domain, value, units, counts, leakage, closure, witnesses, bank, names, rng):
    k = len(domain)
    tau = math.log2(k / 2)
    salt = secrets.token_hex(16)
    commitment = hmac.new(salt.encode(), value.encode(), hashlib.sha256).hexdigest()
    target = dict(target_id=target_id, dataset="eedi_exam", kind="teaching_asset", domain=domain,
                  K=k, prior="uniform", gain={"type": "identity"}, tau_bits=tau,
                  value_commitment=commitment, label_status="computed")
    ids = [u["unit_id"] for u in units]

    def members(mask):
        return [unit_id for i, unit_id in enumerate(ids) if mask & (1 << i)]

    sets = [members(m) for m in witnesses]
    keep = set(witnesses)
    rows = [dict(target_id=target_id, units=members(m), consistent=n, L_bits=leakage[m],
                 L_star_bits=closure[m])
            for m, n in enumerate(counts) if m.bit_count() <= 4 or m in keep]
    texts = []

    def add(role, gold, parts, **extra):
        texts.append(dict(text_id=f"{target_id}-t{len(texts)}", target_id=target_id,
                          gold_units=gold, role=role, template_id="+".join(t for t, _ in parts),
                          text=" ".join(s for _, s in parts), **extra))

    by_id = {u["unit_id"]: u["predicate"] for u in units}
    for group in [[uid] for uid in ids] + sets:
        parts = [phrase(names, by_id[u]["feature"], by_id[u]["value"], rng) for u in group]
        add("unit" if len(group) == 1 else "combo", group, parts)
    truth = bank.features[value]
    for other in rng.sample([q for q in domain if q != value], 3):
        # A decoy states something true of another candidate and false of the target.
        options = sorted(u for u in bank.features[other] if u not in truth)
        if not options:
            continue
        feature, val = rng.choice(options)
        add("decoy", [], [phrase(names, feature, val, rng)], decoy_of=other)
    return dict(targets=[target], units=units, leakage=rows, texts=texts,
                witness_sets=[dict(target_id=target_id, tau_bits=tau, universe=ids, sets=sets)],
                secrets_private=[dict(target_id=target_id, value=value, salt=salt)])


def generate(root, raw=None, ks=(8, 16, 32), count=300, seed=2026, retries=50):
    raw = Path(raw or raw_dir() / "eedi")
    root = Path(root).resolve()
    if any((p / ".git").exists() for p in (root, *root.parents)):
        raise ValueError("choose an output directory outside the repository")
    dest = root / "eedi_exam"
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("eedi_exam output exists; choose a fresh COGNIGUARD_DATA_DIR")
    features, names = load_bank(raw)
    bank = Bank(features)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = dict(
        dataset="eedi_exam", spec="task book v2 section 4.2, revision 2.1", seed=seed,
        sub_seed_format="{seed}/{K}/{slot}/{attempt}", target_draw="{seed}/{K}: sample count questions",
        K=list(ks), slots_per_K=count, max_redraws=retries, max_units=MAX_UNITS,
        bank_questions=len(bank.ids),
        raw_file_sha256={p.name: digest(p) for p in sorted(raw.glob("*.csv"))},
        rules={"unique_units": "values held by one bank question are excluded from the universe",
               "fill": ["same subject", "shares a retained unit", "whole bank"]},
        scope="All conclusions apply only to the retained universe; excluded direct identifiers are refused by a size-1 witness in deployment and are not evaluated here.",
        positioning="Real Eedi questions; which question is set is a sampled construct, not a real exam leak.",
        prior_scope="Uniform prior over the K candidates by design.",
        by_K={})
    with tempfile.TemporaryDirectory(dir=root) as stage:
        folder = Path(stage) / "eedi_exam"
        folder.mkdir(mode=0o700)
        with ExitStack() as stack:
            handles = {key: stack.enter_context((folder / f"{key}.jsonl").open("x", encoding="utf-8"))
                       for key in FILES}
            for k in ks:
                targets = random.Random(f"{seed}/{k}").sample(bank.ids, min(count, len(bank.ids)))
                rejected, discarded, sizes, histogram, dropped = (Counter() for _ in range(5))
                accepted = redraws = truncated = 0
                tiers = [0, 0, 0]
                for slot, target in enumerate(targets):
                    for attempt in range(retries + 1):
                        result = draw(bank, names, seed, k, slot, attempt, target)
                        if isinstance(result, str):
                            rejected[result] += 1
                            continue
                        batch, info = result
                        for key, rows in batch.items():
                            for row in rows:
                                handles[key].write(json.dumps(row, separators=(",", ":"),
                                                              ensure_ascii=False) + "\n")
                        sizes.update(map(len, batch["witness_sets"][0]["sets"]))
                        dropped[info["dropped_unique"]] += 1
                        truncated += info["truncated"]
                        tiers = [a + b for a, b in zip(tiers, info["fill_tiers"])]
                        accepted += 1
                        break
                    else:
                        discarded[result] += 1
                    redraws += attempt
                    histogram[attempt] += 1
                manifest["by_K"][k] = dict(
                    accepted=accepted, discarded=sum(discarded.values()), redraws=redraws,
                    redraw_histogram=dict(sorted(histogram.items())), rejected_draws=dict(rejected),
                    discarded_by_last_reason=dict(discarded), witness_sizes=dict(sorted(sizes.items())),
                    units_truncated=truncated,
                    unique_units_excluded_per_secret=dict(sorted(dropped.items())),
                    fill_candidates_by_tier=dict(zip(("same_subject", "shares_unit", "bank"), tiers)))
        (folder / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        folder.rename(dest)
    return dest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, nargs="+", default=[8, 16, 32])
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    print(generate(os.environ.get("COGNIGUARD_DATA_DIR", REPO.parent / "cogniguard_data"),
                   None, args.k, args.count, args.seed))
