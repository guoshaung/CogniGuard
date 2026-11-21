"""Create reviewable Chinese reports and scientific figures from completed runs."""
from pathlib import Path
import json,sys,collections
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).parent;sys.path.insert(0,str(P));import design as d
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def write(n,s):(P/n).write_text(s,encoding='utf8')
def table(rows,cols):
 def fmt(x):
  if x is None:return 'NA'
  if isinstance(x,float):return f'{x:.4f}'
  return str(x).replace('|','/')
 return '| '+' | '.join(k for k,_ in cols)+' |\n| '+' | '.join('---' for _ in cols)+' |\n'+'\n'.join('| '+' | '.join(fmt(x.get(v)) for _,v in cols)+' |' for x in rows)+'\n'
metrics=load('comparison_derived.json');dev=[x for x in metrics if x['phase']=='dev'];test=[x for x in metrics if x['phase']=='test'];paired=load('test_results/paired_mechanisms.json');intervals=load('test_results/paired_intervals.json');trans=load('dynamic_transitions.json');contexts=load('context_comparison.json');validation=load('validation.json')
lookup={(x['intent'],x['wording'],x['method']):x for x in test}
for phase in ['dev','test']:assert load(phase+'_results/completion.json')['status']=='COMPLETED'
corecols=[('方法','method'),('MAE↓(分/100)','MAE'),('已观测分数MAE↓','observed_score_MAE'),('契约Recall↑','contract_schema_recall'),('可用契约Recall↑','available_contract_recall_micro'),('BA宏均值','BA_macro'),('AUC宏均值','AUC_macro'),('实际Token','actual_tokens_mean'),('缺失值比例','released_missing_fraction')]
summary_table=table([x for x in contexts if x['phase']=='test'],[('任务','intent'),('表述','wording'),('Full MAE','Full_MAE'),('Safe MAE','SafeTaskTopK_MAE'),('TaskSlot MAE','TaskSlot_MAE'),('TrainMI MAE','TrainMI_MAE'),('契约规则MAE','StageRoleRule_MAE'),('Full−noP','delta_Full_minus_no_projection'),('Full−noA','delta_Full_minus_no_attention')])
write('data_availability_and_leakage.md','''# OULAD可用性、许可、资源及泄漏审查

**状态：AVAILABLE；已完成真实开发与一次后年保留验证。** 下载来自作者在原论文中引用的figshare v1，元数据确认CC BY4.0；非第三方重打包。原始数据与逐学生记录仅本地，远端只同步聚合与代码。

出处：Kuzilek, Hlosta & Zdrahal (2017), Open University Learning Analytics Dataset, Scientific Data 4:170171，[原始论文](https://doi.org/10.1038/sdata.2017.171)，[作者原始数据DOI](https://doi.org/10.6084/m9.figshare.5081998.v1)，[当前OU官方入口](https://research.stem.open.ac.uk/ouanalyse/dataset/)，[CC BY4.0](https://creativecommons.org/licenses/by/4.0/)。本轮衍生了时间截断特征、学生分组、研究标签和聚合报告，均为修改而非原始官方变量。作者/来源/许可及改动说明保留。

## 实际资源

作者archive=46,750,706字节（44.6MiB），下载硬限64MiB，作者MD5=7412686fd77cf0e0ee1e8c3e9b354308，实际一致；完整SHA256见acquisition.json。只下载一次，不下载模型、不使用付费API。studentVle压缩内原文453,836,331字节，用250000行块流式处理，未落地解压；关系表约10MB。每次仅选择预定学生/课程/时点。网络上限和磁盘余量在acquisition_protocol中先记录。本轮两次流式扫描各10,655,280行，实际建模只含下述小规模队列，不将扫描行数当独立学生数。

## 真实分母与分组

官方studentInfo共有32,593条课程注册行，但全表只有28,785个唯一学生ID；3,538个ID在多条注册行出现，不能按行随机拆分。BBB、DDD、FFF预先固定，2013J训练/开发，2014J仅保留验证；同人全局SHA256分组，另按固定哈希排序截取每课200训练、70开发、70保留候选。每个学生在同一presentation只留字典序首个所选课程。分组不看成绩、性别或残疾标签。

原候选训练600、开发210、保留210；按注册活跃、目标可用条件筛选后：训练484人/1337快照，开发166人/473快照，保留167人/462快照。三组学生ID两两交集0。阶段为第42/98/154天，各阶段都按同一规则，未调整到更有利的阶段。快照数不是独立人数，六种任务表述复用相同快照，不将2772个任务请求称2772名测试学生。

开发满足预先的双侧门槛才生成independent_protocol：Attention移除导致至少5%真实payload变化、绝对MAE差>=.5分，且开发>=100人、两属性均至少10正/负学生。保留协议写入后才构建2014J保留标签。全部课程、阶段、任务、表述和10方法进入保留验证，没有只挑开发获胜的单元。没有超参搜索；沿用上轮冻结alpha=.25、温度=.25、成本系数=.25等，Ridge alpha10及LR/RF设置亦预先固定。

## 时间与选择泄漏

VLE只用date<=t的已发生点击，近期14天及此前14天分开；历史成绩只用TMA due<=t−7、date_submitted<=t−7、非banked且score非缺失。按历史due顺序确定最新成绩和更早均值。每例校验目标TMA的due>t且<=t+56，并确认目标ID未进入历史成绩。点击、截止、提交最大时间在本地逐例源审计中记录；2272个不同训练/开发/保留快照的检查均通过。final_result、未来点击、未来注销日期、学生ID及敏感标签没有进入候选字段或预测特征。

**未解决的时间可用性限制：OULAD没有成绩公布时间。** 七天滞后只是可复核的研究代理，不能证明该成绩在当时已向实际系统公布，因此不宣称严格在线无泄漏。previous_attempts/studied_credits视为注册时已知静态信息，原数据也缺少逐时变化版本。registration用于判断t时已注册；仅当unregistration<=t才排除，不把未来退课提前用作特征。

目标取未来56天内首个计划TMA：在due+7内提交的记录用实际score，否则定义为0；另报已观测成绩子集MAE。0是本实验构造的“未按窗口提交即零分”目标，不冒充官方missing score。banked目标/及时提交但缺成绩的目标被排除并计数，属于目标可观测性条件与潜在选择偏差；不能称完全前瞻、无条件的全学生表现估计。开发候选排除banked34、已退课582个快照、未注册3、成绩缺失1；保留排除banked9、已退课159个快照。具体表在*_data/availability.json。

## 尚受阻的确认性结论

BLOCKED：没有独立教师双人标注的“真正必要信息”真值，当前只报告作者事先冻结、公开给所有方法的三字段任务契约Recall。真实教学干预收益与LLM答复质量也未评估。数据本身真实、成绩来自官方记录；这不自动使人工任务设计成为人类盲标确认性实验。全部结论为EXPLORATORY。
''')
dimension_rows=[{'field':k,'type':v[0],'sensitivity':v[1],'role':v[2],'meaning':v[3]} for k,v in d.FIELDS.items()]
write('mechanism_and_code.md','''# 机制与代码边界

本轮只新增独立实验目录，不修改生产核心或旧证据。preservation/validation记录生产三文件及旧批次302个文件哈希未变。冻结副本包括原ProfileSelector、OrthogonalDecoder、TaskAttention、旧StrictSelector和上轮修复选择器。函数名、真实行号、SHA256见code_paths.json。

## 共享编码与数学含义

字段z(r)=对应公共角色单位向量；任务m由同一角色词表在问题中的显式别名得到。OULAD域适配固定为8个角色，13个字段如下；不依字段顺序，不用字段数值、未来成绩或属性标签训练词表。角色定义、别名和任务先于开发结果冻结。

'''+table(dimension_rows,[('字段','field'),('类型','type'),('敏感成本','sensitivity'),('角色','role'),('含义','meaning')])+'''
P=diag(m)，满足P'=P、P²=P、<Pz,(I−P)z>=0；验证全部256种掩码。该运算只是**任务角色的正交坐标投影**，不保证敏感子空间解耦、随机变量独立或互信息消除。投影后向量仅供内部打分，实际对外仍是三个字段及其真实值/NA。所有选择器都知道同一公共角色词表、任务契约和字段敏感成本，不让Full独占任务真值。

Attention用公共record_id/type/knowledge/角色别名的TF-IDF余弦c，w=softmax(c/.25)，u=w/max(w)。分数s=.25||Pz||+.75u−.25sensitivity+bounded_slot_bonus。Slot仅在显式提及mastery ID时加最多.08，不强制补齐/接管。预算子集优化在K3、敏感门、Token64内最大化sum(s)−.15同角色字段对数；不称信息论bottleneck。删除投影仅去该项，删除Attention以常数1代替u，删除优化用同硬约束贪心，额外no-taskslot仅去奖励。

## 共同接口与原版适配

每方法从完全相同的13个安全候选出发，敏感门<=.7；性别、残疾等原始敏感列始终不进选择器，成本为研究策略非法律分类。输出是排序field=value三行，缺失明确为NA；同一个现有Qwen tokenizer逐条计真实Token，cap64且无填充。公开任务/课程/阶段/日历作为共同已知查询上下文，不计为私密画像释放，所有效用模型和攻击器均可使用。外发字段名的presence及NA可用性本身也进入攻击视图。

Original是冻结旧StrictSelector经相同安全候选入口、覆盖完整候选的attention、K/Token硬裁剪后的移植，非原生代码不变结果；TaskSlot仅开启其distinct mastery策略。共同ProfileRecord.value为field=value文本，保持既有画像卡接口。**旧OrthogonalDecoder试图float(value)会回退默认.5，且仍用任务词哈希位置坐标**；因此Original不是经过OULAD数值表示优化的最强旧模型，不能用它弱于Full证明修复创新。主要推断依赖未受此问题影响的SafeTaskTopK、TrainMI及两个透明规则对照。

SafeTaskTopK用同元数据原始余弦Top3；TrainMI仅训练快照上的未来目标拟合MI（中位数补缺也仅训练），任务目标相同故六条件MI次序相同，不以开发/测试标签拟合。StageRoleRule直接使用公开契约的三个字段，K/敏感/Token门一致；其契约Recall按定义为1，不是独立教师必要信息上界。

额外RelevanceCostRule在开发后、保留结果完成前冻结为普通贪心：Top3(.75u−.25sensitivity)，无投影、Slot或子集优化。它是解释性规则对照，不作为新方法提案、不调参。对所有训练/评估快照校验Token可行、无约束最优Full集合一致，并逐条比较真实评估payload；若完全一致，同一确定性拟合的效用及攻击结果自然相同，明确复用而不冒充额外模型运行。

## 动态能力边界

真实特征值随阶段变化，但当前修复选择器只看任务/字段元数据，未输入学生数值、NA或实际更新时刻来决定相关度（数值只影响Token可行性）。因此不能因输入来自动态数据就称其具有动态个体适应能力。跨阶段字段名变化与实际值变化分开计量，详见dynamic_transitions。词表人工定义、模糊表述也由作者设计，未覆盖任意自然语言或跨教师任务分布。
''')
ablation_cols=[('任务','intent'),('表述','wording'),('消融','method'),('非零投影','projection_nonzero_rate'),('投影内部变化','projection_internal_changed_rate'),('Attention内部变化','attention_internal_changed_rate'),('Top3变化','top3_rank_changed_rate'),('最终payload变化','actual_payload_changed_rate'),('预测变化','prediction_changed_rate')]
write('strict_ablation.md','# 严格配对消融：2014J保留组\n\n每行同462个快照/167名学生，相对Repaired-Full。内部变化比例和实际外发变化分别报告；全部保留K3、门限.7、候选13项、Token64、相同模型及训练组。\n\n'+table([x for x in paired if x['method'].startswith('Repaired')],ablation_cols)+ '\n## 配对MAE差值（Full−对照，负值代表Full更小）\n\n'+table([x for x in intervals if x['reference'] in ['SafeTaskTopK','Repaired-no-projection','Repaired-no-attention','Repaired-no-bottleneck','Repaired-no-taskslot']],[('任务','intent'),('表述','wording'),('对照','reference'),('差值','delta_MAE_Full_minus_reference'),('学生分组bootstrap95%','student_group_bootstrap95')])+'''
投影Full非零不代表有效：no-projection使内部投影变零，但所有2772个保留任务输出不变，预测及属性攻击结果也不变。子集优化和Slot奖励移除同样无最终变化。Attention移除在三个条件下改变全部输出并使MAE增大，属于真实选择/预测作用；另外三个条件最终不变。该效果已在开发/保留重现，但同一公开TF-IDF相关度成本贪心可完全替代Full，不能称独立创新。

各方法按其实际释放视图分别训练同一规格Ridge和攻击器；单因素指选择机制干预，非声称所有方法共用一个固定参数预测器。1000次学生组bootstrap仅反映当前固定拟合与样本的条件不确定性，六表述/多比较未作多重校正，训练不确定性未覆盖；不以微小CI越零作为独立创新证据。
''')
body='''# MM-FOPD OULAD跨数据集真实验证

**决策：PIVOT。** 完成真实小规模开发和一次预先锁定的学生不重叠、后年presentation保留验证。Attention有真实效用作用；正交角色投影、复杂子集优化与Slot奖励没有独立贡献。Full的全部保留输出可由普通TF-IDF相关度减固定成本规则逐条复现，未证明不可被简单规则替代的安全—效用收益。建议收缩为透明相关度/成本排序+硬安全门+精确Token会计，投影、冗余优化、奖励Slot删除或降级为可选。正式核心未修改。

## 实际执行与版本

OULAD作者CC BY4.0原始数据下载44.6MiB且MD5一致；复用本地模型tokenizer，不运行LLM或付费API。先冻结任务和参数，再构建2013J小开发，满足预定双侧差异门槛才锁定2014J保留协议，随后一次构建/评估保留集；无调参、无替换测试、无扩大任务寻找领先。两期各60个方法/任务单元、240个属性攻击单元；另对保留的同240个攻击拟合逐阶段复核，BA/AUC全部与主运行精确一致，不能当新独立样本。

训练484人/1337快照，开发166人/473快照，保留167人/462快照。三个公开课程、三个阶段、三意图×两表述；所有方法同一底层人/时点集合。原候选810/210，活跃和目标可用过滤导致实际分母减少，见data_availability_and_leakage。验证302个旧证据文件与生产三文件哈希未变；56,100条真实开发/保留回复逐条复算Token，全部三字段、Token<=64。

任务是根据时点画像预测未来首个TMA成绩（0–100），真实提交成绩来自官方，未及时提交定义为0；不是教学干预RCT，也未衡量LLM答复质量。UCI旧复核仍保留，本轮不复用其测试做盲测，不直接比较不同分制的跨数据集MAE数值。OULAD评分真值独立于选择器；任务契约和模糊措辞是作者冻结的研究设计，缺独立教师标注，因此全部EXPLORATORY。

## 核心对比，2014J保留组

'''+summary_table+'''
RelevanceCostRule在六格均与Full相同（实际2772/2772个保留payload，开发2838/2838也一致，训练所有行可行且同无约束最优集合），因此表中可将Full数值逐格赋予这个简单规则；这是已证明的输入/输出及确定性拟合等价，不是假装额外重训了一组模型。

Full与Safe在5/6格完全同内容。模糊readiness中MAE 21.3877对23.1796、差−1.7919，学生组描述区间[-3.2136,-.3316]；但投影和Attention各自删除均不改变这一格，普通相关度成本规则仍完全同Full。其BA .6404对Safe .6390、AUC .6578对.6569略高，**不是更好的隐私推断结果**。此处只能归因于透明成本加权选择，不能归因于投影或复杂结构。

模糊trajectory中Full MAE22.4881、关闭Attention23.7456；engagement显式22.4722对26.2310、模糊22.5640对26.2310。三项为实质选择和预测变化，Safe在这些条件均与Full相同，所以证明了保留相关度排序的实用价值，未证明新增Task Attention机制强于普通TF-IDF。其他三格关闭Attention无最终变化。

## 全方法详细指标

'''
for intent in d.INTENTS:
 for wording in ['explicit','ambiguous']:
  body+=f'\n### {intent} / {wording}：462快照、167学生\n\n'+table([x for x in test if x['intent']==intent and x['wording']==wording],corecols)
