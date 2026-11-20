"""Fixed KOSW stage1 experiment, with write-once results and checkpointed calls."""
import gc
import json
import math
import os
import random
import re
import time
from collections import Counter,defaultdict

import numpy as np
import requests
from common import HERE,OUT,EMBED,SEED,load,dump,sha,seed,frozen_components,prereg_gate
from knowledge_pairs import variants

PROMPTS={
'S':'Rewrite the following sentence in different words. Keep every formula, number, unit and technical term exactly as written. Do not add or remove information. Output only the rewritten sentence.\nSentence: {x}',
'P':'Rewrite the following sentence with a slightly different explanatory emphasis or framing (for example, what is highlighted first, or how the step is motivated). Keep every formula, number, unit and technical term exactly as written. Do not add new facts. Keep the length within ±20%. Output only the rewritten sentence.\nSentence: {x}'}
WORD=re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")


def encode(model,texts):
    a=model.encode(texts,batch_size=32,normalize_embeddings=True,show_progress_bar=False)
    assert a.shape==(len(texts),768) and np.isfinite(a).all()
    return a.astype(np.float64)


def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(str(EMBED),device='cuda',local_files_only=True)


def stop(reason,counts=None):
    report=dict(status='STOP',reason=reason,counts=counts,stage2_started=False)
    dump(OUT/'STOP.json',report)
    dump(HERE/'figure_counts.json',{'kosw_stage1':report})
    (HERE/'K1_RESULT.md').write_text('# KOSW 阶段1\n\n停止原因：'+reason+
        '\n\n实际计数：'+json.dumps(counts,ensure_ascii=False)+'\n\n未进入阶段2。\n',encoding='utf8')
    print(reason,flush=True)


def build_knowledge(sentences,nlp,anchors):
    sibling_path=OUT/'term_siblings.json'
    if sibling_path.exists():
        siblings=load(sibling_path)
    else:
        siblings=build_siblings(sentences,nlp)
    progress=OUT/'knowledge_progress.jsonl'
    completed={}
    if progress.exists():
        for line in progress.read_text(encoding='utf8').splitlines():
            record=json.loads(line)
            completed[(record['split'],record['sentence_id'])]=record['pairs']
    pairs={}
    for split,rows in sentences.items():
        result=[]
        for index,row in enumerate(rows,1):
            key=(split,row['id'])
            if key not in completed:
                (OUT/'K_CURRENT.json').write_text(json.dumps(dict(split=split,index=index,
                    sentence_id=row['id'],status='STARTED')),encoding='utf8')
                items=[dict(sentence_id=row['id'],**item) for item in
                       variants(row,siblings,random.Random(seed('K',row['id'])),anchors)]
                with progress.open('a',encoding='utf8') as handle:
                    handle.write(json.dumps(dict(split=split,sentence_id=row['id'],pairs=items),
                                            ensure_ascii=False)+'\n')
                completed[key]=items
            result.extend(completed[key])
            if index%100==0:
                print('K progress',split,index,'/',len(rows),'pairs',len(result),flush=True)
        pairs[split]=result
        path=OUT/('K_'+split+'.json')
        if path.exists():
            assert load(path)==result
        else:
            dump(path,result)
    (OUT/'K_CURRENT.json').write_text(json.dumps(dict(status='COMPLETE',
        counts={k:len(v) for k,v in pairs.items()})),encoding='utf8')
    return pairs


def build_siblings(sentences,nlp):
    model=get_model()
    subject_terms=defaultdict(set)
    for row in sentences['train']:
        subject_terms[row['subject']].update(a[2:] for a in row['anchors'] if a.startswith('T:'))
    siblings={}
    for subject,terms in sorted(subject_terms.items()):
        terms=sorted(terms)
        if not terms:
            siblings[subject]={};continue
        vectors=encode(model,terms)
        # Frozen lemma analysis excludes case and singular/plural variants.
        forms={t:tuple(x.lemma_.casefold() for x in nlp(t) if not x.is_space) for t in terms}
        similarities=vectors@vectors.T
        siblings[subject]={}
        for i,t in enumerate(terms):
            order=sorted(range(len(terms)),key=lambda j:(-similarities[i,j],terms[j]))
            nearest=[terms[j] for j in order if forms[terms[j]]!=forms[t]][:5]
            siblings[subject][t]=nearest
    dump(OUT/'term_siblings.json',siblings)
    del model;gc.collect()
    import torch
    torch.cuda.empty_cache()
    return siblings


