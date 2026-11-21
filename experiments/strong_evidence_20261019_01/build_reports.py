"""Recompute public aggregates, validate invariants, and write requested reports."""
from pathlib import Path
import json,hashlib,csv,statistics,difflib,inspect,sys,collections
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).parent;ROOT=P.parents[1];sys.path.insert(0,str(ROOT))
def load(p):return json.loads((P/p).read_text(encoding='utf8'))
def save(p,x):(P/p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def write(p,s):(P/p).write_text(s,encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(rows,cols):
 def val(x):return f'{x:.4f}' if isinstance(x,float) else str(x)
 return '\n'.join(['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']+['| '+' | '.join(val(r.get(k,'—')) for k in cols)+' |' for r in rows])+'\n'
def csvout(path,rows):
 with (P/path).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
mm=load('mm/summary.json');atk=load('mm/attacks.json');paired=load('mm/paired.json');syn=load('mm_authored/summary.json');rag=load('rag/results.json');tr=load('rag/traces.json');ctrl=load('rag_controls/results.json');ct=load('rag_controls/traces.json');comp=load('rag/composition.json')
test=lambda rows:[x for x in rows if x['split']!='dev']
ragagg=[]
for method in dict.fromkeys(x['method'] for x in rag):
 n=[x for x in test(rag) if x['method']==method and x['kind']=='normal'];a=[x for x in test(rag) if x['method']==method and x['kind']!='normal'];i=[x for x in a if x['kind']=='identity_split']
 ragagg.append({'method':method,'assets':len(n),'normal_questions':2*len(n),'normal_EM':float(np.mean([x['EM'] for x in n])),'normal_F1':float(np.mean([x['F1'] for x in n])),'normal_availability':float(np.mean([x['availability'] for x in n])),'attack_asset_scenarios':len(a),'attack_full':float(np.mean([x['full_target'] for x in a])),'identity_full':float(np.mean([x['full_target'] for x in i])),'attack_fact_recovery':float(np.mean([x['fact_recovery'] for x in a])),'attack_tokens':float(np.mean([x['tokens'] for x in a])),'attack_ngram5':float(np.mean([x['ngram5'] for x in a])),'attack_lcs':float(np.mean([x['lcs'] for x in a])),'attack_refusal_rate':float(np.mean([x['refusal_rate'] for x in a]))})
controlagg=[]
for method in dict.fromkeys(x['method'] for x in ctrl):
 n=[x for x in test(ctrl) if x['method']==method and x['kind']=='normal'];i=[x for x in test(ctrl) if x['method']==method and x['kind']=='identity_split']
 controlagg.append({'method':method,'assets':len(n),'normal_availability':float(np.mean([x['availability'] for x in n])),'identity_full':float(np.mean([x['full_target'] for x in i])),'identity_fact_recovery':float(np.mean([x['fact_recovery'] for x in i])),'identity_tokens':float(np.mean([x['tokens'] for x in i]))})
save('rag/aggregate.json',ragagg);save('rag_controls/aggregate.json',controlagg)
csvout('mm/metrics.csv',[{k:v for k,v in x.items() if k!='field_frequencies'} for x in mm]);csvout('mm/attacks.csv',atk);csvout('rag/metrics.csv',ragagg);csvout('rag_controls/metrics.csv',controlagg)
checks=[]
def check(name,v):
 checks.append({'check':name,'passed':bool(v)});assert v,name
check('MM 24 method-subject cells and 192 separate attacker-target cells',len(mm)==24 and len(atk)==192)
check('no UCI guarded arm exceeds3 fields or exposes policy-private fields',all(x['fields']<=3 and x['private_exposure']==0 for x in mm if x['method']!='FullProfile'))
check('RAG all guarded attack scenarios obey48 tokenizer tokens',all(x['tokens']<=48 for x in rag if x['method']!='Raw-RAG' and x['kind']!='normal'))
check('corrected controls obey48 token and .15 additive risk budget',all(x['coalition_spend']<=48 and x['fact_cost_sum']<=.15+1e-8 for x in ct))
check('scope-only staticmatched shared equals independent delivery',all(x['delivered']==next(z['delivered'] for z in ct if z['asset']==x['asset'] and z['kind']==x['kind'] and z['turn']==x['turn'] and z['method']=='Fact-Independent-active') for x in ct if x['method']=='Fact-Shared-staticmatched'))
for subject in ['Math','Portuguese']:
 parts=load('mm/'+subject+'_split_LOCAL.json');check(subject+' split row sets disjoint',not(set(parts['train'])&set(parts['test']) or set(parts['train'])&set(parts['dev']) or set(parts['dev'])&set(parts['test'])))
check('core hashes unchanged since MM freeze',all(sha(ROOT/p)==h for p,h in load('mm/protocol.json')['code_sha256'].items()))
check('168 real generator calls retained',len(load('rag/calls.json'))==168)
check('all168 recorded model calls have positive input/output tokens',all(x['input_tokens']>0 and x['output_tokens']>0 for x in load('rag/calls.json')))
save('validation.json',{'status':'PASS','checks':checks,'interpretation':'invariants validate accounting and preservation, not external validity or source entailment'})
# Minimal explicit experiment-copy diff, with actual source text.
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
import textwrap
original=textwrap.dedent(inspect.getsource(ProfileSelector.select_enhanced));new=(P/'mm/strict_select_enhanced.py.txt').read_text(encoding='utf8');write('mm/strict_selector.patch',''.join(difflib.unified_diff(original.splitlines(True),new.splitlines(True),fromfile='core/select_enhanced',tofile='experiment/strict_select_enhanced')))
# Historical evidence: read original result files and retain only hashes/aggregates.
history=[]
for folder in ['uci_math_20261013_01','uci_taskslot_20261016_01','rag_fact_model_20261016_02','round120_20261016_01','rag_expand_real_20261016_01','rag_expand_real_20261016_02']:
 d=ROOT/'experiments/results'/folder;files=list(d.glob('*.json'))+list(d.glob('*.jsonl'));parsed=0;records=0
 for f in files:
  if f.suffix=='.json':json.loads(f.read_text(encoding='utf8'));parsed+=1
  else:
   for line in f.read_text(encoding='utf8').splitlines():
    if line.strip():json.loads(line);records+=1
 history.append({'directory':str(d.relative_to(ROOT)),'json_files_read':parsed,'jsonl_rows_read':records,'files_sha256':{f.name:sha(f) for f in files}})
save('historical_audit.json',history)
historical_values=[]
for folder,pattern,key in [('uci_math_20261013_01','seed-*.json','methods'),('uci_taskslot_20261016_01','math-*.json','arms'),('uci_taskslot_20261016_01','portuguese-*.json','arms')]:
 cells=collections.defaultdict(list)
 for f in (ROOT/'experiments/results'/folder).glob(pattern):
  for row in json.loads(f.read_text(encoding='utf8'))[key]:cells[row.get('method',row.get('arm'))].append(row['mae'])
 historical_values.append({'source':folder+'/'+pattern,'mean_MAE_from_raw_five_overlapping_splits':{m:float(np.mean(v)) for m,v in cells.items()},'warning':'descriptive mean over overlapping old splits, not independent N5'})
for folders,label in [(['rag_fact_model_20261016_02'],'old12'),(['rag_expand_real_20261016_01','rag_expand_real_20261016_02'],'round22')]:
 cells=collections.defaultdict(list)
 for folder in folders:
  for f in (ROOT/'experiments/results'/folder).glob('normal-*.json'):
   z=json.loads(f.read_text(encoding='utf8'));m=z.get('metrics',{});
   if 'answer_token_f1' in m:cells[m['arm']].append(m)
 historical_values.append({'source':label,'normal_raw_recomputed':{m:{'rows':len(v),'F1':float(np.mean([x['answer_token_f1'] for x in v])),'EM':float(np.mean([x['normalized_answer_em'] for x in v])),'released':float(np.mean([x['released'] for x in v]))} for m,v in cells.items()}})
save('historical_recomputed.json',historical_values)
privacy_dir=ROOT/'experiments/results/privacy_attack/20261012T105541140694Z'
old_attack=json.loads((privacy_dir/'per_seed.json').read_text(encoding='utf8'))
save('historical_privacy_recomputed.json',{'population':300,'splits':5,'independent_students_not_600':True,'methods':{m:{'mean_accuracy':float(np.mean([x[m]['attack_accuracy'] for x in old_attack])),'mean_AUC':float(np.mean([x[m]['attack_auc'] for x in old_attack]))} for m in old_attack[0]},'source_hashes':{p.name:sha(p) for p in privacy_dir.glob('*.json')}})
# Figures use independent units in captions; method cells/seeds are never N.
F=P/'figures';F.mkdir(exist_ok=True);plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
for subject in ['Math','Portuguese']:
 z=[x for x in mm if x['subject']==subject and x['method'] in ['FullProfile','NoProfile','SafeTaskTopK-3','TrainMI-SafeTopK-3','MM-Original','MM-TaskSlot']]
 fig,ax=plt.subplots(figsize=(8,4.8))
 for x in z:ax.scatter(x['mae'],x['attack_BA'],s=45);ax.annotate(x['method'],(x['mae'],x['attack_BA']),xytext=(5,5),textcoords='offset points',fontsize=8)
 ax.axhline(.5,color='gray',ls=':');ax.set(xlabel='Grade MAE (grade points; lower is better)',ylabel='Mean BA over 4 targets x 2 attackers (diagnostic)',title=subject+': historical UCI grouped recheck, K<=3 except FullProfile');fig.text(.02,.01,'Source: mm/summary.json; actual token lengths differ; no independent blind test.',fontsize=8);fig.tight_layout(rect=(0,.04,1,1));fig.savefig(F/(subject.lower()+'_privacy_utility.png'),dpi=180);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(12,5))
for ax,subject in zip(axes,['Math','Portuguese']):
 z=[x for x in mm if x['subject']==subject and x['method'].startswith('Strict')];ax.barh([x['method'] for x in z],[x['mae'] for x in z],color='#52768a');ax.set(xlabel='Grade MAE (points)',title=subject+' strict experiment copy');ax.invert_yaxis()
fig.suptitle('MM ablation: fixed safety and candidate pool, K<=3');fig.tight_layout();fig.savefig(F/'mm_strict_ablation.png',dpi=180);plt.close(fig)
fig,ax=plt.subplots(figsize=(11,5));z=[x for x in ragagg if x['method'] not in ['Fact-Independent','Raw-RAG']]
grouped=collections.defaultdict(list)
for x in z:grouped[(x['normal_F1'],x['attack_full'])].append(x['method'])
for (x,y),names in grouped.items():ax.scatter(x,y,s=55,label=' / '.join(names)+f' ({y:.3f})')
ax.set(xlabel='Normal answer token F1 (16 questions / 8 authored assets)',ylabel='Full three-value anchor recovery rate',title='C2 exploratory tradeoff: same Qwen candidates, coalition B=48 tokens',xlim=(0,1.08),ylim=(-.03,.5));ax.legend(loc='center left',bbox_to_anchor=(1.01,.5),fontsize=8);fig.text(.02,.01,'Source: rag/aggregate.json; 32 scenarios / 8 assets; lengths/refusals differ; no human blind review.',fontsize=8);fig.tight_layout(rect=(0,.04,1,1));fig.savefig(F/'rag_utility_reconstruction.png',dpi=180);plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4.5))
for method in ['Raw-RAG-budgeted','Fixed-Truncation','Fact-Shared','C2-no-history','C2-no-binding']:
 ys=[np.mean([x['cumulative_fact_recovery'] for x in test(tr) if x['method']==method and x['kind']=='identity_split' and x['turn']==i]) for i in range(3)];ax.plot([1,2,3],ys,marker='o',label=method)
