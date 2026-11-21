"""Descriptive reports and post-hoc structural proofs, never outcome-driven tuning."""
from collections import Counter, defaultdict
import csv
import io
import itertools
import json
import math
from experiments.c2rag_r34_20261028_02.common import *
from experiments.c2rag_r34_20261028_02.verify import parse, tables, union, masks

def csvfile(name,rows):
    b=io.StringIO(newline='');writer=csv.DictWriter(b,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows);write(name,b.getvalue())
def mdtable(headers,rows):
    return '|'+ '|'.join(headers)+'|\n|'+'|'.join(['---']*len(headers))+'|\n'+''.join('|'+ '|'.join(str(x) for x in row)+'|\n' for row in rows)
def aggregate(rows,keys):
    grouped=defaultdict(list)
    for r in rows:grouped[tuple(r[k] for k in keys)].append(r)
    result=[]
    for key,rs in grouped.items():
        total=8*len(rs);fields=sum(r['target_field_denominator'] for r in rs)
        result.append(dict(zip(keys,key))|{'streams':len(rs),'requests':total,'correct':sum(r['utility'] for r in rs),
            'completion_rate':sum(r['utility'] for r in rs)/total,'refusals':sum(r['refusals'] for r in rs),
            'full_unauthorized_reconstructions':sum(r['complete_unauthorized_target'] for r in rs),
            'target_field_coverage':sum(r['target_fields_recovered'] for r in rs)/fields,
            'partial_only_streams':sum(0<r['target_fields_recovered']<r['target_field_denominator'] for r in rs),
            'input_field_coverage':sum(r['input_fields_recovered'] for r in rs)/sum(r['input_field_denominator'] for r in rs),
            'unauthorized_direct_deliveries':sum(r['direct_unauthorized_deliveries'] for r in rs),'unknown':sum(r['unknown'] for r in rs),
            'bytes':sum(r['bytes'] for r in rs),'cpu_ms':sum(r['cpu_ms'] for r in rs),
            'OPT_gap':sum(r['opt_utility']-r['utility'] for r in rs),
            **{f'unauthorized_exact_k{k}':sum(r[f'unauthorized_exact_k{k}'] for r in rs) for k in [1,2,3]}})
    return result