body+='''
## 动态阶段、模糊需求与真正知识保留

按42/98/154天的完整MAE、契约覆盖、实际Token见stage_utility.csv，按阶段/属性/攻击器BA/AUC见stage_privacy.csv。Full相同意图/措辞下的相邻学生快照字段名变化率为0，实际值payload却会变化，证据见下表。角色投影和权重主要受任务公共文本决定，没有个体数值适配；不能用时序输入包装“动态认知能力”。

'''+table([x for x in trans if x['phase']=='test'],[('任务','intent'),('表述','wording'),('相邻学生阶段对','adjacent_student_stage_pairs'),('字段集合变化','field_set_changed_rate'),('真实payload变化','actual_value_payload_changed_rate')])+'''
公开契约Recall与实际可用契约Recall分开列出，选中了NA不算保留已知事实。availability显示保留older_score/score_delta各191个快照缺失；Full可能固定释放多个NA，缺失释放比例单列。TrainMI在若干条件预测更好却契约Recall更低，这说明该人为契约不是因果“必要性”真值；真正必要信息评测仍BLOCKED于独立标注。不能以契约Recall宣称学习效用提高。

## 属性推断及安全解释

攻击者合法看到实际字段值、字段presence、NA状态及同一公开课程/阶段/日历，不看到被保护属性；两种属性gender_F/disability_Y各用固定LR与RF。BA=(TPR+TNR)/2，AUC用概率，表中宏平均分母4个属性/攻击器单元。保留性别86正/81负学生，残疾15正/152负学生；阶段快照中的类别分母另列。15名残疾阳性学生意味着估计不稳定，不能把重复快照当额外独立阳性。

public_context_attack另测**不释放私密字段**时仅公开背景的攻击能力：性别LR AUC=.7748、RF=.7750。公开背景已有强信号；发布更多特征的某个有限攻击器若反而得分较低，攻击者仍可忽略这些特征，因此不能据此声称安全改善。主表只是固定攻击器表现，未证明最强攻击者界、DP或互信息下降。no-projection实际视图相同则所有攻击结果相同，不能由内部向量非零声称隐私收益。

阶段复核没有更换攻击器或挑最高/最低结果；它重建相同训练视图并校验240个主攻击BA/AUC全部精确匹配，然后按阶段拆分。另按学生平均snapshot概率，属于简单聚合诊断，不是对联合历史训练的最优攻击器，不能证明多轮累计隐私安全。公开背景校准为事后诊断，不是K3公平竞争方法。

## 公平性、局限与失败

共同候选13、K3、敏感门.7、reply上限64及同tokenizer，输出记录逐条真实。实际平均Token随选择不同而不同，本轮并非强行等长度因果实验；Full与Safe匹配的5格及与简单成本规则的6格则内容与长度都精确一致。未填充文本。成本是研究者固定策略，未用属性标签反向优化。TrainMI、标准化、中位数仅训练数据拟合，开发未加入保留训练。

Original/TaskSlot为旧StrictSelector的同入口适配，旧坐标哈希与文本值float回退问题保留，不能把它们当最佳迁移模型或用其退化来夸大修复。强结论基于Safe/MI/普通规则和严格单项删除。所有有效运行无执行失败；负结果包括投影冗余、NA释放、契约与预测目标不一致、属性风险未下降。失败模式和本地逐例证据见failure_cases.md及failure_cases_LOCAL.json。

时间边界通过不等于绝对无泄漏：没有成绩公布时间，七天滞后仅代理；目标可用性/银行成绩排除有选择偏差，静态字段没有逐时版本。模糊任务、领域角色词表及契约为作者设计，未做独立教师盲标；三课程、单个后年presentation的小样本不能外推所有教育任务。本轮不再换测试、扩课或调参。

事后目标时序核查还发现，下一计划TMA已经提前提交的记录为训练9/1337、开发7/473、保留3/462。截止日在未来不等于结果一定未被观察；主任务应准确表述为“用受限历史视图估计下一计划TMA成绩”。主样本与拟合未改动，target_timing_audit另列排除已提交记录后的全部条件敏感性数值，不能拿此子集替换主结果或选择更好排名。

## 证明了什么；不能证明什么

支持：真实OULAD中Attention排序有可复核的外发/效用作用，跨年份保留重现；当前复杂完整流程可由简单相关度成本贪心完全替代，投影没有独立贡献。不能证明：不可替代的新算法、统计隐私解耦、真实教学干预收益、独立必要知识真值、严格实时可用性或广泛人群优势。

论文主证据资格：足以作为真实数据的组件审计、简化设计与负结果证据；不足以作为“正交投影+Attention带来独立安全—效用收益”的主证据。最终PIVOT针对复杂创新主张，并不否定透明排序作为工程基线的用途。

## 组会讲解词（约150字）

本轮在OULAD真实记录上先开发，再冻结后一年保留学生验证，始终保持三字段和共同攻击条件。关闭注意力会使部分任务预测变差，但完整方法多数与SafeTaskTopK相同。删除投影始终不改变外发内容，全部完整输出又能由简单相关度成本规则复现。因此建议保留透明排序与安全门，简化投影和冗余优化；结果支持工程取舍，不支持独立算法创新。
'''
write('mmfopd_oulad_report.md',body)
# Failure modes derived from actual rows; publish patterns/counts, keep exact records local.
evalrows=load('test_data/snapshots_LOCAL.json');rows_by={(x['student'],x['cutoff']):x for x in evalrows};cases=load('test_results/cases_LOCAL.json');patterns=[]
for intent in d.INTENTS:
 for wording in ['explicit','ambiguous']:
  zz=[x for x in cases if x['method']=='Repaired-Full' and x['intent']==intent and x['wording']==wording];miss=[x for x in zz if any(rows_by[x['student'],x['cutoff']]['values'][k] is None for k in x['selected_fields'])];wrong=[x for x in zz if x['schema_contract_recall']<1]
  patterns.append({'intent':intent,'wording':wording,'n':len(zz),'snapshots_releasing_NA':len(miss),'snapshots_contract_incomplete':len(wrong),'absolute_error_over40':sum(abs(x['prediction']-x['target'])>40 for x in zz)})
