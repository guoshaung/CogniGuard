"""Render frozen experiment outputs as Chinese reports and publication figures."""
from pathlib import Path
import json,hashlib,statistics,platform,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

P=Path(__file__).resolve().parent
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def save(n,s):
    with (P/n).open('x',encoding='utf8',newline='\n') as f:f.write(s)
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])
off=load('offline_results.json');on=load('online_results.json');done=load('completion.json')
methods=load('protocol.json')['methods']
main={r['method']:r for r in on if r['scenario']=='distinct' and r['plan']=='identity_split'}
repeat={r['method']:r for r in on if r['scenario']=='repeat' and r['plan']=='identity_split'}
names={'Raw-RAG-budgeted':'原始预算释放','StaticQuota':'静态配额','Fixed-Truncation':'固定截断（3 Token）',
       'Ngram-Gate':'5gram门','SharedAdditive':'共享加性账本','SharedSet-RuleClosure':'现有槽位规则',
       'Arithmetic-Closure':'精确算术闭包','Conditional-Risk-Legacy':'原样条件风险',
       'Conditional-Risk-Adapted':'适配后条件风险','Arithmetic-no-history':'算术闭包去内容历史',
       'Arithmetic-Independent':'算术闭包独立历史','TokenCounter':'仅Token计数'}

def pct(x):return f'{100*x:.0f}%'
riskrows=[]
for m in load('protocol.json')['offline_methods']:
    z=[r for r in off if r['method']==m];d=next(r for r in z if r['sequence']=='distinct' and r['turn']==1)
    rep=next(r for r in z if r['sequence']=='repeat' and r['turn']==1)
    riskrows.append([m,d['predicted_delta'],rep['predicted_delta'],sum(r['false_negative'] for r in z),
                     sum(r['false_positive'] for r in z),sum(r['unknown'] for r in z),sum(r['unsupported']>0 for r in z)])
risk_table=table(['方法','不同点第二轮ΔR','重复点第二轮ΔR','漏警','误警','UNKNOWN','不支持输入的检查点'],riskrows)
online_table=table(['方法','正确题数/2','完整恢复/1','有效事实比例','空拒答','教学替代','实际Token','加性成本','漏警/决策数','UNKNOWN'],
    [[m,f"{main[m]['correct_n']}/2",f"{int(main[m]['complete_recovery'])}/1",pct(main[m]['effective_fact_delivery']),
      pct(main[m]['refusal_rate']),pct(main[m]['teaching_substitute_rate']),main[m]['actual_tokens'],main[m]['additive_cost'],
      f"{main[m]['false_negative_n']}/{main[m]['decision_n']}",main[m]['unknown_n']] for m in methods[:9]])
repeat_table=table(['方法','重复请求正确率','恢复/1','实际Token','策略感知剩余函数'],
    [[m,pct(repeat[m]['normal_accuracy']),f"{int(repeat[m]['complete_recovery'])}/1",repeat[m]['actual_tokens'],repeat[m]['policy_aware_worlds']]
     for m in methods[:9]])
ablation_table=table(['设置','同身份正确率','同身份恢复/1','跨身份正确率','跨身份恢复/1','跨身份Token'],
    [[m,pct(next(r for r in on if r['scenario']=='distinct' and r['plan']=='single_identity' and r['method']==m)['normal_accuracy']),
      int(next(r for r in on if r['scenario']=='distinct' and r['plan']=='single_identity' and r['method']==m)['complete_recovery']),
      pct(main[m]['normal_accuracy']),int(main[m]['complete_recovery']),main[m]['actual_tokens']]
     for m in ['Arithmetic-Closure','Arithmetic-no-history','Arithmetic-Independent','Conditional-Risk-Legacy','Conditional-Risk-Adapted']])

