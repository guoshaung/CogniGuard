"""Create requested Chinese R9 reports/figures from immutable execution JSON."""
from pathlib import Path
import json,statistics,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
sys.stdout.reconfigure(encoding='utf8')
P=Path(__file__).resolve().parent
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def save(n,t):
    with (P/n).open('x',encoding='utf8',newline='\n') as f:f.write(t)
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(map(str,r))+' |' for r in rows])
def pct(v):return '未定义' if v is None else f'{v*100:.1f}%'
e1=load('e1_raw_results.json');s1=load('e1_summary.json');e2=load('e2_raw_results.json');e3=load('e3_raw_results.json')
methods=load('protocol.json')['e2_methods']
main={m:[r for r in e2 if r.get('method')==m and r['scenario']=='cross_agent'] for m in methods}
summary=[]
for m,rows in main.items():
    summary.append({'method':m,'asset_n':len(rows),'complete_n':sum(r['complete_recovery'] is True for r in rows),
                    'partial_only_n':sum(r['partial_only'] is True for r in rows),
                    'correct_n':sum(r['correct_n'] for r in rows),'question_n':sum(r['scorable_questions'] for r in rows),
                    'detector_unknown_rate':sum(r['detector_unknown_n'] for r in rows)/sum(r['candidate_n'] for r in rows),
                    'mean_tokens':statistics.mean(r['actual_tokens'] for r in rows),
                    'refusal_n':sum(r['refusal_n'] for r in rows),'substitution_n':sum(r['substitution_n'] for r in rows)})
estrategies=['Original-Full','Simple-Refusal','Fixed-Reminder','Knowledge-Local'];s3=[]
for st in estrategies:
    rows=[r for r in e3 if r.get('strategy')==st]
    s3.append({'strategy':st,'asset_tasks':len(rows),'correct_n':sum(r['normal_correct'] for r in rows),
               'coverage':statistics.mean(r['teaching_fact_coverage'] for r in rows),
               'complete_n':sum(r['complete_recovery'] is True for r in rows),
               'mean_reply_tokens':statistics.mean(r['reply_tokens'] for r in rows),
               'mean_chars':statistics.mean(r['reply_characters'] for r in rows),
               'empty_n':sum(r['empty_refusal'] for r in rows),'substitute_n':sum(r['substitution'] for r in rows),
               'meaningless_n':sum(r['meaningless_reminder'] for r in rows)})
f1table=table(['方法','P','R','F1','PASS / FAIL / UNKNOWN','UNKNOWN比例'],
 [[r['method'],pct(r['precision']),pct(r['recall']),pct(r['f1']),f"{r['pass_n']} / {r['fail_n']} / {r['unknown_n']}",pct(r['unknown_rate'])]
  for r in s1 if r['scope']=='all'])
rawtable=table(['方法','原始文本单元数','PASS','FAIL','UNKNOWN','F1'],
 [[r['method'],r['items'],r['pass_n'],r['fail_n'],r['unknown_n'],pct(r['f1'])] for r in s1 if r['scope']=='raw_paragraph'])
e2table=table(['方法','完整恢复/4','仅部分恢复/4','正常事实答对/8','检测UNKNOWN','平均实际Token','空拒答/8','替代/8'],
 [[r['method'],r['complete_n'],r['partial_only_n'],r['correct_n'],pct(r['detector_unknown_rate']),f"{r['mean_tokens']:.2f}",r['refusal_n'],r['substitution_n']] for r in summary])
e3table=table(['策略','完整答对/4','题目事实覆盖','完整恢复/4','平均回复Token','平均字符','空拒答/4','替代/4','无意义提醒/4'],
 [[r['strategy'],r['correct_n'],pct(r['coverage']),r['complete_n'],f"{r['mean_reply_tokens']:.2f}",f"{r['mean_chars']:.2f}",r['empty_n'],r['substitute_n'],r['meaningless_n']] for r in s3])
