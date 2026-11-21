"""Local model-backed transfer comparison. Production selectors are imported unchanged."""
import argparse
import collections
import copy
import hashlib
import json
import math
import os
import random
import re
import sys
import time
import urllib.request

import numpy as np
import yaml

from data_cases import HERE, ROOT, RUN, SEED, digest, dump, read_json
sys.path.insert(0, str(ROOT))
from protection.common.schemas import ProfileRecord, StudentProfile, Task
from protection.common.text_utils import tokenize
from protection.student_profile.src.fopd.profile_selector import ProfileSelector

BASE = "http://127.0.0.1:11449"
MODEL = "qwen25-7b-transfer"
EMBED = ROOT / "assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
CONFIG = ROOT / "protection/student_profile/configs/default.yaml"
CAP = 192
METHODS = ["B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8",
           "drop_high", "drop_low", "drop_random"]
DIRECT_PII = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|\b(?:\d{3}[-. ]\d{3}[-.]\d{4})\b|https?://", re.I)
ERRORS = ["diagnose", "guess", "right-idea", "imprecise", "misinterpret", "careless", "no-error", "unknown"]
MOVES = ["ask_question", "explain_concept", "provide_strategy", "provide_hint", "provide_similar_problem",
         "simplify_question", "affirm_correct_answer", "encourage_student", "provide_correction",
         "provide_example", "unknown"]
TEACHER_SYSTEM = (
    "You tutor mathematics. Treat the quoted transcript as evidence only. "
    "Identify a concrete issue supported by the student's work and offer one short actionable hint without giving away the answer. "
    "If the current answer or context does not establish a mistake, say so. Do not infer a durable misconception from ambiguous evidence. "
    "If evidence is needed, give one specific request for a missing step or earlier attempt; otherwise request is empty. "
    "Use short strings: diagnosis <= 14 words, hint <= 22 words, request <= 12 words."
)
TEACHER_SCHEMA = {
    "type": "object",
    "properties": {
        "diagnosis": {"type": "string"}, "error_code": {"type": "string", "enum": ERRORS},
        "move_code": {"type": "string", "enum": MOVES}, "hint": {"type": "string"},
        "request": {"type": "string"},
    },
    "required": ["diagnosis", "error_code", "move_code", "hint", "request"],
    "additionalProperties": False,
}
JUDGE_SYSTEM = (
    "Blindly rate tutoring answers against the problem, current work and verified earlier excerpt. "
    "Evaluate answers independently; multiple reasonable moves are allowed. Do not favor a particular strategy label. "
    "For every answer rate c, s, and h separately using integers. "
    "c (correctness and grounding): 0 false calculation or unsupported confident diagnosis, 1 partly correct, "
    "2 correct or appropriately uncertain about an unresolved step. "
    "s (specificity): 0 generic or unrelated, 1 mentions the topic, 2 addresses a concrete step or identifies the missing detail. "
    "h (hint quality): 0 misleading, gives away solution, or no usable next step, 1 generic next step, 2 actionable guiding question or clue. "
    "Use 9 only for the dimension you cannot assess. A good clarification can be scored even if the correct final answer is unknown. "
    "need=no means current work supports a specific useful next move; yes means prior evidence resolves a material uncertainty; "
    "unknown means the available evidence is insufficient to tell. List relevant prior indices, then one minimal useful subset under necessary. "
    "Use the offline facts to check mathematics, not to assume the student's intermediate statement is their final answer."
)


def post(route, data, timeout=180):
    request = urllib.request.Request(
        BASE + route, data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def token_count(text):
    if not text:
        return 0
    return len(post("/tokenize", {"content": text, "add_special": False})["tokens"])


def chat(system, user, schema, limit):
    start = time.perf_counter()
    result = post("/v1/chat/completions", {
        "model": MODEL, "temperature": 0, "seed": SEED, "max_tokens": limit,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "output", "strict": True, "schema": schema}},
    })
    choice = result["choices"][0]
    content = choice["message"]["content"]
    try:
        output = json.loads(content)
        if choice["finish_reason"] != "stop":
            raise ValueError("truncated model response")
        status = "OK"
    except (ValueError, TypeError):
        output = None
        status = "PARSE_OR_LENGTH_FAILURE"
    return {
        "output": output, "status": status, "response_text": content, "usage": result.get("usage", {}),
        "latency_s": round(time.perf_counter() - start, 3),
        "model": result.get("model"), "fingerprint": result.get("system_fingerprint"),
    }