write('failure_cases.md','''# 真实失败与成功证据

以下模式来自已执行的全部保留样本，不用挑选个例代替整体分母。含真实学生ID、精确成绩、payload和逐样本对照的failure_cases_LOCAL.json只保留本地，不上传；该文件按每个冻结任务条件的Full误差最大3例选出，明确为解释性选择。

'''+table(patterns,[('任务','intent'),('表述','wording'),('分母快照','n'),('释放至少一个NA','snapshots_releasing_NA'),('契约未完整','snapshots_contract_incomplete'),('误差>40分','absolute_error_over40')])+'''
1. **阶段信息缺失未被感知。** 早期真实快照往往仅有一次已知TMA，older_score和score_delta为NA；trajectory显式任务仍固定发这两项，投影非零不会产生不存在的知识。这说明元数据相关不等于对个体动态可用性适配。
2. **模糊engagement选错契约时间窗。** Full实际字段active_days、clicks_earlier、inactive_days，遗漏契约clicks_recent。可用契约Recall=2/3；StageRoleRule给出近期窗口。预测效用是否更好由实际MAE判断，不能仅凭“近期”标签下结论。
3. **模糊readiness有收益但归因不成立。** Full发active_days/completion_rate/overdue_count，而Safe使用另一辅助行为字段；Full MAE更小，但no-projection及no-attention都保持Full，简单相关度成本规则也完全相同，因此不是投影或复杂Attention独立贡献。隐私BA/AUC也没有同时更好。
4. **真实正例：保留相关度优于常数权重。** engagement显式/模糊的Attention删除改变全部462条实际字段与预测，MAE约多3.76/3.67分，证明组件进入最终决策。Full仍与Safe完全相同，不能据此宣称新模块优于强基线。
5. **内部变化不能替代外发证据。** no-projection改变内部投影100%，六条件实际payload变化均0；所有阶段也没有额外隐私改善。完整数值在strict_ablation与stage_privacy。

公开案例只描述共享字段集合和足够聚合的失败计数，避免将删除姓名视为充分脱敏。无新造学生案例冒充OULAD实测。
''')
F=P/'figures';F.mkdir(exist_ok=True);plt.rcParams.update({'font.size':9,'figure.dpi':160})
keys=[(i,w) for i in d.INTENTS for w in ['explicit','ambiguous']];labels=[i[:1].upper()+('-exp' if w=='explicit' else '-amb') for i,w in keys];short={'Original':'Original*','TaskSlot':'TaskSlot*','SafeTaskTopK':'SafeTask','TrainMI':'TrainMI','Repaired-Full':'Full','Repaired-no-projection':'-projection','Repaired-no-attention':'-attention','Repaired-no-bottleneck':'-subset opt.','Repaired-no-taskslot':'-TaskSlot','StageRoleRule':'ContractRule'}
matrix=np.array([[lookup[i,w,m]['MAE'] for i,w in keys] for m in d.METHODS]);fig,ax=plt.subplots(figsize=(10,6));im=ax.imshow(matrix,cmap='Blues');ax.set_xticks(range(6),labels);ax.set_yticks(range(10),[short[m] for m in d.METHODS]);ax.set_xlabel('Frozen intent / phrasing (T=trajectory, E=engagement, R=readiness)');ax.set_ylabel('Selector (common K=3, sensitivity<=0.7, reply cap64 tokens)')
for j in range(10):
 for k in range(6):ax.text(k,j,f'{matrix[j,k]:.2f}',ha='center',va='center',color='white' if matrix[j,k]>27 else 'black')