scenarios=[]
for scenario in ['single','same_identity','cross_agent','redundant','unit_or_premise']:
    rr=[]
    for m in methods:
        rows=[r for r in e2 if r.get('method')==m and r['scenario']==scenario]
        scored=[r for r in rows if r['status']=='SCORED']
        rr.append(f"{sum(r['complete_recovery'] is True for r in scored)}/{len(scored)}"+
                  (f"；UNKNOWN {len(rows)-len(scored)}" if len(rows)!=len(scored) else ''))
    scenarios.append([scenario]+rr)
scenario_table=table(['场景']+methods,scenarios)

save('c2rag_r9_real_text_report.md',f'''# C²-RAG R9：真实教育文本与组合释放实验

2026-10-19（北京时间）；2026-10-20学校组会。**EXPLORATORY；结论PIVOT。** 本轮已实际运行E1、通过门槛的E2和E3，不是仅交计划。

## 主要结论

真实来源的受支持数值子契约中，共享内容历史与成熟算术闭包能识别跨Agent组合风险；当前Conditional前端对这些原始文本全为UNKNOWN，不能宣称泛化成功。给共同类型表示后，诊断路径与强闭包相同，未发现独立算法价值。安全仍伴随明显效用损失，因果/过程与指代并未解决。

## 数据身份与来源

本轮为2本OpenStax教材、4个来源网页、4个已准备的知识资产、2个来源关联资产族。代数4.1两点线性例、代数4.2人口模型、物理20.2车灯电阻、物理20.4热/冷车灯状态关系。它们此前只做过资料准备，本轮首次在这些材料上运行此数值释放协议；**没有把R8仿射合成资产或更旧3份自编资产并入新分母**。

来源核验：4正文+2许可HTML与已有快照SHA256逐字核对；去除MathML重复annotation后保留可见原文，记录真实段落ID。`source_registry.json`给URL/作者/许可/原始HTML哈希，`e1_author_annotations.json`给原句/子片段/关系标签。原始HTML仍留原本地缓存，本轮不改。许可仍按当前网页CC BY-NC-SA 4.0，见[代数前言](https://openstax.org/books/college-algebra-2e/pages/preface)和[物理前言](https://openstax.org/books/college-physics-2e/pages/preface)。公开正文只施加作者模拟应用授权，**不声称禁止实际正常引用或教学使用**。没有访问教师专用答案手册。

4资产都已为准备而阅读，全部为作者开发实验；原“预备留出”不再称未见泛化测试。书籍、作者和来源族元数据沿用旧注册表，见`data_groups.json`。来源族划分不代表数学函数类互斥。统计分母按资产，查询/计划/方法回合不冒充独立样本；不存在学校独立盲测。

正常问题与多轮攻击计划由作者编写；答案为真实来源子片段，另有两种明确标注的单位等价变换。E3为提前冻结的源片段拼装和公共语境说明。**检索未运行、LLM生成未运行、Qwen/MiniLM模型推理0次、付费0次**；仅用已有Qwen tokenizer计算真实Token IDs，用确定性关系提取和精确求解执行交付与攻击。

## E1：真实文本关系识别

为什么做：先确认真实语句是否可被解释，防止把解析器失效当攻击失败或防御成功。比较旧槽位、旧关系规则、作者冻结的有界类型化前端配成熟约束表示、R8当前Conditional前端。所有方法得到同一公开知识契约与文本，不接收隐藏目标参数。

标注由同一AI研究作者编制；没有新增人工标注者、没有独立双人标注或人工一致率/裁决统计。标签用于开发诊断，不是独立真值。20个文本单元包括12个原始段落/句子和8个用于释放的来源子片段；存在来源重叠，不是20个独立资产。

{f1table}

P/R/F1按精确类型原子微平均，变量、单位、状态、条件和否定均属于匹配键。TP/FP/FN保留在CSV；UNKNOWN对应缺失原子仍计入Recall分母，不能丢弃UNKNOWN刷高召回。零预测时Precision未定义，不填成100%。PASS要求预测集合完全正确且无未解决关系；部分提取或错误绑定为FAIL；空且不支持为UNKNOWN。

只看原始文本单元，不混入简单子片段：

{rawtable}

“成熟”指后端精确算术/逻辑表示，不指一个现成的通用自然语言提取器：本轮前端是见过这些材料后、首次运行前冻结的有限规则。不能凭其开发P/R/F1宣称跨语料泛化。旧规则两次把冷态电阻提成无单位、无状态的裸值，记FAIL；旧槽位/Conditional的输入格式不匹配记UNKNOWN。

真实失败：人口文字题的过程目标缺失；热/冷段落的瞬态共变关系未表示；“first equation / other two”指代和限制条件无法可靠解析。没有把“as”自动解释为因果。四材料不足以建立可靠的因果知识重构基准，不临时扩造资产补齐。

E1门槛：每资产两个实际数值/单位候选均须完全PASS，4资产均2/2通过。E2/E3仅评价这4个**数值子契约**，不是整个来源段落都理解成功；失败的过程/指代关系明确UNSUPPORTED。

## E2：跨Agent重构与共享历史

为什么做：检验真实来源局部答复是否可组合，以及内容历史作用是否独立于资源额度。每资产5计划：单片段、同身份互补、跨Agent互补、跨Agent重复、记号/单位/前提变化；20计划×8方法=160个方法回合，仍只有4个资产。

资源与权限固定：联盟回复≤128 Token，活跃身份各128/N，单轮≤64；非空交付成本0.5，联盟≤1，各身份≤1/N。候选与顺序、公开先验、权限相同，拒绝候选不扣费，实际交付后更新。即使拒答，攻击者自己知道的query仍加入可见历史。预算基线不偷读源中的目标系数。

真实跨Agent互补主表：

{e2table}

完整恢复按精确有理数参数与变量/单位/工况契约判定，不按孤立值或5gram。部分恢复定义：仿射独立点约束秩/2，热冷已识别状态系数数/2；单电阻目标不伪造中间恢复率。跨族含义不同，表中仅计“只有部分恢复”的资产数，不将其平均包装成统一风险量。

**归因只限3个互补资产。** 两个仿射例和热/冷例，单片段不完整、并集完整；欧姆例在query已给2.50A时，单个12.0V回复就能恢复R=4.80Ω，属于公共物理先验下单轮危险，并非共享历史特有收益。逐片段与并集判别见`single_union_risk_audit.json`。

B3仍沿用弱参数槽检查：即使审计标记不支持，原行为仍放行，故完整恢复4/4。B5使用当前R8严格query/reply前端，无法处理本轮原文且旧整数参数域也不适用；保守拒绝所有候选，因此正常事实正确0/8，UNKNOWN8/8。它的零恢复是**全拒答退化**，不等于成功理解真实教育知识。

Shared/Independent仅改变内容历史作用域、保留完全相同资源门。同身份Independent与共享同样0/4；跨AgentIndependent恢复3/4，而共享0/4。剩下欧姆例独立单轮也会拦截。支持受限表示下共享内容历史有用，不能归因为共享加性额度。

各场景完整恢复，分母按该场景可评分资产数：

{scenario_table}

重复事实场景强闭包不误拦，正常事实8/8正确、恢复0/4。单位/前提挑战中代数记号、年↔月、电压/电流SI换算可评分；热冷公式指代不支持，故该计划8个方法行均标UNSUPPORTED，完整恢复填空值，不当作8次攻击失败。此场景有效分母3，不混入4资产主比较。

攻击者只读实际query/reply、公开契约及已交付文本；不是复用防御器的成功/失败标签。含不支持文本的攻击状态为UNKNOWN，禁止记恢复0。另用独立SymPy线性求解后端核查152个可评分E2输出及16个E3输出；**它共用有界类型前端，不能当独立语义真值**。固定拒答/输出已记录，但本轮没有证明任意自适应查询及机制侧信道安全，也没有允许攻击者直接联网读取本来公开的教材答案。

## E3：相同危险候选下安全—教学效用

为什么做：检验“低恢复”究竟是否以拒答、泛泛提醒或少答事实为代价。每资产固定相同前置局部历史，再问一个危险复合教学问题；4个策略×4资产=16行。候选在E1前冻结，未根据测试结果补造最佳答复。完整原答为故意不拦的危险对照，其风险同样计算；其他候选全部重进同一风险检查，不默认提醒为零泄露。

{e3table}

E3分母是4个危险复合问题，**不是E2的8道局部题**，不能把两表正确率直接混算。完整答对要求该题全部必要原子；知识局部替代只保留2/3或1/2的题目事实，平均54.2%，完整正确仍0/4。拒答和泛泛提醒均覆盖0%，但固定提醒确有“应用已知关系、检查单位”的步骤，按冻结作者规则“无意义提醒”0/4；该指标没有独立人工主观验证，绝不能用它替代正常答题正确率。

知识局部策略的部分覆盖主要是公共或此前已见事实，新要求的私有目标事实增量均为0，见`utility_information_gain_audit.json`。它不是解决了完整教学效用损失。它还比泛泛提醒更长（20.25 vs10 Token）；没有长度完全匹配，不能主张独立于长度的最优安全—效用优势。原完整答复平均22.75 Token，策略具体字节、字符数、Token IDs和历史总Token全部保留CSV/JSON。

不可兼得性：这些危险题要求的完整正确答案恰好唯一确定受保护目标，攻击者能看到相同语境。因此在本契约下不可能同时完整答对和阻止同能力观察者重构。局部替代有教学相关片段，不等于绕过这个信息冲突。

## E4：强基线与新颖性

当前实现的主要差异是文本/单位/前提表示兼容性，不是后端组合风险新原理。旧槽位漏解析、当前Conditional全UNKNOWN，都不能拿来削弱强闭包或包装新算法。诊断的Conditional-Contract路径与B4共用相同约束后端，20/20输出及Token IDs相同是**构造性的接口核验**，不是新增一场独立新算法竞赛；不能据此声称当前Conditional本身已支持这些文本。

与已审查的[CQE](https://arxiv.org/abs/2405.02458)、[Angerona](https://arxiv.org/abs/1706.02473)、[OCELOT](https://arxiv.org/html/2606.12341v1)一致，内容历史与条件推断本身不是新颖点；本轮未复现这些系统的外部性能。没有发现同契约同信息下超出成熟算术/逻辑闭包的独立机制收益，后续算法候选数量0。

**PIVOT。** 停止将简单内容闭包作为新算法开发。唯一下一步是独立人工核对“单位—工况—否定—指代/过程”的最小语义契约，尤其本轮3个失败单元，并在任何规则修补前冻结新的来源分组评估。它是尚未解决的可靠表示与标注问题，尚不能命名为新算法贡献。本轮不再扩资产、不改题、不调规则刷指标。

## 可复核交付

`protocol.json`保存运行前本地冻结哈希；`e1_raw_results.json`、`e2_raw_results.json`、`e3_raw_results.json`保存所有输出；三张CSV对应E1/E2/E3。`validation.json`记录168次SymPy后端一致性、160回合资源检查与11个旧文件/源快照哈希未改。原始依赖缺失和Unicode显示失败保留`operational_failures.json`，没有安装大模型或改源数据。

![完整知识恢复对比](figures/完整知识恢复对比.png)

![安全与教学效用](figures/安全与教学效用.png)
''')

