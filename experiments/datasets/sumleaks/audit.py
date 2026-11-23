"""Offline Sum Leaks schema and potential join-key audit. Run as a module."""
import json
import re
from collections import Counter, defaultdict
from itertools import combinations

from experiments.datasets.audit_io import digest, raw_dir, save


def defense_match(sentence, names):
    # Use the final assertion only. Some files contain a reasoning preamble.
    clauses = re.findall(r"\bcombination of (.+?) is sensitive\b", sentence, re.I)
    if not clauses:
        matches = sorted(n for n in names if re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", sentence))
        return ("partial" if matches else "none"), matches, False
    bits = re.split(r",\s*(?:and\s+)?|\s+and\s+", clauses[-1])
    items = [re.sub(r"^.*?['’]s\s+", "", b.strip()).strip("' `*\"") for b in bits]
    matches = sorted(set(items) & names)
    return ("full" if all(x in names for x in items) else ("partial" if matches else "none")), matches, True


def inspect_scene(d):
    tables = {}
    cols = []
    names = set()
    for agent, obj in d["data_distribution"].items():
        for name, table in obj["table"].items():
            ref = f"{agent}.{name}"
            names.add(name)
            rows = table["rows"]
            keys = sorted({key for row in rows for key in row})
            tables[ref] = {"columns": keys, "rows": len(rows)}
            for col in keys:
                values = [json.dumps(row[col], sort_keys=True) for row in rows
                          if row.get(col) is not None and row[col] != ""]
                unique = bool(rows) and len(set(values)) == len(rows)
                cols.append((ref, col, set(values), unique))
    same, other = [], []
    for (a, x, av, au), (b, y, bv, bu) in combinations(cols, 2):
        if a == b:
            continue
        if x == y:
            basis = "id_suffix" if x.endswith("_id") else ("unique_in_both" if au and bu else "attribute")
            same.append({"tables": [a, b], "column": x, "candidate_basis": basis})
        elif av and bv:
            overlap = len(av & bv) / len(av | bv)
            if overlap >= 0.8:
                other.append({"columns": [f"{a}.{x}", f"{b}.{y}"], "jaccard": overlap,
                              "distinct_counts": [len(av), len(bv)]})
    status, matches, parsed = defense_match(d["defense"], names)
    return {"tables": tables, "same_name_candidates": same, "different_name_candidates": other,
            "defense_match": status, "matched_names": matches, "parsed_list": parsed,
            "reasoning_marker": "<think>" in d["defense"]}


def audit(folder):
    scenes, hashes = {}, {}
    types = defaultdict(Counter)
    for path in sorted(folder.glob("experiment_*_def_adv_both.json")):
        d = json.loads(path.read_bytes())
        for k, v in d.items():
            types[k][type(v).__name__] += 1
        key = int(path.name.split("_")[1])
        scenes[key] = inspect_scene(d)
        hashes[path.name] = digest(path)
    if not scenes:
        raise ValueError("no Sum Leaks scenario files")
    # Cover rare defense formats first, then the range of candidate-key counts.
    ranked = sorted(scenes, key=lambda i: (len(scenes[i]["same_name_candidates"]),
                                            len(scenes[i]["different_name_candidates"]), i))
    picked = []
    for i in ranked:
        s = scenes[i]
        if s["reasoning_marker"] or s["defense_match"] != "full":
            picked.append(i)
    for n in range(10):
        picked.append(ranked[round(n * (len(ranked)-1) / 9)])
    picked = list(dict.fromkeys(picked + ranked))[:10]
    return {"files": len(scenes), "field_types": dict(types), "scenes": scenes,
            "table_count": sum(len(v["tables"]) for v in scenes.values()),
            "coverage": dict(Counter(v["defense_match"] for v in scenes.values())),
            "overlap_measure": "Jaccard on typed distinct non-null values, threshold 0.8",
            "representative_ids": picked}, hashes


if __name__ == "__main__":
    save("sumleaks", *audit(raw_dir() / "sumleaks"))
