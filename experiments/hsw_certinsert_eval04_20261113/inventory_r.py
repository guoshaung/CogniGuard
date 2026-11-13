"""Count and deduplicate R paragraph/solution documents, without any scoring."""
import ast
import collections
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

W=Path(__file__).resolve().parents[2]
O=W/'var/results/hsw-st/certinsert_eval04_20261113/stage0'


def norm(text):
    return re.sub(r'\s+',' ',text).strip().casefold()


def main():
    result=json.loads((O/'R_FETCH_RESULT.json').read_bytes())
    if result['failures']:
        raise RuntimeError('Source fetch incomplete; do not substitute')
    renderer=W/'experiments/hsw_insertion_feasibility_20261109_01/run08_long_prepare.py'
    tree=ast.parse(renderer.read_text(encoding='utf8'));ns={}
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)
        and n.name in ['math','render']],type_ignores=[]),'historical_renderer','exec'),ns)
    render=ns['render'];tag=lambda e:e.tag.split('}')[-1]
    base=W/'var/results/hsw-st/certinsert_eval03_lite_20261112/run01'
    historical=[]
    paths=[base/'materials02/T4.json',base/'batch02_adjusted/data/P6_BACKGROUND.json',
        base/'batch02_adjusted/data/T5_QUESTIONS.json']
    e1=W/'var/results/hsw-st/certinsert_eval_20261111_01/run01/data/selection02'
    paths += [e1/'T1.json',e1/'T2.json',e1/'T3_QUESTIONS.json']
    for path in paths:
        rows=json.loads(path.read_bytes())
        historical.extend(norm(x.get('text',x.get('question',''))) for x in rows)
    hashes={hashlib.sha256(x.encode()).hexdigest() for x in historical if x}
    docs=[];questions=[];reject=collections.Counter();seen=set()
    ledger=[json.loads(x) for x in (O/'R_FETCH_LEDGER.jsonl').read_text().splitlines()]
    for source in ledger:
        body=Path(source['path']).read_bytes()
        assert hashlib.sha256(body).hexdigest()==source['sha256']
        root=ET.fromstring(body);parents={c:p for p in root.iter() for c in p}
        for i,node in enumerate(root.iter()):
            kind=tag(node)
            if kind not in ['para','solution','problem']:
                continue
            anc=[];parent=parents.get(node)
            while parent is not None:
                anc.append(tag(parent));parent=parents.get(parent)
            if kind=='para' and set(anc)&{'example','exercise','problem','solution','figure','table','para','note'}:
                continue
            if kind=='solution' and 'solution' in anc:
                continue
            text=re.sub(r'\n{3,}','\n\n',re.sub(r'[ \t]+',' ',render(node))).strip()
            words=len(re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*",text))
            if not (8<=words<=500 if kind=='problem' else 40<=words<=600):
                reject['LENGTH']+=1;continue
            if '\\unsupported{' in text or '[image ' in text or '[cross-reference ' in text or any(tag(x)=='table' for x in node.iter()):
                reject['INCOMPLETE_RENDER']+=1;continue
            normalized=norm(text);digest=hashlib.sha256(normalized.encode()).hexdigest()
            if digest in hashes or any(normalized in x or x in normalized for x in historical if len(x)>80):
                reject['HISTORICAL_DUPLICATE_OR_SUBSTRING']+=1;continue
            if digest in seen:
                reject['R_EXACT_DUPLICATE']+=1;continue
            seen.add(digest)
            row=dict(id=source['id']+'|'+node.get('id',str(i)),kind=kind,text=text,
                text_sha256=hashlib.sha256(text.encode()).hexdigest(),normalized_sha256=digest,
                subject=source['subject'],source_id=source['id'],chapters=source['chapters'],
                source_url=source['url'],revision=source['revision'],raw_sha256=source['sha256'])
            (questions if kind=='problem' else docs).append(row)
    for name,rows in [('R_SOURCE_DOCUMENTS.json',docs),('R_GENERATION_QUESTIONS.json',questions)]:
        (O/name).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    summary=dict(status='MATERIAL_COUNTS_ONLY_NOT_STAGE0_COMPLETE',documents=len(docs),
        question_candidates=len(questions),document_subjects=dict(collections.Counter(x['subject'] for x in docs)),
        question_subjects=dict(collections.Counter(x['subject'] for x in questions)),rejections=dict(reject),
        minimum_document_target=2000,minimum_generated_target=300,T6_content_reads=0,
        renderer_sha256=hashlib.sha256(renderer.read_bytes()).hexdigest(),
        material_gate=len(docs)>=2000 and len(questions)>=300,
        document_unit='one standalone exposition paragraph or complete example solution, 40..600 English words',
        remaining='No corpus split, model generations, NLI scores, fluency or lexicon selection yet')
    (O/'R_MATERIAL_INVENTORY.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    main()