fail=[]
for r in e1:
    if r['method']=='Arithmetic-Logical-Representation' and r['status']!='PASS':
        fail.append(f"### {r['item']} — {r['status']}\n\n来源资产 `{r['asset']}`，段落 `{r['source_locator']}`。\n\n原文：{r['text']}\n\n预测：{r['predicted_atoms']}\n\n作者标签：{r['gold_atoms']}\n\n未支持原因：{r['unresolved_relations']}\n")
save('c2rag_r9_failure_cases.md','''# R9失败、UNKNOWN与效用损失

全部EXPLORATORY，标签为作者开发标注，不冒称独立人类真值。所有失败保留，不改解析规则重跑。

## 真实文本表示失败

'''+ '\n'.join(fail)+'''
## 旧规则丢失单位与工况

Existing-RelationRules对两个冷态电阻文本提取裸值resistance=7/20，但没有cold状态和ohm单位，不能与完整类型原子等同；预测TP0、FP2。若按“出现数字即对”评分，会产生假阳性。

## 当前Conditional零恢复的退化

R8当前前端只支持特定For x=.../y=...格式，本轮源文本与有理/大数契约超出能力；20/20 E1单元UNKNOWN。E2跨Agent主比较8个候选全部UNKNOWN、全部拒答，正确0/8。0/4恢复不能作为文本泛化防御成功。没有强行把新知识塞入[-10,10]旧域，再把UNKNOWN风险1当成功推断。

## 未支持攻击不计失败

热冷公式的“first equation / other two”关系未可靠解析。unit_or_premise计划在全部8方法中均标UNSUPPORTED、恢复值为空；即使防御拒绝后只留下安全文本，也不把这个未解决目标记为安全测试成功。

## 替代策略的局限

知识局部回答平均覆盖54.2%的题目事实，但危险复合题完整正确0/4；保留的主要是公开/已见内容，新增私有目标事实0。固定提醒并非无意义字符串，却仍没有答出必要数值。较低恢复不等于完整教学效用保持，也未做到实际长度匹配。

## 单轮危险不是跨Agent协同收益

欧姆例的query已给2.50A，12V一个回复即可推出4.8Ω。这个资产的阻断不能归于两片段协同；真正互补的只有其余3个。不得把4/4对照恢复都讲成“每个片段单独安全”。

## 真实因果/过程覆盖不足

教材有温度、电阻、功率的瞬态共变文字，但本轮没有可靠因果模型或可评分的完整过程契约。公式/单位子契约结果不能代替因果知识保护。四材料不足以覆盖完整因果类别，未临时扩造大量样本。

## 操作失败

初次源文本检查发现bs4未安装，使用标准库处理而未下载依赖。首次Unicode减号输出触发Windows GBK显示错误，改用UTF8显示，未修改源HTML。这些不计作算法成败，记录见operational_failures.json。
''')

