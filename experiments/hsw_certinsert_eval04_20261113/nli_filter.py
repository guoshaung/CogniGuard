"""CPU-only bidirectional entailment filter with all 100 fixed pairs retained."""
import hashlib
import json
import sys
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

W=Path(__file__).resolve().parents[2]
E=Path(__file__).resolve().parent
O=W/'var/results/hsw-st/certinsert_eval04_20261113/stage0'


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def put(name,value):
    with (O/name).open('x',encoding='utf8') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2)


def report_blocked(funnel,reason):
    text='# 阶段0词表构建：STOPPED\n\n'+reason+'\n\n'
    for key,value in funnel.items():
        text+=f'- {key}: {value if value is not None else "未运行"}\n'
    text+='\n最终L*：未选出。未进入阶段A，未打开T6正文；未放宽筛选阈值。\n'
    (O/'LEXICON_INDUCTION.md').write_text(text,encoding='utf8')
    (O/'STAGE0_STOP.json').write_text(json.dumps(dict(reason=reason,L_star=None,funnel=funnel),
                                              ensure_ascii=False,indent=2),encoding='utf8')


def main():
    if (O/'NLI_RESULTS.json').exists():
        raise FileExistsError('Preserve existing scoring attempt')
    candidates=read(O/'ATTESTED_CANDIDATES.json')
    funnel=read(O/'FUNNEL.json')
    if len(candidates)<10:
        report_blocked(funnel,'真实性筛选后不足10个候选，依照预注册停止。')
        return
    model_info=read(E/'NLI_MODEL_FREEZE.json')
    checkpoint=Path(model_info['path'])
    torch.set_num_threads(4)
    tokenizer=AutoTokenizer.from_pretrained(checkpoint,local_files_only=True)
    model=AutoModelForSequenceClassification.from_pretrained(checkpoint,local_files_only=True).to('cpu').eval()
    label=next(int(i) for i,v in model.config.id2label.items() if v.casefold()=='entailment')
    pool=read(O/'NLI_SENTENCE_POOL.json')
    results=[]
    records=O/'nli';records.mkdir(exist_ok=False)
    for index,candidate in enumerate(candidates,1):
        word=candidate['text']
        sample=sorted(pool,key=lambda row:hashlib.sha256(
            ('EVAL04v3|nli|'+word+'|'+row['id']).encode()).hexdigest())[:100]
        if len(sample)!=100:
            report_blocked(funnel,'NLI可用句子不足100，不复制句子凑数。')
            return
        pairs=[]
        for row in sample:
            original=row['text']
            inserted=word[0].upper()+word[1:]+', '+original[0].lower()+original[1:]
            pairs.extend([(original,inserted),(inserted,original)])
        probabilities=[]
        for start in range(0,200,8):
            batch=pairs[start:start+8]
            encoded=tokenizer([x[0] for x in batch],[x[1] for x in batch],padding=True,
                              truncation=False,return_tensors='pt')
            if encoded['input_ids'].shape[1]>512:
                report_blocked(funnel,'NLI句对超出512-token上下文，不截断、不换句。')
                return
            with torch.inference_mode():
                logits=model(**encoded).logits
                values=torch.softmax(logits,dim=-1)[:,label]
            if not torch.isfinite(values).all():
                raise FloatingPointError('Nonfinite NLI entailment probability')
            probabilities.extend(values.tolist())
        rows=[dict(sentence_id=row['id'],forward=probabilities[2*i],reverse=probabilities[2*i+1])
              for i,row in enumerate(sample)]
        passed=sum(r['forward']>=.9 and r['reverse']>=.9 for r in rows)
        record=dict(**candidate,samples=100,bidirectional_passed=passed,pass_rate=passed/100,
                    qualified=passed>=95,details=rows)
        name=hashlib.sha256(word.encode()).hexdigest()[:24]+'.json'
        (records/name).write_text(json.dumps(record,indent=2),encoding='utf8')
        results.append({k:v for k,v in record.items() if k!='details'})
        print('NLI',index,'/',len(candidates),word,passed,'/100',flush=True)
    put('NLI_RESULTS.json',results)
    qualified=[r for r in results if r['qualified']]
    funnel['NLI']=len(qualified)
    sys.path.insert(0,str(W/'experiments/hsw_english_replication_20261110_01'))
    from e1_v4r7f_anchors import anchors
    anchor_free=[]
    for row in qualified:
        facts=list(anchors(row['text']))
        row['candidate_anchors']=facts
        if not facts:
            anchor_free.append(row)
    funnel['anchor_free']=len(anchor_free)
    put('ANCHOR_FREE_CANDIDATES.json',anchor_free)
    put('FUNNEL_AFTER_NLI.json',funnel)
    if len(anchor_free)<10:
        report_blocked(funnel,'双向NLI与锚点筛选后不足10个合格候选，依照预注册停止；未继续流畅度或L*模拟。')
    else:
        print('NLI_GATE_PASSED',len(anchor_free),flush=True)


if __name__=='__main__':
    main()
