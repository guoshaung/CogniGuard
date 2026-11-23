"""Turn Sum Leaks scenarios into discrete secrets with computed witness sets.

Standard library only. Reads $COGNIGUARD_RAW_DIR/sumleaks/*.json, writes
$COGNIGUARD_DATA_DIR/sumleaks/ (outside the repository). Run as a module:

    python -m experiments.datasets.sumleaks.generate

Secret: "the value of column c in sensitive table T for the entity whose
identifier column a has the public value v". The anchor value v is public; every
table, the anchor's own table included, is a unit. Joins follow only columns
whose name ends in `_id` (verified keys). A secret is `undetermined` when also
joining on other same-name columns changes its witness sets.

L(A) is computed by join reachability. With fewer tables the reachable values are
a subset of those reached with all tables, so S_A is either the whole domain or
{s*}; L is 0 or log2 K. One secret is kept per scenario (largest K, then a fixed
name order), so units are never shared between secrets.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import secrets as secrets_module
import tempfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CLAIM = re.compile(r"\bcombination of (.+?) is sensitive\b", re.I)


def _key(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def load_scene(path: Path) -> dict:
    raw = json.loads(path.read_bytes())
    tables = []
    for agent, obj in sorted(raw["data_distribution"].items()):
        for name, table in sorted(obj["table"].items()):
            rows = [dict(row) for row in table["rows"]]
            columns = sorted({col for row in rows for col in row})
            tables.append({"unit_id": f"{agent}.{name}", "agent": agent, "name": name,
                           "sensitive": table.get("sensitivity") == "sensitive",
                           "rows": rows, "columns": columns})
    return {"scene": int(path.name.split("_")[1]), "tables": tables, "defense": raw.get("defense", "")}


def join_columns(tables, *, ids_only: bool) -> frozenset[str]:
    counts = Counter(col for t in tables for col in t["columns"])
    shared = {col for col, n in counts.items() if n >= 2}
    if ids_only:
        return frozenset(col for col in shared if col.endswith("_id"))
    return frozenset(shared)


def reach(tables, held: frozenset[int], joins, anchor_col, anchor_val, target_idx, target_col):
    """Values of target_col reachable from the anchor through held tables."""
    known = {(anchor_col, _key(anchor_val))}
    matched: set[tuple[int, int]] = set()
    changed = True
    while changed:
        changed = False
        for ti in held:
            for ri, row in enumerate(tables[ti]["rows"]):
                if (ti, ri) in matched:
                    continue
                if any((c, _key(row[c])) in known for c in row if c in joins or c == anchor_col):
                    matched.add((ti, ri))
                    for c in row:
                        if c in joins:
                            pair = (c, _key(row[c]))
                            if pair not in known:
                                known.add(pair)
                                changed = True
                    changed = True
    if target_idx not in held:
        return set()
    return {_key(tables[target_idx]["rows"][ri][target_col])
            for (ti, ri) in matched if ti == target_idx and target_col in tables[ti]["rows"][ri]}


def leakage_table(tables, joins, anchor, target, domain):
    """L for every subset mask of the scene's tables."""
    anchor_col, anchor_val = anchor
    target_idx, target_col = target
    K = len(domain)
    out = {}
    for mask in range(1 << len(tables)):
        held = frozenset(i for i in range(len(tables)) if mask >> i & 1)
        values = reach(tables, held, joins, anchor_col, anchor_val, target_idx, target_col) & domain
        out[mask] = math.log2(K / len(values)) if values else 0.0
    return out


def minimal_witnesses(L: dict[int, float], n: int, tau: float) -> list[int]:
    star = {}
    found = []
    for mask in sorted(L, key=lambda m: (bin(m).count("1"), m)):
        prev = max((star[mask ^ (1 << i)] for i in range(n) if mask >> i & 1), default=0.0)
        star[mask] = max(L[mask], prev)
        if prev <= tau < star[mask]:
            found.append(mask)
    return found