speech='''我们这轮把实验从自编函数移到四个已准备的OpenStax来源材料，覆盖两个仿射例、车灯电阻和热冷状态。公开教材只施加模拟授权策略，不代表它实际禁止教学引用。这不是独立盲测，也没有运行新的大模型生成。

先做真实文本提取。二十个原始句段和来源子片段中，冻结的有界类型前端十七个通过，两个部分失败，一个未知。失败集中在过程目标、温度电阻功率的共变，以及“第一个公式、另外两个公式”的指代。标签只有作者一名，所以不能把这些指标叫独立真值或泛化保证。

只有通过检查的数值子契约进入多轮实验。跨Agent主比较中，原始释放、静态配额、共享加性和旧槽位规则都完整恢复四个目标。共享内容历史加成熟闭包阻止了完整恢复，但正常事实只答对八题中的四题。独立内容历史在跨Agent场景仍恢复三个目标，说明共享内容历史有用。剩下欧姆例本来一个电压回答就能结合问题中的电流求出电阻，不能说它也是两片段协同。

当前Conditional前端则全部未知并全部拒答。它的零恢复不是理解成功。接上共同表示后，诊断路径和成熟闭包完全相同，没有新算法收益。

安全回答策略也没有消除冲突。原完整答复四题都对，也全部泄露。局部替代保留约百分之五十四的题目事实，但完整答对仍是零；而且主要重复公共或已见内容。我们没有用非空提醒冒充答对。

最终判断PIVOT：明确契约内的内容组合风险值得处理，成熟闭包已经足够解释当前收益。下一步先独立核验单位、工况、否定和指代的语义契约，不继续把共享历史或简单求解包装成新算法。'''
save('group_meeting_c2rag_r9.md',f'''# 2026-10-20组会：C²-RAG R9

**结论PIVOT：真实来源数值子契约能验证组合风险；当前Conditional前端不能直接泛化，成熟闭包仍足够。**

## 建议展示的数据

- E1：20个文本单元，类型前端17 PASS / 2 FAIL / 1 UNKNOWN；F1=92.8%，作者开发标注。仅12个原始文本单元时结果另列主报告，不能拿8个简单子片段代表全文。
- E2：跨Agent互补，预算/静态/加性/旧槽位恢复4/4；共享闭包0/4，正常答对4/8；独立内容历史恢复3/4。欧姆例是单轮危险，只有另外3个是互补协同。
- 当前Conditional：主场景8/8候选UNKNOWN、全拒答、答对0/8；不是泛化成功。
- E3：完整答复答对4/4且泄露4/4；局部替代覆盖54.2%题目事实、泄露0/4，但完整答对0/4，新增私有目标事实0。
- 计数：2本书、4来源页、4资产、20计划、160方法回合；方法回合不是独立样本。4资产均为已见资料的开发实验，独立盲测数0。模型推理/付费调用0。

![不同方法完整恢复](figures/完整知识恢复对比.png)

![安全与正常教学效用](figures/安全与教学效用.png)

## 不超过3分钟讲解词

{speech}

讲稿约{len(speech)}字符，按300–350字/分钟约{len(speech)/350:.1f}–{len(speech)/300:.1f}分钟；非录音实测。

## 追问时必须说明

1. 强表示前端是作者冻结的有限规则，成熟的是后端，不是通用文本提取器。
2. 无独立双人标注；因果、过程和指代未可靠覆盖。UNKNOWN没被改成PASS。
3. 算术闭包/共同合同Conditional诊断共用后端，输出相同是接口核验，不是新算法比赛。
4. 新算法候选0。唯一下一步是独立人工核验失败语义契约，规则修补前再冻结新的来源分组评估。
''')

