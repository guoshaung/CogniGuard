"""Render result tables/figures from actual saved runs, never rerun experiments."""
from pathlib import Path
import json,csv,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).parent;sys.path.insert(0,str(P))
import aligned_selector as alg
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def write(n,s):(P/n).write_text(s,encoding='utf8')
def table(rows,cols):
 def val(v):return f'{v:.4f}' if isinstance(v,(float,np.floating)) else str(v)
 return '| '+' | '.join(k for k,_ in cols)+' |\n| '+' | '.join('---' for _ in cols)+' |\n'+'\n'.join('| '+' | '.join(val(r.get(v,'—')) for _,v in cols)+' |' for r in rows)+'\n'
def csvout(name,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with (P/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
mm=load('mm_v2/summary.json');new=load('new_families/summary.json');content=load('visibility_audit/aggregate_main.json');pairs=load('mm_v2/paired_mechanisms.json');lat=load('latency/summary.json')
fixed=load('corrected_baselines/summary.json');fixednew=load('corrected_baselines/new_summary.json');changes=load('corrected_baselines/changes.json')
mm=[next((z for z in fixed if z['dataset']==x['dataset'] and z['method']==x['method']),x) for x in mm];new=[next((z for z in fixednew if z['method']==x['method']),x) for x in new]
for x in pairs:
 z=next((z for z in changes if z['dataset']==x['dataset'] and z['method']==x['method']),None)
 if z:x['final_fields_changed_vs_repaired']=z['fields_changed_vs_repaired'];x['prediction_changed_vs_repaired']=z['predictions_changed_vs_repaired']
csvout('mm_comparison.csv',mm);csvout('mm_new_families.csv',new);csvout('mm_ablation.csv',pairs);csvout('mm_attribute_attacks.csv',[x for x in load('mm_v2/attacks.json') if x['method'] not in ['Original-commonpool','TaskSlot-commonpool']]+[x for x in load('corrected_baselines/attacks.json') if x['dataset']!='new_synthetic_families']);csvout('synthetic_attribute_attacks.csv',[x for x in load('new_families/attacks.json') if x['method'] not in ['Original-commonpool','TaskSlot-commonpool']]+[x for x in load('corrected_baselines/attacks.json') if x['dataset']=='new_synthetic_families']);csvout('content_comparison.csv',content);csvout('latency.csv',lat)
roles=[]
meaning=['早期测验观测','近期测验观测','练习投入','缺勤/出勤','学习困难/错误频率','学校辅导','家庭学习支持','额外付费或提示辅助（粗粒度）','活动/兴趣情境','学习意愿及早期教育背景（粗粒度）','上网/设备/通勤可达性','概念误解','呈现格式偏好','其他一般背景']
for i,(r,aliases) in enumerate(alg.ROLE_ALIASES.items()):roles.append({'coordinate':i,'role':r,'meaning':meaning[i],'public_aliases':', '.join(aliases)})
write('encoding_dimensions.md','# 画像与任务共享编码：14维固定公共角色\n\n字段 z(r)=对应角色单位向量；任务 m(t)=问题显式提及该角色别名的0/1向量。按字段ID映射，不使用字段值、测试G3或属性标签。画像顺序变化不会改变坐标意义。\n\n'+table(roles,[('坐标','coordinate'),('角色','role'),('含义','meaning'),('字段/任务别名','public_aliases')])+ '\n这是一套人工公共词表，未经独立标注或语义编码器验证。paid_support将付费支持与提示合并、learning_intent将nursery与higher合并，属于粗粒度角色近似，不能声称严格概念同一；更细语义应独立标注后另冻结验证。本轮不在见过测试结果后修改词表。词表未使用标签学习，也不声称具备自由文本语义泛化。\n')
sources='''# 内容历史风险与已有工作的对应（2026-10-19核验）

本轮是开发诊断，不将联合信息风险、共享集合或规则推理称为新颖。仅核对一手论文/项目，没有复现外部系统，也不据此给出最新领域穷尽性结论。

1. 历史查询审计已经考察查询与既往答复组合是否泄露，且拒绝本身也可能泄露；因此维护历史并不足以给出端到端安全证明。[Simulatable Auditing](https://cs.stanford.edu/people/kngk/papers/SimulatableAuditing.pdf)。本原型没有实现可模拟拒绝审计。
2. CQE用知识推理后的可披露性作为控制对象，而非只限制字面量或加性Token。[Controlled Query Evaluation through Epistemic Dependencies](https://arxiv.org/abs/2405.02458)。其形式化策略比本原型3种固定函数族更一般。
3. 已有可执行的内容依赖披露实现：2025年CQE工作给出认识依赖策略下的查询重写及SQL实验，论文第7节提供Java源码压缩包，依赖Java8+/MySQL/Python3，可选Maven。[论文及实现说明](https://arxiv.org/html/2507.17487v1)，[作者论文链接的代码](https://github.com/anonymous-iswc25/iga-ed-rewriter/blob/main/iga-ed-rewriter.zip)。本轮没有下载或运行，不能称复现比较。
4. 信息流控制已有实际编译器及运行时。Jif按主体、数据标签和解密授权追踪信息流；这不同于自动发现自然语言关系，但说明联合披露与接收者权限并非空白问题。[Cornell Jif官方实现](https://www.cs.cornell.edu/jif/)。
5. RAG攻击已有反馈引导迭代抽取，以及用正常问题实施隐式知识抽取的工作；只检验原文复现会遗漏这一攻击面。[Feedback-Guided Extraction](https://arxiv.org/abs/2411.14110)，[Silent Leaks](https://arxiv.org/abs/2505.15420)。本轮使用可执行有限假设攻击者，未将它与这些LLM攻击器做能力排名。

本轮收益完全被普通共享集合规则基线复现，最接近已有的内容依赖披露控制。Delta风险可作为统一接口描述，不能据变量换名宣称新算法。可能值得后续研究的是未知先验下的保守估计、跨资产语义闭包、风险校准和拒绝侧信道；本轮没有证明或实现这些扩展。
'''
write('related_work.md',sources)
mmcols=[('方法','method'),('MAE↓','MAE'),('BA宏平均','BA_macro'),('AUC宏平均','AUC_macro'),('字段数','fields_mean'),('真实Token','tokens_mean')]
newcols=[('方法','method'),('算术MAE↓','MAE_arithmetic'),('必要信息F1↑','necessary_F1'),('BA宏平均','BA_macro'),('AUC宏平均','AUC_macro'),('Token','tokens_mean')]
ablcols=[('科目','dataset'),('方法','method'),('投影非零率','projection_nonzero_rate'),('Top3排序变化','top3_rank_changed_vs_repaired'),('字段变化','final_fields_changed_vs_repaired'),('预测变化','prediction_changed_vs_repaired')]
text='''# MM-FOPD 表示对齐修复与严格消融

**决策：PIVOT。** 修复接线与尺度问题有效，复杂算法增益未成立。保留负结果；以SafeTaskTopK和硬安全/Token门为简化方向，投影、子集优化和TaskSlot奖励降级为可选或删除，Attention仅作为普通相关度排序，不包装为独立创新。不能用本轮作为论文主方法领先的证据。

## 已执行、冻结顺序与边界

读取原ProfileSelector、OrthogonalDecoder、TaskAttention、旧StrictSelector及最新因果审计；原文件保存在frozen_original，源哈希和两批旧证据哈希在preservation.json。仅新增本实验目录。protocol.json在开发选择前冻结；9组开发参数均为相同平均MAE 1.004933，按预定次序选alpha=.25、温度=.25，selected_config_lock在旧测试复核和新任务族生成前落盘。没有根据新结果重新调参。

第一次开发执行被精确Token断言拦截：两个科目复用了画像ID，Token缓存错误串用。原脚本及mm/failure.json保留，v2缓存键纳入知识域和字段值，失败时未评估测试。随后完成18个旧科目/方法单元、144个属性攻击单元；新任务400个虚构画像，200训练、40开发、160评估，4个未用于开发的任务组合，36个属性攻击单元。0付费调用、0新增LLM调用、0下载。后置公平入口核验另冻结fairpool/protocol.json，不改变超参数或重新挑测试。

UCI Math 226/86/83，Portuguese 389/129/131，沿用旧划分且多次查看，仅作开发/复核。两科存在同人重叠，不能把214当214个独立人。新任务是作者设计的合成新身份/新组合，非独立教师双人盲标或真实学校外部确认；不称blind test。指标是实际确定性/Ridge运算，未运行新的LLM教学回答。

## 机制与数学定义

14维画像角色单位向量z与任务显式语义掩码m共用坐标，详见encoding_dimensions.md。P=diag(m)，P'=P且P²=P，Pz与(I-P)z内积为0。validation检查全部16384种掩码。它是**正交坐标投影**，贡献的是任务角色保留；不是学得的敏感子空间解耦、独立性或互信息消除。粗粒度人工别名存在语义近似，不是语义表征模型的验证成果。

Attention以公共字段ID/type/knowledge/角色别名的TF-IDF余弦c排序，w=softmax(c/T)，u=w/max(w)。原w约.04小于cost约.125的问题通过有界相对权重修正。得分s=alpha*||Pz||+(1-alpha)*u-.25*sensitivity+slot_bonus；Slot仅在显式提及mastery字段时最多+.08，不预留或补齐字段。子集选择在共同硬约束下最大化sum(s)-.15*同角色字段对数，先取最大可行字段数；准确名称为预算子集优化，**不称信息论bottleneck**。

删除投影仅去alpha*||Pz||项；删除Attention以共同常数代替u；删除子集优化用同约束贪心；删除Slot仅去+.08。所有消融保留相同候选入口、敏感阈值、K和Token上限，不修改总预算。这些单项删除比较的是修复后机制，不是旧开关的混杂行为。

## 强基线公平性

全部K=3、敏感门限<=.7、canonical排序field=value换行序列使用现有Qwen真实tokenizer，cap32，无填充。最终释放实际字段值；投影向量仅内部使用。UCI共同安全候选20项，合成12项。逐字段记录均已校验，真实UCI记录仅本地*_LOCAL.json保存，不同步。所有方法实际都释放3字段；长度并非强行相等，Token均值列出，不把差异视为纯长度因果实验。Full与Safe逐条内容相同，因而这对严格等长且等信息。

Original-commonpool与TaskSlot-commonpool为原严格逻辑+共同硬约束的适配比较，非未改动历史原生算法：将attention覆盖扩到全部共同候选、允许类型统一、最后K/Token裁剪；两者仅是否要求distinct mastery slots不同。v2旧版Attention入口仍读全画像，后置检查将入口改为同一安全画像。第一次检查未固定旧哈希种子，标记INVALID并保留；fairpool_v2固定20261013后复核。为保证入口与哈希均一致，corrected_baselines重新执行这两个基线的4个UCI单元、2个合成单元及40个攻击单元，不重新调修复算法。本报告主表用纠正结果，v2旧基线结果保留不混用。该适配限制必须随表一起报告，原生旧6对3字段结果仅作混杂证据。

SafeTaskTopK使用同一公共词表与TF-IDF原始余弦贪心，无投影/优化/Slot奖励；不给本方法独占语义信息。UCI TrainMI仅训练G3计算MI；合成TrainMI按公开任务算式在训练行计算任务条件MI，未给测试答案。MI作为通用关联筛选本来可能不如显式算式，因此不能仅凭合成数据胜MI声称优越。

## 实际对比

### 历史Math，83条复核

'''+table([x for x in mm if x['dataset']=='Math'],mmcols)+ '\n### 历史Portuguese，131条复核\n\n'+table([x for x in mm if x['dataset']=='Portuguese'],mmcols)+ '\n### 新合成任务族，160条 / 4个任务组合\n\n'+table(new,newcols)+'''
Full与Safe在两科全部1044条以及新任务160条评估记录的外发字段逐条相同，MAE与攻击BA/AUC相同。因此没有实际对外信息差异支持“投影降低隐私”。必要信息是公开算式的3个必需操作数，Precision=交集/已释放数，Recall=交集/3，F1按每例计算后平均。合成Full/Safe均480/480个操作数保留、MAE0，所有4项删除也相同；这是任务易于由显式字段名解决的结果，不是独立算法贡献。真实UCI没有必要信息真值，保持NA。

## 严格配对消融

表中变化均相对修复Full；Top3按得分排序，不等于最终受约束集合。投影非零分母为对应样本数。

'''+table([x for x in pairs if x['method'].startswith('Repaired')],ablcols)+'''
旧版是执行214/214但投影零214/214；本轮Full非零214/214，新任务160/160。删除投影最终字段仍0/214变化，新任务0/160：**接线修好了，效用增益没证明**。删除Attention旧UCI字段与预测214/214变化；Math MAE降低.007551，Portuguese升高.007474，不能宣称一致提升；相应Token也变化。它有真实选择作用，尚无超越Safe的贡献。删除子集优化和Slot奖励字段、预测均0/214变化，新任务0/160，属于本批冗余，不再归因于Slot无条件覆盖。

旧Attention排序89%～94%变化而最终不变，是后续压缩空集/Slot接管；当前20个安全候选net>0，Slot前后排序0变化，已不再强制覆盖。完整逐样本内表和旧审计保留，用均值不能代替字段/预测配对。

## 隐私、延迟、失败与解释范围

MAE=mean(|预测G3-真实G3|)，Ridge仅train拟合、dev选正则；UCI攻击每方法4目标(health/romantic/Pstatus/Dalc)×LR/RF，BA=(TPR+TNR)/2，AUC基于概率。宏平均分母8个目标/攻击器单元；合成2目标×2攻击器，分母4。类分母见attacks.json，目标值及其presence不作为攻击输入。BA越低通常代表更难推断，但.5以下也不证明隐私；没有DP或攻击能力完备证明。所有方法直接私密字段暴露0，代理属性仍可推断，不能以0直接暴露称全面隐私安全。部分目标类不平衡，报告AUC及BA，不用Accuracy包装。

全量主运行中修复算法使用合法结果缓存，不能将其0.1ms与未缓存Safe比较。另在两科各前20个开发样本、每方法40次测量：公共Token成本表预计算，清空选择结果缓存，包含实际选择计算，不含模型拟合/Token表构建；单机顺序测量，不是端到端生产延迟。下面才是可解释的测量。

'''+table(lat,[('方法','method'),('调用数','n_calls'),('均值ms','mean_ms'),('p95 ms','p95_ms')])+'''
Full约为Safe 4.17倍，优化耗时并无已证收益。no-attention仍计算attention_values再忽略其结果，属于效果消融；不能将该耗时解释为移除Attention算子的成本节省。cold脚本旧适配入口见其protocol，后续入口审查是输出等价核验，不用它重算吞吐结论。

保留的失败：首次开发缓存冲突；入口检查首次未固定旧哈希种子，保留且标无效，之后固定种子复核并重算基线；后续有效27个方法/数据单元无失败。不存在靠挑选样本证明组件有效的追加测试。Math Full-Safe差值0，Full-TrainMI差+.007551，旧同人分组条件bootstrap95%[-.040997,.052742]；仅已看过队列、固定模型的描述区间，不能据此做独立显著性结论。

## 代码路径与可复核证据

code_paths.json给出真实函数起始行及源哈希。旧路径ProfileSelector.select_enhanced→OrthogonalDecoder.decompose/project_to_task→TaskAttention.compute_attention→压缩→TaskSlot，旧源码和StrictSelector均保留。修复路径run_mm_v2.select共同门→aligned_selector.embedding/task_mask→attention_values→choose预算优化；fairpool.fair给旧方法相同入口。没有改生产源文件。真实学生个案只本地保留，公开证据发布聚合字段频数与自编合成个案，见case_evidence.md。

支持：工程性修复使表示对齐、候选不再因尺度而空、Attention可改变实际选择。不能证明：投影解耦隐私、各组件必要、比强基线好、真实教学质量提升、独立人群外推。**论文主证据：不足；方法审计与负结果可用。**

## 组会讲解词（约150字）

我们先修复画像和任务坐标错位，并统一注意力与隐私成本尺度，再固定三字段预算做真实配对。投影由全部为零变为全部非零，但删除投影后外发字段仍完全相同。注意力能改变旧数据的选择，效果却不一致。新任务族上完整方法与SafeTaskTopK持平，其他组件没有额外收益，完整方法还更慢。因此建议简化模型，保留负结果，不把内部向量变化当作隐私改善。
'''
write('mmfopd_repair_results.md',text)
ctcols=[('方法','method'),('完整恢复n/3','complete_recovery_n'),('恢复率↓','complete_recovery_rate'),('事实效用宏平均↑','fact_utility_macro'),('事实数/7','facts_delivered'),('真实Token均值','actual_tokens_mean'),('空拒绝','refusals'),('教学替代','fallbacks')]
write('c2rag_content_risk_results.md','''# C²-RAG 内容条件化重构风险诊断

**决策：ANALYZE。** 已执行最小开发原型和反例，证明固定预算加性账本不等于内容组合控制；收益被普通共享集合规则完全解释。停在有限语义开发诊断，不扩独立测试、不称创新、不把它直接部署成安全保证。

## 风险定义与可证伪对象

K_seen是接收者/联盟合法已见知识，加上明确公开的背景先验；K_new是当前候选的类型化约束。F_protected是公共策略指定的完整函数关系族；隐藏实际参数不传给检测器。所有基线获得相同政策、参数域、候选、query、Token总限额、单位机会额度和背景先验；只有维护历史的方式不同。

一般目标可写Delta R(K_new|K_seen)=R(K_seen∪K_new;F)-R(K_seen;F)。本原型定义H(K)={满足公开参数域及K中约束的函数}，R(K)=1当且仅当H中所有函数在公开有限输入域x=-3..11上行为一致，否则0；矛盾/域外返回UNKNOWN并保守risk1。估计是确定性有限先验可识别性，不是概率、互信息或通用语义蕴含。3族各自被保护，不用多关系相加掩盖定义。

参数先验：仿射a,b∈[-10,10]；幂关系r∈[1,10],p∈{1,2,3}；分支阈值t∈[-2,8]，偏移c∈[-5,8]，倍率m∈{1,2,3,4}。这个先验必须计入攻击者已知知识；范围来自开发策略，不能泛化为真实攻击者知识。放宽假设域可能改变风险判断。

### 既有实现定位

历史查询审计、CQE认识依赖及Jif信息流系统已有历史/内容/知识披露控制；CQE有公开查询重写实现。RAG反馈抽取和隐式知识抽取也已存在。核验来源与区别见related_work.md，未复现外部系统。联合风险和Delta记号本身不构成新颖，本轮共享集合规则等效更直接反驳了新算法主张。

## 实际执行与公平预算

只复用已看过的3个自编开发资产，数学、物理和程序分支各1个。资产、目标、评分规范原已冻结，本轮content/protocol.json再先冻结7个基线和先验。实际运行3资产×2身份计划×2先验×7方法=84方法单元；**独立资产分母仍3，不是84**。没有新测试、LLM调用或收费。候选是原自编资产中逐句抽取的真实回复，不冒充模型生成；最终攻击器只读自己的问题、实际交付回复及公共先验，不读资源正文/隐藏答案。表达式生成后才调用关系评分器。

TokenCounter仅累计实际Token；StaticQuota增加静态身份配额；SharedAdditive累计各交付单位成本；Conditional-no-history只对本片段及初始先验判断；Conditional-Independent维护各身份内容历史；Conditional-Shared维护联盟内容并集；SharedSet-RuleClosure用相同公共规则检查必要参数槽是否齐全。全方法联盟Token<=72，每活动身份<=72/N身份数， factual机会N=2或3，每次实际交付加性成本1/N，总<=1；本批7方法都遵守这组硬限额，不给独立身份3B。TokenCounter也有共同的硬限额，名字仅描述它不额外读取内容历史。

逐条候选顺序相同；完成关系的片段被替换为源资产中的有意义教学提醒，实际计Token与成本，非无意义填充，空拒绝单列。替代内容损失该次精确事实问答效用。数值/事实+原始query联合可见，公开关系族、先验同样可见，未给新方法独占真值。纯正则只承担冻结类型语法抽取，完整恢复由可执行函数验证，非“几个数同时出现即违规”。

## 主比较：空先验、跨身份互补

'''+table(content,ctcols)+'''
主表采用实际可见回复的后置开发语义审查，**共享内容方法完整关系恢复1/3**，对照及独立内容历史为3/3。原受限语法攻击器报0/3是过于乐观的假阴性，已保留并降级为语法内结果，不作为安全结论：物理提醒“Squaring the current...”向攻击者泄露p=2，联合此前合法可见r=4仍能恢复4x²。visibility_audit先冻结公共语义规则再重算全部84单元，没有更换任何防御输出，5个方法/计划/先验单元发现原漏检。

回复平均19.667 Token，高于基线15.667，不能归因于少发Token；但精确事实效用从7/7降为4/7（微平均57.14%，资产宏平均55.56%），所以也**不能宣称正常教学效用无损**。这不是实际长度完全匹配的因果比较，只支持同一硬预算下在部分已建模组合上改变内容可降低恢复，不是同效用下更强。普通规则方法逐条回复完全相同，12/12资产/先验/计划组合无差异。

新鲜空上下文的7个单事实请求，所有方法均允许7/7；它只说明单片段可用，不能替代多轮正常教学质量。先验挑战中，物理公式p=2已经公开，单个r片段就可能完成关系；content/traces记录此时风险/替代。拒绝、替代文本、触发时间本身是可见信息，本原型攻击器未推理这些侧信道，不具备可模拟审计安全证明。

## 可执行个案、指标分母与局限

仿射：只见倍率3时仍有21个偏移候选，只见偏移7时仍有21个倍率；联盟收集二者恢复3x+7。物理：r=4与p=2各自不唯一，合并恢复4x²。分支：阈值4、低支x+5、高支2x逐片均不唯一，合并恢复分段函数，15个有限域检查同时验证前提/结论绑定，覆盖阈值两侧。全部7个单片段风险0，3个联合风险1，关系评分3/3通过；含两个分支的程序个案不是“三个数同现”检测。详见case_evidence.md与single_joint_synergy。

完整恢复率=成功恢复关系的资产数/3；成功需表达式可解析并在15个输入全部行为一致。行为准确率=通过检查数/15；程序前提区间数2。有限验证**不证明无限整数或实数上的数学等价**。事实效用是按请求交付原正确片段的比例，非事实文字覆盖、数值绑定分数或模型教学评分，不能混用。必要事实共7个，交付4个。Token只数实际reply，query对所有方法相同且保留可见日志；加性成本为7个实际交付机会的归一化账目，各资产总1。

**显式失败范围：** parser只接受冻结的肯定句语法，不理解自由改写、否定、单位转换或一般指代；未识别文本返回空约束，直接接自由文本会漏检。validation保存一个真实不可解析改写反例；更严重的是实际教学提醒虽没有数值，仍能携带指数知识，已由真实攻击恢复。通用自然语言前端必须判UNKNOWN并对替代输出重新评估，本轮没有部署，也没有更换提醒再刷出0。保护的是有限行为函数，不是版权法律判定。真实先验、跨资产组合、主动自适应攻击、推断拒绝侧信道、先前不可撤销泄露未被解决。

## 能证明什么、不能证明什么

支持：已建模联盟内容组合能够越过简单加性限额；内容历史能识别完成关系的关键一步；用可执行攻击减少小模型能力不足造成的假阴性。不能证明：全语义泛化、真实RAG模型质量、规模化性能、隐私保证、独立测试优势或算法创新。普通SharedSet规则已完全解释收益，不能把Delta估计器当论文最终新方法主证据。保留开发反例和局限，停止扩量刷优势。

## 作为未来CGC风险输入（仅接口讨论，未实现CGC）

输入可包含资产/主体/联盟标识、公共策略版本、可见先验版本、已交付知识的指纹和候选内容；输出R_seen、R_after、Delta R、UNKNOWN/置信区间、可核验的关系完成证据及实际Token/效用代价。知识历史仅在实际交付后提交，不能按候选即入账；跨身份并集应以明确联盟威胁模型定义，不能任意身份合并。CGC若未来使用此值，需把单位、背景假设、未知状态和正常任务代价显式纳入决策，不能把1/0语义风险与差分隐私epsilon或版权法律风险直接相加。本轮仅输出协议建议，无CGC新算法。

## 组会讲解词（约150字）

我们用三个自编关系资产验证了组合风险：单片段不能唯一恢复，联盟合并后却全部恢复。共享内容控制使恢复从三例降为一例，但事实效用下降，普通集合规则也完全等效。逐句审查还发现教学提醒泄露了指数，纠正了原解析器的零恢复假象。因此目前只支持有限开发诊断，不支持新算法或语义安全保证；负结果保留，不修改输出追求零泄露。
''')
# Publish authored-only cases and anonymized aggregate fieldsets for original students.
cases=['# 逐案例证据（仅自编原始值公开）\n','真实UCI逐学生预测/字段/Token/内部向量仅在本地*_LOCAL.json；不向research-sync上传。公开如下字段集合聚合和自编案例，避免用删除身份ID冒充充分脱敏。\n']
fieldsets=[]
for subject in ['Math','Portuguese']:
 for m in ['Repaired-Full','SafeTaskTopK','Repaired-no-attention']:
  d=load(f'mm_v2/{subject}_{m}_LOCAL.json');freq={}
  for i in d['test_indices']:
   k=','.join(d['selection_all'][i]);freq[k]=freq.get(k,0)+1
  for k,n in freq.items():fieldsets.append({'dataset':subject,'method':m,'fieldset':k,'count':n})
cases.append(table(fieldsets,[('科目','dataset'),('方法','method'),('实际字段','fieldset'),('例数','count')]))
rows=[x for x in load('new_families/rows.json') if x['method'] not in ['Original-commonpool','TaskSlot-commonpool']]+load('corrected_baselines/new_rows.json');records=load('new_families/authored_data.json');byid={x['id']:x for x in records}
examples=[]
for fam in [6,7,8,9]:
 z=[x for x in rows if x['split']=='test' and x['family']==fam and x['method']=='Original-commonpool'];bad=max(z,key=lambda x:abs(x['prediction']-x['target']));ident=bad['id'];item=byid[ident];cases.append(f"\n## 自编 {ident}\n\n公开任务："+' + '.join(f'{c}*{k}' for k,c in zip(item['necessary'],item['coefficients']))+f"。必要字段={item['necessary']}；真值={item['target']}。同一家族选旧方法误差最大例，仅用于展示失败，不代替整体分母。\n\n")
 zz=[{**x,'error':abs(x['prediction']-x['target'])} for x in rows if x['id']==ident and x['method'] in ['Original-commonpool','TaskSlot-commonpool','SafeTaskTopK','TrainMI','Repaired-Full']];examples.extend(zz);cases.append(table(zz,[('方法','method'),('实际字段','selected_fields'),('预测','prediction'),('绝对误差','error'),('Token','tokens')]))
for x in load('visibility_audit/results.json'):
 if x['prior']=='empty_prior' and x['plan']=='identity_split' and x['method'] in ['SharedAdditive','Conditional-Shared']:
  cases.append(f"\n## {x['asset']} / {x['method']}\n\n攻击表达式：{x['attacker_expression']}；完整成功：{x['complete_relation_recovery']}；实际Token={x['actual_tokens']}。\n\n"+table(x['coalition_visible'],[('身份','agent'),('合法可见query','query'),('实际reply','reply')]))
write('case_evidence.md','\n'.join(cases));csvout('mm_fieldset_counts.csv',fieldsets)
# Actual source function paths, not switch labels.
import ast,hashlib
paths=[]
for rel in ['aligned_selector.py','content_risk.py','run_mm_v2.py','run_new_families.py','run_content.py','fairpool_check_v2.py','run_corrected_baselines.py','attacker_visibility_audit.py','frozen_original/profile_selector.py','frozen_original/orthogonal_decoder.py','frozen_original/task_attention.py']:
 p=P/rel;tree=ast.parse(p.read_text(encoding='utf8'));paths.append({'path':rel,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'functions':[{'name':n.name,'line':n.lineno,'end_line':n.end_lineno} for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef))]})
