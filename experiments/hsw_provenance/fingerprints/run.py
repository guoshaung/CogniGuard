"""CPU retrieval baselines for one shared provenance corpus."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import time

WORD = re.compile(r"[a-z]+(?:'[a-z]+)?|\d+(?:\.\d+)?", re.I)
MASK = (1 << 64) - 1
PERMUTATIONS = 96
BGE_REPO = "BAAI/bge-small-en-v1.5"
BGE_REV = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
BGE_INSTRUCTION = "Represent this sentence for searching relevant passages: "
RERANK_REPO = "cross-encoder/ms-marco-TinyBERT-L-2-v2"
RERANK_REV = "81d1926f67cb8eee2c2be17ca9f793c7c3bd20cc"
METHODS = ("sha256", "minhash", "bm25", "bge", "bge_rerank",
           "issuance_lookup", "active_variants")


def digest(text):
    return hashlib.sha256(text.encode("utf8")).hexdigest()


def file_sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@lru_cache(maxsize=8192)
def tokens(text):
    return tuple(WORD.findall(text.lower()))


def split(text):
    return [s.strip() for s in re.split(r"\n+|(?<=[.!?])\s+(?=[A-Z])", text) if s.strip()]


def chunks(text):
    parts = split(text)
    windows = [text.strip()]
    if len(parts) > 1:
        windows.extend(" ".join(parts[i:i+2]) for i in range(len(parts)))
        windows.extend(parts)
    return list(dict.fromkeys(part for part in windows if tokens(part)))


def variants(text):
    parts = split(text)
    if len(parts) < 2:
        return []
    excerpts = [" ".join(parts[start:start+length]) for length in (1, 2, 3)
                for start in range(len(parts)) if length < len(parts)-start+1]
    reordered = [" ".join(parts[1:] + parts[:1]), " ".join(parts[::-1])]
    abbreviated = [re.sub(r"\bfor example\b", "e.g.", part, flags=re.I) for part in parts]
    return list(dict.fromkeys(value for value in [*excerpts,*reordered,*abbreviated]
                              if value != text and tokens(value)))


SALTS = [(int(digest(f"minhash|a|{i}")[:16], 16) | 1,
          int(digest(f"minhash|b|{i}")[:16], 16)) for i in range(PERMUTATIONS)]


@lru_cache(maxsize=8192)
def minhash(text):
    values = tokens(text)
    if len(values) < 3:
        return ()
    base = {int(digest(" ".join(values[i:i+3]))[:16], 16) for i in range(len(values)-2)}
    return tuple(min((multiplier*x+increment) & MASK for x in base)
                 for multiplier,increment in SALTS)


def minhash_score(query, doc):
    a,b = minhash(query), minhash(doc)
    return sum(left == right for left,right in zip(a,b,strict=True))/PERMUTATIONS if a and b else 0


class BM25:
    def __init__(self, documents):
        self.docs = [Counter(tokens(d)) for d in documents]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.average = statistics.mean(self.lengths)
        frequency = Counter(word for d in self.docs for word in d)
        self.idf = {word: math.log1p((len(self.docs)-n+.5)/(n+.5)) for word,n in frequency.items()}

    def scores(self, query):
        terms = set(tokens(query))
        normalizer = sum(self.idf.get(t,0) for t in terms) or 1
        output = []
        for doc,length in zip(self.docs,self.lengths,strict=True):
            penalty = 1.5*(.25+.75*length/self.average)
            score = sum(self.idf[t]*doc[t]*2.5/(doc[t]+penalty) for t in terms if t in doc)
            output.append(score/normalizer)
        return output


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line]


def save_json(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2), encoding="utf8")


def group_key(case):
    return ",".join(sorted(case.get("input_release_ids", ()))) or case["case_id"]


def evaluation_partition(cases):
    shared = {case["case_id"]:case.get("partition",case.get("split")) for case in cases}
    if all(value in {"calibration","dev","test"} for value in shared.values()):
        return {case_id:("dev" if value=="calibration" else value) for case_id,value in shared.items()}
    return {case["case_id"]: ("dev" if int(digest("provenance-fp-v1|"+group_key(case))[:8],16)%4==0 else "test")
            for case in cases}


def retained(case):
    return set(case["retained_source_ids"])


def choose_config(scored, cases, split, method):
    if method in {"sha256","issuance_lookup"}:
        return {"threshold":1.0,"margin":None,"max_sources":3}
    dev = [case for case in cases if split[case["case_id"]] == "dev"]
    vals = sorted({score for case in dev for _,score in scored[case["case_id"]]})
    if not vals:
        return {"threshold":float("inf"),"margin":None,"max_sources":3}
    thresholds = vals[::max(1,len(vals)//120)] + [vals[-1]+1e-6]
    answer = None
    for threshold in thresholds:
        for margin in (None,.1,.2,.35):
            counts = Counter()
            for case in dev:
                ranked = scored[case["case_id"]]
                selected = set(select(ranked,threshold,margin))
                truth = retained(case)
                counts.update(tp=len(selected & truth),fp=len(selected-truth),fn=len(truth-selected))
            d = 2*counts["tp"]+counts["fp"]+counts["fn"]
            f = 2*counts["tp"]/d if d else 0
            priority = (f, -counts["fp"], threshold)
            if answer is None or priority > answer[0]:
                answer = (priority,{"threshold":threshold,"margin":margin,"max_sources":3})
    return answer[1]


def select(ranked, threshold, margin):
    if not ranked:
        return []
    high = ranked[0][1]
    cutoff = max(threshold, high-margin) if margin is not None else threshold
    return [source for source,score in ranked if score >= cutoff][:3]


def load_semantic(bge, rerank, threads):
    import numpy as np
    import torch
    from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(threads)
    torch.set_grad_enabled(False)

    def embedding(path):
        tokenizer = AutoTokenizer.from_pretrained(path,local_files_only=True)
        encoder = AutoModel.from_pretrained(path,local_files_only=True).eval()

        def encode(texts, query=False):
            batches = []
            for start in range(0,len(texts),32):
                batch = [BGE_INSTRUCTION+text if query else text for text in texts[start:start+32]]
                inputs = tokenizer(batch,padding=True,truncation=True,max_length=384,return_tensors="pt")
                first = encoder(**inputs).last_hidden_state[:,0]
                batches.append(torch.nn.functional.normalize(first,dim=1).numpy())
            return np.concatenate(batches)
        return encode

    def ranking(path):
        tokenizer = AutoTokenizer.from_pretrained(path,local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(path,local_files_only=True).eval()

        def classify(pairs):
            scores = []
            for start in range(0,len(pairs),32):
                q,d = zip(*pairs[start:start+32],strict=True)
                batch = tokenizer(list(q),list(d),padding=True,truncation=True,max_length=256,return_tensors="pt")
                scores.extend(torch.sigmoid(model(**batch).logits.reshape(-1)).tolist())
            return scores
        return classify

    return embedding(bge), ranking(rerank)


def rank(mapped, scores):
    best = {}
    for (source,_), score in zip(mapped,scores,strict=True):
        best[source] = max(float(score),best.get(source,-1e10))
    return sorted(best.items(),key=lambda pair:(-pair[1],pair[0]))


def maxima(values):
    return [max(scores) for scores in zip(*values,strict=True)]


def precompute(cases, sources, docs, active_docs, releases, semantic):
    raw = defaultdict(dict)
    costs = defaultdict(dict)
    hashed = defaultdict(set)
    ledger = defaultdict(set)
    hashes = defaultdict(set)
    doc_indexes = {entry:i for i,entry in enumerate(docs)}
    for item in sources:
        hashed[digest(item["text"])].add(item["source_id"])
    for item in releases:
        by_hash = digest(item["text"])
        if item.get("sha256") and item["sha256"] != by_hash:
            raise ValueError(f"Release hash mismatch for {item['release_id']}")
        ledger[by_hash].add(item["source_id"])
        hashes[by_hash].add(item["release_id"])

    bm25 = BM25([d for _,d in docs])
    active_bm = BM25([d for _,d in active_docs])
    if semantic:
        encode, classify = semantic
        begin = time.perf_counter()
        d_vec = encode([d for _,d in docs])
        query_texts = list(dict.fromkeys(chunk for case in cases for chunk in chunks(case["text"])))
        q_vec = dict(zip(query_texts,encode(query_texts,query=True),strict=True))
        prep_seconds = time.perf_counter()-begin
        query_seconds = prep_seconds/max(1,len(cases))
    else:
        prep_seconds = 0

    # Hold raw vectors and the model between samples. Endpoint text is the only query input.
    for case in cases:
        case_id, text = case["case_id"], case["text"]
        segments = chunks(text)
        for method,index,query_keys in (("sha256",hashed,[text]),("issuance_lookup",ledger,[text,*segments])):
            begin = time.perf_counter()
            found = set().union(*(index[digest(part)] for part in query_keys))
            raw[method][case_id] = [(source,1.0) for source in sorted(found)]
            costs[method][case_id] = time.perf_counter()-begin
        if not segments:
            for method in ("minhash","bm25","bge","bge_rerank","active_variants"):
                raw[method][case_id] = []
                costs[method][case_id] = 0
            continue
        for method,mapped,scorer in (
            ("minhash",docs,lambda q: [minhash_score(q,d) for _,d in docs]),
            ("bm25",docs,bm25.scores),
            ("active_variants",active_docs,active_bm.scores),
        ):
            begin = time.perf_counter()
            raw[method][case_id] = rank(mapped,maxima([scorer(part) for part in segments]))
            costs[method][case_id] = time.perf_counter()-begin
        if semantic:
            begin = time.perf_counter()
            similarities = d_vec @ q_vec[segments[0]]
            for part in segments[1:]:
                import numpy as np
                similarities = np.maximum(similarities,d_vec @ q_vec[part])
            raw["bge"][case_id] = rank(docs,similarities)
            costs["bge"][case_id] = time.perf_counter()-begin+query_seconds
    if semantic:
        pairs, indexes = [], []
        for case in cases:
            case_id = case["case_id"]
            segments = chunks(case["text"])
            if not segments:
                continue
            for source,_ in raw["bge"][case_id][:8]:
                nearby = [doc for sid,doc in docs if sid==source]
                for part in segments[:12]:
                    part_vec = q_vec[part]
                    pivot = max(nearby,key=lambda d: float(d_vec[doc_indexes[(source,d)]] @ part_vec))
                    pairs.append((part,pivot))
                    indexes.append((case_id,source))
        begin = time.perf_counter()
        unique_pairs = list(dict.fromkeys(pairs))
        scores = dict(zip(unique_pairs,classify(unique_pairs),strict=True))
        result = [scores[pair] for pair in pairs]
        by_case = defaultdict(dict)
        for (case_id,source),score in zip(indexes,result,strict=True):
            by_case[case_id][source] = max(score,by_case[case_id].get(source,0.0))
        rerank_seconds = time.perf_counter()-begin
        for case in cases:
            case_id = case["case_id"]
            raw["bge_rerank"][case_id] = sorted(by_case[case_id].items(),key=lambda x:(-x[1],x[0]))
            costs["bge_rerank"][case_id] = costs["bge"][case_id]+rerank_seconds*sum(
                1 for cid,_ in indexes if cid==case_id)/max(1,len(indexes))
    return raw,costs,hashes,prep_seconds


def evaluate(rows, cases):
    source = Counter()
    release = Counter()
    multi_correct = multi_total = release_exact = release_known = empty_wrong = 0
    true_candidate_hits = true_candidate_count = candidate_width = 0
    for row in rows:
        case = cases[row["case_id"]]
        truth = retained(case)
        predicted = set(row["source_ids"])
        source.update(tp=len(truth & predicted), fp=len(predicted-truth), fn=len(truth-predicted))
        rt = set(case["retained_release_ids"])
        rp = set(row["release_ids"])
        candidates = set(row["candidate_release_ids"])
        true_candidate_hits += len(rt & candidates)
        true_candidate_count += len(rt)
        candidate_width += len(candidates)
        release.update(tp=len(rt & rp),fp=len(rp-rt),fn=len(rt-rp))
        if len(truth)>=2:
            multi_total += 1
            multi_correct += predicted==truth
        if rt:
            release_known += 1
            release_exact += rt == rp
        if not truth:
            empty_wrong += bool(predicted)

    def metrics(c):
        return dict(c,precision=c["tp"]/max(1,c["tp"]+c["fp"]),
                    recall=c["tp"]/max(1,c["tp"]+c["fn"]),
                    f1=2*c["tp"]/max(1,2*c["tp"]+c["fp"]+c["fn"]))

    return dict(source=metrics(source), release=metrics(release), n=len(rows),
                multi_exact=multi_correct/max(1,multi_total),multi_n=multi_total,
                release_exact=release_exact/max(1,release_known),release_n=release_known,
                release_candidate_recall=true_candidate_hits/max(1,true_candidate_count),
                release_candidate_width_mean=candidate_width/max(1,len(rows)),
                false_attribution=source["fp"]/max(1,source["tp"]+source["fp"]),
                null_false_positive_cases=empty_wrong,
                null_cases=sum(not retained(cases[row["case_id"]]) for row in rows),
                mean_seconds=statistics.mean(row["seconds"] for row in rows) if rows else 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--bge",type=Path)
    parser.add_argument("--rerank",type=Path)
    parser.add_argument("--threads",type=int,default=3)
    args = parser.parse_args()
    files = {name:args.data / name for name in ("sources.json","releases.json","cases.jsonl")}
    sources = json.loads(files["sources.json"].read_bytes())
    releases = json.loads(files["releases.json"].read_bytes())
    cases = jsonl(files["cases.jsonl"])
    docs = list(dict.fromkeys((s["source_id"],text) for s in sources
                              for text in chunks(s["text"])))
    active_docs = list(dict.fromkeys([*docs,*[(s["source_id"],text) for s in sources
                                            for text in variants(s["text"])]]))
    args.out.mkdir(parents=True,exist_ok=True)
    config = {
        "data_sha256":{name:file_sha(path) for name,path in files.items()},
        "source_documents":len(sources),"indexed_passages":len(docs),"active_index_passages":len(active_docs),
        "feature_split":"input-release lineage group, SHA-256 modulo 4 if no common split supplied",
        "cpu_threads":args.threads,"gpu_hours":0,
        "bge_revision": BGE_REV,
        "reranker":RERANK_REPO,"rerank_revision":RERANK_REV,
        "minhash":{"shingle_words":3,"permutations":PERMUTATIONS},
        "bm25":{"k1":1.5,"b":.75,"normalized_by_query_idf":True},
        "active_variants":"Adds proactively registered source excerpts, sentence reordering and abbreviation variants to BM25 passage index.",
        "issuance_policy":"Exact release text and exact text segments with all ambiguous release IDs logged. Unique issuer returned only for a compatible singleton via a text hash. No ledger metadata leaks into match selection.",
        "calibration":"Dev micro-F1 for thresholds in the source task. Fixed scope max three source predictions. No test retained set, requested fusion count or attack type read by ranking.",
    }
    semantic = None
    if args.bge and args.rerank:
        config["model_sha256"] = {"bge":file_sha(args.bge/"model.safetensors"),
                                  "rerank":file_sha(args.rerank/"model.safetensors")}
        semantic = load_semantic(args.bge,args.rerank,args.threads)
    start = time.perf_counter()
    raw, costs, hashes, preprocessing = precompute(cases,sources,docs,active_docs,releases,semantic)
    config["semantic_embedding_preprocessing_seconds"] = preprocessing
    config["ranking_elapsed_seconds"] = time.perf_counter()-start
    partition = evaluation_partition(cases)
    by_release = {item["release_id"]:item for item in releases}
    by_case = {case["case_id"]:case for case in cases}
    rows = []
    summary = {}
    for method in METHODS:
        if method not in raw:
            continue
        options = choose_config(raw[method],cases,partition,method)
        config[method] = options
        subset = []
        for case in cases:
            begin = time.perf_counter()
            case_id = case["case_id"]
            ranked = raw[method][case_id]
            out = select(ranked,options["threshold"],options["margin"])
            raw_release_ids = set().union(*(hashes[digest(chunk)] for chunk in [case["text"],*chunks(case["text"])]))
            compatible = sorted(item["release_id"] for item in releases if item["source_id"] in out)
            compatible_exact = sorted(rid for rid in raw_release_ids if by_release[rid]["source_id"] in out)
            unique_ids = []
            for source in out:
                candidates = [rid for rid in compatible_exact if by_release[rid]["source_id"]==source]
                if len(candidates)==1:
                    unique_ids.extend(candidates)
            subset.append(dict(case_id=case_id,method=method,split=partition[case_id],source_ids=out,
                               release_ids=unique_ids, issuer_ids=sorted({by_release[rid]["issuer_id"] for rid in unique_ids}),
                               candidate_release_ids=compatible, exact_candidate_release_ids=compatible_exact,
                               ranked_sources=[{"source_id":source,"score":score} for source,score in ranked],
                               seconds=costs[method][case_id]+time.perf_counter()-begin))
        tests = [row for row in subset if row["split"]=="test"]
        summary[method] = {"dev":evaluate([row for row in subset if row["split"]=="dev"],by_case),
                           "test":evaluate(tests,by_case),
                           "by_depth":{depth:evaluate([r for r in tests if by_case[r["case_id"]]["depth"]==depth],by_case)
                                       for depth in sorted({case["depth"] for case in cases})},
                           "by_transform":{condition:evaluate(
                               [r for r in tests if by_case[r["case_id"]]["transform"]==condition],by_case)
                               for condition in sorted({case["transform"] for case in cases})}}
        rows.extend(subset)
        print(method,summary[method]["test"]["source"],summary[method]["test"]["release_exact"],flush=True)
    with (args.out/"predictions.jsonl").open("w",encoding="utf8") as stream:
        for row in rows:
            stream.write(json.dumps(row,ensure_ascii=False)+"\n")
    save_json(args.out/"configuration.json",config)
    save_json(args.out/"summary.json",summary)


if __name__ == "__main__":
    main()
