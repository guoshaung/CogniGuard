"""Transcribe independent reading of the 180 observed GPU pilot endpoints."""
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
VARIANTS = ("plain", "M1", "M2", "M3")
CONTROLLED = PROJECT / "experiments/hsw_provenance/propagation"
CANDIDATES = HERE.parent / "candidates"

# Each code gives surviving core claims for the scheduled sources in order.
# Explicit conditions are required for condition-bearing claims (e.g. no drag),
# while contextual quantities can be understood from adjacent sentences.
REVIEW = {
    "f1-summary": {1: ["23"]*4, 3:["23"]*4, 5:["23"]*4},
    "f2-summary": {
        1:["2/123"]*4,
        3:["2/123", "2/23", "2/123", "2/13"],
        5:["2/13", "2/3", "2/13", "2/13"],
    },
    "f3-summary": {
        1:["23/23/12", "123/23/123", "23/23/12", "23/3/12"],
        3:["23/23/12", "3/3/12", "23/23/12", "23/3/12"],
        5:["23/23/12", "3/3/", "23/23/12", "23/3/12"],
    },
    "f1-light_rewrite": {1:["123"]*4,3:["123"]*4,5:["123"]*4},
    "f2-light_rewrite": {1:["123/123"]*4,3:["123/123"]*4,5:["123/123"]*4},
    "f3-light_rewrite": {
        1:["123/123/123"]*4,
        3:["123/12/123","123/23/123","123/123/123","123/123/123"],
        5:["123/12/123","123/23/123","123/123/123","123/123/123"],
    },
    "f1-strong_rewrite": {1:["123"]*4,3:["23"]*4,5:["23"]*4},
    "f2-strong_rewrite": {
        1:["123/123","123/123","12/23","123/123"],
        3:["123/23","123/123","12/23","123/23"],
        5:["123/23","123/23","12/23","123/23"],
    },
    "f3-strong_rewrite": {
        1:["123/123/123"]*4,
        3:["123/123/123","123/123/123","123/23/123","123/23/123"],
        5:["123/123/123","123/123/123","123/23/123","123/23/123"],
    },
}


def read_json(path):
    return json.loads(path.read_bytes())


def contextual_review(group, depth, variant):
    altered = []
    material = []
    if group == "f1-strong_rewrite" and depth >= 3 and variant in ("plain","M1"):
        altered.append("math-01:f1")
        material.append("Changes one genre per shelf into one shelf per genre; M1 adds equal shelf height.")
    if group == "f3-light_rewrite" and depth >= 3:
        if variant == "plain":
            altered.append("physics-01:f3")
            material.append("Substitutes work for heat in the process-dependent comparison, dropping the original heat claim.")
        elif variant == "M1":
            altered.append("physics-01:f1")
            material.append("Claims constant internal energy while also stating an increase of 650 J.")
    return altered, material


