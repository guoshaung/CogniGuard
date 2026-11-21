"""Freeze attestation and deterministic quick-pilot edits before compression."""
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

from forms import MATH, UREG, COUNT_WORDS, scan

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'var/results/hsw-st/afk_stage0_20261121'
AT=OUT/'attestation04'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def rank(ident):return hashlib.sha256(('AFK-A0-20261121|quick|'+ident).encode()).hexdigest()


def alternate(item,styles):
    dimension=item['dimension'];raw=item['raw'];style=item['style']
    other=next((x for x in sorted(styles) if x!=style),None)
    if not other:return None
    if dimension=='large_number':
        digits=raw.replace(',','')
        new=format(int(digits),',') if other=='comma' else digits
        assert new.replace(',','')==digits
    elif dimension=='percentage':
        value=raw.rstrip(' %').removesuffix('percent').strip()
        new=value+(' percent' if other=='word' else '%')
    elif dimension=='unit_spelling':
        unit=item['canonical'];q=UREG.Unit(unit)
        symbol=f'{q:~}'
        names={'kg':'kilograms','g':'grams','m':'meters','cm':'centimeters','s':'seconds',
          'h':'hours','l':'liters','L':'liters','N':'newtons','J':'joules','W':'watts','Pa':'pascals',
          'mol':'moles','K':'kelvin','V':'volts','A':'amperes'}
        if other=='word_unit':
            if symbol not in names:return None
            new=names[symbol]
        elif other=='latex_wrapped_symbol':new=r'\mathrm{'+symbol+'}'
        elif other=='plain_symbol':new=symbol
        else:return None
        assert UREG.Unit(unit)==q
    elif dimension=='small_count':
        value=int(item['canonical'].split('|')[0]);new=str(value) if other=='digit' else COUNT_WORDS[value]
    else:return None
    return new


