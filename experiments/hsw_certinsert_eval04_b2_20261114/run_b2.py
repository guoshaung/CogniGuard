"""Execute the B2 development sequence after the preregistration commit."""
import argparse
import csv
import hashlib
import json
import math
import pickle
import subprocess
import sys
import time
from collections import Counter
from functools import lru_cache

import numpy as np

import b2_core as b


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inputs():
    lock = b.load(b.FREEZE)
    assert file_hash(b.HERE / "B2_PREREG.md") == lock["prereg_sha256"]
    for path, expected in lock["files_sha256"].items():
        assert file_hash(b.ROOT / path) == expected, path
    keybytes = (b.OUT / "private_keys.bin").read_bytes()
    keys = [keybytes[i:i+32] for i in range(0, len(keybytes), 32)]
    assert len(keys) == 1001 and len(set(keys)) == 1001
    assert b.sha(keys[0]) == lock["key_commitments"]["dev_sha256"]
    assert [b.sha(key) for key in keys[1:]] == lock["key_commitments"]["calibration_sha256"]
    corpus = b.load(b.STAGE / "R_CORPUS.json")
    assert len(corpus) == 4461
    chosen = [r for r in corpus if r["split"] == "calib" or r["kind"] == "generated"]
    assert sum(r["split"] == "calib" for r in chosen) == 893
    assert sum(r["kind"] == "generated" for r in chosen) == 300
    connectives = {r["text"] for r in b.load(b.STAGE / "ATTESTED_CANDIDATES.json")}
    pdtb = set(b.load(b.OUT / "pdtb100.json"))
    assert len(connectives) == 47 and len(pdtb) == 100
    return lock, keys, chosen, (connectives | pdtb) - set(b.FRAMES)


def parse_corpus(rows, connectives):
    cache = b.OUT / "plans.local.pickle"
    if cache.exists():
        with cache.open("rb") as f:
            return pickle.load(f)
    plans = {}
    from e1_detector import word_count
    texts = [b.masked(row["text"]) for row in rows]
    for row, parsed in zip(rows, b.nlp.pipe(texts, batch_size=16), strict=True):
        p = b.plan(row["text"], row.get("question", ""), connectives, parsed)
        p["words"] = word_count(p["body"]) if row["kind"] == "generated" else None
        p["kind"] = row["kind"]
        p["split"] = row["split"]
        plans[row["id"]] = p
    with cache.open("xb") as f:
        pickle.dump(plans, f)
    return plans


def counts(k, n):
    return {"k": int(k), "n": int(n)}


def calibration(plans, keys):
    selected = {key:p for key,p in plans.items() if p["split"] == "calib"}
    signatures = sorted({slot["signature"] for p in selected.values() for slot in p["slots"]})
    signature_index = {sig:index for index,sig in enumerate(signatures)}
    cutoffs = [gamma*(1<<256) for gamma in b.GAMMAS]
    marks = np.empty((len(keys), len(signatures), len(cutoffs)), dtype=np.bool_)
    for i, key in enumerate(keys):
        for j, signature in enumerate(signatures):
            value = b.mark_int(key, signature)*100
            marks[i,j] = [value < cutoff for cutoff in cutoffs]
    results = {}
    with (b.HERE/"calibration_by_doc.csv").open("x", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["id","gamma","mode","S","N","duplicate_slot_fraction","keys","not_testable",
                         "marked_frame_units","frame_units_times_keys","fp_001","fp_01","fp_05"])
        for gindex, gamma in enumerate(b.GAMMAS):
            results[str(gamma)] = {}
            for mode in ("signature","slot"):
                ps = []
                not_testable, hits, opportunities = 0,0,0
                for key,p in selected.items():
                    slots = p["slots"]
                    group = b.units(slots)
                    duplicates = (len(slots)-len(group))/len(slots) if slots else 0
                    if mode == "signature":
                        item = [(sig,any(s["frame"] for s in ss)) for sig,ss in group.items()]
                    else:
                        item = [(s["signature"],bool(s["frame"])) for s in slots]
                    si = [signature_index[sig] for sig,_ in item]
                    hi = [signature_index[sig] for sig,hit in item if hit]
                    s,n = len(si),len(hi)
                    m = marks[:,si,gindex].sum(axis=1)
                    x = marks[:,hi,gindex].sum(axis=1)
                    pv = np.array([b.pvalue(s,int(mv),n,int(xv)) for mv,xv in zip(m,x,strict=True)])
                    ps.extend(pv)
                    skipped = int((m==0).sum()) if n else len(keys)
                    fp = [int((pv < alpha).sum()) for alpha in (.001,.01,.05)]
                    not_testable += skipped
                    hits += int(x.sum())
                    opportunities += n*len(keys)
                    writer.writerow([key,gamma,mode,s,n,duplicates,len(keys),skipped,int(x.sum()),n*len(keys),*fp])
                pv = np.sort(ps)
                results[str(gamma)][mode] = {
                    "not_testable":counts(not_testable,len(pv)),
                    "marked_frame_fraction":counts(hits,opportunities),
                    "false_positive":{str(alpha):counts((pv<alpha).sum(),len(pv)) for alpha in (.001,.01,.05)},
                    "qq":[{"quantile":i/1000,
                           "observed":float(pv[max(0,math.ceil(i*len(pv)/1000)-1)])}
                          for i in range(1001)],
                }
    b.save("calibration.json",results)
    print("CPU calibration complete",flush=True)
    return results