def candidates(scene):
    tables = scene["tables"]
    ids = join_columns(tables, ids_only=True)
    anchors = sorted({(t["name"], col, _key(row[col])) for t in tables if not t["sensitive"]
                      for row in t["rows"] for col in row if col in ids and row[col] is not None})
    for ti, t in enumerate(tables):
        if not t["sensitive"]:
            continue
        for col in t["columns"]:
            if col.endswith("_id"):
                continue
            domain = {_key(row[col]) for row in t["rows"] if row.get(col) is not None}
            if len(domain) < 2:
                continue
            for _aname, acol, akey in anchors:
                aval = json.loads(akey)
                everything = frozenset(range(len(tables)))
                full = reach(tables, everything, ids, acol, aval, ti, col) & domain
                if len(full) != 1:
                    continue
                yield {"target_table": ti, "target_col": col, "anchor_col": acol, "anchor_val": aval,
                       "domain": sorted(domain), "value": next(iter(full)), "K": len(domain)}


def evaluate(scene, c):
    """Add witness sets and the label status. None when a single table already leaks."""
    tables = scene["tables"]
    ids = join_columns(tables, ids_only=True)
    broad = join_columns(tables, ids_only=False)
    domain = set(c["domain"])
    tau = max(math.log2(c["K"]) - 1, 0.5)
    anchor, target = (c["anchor_col"], c["anchor_val"]), (c["target_table"], c["target_col"])
    L = leakage_table(tables, ids, anchor, target, domain)
    wit = minimal_witnesses(L, len(tables), tau)
    if not wit or min(bin(m).count("1") for m in wit) < 2:
        return None
    L_broad = leakage_table(tables, broad, anchor, target, domain)
    status = "computed" if minimal_witnesses(L_broad, len(tables), tau) == wit else "undetermined"
    return {**c, "tau": tau, "L": L, "witnesses": wit, "status": status}


def defense_names(sentence: str, names: set[str]) -> set[str]:
    clauses = CLAIM.findall(sentence)
    if not clauses:
        return set()
    bits = re.split(r",\s*(?:and\s+)?|\s+and\s+", clauses[-1])
    items = {re.sub(r"^.*?['’]s\s+", "", b.strip()).strip("' `*\"") for b in bits}
    return items & names


def pick(scene):
    """Walk pairs by larger K, then a fixed name order. Keep the first determined one;
    if none is determined, keep the first undetermined one. Returns (choice, pairs, evaluated)."""
    tables = scene["tables"]

    def order(c):
        return (-c["K"], tables[c["target_table"]]["unit_id"], c["target_col"], c["anchor_col"],
                _key(c["anchor_val"]))

    pool = sorted(candidates(scene), key=order)
    fallback = None
    for evaluated, c in enumerate(pool, 1):
        full = evaluate(scene, c)
        if full is None:
            continue
        if full["status"] == "computed":
            return full, len(pool), evaluated
        fallback = fallback or full
    return fallback, len(pool), len(pool)


