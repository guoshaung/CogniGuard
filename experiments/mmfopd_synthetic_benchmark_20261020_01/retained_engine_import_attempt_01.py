"""Frozen legacy methods, strict single-factor switches, common real wire budget."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from pathlib import Path
import sys,types,importlib.util,copy,json
import numpy as np
P=Path(__file__).parent;ROOT=P.parents[1];sys.path.insert(0,str(ROOT))
from protection.common.schemas import ProfileRecord,StudentProfile,Task
pkg=types.ModuleType('_synfrozen');pkg.__path__=[str(P/'frozen')];sys.modules['_synfrozen']=pkg
def module(name,file):
    spec=importlib.util.spec_from_file_location('_synfrozen.'+name,P/'frozen'/file);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
orth=module('orthogonal_decoder','orthogonal_decoder.py');att=module('task_attention','task_attention.py');sel=module('profile_selector','profile_selector.py');base=module('baselines','baselines.py')
original=module('original_selector','original_profile_selector.py')
from generator import FIELDS
from truth import PARAMS
from transformers import AutoTokenizer
TOKENIZER=AutoTokenizer.from_pretrained(str(ROOT/'models/qwen2.5-0.5b-instruct-7ae55760'),local_files_only=True)
CONTEXT={}
class CachedSelector(sel.ProfileSelector):
    def score_records(self,profile,task):
        if 'score' not in CONTEXT:CONTEXT['score']=super().score_records(profile,task)
        return list(CONTEXT['score'])
base.ProfileSelector=CachedSelector
oldattention=att.TaskAttentionSelector.compute_attention
def cached_attention(self,task,records):
    key=('attention',self.temperature,self.top_k)
    if key not in CONTEXT:CONTEXT[key]=oldattention(self,task,records)
    return list(CONTEXT[key])
att.TaskAttentionSelector.compute_attention=cached_attention
PRIMARY=list(base.METHODS)+['SafeTaskTopK','RelevanceCostRule']
METHODS=PRIMARY+['MM-no-projection','MM-no-attention','MM-no-bottleneck','MM-no-taskslot']
from protection.student_profile.src.pipeline.run_demo import load_config
CONFIG=load_config(ROOT/'protection/student_profile/configs/default.yaml')
KEYS=list(FIELDS)+[f'history_noise_{j}' for j in range(8)]
PUBN=32+5+8+5;DIM=PUBN+len(KEYS)*3
def config(k,method):
    x=copy.deepcopy(CONFIG);f=x['fopd'];f['top_k_profile_records']=k;f['unit_budget']['max_units']=k
    flags=f.setdefault('components',{});flags.update(use_orthogonal=True,use_task_attention=True,use_bottleneck=True,use_taskslot=True)
    for name,flag in [('MM-no-projection','use_orthogonal'),('MM-no-attention','use_task_attention'),('MM-no-bottleneck','use_bottleneck'),('MM-no-taskslot','use_taskslot')]:
        if method==name:flags[flag]=False
    return x
def begin(public):
    CONTEXT.clear()
    profile=StudentProfile(public['student_id'],{},[ProfileRecord.from_dict(x) for x in public['records']])
    task=Task(public['request_id'],public['student_id'],public['question'],public['knowledge'],public['difficulty'],False)
    return profile,task
def values(profile):
    out={}
    for rec in profile.profile_records:
        key,value=rec.value.split('=',1);assert key==rec.record_id;out[key]=None if value=='NA' else float(value)
    return out
def payload(v,selected):return '\n'.join(k+'='+('NA' if v[k] is None else str(v[k])) for k in sorted(selected))
def release(items,v,k):
    chosen=[];cost=0
    for item in items:
        name=item.record.record_id
        if name in chosen:continue
        if len(chosen)>=k:break
        cost=len(TOKENIZER.encode(payload(v,chosen+[name]),add_special_tokens=False))
        if cost<=96:chosen.append(name)
    wire=payload(v,chosen);n=len(TOKENIZER.encode(wire,add_special_tokens=False));assert len(chosen)<=k and n<=96
    parsed={}
    for line in wire.splitlines():
        key,value=line.split('=',1);parsed[key]=None if value=='NA' else float(value)
    return chosen,wire,n,parsed
def choose(method,profile,task,k):
    cfg=config(k,method)
    if method in base.METHODS:return base.METHODS[method](profile,task,cfg)
    selector=CachedSelector(cfg)
    if method.startswith('MM-'):return selector.select(profile,task)
    scored=[x for x in selector.score_records(profile,task) if x.record.sensitivity<=.7]
    if method=='SafeTaskTopK':return sorted(scored,key=lambda x:(-x.components['rel'],-x.components['tag'],x.record.record_id))
    if method=='RelevanceCostRule':return sorted(scored,key=lambda x:(-(x.components['rel']+.25*x.components['tag']-.25*x.record.sensitivity),x.record.record_id))
    raise ValueError(method)
def public_features(t):
    x=np.zeros(PUBN,dtype=np.float32);x[t['type_id']*4+t['variant']]=1.
    x[32+['explicit','ambiguous','missing','dependency','sensitive_proxy'].index(t['difficulty'])]=1.
    x[37+int(t['knowledge'][5:])]=1.
    for i,k in enumerate(['threshold','weight','budget','count','days']):
        if k in PARAMS[t['type_id']][t['variant']]:x[45+i]=t['params'][k]
    return x
def view(t,parsed):
    x=np.zeros(DIM,dtype=np.float32);x[:PUBN]=public_features(t)
    for key,value in parsed.items():
        i=KEYS.index(key);x[PUBN+3*i]=1.
        if value is None:x[PUBN+3*i+1]=1.
        else:x[PUBN+3*i+2]=value
    return x
