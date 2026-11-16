"""Score full text, variants, source attribution and the frozen P1 suite."""
import argparse
import collections
import csv
import json
import math
import sys

import numpy as np
from tokenizers import Tokenizer

from stage_c_embed import ARMS, B, C, HERE, OUT, ROOT, m
from t6_sources import load, sha, write

OLD=ROOT/"var/results/hsw-st/english_replication_20261110_01/e1_guarded"
LEGACY=ROOT/"var/results/hsw-st/certinsert_eval_20261111_01/run01"
DATA=ROOT/"var/results/hsw-st/certinsert_eval03_lite_20261112/run01/batch02_adjusted/data"
CPU=OUT/"cpu_controls"
sys.path.insert(0,str(m.PRIMARY/"var/results/hsw_gpu0_deploy_20261102_r21"))
SCORE_OUT=OUT/"scores"
SCORE_OUT.mkdir(exist_ok=True)
CROPS=((100,"first"),(100,"middle"),(100,"last"),(200,"first"),(200,"middle"))


def read_text(path,digest=None):
    data=path.read_bytes()
    if digest:assert sha(data)==digest,path.name
    return data.decode()


class Fingerprint:
    def __init__(self, sources):
        reference=OLD/"attack_three_seed_round01"
        parameters=load(reference/"FINGERPRINT_FREEZE.json")
        self.prime=parameters["prime"]
        rng=np.random.default_rng(parameters["seed"])
        assert parameters["num_perm"]==128
        self.a=rng.integers(1,self.prime,128,dtype=np.uint64)
        self.b=rng.integers(0,self.prime,128,dtype=np.uint64)
        historical=load(reference/"FINGERPRINT_CORPUS.json")
        corpus={x["id"]:x["text"] for x in historical}
        assert not corpus.keys()&sources.keys()
        corpus.update(sources)
        self.reference_count=len(corpus)
        self.ids=[]
        signatures=[]
        for ident,text in corpus.items():
            sig=self.signature(text)
            if sig is not None:
                self.ids.append(ident)
                signatures.append(sig)
        self.matrix=np.stack(signatures)

    def signature(self,text):
        facts=m.anchors(text)
        if not facts:
            return None
        values=np.array([int.from_bytes(bytes.fromhex(sha(f.encode())[:8]),"little")%self.prime
                         for f in facts],dtype=np.uint64)
        return ((self.a[:,None]*values+self.b[:,None])%self.prime).min(1)

    def identify(self,text,ident):
        signature=self.signature(text)
        if signature is None:
            return {"fingerprint_status":"REJECT","fingerprint_similarity":0.}
        similarity=(self.matrix==signature).mean(1)
        best=float(similarity.max())
        winners=np.flatnonzero(similarity==best)
        state=("REJECT" if best==0 else "AMBIGUOUS" if len(winners)>1 else
               "CORRECT" if self.ids[winners[0]]==ident else "WRONG")
        return {"fingerprint_status":state,"fingerprint_similarity":best}


class Detector:
    def __init__(self, include_baselines=True):
        self.det=m.SentenceDetector()
        assert sha(self.det.key)==load(m.HERE/"M_FREEZE.json")["secret_commitment_sha256"]
        self.rc=self.det.select("")
        self.post=None
        self.baselines=include_baselines
        self.cache={}
        if not include_baselines:
            return
        from kgw_ref.kgw import Greenlist

        masked=load(LEGACY/"PUBLIC_TOKENIZER_VALIDATION.json")
        assert m.digest(m.Path(masked["path"]))==masked["sha256"]
        self.tokenizer=Tokenizer.from_file(masked["path"])
        self.key=(OLD/"frozen_comparison09/restricted/kgw_key.txt").read_text(encoding="utf-8")
        self.kgw=Greenlist(self.key,cache_size=64)
        self.mask=set(load(LEGACY/"restricted/UNIGRAM_GREEN.json"))

    def get_postmark(self):
        if self.post is None:
            from t6_postmark import PostMark, assets, P
            gate=load(HERE/"T6_POSTMARK_GATE.json")
            assert m.digest(P/"CALIBRATION.json")==gate["calibration_sha256"]
            self.post=PostMark(assets())
            self.post_threshold=gate["threshold"]
        return self.post

    def score(self,text,method):
        cache=(method,sha(text.encode()))
        if cache in self.cache:
            return dict(self.cache[cache])
        row={"scorable":True,"detected":None}
        if method in ARMS or method=="RC":
            p=self.det.p(text,self.rc if method=="RC" else None)
            row.update(p=p,detected=p<.01)
        elif method in ("KGW","Unigram"):
            ids=self.tokenizer.encode(text,add_special_tokens=False).ids
            if method=="KGW":
                n=max(0,len(ids)-4)
                k=0
                for i in range(4,len(ids)):
                    indices=self.kgw.indices(ids[i-4:i])
                    j=int(np.searchsorted(indices,ids[i]))
                    k+=int(j<len(indices) and indices[j]==ids[i])
                gamma=.25
            else:
                n=len(ids)
                k=sum(t in self.mask for t in ids)
                gamma=.5
            z=(k-gamma*n)/math.sqrt(gamma*(1-gamma)*n) if n else None
            row.update(z=z,token_denominator=n,token_hits=k,detected=(z>(3 if method=="KGW" else 4)) if z is not None else None,
                       scorable=z is not None)
        elif method=="PostMark":
            value=self.get_postmark().score(text)
            row.update(score=value,detected=value>self.post_threshold if value is not None else None,scorable=value is not None)
        elif method=="Fingerprint":
            row["detected"]=None
        else:
            raise KeyError(method)
        self.cache[cache]=dict(row)
        return row


