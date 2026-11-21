"""Full-denominator paired summaries and preregistered first cases, no reruns."""
from collections import Counter,defaultdict
import csv
import math
import statistics
import time
from experiments.c2rag_imperfect_forecast_20261027_01.common import *


def csvfile(n,rows):
    with (OUT/n).open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    deadline();frozen();streams=read('events.json');rows=read('verified_rows.json');banks=read('public/banks.json')
    lookup={(r['stream_id'],r['method'],r['condition']):r for r in rows}
    gold={r['stream_id']:r for r in read('private/generation_gold.json')}
    quality=[];ql={};conditions=['none','weak','strong','misleading']
    for stream in streams:
        sid=stream['id'];actual=[e['qid'] for e in stream['requests']];k=len(banks[stream['structure']]['queries'])
        for c in ['prior']+conditions:
            packets=read(f'forecasts/{sid}__{c}.json');nll=[];brier=[];correct=[]
            for t in range(7):
                p=packets[t]['next_type_probabilities'];truth=actual[t+1]
                nll.append(-math.log(p[truth]));brier.append(sum((p[j]-int(j==truth))**2 for j in range(k)))
                correct.append(int(max(range(k),key=lambda j:p[j])==truth))
            hint=gold[sid]['hints'].get(c)
            q={'stream_id':sid,'structure':stream['structure'],'family':stream['family'],'condition':c,
               'next_predictions':7,'mean_logloss':sum(nll)/7,'mean_brier':sum(brier)/7,
               'argmax_accuracy':sum(correct)/7,'hint_matches_mode':None if c=='prior' else int(hint==gold[sid]['hidden_mode'])}
            quality.append(q);ql[(sid,c)]=q
    enriched=[]
    for r in rows:
        sid=r['stream_id'];g=lookup[(sid,'G-Shared','baseline')]['utility'];r=r.copy()
        r['delta_G']=r['utility']-g
        prior='Simple-Prior' if r['method'].startswith('Simple') else 'A2-Prior'
        r['delta_corresponding_Prior']=r['utility']-lookup[(sid,prior,'prior')]['utility'] if 'Forecast' in r['method'] else None
        r['A2_minus_Simple']=r['utility']-lookup[(sid,'Simple-Forecast',r['condition'])]['utility'] if r['method']=='A2-Forecast' else None
        q=ql.get((sid,r['condition']))
        r['next_logloss']=q['mean_logloss'] if q else None;r['next_brier']=q['mean_brier'] if q else None
        enriched.append(r)
    csvfile('per_stream.csv',enriched);csvfile('prediction_quality.csv',quality)
    comparison=[]
    def paired(ss,m,c,baseline,bc):
        delta=[lookup[(s['id'],m,c)]['utility']-lookup[(s['id'],baseline,bc)]['utility'] for s in ss]
        return {'delta':sum(delta),'wins':sum(x>0 for x in delta),'ties':sum(x==0 for x in delta),'losses':sum(x<0 for x in delta)}
    def total(ss,m,c):return sum(lookup[(s['id'],m,c)]['utility'] for s in ss)
    aggregate=[]
    for structure in ['kinetic','T06']:
        for family in ['uniform','biased']:
            ss=[s for s in streams if s['structure']==structure and s['family']==family]
            for c in conditions:
                x={'structure':structure,'family':family,'condition':c,'streams':16,'requests':128,
                   'G':total(ss,'G-Shared','baseline'),'Simple_Prior':total(ss,'Simple-Prior','prior'),
                   'A2_Prior':total(ss,'A2-Prior','prior'),'Simple':total(ss,'Simple-Forecast',c),
                   'A2':total(ss,'A2-Forecast',c),'Oracle':total(ss,'A2-Oracle','oracle'),'OPT':total(ss,'OPT','oracle')}
                x['Simple_minus_G']=x['Simple']-x['G'];x['A2_minus_G']=x['A2']-x['G']
                x['Simple_minus_Prior']=x['Simple']-x['Simple_Prior'];x['A2_minus_Prior']=x['A2']-x['A2_Prior']
                x['A2_minus_Simple']=x['A2']-x['Simple'];x['Simple_gap_OPT']=x['OPT']-x['Simple'];x['A2_gap_OPT']=x['OPT']-x['A2']
                aggregate.append(x)
                for m in ['Simple-Forecast','A2-Forecast']:
                    for b,bc in [('G-Shared','baseline'),('Simple-Prior' if m.startswith('Simple') else 'A2-Prior','prior')]:
                        comparison.append({'structure':structure,'family':family,'condition':c,'method':m,'baseline':b,**paired(ss,m,c,b,bc)})
                comparison.append({'structure':structure,'family':family,'condition':c,'method':'A2-Forecast','baseline':'Simple-Forecast',**paired(ss,'A2-Forecast',c,'Simple-Forecast',c)})
    csvfile('stratified_results.csv',aggregate);csvfile('paired_comparisons.csv',comparison)
    overall=[]
    for c in conditions:
        x={'condition':c,'G':total(streams,'G-Shared','baseline'),'SimplePrior':total(streams,'Simple-Prior','prior'),
           'A2Prior':total(streams,'A2-Prior','prior'),'Simple':total(streams,'Simple-Forecast',c),'A2':total(streams,'A2-Forecast',c),
           'Oracle':total(streams,'A2-Oracle','oracle'),'OPT':total(streams,'OPT','oracle'),
           'Simple_vs_G':paired(streams,'Simple-Forecast',c,'G-Shared','baseline'),
           'A2_vs_G':paired(streams,'A2-Forecast',c,'G-Shared','baseline'),
           'Simple_vs_Prior':paired(streams,'Simple-Forecast',c,'Simple-Prior','prior'),
           'A2_vs_Prior':paired(streams,'A2-Forecast',c,'A2-Prior','prior'),
           'A2_vs_Simple':paired(streams,'A2-Forecast',c,'Simple-Forecast',c)}
        overall.append(x)
    write('overall_results.json',overall)
    # Input-order selection, never best-looking gain or largest loss.
    selected={k:None for k in ['first_forecast_gain','first_A2_simple_difference','first_misleading_loss']}
    for s in streams:
        sid=s['id']
        for c in conditions:
            for m in ['Simple-Forecast','A2-Forecast']:
                r=lookup[(sid,m,c)];g=lookup[(sid,'G-Shared','baseline')]
                if selected['first_forecast_gain'] is None and r['utility']>g['utility']:
                    selected['first_forecast_gain']={'stream_id':sid,'condition':c,'qualifying_method':m}
                if selected['first_A2_simple_difference'] is None and lookup[(sid,'A2-Forecast',c)]['utility']!=lookup[(sid,'Simple-Forecast',c)]['utility']:
                    selected['first_A2_simple_difference']={'stream_id':sid,'condition':c,'qualifying_method':'A2-Forecast'}
                if c=='misleading' and selected['first_misleading_loss'] is None and r['utility']<g['utility']:
                    selected['first_misleading_loss']={'stream_id':sid,'condition':c,'qualifying_method':m}
    case_text=['# 三个预登记首例\n\n按冻结stream顺序、提示none/weak/strong/misleading、方法Simple/A2顺序；不是最大增益挑选。JSON保存完整候选分数/rollout/菜单及实际文本。\n']
    cases={}
    for category,sel in selected.items():
        if sel is None:case_text.append(f'## {category}\n\n未出现。\n');cases[category]=None;continue
        sid=sel['stream_id'];c=sel['condition'];s=next(x for x in streams if x['id']==sid)
        configs=[('G-Shared','baseline'),('Simple-Prior','prior'),('A2-Prior','prior'),('Simple-Forecast',c),('A2-Forecast',c),('A2-Oracle','oracle'),('OPT','oracle')]
        ts={m:read(f'traces/{sid}__{m}__{cc}.json') for m,cc in configs}
        cases[category]=sel|{'stream':s,'gold_evaluation_only':gold[sid],'traces':ts,'packets':read(f'forecasts/{sid}__{c}.json')}
        case_text+=[f'## {category}: {sid} / {c}\n',
          f'触发方法{sel["qualifying_method"]}；任务数：'+', '.join(f'{m}={ts[m]["summary"]["utility"]}' for m,_ in configs)+'。',
          f'实际题型序列{[e["qid"] for e in s["requests"]]}。隐藏模式{gold[sid]["hidden_mode"]}、提示{gold[sid]["hints"][c]}仅用于此事后解释，不提供给控制器。',
          '\n|步/接收者|当前问题|G实际回答|Simple实际回答|A2实际回答|预测未来次数均值|\n|---|---|---|---|---|---|']
        for t in range(8):
            packet=cases[category]['packets'][t];count=Counter(q for sc in packet['scenarios'] for q in sc)
            case_text.append(f'|{t+1}/r{t}|{ts["G-Shared"]["steps"][t]["query"]}|'+
                '|'.join(ts[m]['steps'][t]['actual_reply'] or 'EMPTY（拒答）' for m in ['G-Shared','Simple-Forecast','A2-Forecast'])+
                '|'+str({q:count[q]/32 for q in range(len(banks[s['structure']]['queries']))})+'|')
        case_text.append('\n完整对照（含Prior/Oracle/OPT）与所有当前候选分数：selected_cases.json。\n')
    write('selected_cases.json',cases);write('CASES.md','\n'.join(case_text))
    # Cost is one measured run; OPT search reported separately from selection replay.
    timing=[]
    for m,c in sorted({(r['method'],r['condition']) for r in rows}):
        subset=[r for r in rows if r['method']==m and r['condition']==c]
        values=[r['decision_wall_ms']/8 for r in subset]
        timing.append({'method':m,'condition':c,'streams':64,'total_decision_ms':sum(r['decision_wall_ms'] for r in subset),
           'mean_ms_per_request':statistics.mean(values),'median_stream_mean_ms':statistics.median(values),
           'definition':'decision scoring only; excludes init/forecast generation/independent verification; OPT search separately'})
    csvfile('decision_cost.csv',timing)
    pq=[]
    for structure in ['kinetic','T06']:
        for family in ['uniform','biased']:
            for c in ['prior']+conditions:
                qs=[q for q in quality if q['structure']==structure and q['family']==family and q['condition']==c]
                pq.append({'structure':structure,'family':family,'condition':c,'streams':16,'predictions':112,
                    'logloss':statistics.mean(q['mean_logloss'] for q in qs),'brier':statistics.mean(q['mean_brier'] for q in qs),
                    'accuracy':statistics.mean(q['argmax_accuracy'] for q in qs),
                    'hint_matches':None if c=='prior' else sum(q['hint_matches_mode'] for q in qs)})
    csvfile('prediction_quality_stratified.csv',pq)
    scope=[]
    for st in ['kinetic','T06']:
        for fam in ['uniform','biased']:
            ss=[s for s in streams if s['structure']==st and s['family']==fam]
            scope.append({'structure':st,'family':fam,'G':total(ss,'G-Shared','baseline'),'OPT':total(ss,'OPT','oracle'),
                'positive_gap_streams':sum(lookup[(s['id'],'OPT','oracle')]['utility']>lookup[(s['id'],'G-Shared','baseline')]['utility'] for s in ss),
                'unique_actual_type_sequences':len({tuple(e['qid'] for e in s['requests']) for s in ss})})
    write('workload_scope.json',scope)
    lines=['# RESULT · 不完美预测下的前瞻释放\n',
      '**Q1：本批受控合成负载中，未来信息有局部价值且有失配风险。Q2：A2未整体超过强Simple；没有证据支持为本批结构增加复杂规划。** 全64条流/832次方法运行完成，0越权、0 UNKNOWN，所有OPT经独立全计划枚举认证。\n',
      'SYNTHETIC / EXPLORATORY。2个既有知识结构，非64份独立知识资产；每结构32条外生需求流，四提示条件复用同一实际流。每条件每方法512请求；不同方法/提示/情景不作额外独立样本。本报告不作真实课堂收益或创新性主张。\n',
      '## 总体主结果（每行同一64条流、512请求）\n',
      '|提示|G|Simple-Prior|Simple-Forecast|A2-Prior|A2-Forecast|A2−Simple|Oracle|OPT|\n|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for x in overall:lines.append(f'|{x["condition"]}|{x["G"]}|{x["SimplePrior"]}|{x["Simple"]}|{x["A2Prior"]}|{x["A2"]}|{x["A2"]-x["Simple"]}|{x["Oracle"]}|{x["OPT"]}|')
    lines+=['所有在线方法的完成数对应拒答=512−完成数；全部实际字节和拒答逐流见per_stream.csv。不能把四行相加当作2048条独立请求证据。',
      '\n|提示|Simple−G（胜/平/负）|Simple−Prior（胜/平/负）|A2−G（胜/平/负）|A2−Prior（胜/平/负）|A2−Simple（胜/平/负）|\n|---|---|---|---|---|---|']
    for x in overall:
        vals=[]
        for k in ['Simple_vs_G','Simple_vs_Prior','A2_vs_G','A2_vs_Prior','A2_vs_Simple']:
            d=x[k];vals.append(f'{d["delta"]:+d} ({d["wins"]}/{d["ties"]}/{d["losses"]})')
        lines.append('|'+x['condition']+'|'+'|'.join(vals)+'|')
    lines+=['\n## 离线空间与零空间分母\n',
      '|结构/分布|G/128|OPT/128|有空间流/16|不同题型序列数/16|\n|---|---:|---:|---:|---:|']
    for x in scope:lines.append(f'|{x["structure"]}/{x["family"]}|{x["G"]}|{x["OPT"]}|{x["positive_gap_streams"]}|{x["unique_actual_type_sequences"]}|')
    lines+=['重复序列是独立随机流可能产生的相同结果，全部保留不去重、不视为新知识结构。kinetic两类结构仍有OPT=max(n_m,n_v)的简单解释；T06原三元组保护和N/C两解法不变。本批跨题16请求只作历史回归，未混进512请求分母。',
      '\n## 按结构、分布与提示分层（每行128请求）\n',
      '|结构/分布|提示|G|Simple|ΔG/ΔPrior|A2|ΔG/ΔPrior|A2−Simple|Simple/A2距OPT|\n|---|---|---:|---:|---|---:|---|---:|---|']
    for x in aggregate:lines.append(f'|{x["structure"]}/{x["family"]}|{x["condition"]}|{x["G"]}|{x["Simple"]}|{x["Simple_minus_G"]:+d}/{x["Simple_minus_Prior"]:+d}|{x["A2"]}|{x["A2_minus_G"]:+d}/{x["A2_minus_Prior"]:+d}|{x["A2_minus_Simple"]:+d}|{x["Simple_gap_OPT"]}/{x["A2_gap_OPT"]}|')
    lines+=['逐层胜平负全部见paired_comparisons.csv。没有只统计OPT>G、预测正确或获胜子集。未做置信区间或显著性推断；若以后重采样必须以需求流为配对单位，而非预测情景或方法运行。',
      '\n## 预测质量：真实下一请求，112次预测/分层\n',
      '|结构/分布|提示|LogLoss↓|Brier↓|argmax准确率|提示命中隐藏模式/16|\n|---|---|---:|---:|---:|---:|']
    for x in pq:lines.append(f'|{x["structure"]}/{x["family"]}|{x["condition"]}|{x["logloss"]:.4f}|{x["brier"]:.4f}|{x["accuracy"]:.3f}|{x["hint_matches"] if x["hint_matches"] is not None else "NA"}|')
    lines+=['.5/.9是“采用真模式，否则独立均匀”的混合概率，理论模式命中还含随机回落命中的概率；不是下一题预测准确率。misleading用不同真实机制生成、却按strong似然更新，故是明确模型失配。公开uniform模式已知时所有条件与Prior情景逐字相同，新增提示收益严格0；biased的none仍通过前缀学习，并保留潜在主题导致的未来相关性，不能当固定iid prior。Forecast−Prior同时包含机制建模/前缀/提示信息，不能全归因于课程提示。\n',
      '## Q1与Q2机制判断\n',
      '强提示下Simple=371/512（G360，+11；Simple-Prior359，+12）；A2=365（G+5；A2-Prior359，+6）。最清晰局部为T06/biased：Simple与A2均113/128，G108；对各自Prior分别+11/+4。uniform流Simple/A2的条件差异为0，任何相对G收益属于规划/有限情景效应，不是提示预测有效。',
      '同信息强条件A2整体低于Simple6次；T06/uniform低10，T06/biased相等。kinetic/uniform A2比Simple多4，但这也在固定Prior中出现，且已知只有二类计数结构；不能据此声称高阶联合规划创新。32条Monte Carlo计数和重规划可能产生等待与有限样本偏差，A2的空答后G rollout与Simple固定菜单承诺是不同的基策略。保留此局部差异，未换种子或增加情景数使它消失。',
      'Oracle=384仍低于OPT397，说明即便准确知道后缀，一步候选加后续安全G也非普遍最优（kinetic/biased差2，T06/uniform差9、biased差2）。这是冻结rollout基础策略的限制；不能把它解释成预测错误，也不支持直接训练更大预测器解决全部差距。',
      '误导条件Simple352、A2339，比G分别−8/−21；比对应Prior分别−7/−20。未删退步流。预测误差有真实服务损失，不能把R32的30%理想信息空间写成实际收益。',
      '\n## 决策开销（一次本机CPU执行，不是系统基准）\n',
      '|方法/提示|总决策毫秒|平均毫秒/请求|\n|---|---:|---:|']
    for x in timing:lines.append(f'|{x["method"]}/{x["condition"]}|{x["total_decision_ms"]:.2f}|{x["mean_ms_per_request"]:.4f}|')
    optsearch=sum(read(f'opt/{s["id"]}.json')['wall_ms'] for s in streams)
    lines.append(f'OPT枚举另耗{optsearch:.2f}ms；上表OPT只为已求得计划的执行选择，不应伪称OPT比在线方法快。决策计时排除初始化、预测生成、ExactK3提交核对和独立评分；含本方法菜单/rollout与安全缓存。真实输出字节在per_stream.csv，模型/付费API成本0。\n')
    lines+=['## 完整首例与复核\n',
      '预登记顺序选出的三个案例：'+str(selected)+'。详见CASES.md及selected_cases.json；不存在的类别会留空，未另造例。',
      '832次方法、6656实际步骤经独立真实文本评分，612352联盟前缀检查，0越权/0 UNKNOWN。全部64个OPT由独立set全计划穷举复核；T06全部128字段组合的精确方程与反世界一致，涵盖重新分配接收者后的N/C混合。独立规划核验重算2560次菜单决策、3072次A2/Oracle决策及5368个候选rollout得分，全部一致。',
      '历史回归中原Shared持久视图无风险、原Reset第13步起观察者仍有风险，证明没有把观察者随题清空；这是旧构造回归，不是生产系统漏洞发现。',
      '\n## 信息隔离修复与限制\n',
      '初版forecast批处理进程读取一个含所有时刻前缀的文件，虽然纯packet函数仅使用当前行，文件级时序边界不够严格。工程修复改为每流/条件独立进程：父调度器只在收到当前预测后才发送下一前缀，子进程禁止读取所有证据文件。320进程重新生成2560包，全部字段与原情景/哈希逐字相同；原文件和方法轨迹保留，不需要选择更好结果或改配置重跑。详见repairs/forecast_information_boundary.json；该修复不改变Bayes模型、种子或方法。',
      '本轮没有真实预测器训练、没有新数据/模型安装、没有生产或历史修改。合成latent机制、独立随机数和提示可信度预先公开；候选语义是作者契约，非自动自然语言抽取验证。权限和重构判据模拟实例资产，不等于真实版权限制；未建模拒答/时延等额外推断侧信道。',
      '\n## 下一步唯一判断\n',
      '**保留强Simple作为默认研究基线，优先检查预测可信度校准及失配退化；本批证据不足以增加复杂A2规划。** 这是受控合成机制中的局部判断，不否认其他负载的预测性释放。Oracle尚有G rollout局限，但先保留简单策略并解释其失配，不自动训练、调lambda、扩量或排下一轮。\n']
    write('RESULT.md','\n'.join(lines))
    write('PROTOCOL_IMPLEMENTATION_NOTE.md','原PROTOCOL与冻结配置保持不变。补强了预测文件级时序隔离：由批处理纯函数改为逐步stdin请求/响应、每流每提示独立进程。所有2560预测包严格相同，因此没有候选/种子/分布/方法输出变化，原始证据全部保留。此为工程信息边界修复，不是新的预测模型或调参。\n')
    write('REPRODUCE.md','''# 复现

在新的独立副本设置common.OUT，避免覆盖既有产物；固定前序Git提交和本地原始材料不变。

1. .venv-langgraph/Scripts/python.exe -B -m experiments.c2rag_imperfect_forecast_20261027_01.prepare
2. run.cmd test experiments/c2rag_imperfect_forecast_20261027_01/test_methods.py -q
3. .venv/Scripts/python.exe -B -m experiments.c2rag_imperfect_forecast_20261027_01.verify_math
4. .venv-langgraph/Scripts/python.exe -B -m experiments.c2rag_imperfect_forecast_20261027_01.forecast
5. .venv-langgraph/Scripts/python.exe -B -m experiments.c2rag_imperfect_forecast_20261027_01.reverify_forecasts
6. .venv-langgraph/Scripts/python.exe -B -m experiments.c2rag_imperfect_forecast_20261027_01.execute
7. .venv-langgraph/Scripts/python.exe -B -m experiments.c2rag_imperfect_forecast_20261027_01.verify
8. .venv-langgraph/Scripts/python.exe -B -m experiments.c2rag_imperfect_forecast_20261027_01.verify_planning
9. .venv-langgraph/Scripts/python.exe -B -m experiments.c2rag_imperfect_forecast_20261027_01.report

common.START/DEADLINE是本次固定120分钟窗口，新复现实验需用户新授权窗口，不自动续期。上述命令不是本轮自动重跑入口；所有输出拒绝覆盖，execute仅可同配置续跑尚未完成的trace。无需GPU/模型/API/安装。预测器stdin隔离修复后所有预测与原批处理相同。同步包为数据证据，CG源代码和baseline snapshots保留本地并有hash，不冒称GitHub包自包含运行环境。
''')
    write('decision.json',{'decision':'ANALYZE_KEEP_SIMPLE_PRIORITIZE_CALIBRATION','complete':True,'streams':64,'model_calls':0,
        'G':360,'OPT':397,'strong_Simple':371,'strong_A2':365,'misleading_Simple':352,'misleading_A2':339,
        'Q1':'limited synthetic value of imperfect future information; mismatch losses retained',
        'Q2':'no aggregate A2 advantage over strong same-information menu baseline; local differences retained',
        'next_unique_recommendation':'retain Simple and diagnose hint calibration/model mismatch; no next run started',
        'novelty_claim':False,'stopped_after_delivery':True})
    write('FAILURES_AND_REPAIRS.json',{'execution_failures':[],
       'forecast_boundary_repair':'repairs/forecast_information_boundary.json; all packets identical; no method result overwritten',
       'parameter_search':False,'independent_checks_passed':True,'global_start_epoch':START,'deadline_epoch':DEADLINE,
       'reported_at_epoch':time.time(),'remaining_seconds':DEADLINE-time.time()})
    write('README.md','# 不完美预测前瞻释放证据\n\nSYNTHETIC/EXPLORATORY。先读RESULT.md，冻结PROTOCOL.md，全部per_stream.csv与分层CSV，CASES.md及selected_cases.json，forecasts/与traces/完整数据，独立核验JSON及信息隔离修复记录。两个结构、64条需求流，模型/GPU/API/训练0。已停止，不自动排下一轮。\n')
    print(json.dumps({'overall':[{k:x[k] for k in ['condition','G','Simple','A2','OPT']} for x in overall],
                     'selected':selected,'scopes':scope},ensure_ascii=False))


if __name__=='__main__':main()