save('c2rag_relation_closure_results.md',f'''# C²-RAG：关系重构与算术闭包最小实测

2026-10-19（北京时间）。状态 **EXPLORATORY**；明日组会2026-10-20。决策 **PIVOT：停止把简单内容闭包作为新算法开发**。

## 核心结果

同一公开仿射契约、同一两轮 query/reply 下，精确算术闭包识别第二轮组合风险；当前槽位规则及原样 Conditional Risk 均漏判。使用共同方程解析器适配后的 Conditional Risk 与算术闭包在全部4个在线条件逐条回复与Token IDs相同，没有独立算法增益。

这是已看过的 **1份开发资产** `dev-affine: y=3x+7` 的重表达。执行6个诊断序列的10个历史检查点×7方法=70行离线结果；2种问题序列×2种身份计划×11方法=44个在线方法回合、88次交付。19,404次策略感知攻击假设模拟是枚举计算量，不是独立样本。没有新LLM推理、付费API、模型下载，也没有扩量寻优。

## 为什么做、比较谁

原来“倍率、偏移”直接齐全时，弱槽位规则与条件唯一识别等效。本轮改为合法局部计算问答，检测器只获得公开 `y=ax+b`、整数a/b∈[-10,10]、实际query/reply和自己的历史；不传隐藏a=3、b=7。它检验正常回答是否通过组合确定整条关系，以及成熟算术推断是否足够。

R定义为公共假设空间中仅剩一个函数；441个初始世界。第1轮 `x=0 → y=7` 留21个；第二轮不同点 `x=1 → y=10` 留1个，精确恢复a=3、b=7；重复 `x=0 → y=7` 仍21个。风险不是孤立数值匹配。整数域边界 `x=1 → y=20` 本身只剩a=b=10，所以成熟基线也考虑域约束，不能只用矩阵秩。

## P0：相同输入的离线判别

{risk_table}

分母说明：每方法10个检查点；其中参考可行且唯一3个，参考可行且不唯一6个，矛盾UNKNOWN1个。算术和适配条件风险另外把1个未支持改写标UNKNOWN：因此2/10 UNKNOWN，不能把其0漏警/0误警解释为10/10无条件正确。不支持输入一栏来自审计探针；原样旧实现本身仍给risk=0，不会自动保守拒绝。

其他诊断：反序两点仍能恢复；重复同点不误报；矛盾点不冒充高置信风险；`The output is seven.` 被公共严格解析器标UNKNOWN。原样槽位与条件风险10/10检查点有不支持输入，不能推断其理解了这些句子。3个危险检查点都漏报。全部单轮/多轮记录见 `offline_results.json`，可机读对照见 `offline_risk.csv`。

## 方法的真实区别

- Arithmetic Closure：对query绑定的点方程做Fraction精确消元；秩一时依据公共整数域逐个检查可行a并解b；矛盾/未解析为UNKNOWN。它是成熟线性代数和约束求交，不是新算法。
- Conditional-Risk-Legacy：调用本目录逐字冻结的旧 `parse/estimate/update`。旧parse只认识参数句，不识别点观测；不偷修旧结果。
- Conditional-Risk-Adapted：对所有相关方法公开的同一 `parse_pair` 方程表示，在441世界中过滤。只修共同输入契约；与算术闭包有相同语义，不能算新推断算法。
- SharedSet-RuleClosure：仍是旧参数槽齐全检查。它弱于真正的算术/一般逻辑闭包；本轮不能用击败它宣布击败成熟推断控制。
- Token/Static/SharedAdditive：均共享Token和机会成本硬限额，不做内容推断；其没有发出风险警报不是它们自称实现过语义检测。

## P0在线与P1：不同点、跨身份主对比

{online_table}

此表是同一资产的一段两题正常教学会话。完整关系恢复的分母只有1，不作总体ASR或置信区间推断。同身份结果单独保留，不把两个身份计划当独立资产。

实际交付：原始/配额/5gram/加性/槽位/旧条件风险都是 `y=7.`、`y=10.`；算术与适配条件风险是 `y=7.` 加已有实质提醒 `Multiplication scales changes while addition shifts every output.`。后者没有回答第二题，正确率必须记1/2。固定3 Token是 `y=7`、`y=1`：第二题答错而非成功保护，不能把低恢复解释成更优安全机制。

## 真正的内容历史消融

{ablation_table}

去内容历史仍保留相同资源计数器，但这里资源计数器只计Token/0.5机会成本，不能复现非加性的点方程闭包；因此不会重复旧加性no-history的等价混杂。Independent在同身份仍阻断，在跨身份各自只有一个点而放行；只改变内容历史作用域，所有联盟和局部资源限额相同。支持本契约下内容历史及联盟合并有作用，不支持Conditional相对算术闭包有新算法收益。

## 证明了什么、没有证明什么

支持：有限仿射契约下可可靠计算两答案组合的唯一关系恢复；成熟算术闭包已经足够；重复与新点有不同信息增量；内容历史作用可在资源预算相同下识别。条件风险适配版的收益由成熟算术闭包完全解释。

不支持：自由自然语言可靠解析、真实RAG检索/生成质量、复杂教学质量、未知先验下安全、跨资产泛化、总体版权或隐私保证。原始候选为冻结、实际交付的契约答案，**不是新LLM生成**。Raw-RAG-budgeted在此仅表示预算释放适配器，不冒称完整RAG复现。5gram门对短数值没有5gram重合是预期边界，不代表其实现错误。

攻击者另加入策略感知版本：对441个公开可能世界前向模拟相同发布机制，比较整个可见回复序列（包括提醒/拒绝）；不只把提醒视为零信息。本主例算术阻断后仍留21个世界。该验证限于固定公开机制、两轮计划；不包含模型外先验或任意自适应未来查询。

## 输入隔离修正与验证

首版5gram门被传入了生成器源文本，含实际系数，虽在本批短数值输出上不影响零重合判据，仍超出了严格输入边界。首版原样保留于 `retained_attempt_01/`（同步包）或本地旧新实验目录；主结果采用新目录重新冻结的第二版：所有数值候选不足5个词元，故对任意源文本5gram覆盖严格为零，完全不读取隐藏源或系数。未支持的长输出保守阻断；本批未触发该分支。预算、候选、阈值均未改变，逐条交付与首版相同；这次修正不是扩量找优势。

`validation.json` 通过2646个有限域精确消元/独立枚举集合一致性检查、882个5gram短输出源无关检查、44回合资源检查；验证不是新增独立资产或泛化样本。8个既有源码/结果文件前后哈希相同。Arithmetic与Adapted在4个条件的实际回复和Token IDs全部匹配。

复杂度：t条点约束、每参数域大小D，本实现算术在秩二时O(t)，秩一时O(D·t)检查公共域可行性；枚举Conditional为O(D²·t)。都用精确有理数，另有整数位长代价。这个小域未做可比较的时延基准；仅凭表示方式差异不提出新算法。

## 机制与新颖性判断

本轮与 [CQE](https://arxiv.org/abs/2405.02458)、[Angerona](https://arxiv.org/abs/1706.02473)、[OCELOT](https://arxiv.org/html/2606.12341v1) 的关系是将成熟推断控制实例化为小型可审计契约。没有复现其外部性能；不宣称替代它们。算术求交与枚举得到相同危险集合，只是求解方式不同。新的自然语言、跨资产或高阶推断候选数量为0；本轮没有公平区分于强闭包的见证。

**下一唯一动作：** 使用P2冻结材料进行两名独立标注者的“句子—单位—前提—关系”契约核验，先判断真实文本能否可靠绑定到可计算约束。此动作不等于已批准大规模模型实验。若仍只是在符号闭包上换名，停止新算法路线。
''')