def main():
    summary=read(AT/'ATTESTATION_SUMMARY.json');stats=read(AT/'CORPUS_STYLE_STATS.json')
    table=['# AFK写法表（压缩前冻结）','',
      '采用门槛：每种写法份额≥10%且文档频率≥20；同一维度不足两种则整个维度不采用。',
      '统计语料为R_build与去重后的全部OpenStax部分的并集，4407个文档，不将重叠文档重复计数。',
      '分数系数与乘号按同一个公式规范类分开统计，不混用不同公式来凑频率。',
      '公式规范化保留等式两边顺序；不采用移项、解变量、单位换算或有效数字改变。','',
      '## 采用的维度与写法','']
    for group,styles in summary['adopted_groups'].items():
        table.append('- '+group)
        for style in styles:
            x=stats[group][style];table.append(f"  - {style}: df={x['documents']}, 次数={x['occurrences']}, 份额={x['share']:.6f}")
    table+=['','## 文内一致性与分组','']
    for dim,x in summary['style_consistency'].items():
        table.append(f"- {dim}: {x['consistent_documents']}/{x['eligible_documents']}，一致率={x['rate']}；"+
                     ('每篇只计一组' if x['document_style'] else '按维度与规范类分组'))
    table+=['','## 完整候选计数','',
      '全部维度/规范类/写法的通过与失败频次见VARIANT_COUNTS.json，不在此列出数百个公式类。',
      '大数按去逗号后的精确数字、百分比按精确数值、单位按同一pint单位对象分组。',
      '小整数只接受冻结spaCy判定的计数名词，排除pint可解析的物理单位。',
      '分数系数/乘号规范类以SymPy算术规范形定义；不支持函数/长式等解析边界列入失败，不等于没有公式。',
      '固定解析器5秒超时为工程退出，不用.equals作无限零判定；解析失败的变体不进入测量。',
      '初次库存中发现的LaTeX单位和计数词漏识别已在压缩前补齐；早期inventory文件留存，不作为最终容量结论。','']
    (HERE/'VARIANT_TABLE.md').write_text('\n'.join(table),encoding='utf8')
    (HERE/'VARIANT_COUNTS.json').write_bytes((AT/'CORPUS_STYLE_STATS.json').read_bytes())
    corpus=read(ROOT/'var/results/hsw-st/certinsert_eval04_20261113/stage0/R_CORPUS.json')
    generated=[x for x in corpus if x['kind']=='generated'];byid={x['id']:x for x in generated}
    anchors=read(AT/'GENERATED_ANCHORS_INITIAL.json')
    examples=[];jobs=[];changed=0
    for row in sorted(generated,key=lambda x:rank(x['id'])):
        items=anchors[row['id']];groups={}
        for item in items:
            dim=item['dimension'];key=dim+'|'+(item['canonical'] if dim in ['fraction_coefficient','multiplication'] else '*')
            styles=summary['adopted_groups'].get(key)
            if not styles or item['style'] not in styles:continue
            group=dim+'|DOCUMENT' if summary['style_consistency'][dim]['document_style'] else dim+'|'+item['canonical']
            groups.setdefault(group,[]).append(item)
        edits=[]
        for group,group_items in sorted(groups.items()):
            dimension=group_items[0]['dimension'];key=dimension+'|'+(group_items[0]['canonical'] if dimension in ['fraction_coefficient','multiplication'] else '*')
            styles=summary['adopted_groups'][key];original_styles={x['style'] for x in group_items}
            possible=[s for s in styles if s not in original_styles]
            if not possible:continue
            selected=random.Random(int(rank(row['id']+'|'+group),16)).choice(possible)
            proposed=[]
            for item in group_items:
                new=alternate(item,[selected,item['style']])
                if new is None:proposed=[];break
                # Unit surface replacements must not introduce a formula delimiter
                # or consume unmatched braces; each edit is literal and reversible.
                if item['raw'].count('{')!=item['raw'].count('}'):
                    proposed=[];break
                proposed.append(dict(**item,new=new,group=group))
            edits.extend(proposed)
        # Reject overlap rather than silently composing conflicting surface edits.
        ordered=sorted(edits,key=lambda x:(x['start'],x['end']));accepted=[]
        for item in ordered:
            if accepted and item['start']<accepted[-1]['end']:continue
            accepted.append(item)
        text=row['text']
        for item in reversed(accepted):
            assert text[item['start']:item['end']]==item['raw']
            text=text[:item['start']]+item['new']+text[item['end']:]
        if len(jobs)<30:
            jobs.append(dict(id='A0_'+rank(row['id'])[:24],source_id=row['id'],subject=row['subject'],
                original=row['text'],variant=text,edits=accepted,source_sha256=row['text_sha256']))
            changed+=bool(accepted)
        for item in accepted:
            if len(examples)>=50:break
            start=max(0,item['start']-100);end=min(len(row['text']),item['end']+100)
            examples.append(dict(id='AFK_REVIEW_'+str(len(examples)+1).zfill(3),
                source_id=row['id'],original=row['text'][start:end],variant=item['new'],
                old=item['raw'],dimension=item['dimension'],label=None))
    assert len(jobs)==30
    (OUT/'QUICK_INPUTS.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'NATURALNESS_REVIEW.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2),encoding='utf8')
    lines=['# AFK自然度人工检查','',f'可提供{len(examples)}个未打标签的写法替换示例；标签由用户填写。','']
    for x in examples:
        lines.extend([f"## {x['id']} · {x['dimension']}",'',x['original'],'',
                      f"只把 `{x['old']}` 改成 `{x['variant']}`。",'','自然 / 不自然 / 无法判断：未填',''])
    (HERE/'EXAMPLES.md').write_text('\n'.join(lines),encoding='utf8')
    freeze=dict(status='VARIANT_TABLE_FROZEN_BEFORE_COMPRESSION',table_sha256=sha(HERE/'VARIANT_TABLE.md'),
        counts_sha256=sha(HERE/'VARIANT_COUNTS.json'),quick_inputs_sha256=sha(OUT/'QUICK_INPUTS.json'),
        selected_sources=30,selected_sources_with_usable_edits=changed,
        corpus_sha256=sha(ROOT/'var/results/hsw-st/certinsert_eval04_20261113/stage0/R_CORPUS.json'),
        capacity_file_sha256=sha(AT/'CAPACITY_INITIAL.json'),human_labels_received=0,paid_calls=0)
    (HERE/'VARIANT_TABLE_FREEZE.json').write_text(json.dumps(freeze,indent=2),encoding='utf8')
    print(json.dumps(freeze),flush=True)


if __name__=='__main__':main()