fig.colorbar(im,ax=ax,label='Next TMA MAE, score points /100 (lower better)');ax.set_title('OULAD2014J: 462 snapshots /167 disjoint students; one frozen holdout');fig.tight_layout();fig.savefig(F/'01_holdout_MAE.png',bbox_inches='tight');plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(13,4.5));x=np.arange(6);width=.24
for j,(m,color) in enumerate([('Repaired-no-projection','#adb9c2'),('Repaired-no-attention','#247a9f'),('Repaired-no-bottleneck','#d49a53')]):
 deltas=[lookup[i,w,'Repaired-Full']['MAE']-lookup[i,w,m]['MAE'] for i,w in keys];rates=[next(z for z in paired if z['intent']==i and z['wording']==w and z['method']==m)['actual_payload_changed_rate'] for i,w in keys];axes[0].bar(x+(j-1)*width,deltas,width,label=short[m],color=color);axes[1].bar(x+(j-1)*width,rates,width,label=short[m],color=color)
for ax in axes:ax.set_xticks(x,labels);ax.set_xlabel('Frozen task context');ax.legend(fontsize=8)
axes[0].axhline(0,color='#555555',lw=.8);axes[0].set_ylabel('MAE Full minus removal (score points /100)');axes[0].set_title('Negative: Full has lower error');axes[1].set_ylabel('Fraction of462 actual payloads changed');axes[1].set_title('Internal nonzero projection does not imply contribution');fig.tight_layout();fig.savefig(F/'02_strict_ablation.png',bbox_inches='tight');plt.close(fig)
subs=load('test_results/subgroups.json');fig,axes=plt.subplots(2,3,figsize=(13,7))
for ax,(intent,wording) in zip(axes.flat,keys):
 for m,style,color in [('Repaired-Full','o-','#247a9f'),('SafeTaskTopK','x--','#d49a53'),('TrainMI','s:','#747e86'),('StageRoleRule','^-.','#499879')]:
  vals=[next(z['MAE'] for z in subs if z['intent']==intent and z['wording']==wording and z['method']==m and z['subgroup']=='cutoff' and z['value']==t) for t in d.CUTOFFS];ax.plot(d.CUTOFFS,vals,style,label=short[m],color=color,alpha=.85)
 ax.set_title(intent+' / '+wording);ax.set_xlabel('Days after module presentation start');ax.set_ylabel('Next TMA MAE (score points /100)');ax.set_xticks(d.CUTOFFS)
