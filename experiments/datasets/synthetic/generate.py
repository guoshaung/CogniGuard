"""Generate the v2 synthetic discrete-secret benchmark using the standard library."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import random
import secrets
import tempfile
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = (
    "Item property {f} is {v}.",
    "The item has value {v} for feature {f}.",
    "For feature {f}, choose value {v}.",
)
FILES = ("targets", "units", "leakage", "witness_sets", "texts", "secrets_private")


def subsets(domain, units):
    """Return sizes, realized leakage, monotone closure, and all minimal witnesses."""
    size = len(domain)
    tau = math.log2(size / 2)
    possible = [set(domain)]
    leakage = [0.0]
    closure = [0.0]
    witnesses = []
    supports = [set(u["satisfied_by"]) for u in units]
    for mask in range(1, 1 << len(units)):
        bit = mask & -mask
        support = possible[mask ^ bit] & supports[bit.bit_length() - 1]
        possible.append(support)
        value = math.log2(size / len(support))
        leakage.append(value)
        previous = max(closure[mask ^ (1 << i)] for i in range(len(units)) if mask & (1 << i))
        closure.append(max(value, previous))
        if previous <= tau < closure[mask]:
            witnesses.append(mask)
    return list(map(len, possible)), leakage, closure, witnesses


def draw(seed, k, slot, attempt, features, values):
    rng = random.Random(f"{seed}/{k}/{slot}/{attempt}")
    target_id = f"{k}.{slot}"
    domain = [f"q{i}" for i in range(k)]
    vectors = [tuple(rng.randrange(values) for _ in range(features)) for _ in domain]
    selected = rng.randrange(k)
    units = []
    for i, value in enumerate(vectors[selected]):
        units.append(dict(target_id=target_id, unit_id=f"{target_id}.{i}",
                          unit_type="attribute", predicate=dict(feature=i, value=value),
                          satisfied_by=[q for q, row in zip(domain, vectors) if row[i] == value],
                          is_public=False))
    units.sort(key=lambda u: (len(u["satisfied_by"]), u["unit_id"]))
    units = sorted(units[:12], key=lambda u: u["unit_id"])
    counts, leakage, closure, witnesses = subsets(domain, units)
    bad_a = any(len(u["satisfied_by"]) < 2 for u in units)
    bad_b = not any(2 <= m.bit_count() <= 4 for m in witnesses)
    if bad_a or bad_b:
        return "a+b" if bad_a and bad_b else ("a" if bad_a else "b")
    return records(target_id, domain, selected, vectors, units, counts, leakage, closure,
                   witnesses, rng)


def records(target_id, domain, selected, vectors, units, counts, leakage, closure, witnesses, rng):
    k = len(domain)
    tau = math.log2(k / 2)
    value = domain[selected]
    salt = secrets.token_hex(16)
    commitment = hmac.new(salt.encode(), value.encode(), hashlib.sha256).hexdigest()
    target = dict(target_id=target_id, dataset="synthetic", kind="teaching_asset", domain=domain,
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

    def sentence(feature, val):
        t = rng.randrange(len(TEMPLATES))
        return f"attr_{t}", TEMPLATES[t].format(f=feature, v=val)

    def add(role, gold, sentences, **extra):
        texts.append(dict(text_id=f"{target_id}-t{len(texts)}", target_id=target_id,
                          gold_units=gold, role=role,
                          template_id="+".join(t for t, _ in sentences),
                          text=" ".join(s for _, s in sentences), **extra))

    by_id = {u["unit_id"]: u["predicate"] for u in units}
    for group in [[uid] for uid in ids] + sets:
        phrases = [sentence(by_id[uid]["feature"], by_id[uid]["value"]) for uid in group]
        add("unit" if len(group) == 1 else "combo", group, phrases)
    for j in rng.sample([j for j in range(k) if j != selected], 3):
        different = [p["feature"] for p in by_id.values() if vectors[j][p["feature"]] != p["value"]]
        f = rng.choice(different)
        add("decoy", [], [sentence(f, vectors[j][f])], decoy_of=domain[j])
    return dict(targets=[target], units=units, leakage=rows, texts=texts,
                witness_sets=[dict(target_id=target_id, tau_bits=tau, universe=ids, sets=sets)],
                secrets_private=[dict(target_id=target_id, value=value, salt=salt)])


def generate(root, ks=(8, 16, 32), count=200, features=6, values=3, seed=2026, retries=50):
    if not ks or len(set(ks)) != len(ks) or min(ks) < 4:
        raise ValueError("choose distinct K >= 4 for three decoys")
    if count < 1 or features < 1 or values < 2 or not 0 <= retries <= 50:
        raise ValueError("invalid synthetic dataset parameters")
    root = Path(root).resolve()
    if any((p / ".git").exists() for p in (root, *root.parents)):
        raise ValueError("choose an output directory outside the repository")
    dest = root / "synthetic"
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("synthetic output exists; choose a fresh COGNIGUARD_DATA_DIR")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = dict(dataset="synthetic", seed=seed, sub_seed_format="{seed}/{K}/{slot}/{attempt}",
                    K=list(ks), slots_per_K=count, F=features, V=values, max_redraws=retries,
                    raw_file_sha256={}, scope="All conclusions apply only to the retained universe.",
                    prior_scope="Uniform reference prior on candidate IDs before observing units.",
                    by_K={})
    with tempfile.TemporaryDirectory(dir=root) as stage:
        folder = Path(stage) / "synthetic"
        folder.mkdir(mode=0o700)
        with ExitStack() as stack:
            handles = {key: stack.enter_context((folder / (key + ".jsonl")).open("x", encoding="utf-8"))
                       for key in FILES}
            for k in ks:
                rejected, discarded, sizes, histogram = (Counter() for _ in range(4))
                accepted = redraws = 0
                for slot in range(count):
                    for attempt in range(retries + 1):
                        batch = draw(seed, k, slot, attempt, features, values)
                        if isinstance(batch, str):
                            rejected[batch] += 1
                            continue
                        for key, rows in batch.items():
                            for row in rows:
                                handles[key].write(json.dumps(row, separators=(",", ":")) + "\n")
                        sizes.update(map(len, batch["witness_sets"][0]["sets"]))
                        accepted += 1
                        break
                    else:
                        discarded[batch] += 1
                    redraws += attempt
                    histogram[attempt] += 1
                manifest["by_K"][k] = dict(accepted=accepted, discarded=sum(discarded.values()),
                    redraws=redraws, redraw_histogram=dict(histogram), rejected_draws=dict(rejected),
                    discarded_by_last_reason=dict(discarded), witness_sizes=dict(sizes),
                    units_truncated=accepted * max(features - 12, 0))
        (folder / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        folder.rename(dest)
    return dest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, nargs="+", default=[8, 16, 32])
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--features", type=int, default=6)
    parser.add_argument("--values", type=int, default=3)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    print(generate(os.environ.get("COGNIGUARD_DATA_DIR", REPO.parent / "cogniguard_data"),
                   args.k, args.count, args.features, args.values, args.seed))
