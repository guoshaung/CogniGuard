"""Reports and figures from recorded outputs only; no experiment reruns."""
from pathlib import Path
import json,csv,hashlib,statistics,collections,sys,shutil,importlib.metadata
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).parent;ROOT=P.parents[1];OLD=ROOT/'experiments/strong_evidence_20261019_01'
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def save(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def write(n,t):(P/n).write_text(t,encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(rows,cols):
 def fmt(x):return f'{x:.4f}' if isinstance(x,float) else str(x)
 return '\n'.join(['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']+['| '+' | '.join(fmt(x.get(k,'—')) for k in cols)+' |' for x in rows])+'\n'
def csvsave(n,rows):
 keys=list(dict.fromkeys(k for x in rows for k in x))
 with (P/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
r=load('rag_dev/results.json');tr=load('rag_dev/traces.json');sym=load('symbolic_audit/results.json');fmt=load('rag_format_audit/rows.json');mm=load('mm/corrected_stage_summary.json');legacy=load('mm/legacy_wiring_replay.json');devmm=load('mm/dev_summary.json');cost=load('rag_dev/completion.json');decision=load('rag_dev/decision.json');attacks=load('rag_dev/attacks.json')
aggregate=[]
for beta in [.18,.36,.72,1.2]:
 for method in load('rag_dev/protocol.json')['methods']:
  normal=[x for x in r if x['beta']==beta and x['method']==method and x['kind']=='normal'];a=[x for x in r if x['beta']==beta and x['method']==method and x['kind']=='identity_split'];s=[x for x in sym if x['beta']==beta and x['method']==method and x['kind']=='identity_split'];f=[x for x in fmt if x['beta']==beta and x['method']==method and x['kind']=='identity_split'];units=[x['numeric_unit_binding'] for x in a if x['numeric_unit_binding'] is not None]
  aggregate.append({'risk_beta':beta,'method':method,'source_assets':3,'normal_questions':6,'normal_correct':float(np.mean([x['normal_correct'] for x in normal])),'normal_F1':float(np.mean([x['normal_F1'] for x in normal])),'primary_LLM_relation_ASR':float(np.mean([x['complete_relation'] for x in a])),'posthoc_format_LLM_relation_ASR':float(np.mean([x['posthoc_complete_relation'] for x in f])),'posthoc_symbolic_relation_ASR':float(np.mean([x['complete_relation'] for x in s])),'symbolic_premise_conclusion_accuracy':float(np.mean([x['premise_conclusion_accuracy'] for x in s])),'tokens_mean':float(np.mean([x['tokens'] for x in a])),'risk_used_mean':float(np.mean([x['risk_total'] for x in a])),'source_sentence_witness_lower_bound':float(np.mean([x['verified_fact_fraction'] for x in a])),'numeric_unit_witness_physics_only_n1':float(np.mean(units)) if units else None,'refusal_rate':float(np.mean([x['refusal_rate'] for x in a])),'reminder_fallback_rate':float(np.mean([x['fallback_rate'] for x in a])),'source5gram':float(np.mean([x['ngram5'] for x in a])),'sourceLCS':float(np.mean([x['lcs'] for x in a]))})
save('rag_dev/aggregate.json',aggregate);csvsave('rag_dev/metrics.csv',aggregate);csvsave('mm/stage_metrics.csv',mm);csvsave('mm/dev_metrics.csv',devmm)
lengths=[]
for beta in [.18,.36,.72,1.2]:
 for aid in ['dev-affine','dev-power','dev-branch']:
  zs={m:next(x for x in r if x['beta']==beta and x['asset']==aid and x['kind']=='identity_split' and x['method']==m) for m in ['FactRelease-Shared','FactRelease-Independent','FactRelease-Shared-staticmatched','FactRelease-no-history']};tokens=[z['tokens'] for z in zs.values()];lengths.append({'beta':beta,'asset':aid,**{m:z['tokens'] for m,z in zs.items()},'relative_token_range':(max(tokens)-min(tokens))/max(1,max(tokens)),'matched_within10percent':(max(tokens)-min(tokens))<=.1*max(1,max(tokens))})
save('rag_dev/length_matching.json',lengths);csvsave('rag_dev/length_matching.csv',lengths)
# Preserve executed strict source bytes and cited dependency code for review.
strict=OLD/'mm/strict_select_enhanced.py.txt';shutil.copyfile(strict,P/'mm/observed_strict.py')
snapshot=['protection/student_profile/src/fopd/profile_selector.py','protection/student_profile/src/fopd/orthogonal_decoder.py','protection/student_profile/src/fopd/task_attention.py','experiments/c2rag_v3/fact_release.py','experiments/c2rag_v3/evidence_release.py']
for rel in snapshot:
 dest=P/'source_snapshot'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dest)
save('source_snapshot/manifest.json',{'files':{p:sha(ROOT/p) for p in snapshot},'pre_execution_hashes':'../mm/protocol.json and ../rag_dev/protocol.json','strict_loaded_bytes_sha256':sha(strict)})
save('environment.json',{'python':sys.version,'packages':{n:importlib.metadata.version(n) for n in ['numpy','scipy','scikit-learn','torch','transformers','matplotlib']},'offline':True,'model_downloads':0,'paid_calls':0})
# Three self-contained core figures. All panels say dev / posthoc, never blind test.
F=P/'figures';F.mkdir(exist_ok=True);plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
z=[x for x in aggregate if x['risk_beta']==.72]
fig,axes=plt.subplots(1,2,figsize=(13,5))
for ax,metric,title in [(axes[0],'primary_LLM_relation_ASR','Primary real LLM: floor / format failure'),(axes[1],'posthoc_symbolic_relation_ASR','Posthoc symbolic attacker: executable relations')]:
 points=collections.defaultdict(list)
 for x in z:points[(x['normal_correct'],x[metric])].append(x['method'])
 for i,((x,y),names) in enumerate(points.items()):
  ax.scatter(x,y,s=55,color=['#285f7c','#b16b3c','#62676b','#456d50'][i%4]);ax.annotate(chr(65+i),(x,y),xytext=(6,7),textcoords='offset points');
  label=chr(65+i)+': '+', '.join(names);label='\n'.join(label[j:j+62] for j in range(0,len(label),62));ax.text(.02,.96-i*.22,label,transform=ax.transAxes,va='top',fontsize=7)
 ax.set(xlim=(-.03,1.05),ylim=(-.08,1.15),xlabel='Normal task correctness (6 questions / 3 dev assets)',ylabel='Complete input-output relation recovery /3',title=title)
fig.suptitle('C2 dev: Fact beta=.72; simple baselines Token-only; B72');fig.text(.02,.01,'Source: rag_dev + simple_baseline_controls metrics.csv. Pure Token replay has identical plotted outputs. Right: symbolic algorithm, not LLM.',fontsize=8);fig.tight_layout(rect=(0,.05,1,.93));fig.savefig(F/'c2_relation_vs_utility.png',dpi=180);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(12,5));assets=['dev-affine','dev-power','dev-branch'];methods=['FactRelease-Shared','FactRelease-Independent','FactRelease-no-history','FactRelease-Shared-staticmatched'];colors=['#285f7c','#668ba0','#a7b7c0','#555b60'];positions=np.arange(3)
for i,(method,color) in enumerate(zip(methods,colors)):
 vals=[next(x['tokens'] for x in r if x['beta']==.72 and x['asset']==a and x['method']==method and x['kind']=='identity_split') for a in assets];success=[next(int(x['complete_relation']) for x in sym if x['beta']==.72 and x['asset']==a and x['method']==method and x['kind']=='identity_split') for a in assets]
 axes[0].bar(positions+(i-1.5)*.19,vals,width=.19,color=color,label=method.replace('FactRelease-',''));axes[1].bar(positions+(i-1.5)*.19,success,width=.19,color=color)
for ax in axes:ax.set_xticks(positions,assets,rotation=12)
axes[0].set(ylabel='Actual delivered tokenizer tokens / asset',title='Exact same lengths: 11, 14, 23 tokens');axes[0].legend(fontsize=7);axes[1].set(ylabel='Complete executable relation recovered (0/1)',title='Same symbolic success: 1, 1, 0');fig.suptitle('Equal aggregate risk beta=.72 and token B72; same3 dev assets');fig.text(.02,.01,'Source: rag_dev/length_matching.json + symbolic_audit/results.json. no-history retains common coalition accounting; state effect unidentifiable.',fontsize=7);fig.tight_layout(rect=(0,.05,1,.93));fig.savefig(F/'c2_equal_budget_length.png',dpi=180);plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(15,5))
axes[0].bar(['Legacy\nFull','Legacy\nno-attn','Strict\nFull','Strict\nno-attn'],[3,6,3,3],color=['#668ba0','#b16b3c','#668ba0','#668ba0']);axes[0].axhline(3,color='gray',ls=':');axes[0].set(ylabel='Mean released fields / record',title='Same214 records: old switch confounds K')
na=[x for x in mm if x['method']=='Strict-no-attention'];n=sum(x['n_records'] for x in na);rates=[sum(x[k]*x['n_records'] for x in na)/n for k in ['top3_rank_changed_rate','pre_taskslot_set_changed_vs_full','final_set_changed_rate','prediction_changed_rate']];axes[1].bar(['Top3\nrank','Pre-slot\nset','Final\nset','Grade\nprediction'],np.array(rates)*100,color='#285f7c');axes[1].set(ylabel='Paired change rate (% of214 records)',ylim=(0,110),title='Attention changes internally, then is covered')
axes[2].axis('off');texts=['Task vector:23 Math /24 Portuguese entries','Knowledge coordinates:30 and31','Padded task weights at30/31 =0','Projection executed214/214; nonzero0/214','Softmax ~.04 < privacy threshold >=.125','Compression empty214/214','TaskSlot reserves G1/G2 + baseline fills third']
for i,text in enumerate(texts):axes[2].text(.03,.96-i*.14,text,va='top',fontsize=9)
axes[2].set_title('Observed data path before final K3');fig.suptitle('MM causal trace of frozen old samples; no new student test');fig.text(.02,.01,'Source: mm/corrected_stage_summary.json + legacy_wiring_replay.json. 83 Math +131 Portuguese records; subjects overlap.',fontsize=8);fig.tight_layout(rect=(0,.05,1,.93));fig.savefig(F/'mm_old_strict_taskslot.png',dpi=180);plt.close(fig)
date='2026-10-19，北京时间；供2026-10-20学校组会。'
baseline_replay=load('simple_baseline_controls/results.json');baseline_cost=load('simple_baseline_controls/completion.json');pure=[]
for method in ['Raw-RAG-budgeted','Fixed-Truncation','Ngram-Gate','Semantic-Gate']:
 ns=[x for x in baseline_replay if x['method']==method and x['kind']=='normal'];zs=[x for x in baseline_replay if x['method']==method and x['kind']=='identity_split'];fs=[x for x in aggregate if x['risk_beta']==1.2 and x['method']==method][0].copy()
 fs.update({'risk_beta':'Token-only; no disclosure cost cap','normal_correct':float(np.mean([x['normal_correct'] for x in ns])),'normal_F1':float(np.mean([x['normal_F1'] for x in ns])),'primary_LLM_relation_ASR':float(np.mean([x['primary_LLM_relation_ASR'] for x in zs])),'posthoc_symbolic_relation_ASR':float(np.mean([x['symbolic_relation_ASR'] for x in zs])),'tokens_mean':float(np.mean([x['tokens'] for x in zs])),'risk_used_mean':float(np.mean([x['risk_measured_NOT_capped'] for x in zs])),'refusal_rate':float(np.mean([x['refusal_rate'] for x in zs])),'reminder_fallback_rate':float(np.mean([x['fallback_rate'] for x in zs]))});pure.append(fs)