write('code_paths.json',json.dumps(paths,ensure_ascii=False,indent=2))
F=P/'figures';F.mkdir(exist_ok=True);plt.rcParams.update({'font.size':10,'figure.dpi':150})
short={'Original-commonpool':'Original*','TaskSlot-commonpool':'TaskSlot*','SafeTaskTopK':'SafeTask','TrainMI':'TrainMI','Repaired-Full':'Full','Repaired-no-projection':'-projection','Repaired-no-attention':'-attention','Repaired-no-bottleneck':'-subset opt.','Repaired-no-taskslot':'-TaskSlot'}
fig,ax=plt.subplots(1,3,figsize=(15,4.5));names=[short[x['method']] for x in new]
for a,subject in zip(ax[:2],['Math','Portuguese']):
 z=[x for x in mm if x['dataset']==subject];a.barh(names,[x['MAE'] for x in z],color=['#9099a2']*4+['#237bab']+['#aacbdc']*4);a.invert_yaxis();a.set_xlabel('Actual grade MAE (lower is better)');a.set_title(subject+' / historical recheck, n='+str(z[0]['test_n']))
ax[2].barh(names,[x['necessary_F1'] for x in new],color=['#9099a2']*4+['#237bab']+['#aacbdc']*4);ax[2].invert_yaxis();ax[2].set_xlabel('Necessary operand F1');ax[2].set_title('Authored heldout combinations, n=160');ax[2].set_xlim(0,1.05)
fig.suptitle('Repair is functional; Full does not beat metadata-aware SafeTask');fig.tight_layout();fig.savefig(F/'mm_comparison.png',bbox_inches='tight');plt.close(fig)
fig,ax=plt.subplots(1,2,figsize=(12,4.5));abl=[x for x in pairs if x['dataset']=='Math' and x['method'].startswith('Repaired')];x=np.arange(len(abl));w=.25
for j,(key,label,color) in enumerate([('projection_nonzero_rate','Nonzero projection','#9ab3c4'),('top3_rank_changed_vs_repaired','Top3 changed','#f4b261'),('final_fields_changed_vs_repaired','Final fields changed','#267fa4')]):ax[0].bar(x+(j-1)*w,[z[key] for z in abl],w,label=label,color=color)
ax[0].set_xticks(x,[short[z['method']] for z in abl],rotation=20);ax[0].set_ylabel('Fraction of historical Math rows, n=83');ax[0].legend(fontsize=8);ax[0].set_title('Internal representation is not released information')
ax[1].barh([short[z['method']] for z in lat],[z['mean_ms'] for z in lat],color='#267fa4');ax[1].invert_yaxis();ax[1].set_xlabel('Mean selection milliseconds (40 dev calls / method)');ax[1].set_title('Selection cache cleared; token tables excluded');fig.tight_layout();fig.savefig(F/'mm_mechanism_latency.png',bbox_inches='tight');plt.close(fig)
fig,ax=plt.subplots(1,2,figsize=(13,4.5));colors=['#a5acb3']*5+['#ecb255','#267fa4'];labels=[x['method'].replace('Conditional-','C-').replace('SharedSet-RuleClosure','SharedSet-rule') for x in content]
for i,z in enumerate(content):ax[0].scatter(z['fact_utility_macro'],z['complete_recovery_rate'],s=90+30*i,facecolors='none' if i==6 else colors[i],edgecolors=colors[i],linewidths=2,label=labels[i])
ax[0].set_xlabel('Exact local-fact utility (asset macro mean)');ax[0].set_ylabel('Complete relation recovery (3 assets)');ax[0].set_xlim(.45,1.08);ax[0].set_ylim(-.1,1.1);ax[0].legend(loc='center left',fontsize=8);ax[0].set_title('Shared-content = ordinary shared-rule control')
x=np.arange(len(content));ax[1].bar(x,[z['actual_tokens_mean'] for z in content],color=colors);ax[1].set_xticks(x,labels,rotation=35,ha='right');ax[1].set_ylabel('Actually delivered reply tokens, mean');ax[1].set_title('Same cap72; protected outputs are longer');fig.suptitle('Development only: empty prior, split identities; utility loss disclosed');fig.tight_layout();fig.savefig(F/'c2_safety_utility_tokens.png',bbox_inches='tight');plt.close(fig)
fig,ax=plt.subplots(figsize=(9,4.2))
for family,seq in [('affine',[0,0,1]),('power',[0,0,1]),('branch',[0,0,0,1])]:ax.plot(range(len(seq)),seq,marker='o',label=family,alpha=.75)
ax.set_xticks([0,1,2,3]);ax.set_xlabel('Number of complementary facts in coalition view');ax.set_ylabel('Identifiable function in finite hypothesis class');ax.legend();ax.set_title('Each individual fact: R=0; completing coalition: Delta R=1');fig.tight_layout();fig.savefig(F/'c2_conditional_risk.png',bbox_inches='tight');plt.close(fig)
write('ablation_review.md','# 机制归因结论\n\n'+table([x for x in pairs if x['method'].startswith('Repaired')],ablcols)+'\nMM：修复投影非零，但删除投影未变最终选择；Attention改变旧数据外发内容，方向不一致；新任务所有删除与Full持平。Full与Safe对外内容相同，属性攻击结果相同，无独立隐私提升。旧版与TaskSlot是共同门适配的冻结逻辑，不是原生代码不变对比。\n\nC²：同额度的普通共享集合/规则与条件风险逐条等同。新增内容历史控制改变可见事实并牺牲序列效用，非加性累计额度的贡献。已有工作已实现知识依赖披露，因此不宣称新算法。\n')
write('group_meeting_results.md','''# 2026-10-20组会：实际修复与可证伪风险诊断

**MM-FOPD：PIVOT。C²-RAG：ANALYZE。全部EXPLORATORY。**

MM完成9方法×两科214条历史复核、9方法×160条新合成任务组合、180个属性攻击单元、360次开发延迟检查；C²完成3自编开发资产×7方法×2先验×2身份计划。没有新模型推理调用或付费API。首次Token缓存错误保留，修正后有效实验完成，生产源码与旧证据哈希未变。详细报告含机制、数学、分母、公平审查、局限和两段约150字讲解词。

## 组会核心表

'''+table([x for x in mm if x['method'] in ['TaskSlot-commonpool','SafeTaskTopK','TrainMI','Repaired-Full']],[('数据','dataset'),*mmcols])+ '\n'+table([x for x in new if x['method'] in ['TaskSlot-commonpool','SafeTaskTopK','TrainMI','Repaired-Full']],newcols)+'\n'+table(content,ctcols)+'''
## 图与解读

![MM真实对比](figures/mm_comparison.png)

![MM内部变化与外发变化/延迟](figures/mm_mechanism_latency.png)

![内容组合安全-效用及实际长度](figures/c2_safety_utility_tokens.png)

![逐步条件风险](figures/c2_conditional_risk.png)

第一张说明修复后仍与强基线持平；第二张说明投影非零不等于有效，完整方法选择成本更高；第三张说明共享内容控制有损效用且完全被规则基线解释，并非少发Token；第四张是有限先验可执行关系的组合反例，不是通用语义安全证明。

## 每项实验试图证明什么，实际支持什么

1. 表示/尺度修复：试图恢复有效组件输入。实际证明投影可执行且非零、候选成本尺度合理；未证明私密空间解耦。
2. 严格消融：试图区分组件贡献。Attention确实改变旧数据外发字段，投影/优化/Slot未增加已测收益；均未超过Safe。
3. 新任务组合：试图检验跨组合能力。Full、Safe与全部删除均F1=1；作者设计任务较直接，不能证明真实教学迁移或创新。
4. 属性攻击：试图验证外发信息泄露。Full与Safe内容及BA/AUC相同；不能从内部投影声称隐私提升。
5. 内容风险开发：试图排除加性账本无法检测组合。确有3/3非地板反例；共享内容与规则控制恢复1/3，原受限语法0/3被实际提醒语义漏检反例纠正。事实效用下降，拒绝侧信道未覆盖，无算法新颖性。

## 主证据资格

两个模块目前均不足以作为最终论文“新算法领先”主证据。可用作接线审计、失败归因、开发反例与方法局限。MM建议收缩为可解释SafeTask排序+硬门；C²保留开发研究，先明确与CQE/内容依赖控制的区别，不继续调到出现优势。

阅读：mmfopd_repair_results.md、c2rag_content_risk_results.md、case_evidence.md、encoding_dimensions.md、related_work.md。完整数值CSV、原始聚合JSON、冻结协议、函数行号、验证结果和哈希在同目录。真实学生明细仅本地，公共包只含聚合与自编案例。
''')
write('README.md','# CogniGuard 独立实验副本 / 2026-10-19\n\n入口：group_meeting_results.md。MM决策PIVOT，C²决策ANALYZE。仅实验副本，EXPLORATORY。\n\n运行顺序：freeze.py → run_mm.py（失败并保留）→ repair_driver.py → run_mm_v2.py → run_new_families.py → run_content.py → cold_latency.py → fairpool_check.py → validate_evidence.py → build_reports.py。实验驱动拒绝覆盖已有冻结目录。复现请复制到新目录，不在原证据上重跑。依赖本地旧实验、授权UCI缓存和现有Qwen tokenizer；未打包学生数据或模型。相关工作仅文献核对，未运行第三方系统。\n\n_MM全量耗时混用合法选择缓存，不能作为公平速度对比；采用独立cold latency表。真实学生*_LOCAL.json仅本地，远端逐文件哈希核验记录见本地sync_receipt.json。_\n')
print('reports, CSV and four figures generated')