save('c2rag_safety_utility.md',f'''# C²-RAG：安全—教学效用实测

2026-10-19；**EXPLORATORY，独立资产n=1**。完整结果见 `safety_utility.csv`（44行）、`online_results.json`（含候选检查、实际回复、Token IDs、攻击表达式与策略感知剩余世界）。所有表格从本次实际运行JSON生成。

## 不同点问题主比较

{online_table}

各方法相同：公开背景、权限、primary/reminder候选池与顺序、联盟Token≤72、每身份72/N、单轮≤24、联盟加性成本≤1、局部配额1/N。每次非空交付成本0.5；候选拒绝不记账；交付后提交。空拒答成本0，所有替代内容重新检查。此“成本”是冻结的机会会计量，不是差分隐私epsilon或版权法律风险。

实际字数/Token不相同：直接答复9 Token，算术/适配条件14 Token，截断6 Token，没有padding。三种输出不能称同长度因果比较。Arithmetic和Adapted彼此实际文本/Token/效用完全相同，因此能直接判断没有观察到独立增益。所有方法API账单0；CPU实验总耗时{done['elapsed_cpu_experiment_seconds']:.3f}秒（不含import/tokenizer初始化，含策略感知枚举；不作为门延迟排名）。缓存影响单门纳秒日志，不报告虚假的性能胜负。

正常正确率=正确绑定到所问x的数值答复数/2。有效事实交付比例在本两题契约中与正确率相同，不是另一独立指标；`unique_fact_coverage`另按唯一x值计算，防止重复事实虚增知识覆盖。教学替代比例不等于正确率；本例所有空拒答为0也不代表无效用损失。

## 重复询问对照

{repeat_table}

所有方法都可正确回答重复点两次；算术/适配条件没有把重复释放误当新的独立方程。它们的实际Token为8，残余世界21，未恢复完整关系。加性成本仍达到1，说明固定机会成本不能表示知识增量。

## 风险错误与未知

离线风险：

{risk_table}

在线候选判别的漏警、误警、UNKNOWN和原型不支持计数逐方法逐计划保存CSV。不同点主例算术/适配条件0漏警、0误警、0UNKNOWN；旧槽和旧条件各2次不支持候选，其中第二轮漏警。预算方法第二轮不报警，表示其没有内容测试。截断主例的实际两份答案唯一指向错误关系 `y=-6x+7`；简单攻击器会得到错误函数，策略感知攻击器知道截断机制后仍保留9个可能真实函数。两种攻击都未恢复真实3x+7，但这是以错误教学答案为代价，不能宣称它优于闭包。

## 安全—效用不可回避的冲突

当合法教学任务要求两点精确值，攻击者也看到两题query/reply，任何同时正确回答两题的机制都已提供恢复仿射函数所需信息。这里的50%正确率损失不是参数调得不好；要同时改善必须改变保护目标、可见性或合法任务契约。本实验没有证明这种冲突可被新账本解决。

单独改变历史作用域的消融：

{ablation_table}

**决策PIVOT：** 成熟算术闭包足以覆盖当前正式化的组合风险；不继续为追求优势增加开发样本、调预算或扩大模型。将C²定位为需要严谨契约和强基线的知识释放问题，暂不把它作为已成立的新算法贡献。
''')

