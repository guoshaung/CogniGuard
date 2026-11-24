"""Two-issuer carrier pilot using frozen HSW sentence-prefix vocabulary."""
import difflib
import hashlib
import json
import re
import time
import argparse
from pathlib import Path

from propagation.build import replay_marked

HERE = Path(__file__).resolve().parent
PREFIX = {"issuer-a": "Here, ", "issuer-b": "In this case, "}
WORD = re.compile(r"\b[\w]+\b")
TOKEN = re.compile(r"\w+|[^\w\s]")


def words(text):
    return set(WORD.findall(text.lower()))


def spans(text):
    for line in text.splitlines():
        yield line


def mark(release):
    prefix = PREFIX[release["issuer_id"]]
    output = []
    edits = []
    for line in spans(release["text"]):
        if not re.match(r"[A-Z][a-z]+ ", line):
            output.append(line)
            continue
        proposed = prefix + line[0].lower() + line[1:]
        if len(WORD.findall(prefix)) > int(len(WORD.findall(line)) * .10):
            output.append(line)
            continue
        edits.append({"line": len(output), "prefix": prefix, "original_initial": line[0]})
        output.append(proposed)
    restored = output.copy()
    for edit in edits:
        i = edit["line"]
        restored[i] = edit["original_initial"] + output[i][len(edit["prefix"])+1:]
    assert "\n".join(restored) == release["text"]
    text = "\n".join(output)
    return dict(release, text=text, marked_sha256=hashlib.sha256(text.encode()).hexdigest(),
                certificate=edits, exact_inverse=True)


def identify_line(line, by_source):
    q = words(line)
    ranked = sorted((max(len(q & f) / max(1,len(q | f)) for f in refs), source)
                    for source, refs in by_source.items())
    best, source = ranked[-1]
    return source if best >= .30 and best - ranked[-2][0] >= .07 else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data",type=Path,default=HERE/"propagation")
    parser.add_argument("--out",type=Path,default=HERE/"watermark")
    args = parser.parse_args()
    source_dir, out = args.data, args.out
    out.mkdir(parents=True, exist_ok=True)
    releases = json.loads((source_dir/"releases.json").read_bytes())
    sources = json.loads((source_dir/"sources.json").read_bytes())
    cases = [json.loads(line) for line in (source_dir/"cases.jsonl").read_text(encoding="utf8").splitlines()]
    if not all(row["issuer_id"] in PREFIX for row in releases):
        raise ValueError("Unexpected issuer")
    marked = [mark(row) for row in releases]
    lookup = {(row["source_id"],row["issuer_id"]):row["release_id"] for row in releases}
    by_source = {row["source_id"]:[words(unit["text"]) for unit in row["units"]] for row in sources}
    rows = []
    def predict(case_id, method, content, tagged):
        start = time.perf_counter()
        source_set = set()
        release_set = set()
        issuer_set = set()
        for line in spans(content):
            issuer = next((name for name,prefix in PREFIX.items() if line.startswith(prefix)),None) if tagged else None
            source = identify_line(line[len(PREFIX[issuer]):] if issuer else line,by_source)
            if source:
                source_set.add(source)
            if issuer:
                issuer_set.add(issuer)
                if source:
                    release_set.add(lookup[(source,issuer)])
        return {"case_id":case_id,"method":method,
                     "source_ids":sorted(source_set),"release_ids":sorted(release_set),
                     "issuer_ids":sorted(issuer_set),"seconds":time.perf_counter()-start,
                     "text":content}
    for plain, watermarked in zip(cases,replay_marked(cases,releases,marked),strict=True):
        rows.append(predict(plain["case_id"],"HSW-prefix + lexical retrieval",watermarked["text"],True))
        rows.append(predict(plain["case_id"],"Same lexical retrieval, unmarked",plain["text"],False))
    stress = []
    for issuer,prefix in PREFIX.items():
        content = prefix + "take a short break before opening the next exercise."
        stress.append(predict(issuer,"Marker with no retained facts",content,True))
    (out/"orphan_stress.json").write_text(json.dumps(stress,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    (out/"marked_releases.json").write_text(json.dumps(marked,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    with (out/"predictions.jsonl").open("w",encoding="utf8") as stream:
        for row in rows:
            stream.write(json.dumps(row,ensure_ascii=False)+"\n")
    config = dict(prefixes=PREFIX, source_match="max word-set Jaccard ≥.30 and margin ≥.07",
                  issuance="two issuers share each unmarked source; per-block prefix is bound to retrieved source",
                  ceiling="floor(10% of words per fact sentence); preserve line breaks and permit reversible case change",
                  scope="HSW vocabulary adapter with direct tag lookup; no CertInsert statistical or keyed attribution claim",
                  transport="same fact IDs and transformations as the frozen controlled corpus; rewritten facts lose lexical surface",
                  power="the assignments are public for this pilot, no adversarial authentication",
                  embedded_releases=sum(bool(row["certificate"]) for row in marked), released=len(marked))
    (out/"config.json").write_text(json.dumps(config,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(len(rows), config["embedded_releases"])


if __name__=="__main__":
    main()
