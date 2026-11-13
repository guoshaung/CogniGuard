"""After generation completes, materialize R, split, mine and count candidate funnel."""
import collections
import hashlib
import json
import math
import re
from pathlib import Path

import spacy

W=Path(__file__).resolve().parents[2]
E=Path(__file__).resolve().parent
O=W/'var/results/hsw-st/certinsert_eval04_20261113/stage0'


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def put(name,value):
    p=O/name
    with p.open('x',encoding='utf8') as handle:
        json.dump(value,handle,indent=2,ensure_ascii=False)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def normalized(text):
    return re.sub(r'\s+',' ',text).strip().casefold()


def prefix(text):
    match=re.match(r"^\s*([A-Za-z]+(?:['’-][A-Za-z]+)*(?:\s+[A-Za-z]+(?:['’-][A-Za-z]+)*){0,3})\s*,",text)
    return normalized(match[1]) if match else None


def main():
    gen=read(O/'generation01/RESULT.json')
    if gen['attempted']!=300 or any(r['status']!='COMPLETED' for r in gen['rows']):
        raise RuntimeError('R needs 300 completed once-generated explanations; no substitution')
    sources=read(O/'R_SOURCE_DOCUMENTS.json')
    questions={r['id']:r for r in read(E/'R_GENERATION_INPUTS.json')}
    historical=[]
    base=W/'var/results/hsw-st/certinsert_eval03_lite_20261112/run01'
    for p in [base/'materials02/T4.json',base/'batch02_adjusted/data/P6_BACKGROUND.json']:
        historical.extend(normalized(x['text']) for x in read(p))
    seen={digest(normalized(x['text'])) for x in sources}
    generated=[]
    for row in gen['rows']:
        p=O/'generation01/outputs'/(row['id']+'.txt')
        text=p.read_text(encoding='utf8');h=digest(normalized(text))
        if not text.strip() or h in seen or any(normalized(text) in t or t in normalized(text) for t in historical if len(t)>80):
            raise RuntimeError('Generated document empty or duplicates R/historical data: '+row['id'])
        seen.add(h)
        source=questions[row['source_id']]
        generated.append(dict(id=row['id'],kind='generated',text=text,text_sha256=digest(text),
            normalized_sha256=h,chapters=source['chapters'],subject=source['subject'],
            source_id=source['id'],question_sha256=source['text_sha256'],
            question=source['text'],natural_eos=row.get('stop_type')=='eos'))
    docs=sources+generated
    docs.sort(key=lambda x:digest('EVAL04v3|R_split|'+x['id']))
    nbuild=math.floor(.8*len(docs))
    for i,row in enumerate(docs):
        row['split']='build' if i<nbuild else 'calib'
    put('R_CORPUS.json',docs)
    put('RAG_CORPUS_MANIFEST.json',dict(status='CORPUS_COMPLETE',documents=len(docs),
        source_documents=len(sources),generated_documents=300,build=nbuild,calib=len(docs)-nbuild,
        split_rule='SHA256(EVAL04v3|R_split|document_id), exact 80/20 by floor',
        T6_content_reads=0,chapter_allocation_sha256=digest((O/'CHAPTER_ALLOCATION.json').read_text()),
        records=[{k:v for k,v in r.items() if k not in ['text','question']} for r in docs],
        dedup='source inventory historical exact/substrings; generated exact R and historical exact/substrings',
        semantic_dedup_claimed=False))
    nlp=spacy.load('en_core_web_sm')
    counts=collections.Counter();sentences=[]
    build=[r for r in docs if r['split']=='build']
    for row,doc in zip(build,nlp.pipe((r['text'] for r in build),batch_size=16)):
        prefixes=set()
        for i,sent in enumerate(doc.sents):
            text=sent.text.strip();candidate=prefix(text)
            if candidate:
                prefixes.add(candidate)
            if not candidate and not re.search(r'\\[([]|[\n\r]',text) and 8<=len([t for t in sent if t.is_alpha])<=80:
                sentences.append(dict(id=row['id']+'|s'+str(i),text=text,document_id=row['id']))
        counts.update(prefixes)
    attested=[dict(text=c,df=n) for c,n in sorted(counts.items()) if n>=.002*nbuild]
    put('MINED_CANDIDATES.json',[dict(text=c,df=n) for c,n in sorted(counts.items())])
    put('ATTESTED_CANDIDATES.json',attested)
    put('NLI_SENTENCE_POOL.json',sentences)
    put('FUNNEL.json',dict(documents=len(docs),build_documents=nbuild,calib_documents=len(docs)-nbuild,
        mined=len(counts),attested=len(attested),df_cutoff=.002*nbuild,
        nli_sentence_pool=len(sentences),NLI=None,anchor_free=None,fluency=None,
        frequency=None,independence=None,group_capped=None))
    print('MINED',len(counts),'ATTESTED',len(attested),'NLI_POOL',len(sentences),flush=True)


if __name__=='__main__':
    main()
