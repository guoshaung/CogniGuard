"""Evaluate frozen quick outputs and apply the pre-registered seven-bit gate."""
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from forms import scan,formula_items,count_slots,MATH

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'var/results/hsw-st/afk_stage0_20261121'
AT=OUT/'attestation04'


def load(p):return json.loads(p.read_bytes())


def main():
    if (HERE/'A0_RESULT.md').exists():raise FileExistsError('Keep completed report immutable')
    table=load(AT/'ATTESTATION_SUMMARY.json');scenarios=load(OUT/'QUICK_SCENARIOS.json')
    capacities=load(AT/'CAPACITY_INITIAL.json');capmap={x['id']:x for x in capacities}
    basejobs={x['id']:x for x in load(OUT/'QUICK_INPUTS.json')}
    sys.path.insert(0,str(ROOT/'experiments/hsw_english_replication_20261110_01'))
    from capacity_shared_v32 import nlp
    parsed={x['raw']:x for x in [json.loads(l) for l in (OUT/'FORMULA_PARSE.jsonl').read_text(encoding='utf8').splitlines()]}
    def inventory(text):
        for m in MATH.finditer(text):
            raw=next(g for g in m.groups() if g is not None)
            if raw not in parsed:parsed[raw]=formula_items(raw)
        return scan(text,parsed,count_slots(nlp(text)))
    def group(item):
        dim=item['dimension'];bucket=dim+'|'+(item['canonical'] if dim in ['fraction_coefficient','multiplication'] else '*')
        styles=table['adopted_groups'].get(bucket,[])
        if item['style'] not in styles:return None
        key=dim+'|DOCUMENT' if table['style_consistency'][dim]['document_style'] else dim+'|'+item['canonical']
        return key,len(styles)
    def groups(items):
        return {g[0]:g[1] for a in items if (g:=group(a))}
    rows=[];totals={};new_bit_rows=[]
    for compressor in ['C1','C2']:
        folder=OUT/'quick_compression'/compressor;completed=load(folder/'RESULT.json')
        records={x['scenario_id']:x for x in completed['results']}
        counters=defaultdict(lambda:dict(retained=0,n=0,eligible_documents=0,not_applicable_documents=0))
        for source in scenarios:
            original=source['original'];original_groups=groups(inventory(original))
            for scene in source['scenarios']:
                kind=scene['kind'];ident=source['id']+'__'+kind
                if ident not in records:
                    counters[kind]['not_applicable_documents']+=1
                    continue
                record=records[ident]
                assert record['status']=='COMPLETED'
                output=(folder/'outputs'/(record['id']+'.txt')).read_text(encoding='utf8')
                out_items=inventory(output);out_groups=groups(out_items)
                before_items=inventory(scene['text']);before_groups=groups(before_items)
                if kind=='variant':
                    # Each modified anchor is a distinct trial, not one arbitrary
                    # substring hit for an entire document.
                    for edit in scene['edits']:
                        expected=next((x for x in before_items if x['dimension']==edit['dimension']
                                       and x['canonical']==edit['canonical'] and x['raw']==edit['new']),None)
                        match=[x for x in out_items if x['dimension']==edit['dimension'] and x['canonical']==edit['canonical']]
                        retained=bool(expected and any(x['raw']==edit['new'] for x in match))
                        state='VARIANT_RETAINED' if retained else 'REWRITTEN' if match else 'DISAPPEARED'
                        rows.append(dict(compressor=compressor,id=source['id'],kind=kind,
                                         dimension=edit['dimension'],canonical=edit['canonical'],state=state,retained=retained))
                        counters[kind]['n']+=1;counters[kind]['retained']+=retained
                else:
                    for edit in scene['edits']:
                        content=edit['inserted'].strip()
                        retained=content in output
                        rows.append(dict(compressor=compressor,id=source['id'],kind=kind,
                                         inserted=content,retained=retained,
                                         survival_definition='literal inserted surface retained'))
                        counters[kind]['n']+=1;counters[kind]['retained']+=retained
                counters[kind]['eligible_documents']+=bool(scene['edits'])
                new={k:v for k,v in before_groups.items() if k not in original_groups}
                survived={k:v for k,v in new.items() if k in out_groups}
                new_bit_rows.append(dict(compressor=compressor,id=source['id'],kind=kind,
                    new_groups=len(new),survived_new_groups=len(survived),
                    new_bits=sum(math.log2(v) for v in new.values()),
                    retained_new_bits=sum(math.log2(v) for v in survived.values())))
        totals[compressor]={}
        for kind,c in counters.items():totals[compressor][kind]=dict(**c,rate=c['retained']/c['n'] if c['n'] else None)
    median_bits=float(np.median([x['bits'] for x in capacities]))
    contributions={}
    for compressor in ['C1','C2']:
        # Missing/inapplicable insertion types contribute zero observed evidence,
        # with their applicability counts explicitly retained above.
        per_source=[]
        for source in scenarios:
            per_source.append(sum(x['retained_new_bits'] for x in new_bit_rows
                if x['compressor']==compressor and x['id']==source['id'] and x['kind']!='variant'))
        added=float(np.median(per_source));r=totals[compressor]['variant']['rate']
        contributions[compressor]=dict(capacity_median=median_bits,variant_retention=r,
            original_surviving_bits=median_bits*r if r is not None else None,
            inserted_surviving_bits_median=added,
            total=median_bits*r+added if r is not None else None,
            passed=r is not None and median_bits*r+added>=7)
    def distribution(items):
        values=[x['bits'] for x in items]
        return dict(n=len(items),quantiles=np.quantile(values,[0,.25,.5,.75,1]).tolist() if values else None)
    subjects={s:distribution([x for x in capacities if x['subject']==s]) for s in sorted({x['subject'] for x in capacities})}
    lengths={label:distribution([x for x in capacities if low<=x['words']<=high])
        for label,low,high in [('<100',0,99),('100-200',100,200),('201-400',201,400),('>400',401,10**9)]}
    result=dict(status='QUICK_GATE_EVALUATED',capacity_quantiles=table['capacity_quantiles'],
        capacity_by_subject=subjects,capacity_by_length=lengths,
        survival=totals,contributions=contributions,gate_bits=7,
        passed=all(v['passed'] for v in contributions.values()),human_A0='AWAITING_50_USER_LABELS',
        paid_API_calls=0,H2_calls=0,stage3_started=False,stage1_started=False,
        limitations=['Parser/validation coverage documented in VARIANT_TABLE and CPU_CAPACITY.',
          'Literal insertion survival is distinguished from equivalently rewritten content.',
          'No applicable source-backed unit-substitution or dimension-check insertion was constructed in the fixed 30-source sample; these cells are unavailable, not a measured 0% survival.',
          'Groups newly appearing in separate insertion arms can overlap; summing their bits is an optimistic diagnostic bound, not simultaneous independent capacity.'])
    (OUT/'QUICK_RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'QUICK_PER_ANCHOR.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'QUICK_NEW_GROUPS.json').write_text(json.dumps(new_bit_rows,ensure_ascii=False,indent=2),encoding='utf8')
    import csv
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with (HERE/'per_anchor.csv').open('x',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
    (HERE/'figure_counts.json').write_text(json.dumps({'afk_stage0':result},ensure_ascii=False,indent=2),encoding='utf8')
    lines=['# AFK阶段0快速预判','',
        '结论：'+('快速门槛通过，尚待A0人工自然度与后续阶段0测量。' if result['passed'] else '快速预判未达到7比特，按预注册停止，不进入第3节和阶段1。'),'',
        '## 有效容量','',json.dumps(result['capacity_quantiles'],ensure_ascii=False),'',
        '容量来自300篇R生成讲解；30篇压缩预判按固定哈希选择，不按容量挑选。','',
        '## 压缩后的有效证据','']
    for name,v in contributions.items():lines.append(f"- {name}：中位容量{v['capacity_median']:.3f} × 写法保留率{v['variant_retention']:.4f} + 插入带来的存活新比特中位数{v['inserted_surviving_bits_median']:.3f} = {v['total']:.3f}比特；要求≥7。")
    lines+=['','## 各类存活计数','',json.dumps(totals,ensure_ascii=False,indent=2),'',
        '## 边界','']+['- '+x for x in result['limitations']]+['',
        '50项自然度表保持空白，不能宣称A0通过。第3节的300篇×多密钥测量、3B评分与微基准未启动，未运行数字不填0。',
        'H2额外留出调用0、付费调用0。','']
    (HERE/'A0_RESULT.md').write_text('\n'.join(lines),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