font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False,'font.size':11,
 'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
figs=P/'figures';figs.mkdir(exist_ok=True)
labels={'B0-Raw-RAG-budgeted':'B0 预算原始释放','B1-StaticQuota':'B1 静态配额','B2-SharedAdditive':'B2 共享加性',
        'B3-SharedSet-RuleClosure':'B3 旧槽位规则','B4-Closure':'B4 共享算术/逻辑闭包',
        'B5-Conditional-Current':'B5 当前Conditional前端','Diagnostic-Conditional-Contract':'共同表示诊断（同后端）',
        'Ablation-Independent-Closure':'独立内容历史消融'}
fig,ax=plt.subplots(figsize=(12.5,6.7));yy=list(range(len(summary)))
colors=['#8d969d']*4+['#25658a','#c9cdd0','#477a93','#b67b57']
ax.barh(yy,[r['complete_n'] for r in summary],color=colors,height=.58)
ax.set_yticks(yy,[labels[r['method']] for r in summary]);ax.invert_yaxis();ax.set_xlim(0,5.3)
ax.set_xticks([0,1,2,3,4]);ax.set_xlabel('完整目标恢复数量（个资产；分母4，越低越好）')
ax.set_title('R9真实来源开发材料：跨Agent互补后的完整恢复',fontsize=16,pad=16)
for i,r in enumerate(summary):
    text=f"{r['complete_n']}/4；正常事实{r['correct_n']}/8"
    if r['method']=='B5-Conditional-Current':text='0/4；全拒答，8/8候选UNKNOWN'
    ax.text(r['complete_n']+.08,i,text,va='center',fontsize=9)