def build(raw: Path, out_root: Path) -> Path:
    out_root = out_root.resolve()
    if any((p / ".git").exists() for p in (out_root, *out_root.parents)):
        raise ValueError("choose an output directory outside the repository")
    dest = out_root / "sumleaks"
    if dest.exists():
        raise FileExistsError(f"{dest} exists; choose a fresh COGNIGUARD_DATA_DIR")
    files = sorted(raw.glob("experiment_*_def_adv_both.json"))
    if not files:
        raise ValueError("no Sum Leaks scenario files")
    out_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    records = {k: [] for k in ("targets", "units", "witness_sets", "leakage", "secrets_private")}
    stats = Counter()
    k_hist, w_hist, jaccard = Counter(), Counter(), []
    hashes = {}
    for path in files:
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        scene = load_scene(path)
        chosen, n_pool, n_det = pick(scene)
        stats["scenes"] += 1
        stats["candidate_pairs"] += n_pool
        stats["evaluated_pairs"] += n_det
        if chosen is None:
            stats["scenes_without_secret"] += 1
            continue
        tables = scene["tables"]
        tid = f"sl.{scene['scene']}"
        salt = secrets_module.token_hex(16)
        value = chosen["value"]
        status = chosen["status"]
        stats[f"secrets_{status}"] += 1
        records["targets"].append({
            "target_id": tid, "dataset": "sumleaks", "kind": "student_attribute",
            "domain": chosen["domain"], "K": chosen["K"], "prior": "uniform",
            "gain": {"type": "identity"}, "tau_bits": chosen["tau"],
            "value_commitment": hmac.new(salt.encode(), value.encode(), hashlib.sha256).hexdigest(),
            "label_status": status,
            "secret": {"target_table": tables[chosen["target_table"]]["unit_id"],
                       "target_column": chosen["target_col"], "anchor_column": chosen["anchor_col"]},
        })
        records["secrets_private"].append({"target_id": tid, "value": value, "salt": salt,
                                           "anchor_value": chosen["anchor_val"]})
        universe = [t["unit_id"] for t in tables]
        for t in tables:
            records["units"].append({
                "target_id": tid, "unit_id": t["unit_id"], "unit_type": "relation",
                "predicate": {"agent": t["agent"], "table": t["name"], "columns": t["columns"]},
                "satisfied_by": chosen["domain"], "is_public": not t["sensitive"],
            })
        if status != "computed":
            continue
        k_hist[chosen["K"]] += 1

        def members(mask):
            return [universe[i] for i in range(len(universe)) if mask >> i & 1]

        sets = [members(m) for m in chosen["witnesses"]]
        w_hist.update(len(s) for s in sets)
        records["witness_sets"].append({"target_id": tid, "tau_bits": chosen["tau"],
                                        "universe": universe, "sets": sets})
        star = {}
        for mask in sorted(chosen["L"], key=lambda m: (bin(m).count("1"), m)):
            prev = max((star[mask ^ (1 << i)] for i in range(len(universe)) if mask >> i & 1),
                       default=0.0)
            star[mask] = max(chosen["L"][mask], prev)
            records["leakage"].append({"target_id": tid, "units": members(mask),
                                       "L_bits": chosen["L"][mask], "L_star_bits": star[mask]})
        claimed = defense_names(scene["defense"], {t["name"] for t in tables})
        used = {universe[i].split(".", 1)[1] for m in chosen["witnesses"]
                for i in range(len(universe)) if m >> i & 1}
        if claimed:
            jaccard.append(len(claimed & used) / len(claimed | used))
    manifest = {
        "dataset": "sumleaks", "raw_file_sha256": hashes, "join_rule": "same-name columns ending in _id",
        "undetermined_rule": "witness sets change when all same-name columns are joined",
        "selection": "one secret per scenario: determined first, then largest K, then name order",
        "scope": "All conclusions apply only to the scenario's tables.",
        "counts": dict(stats), "K_histogram": dict(sorted(k_hist.items())),
        "witness_size_histogram": dict(sorted(w_hist.items())),
        "defense_jaccard_mean": (sum(jaccard) / len(jaccard)) if jaccard else None,
        "defense_jaccard_n": len(jaccard),
    }
    with tempfile.TemporaryDirectory(dir=out_root) as stage:
        folder = Path(stage) / "sumleaks"
        folder.mkdir(mode=0o700)
        for name, rows in records.items():
            with (folder / f"{name}.jsonl").open("x", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        (folder / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        folder.rename(dest)
    return dest


if __name__ == "__main__":
    raw = Path(os.environ.get("COGNIGUARD_RAW_DIR", REPO.parent / "cogniguard_raw")) / "sumleaks"
    out = Path(os.environ.get("COGNIGUARD_DATA_DIR", REPO.parent / "cogniguard_data"))
    print(build(raw, out))