axes[0,0].legend(fontsize=8);fig.suptitle('Dynamic values, static Full field choices within each intent; cohort counts vary by stage');fig.tight_layout();fig.savefig(F/'03_dynamic_stage_utility.png',bbox_inches='tight');plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(14,4.6));marks=['o','s','^','D','x'];colors=['#247a9f','#d49a53','#747e86','#499879','#8b718a']
for ax,intent in zip(axes,d.INTENTS):
 for j,m in enumerate(['Repaired-Full','SafeTaskTopK','TrainMI','TaskSlot','StageRoleRule']):
  z=lookup[intent,'ambiguous',m]
  if j==4:ax.scatter(z['MAE'],z['AUC_macro'],label=short[m],marker='x',s=90,color=colors[j],linewidths=1.5)
  else:ax.scatter(z['MAE'],z['AUC_macro'],label=short[m],marker=marks[j],s=90,facecolors='none' if j==0 else colors[j],edgecolors=colors[j],linewidths=1.5)
 ax.set_xlabel('Next TMA MAE (score points /100, lower better)');ax.set_ylabel('Attribute attack AUC (2 attributes x2 attackers)');ax.set_title(intent+' / ambiguous');ax.set_ylim(.62,.71);ax.set_xlim(21,28)
 if intent in ['trajectory','engagement']:ax.text(.97,.03,'Full = Safe: same payload',transform=ax.transAxes,ha='right',fontsize=8)
