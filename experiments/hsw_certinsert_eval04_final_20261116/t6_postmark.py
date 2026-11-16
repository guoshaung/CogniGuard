"""PostMark@12 with pinned published assets and the local Mistral inserter."""
import argparse
import hashlib
import io
import json
import os
import pickle
import random
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from t6_sources import HERE, OUT, ROOT, load, rank, sha, write
from t6_model_arms import Server, file_hash
from t6_generate import MODEL as MISTRAL, SERVER

P=OUT/"postmark"
ASSETS=OUT/"postmark_reference"
EMBED=ROOT/"assets/models/hsw-t6-postmark-nomic"
TEMPLATE=ASSETS/"insert.txt"
STOP={"stop","length"}


def torch_storage(raw):
    return torch.load(io.BytesIO(raw),map_location="cpu",weights_only=True)


class DataOnly(pickle.Unpickler):
    """The released data files use torch tensors and NumPy arrays."""
    def find_class(self,module,name):
        if (module,name)==("torch.storage","_load_from_bytes"):
            return torch_storage
        allowed={
            ("collections","OrderedDict"),("numpy","ndarray"),("numpy","dtype"),
            ("numpy.core.multiarray","_reconstruct"),("numpy.core.multiarray","scalar"),
            ("torch._utils","_rebuild_tensor_v2"),("torch._utils","_rebuild_tensor"),
        }
        if (module,name) in allowed:
            return super().find_class(module,name)
        raise pickle.UnpicklingError(f"Unsupported published data type {module}.{name}")


def data_file(path):
    with path.open("rb") as f:
        return DataOnly(f).load()