fig.text(.02,.047,'来源：e2_raw_results.json；2026-10-19；4资产、2教材，EXPLORATORY；仅数值子契约，非独立盲测。',fontsize=9)
fig.text(.02,.018,'欧姆例为单轮危险，其余3例为互补组合；当前前端的零恢复不能解释为语义防御成功。',fontsize=9)
fig.tight_layout(rect=[0,.09,1,1]);fig.savefig(figs/'完整知识恢复对比.png',dpi=185);fig.savefig(figs/'完整知识恢复对比.svg');plt.close(fig)

fig,ax=plt.subplots(figsize=(11.8,6.4));xx=list(range(4));width=.23
ax.bar([x-width for x in xx],[r['correct_n']/4*100 for r in s3],width,label='完整答题正确率（4题）',color='#25658a')
ax.bar(xx,[r['coverage']*100 for r in s3],width,label='题目相关事实覆盖（作者标签）',color='#92aab7')
ax.bar([x+width for x in xx],[r['complete_n']/4*100 for r in s3],width,label='完整知识恢复率（越低越好）',color='#b67b57')
ax.set_xticks(xx,['原始完整答复','简单拒答','固定教学提醒','知识感知局部替代'])
ax.set_ylim(0,118);ax.set_yticks([0,25,50,75,100],['0%','25%','50%','75%','100%']);ax.set_ylabel('观测比例（%）')
ax.set_xlabel('同一冻结危险问题及前置历史；每种策略4个资产问题')
ax.set_title('安全—教学效用：部分事实覆盖不能替代完整答对',fontsize=16,pad=16)
for i,r in enumerate(s3):
    ax.text(i,r['coverage']*100+2,f"覆盖{r['coverage']*100:.1f}%",ha='center',fontsize=10)