axes[0].legend(fontsize=8);fig.suptitle('Fixed attacker performance, not a privacy bound; public context is available to all');fig.tight_layout();fig.savefig(F/'04_safety_utility.png',bbox_inches='tight');plt.close(fig)
# Main group-meeting artifact gathers all requested deliverables.
write('group_meeting_results.md','''# MM-FOPD：OULAD跨数据集验证组会材料

**最终决策：PIVOT（简化组件）；全部EXPLORATORY。** 完成小开发后按预定门槛冻结并执行一次后年保留验证，没有调参或重新挑测试。

- 训练484人/1337快照，开发166人/473快照，2014J保留167人/462快照；三组学生无交集。
- 10个选择器、3意图×2表述、3阶段、共同13候选、K3、敏感门.7、Token64；两期合计120个方法/任务单元、480个固定属性攻击单元。
- 删除投影、子集优化、Slot奖励均不改变保留输出。Attention有3格真实增益，但5/6格Full等同Safe，6/6格等同简单相关度成本规则。
- 无生产修改、无旧结果覆盖、无付费调用、无模型下载；44.6MiB作者公开数据已验证许可和校验和。

## 核心表：2014J保留组，MAE为0–100分制

'''+summary_table+'''
## 图表

![全方法真实MAE](figures/01_holdout_MAE.png)

![严格消融与实际输出变化](figures/02_strict_ablation.png)

![动态学习阶段](figures/03_dynamic_stage_utility.png)

![安全与效用](figures/04_safety_utility.png)

## 实验试图证明与实际支持

1. 跨数据集迁移：真实OULAD成绩与行为验证已执行，但人工任务设计不等于独立教师真值。
2. 组件必要性：Attention删除能改变最终信息和效用，投影/复杂优化/Slot奖励没有独立贡献。
3. 动态适应：真实值随阶段变化，Full字段集合仍固定；没有证明对个体状态动态选择。
4. 不能被简单规则替代：未成立，相关度减固定成本贪心复现全部Full。
5. 隐私收益：没有投影引起的外发差异，且公开课程信息本身可推断属性；不能宣称正交解耦保护。

当前可作为论文机制审计、真实数据负结果和简化设计证据；不能作为复杂算法独立安全—效用领先的主证据。建议保留透明相关度成本排序、共同硬门与真实Token会计，删除/可选化投影、子集优化、Slot奖励，不继续改测试追求领先。

## 必须随结果说明的限制

成绩公布时间缺失，七天lag仅代理；未按窗口提交定义0，目标banked/缺失有排除；真实必要信息未获独立标注，契约Recall仅代理；残疾阳性保留学生仅15；重复快照/多表述不是独立人数；固定攻击器BA/AUC不是隐私保证。完整分母、明细攻击和失败模式均在报告/CSV。

## 组会讲解词（约150字）

本轮在OULAD真实记录上先开发，再冻结后一年保留学生验证，始终保持三字段和共同攻击条件。关闭注意力会使部分任务预测变差，但完整方法多数与SafeTaskTopK相同。删除投影始终不改变外发内容，全部完整输出又能由简单相关度成本规则复现。因此建议保留透明排序与安全门，简化投影和冗余优化；结果支持工程取舍，不支持独立算法创新。

详见mmfopd_oulad_report.md、strict_ablation.md、failure_cases.md、data_availability_and_leakage.md、mechanism_and_code.md。全方法全指标comparison.csv、stage_utility.csv、stage_privacy.csv及真实聚合JSON可复核；逐学生值、预测、ID与payload仅本地*_LOCAL.json。
''')
write('README.md','''# OULAD dynamic MM-FOPD / 2026-10-19

入口：group_meeting_results.md。最终PIVOT，EXPLORATORY。仅独立实验副本，正式核心和302个历史证据文件未改。

实际运行顺序：acquire.py → freeze.py → build_data.py dev → run_experiment.py dev → gate_independent.py → build_data.py test → run_experiment.py test。其后执行冻结的check_simple_rule.py dev/test、stage_privacy.py、public_context_attack.py、validate_and_derive.py和build_reports.py。primary10方法的设计/代码在开发前冻结，后置规则/分阶段审查不改变主测试；public-only为事后背景校准。

Python进程启动前设置PYTHONHASHSEED=20261013。实验驱动拒绝覆盖冻结结果，复现应复制到experiments下新目录并重新建独立输出；依赖原项目、现有Qwen tokenizer及作者公开OULAD archive。先运行acquire有64MiB硬下载限额，无模型下载/付费调用。

不要将Repeated snapshot/context数量当学生数、不要把契约召回当因果必要性、不要把成绩lag代理称为严格实时无泄漏。原始数据和逐学生记录仅本地。证据清单/远端校验回执说明哪些文件被同步。
''')
# Explicit temporal and rule-equivalence appendices, preserving primary tables.
timing=load('target_timing_audit.json');write('data_availability_and_leakage.md',(P/'data_availability_and_leakage.md').read_text(encoding='utf8')+'\n## 事后目标时序敏感性核查（不更换主测试）\n\n'+table(timing['cohorts'],[('阶段','phase'),('快照数','n_snapshots'),('预测时已提交目标','next_scheduled_TMA_already_submitted_by_cutoff'),('比例','already_submitted_fraction')])+'\n未来截止日不保证目标尚未提交；成绩公布仍不可见。所有主样本和模型保持原样，全部条件的排除已提交目标敏感性MAE保存在target_timing_audit.json，仅作描述性检查，不替换主结果。\n')
subs=load('test_results/subgroups.json');stagecomp=[]
for stage in d.CUTOFFS:
 vals={m:next(x for x in subs if x['intent']=='readiness' and x['wording']=='ambiguous' and x['method']==m and x['subgroup']=='cutoff' and x['value']==stage) for m in ['Repaired-Full','SafeTaskTopK','StageRoleRule']};stagecomp.append({'stage':stage,'n':vals['Repaired-Full']['n_snapshots'],'Full':vals['Repaired-Full']['MAE'],'Safe':vals['SafeTaskTopK']['MAE'],'ContractRule':vals['StageRoleRule']['MAE'],'Full_minus_Safe':vals['Repaired-Full']['MAE']-vals['SafeTaskTopK']['MAE'],'Full_minus_contract':vals['Repaired-Full']['MAE']-vals['StageRoleRule']['MAE']})