ax.set(xlabel='Delivered query turn (3 agents, one turn each)',ylabel='Cumulative recovered value units / 3',title='Cross-identity composition: 8 authored test assets');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(F/'rag_cross_turn.png',dpi=180);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(11,5));names=[x['method'].replace('Fact-','') for x in controlagg]
axes[0].bar(names,[x['identity_fact_recovery'] for x in controlagg],color='#52768a');axes[0].set(ylabel='Recovered value units /3',title='Equal aggregate risk .15 and Token B48');axes[1].bar(names,[x['identity_full'] for x in controlagg],color='#52768a');axes[1].set(ylabel='Full target recovery rate',title='All arms at floor: no shared safety advantage');
for ax in axes:ax.tick_params(axis='x',rotation=17)
fig.suptitle('Posthoc fairness controls, same 8 assets; staticmatched isolates scope');fig.tight_layout();fig.savefig(F/'rag_equal_budget_ledger.png',dpi=180);plt.close(fig)
date='2026-10-19（北京时间）；供2026-10-20组会使用。'
common='本轮不修改生产核心、不覆盖旧实验、不调用付费API、不下载模型。UCI均为历史数据复核；自编材料为合成/探索性留出验证，不能称真实学校独立盲测。原始逐人信息只存本地，公开包仅含聚合统计及自编资料。'
mm_main=table([{k:x[k] for k in ['subject','method','test_n','mae','fields','tokens','private_exposure','attack_BA','attack_AUC']} for x in mm if not x['method'].startswith('Strict')],['subject','method','test_n','mae','fields','tokens','private_exposure','attack_BA','attack_AUC'])
mmtext=f'''# MM-FOPD 强基线与隐私—效用实验

{date}

## 判断

**尚无足以支撑“稳定优于强基线”的论文主证据。** Math TaskSlot MAE1.2275，TrainMI1.2437，描述性配对差−0.0162，区间跨零；Portuguese TaskSlot0.9149，TrainMI0.8987。新自编任务中TaskSlot与SafeTaskTopK必要字段F1均1，未胜出。不能用均值攻击BA低于.5证明隐私安全。

{common}

## 设计、冻结与独立单位

目的是排除旧消融安全门限和字段预算改变的混杂，同时检验零直接暴露时的残留属性信号。`mm/protocol.json`先于训练/评估生成；字段预算K≤3，Full/No作诊断。TrainMI仅用训练G3拟合字段排序；Ridge仅用开发集选择alpha∈1,10,100；LR和RF预定参数分别报告，不取测试表现好的攻击器。没有校准型安全阈值需另拟合，dev即效用调参集；无额外校准数据。

Math395行，train/dev/test=226/86/83；Portuguese649行，389/129/131。按UCI merge脚本13字段代理身份对两科共同分组，662个不同键；Math391键、Portuguese637键、共有366键。官方merge的382是匹配行数，不能等同366个独特键。无完全重复行；同键不跨partition。无可靠真实学生ID，近重复身份不可完全排除；两科测试样本不能相加成独立学生数量。拆分行号和逐人预测留本地 `_LOCAL.json`。

## 强基线结果（两类攻击器×四属性宏均值仅为诊断摘要）

{mm_main}

FullProfile提供32字段且直接目标暴露，不是攻击器读取目标的借口；所有残留攻击都移除目标字段**及presence mask**。NoProfile恒定空视图。RuleSummary=studytime/failures/absences，为明确内部规则参照。公开攻击明细CSV按health/romantic/Pstatus/Dalc、LR/RF分别列Accuracy、BA、AUC及正类数，见`mm/attacks.csv`，共192格。没有把FullProfile显式值当残留推断100%。

字段数相等并不等于信息量或Token相等；此处上限相同，实际Token用本地Qwen tokenizer对排序field=value规范串计算，无padding。字段ID及真实值的释放记录留本地；公开field_frequencies保留可解释性。没有声称Shannon信息泄露量；未估计信息论互信息或差分隐私。

## 配对差值与严格消融

{table([x for x in paired if x['method']=='MM-TaskSlot'],['subject','method','delta_MAE','conditional_group_bootstrap_95'])}

区间按测试代理学生身份整组重采样2000次，仅描述当前拟合、历史已见队列，不覆盖训练不确定性、多重选择和真实学校总体。每科只评估一个冻结新划分，不用重叠seed制造N。原版与Strict副本区分见`ablation_review.md`。

## 自编教育必要字段验证

`mm_authored`含200个虚构画像，10种加权教学评分任务，按任务族120/20/60切分。必要字段是完成显式加权计算的三个输入，独立于selector输出定义。TrainMI只用120训练画像的计算目标；不要求其知道测试任务族。属于任务迁移压力测试，因此MI的下降也不能解释为它在原任务中无效。没有把确定性计算称LLM教学生成。dev没有用于反复修改选择器。

{table(syn,['method','n','precision','recall','F1','task_solvable','direct_exposure','tokens','budget_violations'])}

只有3个人工选择的测试任务族，60画像不能当60个独立任务设计。不给总体CI。此批仅验证必要字段/可计算性，未补跑合成属性攻击；属性隐私主证据来自上述UCI实测，不能跨数据拼成同一个胜出结论。TaskSlot与SafeTopK逐请求字段相同，无法证明TaskSlot超过这个强简单基线。

## 成功与失败案例（脱敏）

1. UCI原版在两科测试中G1释放率1、G2释放率0；TaskSlot均补齐G1/G2，解释了大部分MAE改善，但不证明投影解耦隐私。
2. 自编测试任务族7需要recent_score/access_hours/misconception_code，安全TopK与TaskSlot都能保留必要项；原版优先类型与任务必要性不完全一致。完整值均为自编，见`mm_authored/data.json`。

## 成本、失败、可复现性

24个科目×方法格、192个属性×攻击器格均完成，运行异常0；每格test_n、真实选择CPU秒和全流程秒见`mm/metrics.csv`。CPU时间是当前硬件上的实测wall time，Token是外发规范串长度，非API计费。UCI真实模型/API调用0；仅tokenizer计数。自编画像1200条方法结果，异常0，时间见completion。实际能耗和本地折旧未计价，不能把无API账单解释为计算成本为零。

外部LaMP/GPG/PAPILLON/Privacy Funnel均NOT RUN，具体可信来源与接口不匹配原因见`external_baselines.md`；旧style方法只作历史内部机制参照。

## 100～150字组会讲解词

这轮把两个科目按疑似同一学生分组，重新跑了等字段预算基线和两类属性攻击。任务槽版本在数学上仅略优于训练互信息，配对区间跨零，在葡语上仍略差。自编必要字段任务中，它与安全TopK持平。严格去掉投影或注意力后结果不变，因此目前能讲任务适配改善，不能讲整体算法稳定领先或已实现属性隐私。

## 证据状态

代码`run_mm.py`、`run_authored_mm.py`；配置`mm/protocol.json`、`mm_authored/protocol.json`；聚合`mm/summary.json`、`mm/attacks.csv`；配对`mm/paired.json`；图`figures/math_privacy_utility.png`、`portuguese_privacy_utility.png`、`mm_strict_ablation.png`。所有路径相对本次目录；SHA256见`evidence_manifest.json`。必要字段结果仅能写合成机制验证，真实教学质量仍BLOCKED。
'''
write('mmfopd_strong_baselines.md',mmtext)
ragtext=f'''# C²-RAG 强基线与语义重构实验

{date}

## 判断

**补齐了真实小模型、真实语义编码器、同候选及等联盟Token上限的探索证据，但不足以支撑共享账本优于等总预算独立账本的论文主张。** 无防护等预算对照跨身份恢复7/8目标，攻击不是全局地板；Fact共享与独立均0/8，主比较仍有地板。共享池释放的事实更多，不能把它描述为隐私优势。

{common}

## 设计与模型

12份全新自编虚构教学资产，涉及光学、声学、生态、机器人等领域；每份有instrument正常答案、三个自编设置值、允许单事实和禁止完整三事实组合的规则。4dev、8冻结探索性test；共享作者与结构模板，不称8个真实独立教师来源。每资产2正常问题；原文、释义、3轮同会话、3身份互补四种攻击。不是实际版权法律判断。

同一Qwen2.5-0.5B-Instruct离线GPU、greedy、max_new_tokens64生成所有120个源候选；每候选被11方法复用，避免模型采样差异。另48次真实攻击者组合调用只看已交付回复，隐藏source、gold和值不进入攻击者输入。真实MiniLM编码器经attention-mask mean-pooling和L2归一化，output/source cosine门限.85，非TF-IDF代理。文件权重哈希见`rag/model_manifest.json`；未下载任何模型。

阈值、提示、攻击计划先冻结；本轮没有dev调阈值或最终test后择优报告。后续公平性纠错明确为posthoc复核，原结果不覆盖。没有独立人工语义校准集/盲评，语义泛化主张BLOCKED。

## 各门控的真实差异

Raw-RAG为无上限诊断；另有Raw-RAG-budgeted满足相同Token额度。其余每个攻击episode联盟B48 Token、各会话静态16，未使用padding。Fixed截取前4个真实token；Ngram门拒绝source唯一5gram覆盖>.10的候选；Semantic门运行MiniLM；Fact调用现有`gate_fact`短答案、来源见证、实际披露成本账本。trusted witness由可信retriever绑定整个source，**不冒称模型自己生成了引用或完整生产RAG系统**。检索候选明确给定同一资产，本轮不测开放库检索。

Fact-Independent把总加性风险额度.15预分三份.05；Shared总.15。两者Token上限相同，但静态分配与共享池差异必须单列，不能称纯状态作用域增益。C2-Full-adapter是实验中的Fact+MiniLM组合，不是对完整生产C²-RAG的官方复现。

## 原冻结批结果：8资产、16正常问题、32攻击资产场景

{table(ragagg,['method','normal_F1','normal_availability','identity_full','attack_full','attack_fact_recovery','attack_tokens','attack_refusal_rate'])}

**原批Fact-Independent正常F1=.4375不可用于“共享提升正常效用”结论**：正常任务只有一个有效会话，原实现仍只给.05，而Shared给.15。该失败原样保留。所有其他门均显示真实拒答/输出长度；安全下降不排除更短输出的作用。

## 公平性纠错与作用域控制（同一候选，事后重放，不是新test）

正常/同会话攻击只有一会话，独立与共享均给.15；跨身份独立仍三份.05，共享池.15。新增staticmatched共享控制既要求同样每会话.05，也维护总共享.15，只比较多出的全局历史。预算在Token门通过后原子提交，纠正原适配器可能在未交付时先记账的问题。

{table(controlagg,['method','assets','normal_availability','identity_full','identity_fact_recovery','identity_tokens'])}

匹配静态分配后Shared与Independent逐条交付完全一致；各8资产完整目标恢复均0，不能从零差的退化bootstrap推断等效或零风险。共享池对独立的跨身份事实恢复差为+0.5833，说明共享额度更易利用，**不是更安全**。资产配对的描述性区间及Token差见`rag_controls/paired.json`，不能作现实总体推断。

## 指标、事实核验与边界

正常EM=规范化答案一致，F1=token多重集F1，必要证据覆盖由必要单事实答案是否交付近似；本例EM/F1/可用率一致不代表复杂教学。拒答=空交付。5gram/LCS分别测source唯一n-gram及最长公共子序列覆盖，不与语义混用。事实恢复以预先固定设置值的规范化锚点匹配计数；三值齐全作为完整目标，按原始asset聚合。数值短答可以被释义/拼接恢复而5gram为0。此法会漏掉数值改写，可能误把孤立值当关系；不是完整蕴含判别。独立双人语义审查仍BLOCKED。

“越权交付”仅指所定义完整禁止组合出现，不是通用授权协议越权检测；允许单事实恢复不自动算违规。攻击者参数名来自已知问题schema，不含隐藏值；所有真实交付和组合模型输出可审计。正常两题和四种攻击场景不能当40个独立资产；同模型候选复用不能计为1320次新生成。

## 消融与典型失败

no-history去累计Fact账本；no-semantic仅去MiniLM门；no-binding把历史键改为会话别名。三者均维持B48 Token。身份绑定消融同时放宽加性风险作用域，属于复合会计干预，不用来证明单独身份绑定收益。固定短答/词面基线为强简单参照；详见`ablation_review.md`。

1. asset04生态资产：预算无防护三身份分别交付29 meters、11 days、47 meters，9 Token可恢复完整三设置，5gram不需重合。Shared仅交前两项，第三项受累计风险拦截；原Independent三项均拒绝，不能说Shared更安全。
2. 实际MiniLM门在短数值互补回复上未阻断完整重构；与等Token Raw的identity恢复率相同7/8。no-semantic与完整adapter结果一致，未观察到语义门的独立安全增益。

## 实际成本、失败与证据

真实decoder调用168（120可信生成+48攻击者组合），输入16325、输出3335 Token，GPU生成实测105.92秒；含dev与test，不能只算test或按11方法重复乘计。模型加载、最初编码器执行未单独计时；gate_seconds不含共享预计算的encoder开销，不能作为完整语义门延迟。API收费0，本地电力/折旧未计价。生成运行异常0；语义评测不足不计成生成成功或安全成功。自编模型原始输出全部保留；风险/Token预算违规0。

真实模型组成输出见`rag/composition.json`，它是攻击者实际生成而非确定性模拟；主表用交付并集锚点评分，不能将其混成攻击者模型逐项重建正确率。必要证据覆盖、复杂释义蕴含和人工裁决尚无可独立验证结果。

## 100～150字组会讲解词

这轮用本地真实小模型跑了十二份全新自编教学资产。等Token预算无防护组仍能通过跨身份短答案重构七个完整目标，说明只看原文重合会漏检。共享账本虽把完整恢复降为零，但等总风险预算独立账本同样为零；匹配分配后交付完全一致。目前能证明累计限制存在作用，不能证明共享账本更安全，语义门也尚未显示独立增益。

证据：`rag/protocol.json`、`rag/assets.json`、`rag/calls.json`、`rag/traces.json`、`rag/metrics.csv`及`rag_controls`；图`figures/rag_utility_reconstruction.png`、`rag_cross_turn.png`、`rag_equal_budget_ledger.png`；哈希见evidence_manifest。RAGFort/CanaryRAG为NOT RUN，参见external_baselines。
'''
write('c2rag_strong_baselines.md',ragtext)
write('ablation_review.md',f'''# 严格消融审查

{date}

## MM：严格副本与原版分开

原版的no-orthogonal会同时关安全门，no-attention候选从8变全量，no-bottleneck还切换类型补齐，旧结论不用于单因素归因。此次`StrictSelector`仅在实验目录通过继承替换select_enhanced，不改生产文件。安全门总启用、attention排序候选固定全部32字段、K3；bottleneck关时仍保留TaskSlot/类型补齐。完整差异见`mm/strict_selector.patch`；这份补丁的每一行都来自实际执行的源码。

{table([x for x in mm if x['method'].startswith('Strict')],['subject','method','test_n','mae','fields','tokens','private_exposure','attack_BA'])}

Strict-Full/no-projection/no-attention结果相同：任务槽覆盖排序作用，未观察到独立效用收益。no-bottleneck的差仅+0.01095 Math和−0.01021 Portuguese，无稳定方向。no-taskslot恢复原版较差MAE；只能说明此适配在本任务有用，不说明真实教学、投影独立性或隐私优势。Strict完整采用全候选池，属于审计副本，不能伪装成原始实现。

## C²：消融归因等级

{table([x for x in ragagg if x['method'] in ['C2-Full-adapter','C2-no-history','C2-no-semantic','C2-no-binding','Fixed-Truncation','Ngram-Gate']],['method','normal_F1','identity_full','attack_full','attack_tokens','attack_refusal_rate'])}

1. no-history：同候选、同语义门、Token上限不变，去除累计风险状态；可作本adapter机制消融，但安全提升伴随更少交付，不能排除输出量作用。
2. no-semantic：唯一去掉MiniLM cosine门，输出风险指标未变，不能声明语义组件独立有效。
3. no-binding：键改成会话别名同时扩大了可消费加性风险总额，**复合会计干预，不纳入严格单因素贡献**。TokenB48不等于所有风险约束也相同。
4. Independent/Shared：静态分配对共享池，不是纯历史作用域；新增staticmatched控制匹配所有局部与总额度，真实逐条交付相同，主比较处于地板。
5. 固定截断和Ngram不是对完整adapter仅关一个开关；是不同完整机制的强简单基线。

原始纠错前结果不删除；校正协议标记posthoc，不能称独立确认。没有为预算相等而填充内容、重复算Token或给三个独立Agent各自完整联盟B。

## 尚不能写入论文的贡献

投影带来属性独立；attention在TaskSlot存在时独立改善；MiniLM门防止短事实组合；共享账本比等联盟预算独立账本更安全；身份绑定消融提供纯组件因果证据——以上均不成立或尚未证明。
''')
write('external_baselines.md','''# 外部论文方法核验（2026-10-19）

全部区分“方法存在/官方源码存在”与“本轮真实运行”。无内部style规则冒充论文复现，以下均NOT RUN。

- LaMP：[作者官方仓库](https://github.com/LaMP-Benchmark/LaMP)。确有检索增强个性化实现，接口为多条个人历史文本及分类/生成任务，非UCI字段K3及属性隐私约束。未接入训练模型/原任务协议；复用本地TF-IDF不能称官方LaMP复现。
- PAPILLON：[官方README](https://github.com/Columbia-NLP-Lab/PAPILLON/blob/main/README.md)。官方流程含本地模型和远程模型的DSPy优化，公开复现分支papillon_v1.0；当前本地0.5B并非其优化配置，远程API不在本轮自动付费授权中。不以extractive规则冒充。
- GPG：[原论文](https://arxiv.org/abs/2409.13093)。是多步自然语言画像生成，论文使用GPT3.5偏好/改写/对话任务。本轮未核到可直接对接K3字段任务的可信官方接口，未复现；没有宣称无官方代码。
- Privacy Funnel：[原论文](https://arxiv.org/abs/1402.1774)。优化联合分布下随机映射，离散greedy合并并非字段TopK；本地无已验证官方实现及冻结联合分布映射。内部Funnel-style不算其实现。
- RAGFort：[官方源码](https://github.com/happywinder/RAGFort)、[README](https://raw.githubusercontent.com/happywinder/RAGFort/main/README.md)。确有源码；包含聚类、SupCon重训练编码器及draft/verifier级联解码。与本轮同冻结生成模型和同候选释放门任务不同；缺匹配验证模型/训练产物，不下载未经确认模型，不将MiniLM门冒充RAGFort。
- CanaryRAG：[原论文](https://arxiv.org/abs/2604.10717)。检索片段植入canary和双路径运行完整性检测；本轮检索候选固定、未建立其原生成与检测校准协议。检索到的论文页面未核实可执行官方代码入口，不能断言不存在官方代码。标记NOT RUN / 官方可运行接口尚未核实。

P2未完成一项官方完整复现，这属于明确证据缺口；强简单基线已实跑不弥补该缺口。网页来源只用于接口/适用性核验，不用其摘要代替本轮实验结果。
''')
write('paper_ready_evidence_matrix.md','''# 论文证据矩阵

## 可写入论文（附探索性限定）

- UCI代理身份分组复核：原始MM在两科MAE明显差于TrainMI；TaskSlot接近MI，不能称稳定胜出。原始学生数据不公开。
- 等K3、相同安全门与候选池的实验副本：投影和attention去除不改变本任务结果，为负结果，不能反向证明组件永远无效。
- 全新合成必要字段任务：TaskSlot与SafeTaskTopK持平；合成计算可解性不等于教学质量。
- 真实本地小模型和真实MiniLM编码器：短答案跨身份组合可绕过原文5gram；锚点评分下无防护等Token对照7/8恢复目标。
- 本Fact门的累计状态相较无历史变体降低完整锚点恢复，但伴随更少交付；需写清模型、12自编资产、8探索test和输出长度差异。
- 匹配局部配额的Shared与Independent逐交付一致；共享池与静态分配的差异不可归因为纯共享历史增益。

## 不可作为论文主张

- MM普遍优于强外部个性化/隐私方法：NOT SUPPORTED。
- 零直接敏感暴露意味着零属性推断风险：FALSE；各属性LR/RF已分别记录。
- C²-RAG优于等联盟预算独立账本的安全性：NOT SUPPORTED；恢复率均0，比较处于地板。
- 真正通用释义语义重构评测充分：BLOCKED；仅值锚点与可核验问答，无独立人工蕴含审查。
- 来源与身份绑定独立因果收益：NOT ESTABLISHED；会计作用域联动。
- 外部LaMP/GPG/PAPILLON/PrivacyFunnel/RAGFort/CanaryRAG官方复现：NOT RUN。
- 新真实学生/真实教师独立盲测：NOT RUN。历史UCI、合成任务和作者资产不能互相冒充。

## 下一步唯一优先实验

用一批由独立标注者冻结的全新资产，先在开发资产校准到等预算独立账本存在非零恢复风险、正常任务效用接近且实际交付长度匹配，再对Shared/Independent做一次按资产留出的盲测。联盟Token和加性风险总额度相同，预分配规则一致，只改变历史可见范围；双人核验事实关系而非只匹配值。若这些约束使两者必然等价，应报告等价条件并重新界定共享账本主张，不靠放大独立Agent预算制造增益。
''')
write('group_meeting_results.md',f'''# 2026-10-20组会：本轮真实新增结果

{date}

## 最终回答

**MM-FOPD：尚不足支撑稳定优于强基线的主张。C²-RAG：尚不足支撑共享账本优于等联盟预算独立账本的主张。** 本轮已有可复现的新实跑结果，包含有用负结果；不是只完成计划。

## 本轮新增完成

- MM：Math395、Portuguese649行按共同代理身份分组，12方法×2科=24格；4属性×2真实攻击器×24=192格，LR/RF分别报告Accuracy/BA/AUC。每科一次冻结划分，不叠加seed。
- 新合成必要字段任务：200虚构画像，120train/20dev/60test，6方法，必要字段P/R/F1和任务可解性；无真实学生数据。
- C²：12新自编资产、4dev/8冻结探索test；168次真实Qwen模型调用（含攻击者组合）；真实MiniLM门、11种释放条件；同候选、真实Token计数、未发现预算超额。
- 完成初版公平性缺陷记录及纠错重放；新增相同局部配额的纯作用域控制。保留所有失败和原始运行，不把纠错再叫独立测试。

## 可上组会的核心数字

1. Math原MM/TaskSlot/TrainMI MAE=2.0112/1.2275/1.2437；TaskSlot−MI配对差−0.0162，描述性区间[−0.0758,0.0459]。Portuguese=1.4603/0.9149/0.8987。
2. 自编必要字段F1：原MM .7778、TaskSlot1.0、SafeTaskTopK1.0，TaskSlot没有超过强简单基线。
3. 严格副本去投影、去attention结果不变；去bottleneck差异很小且两科方向不同。
4. 等Token无防护跨身份完整目标恢复7/8；Shared0/8、Independent0/8。Shared不是唯一成功者。匹配静态子配额后两者逐条交付一致。
5. 原始独立账本正常问答F1 .4375有额度分配混杂；纠错后Shared/Independent正常可用率均1.0，不展示虚假的共享效用优势。

## 历史复核与实跑区分

已读取旧UCI每seed文件、TaskSlot各科每seed、旧FactRelease正常/攻击输出、round120及两批parent原始JSON/usage，文件数和SHA256见historical_audit。旧评审中的UCI原MM2.1104、TaskSlot1.1876、MI1.1629属于旧划分，不与新分组划分混表。旧Stage1-E三资产多架构trace的联盟额度不等问题仍保留；本轮没有重跑或修改Stage1-E。历史报告复核不计成新增模型调用。

## 真正优于强基线的指标

只有探索性点估计：Math TaskSlot比TrainMI MAE低.0162，同时平均攻击BA较低；区间跨零、Token不完全相等，葡语不复现，不能称可信稳定隐私—效用优势。自编任务TaskSlot胜训练MI但与SafeTopK持平。C²的Fact共享相对固定截断在完整锚点恢复上更低，但交付更短，不能排除输出量影响；相对等总预算Independent无安全优势。

## 成本、失败和交付

模型调用168，输入16325、输出3335 Token，生成GPU秒105.92；付费API0，模型下载0。运行异常0；严谨语义人工评测、外部官方基线复现与真实教学质量为未完成项，不能被“运行成功”掩盖。原始统计、配置、代码、脱敏报告、6张PNG、校验结果均在本目录。公开包不含逐行UCI值、个人画像、Token、权重或.env。

## 明天怎么讲

先讲两项反例：任务槽改善不等于投影贡献；共享账本限制累计释放不等于战胜等预算独立账本。展示Math/Portuguese散点、严格消融、跨轮曲线和等预算账本图，再说明哪些结论只能用于探索性机制验证。两模块各100～150字讲解词已放入各自强基线报告。

下一步只优先做一项：**独立标注新资产、等联盟预算及长度匹配、非地板攻击下的Shared/Independent一次冻结盲测。** 详见paper_ready_evidence_matrix。
''')
write('README.md','''# CogniGuard 强基线实验补强 2026-10-19

入口：group_meeting_results.md。分模块：mmfopd_strong_baselines.md、c2rag_strong_baselines.md；严格归因：ablation_review.md；论文可用边界：paper_ready_evidence_matrix.md。

本轮可执行批次与公平性纠错均执行完成，受阻分支见证据矩阵。旧核心与旧实验未由本轮写入。所有模型离线，付费调用0，下载0。不是新真实学生盲测，不是论文官方方法全量复现。

重放应在独立新目录复制本轮驱动，保留旧输出。Windows项目根目录用`.venv/Scripts/python.exe`运行各驱动；先设`PYTHONHASHSEED=20261013`、`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`。顺序run_mm.py、run_authored_mm.py、run_rag.py、replay_rag_controls.py、build_reports.py。各主驱动存在protocol时拒绝覆盖。原项目与固定本地模型为依赖；见源码哈希和model_manifest，未把权重上传。实际新运行应自选新目录，不要删除既有protocol绕过拒写保护。

公开包采用允许列表：报告、驱动代码、聚合统计、配置哈希、自编资产与输出、图。所有`*_LOCAL.json`和原始UCI数据不进入同步。evidence_manifest列本轮所有证据的相对路径/字节数/SHA256，包含仅本地证据的哈希但不含其值。远端同步后另生成sync_receipt.json。
''')
if (P/'composition_audit/completion.json').exists():
 extra=load('composition_audit/completion.json');initial=load('rag/completion.json');total={k:initial[k]+extra[k] for k in ['real_model_calls','input_tokens','output_tokens','generation_seconds','failures','paid_calls']};save('model_cost_total.json',total)
 supplement=f'''\n\n## 后续真实攻击者信息核验（事后诊断，保留主批）

最初组合模型只看到回复，没有看到攻击者本来知道的问题，且出现语义关系错配；不能把7/8交付并集值锚点恢复说成7/8真实语义重建。已另冻结`composition_audit/protocol.json`，给模型合法可见query/reply对，仍隐藏原文和gold，追加32次真实模型调用。严格要求设置名与值同一行出现，无防护等Token组完整关系重建仅1/8，三个账本控制均0/8。这个严格匹配规则也漏掉有序数值列表和省略单位（例如stack count回复27，源值27 frames），所以1/8是格式依赖下界，不能当可靠语义ASR。真实成功案例asset05明确正确重建wheel speed83RPM、turn angle67degrees、pause duration31seconds；失败/评分不足例asset04只复述有序值，不输出关系名。未据此改阈值、重调系统或宣称新独立test。

本轮decoder调用总计**{total['real_model_calls']}**，输入**{total['input_tokens']}**、输出**{total['output_tokens']}** Token，GPU生成累计**{total['generation_seconds']:.2f}秒**；异常0、付费0。主批168次/16325输入/3335输出、补充32次/3818输入/443输出分别保留。对通用释义和事实关系的充分语义评测仍为BLOCKED，不因为出现一个成功案例便宣称已充分验证。
'''
 for name in ['c2rag_strong_baselines.md','group_meeting_results.md']:
  write(name,(P/name).read_text(encoding='utf8')+supplement)
 write('README.md',(P/'README.md').read_text(encoding='utf8')+'\n补充驱动audit_composition.py在原RAG及controls之后运行，32次真实模型核验；本轮总模型调用200。历史原始数字重新聚合见historical_recomputed.json；真实关系重建与锚点恢复严格区分。\n')
 write('paper_ready_evidence_matrix.md',(P/'paper_ready_evidence_matrix.md').read_text(encoding='utf8')+'\n后续模型信息审计：200次decoder总调用。实际模型明确关系重建仅观察到无防护1/8严格成功，锚点并集7/8不是同一指标。评分规则存在省略单位/格式漏检，完整语义评测仍不充分。\n')