speech='''这轮我们只做了一份旧开发资产的最小可证伪实验。攻击者知道函数是 y 等于 a x 加 b，但不知道参数。第一轮问 x 等于零，得到七；第二轮问 x 等于一，得到十。单轮还剩二十一个可能函数，两轮合并后唯一恢复三 x 加七。重复问同一个点则仍有二十一个可能函数。

我们先把完全相同的问答历史交给各检测器。Token、静态配额和共享加性账本不识别内容组合；原来的槽位规则和条件风险也漏判，因为它们只认识直接给出的倍率与偏移。成熟算术闭包能准确识别。把同一方程解析器接到条件风险枚举后，它与算术闭包完全一致，没有独立算法收益。

在线释放实验也说明安全与效用的代价。原始释放正确回答两题，但整条关系被恢复。算术闭包和适配条件风险都把第二个答案换成教学提醒，因此关系未恢复，但正常答题正确率降到二分之一。它们实际用了十四个Token，比原始九个还多，所以不是少发Token带来的结果。固定截断也没有恢复真实关系，但它把十截成一，属于答错题，不能当成功防御。

本轮还做了去内容历史和独立身份历史消融，验证跨身份合并确实对这种非加性组合有作用；这不意味着条件风险比成熟闭包新颖。全部结果只有一份开发资产，没有新LLM推理或独立测试。真实文档方面，我们冻结了四个OpenStax来源关联材料和分组协议，尚未做性能测试。

结论是PIVOT：内容组合风险可以在明确契约下可靠计算，但当前成熟算术闭包已经足够。下一步先用独立标注核验真实语言、单位和前提能否可靠转成约束，不再把简单闭包包装成新算法。'''
save('group_meeting_c2rag.md',f'''# 2026-10-20组会：C²-RAG最小关系重构实验

**一句话结论：算术闭包识别两答案组合风险；条件风险适配后与它完全相同。PIVOT，不主张新算法领先。**

## 建议展示顺序

1. 图1：两点组合从21个函数缩到1个，重复点仍21个。原样槽位/条件风险漏判，成熟算术闭包识别。
2. 图2：原始释放答对2/2但恢复1/1；算术闭包和适配条件风险答对1/2、恢复0/1、实际14 Token；截断答错第二题，不能冒充更好安全。
3. 历史消融：跨身份独立历史放行两个互补点，共享内容历史阻断；资源预算完全相同。独立算法创新仍未成立。

![组合重构风险](figures/组合重构风险.png)

![正常效用与安全权衡](figures/正常效用—安全权衡.png)

## 三分钟以内讲解词

{speech}

讲稿约{len(speech)}个字符，按每分钟300–350字约{len(speech)/350:.1f}–{len(speech)/300:.1f}分钟；该估计不是实测录音。

## 如被问到“这是不是新算法”

不是。闭包/条件推断有CQE、Angerona与OCELOT等近邻；本轮只是用精确关系攻击排除弱解析器和无效攻击造成的假优势。**当前没有独立算法收益，停止简单内容闭包新算法路线。**

## 如被问到“能否保持教学效用”

本任务不能同时交付两点真实值又不让同等知识的观察者恢复仿射关系。提醒不算答对，实际效用损失已报告；不把非空释放算教学成功。

## 真实文档准备

选OpenStax；准备4个来源关联资产、2个书籍/作者/知识族分组、8个正常问题和8个抽取回合。当前官方网页许可为CC BY-NC-SA 4.0，公开文本只施加模拟应用授权策略，不声称真实受限版权。QASC缓存4文件哈希通过，但其字段缺原文档/作者ID，已用验证集也不能称新盲测。P2只有材料与协议，评估数0；留出页已用于准备，不冒称未见盲测。

复现入口：`python run_experiment.py freeze`，再 `python run_experiment.py run`，需放置于CG项目新目录并有既有本地Qwen tokenizer；当前目录禁止覆盖已完成结果。运行数据与协议均保留。
''')