write('dynamic_stage_analysis.md','# 动态阶段与模糊需求：避免均值掩盖机制\n\n模糊readiness的Full相对Safe总体MAE更小，但下表显示阶段效应；对契约规则的方向也随阶段而变。此表是固定全部样本的分层描述，不重新选择阶段或拟合模型。\n\n'+table(stagecomp,[('天数','stage'),('同阶段快照n','n'),('Full MAE','Full'),('Safe MAE','Safe'),('契约规则MAE','ContractRule'),('Full−Safe','Full_minus_Safe'),('Full−契约规则','Full_minus_contract')])+'\n所有Full字段集合在同意图/措辞下跨阶段不变。阶段误差变化来自真实数值、缺失、标签分布和同一训练模型，并不能归因于投影具备动态状态适应。相邻阶段完整字段/payload变化比例在dynamic_transitions.csv。\n\n属性推断的分阶段BA/AUC见stage_privacy.csv，模型先精确复现主攻击结果再拆分；各阶段正负分母均保留，不能将15名残疾阳性的重复快照当更多独立人。学生平均概率分析仅是简单汇聚，不涵盖最强历史组合攻击。\n')
import csv
rulemetrics=[]
for x in metrics:
 if x['method']=='Repaired-Full':rulemetrics.append({**x,'method':'RelevanceCostRule','metric_provenance':'exact same train/eval releases; reuse identical fixed-fit results, no additional model fitting'})
with (P/'rule_equivalent_metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(rulemetrics[0]));writer.writeheader();writer.writerows(rulemetrics)
print('Reports and4 figures built from completed results')