def generate(sentences,anchors):
    folder=OUT/'calls';folder.mkdir(exist_ok=True)
    expected=load(OUT/'OLLAMA_ASSET.json')['digest']
    tags=requests.get('http://127.0.0.1:11434/api/tags',timeout=20).json()['models']
    assert next(m['digest'] for m in tags if m['name']=='qwen2.5:7b-instruct')==expected
    retained={s:[] for s in sentences}
    # Four P attempts on heldout = two required pairs plus two capacity candidates.
    # Rejected attempts remain rejected, never repeatedly regenerate until accepted.
    total=sum(len(rows)*(6 if split=='heldout' else 4) for split,rows in sentences.items())
    done=0;started=time.monotonic()
    for split,rows in sentences.items():
        for row in rows:
            for kind in ['S','P']:
                for replicate in range(4 if split=='heldout' and kind=='P' else 2):
                    ident=f"{row['id']}_{kind}_{replicate}"
                    path=folder/(ident+'.json')
                    if path.exists():
                        record=load(path)
                    else:
                        marker=folder/(ident+'.started.json')
                        if marker.exists():
                            raise RuntimeError('Unresolved interrupted call: '+ident)
                        sd=seed('ollama',ident)&0x7fffffff
                        prompt=PROMPTS[kind].format(x=row['text'])
                        dump(marker,dict(seed=sd,prompt_sha256=__import__('hashlib').sha256(prompt.encode()).hexdigest()))
                        tick=time.monotonic()
                        response=requests.post('http://127.0.0.1:11434/api/generate',json=dict(
                            model='qwen2.5:7b-instruct',prompt=prompt,stream=False,keep_alive='10m',
                            options=dict(temperature=.8,top_p=.95,seed=sd,num_predict=256)),timeout=300)
                        response.raise_for_status();body=response.json();text=body['response'].strip()
                        same=tuple(anchors(text))==tuple(row['anchors'])
                        ratio=len(WORD.findall(text))/max(1,len(WORD.findall(row['text'])))
                        good=same and bool(text) and (kind=='S' or .8<=ratio<=1.2)
                        record=dict(sentence_id=row['id'],split=split,type=kind,replicate=replicate,
                            text=text,seed=sd,anchors_equal=same,length_ratio=ratio,accepted=good,
                            capacity_only=kind=='P' and replicate>=2,
                            done_reason=body.get('done_reason'),seconds=time.monotonic()-tick,
                            eval_count=body.get('eval_count'),eval_duration=body.get('eval_duration'))
                        dump(path,record)
                    done+=1
                    if record['accepted']:
                        retained[split].append(record)
                    if done%100==0:
                        print('LLM calls',done,'/',total,'seconds',round(time.monotonic()-started),flush=True)
    requests.post('http://127.0.0.1:11434/api/generate',json=dict(model='qwen2.5:7b-instruct',keep_alive=0),timeout=60).raise_for_status()
    return retained


def write_examples(pairs):
    sentences={r['id']:r for group in load(OUT/'SENTENCES.json').values() for r in group}
    lines=['# KOSW句对例子','']
    for kind in ['K','S','P']:
        rows=[r for group in pairs.values() for r in group if r['type'].startswith(kind)]
        chosen=random.Random(seed('examples',kind)).sample(rows,min(20,len(rows)))
        lines.extend(['## '+kind,''])
        for row in chosen:
            lines.extend(['- ID: '+row['sentence_id'],'  - 原句：'+sentences[row['sentence_id']]['text'],
                          '  - 变体：'+row['text'],''])
    (HERE/'EXAMPLES.md').write_text('\n'.join(lines),encoding='utf8')


