"""Causal prefix-only predictor; no experiment data files may be read."""
import json
import random
import sys
from pathlib import Path
from experiments.c2rag_r34_20261028_01.common import OUT, enc, sha

def distribution(mode,k):return [1/k]*k if mode=='U' else [.7 if q==mode else .3/(k-1) for q in range(k)]
def categorical(rng,weights):
    u=rng.random();total=0
    for i,w in enumerate(weights):
        total+=w
        if u<total:return i
    return len(weights)-1
def packet(item):
    k=item['types'];condition=item['condition']
    modes=['U'] if condition=='prior' or item['family']=='uniform' else list(range(k))
    alpha={'prior':0,'none':0,'strong':.9,'misleading':.9}[condition]
    weights=[]
    for mode in modes:
        w=1 if condition=='prior' else alpha*int(item['hint']==mode)+(1-alpha)/(k+1)
        if condition!='prior':
            for q in item['prefix']:w*=distribution(mode,k)[q]
        weights.append(w)
    total=sum(weights);weights=[w/total for w in weights]
    rng=random.Random(item['seed']);scenarios=[]
    for _ in range(32):
        mode=modes[categorical(rng,weights)];dist=distribution(mode,k)
        scenarios.append([categorical(rng,dist) for _ in range(7-item['step'])])
    probabilities=[sum(w*distribution(m,k)[q] for m,w in zip(modes,weights)) for q in range(k)]
    return {'input':item,'modes':modes,'weights':weights,'probabilities':probabilities,'scenarios':scenarios,'sha256':sha(enc(scenarios))}

def main():
    sys.stdin.reconfigure(encoding='utf8');sys.stdout.reconfigure(encoding='utf8')
    def audit(event,args):
        if event.startswith('socket.'):raise PermissionError('No networking')
        if event=='open' and isinstance(args[0],str) and Path(args[0]).resolve().is_relative_to(OUT):
            raise PermissionError('No evidence-file access')
    sys.addaudithook(audit)
    try:open(OUT/'events.json')
    except PermissionError:pass
    else:raise AssertionError('Isolation self-test failed')
    previous=[];last=-1;identity=None
    for line in sys.stdin:
        item=json.loads(line)
        assert set(item)=={'stream_id','condition','types','family','hint','prefix','step','seed'}
        now=(item['stream_id'],item['condition'])
        if identity is None:identity=now
        assert identity==now and item['step']==last+1 and item['prefix'][:-1]==previous
        previous=item['prefix'];last=item['step']
        print(json.dumps(packet(item),ensure_ascii=False),flush=True)
    assert last==7

if __name__=='__main__':main()
