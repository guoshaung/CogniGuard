"""Retain preregistered cases and explicitly distinguish method gain from info gain.

Secondary causal diagnostics are labeled post hoc, first-in-input-order; no
streams, scores, predictions or originally selected cases are changed.
"""
from experiments.c2rag_imperfect_forecast_20261027_01.common import *


def main():
    streams=read('events.json');rows=read('verified_rows.json');lookup={(r['stream_id'],r['method'],r['condition']):r for r in rows}
    original=read('selected_cases.json');out={}
    text=['# 案例归因补充（事后诊断，原三个预登记首例原样保留）\n',
      'Forecast方法胜过G不一定是新增预测信息有效；misleading条件下退步也不一定由误导造成。必须与同一流的Prior及其他提示条件比较。这里只对已冻结64条流作原因核查，不新增案例样本、不重跑方法、不更改原先选择。\n',
      '## 原三个案例的完整条件对照\n']
    for category,case in original.items():
        if case is None:continue
        sid=case['stream_id'];g=lookup[(sid,'G-Shared','baseline')]['utility']
        text.append(f'### {category} / {sid}\n\nG={g}。')
        for method in ['Simple','A2']:
            values={c:lookup[(sid,method+'-Forecast',c)]['utility'] for c in ['none','weak','strong','misleading']}
            prior=lookup[(sid,method+'-Prior','prior')]['utility']
            text.append(f'- {method}: Prior={prior}；四提示={values}。')
        if '-uniform-' in sid:text.append('此流公开为uniform，所有提示与Prior的预测情景相同：方法差异只能归因于规划/有限情景，不是课程提示信息；其misleading标签不能单独证明误导的因果损失。')
    secondary={'first_incremental_information_gain':None,'first_mismatch_attributable_loss':None}
    for stream in streams:
        sid=stream['id'];g=lookup[(sid,'G-Shared','baseline')]['utility']
        for c in ['none','weak','strong','misleading']:
            for method in ['Simple','A2']:
                value=lookup[(sid,method+'-Forecast',c)]['utility'];prior=lookup[(sid,method+'-Prior','prior')]['utility']
                if secondary['first_incremental_information_gain'] is None and value>g and value>prior:
                    secondary['first_incremental_information_gain']={'stream_id':sid,'condition':c,'method':method,'G':g,'Forecast':value,'Prior':prior}
                if c=='misleading' and secondary['first_mismatch_attributable_loss'] is None and value<g and value<lookup[(sid,method+'-Forecast','none')]['utility']:
                    secondary['first_mismatch_attributable_loss']={'stream_id':sid,'condition':c,'method':method,'G':g,'Forecast':value,'none':lookup[(sid,method+'-Forecast','none')]['utility']}
    for category,case in secondary.items():
        if case is None:text.append(f'## {category}\n\n未出现。');continue
        sid=case['stream_id'];c=case['condition'];method=case['method']
        configs=[('G-Shared','baseline'),(method+'-Prior','prior'),(method+'-Forecast','none'),(method+'-Forecast',c),('OPT','oracle')]
        traces={m+'/'+cc:read(f'traces/{sid}__{m}__{cc}.json') for m,cc in configs}
        out[category]=case|{'post_hoc_first_order_diagnostic':True,'traces':traces,'packets':read(f'forecasts/{sid}__{c}.json')}
        text+=[f'## {category}（补充首例）\n',str(case),
          '\n|步|问题|G实际回答|Prior实际回答|none实际回答|该条件实际回答|\n|---|---|---|---|---|---|']
        for t in range(8):
            keys=[m+'/'+cc for m,cc in configs[:4]]
            text.append(f'|{t+1}|{traces[keys[0]]["steps"][t]["query"]}|'+
                        '|'.join(traces[k]['steps'][t]['actual_reply'] or 'EMPTY（拒答）' for k in keys)+'|')
    text+=['\n## 全分母的提示增量\n',
       '同一64条需求流，strong−none：Simple +5，A2 +5；misleading−none：Simple −14，A2 −21。uniform流严格0差异，全部提示增量来自biased流。',
       '强提示Forecast−Prior的+12/+6包含“none−Prior”的+7/+1和“strong−none”的+5/+5。因此不能把全部Forecast−Prior收益都写成课程提示本身的收益。原始三个首例及全部退步仍保留。']
    write('CASE_ATTRIBUTION.md','\n'.join(text));write('case_attribution_appendix.json',out)
    # Preserve original report draft when adding this material qualification.
    p=OUT/'RESULT.md';original_bytes=p.read_bytes();(OUT/'RESULT.initial.md').open('xb').write(original_bytes)
    addition='\n\n## 案例标签与信息增量的归因校正\n\n原预登记三个首例按机械谓词选择，均落在uniform流；故第1例Forecast>G不能证明新增提示信息，第3例misleading下退步也不是误导本身的因果证据。原案例不替换。CASE_ATTRIBUTION.md另列明确标记为事后诊断的最早“Forecast同时超过G与Prior”和“misleading同时低于G与none”案例，并保存完整实际回答。全64流strong−none仅+5/+5；misleading−none为−14/−21。将这部分与规划自身的收益/损失分开。\n'
    p.write_bytes(original_bytes+addition.encode('utf8'))
    write('reporting_correction.json',{'reason':'case label does not imply causal prediction benefit; append controlled condition comparisons',
        'backup':'RESULT.initial.md','inputs_scores_predictions_or_selected_cases_changed':False,'secondary_selection_post_hoc':True})
    print(secondary)


if __name__=='__main__':main()