def analyze(sentences,pairs):
    from scipy import linalg,stats
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    model=get_model()
    original={r['id']:r for group in sentences.values() for r in group}
    texts=sorted(set(r['text'] for r in original.values())|set(r['text'] for group in pairs.values() for r in group))
    vectors=encode(model,texts);emb={t:v for t,v in zip(texts,vectors)}
    deltas={}
    for split,rows in pairs.items():
        for kind in ['K','S','P']:
            selected=[r for r in rows if r['type'].startswith(kind) and not r.get('capacity_only')]
            deltas[(split,kind)]=np.stack([emb[r['text']]-emb[original[r['sentence_id']]['text']] for r in selected])
    cov=lambda D:D.T@D/len(D)
    CK,CS,CP=[cov(deltas['train',k]) for k in ['K','S','P']]
    delta=1e-3*np.trace(CS)/768;I=np.eye(768)
    lamK,VK=linalg.eigh(CK,CS+delta*I)
    UK=np.linalg.qr(VK[:,::-1][:,:32])[0]
    perp=I-UK@UK.T
    lamC,VC=linalg.eigh(perp@CP@perp,perp@(CS+CK)@perp+delta*I)
    UC=np.linalg.qr(perp@VC[:,::-1][:,:16])[0]
    for name,a in [('UK',UK),('UC',UC),('lamK',lamK),('lamC',lamC)]:
        np.save(OUT/(name+'.npy'),a)
    def classification(split):
        D=np.concatenate([deltas[split,k] for k in ['K','S','P']])
        y=np.concatenate([np.ones(len(deltas[split,'K'])),np.zeros(len(deltas[split,'S'])+len(deltas[split,'P']))])
        return D,y
    Dt,yt=classification('train');Dh,yh=classification('heldout')
    clf=LogisticRegression(max_iter=1000,random_state=SEED).fit(Dt@UK,yt)
    scores=clf.predict_proba(Dh@UK)[:,1];auc=float(roc_auc_score(yh,scores))
    # Unit-normalized embedding cosine distance equals ||difference||^2/2.
    cos_t=(Dt*Dt).sum(1)/2;cos_h=(Dh*Dh).sum(1)/2
    cos_clf=LogisticRegression(max_iter=1000,random_state=SEED).fit(cos_t[:,None],yt)
    cos_auc=float(roc_auc_score(yh,cos_clf.predict_proba(cos_h[:,None])[:,1]))
    krows=[r for r in pairs['heldout'] if r['type'].startswith('K')]
    by_rule={}
    for kind in ['K-formula','K-number','K-unit','K-term','K-polarity']:
        mask=np.concatenate([np.array([r['type']==kind for r in krows]),np.ones(len(yh)-len(krows),dtype=bool)])
        by_rule[kind]=(dict(n=sum(r['type']==kind for r in krows),
            auc=float(roc_auc_score(yh[mask],scores[mask])))
            if any(r['type']==kind for r in krows) else None)
    def rho(D):
        return float(((D@UC)**2).sum(1).mean()/16/((D*D).sum(1).mean()/768))
    ratios={k:rho(deltas['heldout',k]) for k in ['K','S','P']}
    # Independent diagnostic keys, raw key bytes remain local, only commitment is published.
    key_path=OUT/'diagnostic_keys.npy'
    if key_path.exists():keys=np.load(key_path)
    else:
        keys=np.frombuffer(os.urandom(32000),dtype=np.uint8).reshape(1000,32).copy();np.save(key_path,keys)
    def directions(sid):
        return np.stack([np.random.default_rng(int.from_bytes(__import__('hashlib').sha256(
            k.tobytes()+sid.encode()).digest()[:8],'big')).normal(size=16) for k in keys])
    def unit(text):
        a=emb[text]@UC;n=np.linalg.norm(a)
        if n==0:raise ValueError('Zero carrier projection')
        return a/n
    gain=[];nstars=[];capacity=[]
    for source in sentences['heldout']:
        options=[r['text'] for r in pairs['heldout'] if r['type']=='P' and r['sentence_id']==source['id']]
        options=list(dict.fromkeys(options))[:4]
        R=directions(source['id']);R/=np.linalg.norm(R,axis=1,keepdims=True)
        base=R@unit(source['text']);candidate=np.stack([unit(t) for t in [source['text']]+options])
        maximum=(R@candidate.T).max(1);g=maximum-base;ez=4*maximum.mean()
        nstar=(3.09/ez)**2 if ez>0 else None
        gain.extend(g.tolist());nstars.append(float(nstar) if nstar is not None else float('inf'))
        capacity.append(dict(id=source['id'],retained_P_candidates=len(options),mean_gain=float(g.mean()),nstar=nstar))
    # R_calib only; same frozen structure/sentence functions and 8..60 words.
    nlp,_,_,_,_,_,split_fn,allowed=frozen_components()
    corpus=[r for r in load(ROOT/'var/results/hsw-st/certinsert_eval04_20261113/stage0/R_CORPUS.json') if r['split']=='calib']
    null_sentences=[];documents={}
    for row,doc in zip(corpus,nlp.pipe((r['text'] for r in corpus),batch_size=16)):
        structure=split_fn(row['text'],row.get('question',''));items=[]
        for j,s in enumerate(doc.sents):
            text=s.text.strip()
            if 8<=len(WORD.findall(text))<=60 and allowed(structure,s.start_char) and not any(
                x['role']!='BODY' and x['start']<s.end_char and x['end']>s.start_char for x in structure['spans']):
                sid=row['id']+'|s'+str(j);items.append((sid,text));null_sentences.append(text)
        if items:documents[row['id']]=items
    new=sorted(set(null_sentences)-set(emb));new_vectors=encode(model,new) if new else []
    emb.update(zip(new,new_vectors))
    Ts=[]
    for ident,items in documents.items():
        sums=np.zeros(1000)
        for sid,text in items:
            R=directions(sid);R/=np.linalg.norm(R,axis=1,keepdims=True)
            sums+=4*(R@unit(text))
        Ts.extend((sums/math.sqrt(len(items))).tolist())
    Ts=np.asarray(Ts);ks=stats.kstest(Ts,'norm')
    null=dict(documents=len(documents),text_key_combinations=len(Ts),mean=float(Ts.mean()),variance=float(Ts.var()),
        ks_statistic=float(ks.statistic),ks_p=float(ks.pvalue),
        fpr01=float((Ts>stats.norm.ppf(.99)).mean()),fpr001=float((Ts>stats.norm.ppf(.999)).mean()))
    median=float(np.median(nstars))
    results=dict(status='EVALUATED',G1=dict(auc=auc,cosine_auc=cos_auc,by_rule=by_rule,passed=auc>=.9 and auc-cos_auc>=.05),
        G2=dict(top16=lamC[::-1][:16].tolist(),passed=int((lamC[::-1][:16]>=2).sum())>=8),
        G3=dict(rho_S=ratios['S'],rho_P=ratios['P'],ratio=ratios['P']/ratios['S'],passed=ratios['S']<=.5 and ratios['P']/ratios['S']>=2),
        G4=dict(rho_K=ratios['K'],passed=ratios['K']<=.5),
        G5=dict(mean_gain=float(np.mean(gain)),gain_quantiles=np.quantile(gain,[0,.25,.5,.75,1]).tolist(),
            median_nstar=median if np.isfinite(median) else None,passed=median<=10),
        G6=dict(**null,passed=null['ks_p']>.01 and null['fpr01']<=.01 and null['fpr001']<=.001),
        subspace_sha256={n:sha(OUT/n) for n in ['UK.npy','UC.npy','lamK.npy','lamC.npy']},
        diagnostic_key_sha256=sha(key_path),stage2_started=False)
    results['all_passed']=all(results[g]['passed'] for g in ['G1','G2','G3','G4','G5','G6'])
    dump(OUT/'CAPACITY.json',capacity);dump(OUT/'RESULT.json',results)
    dump(HERE/'figure_counts.json',{'kosw_stage1':results})
    text='# KOSW 阶段1结果\n\n'+('全部门槛通过。' if results['all_passed'] else '至少一项门槛未通过，停止。')+'\n\n'
    for g in ['G1','G2','G3','G4','G5','G6']:
        text+='## '+g+'\n\n'+json.dumps(results[g],ensure_ascii=False,indent=2)+'\n\n'
    text+='本结果针对本次固定模型、构造数据、子空间估计及门槛；失败不构成所有可能方向不存在的数学证明。阶段2未执行。\n'
    (HERE/'K1_RESULT.md').write_text(text,encoding='utf8')