ax.legend(loc='upper right',fontsize=9)
fig.text(.02,.075,'局部替代主要保留公共/已见事实，完整答对仍0/4；没有解决完整正确答案必然泄露的契约冲突。',fontsize=10)
fig.text(.02,.043,'平均回复Token：完整22.75，拒答0，固定10，局部20.25；实际长度未完全匹配，不主张长度无关优势。',fontsize=9)
fig.text(.02,.015,'来源：e3_raw_results.json；2026-10-19；EXPLORATORY，作者开发标注，无新LLM生成。',fontsize=9)
fig.tight_layout(rect=[0,.13,1,1]);fig.savefig(figs/'安全与教学效用.png',dpi=185);fig.savefig(figs/'安全与教学效用.svg');plt.close(fig)

save('README.md','''# C²-RAG R9实测交付

决策 **PIVOT**。4个真实来源关联开发资产，非独立盲测。已执行E1、通过门槛的E2/E3；没有新LLM推理、付费调用或大模型下载。

- [完整报告](c2rag_r9_real_text_report.md)
- [组会稿及3分钟以内讲解词](group_meeting_c2rag_r9.md)
- [失败与UNKNOWN](c2rag_r9_failure_cases.md)
- [关系提取CSV](c2rag_r9_relation_extraction.csv)
- [多Agent重构CSV](c2rag_r9_multiagent_reconstruction.csv)
- [安全效用CSV](c2rag_r9_safety_utility.csv)
- [协议](protocol.json)、[数据分组](data_groups.json)、[来源](source_registry.json)、[许可](LICENSE_SOURCE_MATERIAL.md)、[验证](validation.json)

运行顺序：prepare_and_freeze.py → run.py e1 → 检查e1_to_e2_gate.json → run.py e23 → validate.py → build_reports.py。已有输出拒绝覆盖。原始JSON给全部候选、实际交付、Token IDs、风险/UNKNOWN和攻击约束，不拿无效攻击当防御成功。

源HTML使用项目既有本地快照；发布其哈希、真实段落ID与必要文本，不重传全部HTML。依赖Qwen tokenizer但不加载模型权重；SymPy仅核验求解后端。所有数据选择/规则/候选均在首次E1执行前冻结，未因结果调规则或扩样本。
''')
save('report_summary.json',json.dumps({'e2_cross_agent':summary,'e3':s3,'speech_characters':len(speech),
    'decision':'PIVOT','candidates_for_new_algorithm':0},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'reports':3,'csvs':3,'figures':2,'speech_characters':len(speech),'decision':'PIVOT'},ensure_ascii=False))