def crop(text, length, position):
    words=list(m.WORDS.finditer(text))
    if len(words)<length:
        return None
    at={"first":0,"middle":(len(words)-length)//2,"last":len(words)-length}[position]
    return text[words[at].start():words[at+length-1].end()]


def variants(registry,detector,compressions=True):
    input_=load(B/"RESULT.json")["rows"]
    sources={r["id"]:read_text(B/"outputs"/(r["id"]+".txt"),r["output_sha256"])
             for r in input_ if r["status"]=="COMPLETED" and r["format_pass"]}
    originals={case:{"n":set(m.numbers(text)),"f":set(m.forms(text)),"w":len(m.WORDS.findall(text))}
               for case,text in sources.items()}
    fp=Fingerprint(sources)
    found=[]
    passing=[]
    for i,r in enumerate(registry,1):
        text=read_text(ROOT/r["path"],r["sha256"])
        rid=r["record_id"]
        conditions={"none":text}
        if compressions:
            for width,position in CROPS:
                conditions[f"crop_{position}{width}"]=crop(text,width,position)
            ocr=OUT/"ocr/records"/(rid+".json")
            comp=OUT/"stage_d_model_arms/compress/records"/(rid+"__compress70.json")
            for label,record,root in (
                ("ocr",ocr,OUT/"ocr/texts"/(rid+".txt")),
                ("compress70",comp,OUT/"stage_d_model_arms/compress/outputs"/(rid+"__compress70.txt")),
            ):
                if record.exists() and (v:=load(record))["status"]=="COMPLETED":
                    conditions[label]=read_text(root,v["output_sha256"])
                else:
                    conditions[label]=None
        for condition,out in conditions.items():
            row={"id":r["id"],"method":r["method"],"record_id":rid,"condition":condition}
            if out is None:
                row.update(scorable=False,status="NOT_APPLICABLE_SHORT" if condition.startswith("crop") else "NOT_RUN_OR_FAILED")
            else:
                row.update(status="SCORED",**detector.score(out,r["method"]),**fp.identify(out,r["id"]))
                ori=originals[r["id"]]
                row["number_formula_intact"]=ori["n"]<=set(m.numbers(out)) and ori["f"]<=set(m.forms(out))
                row["relative_words"]=len(m.WORDS.findall(out))/max(1,ori["w"])
                row["relative_to_parent_words"]=len(m.WORDS.findall(out))/max(1,len(m.WORDS.findall(text)))
                row["text_sha256"]=sha(out.encode())
                if condition=="none" and row.get("detected") is True:
                    passing.append(rid)
            found.append(row)
        if i%50==0:
            print("variant metrics",i,len(registry),flush=True)
    return found,passing,{"index_entries":len(fp.ids),"index_planned":fp.reference_count}


def false_positives(det):
    historical=load(DATA/"P6_BACKGROUND.json")
    generated=load(B/"RESULT.json")["rows"]
    found=[]
    methods=["KGW","Unigram"]
    if (HERE/"T6_POSTMARK_GATE.json").exists():
        methods.append("PostMark")
    for name,items in (("EVAL03_in_domain",historical),("T6_source",generated)):
        for i,r in enumerate(items,1):
            text=r["text"] if name=="EVAL03_in_domain" else read_text(B/"outputs"/(r["id"]+".txt"),r["output_sha256"])
            for method in methods:
                found.append(dict(id=r["id"],dataset=name,method=method,**det.score(text,method)))
            if i%100==0:print("fixed baseline FPR",name,i,len(items),flush=True)
    return found


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage",choices=("public_gate","variants","frequency","baseline_fpr"))
    p.add_argument("--primary",action="store_true")
    args=p.parse_args()
    stem="primary" if args.primary else "all"
    registry=OUT/("score_registry_primary.json" if args.primary else "score_registry.json")
    freeze=load(HERE/("T6_PRIMARY_VARIANT_FREEZE.json" if args.primary else "T6_VARIANT_FREEZE.json"))
    assert sha(registry.read_bytes())==freeze["registry_sha256"]
    det=Detector(include_baselines=not args.primary)
    if args.stage=="baseline_fpr":
        write(SCORE_OUT/"baseline_fpr.json",{"rows":false_positives(det)})
        return
    if args.stage=="frequency":
        fld=OUT/"frequency"/stem
        man=load(fld/"manifest.json")
        lock=load(HERE/("T6_P1_PRIMARY_FREEZE.json" if args.primary else "T6_P1_FREEZE.json"))
        assert sha((fld/"manifest.json").read_bytes())==lock["attack_manifest_sha256"]
        assert sha((fld/"inputs.local.json").read_bytes())==man["inputs_sha256"]
        rows=[]
        for i,r in enumerate(load(fld/"inputs.local.json"),1):
            assert sha(r["text"].encode())==r["sha256"]
            rows.append({**{k:v for k,v in r.items() if k!="text"},**det.score(r["text"],r["method"])})
            if i%200==0:
                print("P1 scores",i,len(rows),flush=True)
        write(SCORE_OUT/(stem+"_frequency.json"),{"conditions":man["conditions"],"rows":rows})
        return
    rows,passing,index=variants(load(registry)["items"],det,compressions=args.stage=="variants")
    if args.stage=="public_gate":
        write(OUT/"baseline_public_gate.json",{"passing":passing,"rows":rows})
    else:
        write(SCORE_OUT/(stem+"_variants.json"),{"index":index,"rows":rows})


if __name__=="__main__":
    main()