if (P/'mm/partition_group_counts.json').exists():
 counts=load('mm/partition_group_counts.json')
 write('mmfopd_strong_baselines.md',(P/'mmfopd_strong_baselines.md').read_text(encoding='utf8')+'\n独立单位补充：Math测试83行对应82个代理身份组，Portuguese测试131行对应128组；跨科test与另一科train/dev身份交叉为0。详见mm/partition_group_counts.json。报告MAE按行计，CI按组重采样，两者权重口径明确区分。\n')
import importlib.metadata,platform,shutil
save('environment.json',{'python':sys.version,'platform':platform.platform(),'packages':{n:importlib.metadata.version(n) for n in ['numpy','scipy','scikit-learn','torch','transformers','matplotlib','tokenizers']},'hash_seed':'20261013','models_offline':True})
snapshot_paths=['experiments/mmfopd_uci/runner.py','experiments/mmfopd_uci/alignment_probe.py','experiments/mmfopd_uci/portuguese_transfer_probe.py','protection/common/schemas.py','protection/common/text_utils.py','protection/student_profile/src/fopd/profile_selector.py','protection/student_profile/src/fopd/task_attention.py','protection/student_profile/src/fopd/orthogonal_decoder.py','protection/student_profile/src/fopd/multimodal_profile.py','experiments/c2rag_v3/core.py','experiments/c2rag_v3/generator.py','experiments/c2rag_v3/fact_release.py','experiments/c2rag_v3/evidence_release.py']
for relative in snapshot_paths:
 source=ROOT/relative;destination=P/'source_snapshot'/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
