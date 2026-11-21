"""CPU-only AFK attestation, style consistency, and upper capacity statistics."""
import concurrent.futures
import hashlib
import json
import math
import multiprocessing as mp
import time
from collections import Counter,defaultdict
from pathlib import Path

import numpy as np

from forms import MATH, formula_items, scan, count_slots

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
BASE=ROOT/'var/results/hsw-st/afk_stage0_20261121'
OUT=BASE/'attestation04'
CORPUS=ROOT/'var/results/hsw-st/certinsert_eval04_20261113/stage0/R_CORPUS.json'


def dump(name,data):
    p=OUT/name
    with p.open('x',encoding='utf8') as handle:
        json.dump(data,handle,ensure_ascii=False,indent=2)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'CORPUS_STYLE_STATS.json').exists():
        raise FileExistsError('Preserve existing attestation')
    corpus=json.loads(CORPUS.read_bytes())
    # Union by ID: OpenStax source corpus plus R_build, no double-count of documents.
    reference={r['id']:r for r in corpus if r['split']=='build' or r['kind']!='generated'}
    generated=[r for r in corpus if r['kind']=='generated']
    assert len(generated)==300
    raws=sorted({next(g for g in m.groups() if g is not None)
                 for r in list(reference.values())+generated for m in MATH.finditer(r['text'])})
    cache={};cache_path=BASE/'FORMULA_PARSE.jsonl'
    if cache_path.exists():
        cache={r['raw']:r for r in [json.loads(s) for s in cache_path.read_text(encoding='utf8').splitlines()]}
    # One cancellable worker bounds each formula parser, not a changed scientific cutoff.
    context=mp.get_context('spawn');pool=context.Pool(1)
    try:
        for index,raw in enumerate(raws,1):
            if raw in cache:continue
            task=pool.apply_async(formula_items,(raw,))
            try:
                record=task.get(timeout=5)
            except mp.TimeoutError:
                pool.terminate();pool.join();pool=context.Pool(1)
                record=dict(raw=raw,status='PARSE_TIMEOUT',reason='5s CPU parser cap, excluded and recorded')
            cache[raw]=record
            with cache_path.open('a',encoding='utf8') as handle:handle.write(json.dumps(record,ensure_ascii=False)+'\n')
            if index%100==0:print('Formula parse',index,'/',len(raws),flush=True)
    finally:
        pool.terminate();pool.join()
    # Formula coefficient styles need attestation within exact formula class.
    # Other dimensions share surface templates but retain per-anchor canonical values.
    count_cache_path=BASE/'COUNT_SLOTS.json'
    if count_cache_path.exists():counts=json.loads(count_cache_path.read_bytes())
    else:
        import sys
        sys.path.insert(0,str(ROOT/'experiments/hsw_english_replication_20261110_01'))
        from capacity_shared_v32 import nlp
        allrows=list({r['id']:r for r in list(reference.values())+generated}.values());counts={}
        for index,(row,doc) in enumerate(zip(allrows,nlp.pipe((r['text'] for r in allrows),batch_size=16)),1):
            counts[row['id']]=count_slots(doc)
            if index%500==0:print('Count noun parsing',index,'/',len(allrows),flush=True)
        count_cache_path.write_text(json.dumps(counts,ensure_ascii=False),encoding='utf8')
    occurrences={r['id']:scan(r['text'],cache,counts[r['id']]) for r in reference.values()}
    groups=defaultdict(lambda:defaultdict(lambda:dict(docs=set(),count=0,examples=[])))
    for ident,items in occurrences.items():
        for a in items:
            bucket=a['dimension']+'|'+(a['canonical'] if a['dimension'] in ['fraction_coefficient','multiplication'] else '*')
            item=groups[bucket][a['style']];item['docs'].add(ident);item['count']+=1
            if len(item['examples'])<3:item['examples'].append(a['raw'])
    adopted={};stats={}
    for group,styles in sorted(groups.items()):
        total=sum(v['count'] for v in styles.values());stats[group]={}
        eligible=[]
        for style,v in styles.items():
            share=v['count']/total;passed=share>=.1 and len(v['docs'])>=20
            stats[group][style]=dict(documents=len(v['docs']),occurrences=v['count'],share=share,passed=passed,examples=v['examples'])
            if passed:eligible.append(style)
        if len(eligible)>=2:adopted[group]=sorted(eligible)
    dimensions=sorted({g.split('|',1)[0] for g in adopted})
    consistency={}
    for dim in dimensions:
        numerator=denominator=0
        for items in occurrences.values():
            relevant=[a for a in items if a['dimension']==dim]
            if len(set(a['canonical'] for a in relevant))<2:continue
            denominator+=1;numerator+=len(set(a['style'] for a in relevant))==1
        ratio=numerator/denominator if denominator else None
        consistency[dim]=dict(consistent_documents=numerator,eligible_documents=denominator,rate=ratio,
                              document_style=ratio is not None and ratio>=.9)
    def eligible(a):
        bucket=a['dimension']+'|'+(a['canonical'] if a['dimension'] in ['fraction_coefficient','multiplication'] else '*')
        return bucket if bucket in adopted and a['style'] in adopted[bucket] else None
    capacity=[];genitems={}
    for row in generated:
        items=scan(row['text'],cache,counts[row['id']]);genitems[row['id']]=items;style_groups={}
        for a in items:
            bucket=eligible(a)
            if not bucket:continue
            dim=a['dimension'];key=dim+'|DOCUMENT' if consistency[dim]['document_style'] else dim+'|'+a['canonical']
            if key in style_groups:style_groups[key]&=set(adopted[bucket])
            else:style_groups[key]=set(adopted[bucket])
        effective={k:len(v) for k,v in style_groups.items() if len(v)>=2}
        capacity.append(dict(id=row['id'],subject=row['subject'],words=len(row['text'].split()),
                             groups=effective,bits=sum(math.log2(v) for v in effective.values()),
                             usable_anchor_occurrences=sum(eligible(a) is not None for a in items)))
    vals=[r['bits'] for r in capacity]
    summary=dict(reference_documents=len(reference),R_generated=300,unique_formulas=len(raws),
        formula_parse_status=dict(Counter(x['status'] for x in cache.values())),
        adopted_groups=adopted,style_consistency=consistency,
        capacity_quantiles=dict(zip(['min','p25','median','p75','max'],np.quantile(vals,[0,.25,.5,.75,1]).tolist())),
        documents_with_any_group=sum(v>0 for v in vals),test_content_reads=0,paid_calls=0,
        limitations=['Small-count recognizer uses frozen spaCy count nouns and excludes pint-recognized units.',
          'Formula parsing limited to arithmetic without functions or long expressions; rejected formulas separately recorded.',
          'Unit spellings cover listed SI symbols, word units, LaTeX wrappers and velocity/acceleration templates; unsupported units are not silently asserted equivalent.'],
        status='INITIAL_ATTESTATION_REQUIRES_COVERAGE_REVIEW')
    dump('CORPUS_STYLE_STATS.json',stats);dump('CAPACITY_INITIAL.json',capacity)
    dump('GENERATED_ANCHORS_INITIAL.json',genitems);dump('ATTESTATION_SUMMARY.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
