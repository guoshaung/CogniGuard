"""Isolated Bayesian forecast worker; no access to hidden modes or suffix files."""
from collections import defaultdict
import random
import sys
from experiments.c2rag_imperfect_forecast_20261027_01.common import OUT,read,write,deadline,encoded,sha


def distribution(mode,k):return [1/k]*k if mode=='U' else [0.7 if q==mode else 0.3/(k-1) for q in range(k)]


def posterior(item):
    assert set(item)=={'stream_id','structure','family','condition','hint','prefix','step','length','types','scenario_seed'}
    k=item['types'];c=item['condition']
    if c=='prior':return ['U'],[1.0]
    modes=['U'] if item['family']=='uniform' else list(range(k))
    alpha={'none':0,'weak':0.5,'strong':0.9,'misleading':0.9}[c]
    weights=[]
    for mode in modes:
        weight=(alpha*int(item['hint']==mode)+(1-alpha)/(k+1))/len(modes)
        d=distribution(mode,k)
        for q in item['prefix']:weight*=d[q]
        weights.append(weight)
    total=sum(weights);assert total>0
    return modes,[w/total for w in weights]


def categorical(u,weights):
    s=0
    for i,w in enumerate(weights):
        s+=w
        if u<s:return i
    return len(weights)-1


def packet(item):
    modes,prob=posterior(item);k=item['types'];rng=random.Random(item['scenario_seed'])
    marginal=[sum(p*distribution(m,k)[q] for m,p in zip(modes,prob)) for q in range(k)]
    scenarios=[]
    for _ in range(32):
        mode=modes[categorical(rng.random(),prob)]
        d=distribution(mode,k)
        scenarios.append([categorical(rng.random(),d) for _ in range(item['length']-item['step']-1)])
    return {'input':item,'posterior_modes':modes,'posterior_probabilities':prob,
            'next_type_probabilities':marginal,'scenarios':scenarios,'scenario_hash':sha(encoded(scenarios)),
            'visible_fields':sorted(item)}


def main():
    allowed_reads={str(OUT/'public/model.json').lower(),str(OUT/'public/forecast_inputs.json').lower()}
    denied=[]
    def audit(event,args):
        if event!='open' or not isinstance(args[0],str):return
        p=str(__import__('pathlib').Path(args[0]).resolve()).lower()
        if not p.startswith(str(OUT).lower()):return
        mode=str(args[1]);writing=any(c in mode for c in 'wax+')
        permitted=(writing and ('forecasts' in __import__('pathlib').Path(p).parts or p==str(OUT/'forecast_receipt.json').lower())) or (not writing and p in allowed_reads)
        if not permitted:denied.append(p);raise PermissionError('forecast worker forbidden evidence access')
    sys.addaudithook(audit)
    try:open(OUT/'events.json',encoding='utf8')
    except PermissionError:pass
    else:raise AssertionError('read isolation selftest failed')
    groups=defaultdict(list)
    for item in read('public/forecast_inputs.json'):
        deadline();groups[(item['stream_id'],item['condition'])].append(packet(item))
    for (sid,c),packets in groups.items():write(f'forecasts/{sid}__{c}.json',packets)
    write('forecast_receipt.json',{'files':len(groups),'packets':sum(map(len,groups.values())),
       'forbidden_read_selftest_passed':True,'denied_attempts':len(denied),'hidden_modes_read':False,
       'suffix_read':False,'scenario_count_per_step':32})
    print('Forecast files',len(groups),'packets',sum(map(len,groups.values())))


if __name__=='__main__':main()