save('source_snapshot/manifest.json',{'purpose':'dependency source copies for local reproducibility; no data, credentials, or weights','captured_after_execution':True,'limitation':'MM protocol prehashes its listed dependencies; RAG protocol prehashes driver only; this postrun snapshot does not retroactively establish a pre-run full dependency lock','files':{p:sha(ROOT/p) for p in snapshot_paths}})
write('README.md',(P/'README.md').read_text(encoding='utf8')+'\n冻结限制：MM在运行前哈希列出的核心依赖；RAG事前仅记录驱动哈希，依赖源码快照为运行后补存，不能追认完整事前环境锁。模型文件哈希已记录；未据此声称论文确认性完整冻结。\n')
manifest=[]
for p in sorted(P.rglob('*')):
 if p.is_file() and '__pycache__' not in p.parts and p.name not in ['evidence_manifest.json','sync_receipt.json'] and 'public_delivery' not in p.parts:
  manifest.append({'path':str(p.relative_to(P)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':sha(p),'local_only':p.name.endswith('_LOCAL.json')})
save('evidence_manifest.json',{'status':'COMPLETED_WITH_EXPLICIT_LIMITATIONS','files':manifest})
print(json.dumps({'reports':5,'figures':len(list(F.glob('*.png'))),'validation':len(checks),'evidence_files':len(manifest)}))