def main():
    prereg_gate();sentences=load(OUT/'SENTENCES.json');nlp,anchors,*_=frozen_components()
    if (OUT/'K_train.json').exists():
        knowledge={s:load(OUT/('K_'+s+'.json')) for s in sentences}
    else:knowledge=build_knowledge(sentences,nlp,anchors)
    counts={s:len(rows) for s,rows in knowledge.items()}
    if counts['train']<2000 or counts['heldout']<600:
        stop('K句对数量不足任务书要求，停止，不生成S/P。',counts);return
    generated=generate(sentences,anchors)
    pairs={s:knowledge[s]+generated[s] for s in sentences}
    counts={s:dict(Counter('K' if r['type'].startswith('K') else r['type'] for r in rows if not r.get('capacity_only'))) for s,rows in pairs.items()}
    for split,rows in pairs.items():
        with (OUT/('pairs_'+split+'.jsonl')).open('x',encoding='utf8') as handle:
            for row in rows:
                handle.write(json.dumps({k:v for k,v in row.items() if k!='seed'},ensure_ascii=False)+'\n')
    write_examples(pairs)
    if any(counts[s].get(k,0)<minimum for s,minimum in [('train',2000),('heldout',600)] for k in ['K','S','P']):
        stop('K/S/P保留句对数量未达到任务书要求。',counts);return
    analyze(sentences,pairs)


if __name__=='__main__':
    main()