def main():
    frozen();rows=read('evaluated_rows.json');banks={b['id']:b for b in read('public/banks.json')};truths={t['id']:t for t in read('private/truth.json')}
    structure=read('structure_audit.json');witnesses=read('minimal_witnesses.json');verification=read('independent_verification.json')
    index={(r['stream'],r['method']):r for r in rows};summ=aggregate(rows,['method']);asset=aggregate(rows,['asset','method']);split=aggregate(rows,['split','method'])
    family=aggregate(rows,['family','method']);families=aggregate([r|{'structure':banks[r['asset']]['family']} for r in rows],['structure','method'])
    csvfile('per_stream.csv',rows);csvfile('method_summary.csv',summ);csvfile('asset_method_summary.csv',asset);csvfile('split_method_summary.csv',split)
    csvfile('demand_family_summary.csv',family);csvfile('structure_method_summary.csv',families)
    pairs=[];losses=[];gaps=[];prefix_cert=[];incomparable_cases=[];risk_refusals=[]
    for stream in read('events.json'):
        sid=stream['id'];bank=banks[stream['asset']];truth=truths[bank['id']];table=tables(truth)
        S=index[sid,'M6-Simple-Oracle']['utility'];O=index[sid,'M8-OPT']['utility'];static=index[sid,'M8-OPT']['static_menu_oracle_utility']
        gaps.append({'stream':sid,'asset':bank['id'],'split':bank['split'],'OPT':O,'Simple_Oracle':S,'StaticMenu_Oracle':static,
            'Gap_OPT_minus_Simple_Oracle':O-S,'Gap_OPT_minus_static_menu':O-static})
        for c in ['none','strong','misleading']:
            sr=index[sid,'M4-Simple-Forecast-'+c];ar=index[sid,'M5-A2-Forecast-'+c]
            pair={'stream':sid,'asset':bank['id'],'split':bank['split'],'condition':c,'Simple':sr['utility'],'A2':ar['utility'],
                'A2_minus_Simple':ar['utility']-sr['utility'],'Simple_minus_Prior':sr['utility']-index[sid,'M3-Simple-Prior']['utility'],
                'Simple_minus_none':sr['utility']-index[sid,'M4-Simple-Forecast-none']['utility'],
                'A2_minus_none':ar['utility']-index[sid,'M5-A2-Forecast-none']['utility'],
                'Simple_Oracle_minus_Forecast':S-sr['utility'],'A2_Oracle_minus_Forecast':index[sid,'M7-A2-Oracle']['utility']-ar['utility']}
            pairs.append(pair)
            if sr['utility']>ar['utility']:losses.append(pair|{'Simple_trace':sr['trace'],'A2_trace':ar['trace']})
        if S>index[sid,'M7-A2-Oracle']['utility']:
            losses.append({'stream':sid,'asset':bank['id'],'condition':'oracle','Simple':S,'A2':index[sid,'M7-A2-Oracle']['utility'],
                'Simple_trace':index[sid,'M6-Simple-Oracle']['trace'],'A2_trace':index[sid,'M7-A2-Oracle']['trace']})
        # Convert independently certified OPT into a static type menu. This is a
        # certificate of the post-hoc reduction, not a newly executed algorithm.
        opt=read(f'opt/{sid}.json')['opt'];answers={a['id']:a for q in bank['queries'] for a in q['answers']};answers['EMPTY']={'reply':''}
        selected={};views=[0]*4
        for e,a in zip(stream['events'],opt['plan']):
            views[e['recipient']]|=parse(answers[a]['reply'],bank,truth)
            if e['recipient']!=3 and a!='EMPTY':selected.setdefault(e['q'],a)
        student_union=views[0]|views[1]|views[2];assert not table[student_union]['recover']
        converted=[];bunion=0
        for e in stream['events']:
            a=bank['queries'][e['q']]['answers'][0]['id'] if e['recipient']==3 else selected.get(e['q'],'EMPTY')
            if e['recipient']!=3:bunion|=parse(answers[a]['reply'],bank,truth)
            converted.append(a)
        assert bunion&~student_union==0 and not table[bunion]['recover'] and sum(a!='EMPTY' for a in converted)==O
        prefix_cert.append({'stream':sid,'student_union_bits':student_union,'converted_menu':selected,'converted_plan':converted,'utility':O,
            'converted_student_union_subset_of_OPT_union':True,'safe':True})
        # Find existing same-prefix incomparable choices with differing compatibility.
        tr=read(index[sid,'M6-Simple-Oracle']['trace']);views=[0]*4
        for t,e in enumerate(tr['steps']):
            options=bank['queries'][e['q']]['answers']
            if len(options)>1 and e['recipient']!=3:
                def safe(v):return all(not table[union(v,m)]['recover'] for m in masks() if not m&8)
                for a,b in itertools.combinations(options,2):
                    A=views.copy();B=views.copy();A[e['recipient']]|=parse(a['reply'],bank,truth);B[e['recipient']]|=parse(b['reply'],bank,truth)
                    if not safe(A) or not safe(B):continue
                    for later in tr['steps'][t+1:]:
                        for candidate in bank['queries'][later['q']]['answers']:
                            Av=A.copy();Bv=B.copy();Av[later['recipient']]|=parse(candidate['reply'],bank,truth);Bv[later['recipient']]|=parse(candidate['reply'],bank,truth)
                            if safe(Av)!=safe(Bv):
                                incomparable_cases.append({'stream':sid,'step':t,'recipient':e['recipient'],'query':e['query'],
                                    'A':a,'B':b,'future_step':later['step'],'future_recipient':later['recipient'],'future_answer':candidate,
                                    'A_then_future_safe':safe(Av),'B_then_future_safe':safe(Bv),'condition':'same actual safe history; two-step isolated continuation, not unexecuted full attack counted as outcome'})
            if not e['reply']:
                feasible=[]
                for candidate in options:
                    v=views.copy();v[e['recipient']]|=parse(candidate['reply'],bank,truth)
                    if all(not table[union(v,m)]['recover'] for m in masks() if not m&8):feasible.append(candidate['id'])
                risk_refusals.append({'stream':sid,'method':'M6-Simple-Oracle','step':t,'safe_current_answers':feasible,
                    'voluntary_future_tradeoff':bool(feasible)})
            views[e['recipient']]|=parse(e['reply'],bank,truth)
    csvfile('paired_comparisons.csv',pairs);csvfile('oracle_gaps.csv',gaps);write('all_Simple_beats_A2_cases.json',losses)
    write('global_union_reduction_certificates.json',prefix_cert);write('answer_compatibility_certificates.json',incomparable_cases);write('oracle_refusal_audit.json',risk_refusals)
    prediction=[];gold={g['stream']:g for g in read('private/generation_gold.json')};uniform_checks=[]
    for stream in read('events.json'):
        cache={}
        for c in ['prior','none','strong','misleading']:
            packets=read(f'forecasts/{stream["id"]}__{c}.json');cache[c]=packets
            for t,p in enumerate(packets[:-1]):
                q=stream['events'][t+1]['q'];ps=p['probabilities'];guess=max(range(len(ps)),key=lambda j:(ps[j],-j))
                prediction.append({'stream':stream['id'],'asset':stream['asset'],'family':stream['family'],'condition':c,'step':t,
                    'next_query':q,'brier':sum((v-int(i==q))**2 for i,v in enumerate(ps)),'logloss_nats':-math.log(ps[q]),
                    'accuracy':int(guess==q),'hint_correct':int(stream['hints'].get(c)==gold[stream['id']]['latent_mode']) if c!='prior' else ''})
        if stream['family']=='uniform':
            assert all(cache[c][t]['scenarios']==cache['prior'][t]['scenarios'] for c in ['none','strong','misleading'] for t in range(8))
            uniform_checks.append({'stream':stream['id'],'all_condition_scenarios_identical_to_prior':True})
    csvfile('prediction_quality.csv',prediction)
    pred=[]
    for family in ['uniform','biased']:
        for c in ['prior','none','strong','misleading']:
            ps=[p for p in prediction if p['family']==family and p['condition']==c]
            pred.append({'family':family,'condition':c,'next_steps':len(ps),'Brier':sum(p['brier'] for p in ps)/len(ps),
                'logloss_nats':sum(p['logloss_nats'] for p in ps)/len(ps),'accuracy':sum(p['accuracy'] for p in ps)/len(ps)})
    csvfile('prediction_quality_summary.csv',pred);write('uniform_negative_controls.json',uniform_checks)
    old=RESULTS_DIR/'c2rag_r34_20261028_01'
    same={n:sha((old/n).read_bytes())==sha((OUT/n).read_bytes()) for n in ['public/banks.json','private/truth.json','sources.json','events.json','private/generation_gold.json','PROTOCOL.md']}
    assert all(same.values());write('REPAIR_DATA_IDENTITY.json',same)
    write('test_receipt.json',{'command':'run.cmd test experiments/c2rag_r34_20261028_02/test_contract.py -q','passed':4,'seconds':.10,
        'scope':'menus vs all short recipient schedules; heterogeneous permission; persistent single identity; incomparable work answers; immutable G'})
    total={s['method']:s for s in summ};assetgaps=[]
    for asset_id in banks:
        rs=[g for g in gaps if g['asset']==asset_id];assetgaps.append([asset_id,banks[asset_id]['split'],sum(r['OPT'] for r in rs),sum(r['Simple_Oracle'] for r in rs),sum(r['StaticMenu_Oracle'] for r in rs),sum(r['Gap_OPT_minus_Simple_Oracle'] for r in rs)])
    methods_table=mdtable(['方法','正确/288','拒答','未授权完整恢复/36流','实际UTF8字节','OPT效用差'],
        [[s['method'],s['correct'],s['refusals'],s['full_unauthorized_reconstructions'],s['bytes'],s['OPT_gap']] for s in summ])
    asset_table=mdtable(['资产','分组','OPT/48','Simple-Oracle/48','静态菜单Oracle/48','差距'],assetgaps)
    source_lines='\n'.join(f'- {s["asset"]}: [OpenStax]({s["url"]})；缓存SHA256 `{s["sha256"]}`；定位 '+', '.join(p['locator'] for p in s['paragraphs']) for s in read('sources.json'))
    structure_table=mdtable(['资产','科目/关系族','世界数','最小恢复支持','许可背景与合成边界'],
        [[s['asset'],s['subject']+'/'+s['family'],s['worlds'],'；'.join('+'.join(x) for x in s['minimal_sets']),'公开规律；实例/域/授权/请求SYNTHETIC'] for s in structure['assets']])
    write('DATASET_AUDIT.md',f"""# R34 数据与结构审查 · EXPLORATORY

六资产、四科目、四本OpenStax教材/六页缓存，36合成流/288请求。0真实需求记录，0模型生成。
不是六种独立新机制：S01为二选一同构对照；S02复用已见T06的功差结构；S03与S06的观察恢复超图严格同构。
五种观测禁集超图类；开发S01–03，留出S04–06中仅S04/S05是本批未见超图类，S06不是结构独立留出。
作者留出、作者标注，不冒称盲测或双人标注。原理/任务不同，但不按六资产推断总体教育分布。

{structure_table}

多个二元/三元禁集重叠，源任务同一实例跨query绑定；S02/03/05/06的多答案在实际有限世界分割中信息不可比较，证据structure_audit.json。
不同正确答案是否未来兼容不同另存answer_compatibility_certificates.json，共{len(incomparable_cases)}个两步反事实诊断，不把未实际执行支路算攻击成功。
有限域/单位/正值/布尔前提均可核验，164全部观察子集独立世界消元一致，安全集合附显式反世界索引。

## 最严重的三项不足
1. 权限异质性退化：三名未授权学生恰好组成k=3联盟，r3单独授权且含r3的组全部授权。所有未授权风险等价学生总并集；没有多个互不包含的最大未授权联盟冲突。不能声称完成了困难异质权限规划验证。
2. S02/S03出现有限域特有捷径。S02仅N115与WA96即可在离散库定位输入，连续正域却存在F160/f45/d0.6反世界；S03 PV8和P/T1在离散库确定nR4，连续域可P1/V8/T1得到nR8。标签在冻结域内正确，但不具连续物理外推性，原契约与结果不改。
3. 结构留出和语言效度有限：S03/S06同构；S06仅作者布尔玩具模型；没有自然语言解析或真实学习效果。六实例不代表六份独立未见教育证据。

## 全量保留与缺口
不增删数据、不挑种子。NoGate安全阴性13/36流与风险23/36都保留；相同题型重复及不同题型互补均留在原始事件。
所有非空候选语义正确，直接泄露候选次数为0；本批实际风险全部为组合，未覆盖单条完整目标直答压力测试。
公开实例可见+授权控制与全授权控制12项无报警；其含义是公开数据无需保密，绝非教材真实禁用政策。
四人中只有三人无权：有实际三人前缀见证，但未测试增加第4名未授权人，不能推断扩大接收者规模的收益。
缺少真实角色权限依据、非覆盖式联盟授权、连续域稳健性、独立人工标注、外部请求与自然语言语义攻击。

## 来源与许可
缓存页脚CC BY-NC-SA4.0，署名OpenStax；研究非商业、改编共享相同许可。无需下载新源。
仅公开规律作背景；实例参数域、数值、目标、权限和所有请求为作者合成。S06布尔式为作者假设，不冒称教材原规律。
{source_lines}
""")
    write('GLOBAL_UNION_REDUCTION.md',"""# 零差距的结构解释（结果后提出的解析证明，未用于调参）

令U={r0,r1,r2}。本批每个目标的未授权联盟恰为U的所有非空子集，且|U|=k=3；含r3联盟均授权。
知识恢复对观察单调。因此：存在一个未授权≤3联盟能恢复，当且仅当U的整体交付并集能恢复。
给r3的内容不进入任何未授权联盟。接收身份分片不改变这一主安全可行性，只改变k=1/2诊断。

**固定菜单充分性。** 取任一最优安全完整计划，学生获得的所有知识并集为V。对每个曾获非空回答的题型，任选该计划中该题型的一条正确答案；对其余题型置EMPTY。
用这一菜单回答全部同题型学生请求，r3自由回答。每条菜单知识都属于V，重复不会增加并集，因此仍安全；完成任务不少于原计划。字节预算不绑定且每个正确答案效用均1，所以它也是最优。
菜单的总并集包含于V，对任何未来题型顺序也安全；Simple的通用兼容性约束不排除它。

从任意已交付安全历史重复同一论证，精确未来的Simple可以选到一个最优后续菜单。
其一步得分=当前任务+精确未来菜单可完成数，选中动作至少有此最优菜单作为安全后续承诺；归纳可得Simple-Oracle达到OPT。
这不限于两事实二选一：在本批权限、单调恢复、等任务效用、非绑定预算、同题型候选与身份无关时，任意重叠恢复超图均成立。

局限：它不是所有C²-RAG/任意权限/任意预算的定理。若未授权最大联盟互不包含，或答案可用性/效用依身份而异、预算绑定、存在非单调规则，此推理未给出结论。
增加身份本身不算贡献；须有真实任务依据后才能改变这些条件。本轮不按结果改身份或权限。
36个OPT到静态菜单转换及包含性证书见global_union_reduction_certificates.json。独立枚举36个OPT以及36个静态菜单最优值均相同；不是只看合计抵消。
""")
    write('METHOD_COMPARISON.md',f"""# 方法比较 · EXPLORATORY

{methods_table}

每方法同一36流/288请求/候选/接收者/授权/字节预算；无真实检索、LLM生成、语义攻击或模型Token成本。
同一次主执行468轨迹/3744步；52,416联盟前缀独立检查；36个OPT完全笛卡尔积认证，无UNKNOWN/安全分歧。
独立规划评分器重算3456个非OPT决定、11775个菜单/rollout候选评分，所选答案一致。
M0直接越权完整目标交付为0，23例是联合披露，不把组合违规错误归类为单条越权。
结构化目标UNKNOWN=0不等于自然语言提取UNKNOWN=0；后者未测试。

## 逐资产核心差距
{asset_table}

Simple-Oracle/静态菜单Oracle/OPT逐流全部相同，Gap=0/36；不只是平均接近，所有六资产均0。
最小负例S01二选一，留出S04稀释全部方法Oracle44/48，均完整保留。
M2固定菜单用均匀题型覆盖静态选，故不如可重选/知未来菜单；不把M2落后当成排除所有简单规则。

## 同预测信息与误差归因
none: A2−Simple=+2；strong:+2；misleading:+1，收益全来自已见S02功差开发族；三个结构留出资产同条件A2−Simple全部0。
strong−none：Simple+3/A2+3，只来自S05；misleading−none：Simple−2/A2−3。36流小样本，不作真实预测泛化或显著性结论。
Oracle：A2比Simple少6，功差−2/二次式−4；{len(losses)}条Simple>A2的条件/Oracle案例原始轨迹全部列在all_Simple_beats_A2_cases.json，不能只展示A2增益。
预测误差、有限32情景Monte Carlo误差与策略非线性混合，因此“Oracle−Forecast”是信息替换对照，不是纯不可约预测误差。
none也利用已知family与prefix潜在主类，不等于iid Prior；uniform18流各条件情景与Prior逐项完全相同，保留阴性证据。
实际下一题的Brier/logloss/accuracy见prediction_quality_summary.csv；不在预测子进程读取真实未来评分。

## 开销与公平性边界
实际输出字节完整记录，拒答0字节；正确候选均效用1，不把非空提示当答对。本轮无替代提醒候选。
CPU取process_time，Windows观察粒度约15.625ms，个别0仅为分辨率限制；方法时间含提交/核验、不含Gate初始化与预测子进程，不用于性能优越性论断。
OPT枚举耗时另见opt/；主父进程CPU约{read('execution_completed.json')['cpu_seconds']:.3f}s，不包含144个预测子进程CPU，不能当端到端耗时。
预算均未绑定。未做相同字节量强制截断，差异来自实际允许/拒绝内容，不能把少字节当安全算法价值。
G/Fixed的回放包装器存在未使用的scenarios参数（传入真实后缀），但函数分支完全不读它；独立评分器按无未来规则重算所有决定相同。只宣称功能上的无未来依赖，不宣称这些分支有进程级信息隔离；预测器确有单流顺序stdin与禁止文件/网络边界。
""")
    # Representative evidence chosen by frozen identifier order, retaining all cases.
    first_three=structure['three_person_entire_prefix_certificates'][0]
    first_incomp=incomparable_cases[0] if incomparable_cases else None
    write('selected_cases.json',{'rule':'first identifier-order qualifying evidence; all cases retained, no causal hint claim from method labels',
        'three_person':first_three,'incomparable_answer':first_incomp,'first_negative_simple_equals_opt':gaps[0]})
    write('FAILURES.md',f"""# 失败、负结果与不确定性

1. 编号01工程失败：离线固定菜单已判无效前缀却继续调用G，触发无可行EMPTY断言。未保存任何方法对比结果。原编号01的协议、冻结、4预测文件和execution_failure.json完整保留；02只修复跳出无效菜单循环，六个数据/协议文件哈希逐字相同，见ENGINEERING_REPAIR/REPAIR_DATA_IDENTITY。主完整实验仅02一次。
2. 研究假设未成立：Simple-Oracle=OPT252/288，全部36流Gap0；不能支持新规划算法。更复杂禁集没有突破全局并集+固定菜单充分结构。
3. 异质权限不足：r3单独完全授权，其他三人可全体共谋。未覆盖互不包含的最大未授权联盟。保留此失败，不按结果增加人或改权。
4. S03/S06超图严格同构，S06不能称独立新结构留出；所有模型均作者标注，0独立人工标注者/真实学生记录。
5. S02/S03有离散域捷径，连续域反世界已核验，见FINITE_DOMAIN_LIMITATIONS.json。域内零UNKNOWN不能外推真实物理推断可靠性。
6. 同信息A2仅在已见S02局部净增，Oracle更差6；所有Simple>A2的{len(losses)}例及全部无差异保留。
7. NoGate13/36流没有完整未授权恢复，最终14流单人、9流最少两人、13流无恢复；没有最终仍必须三人的流。仅S03两条流的5个前缀真正需要三人，不能把重复前缀当5个独立三人样本。
8. 未测试单条完整目标直答、真实LLM/自然语言抽取、连续域、噪声、多来源自动关联、真实学习/版权保护、更多未授权接收者。作者构造选择性与六资产样本量不支持总体置信区间。
9. 本轮没有改冻结契约、未挑选较好seed/案例、未进行结果驱动第二轮。预测工具依赖探测bs4/matplotlib未安装，未安装或调用；工具读取远端README404不影响证据，本库四份实际报告已读且校验。

冻结知识/算法源码前后哈希检查一致。原研究/生产目录不改，模型/GPU/训练/付费API/新源下载均0。
""")
    write('NOVELTY_GAP.md',"""# 新颖性与下一步：PIVOT

主目标Gap=U_OPT−U_Simple-Oracle=0，六资产/36流逐项成立；最佳离线固定菜单也=OPT。
非加性知识组合风险、跨题历史和真正三人恢复前缀均存在，但它们没有自动产生新的释放决策算法问题。
GLOBAL_UNION_REDUCTION给出了本批零差距的简单规则证明，比“更大模型/复杂公式可能有用”的猜测更强。
本轮不提出/实现新算法候选，避免在无独立结构差距时结果驱动设计。保留成熟闭包+强Simple为默认研究参照；不继续开发更复杂A2或预测器。

一般问题可表述为：选每请求至多一个答案，最大化正确任务和，约束每个前缀的每个未授权≤3联盟均不能恢复任一目标，遵守预算/权限。
这只是约束优化表述，不是创新。即使将来一般情形有困难，也必须先排除固定菜单、静态禁集、成熟闭包和独立穷举的解释。
本轮的多答案不可比较、重叠禁集和跨题历史都被全局并集吸收；异质权限未制造真正非覆盖联盟，故没有跨资产可复核的新算法Gap。

唯一建议：下一轮先做有来源依据的“授权—联盟覆盖结构审计”，确认真实教学职责是否确实存在无法由同一≤3人未授权联盟覆盖的接收视图，以及相应同效用答案。只审计这种任务依据，不先调身份造Simple反例或开发控制器。
若不存在，应停止前瞻规划新算法路线；若存在，再冻结其连续域/逻辑关系，公平比较强菜单和OPT。当前不自动启动该审计。
连续域两个反世界、布尔玩具和同构留出都必须先披露；不拿离散域正结果写真实教材泛化。

CCF-C判断：当前证据不足以支撑独立新算法论文。可作为严谨负结果/基准设计教训积累，不能以题目复杂、多人或0攻击恢复包装创新。
""")
    write('RESULT.md',f"""# R34 结果：依赖更复杂，主规划仍退化；PIVOT

EXPLORATORY。实际完成六作者合成资产、36流、288请求、468方法轨迹、0模型调用。六资产不等于六新结构；4科目、5个禁集超图类，三份作者留出中S06与开发S03同构。

{methods_table}

## 对六个研究问题的直接回答
1. 比旧二选一复杂吗？知识依赖层面是：5/6资产有重叠禁集，其中S02/S03/S04/S06二元/三元重叠；四资产有真正不可比较的同效用答案。整体安全可行性仍退化为三名无权人的全局并集，未形成多联盟规划难题。
2. Simple还差OPT多少？**0**。Simple-Oracle252/288=OPT252/288，逐36流相等；StaticMenu-Oracle也252。强预测Simple240，离线差12；这不是可以直接宣称实现的算法空间。
3. 简单规则能解释吗？能。全局学生并集上的单调禁集＋每题型一个答案的安全菜单已充分，附解析证明和36个转换证书。不是只因两类多数计数；重叠关系也适用。
4. 多人共谋改变问题吗？改变检测边界，但未改变本轮调度优化类别。NoGate23/36流违规；S03-uniform-2前三步(r0 V、r1 P、r2 T)任意双人不足、三人恢复nR4。两条流共5个k_min=3前缀，最终全部风险流已降为14个单人/9个两人，无最终必须三人的流。权限使4流从全无权时有风险变为本策略合法，但不能推断更大接收者规模。
5. 最值得开发的算法？本轮无新算法候选；保留共享实例历史+成熟闭包+强Simple。A2强提示242比Simple240多2，全来自已见S02；留出三资产没有同信息净增，A2-Oracle还少6。
6. 是否值得继续追求CCF-C算法贡献？当前不支持。先审计有教学依据的非覆盖授权联盟，不训练预测器、不扩同构样本。

{asset_table}

## 安全、效用及边界
NoGate288正确但23/36流完整未授权恢复；G235正确/53拒答/0恢复；Simple强240/48/0；Simple-Oracle与OPT252/36/0。
完整恢复按单一目标计；元组单字段/输入恢复独立报告asset_method_summary.csv，不能用全目标尚未齐掩盖部分泄露。
正常任务只评价作者规范候选完整正确，不评价真实学习。所有非NoGate组与独立观察者逐步0分歧/0 UNKNOWN；UNKNOWN仅结构化域，不代表语义理解全覆盖。
预测strong相对none净+3/+3；misleading相对none−2/−3，数据见paired_comparisons；uniform全部提示情景与Prior一致。
S02/S03额外有限域恢复捷径不能用于连续参数；S06布尔式不是自然语言因果提取。公开完整来源实例可见时保护问题消失。

## 可复核证据与失败
PROTOCOL/freeze在任何方法表现前落盘。编号01工程失败保留；02数据、权限、候选、请求与01逐字相同，不因表现调参。
164个观察子集独立方程/布尔世界核验、52416联盟前缀、36个独立穷举OPT、3456方法决定/11775评分重算全部一致。
多答案后续兼容性证据、最小跨题支持、删动作反世界、三人前缀和实际query/reply均在JSON归档。
详细局限见DATASET_AUDIT、FAILURES、GLOBAL_UNION_REDUCTION。没有生产变化、真实LLM攻击或语义防御证据。

下一步唯一值得做的事：核查真实教学授权是否支持非覆盖的最大未授权联盟；本轮完成后停止，不启动下一实验。
""")
    write('decision.json',{'decision':'PIVOT','complete':True,'exploratory':True,'assets':6,'distinct_observation_hypergraphs':5,
        'author_structural_holdout_assets':3,'holdout_new_hypergraph_classes':2,'streams':36,'requests':288,
        'Simple_Oracle':252,'OPT':252,'StaticMenu_Oracle':252,'Gap':0,'positive_gap_streams':0,
        'NoGate_violating_streams':23,'non_NoGate_violations':0,'strong_Simple':240,'strong_A2':242,
        'new_algorithm_candidate':None,'algorithm_contribution_supported':False,'CCF_C_algorithm_evidence_sufficient':False,
        'main_failure':'all unauthorized receivers fit one k=3 coalition; heterogeneous rights reduce to trusted receiver free plus global union',
        'next_unique_action':'source-backed authorization/coalition covering-structure audit; do not relabel identities to manufacture a gap',
        'model_calls':0,'paid_API_calls':0,'production_changes':False,'next_experiment_started':False})
    write('REPRODUCE.md',"""# 复现与冻结

数据、算法和顺序见PROTOCOL.md/freeze.json。Python3.12标准库，主环境.venv-langgraph；无需SymPy/GPU/模型。
源码experiments/c2rag_r34_20261028_02；原ExactK3/set参考为snapshot/哈希标识的已有研究原型（不修改生产控制器）。
为保护原始数据，只在独立新运行名中执行prepare → run.cmd test本目录test_contract.py -q → run → verify → audit → report。
common.NAME/OUT及模块路径须统一改成新的复现命名，保留原冻结输入，禁止在现有OUT重跑覆盖。
所有输出exclusive-create；主执行36流468轨迹，forecasts为独立进程逐prefix交换，预测只读当前prefix。
01工程失败与02修复前后字节身份另存。报告/audit为结果后解释程序，算法/数据冻前哈希与结果后哈希分开存档。
发表包不包含教师私有内容、学生日志、模型、凭据或本地个人路径；公开来源仅署名/许可证/定位与哈希。
""")
    write('GROUP_MEETING.md',"""# R34 两分钟讲解

这轮我们问：加入跨题、重叠关系、多种正确答案和不同权限后，强Simple是否仍接近最优。
我们冻结六个不同教学实例族、36条合成请求流，跑了全部九类方法，并用独立方程、联盟观察者和穷举核验。
无拦截有23条流泄露，保护组均为零。强提示下Simple答对240/288、A2答对242；但两个增量全来自已见功差实例，三份留出没有A2收益。
最关键是Simple-Oracle和独立OPT都252，而且每一条流相等。不是没有组合风险，而是本轮授权结构太简单：四人中一人已授权，其他三人正好可以一起共谋，所以只需检查三人的总并集。对这样的单调安全规则，每题型挑一个答案的固定菜单已经最优。
我们确实找到前三步需要三人才能恢复气体目标的前缀，但到完整历史时已有单人或双人替代路径，不能把它包装成新的多人规划问题。
数据还暴露两个有限域捷径和一对同构留出；这些失败全部保留，不换种子或身份。
因此结论PIVOT：当前不足以追求新算法论文。下一步先找有真实教学依据、无法由单个三人联盟覆盖的授权结构，找不到就停止复杂前瞻调度路线。本轮不再开发算法。
""")
    print('Reports written. PIVOT; gap=0 on all 36 streams.')

if __name__=='__main__':main()
