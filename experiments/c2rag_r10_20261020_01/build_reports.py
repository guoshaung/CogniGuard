"""Build descriptive reports from immutable executed outputs. No tuning."""
from pathlib import Path
import json,csv,math,html
P=Path(__file__).resolve().parent
def read(n):return json.loads((P/n).read_text(encoding='utf8'))
def text(n,t):
 with (P/n).open('x',encoding='utf8',newline='\n') as f:f.write(t)
def save(n,x):text(n,json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def csvsave(n,rr):
 with (P/n).open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
A=read('adjudicated_assets.json');ep=read('C_D_episodes.json');risk=read('B_risk.json');ex=read('A_extraction.json');protocol=read('protocol.json');methods=protocol['methods']
cn={'formula':'公式参数','units':'物理／化学单位','condition':'条件判定','process':'因果过程'}
labels={'B0-Raw-budgeted':'Raw预算释放','B1-StaticQuota':'静态配额','B2-SharedAdditive':'共享加性',
 'B3-LegacySlots':'旧槽位闭包','B4-SharedClosure':'共享成熟闭包','B5-Conditional-Matched':'条件风险（同表示）',
 'B5old-Conditional-Current':'旧Conditional前端','A0-NoContentHistory':'无内容历史','A1-IndependentHistory':'独立内容历史','S-TypedSet':'共享带类型事实集'}
summary=[]
for scenario in dict.fromkeys(r['scenario'] for r in ep if r['scenario']!='NOT_RUN'):
 for m in methods:
  for cat in ['ALL',*cn]:
   rr=[r for r in ep if r['scenario']==scenario and r['method']==m and (cat=='ALL' or r['category']==cat)]
   if not rr:continue
   ss=[r for r in rr if r['complete'] is not None]
   summary.append({'scenario':scenario,'method':m,'category':cat,'assets':len(rr),'scored_assets':len(ss),
    'complete_n':sum(r['complete'] for r in ss),'complete_rate':sum(r['complete'] for r in ss)/len(ss) if ss else None,
    'correct_n':sum(r['correct_n'] for r in rr),'question_n':sum(r['question_n'] for r in rr),
    'fact_coverage':sum(r['fact_coverage'] for r in rr)/len(rr),'refusal_n':sum(r['refusal_n'] for r in rr),
    'reply_tokens':sum(r['reply_tokens'] for r in rr),'mean_reply_tokens':sum(r['reply_tokens'] for r in rr)/len(rr),
    'unknown_turn_n':sum(r['unknown_turn_n'] for r in rr),'substitution_n':0})
save('summary.json',summary);csvsave('asset_method_summary.csv',summary)
rs=[]
for m in methods:
 rr=[r for r in risk if r['method']==m];pos=[r for r in rr if r['truth']==1];neg=[r for r in rr if r['truth']==0];unk=[r for r in rr if r['truth'] is None]
 rs.append({'method':m,'dangerous_prefix_n':len(pos),'safe_prefix_n':len(neg),'reference_unknown_n':len(unk),
  'decision_miss_n':sum(r['decision_miss'] for r in rr),'decision_false_block_n':sum(r['decision_false_block'] for r in rr),
  'detector_unknown_n':sum(r['unknown'] for r in rr),'risk_FN_n':sum(r['risk_FN'] for r in rr),'risk_FP_n':sum(r['risk_FP'] for r in rr),
  'known_risk_predictions':sum(r['predicted_risk'] is not None for r in rr),
  'note':'operative allow/block errors differ from semantic detector errors; budget-only has no risk predictions'})
save('risk_summary.json',rs);csvsave('risk_summary.csv',rs)
exs=[]
for m in dict.fromkeys(r['method'] for r in ex if r['method']!='ALL'):
 rr=[r for r in ex if r['method']==m and r.get('gold') is not None];tp=sum(r['tp'] for r in rr);fp=sum(r['fp'] for r in rr);fn=sum(r['fn'] for r in rr)
 exs.append({'method':m,'author_candidate_sentences':len(rr),'PASS':sum(r['status']=='PASS' for r in rr),'FAIL':sum(r['status']=='FAIL' for r in rr),'UNKNOWN':sum(r['status']=='UNKNOWN' for r in rr),
             'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn),'F1':2*tp/(2*tp+fp+fn),
             'scope':'author-controlled binding grammar ONLY; not original textbook semantic relation extraction'})
save('extraction_summary.json',exs)
groups=[]
for a in A:
 mathfam='unsupported-process' if a['category']=='process' else 'unverified' if not a['source_verified'] else 'monomial' if a['category']=='formula' or a['id'] in ['heat','electric-power'] else 'rational-quotient' if a['category']=='units' else 'polynomial-inequality' if a['id'] in ['discriminant','root-domain'] else 'rational-inequality' if a['id']=='geometric-series' else 'affine-inequality'
 groups.append({'asset':a['id'],'book':a['book'],'source_section':a['page'],'semantic_family':a['family'],'mathematical_family':mathfam,'eligible':a['eligible'],'split':'author-development-seen','source_seen_R9':a.get('seen_source_r9',False)})
save('data_groups.json',groups)
add=read('additional_source_capture_private.json');save('source_registry_addendum.json',{k:{x:y for x,y in v.items() if x!='paragraphs'} for k,v in add.items()})
text('LICENSE_SOURCE_MATERIAL.md','''# 来源、许可与模拟授权

来源为 OpenStax / Rice University：College Physics 2e（Paul Peter Urone、Roger Hinrichs 等），College Algebra 2e（Jay Abramson 等），Chemistry 2e（Paul Flowers、Klaus Theopold、Richard Langley、William R. Robinson 等），Biology 2e（Mary Ann Clark、Matthew Douglas、Jung Choi 等）。作者完整名单以各书前言为准。

2026-10-20抓取的前言许可链接均为 CC BY-NC-SA 4.0。本包来源派生摘录与作者改编问题按同许可标注；仅供非商业教育研究，保持署名和相同方式共享。原始整页HTML只在本地local_sources保存，发布URL、段落ID、HTML哈希与短摘录。排除第三方插图、专用教师手册。模拟应用保护策略不改变教材实际许可，不声称公众不能引用、学习或正常教学使用。

前言：https://openstax.org/books/college-physics-2e/pages/preface ；https://openstax.org/books/college-algebra-2e/pages/preface ；https://openstax.org/books/chemistry-2e/pages/preface ；https://openstax.org/books/biology-2e/pages/preface 。失败的Prealgebra来源不进入实验。
''')
cats=[]
for cat in cn:
 aa=[a for a in A if a['category']==cat];cats.append(f'- {cn[cat]}：候选 {len(aa)}，来源核验 {sum(a["source_verified"] for a in aa)}/{len(aa)}，约束实验有效 {sum(a["eligible"] for a in aa)}/{len(aa)}。')
cross=[r for r in summary if r['scenario']=='cross_agent' and r['category']=='ALL']
lines=[]
for r in cross:
 lines.append(f'- {labels[r["method"]]}：完整恢复 {r["complete_n"]}/{r["scored_assets"]}；正常答对 {r["correct_n"]}/{r["question_n"]}；事实覆盖 {r["fact_coverage"]:.1%}；拒答 {r["refusal_n"]}；回复 Token 总计 {r["reply_tokens"]}，每资产均值 {r["mean_reply_tokens"]:.2f}；检测 UNKNOWN {r["unknown_turn_n"]}。')
rlines=[f'- {labels[r["method"]]}：危险历史放行 {r["decision_miss_n"]}/59；安全历史误拦 {r["decision_false_block_n"]}/144；检测器 UNKNOWN {r["detector_unknown_n"]}/220；有值风险预测 {r["known_risk_predictions"]}/220。' for r in rs]
manifest_note='''全部单一AI作者开发标注；没有两名独立标注者、盲测或人类一致性统计。24是候选知识资产数；23来源核验，17进入人工结构化契约实验。127个攻击计划、1270个有效资产×计划×方法运行、2200条离线方法判定都不是独立样本。另70条为7个未支持/失败资产×10方法的未运行记录。

有效17资产来自3本书（物理12、代数4、化学1），17个语义任务族但只有5个主要数学结构族；乘积式及商式重复较多。生物6过程只做来源检查。没有按书籍/作者隔离的训练—测试验证，也没有把R9四资产加入新分母；电功率来源章节已在R9看过，新问题仍属开发。其它资料也经本轮作者阅读，不称未见留出。
'''
text('c2rag_r10_report.md',f'''# C²-RAG R10：24候选／17受支持契约扩样与强基线验证

2026-10-20，北京时间。**EXPLORATORY，决策 PIVOT。已执行，未调题重跑，停止扩至40。**

## 结论与边界

共享内容历史在跨Agent互补披露中有作用，但新增17任务仍未证明需要新的Conditional Risk或额外算术闭包：成熟符号闭包、有限世界条件判据、共享带类型事实集，在全部127计划上回复Token IDs一致。当前保护目标要求两个私有输入绑定及其派生结论，直接事实齐全便足够判断；这是对本轮构造偏简单的限制，不能解释成强算法创新。

本轮没有完成24份可评分的真实语言知识重构测试。不能把17份来源支持的作者数值任务、6份未支持过程和1份来源失败，包装为24份独立真实文本安全证据。

## 样本、来源与分母

{manifest_note}
{chr(10).join(cats)}

每份来源记录正文URL、段落ID、HTML SHA256与许可；源词定位失败及更正保留在assets.json、source_adjudication.json。正式表现前对胡克来源用词及级数章节作溯源更正；三角形URL失败仍保留，未换一个成功题补数。原HTML只存本地。前言均观察到CC BY-NC-SA 4.0，见LICENSE_SOURCE_MATERIAL.md。公开教材只受模拟应用授权，不声称教材真实禁止教学引用。

## 冻结与公平条件

先读取远端算法审查、关系闭包及R9，哈希见prior_evidence_audit.json。prepare/adjudicate完成来源核验后，freeze.py在第一次A/B/C/D运行前固定资产、目标、公开知识、候选、正常问题、攻击计划、变量域、UNKNOWN策略和代码SHA256。没有据表现修改测试。

每资产保护的是“完整绑定的作者教学例题实例”：两个私有输入（含单位／同对象同状态）加公开教材公式导出的结论。公式本身公开。攻击恢复必须输入绑定全部正确且派生结果正确，不能凭一个孤立数字算完整恢复。**保护目标是完整实例，不是任意单个答案或教材公式的保密性。** 不同任务的公开规律不同，绝不是只改同一个仿射例子的数字；但代数结构高度重复，必须按结构族认识其相关性。

联盟回复预算256 Token、每身份256/N、单轮128；联盟非空交付机会2、每身份2/N，每次非空计1。预算不专门缩紧到使Raw自动安全。本轮无候选因预算截断；相同预算不代表交付相同Token，实际数量逐条记录。全部方法的公开契约、权限、候选及可见query/reply相同。查询不夹带私有输入，拒答查询也留在历史。无内容／独立历史仅移除内容范围，预算计数器保留，区别被明确记录。

## A：关系提取，不能与推理性能混写

17资产各2条作者规范化数值答案，共34句有开发真值。R10通用赋值／单位语法34/34 PASS，数值绑定P/R/F1均1，UNKNOWN0；这只是刻意受控的输入接口检查。四个原样R9前端各0/34 PASS、34/34 UNKNOWN，Recall/F1为0，无预测时Precision未定义。旧Conditional并未获得更强解析器后仍冒称原实现有效。

原始教材段落也提交并保存输出，但本轮没有建立可靠的完整原文关系原子真值，故原文Precision/Recall/F1 **不评分**；它们不是34句规范化作者答案。6个过程同样没有可靠因果／时序契约。原始自然语言端到端安全有效分母为0，不能用受控接口100%补这个空缺。代数条件的5个正例全是True，没有False条件分支，故不能证明条件分支泛化。

## B：同一历史下风险判定

220个历史前缀（相关重复）中，有限世界参考判据59危险、144不完整安全、17前提冲突UNKNOWN。成熟SymPy等式唯一解与共同公开有限域枚举220/220一致；其中203是有值判断，17是共同UNKNOWN。B5-Conditional-Matched是有限世界条件风险适配器，使用与B4完全相同的变量、单位解析与历史输入，不是原Conditional原文前端，也不是新算法候选。另行保留原Conditional前端退化对照。

{chr(10).join(rlines)}

预算方法没有内容风险预测，不能把其操作漏放率伪装成语义检测F1；旧槽检查UNKNOWN时按原逻辑放行；旧Conditional全UNKNOWN保守拒答。风险漏检／误检与操作放行／阻断分别保存在B_same_history_risk.csv及risk_summary.csv，未知不变成“安全”。220条前缀不能当220份独立资产。

## C／D：实际释放后的重构与正常教学质量

以下是同一跨Agent互补计划：17份有效资产、34个局部正常问题。Raw为直接释放冻结候选的预算适配器，**未运行检索、生成或真实模型攻击**。

{chr(10).join(lines)}

按类别，Raw／静态／加性／旧槽位均为公式6/6、单位6/6、条件5/5完整恢复；共享闭包、同表示条件判据、类型事实集均为0/6、0/6、0/5，正常答对分别6/12、6/12、5/10。过程0份有效，恢复率为NA而不是0%。

同身份互补时，独立内容历史也阻断完整恢复；跨身份17/17恢复。这是共享范围的作用。无内容历史同身份与跨身份均17/17恢复。单轮完整候选17/17本就危险，三种共享内容控制拒绝全部完整候选；不能归为跨Agent收益。重复冗余与“第一事实＋公共前提”阴性组均未完整恢复，三种内容控制正常答对各34/34，操作误拦0。单位换算只有8份适用资产，非17份：Raw8/8恢复，三种共享内容方法0/8，正常8/16。前提冲突17份全标UNKNOWN、移出保护率；即使某方法拒答后历史变成不完整，也不借此计算“安全成功”。

所有拒答都是实际空答，正常问题按0分计；没有提醒充当答对，没有新生成教学替代。替代次数均0。C记录完整恢复、部分绑定、UNKNOWN；D记录严格正确率、事实覆盖、拒答与实际query/reply Token。局部完整答对不代表能答对危险复合题。未实现自适应网络攻击、外部教材检索或拒答侧信道分析，不能据此宣称语义安全保证。

## 统计与验证

统计单位为资产，主比较17；查询、Agent、方法不扩分母。该集合为作者便利开发样本，来源书籍有效聚类仅3个，且保护目标／数学结构高度相关。**不提供具有总体推断意义的95%置信区间**；对17次相关开发题机械套二项区间会夸大可信度。asset_method_summary.csv报告每类分子分母与逐资产数据，可供将来真实分组留出使用。

验证：220条符号vs有限世界、220条冻结作者标签vs求解器、17条独立Fraction/Boolean派生计算、254条方法输出Token IDs比较、1270个预算检查均通过；53个旧JSON工件哈希未变。两种求解器共用关系前端，这些验证不是独立语义标注。没有付费API、大模型下载、检索或模型推理；仅复用本地Qwen tokenizer。执行耗时见completion.json，不把加载外CPU耗时当系统延迟比较。

## 机制审稿与下一步

共享历史收益：有，来自联合可见信息的范围；预算类不能替代。成熟闭包：对这17个受控数值/条件契约足够，而且更简单的带类型事实集合也足够。真实语言：仍是表示、单位/对象/状态绑定、前提作用域、跨公式指代与过程契约的问题，本轮未解决。创新性：没有支持新C²算法的独立贡献，不能把有限世界枚举、条件推断或多轮积累称作创新；CQE/Angerona/OCELOT近邻判断沿用已同步审查，不因扩样推翻。

**PIVOT：停止扩到40与开发新Conditional算法。下一步唯一值得投入的是独立标注、按来源族留出的原文→带类型约束验证；在此之前，不继续报新的安全泛化率。** 若没有资源取得可靠标注，停止该方向新增性能实验。不是为了算法领先而引入更大模型或额外模块。
''')
text('c2rag_r10_failure_cases.md','''# R10失败与反例（全部保留）

1. 三角形目标来源URL抓取失败，未核验来源；不更换一个好题补数，约束分母排除1。
2. 级数初选9.3只有几何序列，不足以支持无限级数目标；正式冻结前定位9.4级数章节，原抓取与更正保留。胡克定律的关键词spring constant未命中，正式冻结前用原章force constant段落核验；signed force是-kx，本题明确只求恢复力大小。
3. 生物6过程虽有原文，缺独立可靠因果／时序标注，全部UNSUPPORTED，不跑伪造恢复率。
4. 34条答案是作者规范化赋值，不是34条原始教材句子。R10解析34/34并不证明自然语言关系泛化。原文完整关系F1未评分；旧前端34/34 UNKNOWN。
5. 5个条件题全部处于True分支，没有False分支测试；前提冲突只按UNKNOWN处理。不能声称覆盖了完整条件分支。
6. 保护目标要求两个输入与派生关系全部恢复，因此简单类型事实集合就能匹配成熟闭包。127/127计划输出相同：扩样没有提供超越集合闭包的新算法区分证据。
7. 跨Agent防护0/17完整恢复对应正常17/34；安全以拒答第二事实为代价。旧Conditional0/17对应0/34且全UNKNOWN，不能称有效语义防护。
8. 17资产语义来源不同，但只有5个主要代数结构族、3本有效来源书籍；无独立盲测与双人标注。不能以1270回合宣称1270样本。
9. 攻击者是冻结约束重构器，不模拟攻击者检索公开教材、知识先验猜测或策略拒答侧信道。公开教材保护只是模拟授权。
10. 未扩至40；未因结果更改资产、规则、配额、问题或候选；未修改生产代码与旧结果。
''')
speech='''我们这轮检查的是：扩到更多教材主题以后，共享内容历史能否阻止互补知识被拼全，以及是否真的需要新的算法。

先冻结了24个候选，覆盖公式、单位、条件和过程，每类6个。结果只有17个适合进入精确约束实验：6个公式、6个单位、5个条件；另有一个来源失败，6个生物过程缺可靠形式化契约，保留为不支持。所有标注都是作者开发标注，不是独立盲测。

我们必须分清两条轨道：教材来源是真实的，但数值问题和候选答案是预先编写的。受控赋值句能解析，不代表原始教材的指代、前提和过程已经解析成功。真实原文端到端安全测试的有效分母仍然是零。

在17个受支持实例的跨Agent互补场景里，预算释放、静态配额和共享加性都完整恢复17个，正常回答34题全部正确。共享内容控制阻断完整恢复，但只答对17题，安全存在明确的教学代价。重复同一个事实则没有完整恢复，也无需拒绝。

最关键的反例是：成熟符号闭包、有限世界条件判据和简单带类型事实集合，在全部127个计划上的输出完全相同。不是Conditional获得了新优势，而是这批保护目标仍可以由事实齐全判断。旧Conditional前端全部未知、全部拒答，更不能算泛化成功。

因此结论是转向，而不是继续凑到40：共享内容历史有用，新闭包算法的独立价值仍没有证据。下一步应先做独立标注和来源族留出的原文关系表示验证，解决表示可信度，再讨论新的安全—效用算法。'''
text('group_meeting_c2rag_r10.md','# C²-RAG R10组会稿（约2分半）\n\n'+speech+'\n\n数据：24候选，17受控有效；主结果17/17→0/17，正常34/34→17/34；PIVOT。所有结果EXPLORATORY。\n')
text('README.md','# C²-RAG R10：24候选／17受支持\n\nEXPLORATORY，PIVOT。先看[c2rag_r10_report.md](c2rag_r10_report.md)和[group_meeting_c2rag_r10.md](group_meeting_c2rag_r10.md)。\n\nA原文语义F1未可靠标注，不评分；34条规范化作者答案仅验证接口。B同历史风险、C实际恢复、D正常效用分别存CSV/JSON。17个新任务由真实来源规律支持，不是教材例题原数值，也不是独立盲测；6过程不支持、1来源失败。\n\n复现：已有项目CPU Python/SymPy/transformers环境，本地Qwen tokenizer，不需模型推理。prepare→adjudicate_sources→freeze→run→validate→build_reports；输出拒绝覆盖，应在新副本运行。公开包不含本地HTML；source_registry与addendum记录来源哈希。\n')
text('.gitattributes','* -text\n');text('.gitignore','__pycache__/\nlocal_sources/\n*_private.json\n')
# Scientific figures: actual counts, Chinese labels; no synthetic showcase data.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False,'font.size':11})
(P/'figures').mkdir(exist_ok=True)
fig,ax=plt.subplots(figsize=(13,7.5));y=list(range(len(cross)));vals=[r['complete_n'] for r in cross]
colors=['#808b96' if r['method'] not in ['B4-SharedClosure','B5-Conditional-Matched','S-TypedSet'] else '#287d8e' for r in cross]
ax.barh(y,vals,color=colors);ax.set_yticks(y,[labels[r['method']] for r in cross]);ax.invert_yaxis();ax.set_xlim(0,20)
for i,r in enumerate(cross):
 note=f'{r["complete_n"]}/17'
 if r['method']=='B5old-Conditional-Current':note+='（全UNKNOWN、全拒答）'
 ax.text(r['complete_n']+.15,i,note,va='center',fontsize=10)
ax.set_xlabel('完整实例恢复资产数（受支持分母17）');ax.set_ylabel('释放方法');ax.set_title('R10跨Agent互补：共享内容控制有效，但简单类型集合已足够',pad=15)
fig.subplots_adjust(left=.25,bottom=.20,top=.88,right=.97)
fig.text(.03,.10,'公式6＋单位6＋条件5；生物过程6不支持、来源失败1未计入。24候选不等于24份有效证据。',fontsize=10)
fig.text(.03,.055,'来源：C_D_episodes.json，2026-10-20；作者编写的教材来源关联任务，EXPLORATORY，非原文端到端泛化。',fontsize=9)
for ext in ['png','svg']:fig.savefig(P/'figures'/('完整重构对比.'+ext),dpi=180)
plt.close(fig)
fig,ax=plt.subplots(figsize=(13,7));x=list(range(len(cross)));correct=[r['correct_n']/r['question_n']*100 for r in cross];safe=[(1-r['complete_rate'])*100 for r in cross]
ax.bar([i-.18 for i in x],correct,width=.36,label='正常局部问题答对率',color='#287d8e')
ax.bar([i+.18 for i in x],safe,width=.36,label='未完整恢复比例（不等于语义安全保证）',color='#9aa3ab')
ax.set_xticks(x,[labels[r['method']].replace('（','\n（') for r in cross],rotation=30,ha='right',fontsize=9)
ax.set_ylim(0,115);ax.set_ylabel('比例（%）');ax.set_xlabel('方法；每方法17资产、34局部问题');ax.set_title('R10安全—效用：阻断互补释放对应正常答对率下降至50%',pad=15)
ax.legend(loc='upper center',ncol=2,fontsize=9)
fig.subplots_adjust(left=.08,bottom=.32,top=.86,right=.98)
fig.text(.03,.105,'旧Conditional全部UNKNOWN拒答：其灰柱100%仅表示未交付，不能算可靠风险识别。三种共享内容方法输出一致。',fontsize=10)
fig.text(.03,.065,'跨Agent回复Token总计：预算类279；共享闭包／条件判据／类型集合135；旧Conditional 0。长度并未匹配。',fontsize=10)
fig.text(.03,.025,'来源：D_safety_utility.csv，2026-10-20；受控契约作者开发实验，EXPLORATORY；6过程与1失败来源排除。',fontsize=9)
for ext in ['png','svg']:fig.savefig(P/'figures'/('安全教学效用.'+ext),dpi=180)
plt.close(fig)
# Standalone review view with embedded real figures and explicit denominator warnings.
text('report.html','<!doctype html><meta charset="utf-8"><title>C²-RAG R10</title><style>body{max-width:1100px;margin:40px auto;font:17px system-ui;line-height:1.7;color:#243746}img{width:100%}strong{color:#9b4427}</style><h1>C²-RAG R10：24候选，17受支持</h1><p><strong>EXPLORATORY · PIVOT · 不是24份独立真实语言测试</strong></p><p>6个过程未支持，1个来源失败；受控任务跨Agent恢复17/17→0/17，正常答对34/34→17/34。简单类型事实集合已匹配成熟闭包，未发现新算法收益。</p><img src="figures/完整重构对比.png"><img src="figures/安全教学效用.png"><p>原文关系F1未可靠标注，端到端原文安全有效分母为0。全部数据、协议、失败与原始运行见同目录。</p>')
print('Reports and figures written; no performance inputs changed')