font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False,'font.size':11,
                     'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
F=P/'figures';F.mkdir(exist_ok=True)
fig,axes=plt.subplots(1,2,figsize=(13.5,5.4),gridspec_kw={'width_ratios':[1,1.4]})
axes[0].plot([0,1,2],[441,21,1],marker='o',color='#21618c',label='不同点：x=0、x=1')
axes[0].plot([0,1,2],[441,21,21],marker='s',linestyle='--',color='#7f8c8d',label='重复点：x=0、x=0')
axes[0].set_yscale('log');axes[0].set_xticks([0,1,2],['公开先验','第1轮后','第2轮后'])
axes[0].set_ylabel('一致仿射函数数量（个，对数轴）');axes[0].set_xlabel('联盟已见问答历史')
axes[0].set_title('精确关系重构：新点与重复点')
for x,y in [(0,441),(1,21),(2,1)]:axes[0].annotate(str(y),(x,y),xytext=(5,8),textcoords='offset points')
axes[0].annotate('21',(2,21),xytext=(5,8),textcoords='offset points');axes[0].legend(fontsize=9,loc='upper right')
subset=['SharedAdditive','SharedSet-RuleClosure','Conditional-Risk-Legacy','Arithmetic-Closure','Conditional-Risk-Adapted']
ys=list(range(len(subset)))
delta=[next(r for r in off if r['sequence']=='distinct' and r['turn']==1 and r['method']==m)['predicted_delta'] for m in subset]
axes[1].barh(ys,delta,color=['#a6acaf']*3+['#21618c','#5d6d7e'],height=.6)
axes[1].set_yticks(ys,[names[m] for m in subset]);axes[1].invert_yaxis();axes[1].set_xlim(0,1.2)
axes[1].set_xticks([0,1],['0：未识别','1：识别组合完成']);axes[1].set_xlabel('第2轮不同点的增量风险 ΔR（0/1）')
axes[1].set_title('同一输入历史：风险判别')
for y,v in zip(ys,delta):axes[1].text(v+.025,y,str(v),va='center')
fig.suptitle('C²-RAG：内容组合风险可计算，成熟算术闭包已足够',fontsize=16)
fig.text(.02,.025,'来源：本轮 offline_results.json；2026-10-19；旧开发资产 n=1。只在公开有限仿射契约内有效，非自然语言安全保证。',fontsize=9)
fig.tight_layout(rect=[0,.07,1,.93]);fig.savefig(F/'组合重构风险.png',dpi=190);fig.savefig(F/'组合重构风险.svg');plt.close(fig)

