"""Separate expanded-pool estimates, including observation overlap; no new trials."""
from common_adjusted import *
import collections, math, numpy as np

def summarize(rows):
    valid=[r for r in rows if isinstance(r.get('detected'),bool)]
    groups=collections.defaultdict(list)
    for r in valid: groups[r['cluster']].append(r['detected'])
    k=sum(r['detected'] for r in valid);n=len(valid);ci=None;wilson=None
    if n:
        rng=np.random.default_rng(2026111206)
        a=np.array([[sum(v),len(v)] for v in groups.values()])
        s=a[rng.integers(len(a),size=(2000,len(a)))].sum(1)
        ci=np.quantile(s[:,0]/s[:,1],[.025,.975]).tolist()
        z=1.959963984540054;p=k/n;den=1+z*z/n
        c=(p+z*z/(2*n))/den;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
        wilson=[c-h,c+h]
    return dict(k=k,n=n,unknown=len(rows)-n,source_clusters=len(groups),cluster_bootstrap95=ci,descriptive_wilson95=wilson)

def main():
    d=O/'delivery_P1_expanded';d.mkdir(exist_ok=False)
    raw=[read(p) for p in (O/'P1_expanded/scores').glob('*.json')]
    result=read(O/'P1_expanded/RESULT.json');obs=read(O/'data_expanded/OBSERVATIONS.json')
    fc=read(O/'delivery_P3_P4/figure_counts.json')
    fc['attack_phases']={'initial_T4_N10':read(O/'P1/RESULT.json')['counts'],'expanded_T4_T5':result['counts']}
    fc['meta']['attack_primary_phase']='expanded_T4_T5; initial phase retained separately, not pooled'
    fc['attack_observation_availability']=obs
    public=read(O/'data_expanded/PUBLIC_OUTPUTS.json')
    fc['attack_pool_zero_insertion_outputs']={method:dict(k=sum(read(Path(x['record_path'])).get('inserted_entries')==0 for x in items),n=len(items)) for method,items in public.items()}
    fc['scrubbing_observation_overlap']={}
    for method in ['CertInsert','RC']:
        fc['scrubbing_observation_overlap'][method]={}
        for N in [10,50,200]:
            for m in [4,8]:
                label=f'N{N}_m{m}';cell=result['counts'][method][label]
                for attack in ['spoofing','scrubbing']:
                    v=cell[attack]
                    fc[attack][method][label]=None if v is None else {k:v[k] for k in ['k','n']}
                rr=[r for r in raw if r['method']==method and r['N']==N and r['m']==m and r['attack']=='scrubbing']
                fc['scrubbing_observation_overlap'][method][label]={
                    'overlap':summarize([r for r in rr if r['observation_overlap']]),
                    'disjoint':summarize([r for r in rr if not r['observation_overlap']])} if rr else None
    fc['spoofing_unmodified_controls']=read(O/'P1_unmodified_controls/RESULT.json')
    put(d/'figure_counts.json',fc)
    put(d/'COUNTS.json',dict(all=result,overlap=fc['scrubbing_observation_overlap']))
    lines=['# P1：扩展公开输出池的频率攻击','','本阶段使用T4与T5合并后的公开输出；与已归档T4-only N10分别报告，不合并重复目标。','', '|方法|观察N|前m短语|伪造接受 k/n|擦除后检出 k/n|', '|---|---|---|---|---|']
    def fmt(v): return 'NOT_AVAILABLE' if v is None else f"{v['k']}/{v['n']}"
    for method in ['CertInsert','RC']:
        for N in [10,50,200]:
            for m in [4,8]:
                c=result['counts'][method][f'N{N}_m{m}']
                lines.append(f"|{method}|{N}|{m}|{fmt(c['spoofing'])}|{fmt(c['scrubbing'])}|")
    lines+=['',f"公开输出池中零插入即达到预测目标的数量：{json.dumps(fc['attack_pool_zero_insertion_outputs'])}；它们保持原分母，不称作新嵌入的水印信号。",'每格的源文本聚类bootstrap95%区间见COUNTS.json；零事件的退化bootstrap区间不能证明总体零风险。','区间条件于本轮固定密钥、固定观察样本和学得短语，不包含跨密钥或重新训练攻击器的不确定性。','擦除目标可能与观察输出重叠，重叠与未观察子组分别报告；材料不足的N不以较小N冒充。','攻击只用公开句首频率，不读取密钥、真实插入位置或私有选词列表；真实检测在攻击文本冻结之后进行。','200篇伪造目标未攻击时，两方法均0/200。主动接受率不可由自然背景低误报抵消。','伪造只证明冻结统计检测可被公开频率攻击影响，不证明伪造文本知识正确或具有合法发行身份。','CertInsert与RC的差异不是锚点保护的独立因果效应：学得词成本、可插位置及预测容量不同。']
    (d/'RESULT.md').write_text('\n'.join(lines),encoding='utf8')
    import csv
    fields=sorted({k for r in raw for k in r})
    with (d/'per_item.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in raw)
    parsed=list(csv.DictReader((d/'per_item.csv').open(encoding='utf-8-sig')))
    for method in ['CertInsert','RC']:
        for N in [10,50,200]:
            for m in [4,8]:
                for a in ['spoofing','scrubbing']:
                    rr=[r for r in parsed if r['method']==method and r['N']==str(N) and r['m']==str(m) and r['attack']==a and r['detected'] in ['True','False']]
                    expected=fc[a][method][f'N{N}_m{m}']
                    assert (dict(k=sum(r['detected']=='True' for r in rr),n=len(rr)) if rr else None)==expected
    put(d/'INDEPENDENT_VALIDATION.json',dict(PASS=True,rows=len(parsed),source='serialized per_item.csv'))

if __name__=='__main__':main()