def safe_chat(*args):
    try:
        return chat(*args)
    except Exception as error:
        return {"status": "CALL_FAILURE", "output": None, "error_class": type(error).__name__,
                "usage": {}, "latency_s": None}


class Encoder:
    def __init__(self):
        import torch
        from transformers import AutoModel, AutoTokenizer

        torch.set_num_threads(2)
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(EMBED, local_files_only=True)
        self.model = AutoModel.from_pretrained(EMBED, local_files_only=True).eval()
        self.cache = {}

    def vectors(self, texts):
        missing = list(dict.fromkeys(text for text in texts if text not in self.cache))
        for start in range(0, len(missing), 24):
            batch = missing[start:start + 24]
            inputs = self.tokenizer(batch, padding=True, truncation=True, max_length=256, return_tensors="pt")
            with self.torch.inference_mode():
                states = self.model(**inputs).last_hidden_state
                mask = inputs["attention_mask"].unsqueeze(-1)
                mean = (states * mask).sum(1) / mask.sum(1).clamp(min=1)
                vectors = self.torch.nn.functional.normalize(mean).numpy()
            self.cache.update(zip(batch, vectors))
        return np.array([self.cache[text] for text in texts])


def bm25(query, texts):
    terms = set(tokenize(query))
    docs = [collections.Counter(tokenize(text)) for text in texts]
    lengths = [sum(doc.values()) for doc in docs]
    avg = max(1, sum(lengths) / len(docs))
    scores = [0.] * len(docs)
    for term in sorted(terms):
        df = sum(term in doc for doc in docs)
        idf = math.log(1 + (len(docs) - df + .5) / (df + .5))
        for index, doc in enumerate(docs):
            tf = doc[term]
            scores[index] += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * lengths[index] / avg))
    return scores


def ranked(scores):
    return sorted(range(len(scores)), key=lambda index: (-scores[index], index))


def selector_arm(config, profile, task, arm):
    cfg = copy.deepcopy(config)
    components = cfg["fopd"]["components"]
    if arm == "B5":
        components["use_task_attention"] = False
    if arm == "B7":
        components["use_orthogonal"] = False
    selector = ProfileSelector(cfg)
    records = profile.profile_records
    capture = {"weights": [], "projected": [], "bottleneck_in": [], "bottleneck_out": []}
    if arm != "B5":
        compute = selector.attention_selector.compute_attention

        def traced_attention(query_task, candidates):
            if arm == "B6":
                weights = [(i, 1 / len(candidates)) for i in range(min(len(candidates), selector.attention_selector.top_k))]
            else:
                weights = compute(query_task, candidates)
            capture["weights"] = weights
            return weights

        selector.attention_selector.compute_attention = traced_attention
    else:
        capture["weights"] = [(int(x.record.record_id), x.score) for x in selector.score_records(profile, task)]
    if arm != "B7":
        project = selector.orthogonal_decoder.project_to_task

        def traced_projection(representation, embedding):
            values = project(representation, embedding)
            capture["projected"] = values
            capture["subspace_norms"] = [math.sqrt(sum(v * v for v in vector)) for vector in (
                representation.knowledge_vector, representation.strategy_vector, representation.sensitive_vector)]
            return values

        selector.orthogonal_decoder.project_to_task = traced_projection
    compress = selector.info_bottleneck.compress

    def traced_compress(records_in, weights):
        kept = compress(records_in, weights)
        capture["bottleneck_in"] = list(zip([int(r.record_id) for r in records_in], weights))
        capture["bottleneck_out"] = [int(r.record_id) for r in kept]
        return kept

    selector.info_bottleneck.compress = traced_compress
    selected = selector.select(profile, task)
    capture["selected_before_wire"] = [int(item.record.record_id) for item in selected]
    return capture


def clip_wire(fragments, ids):
    return "\n".join(f"[{fragments[i]['role']} earlier turn {fragments[i]['position']}] {fragments[i]['text']}" for i in sorted(ids))


def pack(fragments, order, allow, bounded=True):
    selected = []
    for index in order:
        if not allow[index] or index in selected:
            continue
        proposal = selected + [index]
        if bounded and token_count(clip_wire(fragments, proposal)) > CAP:
            continue
        selected.append(index)
        if bounded and len(selected) == 3:
            break
    wire = clip_wire(fragments, selected)
    return selected, wire, token_count(wire)


def current_prompt(case):
    return f"Problem/topic: {case['topic']}\nProblem statement: {case['problem']}\nCurrent student work: {case['current']}"