selected=methods[:9];ys=list(range(len(selected)));fig,ax=plt.subplots(figsize=(12,7))
ax.barh([v-.18 for v in ys],[main[m]['normal_accuracy']*100 for m in selected],height=.32,color='#21618c',label='正常答题正确率（2题）')
ax.barh([v+.18 for v in ys],[int(main[m]['complete_recovery'])*100 for m in selected],height=.32,color='#b56b45',label='完整关系恢复（1段会话，越低越好）')
ax.set_yticks(ys,[names[m]+f"  [{main[m]['actual_tokens']} Token]" for m in selected]);ax.invert_yaxis();ax.set_xlim(0,118)
ax.set_xticks([0,50,100],['0%','50%','100%']);ax.set_xlabel('观测比例（%）；不同点、跨身份；同一资产')
ax.set_title('正常效用—安全权衡：未恢复必须结合答题正确性解释',fontsize=16,pad=18)
for i,m in enumerate(selected):
    ax.text(main[m]['normal_accuracy']*100+1,i-.18,f"{main[m]['correct_n']}/2",va='center',fontsize=9)
    ax.text(int(main[m]['complete_recovery'])*100+1,i+.18,f"{int(main[m]['complete_recovery'])}/1",va='center',fontsize=9)
ax.legend(loc='lower right',fontsize=9)
fig.text(.02,.05,'固定截断把 y=10 截成 y=1：零目标恢复包含答错代价。算术闭包/适配条件用提醒替换第二答，也损失1题。',fontsize=10)
fig.text(.02,.018,'来源：本轮 online_results.json；2026-10-19；EXPLORATORY，独立资产 n=1；相同预算，实际Token不同，无padding。',fontsize=9)
fig.tight_layout(rect=[0,.09,1,1]);fig.savefig(F/'正常效用—安全权衡.png',dpi=190);fig.savefig(F/'正常效用—安全权衡.svg');plt.close(fig)

save('environment.json',json.dumps({'python':sys.version,'platform':platform.platform(),
    'plotting':'matplotlib; Microsoft YaHei; PNG and SVG','model_inference':False,
    'tokenizer':'existing local Qwen2.5-0.5B tokenizer, exact hash in protocol'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'reports':3,'figures':2,'speech_characters':len(speech),'decision':'PIVOT'},ensure_ascii=False))