class PostMark:
    def __init__(self,freeze):
        import spacy

        os.environ.update(HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1")
        torch.set_num_threads(2)
        self.doc=spacy.load("en_core_web_sm")
        self.tok=AutoTokenizer.from_pretrained(EMBED/"bert_tokenizer",local_files_only=True)
        config=load(EMBED/"config.json")
        adapted=P/"model_config"
        adapted.mkdir(exist_ok=True)
        for name in ("model.safetensors","configuration_hf_nomic_bert.py","modeling_hf_nomic_bert.py"):
            dest=adapted/name
            if not dest.exists():
                try:os.link(EMBED/name,dest)
                except OSError:
                    from shutil import copy2
                    copy2(EMBED/name,dest)
            assert file_hash(dest)==file_hash(EMBED/name)
        config["auto_map"]={name:value.split("--",1)[-1] for name,value in config["auto_map"].items()}
        config_path=adapted/"config.json"
        if not config_path.exists():
            write(config_path,config)
        assert load(config_path)==config
        self.model=AutoModel.from_pretrained(adapted,trust_remote_code=True,local_files_only=True).eval()
        self.names=data_file(ASSETS/"valid_wtmk_words_in_wiki_base-only-f1000.pkl")
        reference=data_file(ASSETS/"filtered_data_100k_unique_250w_sentbound_nomic_embs.pkl")
        rng=random.Random(freeze["table_seed"])
        indices=rng.sample(range(len(reference)),len(self.names))
        rng.shuffle(indices)
        self.table=torch.nn.functional.normalize(
            torch.stack([torch.as_tensor(reference[i],dtype=torch.float32) for i in indices]),dim=1)
        del reference
        self.dict=load(ASSETS/"paragram_xxl_words.json")
        self.paragram=torch.as_tensor(data_file(ASSETS/"paragram_xxl.pkl"),dtype=torch.float32)
        self.cache={}

    def embed(self,texts):
        batch=self.tok(texts,padding=True,truncation=True,max_length=512,return_tensors="pt")
        with torch.inference_mode():
            h=self.model(**batch)[0]
            mask=batch["attention_mask"].unsqueeze(-1)
            h=(h*mask).sum(1)/mask.sum(1).clamp(min=1)
            return torch.nn.functional.normalize(h,dim=1)

    def terms(self,text):
        k=int(len(text.split())*.12)
        if not k:
            return []
        document=self.embed([text])[0]
        nearest=(self.table@document).topk(min(3*k,len(self.names))).indices.tolist()
        candidates=[self.names[i] for i in nearest]
        vectors=torch.cat([self.embed(candidates[i:i+48]) for i in range(0,len(candidates),48)])
        ranking=(vectors@document).topk(min(k,len(candidates))).indices.tolist()
        return sorted({candidates[i].lower() for i in ranking})

    def vectors(self,words):
        dim=self.paragram.shape[1]
        matrix=torch.zeros((len(words),dim),dtype=torch.float32)
        rows=[];ids=[]
        for i,w in enumerate(words):
            if w in self.dict:
                rows.append(i);ids.append(self.dict[w])
        if rows:
            matrix[rows]=self.paragram[ids]
        return torch.nn.functional.normalize(matrix,dim=1)

    def score(self,text):
        digest=sha(text.encode())
        if digest in self.cache:
            return self.cache[digest]
        keys=self.terms(text)
        words=[t.text.lower() for t in self.doc(text) if not t.is_punct and not t.is_space]
        if not keys or not words:
            value=None
        else:
            best=(self.vectors(keys)@self.vectors(list(dict.fromkeys(words))).T).max(1).values.tolist()
            found=set(words)
            value=sum(w in found or score>=.7 for w,score in zip(keys,best,strict=True))/len(keys)
        self.cache[digest]=value
        return value


def assets():
    f=load(HERE/"T6_POSTMARK_FREEZE.json")
    for name,h in f["files_sha256"].items():
        assert file_hash(ROOT/name)==h,name
    return f


def calibration(det):
    from t6_sources import STAGE
    docs=[p for p in load(STAGE/"R_CORPUS.json") if p["split"]=="calib"]
    assert len(docs)==893
    vals=[]
    for i,p in enumerate(docs,1):
        vals.append({"id":p["id"],"score":det.score(p["text"])})
        if i%100==0:print("PostMark calibration",i,893,flush=True)
    numeric=sorted(r["score"] for r in vals if r["score"] is not None)
    assert numeric
    threshold=numeric[len(numeric)-1-len(numeric)//100]
    k=sum(v>threshold for v in numeric)
    assert k*100<=len(numeric)
    write(P/"CALIBRATION.json",{"items":vals,"threshold":threshold,"empirical_fp":k,"scorable":len(numeric)})


def process(det,server,task,text,threshold):
    ident=task["id"]
    file=P/"records"/(ident+".json")
    started=P/"records"/(ident+".attempt.json")
    if file.exists():
        return load(file)
    if started.exists():
        return {"id":ident,"status":"INCOMPLETE_PREVIOUS_ATTEMPT"}
    write(started,{"id":ident,"input_sha256":sha(text.encode())})
    row={"id":ident,"status":"FAILED","calls":0}
    try:
        words=det.terms(text)
        result=text
        for start in range(0,len(words),10):
            group=words[start:start+10]
            message=TEMPLATE.read_text(encoding="utf-8").format(result,", ".join(group))
            for trial in range(3):
                seed=int(rank("postmark",f"{ident}|{start}|{trial}")[:8],16)&0x7fffffff
                request={"model":"t6-postmark-mistral","messages":[{"role":"user","content":message}],
                         "max_tokens":600,"temperature":0.,"seed":seed,"stream":False}
                row["calls"]+=1
                reply=server.request("/v1/chat/completions",request,timeout=300)["choices"][0]
                assert reply["finish_reason"] in STOP
                result=reply["message"]["content"]
                if sum(w in result.lower() for w in group)/len(group)>=.5:
                    break
        (P/"outputs"/(ident+".txt")).write_bytes(result.encode())
        score=det.score(result)
        row.update(status="COMPLETED" if result.strip() else "EMPTY",markers_requested=len(words),
                   score=score,detected=score>threshold if score is not None else None,
                   output_sha256=sha(result.encode()))
    except (OSError,TypeError,ValueError,KeyError,IndexError,AssertionError,RuntimeError) as ex:
        row["error"]=type(ex).__name__
    write(file,row)
    return row


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage",choices=("calibrate","generate"))
    args=p.parse_args()
    P.mkdir(exist_ok=True)
    f=assets()
    det=PostMark(f)
    if args.stage=="calibrate":
        calibration(det)
        return
    cal=load(P/"CALIBRATION.json")
    assert file_hash(P/"CALIBRATION.json")==load(HERE/"T6_POSTMARK_GATE.json")["calibration_sha256"]
    assert file_hash(MISTRAL)==f["mistral_sha256"] and file_hash(SERVER)==f["server_sha256"]
    for d in ("records","outputs"):
        (P/d).mkdir(exist_ok=True)
    path=OUT/"stage_b_generation"
    tasks=load(path/"RESULT.json")["rows"]
    assert len(tasks)==200
    server=Server(MISTRAL,SERVER,P,port=11708,alias="t6-postmark-mistral")
    rows=[]
    try:
        for source in tasks:
            raw=(path/"outputs"/(source["id"]+".txt")).read_bytes()
            assert sha(raw)==source["output_sha256"]
            rows.append(process(det,server,source,raw.decode(),cal["threshold"]))
            print("PostMark locally adapted",len(rows),len(tasks),rows[-1]["status"],flush=True)
    finally:
        server.close()
    write(P/"RESULT.json",{"planned":len(tasks),"rows":rows,"statuses":dict(Counter(r["status"] for r in rows)),
                          "server_stopped":True})


if __name__=="__main__":
    main()