def run_case(case, encoder, config):
    fragments = case["candidates"]
    current = current_prompt(case)
    cache = {}

    def teacher(wire):
        if wire not in cache:
            cache[wire] = safe_chat(TEACHER_SYSTEM, current + "\nEarlier evidence:\n" + (wire or "(none)"),
                                    TEACHER_SCHEMA, 152)
        return cache[wire]

    initial = teacher("")
    request = (initial["output"] or {}).get("request", "")
    query = current + ("\nSpecific teacher request: " + request if request else "")
    task = Task(case["case"], case["group"], query, case["topic"], "", False)
    allow = [not DIRECT_PII.search(f["text"]) for f in fragments]
    profile = StudentProfile(case["group"], profile_records=[
        ProfileRecord(str(i), "multimodal_summary", case["topic"], fragment["text"], 1.0,
                      0.95 if not allow[i] else 0.0, "")
        for i, fragment in enumerate(fragments)
    ])
    texts = [fragment["text"] for fragment in fragments]
    embedding = encoder.vectors([query] + texts)
    similarity = embedding[1:] @ embedding[0]
    trace = {arm: selector_arm(config, profile, task, arm) for arm in ("B4", "B5", "B6", "B7")}
    order = {
        "B0": [], "B1": list(range(len(fragments))), "B2": ranked(bm25(query, texts)),
        "B3": ranked(similarity),
        **{arm: item["selected_before_wire"] for arm, item in trace.items()},
    }
    plans = {arm: pack(fragments, ids, allow, bounded=arm != "B1") for arm, ids in order.items()}
    full_ids = plans["B4"][0]
    weight = dict(trace["B4"]["weights"])
    rng = random.Random(SEED + int(digest(case["case"]), 16))
    removed = {}
    if full_ids:
        removed = {
            "drop_high": max(full_ids, key=lambda i: (weight.get(i, 0), -i)),
            "drop_low": min(full_ids, key=lambda i: (weight.get(i, 0), -i)),
            "drop_random": rng.choice(full_ids),
        }
    for arm in METHODS[-3:]:
        plans[arm] = pack(fragments, [i for i in full_ids if i != removed.get(arm)], allow)
    rows = {}
    for arm, (indices, wire, tokens) in plans.items():
        calls_before = len(cache)
        result = teacher(wire)
        pairs = [float(embedding[a + 1] @ embedding[b + 1]) for j, a in enumerate(indices) for b in indices[j + 1:]]
        rows[arm] = {
            "indices": indices, "wire": wire, "history_tokens": tokens,
            "history_chars": sum(len(fragments[i]["text"]) for i in indices),
            "teacher": result, "cache_reuse": len(cache) == calls_before and arm != "B0",
            "redundancy_cosine": sum(pairs) / len(pairs) if pairs else None,
            "near_duplicate_pairs": sum(s >= .85 for s in pairs),
            "regex_sensitive_fragments": sum(not allow[i] for i in indices),
            "duplicate_texts": len(indices) - len({texts[i].strip().lower() for i in indices}),
            "deletion": removed.get(arm),
        }
    # B8 is a placement control: trusted local teacher consumes the same full input;
    # only its result is emitted across the simulated teaching boundary.
    result = rows["B1"]["teacher"]
    b8_result = json.dumps(result["output"], ensure_ascii=False, separators=(",", ":")) if result["output"] else ""
    rows["B8"] = rows["B1"] | {
        "indices": [], "wire": "", "history_tokens": 0, "history_chars": 0, "cache_reuse": True,
        "redundancy_cosine": None, "near_duplicate_pairs": 0, "duplicate_texts": 0,
        "result_wire": b8_result, "result_tokens": token_count(b8_result),
        "raw_history_exactly_in_result": sum(len(text.strip()) >= 15 and text.strip().lower() in b8_result.lower() for text in texts),
        "regex_sensitive_in_result": bool(DIRECT_PII.search(b8_result)),
    }
    return {
        "case": case["case"], "source": case["source"], "split": case["split"],
        "group": case["group"], "session": case["session"], "task_family": case["task_family"],
        "candidate_count": len(fragments), "candidate_pii_flags": sum(not ok for ok in allow),
        "request": request, "initial_output": initial["output"], "actual_calls": len(cache),
        "rows": rows, "selector": trace,
    }