class Scoring:
    def __init__(self, lock):
        self.lock = lock
        self.model = None
        self.started = time.monotonic()
        self.cache = {}
        self.total_tokens = 0
        self.stderr = None

    def command(self, operation, texts):
        assert self.model is not None
        self.model.stdin.write(json.dumps({"operation":operation,"texts":texts})+"\n")
        self.model.stdin.flush()
        reply = self.model.stdout.readline()
        if not reply:
            raise RuntimeError(f"FROZEN_SCORER_PROCESS_EXIT_{self.model.poll()}")
        data = json.loads(reply)
        if "error" in data:
            raise RuntimeError(f"FROZEN_SCORER_{data['error']}")
        return data["result"]

    def get(self, texts, document_started, used):
        if self.model is None:
            free = int(subprocess.check_output(
                ["nvidia-smi","--query-gpu=memory.free","--format=csv,noheader,nounits"],text=True
            ).splitlines()[0])
            if free<3500:
                raise RuntimeError("FROZEN_GPU_MEMORY_ADMISSION")
            model = b.PRIMARY / self.lock["model_path_relative_to_primary"]
            assert file_hash(model) == self.lock["model_sha256"]
            self.stderr = (b.OUT/"scorer_native.stderr.log").open("x",encoding="utf-8")
            self.model = subprocess.Popen(
                [sys.executable,"-S","-B","-u",str(b.HERE/"score_worker.py"),
                 str(b.ROOT),str(b.SCORER_RUNTIME),str(model)],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,
                encoding="utf-8",creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),
            )
            ready = self.model.stdout.readline()
            if not ready or not json.loads(ready).get("ready"):
                raise RuntimeError(f"FROZEN_SCORER_PROCESS_EXIT_{self.model.poll()}")
            self.prefix_tokens = json.loads(ready)["prefix_tokens"]
        missing = list(dict.fromkeys(text for text in texts if text not in self.cache))
        for i in range(0,len(missing),4):
            batch = missing[i:i+4]
            if time.monotonic()-self.started>=7200 or time.monotonic()-document_started>=300:
                raise TimeoutError("FROZEN_SCORING_TIME_LIMIT")
            lens = [n+self.prefix_tokens for n in self.command("tokenize",batch)]
            if max(lens)>1024:
                raise ValueError("FROZEN_CONTEXT_LIMIT_NO_TRUNCATION")
            if used[0]+sum(lens)>250000:
                raise TimeoutError("FROZEN_TOKEN_LIMIT")
            for t,res in zip(batch,self.command("score",batch),strict=True):
                assert math.isfinite(res["log_probability"])
                self.cache[t] = res["log_probability"]
                used[0] += res["input_tokens"]
                self.total_tokens += res["input_tokens"]
        return [self.cache[t] for t in texts]

    def close(self):
        if self.model and self.model.poll() is None:
            self.model.stdin.write('{"operation":"stop"}\n')
            self.model.stdin.close()
            try:
                self.model.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.model.terminate()
                self.model.wait(timeout=15)
        if self.stderr:
            self.stderr.close()


def watermarked(p, key, gamma, used, chosen, connectives, ensure=True):
    if ensure:
        text, spans, changes, raw = b.assemble(p, chosen)
    else:
        text = b.insert_plain(p, chosen)
        spans,changes,raw = [],[],None
    check = b.detect(b.plan(text, p["question"], connectives),key,gamma) if chosen else used
    return text,spans,changes,raw,check


