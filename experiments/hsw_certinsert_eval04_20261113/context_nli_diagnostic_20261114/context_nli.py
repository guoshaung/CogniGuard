"""Run the contextual NLI diagnostic on frozen Stage 0 evidence only."""

import argparse
import hashlib
import json
import re
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
WORKTREE = EXPERIMENT.parents[1]
RUNTIME = WORKTREE / "var/results/hsw-st/certinsert_eval04_20261113"
STAGE0 = RUNTIME / "stage0"
OUTPUT = RUNTIME / HERE.name
TEMPLATES = (
    "In this case", "In this example", "In this problem", "In this situation",
    "In this step", "Here", "For this problem", "For this example",
    "In this exercise", "In this calculation",
)
SAMPLE_COUNT = 100
MAX_LENGTH = 512
BATCH_SIZE = 16
THRESHOLD = 0.9


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(path, expected):
    if digest(path) != expected:
        raise ValueError(f"Frozen SHA-256 mismatch: {path.name}")


def load_inputs():
    mining = read_json(EXPERIMENT / "CORPUS_MINING_FREEZE.json")
    names = ("R_CORPUS.json", "NLI_SENTENCE_POOL.json", "MINED_CANDIDATES.json",
             "ATTESTED_CANDIDATES.json")
    for name in names:
        verify(STAGE0 / name, mining["files"][name])
    stop = read_json(EXPERIMENT / "STAGE0_STOP_FREEZE.json")
    assert stop["L_star"] is None and not stop["next_stage_started"]
    verify(EXPERIMENT / "nli_filter.py", stop["code_sha256"]["nli_filter.py"])
    candidates = {row["text"]: row["df"] for row in read_json(STAGE0 / names[3])}
    assert len(candidates) == mining["attested"] == 47
    baseline = {}
    for filename, expected in stop["nli_records"].items():
        path = STAGE0 / "nli" / filename
        verify(path, expected)
        row = read_json(path)
        baseline[row["text"]] = {item["sentence_id"]: item["forward"] for item in row["details"]}
        assert len(baseline[row["text"]]) == SAMPLE_COUNT
    assert baseline.keys() == candidates.keys()
    return mining, candidates, baseline


def frequency_and_pool(mining):
    build = {row["id"]: row["text"] for row in read_json(STAGE0 / "R_CORPUS.json")
             if row["split"] == "build"}
    assert len(build) == mining["build"] == 3568
    mined = {row["text"]: row["df"] for row in read_json(STAGE0 / "MINED_CANDIDATES.json")}
    family = {"literal": set(), "with_comma": set()}
    frequency = []
    for template in TEMPLATES:
        form = r"\s+".join(re.escape(word) for word in template.split())
        literal = re.compile(rf"(?<![\w’'-]){form}(?![\w’'-])", re.IGNORECASE)
        with_comma = re.compile(literal.pattern + r"\s*,", re.IGNORECASE)
        doc_hits = {label: {key for key, text in build.items() if regex.search(text)}
                    for label, regex in (("literal", literal), ("with_comma", with_comma))}
        assert doc_hits["with_comma"] <= doc_hits["literal"]
        for label, hits in doc_hits.items():
            family[label].update(hits)
        frequency.append({"template": template, "original_sentence_prefix_df": mined.get(template.casefold(), 0),
                          **{label: len(hits) for label, hits in doc_hits.items()}})
    sentence_pool = {row["id"]: row for row in read_json(STAGE0 / "NLI_SENTENCE_POOL.json")}
    context = {}
    for sentence_id, current in sentence_pool.items():
        doc_id, index = sentence_id.rsplit("|s", 1)
        assert doc_id == current["document_id"] and doc_id in build
        prior = sentence_pool.get(f"{doc_id}|s{int(index) - 1}")
        if prior is not None:
            assert prior["document_id"] == doc_id
            assert prior["text"] in build[doc_id] and current["text"] in build[doc_id]
            context[sentence_id] = (prior["id"], prior["text"], current["text"])
    return frequency, {label: len(hits) for label, hits in family.items()}, context, len(sentence_pool)


def ranked_ids(word, context):
    return sorted(context, key=lambda sid: hashlib.sha256(f"EVAL04v3|nli|{word}|{sid}".encode()).digest())