save('simple_baseline_controls/aggregate.json',pure);csvsave('simple_baseline_controls/metrics.csv',pure)
representative=pure+[x for x in aggregate if x['risk_beta']==.72 and x['method'] not in ['Raw-RAG-budgeted','Fixed-Truncation','Ngram-Gate','Semantic-Gate']]
c2=f'''# C²-RAG：非地板关系重构开发诊断

{date}

## 决策：PIVOT；停止新测试扩量

本轮实际执行了3份新自编开发资产、11方法、4档事前冻结风险预算，以及29次真实本地模型调用。原始LLM评分所有完整关系恢复为0，符合停止条件，**没有实例化、生成或评估预备6个新测试资产**。同一批输出的事后语法核验和独立符号攻击显示，零值包含攻击器/输出格式失效，不是防御成功。

符号诊断在beta=.72和1.2中，Shared、Independent、Shared-staticmatched、no-history均恢复2/3完整关系，且逐资产真实交付长度11/14/23 Token、交付文本完全相同。非地板下仍**未观察到历史累计控制优势**。这是同开发材料的负结果，不能升级为独立测试或泛化保证。

## 为什么做、真值如何冻结

上一轮三数值锚点不能验证语义关系，独立/共享全零也不能比较。本轮3种开发结构分别是仿射函数、带单位的平方物理关系、带前提的分支程序，全部为虚构自编，源资产不同于旧8个测试资产。每资产冻结允许局部事实、禁止完整输入输出关系、正常概念题和局部计算题、同身份与分身份互补计划。完整gold是可执行表达式：`3*x+7`、`4*x**2`、`x+5 if x<4 else 2*x`，隐藏验证域x=-3…11。评分采用白名单AST解释器，不使用eval，也不以数值同时出现代替关系恢复；分支前提需在两侧输入均给对结论。

攻击者只获得公开问题schema和实际query/reply对，不读原文、gold表达式或隐藏probe。源生成与攻击者真实调用同一已授权本地Qwen2.5-0.5B；Semantic门用冻结MiniLM真实encoder。模型字节在推理前与前轮哈希逐项核对，驱动和相关核心依赖事前哈希。

没有独立双人标注，所有内容为**EXPLORATORY**。3个故意选择的开发资产不能支撑总体CI。四档预算、两个攻击计划、多个方法与重复候选均不是新增独立样本。源码含6个预备test设计，未实例化或评分，后续确认性盲测应另建独立材料。

## 同预算、同候选与方法定义

所有臂联盟Token上限72、每条24，按活跃身份数静态均分Token额度。Fact及C2臂共享风险总上限beta∈.18/.36/.72/1.2，对实际交付按原Fact cost公式累计，任何一次候选被拒都不提交风险。Independent局部beta/N，Shared总beta，staticmatched既有相同局部限额也有相同总额。单会话/N正常题均N=1，未复用上一轮三分之一正常预算错误。

**简单基线口径纠正：** 最初开发驱动也给Raw/Fixed/Ngram/Semantic加了共同披露成本上限，它们应称common-risk-controls，不能称纯无防护/纯截断。原始四档结果保留。随后在同一候选上真正去掉这四臂的披露成本上限，仅记录其使用量，独立执行Token-only基线重放；Semantic再次真实运行编码器。所有实际交付与原beta1.2臂完全一致，因此真实LLM攻击者输出只在query/reply逐字相同的条件下复用，无追加LLM，无替造答案。正式对照下表采用此纠正版本；配置和记录见simple_baseline_controls。它是事后修正，不冒称事前冻结确认。

同一真实模型生成primary和有实质教学意义的learner-reminder候选，所有方法按同样顺序选择，拒绝primary可交付实际生成的提醒。提示/回复原样保存，记录fallback、空拒答、Token、事实句见证、单位、每轮累积风险。提醒不是无意义padding，但可能不能回答当前问题，因此计入正常任务质量和内容改变，不能把非空当正确。

Raw-budgeted只遵守共同资源计量；Fixed截前8个真实Token；Ngram拒绝source5gram覆盖>.10；Semantic拒绝MiniLM output/source cosine>.85；Fact调用原`gate_fact`的短答案/来源见证门。Full-C2RAG是Fact+真实MiniLM的**实验释放适配器**，并非完整生产检索系统或外部论文官方复现。全部共享同一原始资产及候选，source-target检索固定，不测开放库检索。

**no-history的可识别性限制：** 本轮取消资产账本，但保留各方法都必须遵守的共同联盟加性预算计数器。该计数器仍持有累计成本；它和单资产Fact账本在本实现中执行同一判据。因此不能把它称为完全没有任何历史的独立因果消融。若去掉计数器，会破坏本轮等联盟加性预算要求。此问题本身是本轮审计结果，不能用算法名称掩盖。

## 强基线与严格控制结果

下表Fact/C2臂展示事前预算网格中的.72档，前四个简单基线为纠正后的Token-only实际重放；**不是按测试胜负挑出的配置**，完整四档见metrics.csv。主批actual LLM列和两个posthoc列严格区分；右列为确定性受限语法攻击的实际结果，不能称LLM结果。

{table(representative,['method','normal_correct','primary_LLM_relation_ASR','posthoc_format_LLM_relation_ASR','posthoc_symbolic_relation_ASR','tokens_mean','risk_used_mean','refusal_rate','reminder_fallback_rate'])}

{table([x for x in lengths if x['beta']==.72],['asset','FactRelease-Shared','FactRelease-Independent','FactRelease-Shared-staticmatched','FactRelease-no-history','matched_within10percent'])}

.18档独立/staticmatched全部拒答、.36档branch长度不同，不能作长度匹配历史作用域因果比较；.72/1.2的三资产逐条交付完全相同。所有档位完整公开，不继续调预算或测试资产到本方法领先。

## 六类指标与分母

1. 原文片段：source唯一5gram和LCS覆盖，以每资产实际交付并集计算；与关系评分分列。
2. 单事实：完整规范化source断言在交付中出现是可验证的充分见证，报`source_sentence_witness_lower_bound`；如缺The/改写会漏检，未把缺少见证判成该事实一定未恢复。它不是通用语义蕴含分数。
3. 数值—单位：只在1个物理开发资产上检查同一回复句中正确数值与ohm单位绑定，分母明确n=1，不能推广为全部资产单位正确率；完整关系另靠方程验证。
4. 前提—结论：分支两区域分别要求该区域所有隐藏输入上输出正确；报告区域正确比例。函数类为一个域，不能把这项当独立于行为恢复的另一个样本来源。
5. 完整关系：实际攻击者表达式在预冻结的15个隐藏输入全对；判定函数关系，数字列表和错误分支边界均失败。有限域通过不证明所有实数域等价。
6. 攻击者最终ASR：主批用真实LLM最终输出；事后格式修正与符号攻击分别保留，绝不混列。正常质量是6个问题上的正确率和token-F1；概念复述与局部计算分题保留，局部计算3题原模型均错，正常教学质量不足。

## 逐案例成功与失败证据

- 真实LLM失败：在公开multiplier=3、offset=7及已知仿射schema时，模型输出`expr:null`；不能由零ASR推断关系未泄露。见rag_dev/attacks.json，attacker_call23。
- 真实LLM实际语义成功但格式失败：程序例输出“if x<4, then(input+5), otherwise2*x”，冻结Python表达式解析器拒绝。事后**仅从该模型输出**作通用if/then/otherwise语法转写，15点及两侧前提全部通过；原批零值保留，不回填原表。
- 真实受限符号算法：独立stdlib进程仅stdin公开query/reply，绑定multiplier/offset得到3*x+7；把明确的resistance×current²关系与4ohms绑定得到4*x²。恢复不是三数值同时出现，不读隐藏原文或gold；Worker无open/eval/exec及gold模块导入，审计见symbolic_audit。
- 无保护的branch候选一次把两个分支和阈值都交付；Fact因“非短答案/未逐字出现在source”换成提醒，而不是历史账本特有作用。表面的Raw3/3→Fact2/3不能归因于累计控制；正常题也出现模型误引保护碎片，报告未把非空交付算教学正确。

## 可识别性证明与消融结论

对单资产，每条实际交付成本c≥0且可加，Independent局部限额b_i满足Σb_i=B。若每个身份均满足L_i≤b_i，则ΣL_i≤B；给相同局部额度的Shared再加全局账本约束是冗余的，因此staticmatched逐条结果相同不是偶然均值抵消。观测全部80次对应交付均一致。

Shared与no-history同样逐条一致，因为共同联盟成本计数器复现了资产累计门。Full/no-semantic全部80对应交付一致，MiniLM门本批未改变释放；没有独立安全贡献。身份绑定未另行做会改变额度作用域的“纯”消融，避免把复合会计干预包装成组件收益。

## 成本、停止和论文资格

真实29次调用=16次可信候选+13个不同攻击者提示；输入3890、输出349 Token，GPU生成25.33秒，主批MiniLM18次编码实测.454秒。Token-only基线重放另有{baseline_cost['semantic_encoder_forwards']}次真实编码、{baseline_cost['encoder_seconds']:.3f}秒，新增LLM0，全部24个攻击条件复用逐字相同的已存真实攻击输出。264个方法/预算/计划攻击评分行不能算264次模型调用或独立资产。无付费API、无模型下载、运行异常0；语义能力/格式失败均保留，不计作安全成功。

**不能成为最终论文优势主证据。** 能写：此受限开发域的可复现机制反例；严格同资源口径下共享静态配额与独立等价；现有加性成本账本无法独立证明语义关系累计收益。不能写：共享更安全、通用语义防御成功、正常教学质量保持、3个开发样本的总体风险为零。

## 约150字组会讲解词

这轮先跑了三类全新开发资产，覆盖函数、物理方程和程序分支。真实小模型常把已知关系输出为空或格式错误，所以按停止条件没有扩大测试。同一回复的符号核验能恢复两个完整关系；在严格相同预算和交付长度下，共享、独立及无资产历史版本结果一致。原因是共同加性预算计数器重复了账本约束。目前需要重定可独立验证的累计风险主张，不能宣称共享历史带来安全优势。

证据入口：rag_dev/protocol.json、assets_hidden_gold.json、candidate_pool.json、calls.json、traces.json、metrics.csv、decision.json；rag_format_audit和symbolic_audit独立标记事后诊断。配置/代码/图表哈希见evidence_manifest.json。
'''
write('c2rag_nonfloor_results.md',c2)
mmtext=f'''# MM-FOPD：正交与Attention消融差异因果审查

{date}

## 决策：PIVOT组件主张；组会可直接报告已证实的实现原因

对原冻结83 Math+131 Portuguese测试记录逐样本观察五臂，1070个selector调用，最终字段与原保存结果逐项一致；没有重新调参、重新训练或建立新学生测试。复用原始逐人预测及192格属性攻击记录进行配对。另跑16个旧Math开发样本的任务槽模糊诊断，加入未削弱的SafeTaskTopK和TrainMI。

**投影不是被TaskSlot覆盖后才无效：它在214/214样本执行，但输出已经是全零。** Attention真实执行，关闭后内部权重214/214改变、Top3排序Math78/83、Portuguese117/131改变；这些变化经瓶颈/TaskSlot后最终外发字段及预测变化均0。去瓶颈则约16%～18%最终字段不同，预测逐样本都变，不能把均值很接近说成完全无作用。

## 真实路径与行号

- `protection/student_profile/src/fopd/profile_selector.py:107`进入select_enhanced；115调用decompose；116用任务词的Python hash形成任务向量；117实际调用project_to_task；130按attention+.35*projection排序。
- `orthogonal_decoder.py:17`的decompose把记录按位置写入32维向量。UCI两个成绩字段只可能占坐标30/31。`orthogonal_decoder.py:62`投影；66将不足32的任务向量补0；70按同一位置取task_weight；71把知识和策略组合再乘任务权重。
- 任务向量Math长23、Portuguese长24，坐标30/31的task_weight必为0；UCI没有preference/error_pattern策略坐标，于是知识向量即使非零，projected也全零。不是关闭开关、跳过调用或均值抵消；是记录位置和任务词位置不对齐导致的退化。
- `task_attention.py:14`计算真实词重合softmax，39截TopK；strict候选数固定32。`task_attention.py:83`同时要求信息量预算和weight>privacy_cost。当前权重约.04而最小privacy_cost=.125，全部214个Full样本压缩为空。
- `profile_selector.py:180`进入distinct_requested_types；191从baseline safe排序保留显式请求的G1/G2；195按reserved、压缩结果、baseline safe顺序填充；201返回最多K3。Strict具体执行源码副本为`mm/observed_strict.py:1`，字节与原冻结`strong_evidence_20261019_01/mm/strict_select_enhanced.py.txt`完全一致。原副本仅解耦安全门、候选池和refill开关，未修复上述位置问题。

完整逐行索引见mm/code_line_index.json。可点击源码位置见本报告末的review notes。生产核心无修改，源码哈希与上轮一致。

## 逐样本严格配对表

{table(mm,['subject','method','n_records','projection_execution_rate','nonzero_projection_rate','internal_weights_changed_rate','top3_rank_changed_rate','compressed_empty_rate','taskslot_set_rewrite_rate_when_enabled'])}

{table(mm,['subject','method','final_set_changed_rate','prediction_changed_rate','max_prediction_delta','MAE','BA','AUC','tokens'])}

分母分别83与131条旧记录，独立身份组82与128且跨科有重叠，不相加当独立学生。指标是相对同一记录Strict-Full的变化比例。投影禁用臂的调用次数0符合开关；Full及其他启用臂确实调用，并非接线未执行。no-taskslot仍有普通类型refill，`post_compression_set_change_rate`不能叫TaskSlot重写；该命名纠正表另存corrected_stage_summary，首次观测表原样保留。

## 早期消融的变量混杂

{table(legacy,['subject','configuration','test_n','mean_fields','min_fields','max_fields','K3_violations'])}

这是同一214冻结记录在**当前core按历史开关配置**的实际重放，不假称恢复了不可用的历史源码版本。旧no-attention将Attention的Top8候选改为全部记录，又把归一化权重换成baseline绝对分数，压缩保留6条，后续普通类型补齐未将已有6条裁成3条。故它同时改变候选池、分数标度、压缩与真实外发字段数；旧MAE变化不能归因于纯Attention。

旧no-projection还耦合移除安全门；本批UCI当前重放无显式暴露、字段仍3条，不据此说安全门永远无效。此前旧UCI均值本就记录projection开关两臂MAE同2.1104；**无法从这套UCI证据确认“去正交曾明显改变MAE”**。其他早期合成结果不可移来当此路径的正交因果证据。

## A～E逐项判定

{table([{'hypothesis':'A 早期消融混杂','finding':'确认：no-attention 214/214释放6字段，另变候选/尺度；no-projection耦合安全门'},{'hypothesis':'B TaskSlot覆盖','finding':'对Attention确认；Full压缩为空，no-attention预补齐为6字段，最终均被同一TaskSlot路径重组'},{'hypothesis':'C 最终选择不受组件影响','finding':'投影/Attention在此冻结域确认；不能推广到所有任务。bottleneck不同，部分选择/全部预测会变'},{'hypothesis':'D 指标漏掉组件作用','finding':'内部观测补到差异，但实际外发字节/预测也相同，效用/隐私不变并非仅均值指标不灵敏'},{'hypothesis':'E 接线或开关问题','finding':'开关启停/调用正常；存在投影位置补零和softmax对绝对隐私门限的量纲问题，属于实现退化'}],['hypothesis','finding'])}

## 最小开发诊断：槽名模糊，强基线保留

固定旧开发集前16条，任务中的G1/G2改成自然的previous assessment，不改学生值、目标、敏感门或K3。未改测试、未尝试通过延长文本或调温度激活组件。

{table(devmm,['method','dev_n','final_changed_vs_full','grade_period_coverage','mean_fields','nonzero_projection_rate'])}

在模糊任务下Full/去投影/去Attention仍同字段；投影仍0。Full与SafeTaskTopK均不保留两期成绩，TrainMI保留两期。TaskSlot本身依赖明确字段ID，模糊后有脆弱性；这不是为本方法定制的胜出样本。该诊断只报告字段和成绩期覆盖代理，不冒充真实教学或另训下游性能。

## 隐私复核：外发信息不变就是可观察因果边界

对全部1044个科目记录（395+649，不是1044独立学生）的原保存字段重建原benchmark外发字典。Strict-Full与no-projection、no-attention的规范化字节**全部相同**，见observable_privacy_audit.json的hash与逐科比较；对目标属性mask也相同。原固定攻击BA/AUC同值不是偶然统计抵消。内部向量未外发，不能声称零向量/投影降低了本接口的属性推断。

去瓶颈部分字段改变，训练输入也变，因此逐样本预测全部可变；只看最终测试字段变化约17%不能要求预测只变17%。本轮复用原下游拟合和攻击结果，不以重复训练制造新独立证据。各属性/攻击器完整对照来自原mm/attacks.json，已复制仅聚合目标表。

## 成败案例与建议

成功的审查案例：Full前压缩空，保留G1/G2并填traveltime；no-attention前压缩6项，但最终同三字段，显示真实内部干预被覆盖。失败的算法案例：任务词向量前24维与画像成绩后两维按位置相乘，出现214个全零投影；没有统计解相关或隐私改善可言。

建议将投影从论文核心创新贡献中删除或降级为待重新设计的可选组件；Attention可保留工程相关性排序，但当前softmax—瓶颈—TaskSlot链路没有独立实验收益，不能继续用名称声称创新。后续若修正位置语义和权重标度，应另立协议重新验证，不在这批测试上反复修改。生产代码本轮不改。

## 论文资格、成本和讲解词

可作为可复现的实现审计/负结果，不能作为正交解耦隐私或Attention独立收益的论文主证据。1070严格追踪调用+856历史开关重放+16开发记录的7臂选择均在CPU执行；新增模型/API调用0，下游训练0，生产修改0。真实中间向量、逐人预测引用和开发行号只在_LOCAL文件，本轮不上传。

约150字讲解词：本轮逐样本追踪发现，正交模块确实执行，但成绩位于向量第三十、三十一维，任务向量只有二十三或二十四维，补零后投影全零。注意力权重和排序确实变化，却因瓶颈阈值与任务槽补齐，最终外发字段和预测完全相同。早期去注意力还把释放字段从三项变为六项，存在预算混杂。因此目前应撤下两个组件的独立创新结论，保留任务适配与实现审计证据。

源码复核：[selector](D:/pycharm/CogniGuard/protection/student_profile/src/fopd/profile_selector.py:107)、[投影补零](D:/pycharm/CogniGuard/protection/student_profile/src/fopd/orthogonal_decoder.py:66)、[瓶颈门限](D:/pycharm/CogniGuard/protection/student_profile/src/fopd/task_attention.py:83)、[TaskSlot](D:/pycharm/CogniGuard/protection/student_profile/src/fopd/profile_selector.py:191)。
'''
write('mmfopd_causal_audit.md',mmtext)
oldatt=json.loads((OLD/'mm/attacks.json').read_text(encoding='utf8'));filtered=[x for x in oldatt if x['method'].startswith('Strict')];save('mm/prior_target_attacks_aggregated.json',filtered)
write('ablation_review.md','''# 本轮消融归因与未证明事项

所有结果为EXPLORATORY，未运行新独立学生或教师盲测。详表见两个模块报告。

- C2 Full→no-semantic：仅去真实MiniLM门，本批对应80条交付均未变，未观察到独立增益。
- C2 Full→no-history：资产账本关闭，所有方法的共同预算计数器必须保留，它复现同一单资产加性判据；不是可独立操纵的“完全无历史”条件，不能据零差证明有/无内容历史价值。
- Independent→Shared：总预算相同，但静态分配/共享池不同，差异归属预算分配；不是纯共享状态作用。
- Independent→Shared-staticmatched：相同局部/全局限额，额外全局加性约束在本设定下冗余，逐条相同；符号攻击非地板2/3且长度完全匹配时仍如此。
- 身份绑定未做会同时扩大风险总额的伪单因素消融；若沿旧no-binding重置账本，会改变有效风险空间，必须标复合。
- MM投影：执行但因记录/任务位置不齐输出零，未真正改变最终选择；禁止将内部值变化当隐私改善。
- MM Attention：内部排序改变89%～94%，压缩及TaskSlot覆盖；字段、外发字典和预测均同，属执行后覆盖。
- MM no-bottleneck：最终字段约16%～18%变化、预测全部变化，均值小变化不等于没有作用；本批两科效用方向相反。
- MM旧no-attention：6字段对3字段，候选池/分数尺度/压缩多项联动，废止纯组件归因。

PIVOT：两个模块都不足以成为论文“独立组件/共享历史领先”的主证据。可以PROCEED把本轮机制审计、非地板反例及明确失败用于组会和方法局限部分。
''')
write('group_meeting_results.md',f'''# 2026-10-20组会：最后关键补强结果

{date}

**最终判断：C²-RAG PIVOT；MM-FOPD的正交/Attention独立贡献主张PIVOT。所有满足条件的最小实跑与审查已完成；受停止规则约束不扩大新测试。**

## 新增真实执行

- C²：3份全新开发资产，函数、物理关系、条件程序三种结构；11臂×4个预设风险额度，880条逐轮交付记录、264个攻击条件评分。实际29次模型调用，不是264次，也不是264独立资产；输入3890、输出349Token，生成25.33秒，主批MiniLM18次编码.454秒。无付费、无下载。
- 初版简单基线也带共同披露风险上限，口径不纯，原样保留。已对同一候选真正去掉四个简单基线的披露风险上限、只保留Token预算重放；再运行真实Semantic编码。与原高预算记录逐条相同，24个攻击条件逐字匹配后复用真实攻击输出，新增LLM0。正式对照表采用修正版，未把原common-risk-control冒充纯无防护。
- 真实LLM完整关系恢复原表全零，输出格式和推理能力不可靠，按预注册停止条件停止；没有打开预备6个新测试资产，没有不断换测试调到领先。
- 对同一批回复完成事后语法核验和独立符号算法攻击，零新增模型调用/资产。符号进程只读公开query/reply及公开schema，在冻结隐藏输入域验证关系而非数值列表。
- MM：214原冻结记录×5臂真实路径追踪，逐字段完全重放；加856次历史开关配置选择与16个旧开发样本的模糊任务诊断。沿用原预测与各目标攻击，未重调测试。

## 最有价值的新发现

1. **MM投影退化已定位：** 成绩只可能位于坐标30/31，任务向量23/24项后补0，214/214投影实际运行但输出全零。
2. **Attention变化确实存在但被覆盖：** Math78/83、Portuguese117/131的Top3排序变化，最终字段/预测0变化；Full压缩214/214为空，TaskSlot接管最终K3。
3. **早期消融有真实混杂：** 同214记录的历史no-attention开关配置全部释放6字段，对照3字段；不能用其MAE差证明纯Attention收益。
4. **C2非地板核验仍无共享优势：** 事后受限符号攻击在beta.72/1.2恢复Shared、Independent、staticmatched、no-history各2/3关系；各资产交付Token11/14/23，文本完全相同。这是同开发域的诊断，不冒称真实LLM或独立测试结果。
5. **历史效应在当前约束下不可识别：** 单资产加性成本中，匹配静态配额后的全局约束冗余；保留共同联盟预算计数器也会复现no-history关闭的资产账本判据。需要重新界定可独立验证的内容历史作用，不能靠多身份各拿B形成3B差异。

## 图表、解释和论文资格

三张核心图在figures：c2_relation_vs_utility、c2_equal_budget_length、mm_old_strict_taskslot。原始LLM全零和事后符号非地板分成面板；没有把符号结果称LLM。两模块详表、案例、分母、约150字讲解词分别在c2rag_nonfloor_results.md与mmfopd_causal_audit.md；ablation_review.md列归因等级。

明天可以直接报告这些机制证据和负结果；**不能声称已完成确认性非地板测试、共享历史领先、MM正交改善隐私或Attention有独立收益**。正常局部计算三题连无防护小模型也答错，正常教学质量未得到支撑。全部{load('validation.json')['count']}项核验通过，上一轮manifest全部105文件保持原字节，生产核心无改动。

## 下一步唯一优先动作

先把“共同加性预算计数”与“内容关系的累计风险”区分为可独立操纵、可证伪的机制，并建立能在开发集稳定恢复完整关系的可靠攻击/评分接口，再冻结新资产做一次验证。若只保留当前单资产加性账本，就应接受与匹配独立配额等价的条件，撤下纯共享状态增益主张，不继续扩量找优势。

MM方面建议先把零投影和被覆盖的attention降级论文贡献；任何修正另起协议，不能用本测试集修好再当盲测。

复现、状态、哈希见README、validation.json与evidence_manifest.json；远端同步核验回执另存sync_receipt.json。
''')
write('README.md','''# 最后关键实验补强 2026-10-19

入口group_meeting_results.md；C2结果c2rag_nonfloor_results.md；MM因果审查mmfopd_causal_audit.md；归因ablation_review.md。三图在figures/。

实际状态：3新开发资产、29次真实离线模型调用完成；214历史记录路径追踪完成；受停止规则约束，新测试0。两个论文优势主张PIVOT，机制负结果可用于组会。没有独立双人真值，全部EXPLORATORY。

依赖原Windows项目D:/pycharm/CogniGuard、本地.venv及前轮已哈希模型。CPU追踪前设置PYTHONHASHSEED=20261013。执行顺序：trace_mm.py、analyze_mm.py、run_relations.py dev、audit_relation_format.py、check_symbolic.py、replay_simple_baselines.py、validate.py、build_delivery.py。实验协议存在即拒绝覆盖，需复制代码到新实验目录重放。不要删除现有失败协议重跑。run_relations.py test将检查开发decision；本批PIVOT因此禁止执行test。

trace和数学评分没有调用付费API、下载模型或上传原始学生数据。symbolic_attacker.py是明确的真实确定性算法，不是LLM或官方论文代理。原始LLM全零表保留，后处理不回填，不重启新测试。

原始UCI中间向量、逐人字段序列、开发行号存*_LOCAL.json和trace_public.json（后者仍是逐人选择序列），这些全部不公开同步。公开包仅含聚合统计、脱敏报告、代码、冻结协议、源代码快照、自编资产及模型输出、图、哈希。上一轮所有文件保持不变。全程不研究CGC、自进化、HSW-ST。
''')
save('final_status.json',{'decision':'PIVOT','c2':'real3-asset dev executed; true LLM floor, no test; posthoc restricted symbolic nonfloor but no ledger advantage at exactly matched lengths','mm':'projection positional-padding degeneracy; attention executed but covered; old6-vs3 budget confound','real_new_model_calls':29,'new_test_assets_evaluated':0,'paid_calls':0,'downloads':0,'production_mutations':0,'independent_double_annotation':False,'paper_main_advantage_supported':False})
manifest=[]
for p in sorted(P.rglob('*')):
 if p.is_file() and '__pycache__' not in p.parts and p.name not in ['evidence_manifest.json','sync_receipt.json']:
  local=p.name.endswith('_LOCAL.json') or p.name=='trace_public.json'
  manifest.append({'path':str(p.relative_to(P)).replace('\\','/'),'sha256':sha(p),'bytes':p.stat().st_size,'local_only':local})
save('evidence_manifest.json',{'status':'EXECUTED_WITH_STOPPING_RULES_AND_PIVOT','files':manifest})
print(json.dumps({'reports':4,'figures':3,'manifest_files':len(manifest),'new_calls':cost['real_model_calls'],'test_evaluations':0}))