def embed(p, key, gamma, cap, scoring, connectives):
    start = time.monotonic()
    counter = {f:b.count_frame(p["text"], f) for f in b.FRAMES}
    maximum = (cap+1)//2
    original = b.detect(p,key,gamma)
    if original["p"]<.001:
        return {"status":"NATURAL_POSITIVE","source_p":original["p"],"insertions":0,"tokens":0}, None
    if any(n>maximum for n in counter.values()):
        return {"status":"NATURAL_FRAME_CAP_EXCEEDED","source_p":original["p"],"insertions":0,"tokens":0}, None
    slots = []
    for sig, group in b.units(p["slots"]).items():
        if any(s["frame"] for s in group):
            continue
        s = group[0]
        if b.compatible_insert(p,s) and b.is_marked(b.mark_int(key,sig),gamma):
            slots.append(s)
    chosen = []
    used = [0]
    status = "INSUFFICIENT_MARKED_SLOTS"
    check = original
    step_rows = []
    try:
        while len(chosen)<cap:
            options = [b.candidate(p,s,f) for s in slots
                       if all(abs(s["word_index"]-other["word_index"])>=8 for other in chosen)
                       for f in b.FRAMES if counter[f]<maximum]
            if not options:
                break
            pairs = [b.context_pair(p,chosen,c) for c in options]
            scores = scoring.get([x for a,z,_ in pairs for x in (a,z)],start,used)
            i = min(range(len(options)),key=lambda i:(scores[2*i]-scores[2*i+1],
                                                     options[i]["offset"],options[i]["word"]))
            best = options[i]
            chosen.append(best)
            counter[best["word"]] += 1
            text,spans,changes,raw,check = watermarked(p,key,gamma,original,chosen,connectives)
            step_rows.append({"p":check["p"],"delta_log_probability":scores[2*i+1]-scores[2*i]})
            if check["p"]<.001:
                assert all(b.count_frame(text,f)<=maximum for f in b.FRAMES)
                return ({"status":"WATERMARKED","source_p":original["p"],"posted_p":check["p"],
                        "insertions":len(chosen),"max_frame_repeat":max(counter.values()),
                        "restore_ok":True,"tokens":used[0],"steps":step_rows},
                       {"text":text,"spans":spans,"changes":changes,"raw_inverse":raw})
            status = "TARGET_NOT_REACHED"
    except (RuntimeError, TimeoutError, ValueError) as error:
        status = type(error).__name__+":"+str(error)
        if (status.startswith(("RuntimeError:FROZEN_SCORER_PROCESS",
                               "RuntimeError:FROZEN_GPU_MEMORY_ADMISSION")) or scoring.model is None):
            raise
    return {"status":status,"source_p":original["p"],"insertions":0,"attempted":len(chosen),
            "last_trial_p":check["p"],"tokens":used[0],"steps":step_rows},None


def order(seed, label, ident):
    return hashlib.sha256(f"{seed}|{label}|{ident}".encode()).digest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=("calibration","embed"))
    args=parser.parse_args()
    b.selftest()
    lock,keys,rows,connectives = inputs()
    plans = parse_corpus(rows,connectives)
    if args.stage=="calibration":
        calibration(plans,keys[1:])
        return
    assert (b.OUT/"calibration.json").exists()
    scoring=Scoring(lock)
    generated=sorted((i for i,p in plans.items() if p["kind"]=="generated"),
                     key=lambda i:order(lock["seed"],"generation",i))
    outputs={}
    try:
        with (b.OUT/"embedding.local.jsonl").open("x",encoding="utf-8") as f:
            for i,ident in enumerate(generated,1):
                p=plans[ident]
                scoring.cache.clear()
                for gamma in b.GAMMAS:
                    for cap in b.BUDGETS:
                        row,text=embed(p,keys[0],gamma,cap,scoring,connectives)
                        row.update(id=ident,gamma=gamma,m_max=cap,words=p["words"])
                        f.write(json.dumps(row,ensure_ascii=False)+"\n")
                        f.flush()
                        if text:
                            outputs[(gamma,cap,ident)]=text
                if i%25==0: print("embedded",i,"/",len(generated),"tokens",scoring.total_tokens,"success",len(outputs),flush=True)
    finally:
        scoring.close()
    with (b.OUT/"watermarked.local.pickle").open("xb") as f:
        pickle.dump(outputs,f)
    b.save("embedding_run.json",{"forward_tokens":scoring.total_tokens,
                                "seconds":time.monotonic()-scoring.started,"watermarked":len(outputs)})


if __name__=="__main__":
    main()