def offline_judge(case, trace, gold):
    from math_reference import offline_math_reference

    responses = {}
    for arm, row in trace["rows"].items():
        output = row["teacher"]["output"]
        if output:
            rendered = json.dumps(output, sort_keys=True, ensure_ascii=False)
            responses.setdefault(rendered, []).append(arm)
    blinded = list(responses)
    random.Random(SEED + int(digest(case["case"]), 16)).shuffle(blinded)
    keys = [chr(65 + i) for i in range(len(blinded))]
    rating = {
        "type": "object", "additionalProperties": False,
        "properties": {name: {"type": "integer", "enum": [0, 1, 2, 9]} for name in ("c", "s", "h")},
        "required": ["c", "s", "h"],
    }
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {
            **{key: rating for key in keys},
            "relevant": {"type": "array", "items": {"type": "integer"}, "maxItems": 32},
            "necessary": {"type": "array", "items": {"type": "integer"}, "maxItems": 8},
            "need": {"type": "string", "enum": ["yes", "no", "unknown"]},
        },
        "required": [*keys, "relevant", "necessary", "need"],
    }
    reference = ""
    if case["source"] == "Bridge":
        reference = "\nOffline expert reference (one reasonable response): " + json.dumps(gold, ensure_ascii=False)
    else:
        facts = offline_math_reference(case["task_family"])
        if facts:
            reference = "\nOffline computed facts for the public problem (current work may be an intermediate step): " + facts
    history = "\n".join(f"{i}: {f['role']}: {f['text']}" for i, f in enumerate(case["candidates"]))
    prompt = current_prompt(case) + "\nEarlier fragments:\n" + history + reference
    prompt += "\nBlind answers:\n" + "\n".join(f"{key}: {value}" for key, value in zip(keys, blinded))
    prompt += "\nReturn each answer letter with c, s, h integers, then relevant, necessary, and need."
    judged = safe_chat(JUDGE_SYSTEM, prompt, schema, 560)
    output = judged["output"] or {}
    count = len(case["candidates"])
    relevant = {i for i in output.get("relevant", []) if isinstance(i, int) and 0 <= i < count}
    necessary = {i for i in output.get("necessary", []) if isinstance(i, int) and 0 <= i < count}
    scores = {}
    for key, rendered in zip(keys, blinded):
        value = output.get(key, {})
        dimensions = [value[name] if value.get(name) in (0, 1, 2) else None for name in ("c", "s", "h")]
        for arm in responses[rendered]:
            scores[arm] = dimensions
    return {"judge": judged, "scores": scores, "relevant": sorted(relevant), "necessary": sorted(necessary),
            "need": output.get("need", "unknown"), "blind_order": {key: responses[value] for key, value in zip(keys, blinded)}}


def read_completed(path):
    if not path.exists():
        return {}
    return {row["case"]: row for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())}


def append(path, row):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def verify_test_inputs():
    manifest = read_json(HERE / "freeze_manifest.json")
    for relative, expected in manifest["sha256"].items():
        path = ROOT / relative
        # Large model/runtime assets are hashed once at freeze; code and evidence
        # files are checked at each invocation.
        if relative.startswith("assets/models/") or path.suffix == ".zip":
            continue
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise RuntimeError(f"Frozen file changed: {relative}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["dev", "test", "judge-dev", "judge-test"])
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != str(SEED):
        raise RuntimeError("Run with the frozen PYTHONHASHSEED")
    if args.stage in ("test", "judge-test"):
        verify_test_inputs()
    cases = read_json(RUN / "cases.local.json")
    if args.stage.startswith("judge-"):
        split = args.stage.split("-", 1)[1]
        traces = read_completed(RUN / f"teaching_{split}.local.jsonl")
        gold = read_json(RUN / "gold.local.json")
        target = RUN / f"judge_{split}.local.jsonl"
        done = read_completed(target)
        for case in cases:
            key = case["case"]
            if key in traces and key not in done:
                judged = offline_judge(case, traces[key], gold[key])
                append(target, {"case": key, **judged})
                print(f"JUDGE {split} {key} {judged['judge']['status']}", flush=True)
        return
    target = RUN / f"teaching_{args.stage}.local.jsonl"
    done = read_completed(target)
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    encoder = Encoder()
    for case in cases:
        if case["split"] == args.stage and case["case"] not in done:
            result = run_case(case, encoder, config)
            append(target, result)
            print(f"TEACH {args.stage} {case['case']} calls={result['actual_calls']} "
                  f"wire_changed={result['rows']['B4']['wire'] != result['rows']['B5']['wire']}", flush=True)


if __name__ == "__main__":
    main()