def main():
    raw = HERE / "pilot/cases.jsonl"
    rows = [json.loads(line) for line in raw.read_text(encoding="utf8").splitlines()]
    assert len(rows) == len({(r["case_id"],r["variant"]) for r in rows}) == 180
    releases = {variant:{r["release_id"]:r for r in read_json(
        CONTROLLED/"releases.json" if variant=="plain" else CANDIDATES/f"{variant}_releases.json")}
        for variant in VARIANTS}
    sources = {r["source_id"]:r for r in read_json(CONTROLLED/"sources.json")}
    history = [json.loads(line) for line in (HERE/"pilot/hops.jsonl").read_text(encoding="utf8").splitlines()]
    assert len(history) == 300
    previous = {(r["chain_id"],r["variant"],r["depth"]):r["text"] for r in history}
    annotations = []
    for row in rows:
        group = row["chain_id"].removeprefix("pilot-")
        variant, depth = row["variant"], row["depth"]
        batch_sources = row["input_source_ids"]
        input_ids = row["input_release_ids"]
        reference = [
            fact for sid in batch_sources for fact in (u["fact_id"] for u in sources[sid]["units"])
        ]
        original = "\n\n".join(releases[variant][rid]["text"] for rid in input_ids)
        prior = original if depth == 1 else previous[row["chain_id"],variant,depth-1]
        assert hashlib.sha256(prior.encode()).hexdigest() == row["input_sha256"]
        text = row["text"]
        altered, material = contextual_review(group,depth,variant)
        if row["transform"] in ("forward","truncate"):
            selected = set(text.splitlines())
            retained = [
                fact_id for rid, sid in zip(input_ids,batch_sources,strict=True)
                for unit, body in zip(sources[sid]["units"],releases[variant][rid]["text"].splitlines(),strict=True)
                if body in selected for fact_id in [unit["fact_id"]]
            ]
            review = "Exact original release lines align to the frozen facts."
            instruction_pass = text == prior if row["transform"]=="forward" else prior.startswith(text)
        else:
            code = REVIEW[group][depth][VARIANTS.index(variant)]
            retained = [f"{sid}:f{n}" for sid, digits in zip(batch_sources,code.split("/"),strict=True) for n in digits]
            instruction_pass = bool(text) and not material
            if row["transform"] == "summary":
                instruction_pass &= len(text.split()) <= len(prior.split())*.65
            elif row["transform"] in ("light_rewrite", "strong_rewrite"):
                instruction_pass &= set(retained) == set(reference) and text != prior
            review = "Checked the observed conclusions, quantities, units, and required conditions against the frozen facts."
        assert not set(altered)&set(retained), (group,depth,variant,altered)
        assert set(retained) <= set(reference)
        support = [rid for rid,sid in zip(input_ids,batch_sources,strict=True)
                   if any(f in retained for f in reference if f.startswith(sid+":"))]
        evidence = [f"{fact}: {next(u['text'] for u in sources[fact.split(':',1)[0]]['units'] if u['fact_id']==fact)}"
                    for fact in retained]
        missing = sorted(set(reference)-set(retained)-set(altered))
        annotations.append(dict(case_id=row["case_id"], variant=variant, depth=depth, transform=row["transform"],
                                retained_fact_ids=retained, unknown_fact_ids=[], altered_fact_ids=altered,
                                lost_fact_ids=missing, supported_release_ids=support, history_release_ids=input_ids,
                                compatible_source_ids=[releases[variant][rid]["source_id"] for rid in support],
                                instruction_pass=instruction_pass,
                                text_quality="MATERIAL_KNOWLEDGE_CHANGE" if material else "UNDERSTANDABLE",
                                source_word_count=len(original.split()), previous_word_count=len(prior.split()),
                                output_word_count=len(text.split()), fact_fidelity=len(retained)/len(reference),
                                review_evidence=[review,*material,*evidence],
                                output_sha256=row["text_sha256"]))
    out = HERE / "pilot/annotations.jsonl"
    with out.open("w",encoding="utf-8",newline="\n") as stream:
        for row in annotations:
            stream.write(json.dumps(row,ensure_ascii=False)+"\n")
    summary = dict(n=len(annotations), methodology="Independent Codex review of all rewrite and summary endpoints, with exact matching for controls. Counts measure core facts, with units, quantities and material conditions checked.",
                   results={v:{mode:{str(depth):{
                       "n":len(selected), "mean_fact_fidelity":statistics.mean(r["fact_fidelity"] for r in selected),
                       "quality_counts":dict(Counter(r["text_quality"] for r in selected)),
                       "instruction_pass":sum(r["instruction_pass"] for r in selected)}
                       for depth in (1,3,5)
                       if (selected:=[r for r in annotations if (r["variant"],r["transform"],r["depth"])==(v,mode,depth)])}
                       for mode in sorted({row["transform"] for row in annotations})} for v in VARIANTS})
    (HERE/"pilot/quality_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(out, len(annotations))


if __name__ == "__main__":
    main()
