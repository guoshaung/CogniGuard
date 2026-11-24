"""Score raw GPU relay endpoints with the frozen content retrieval pilot."""
import argparse
import hashlib
from pathlib import Path
import sys
import time

from orphan import HERE, PILOT, read, write

sys.path.insert(0, str(PILOT / "fingerprints"))
from run import chunks, digest, file_sha, jsonl, load_semantic, precompute, select, variants


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bge", type=Path, required=True)
    parser.add_argument("--rerank", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=HERE.parent / "real/pilot/cases.jsonl")
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    source_dir = PILOT / "propagation"
    sources = read(source_dir / "sources.json")
    releases = read(source_dir / "releases.json")
    configuration = PILOT / "fingerprints/configuration.json"
    frozen = read(configuration)
    for name in ("sources.json", "releases.json"):
        assert frozen["data_sha256"][name] == file_sha(source_dir / name)
    for name, path in (("bge", args.bge), ("rerank", args.rerank)):
        assert frozen["model_sha256"][name] == file_sha(path / "model.safetensors")
    public_cases = jsonl(args.cases)
    assert len({(row["case_id"], row["variant"]) for row in public_cases}) == len(public_cases)
    cases = []
    for row in public_cases:
        assert hashlib.sha256(row["text"].encode()).hexdigest() == row["text_sha256"]
        cases.append(dict(case_id=f'{row["case_id"]}|{row["variant"]}', text=row["text"]))
    base_index = list(dict.fromkeys((source["source_id"], chunk) for source in sources
                                     for chunk in chunks(source["text"])))
    active_index = list(dict.fromkeys([*base_index, *((source["source_id"], text)
                      for source in sources for text in variants(source["text"]))]))
    start = time.perf_counter()
    models = load_semantic(args.bge, args.rerank, frozen["cpu_threads"])
    loaded = time.perf_counter()
    ranked, cost, hashes, embedding_seconds = precompute(cases, sources, base_index, active_index, releases, models)
    predictions = []
    for method, queries in ranked.items():
        fixed = frozen[method]
        for raw, case in zip(public_cases, cases, strict=True):
            tick = time.perf_counter()
            ranking = queries[case["case_id"]]
            selected = select(ranking, fixed["threshold"], fixed["margin"])
            text = case["text"]
            matched = set().union(*(hashes[digest(chunk)] for chunk in [text, *chunks(text)]))
            compatible = sorted(row["release_id"] for row in releases if row["source_id"] in selected)
            exact = sorted(matched.intersection(compatible))
            determinate = []
            for source in selected:
                choices = [row["release_id"] for row in releases
                           if row["source_id"] == source and row["release_id"] in exact]
                if len(choices) == 1:
                    determinate.extend(choices)
            predictions.append(dict(case_id=raw["case_id"], variant=raw["variant"], method=method,
                                    source_ids=selected, release_ids=determinate,
                                    candidate_release_ids=compatible, exact_candidate_release_ids=exact,
                                    ranked_sources=[dict(source_id=key,score=value) for key,value in ranking],
                                    text_sha256=raw["text_sha256"], depth=raw["depth"],
                                    transform=raw["transform"], fusion=raw["fusion"],
                                    seconds=cost[method][case["case_id"]]+time.perf_counter()-tick))
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "real_content_predictions.jsonl").open("w", encoding="utf8") as stream:
        import json
        stream.writelines(json.dumps(row, ensure_ascii=False)+"\n" for row in predictions)
    write(args.out / "real_content_config.json", dict(
        queries=len(cases), predictions=len(predictions), methods=sorted(ranked),
        cases_sha256=file_sha(args.cases), frozen_configuration_sha256=file_sha(configuration),
        input_policy="Raw endpoint UTF-8 text exactly as presented to watermark decoder. Zero carrier removal.",
        cpu_threads=frozen["cpu_threads"], gpu_hours=0, paid_api_calls=0,
        model_loading_seconds=loaded-start, embedding_preprocessing_seconds=embedding_seconds,
        execution_seconds=time.perf_counter()-start,
        per_case_timing_policy="BGE includes amortized batch encoding. Cross-encoder time is allocated over its evaluated pairs.",
        deliberate_abstention="Report ledger candidates separately. Identical release text can produce ambiguous candidates."))
    print(len(predictions))


if __name__ == "__main__":
    main()