def make_pair(context, sentence_id, word):
    previous_id, previous, current = context[sentence_id]
    inserted = word[0].upper() + word[1:]
    premise = f"{previous} {current}"
    hypothesis = f"{previous} {inserted}, {current[0].lower() + current[1:]}"
    return previous_id, premise, hypothesis


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "cuda"), required=True)
    args = parser.parse_args()

    import torch
    import transformers
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    begin = time.perf_counter()
    mining, candidates, baseline = load_inputs()
    frequency, family, context, old_pool_count = frequency_and_pool(mining)
    terms = sorted(candidates.keys() | {template.casefold() for template in TEMPLATES})
    assert len(terms) == 55 and len(context) >= SAMPLE_COUNT
    info = read_json(EXPERIMENT / "NLI_MODEL_FREEZE.json")
    model_path = Path(info["path"])
    for name, expected in info["files"].items():
        verify(model_path / name, expected)
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(model_path, local_files_only=True)
    model.to(args.device).eval()
    assert next(model.parameters()).dtype == torch.float32
    label = next(i for i, name in model.config.id2label.items() if name.casefold() == "entailment")
    assert str(label) == "0"

    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = []
    print(f"Context pool: {len(context)} of {old_pool_count} sentences; {args.device} FP32", flush=True)
    with (OUTPUT / "forward_scores.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for word in terms:
            selected = []
            encoded = []
            overlength = 0
            for sid in ranked_ids(word, context):
                previous_id, premise, hypothesis = make_pair(context, sid, word)
                item = tokenizer(premise, hypothesis, truncation=False, verbose=False)
                length = len(item["input_ids"])
                if length > MAX_LENGTH:
                    overlength += 1
                    continue
                selected.append({"sentence_id": sid, "previous_sentence_id": previous_id, "tokens": length,
                                 "original_forward_probability": baseline.get(word, {}).get(sid)})
                encoded.append(item)
                if len(selected) == SAMPLE_COUNT:
                    break
            assert len(selected) == SAMPLE_COUNT
            for start in range(0, SAMPLE_COUNT, BATCH_SIZE):
                inputs = tokenizer.pad(encoded[start:start + BATCH_SIZE], padding=True, return_tensors="pt")
                with torch.inference_mode():
                    logits = model(**inputs.to(args.device)).logits
                    probabilities = logits.softmax(dim=-1)[:, label]
                if not torch.isfinite(probabilities).all():
                    raise FloatingPointError(f"Non-finite probability for {word}")
                for row, value in zip(selected[start:start + BATCH_SIZE], probabilities.tolist(), strict=True):
                    row["forward_probability"] = value
            passed = sum(row["forward_probability"] >= THRESHOLD for row in selected)
            paired = [row for row in selected if row["original_forward_probability"] is not None]
            results.append({
                "term": word, "existing_candidate": word in candidates,
                "template": word in {template.casefold() for template in TEMPLATES},
                "n": len(selected), "forward_passed": passed, "forward_pass_rate": passed / SAMPLE_COUNT,
                "original_full_forward_passed": (sum(value >= THRESHOLD for value in baseline[word].values())
                                                 if word in baseline else None),
                "paired_n": len(paired),
                "paired_original_passed": sum(row["original_forward_probability"] >= THRESHOLD for row in paired),
                "paired_context_passed": sum(row["forward_probability"] >= THRESHOLD for row in paired),
                "skipped_overlength": overlength,
            })
            stream.write(json.dumps({"term": word, "rows": selected}, ensure_ascii=False) + "\n")
            stream.flush()
            print(f"{len(results):02d}/{len(terms)} {word}: {passed}/{SAMPLE_COUNT}", flush=True)
    result = {
        "results": results, "frequency": frequency, "family_distinct_documents": family,
        "build_documents": mining["build"], "context_pool": len(context),
        "original_sentence_pool": old_pool_count, "device": args.device, "dtype": "float32",
        "torch": torch.__version__, "transformers": transformers.__version__,
        "model_repo": info["repo"], "model_revision": info["revision"], "model_files_sha256": info["files"],
        "nli_pairs": len(terms) * SAMPLE_COUNT, "reverse_pairs": 0, "other_model_calls": 0,
        "stage0_status": "STOPPED_BEFORE_FLUENCY", "later_stage_started": False,
        "seconds": round(time.perf_counter() - begin, 3),
    }
    with (OUTPUT / "RUN.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
