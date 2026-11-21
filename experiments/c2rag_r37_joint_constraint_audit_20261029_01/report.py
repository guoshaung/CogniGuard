"""Record mathematical reductions and bounded retrospective findings."""
from experiments.c2rag_r37_joint_constraint_audit_20261029_01.common import (
    SOURCE, frozen, read, sha, write,
)


def main():
    frozen()
    assert read('VERIFICATION.json')['status'] == 'PASS'
    write('MATHEMATICAL_MODEL.md', r'''# 新旧问题的最小数学模型与标准约化

EXPLORATORY；下面是本轮对有限模型的明确推导，不是新的防御算法，也不是自然语言知识推断定理。

## 1. 状态、动作、授权与效用

有限知识原子集F，公开背景P和正Horn规则集R。第t轮请求q_t面向持久接收者r_t；正确候选集合A(q_t,r_t)与空答由契约给定。一个动作必须是(t,r_t,a)，含实际文本reply(a)、透露事实D(a)、字节c(a)、正常效用u_t(a)。不能把同名字段脱离资产/时刻/接收者直接合并。

V_i(t)=V_i(0)∪⋃_{s≤t,r_s=i}D(a_s)，联盟C的可见知识K_C(t)=Cl_R(P∪⋃_{i∈C}V_i(t))。每个保护目标z有允许完整恢复的联盟集合Auth_z。风险是存在非空C、|C|≤3、C∉Auth_z且z∈K_C(t)。任一未授权目标恢复即违规，不能把多个目标拼成大目标稀释风险。

约束：每请求至多一个非空候选，候选须对该接收者合法；共同字节/请求等预算；所有前缀无风险。目标max Σ_t u_t(a_t)。本批正确回答1、空答0，预算非绑定、知识不遗忘、权限固定、恢复单调，因此最终安全蕴含所有前缀安全。负知识、策略变化、拒答侧信道及外部知识不在该结论内；不能直接扩展到任意语义风险。

## 2. R32：二类多数的严格特例

仅两类单原子回答a、b，二者联合即恢复目标；所有实际接收者对目标无权且任意≤2人可观察合并。任何发布a和b的计划都会被一个≤2联盟收齐，所以只能选择一类。预算不绑定/每题效用1时，OPT=max(n_a,n_b)。重复回答增加任务效用、不增加不同知识。

R32的102个旧证书全满足该式；其17资产复用同样需求模式，不是102独立结构。A2在这些已测序列=OPT，不能推出一般rollout最优；R34已存在A2-Oracle<Simple-Oracle。

## 3. 超出多数不等于超出标准优化

对每一有限合法动作建立二进制x_{t,a}。收集在给定接收者/授权下的最小不安全动作集E；安全条件Σ_{v∈e}x_v≤|e|−1，对每个e∈E成立；另加同请求Σ_a x_{t,a}≤1及预算Σc_v x_v≤B。目标Σu_v x_v。

- 禁集全二元：动作冲突图的最大权独立集；同请求冲突也是二元边。
- 存在三元以上禁集：弱超图独立集/超图顶点覆盖的补问题；“弱”是禁止选齐整条边，不能错写成每边至多选一个的强独立集。
- 只有加性费用：背包特例；冲突+费用为带背包约束的独立集/标准0-1整数规划。
- 仅要求资源不能被不同动作重复占用的冲突可写集合打包；一般三元禁集允许选其中两项，不能直接拿普通“集合互不相交”替代。

这些是显式等价编码，不意味着求解多项式。一般情形包含任意图独立集；k=1也可包含这种困难，故不能把困难首次归因于三Agent。最小危险集的显式枚举本身可能指数级。

## 4. 不必展开所有危险集的成熟MILP表示

对每个C（|C|≤3）和事实f设二进制z_{C,f}。若动作v把f交给C中成员，则z_{C,f}≥x_v；已知事实/公开事实设为1。每条规则B→h加z_{C,h}≥Σ_{f∈B}z_{C,f}−|B|+1；对该C未获授权的目标强制z_{C,target}=0。

最小闭包可作为z的赋值，因此实际安全计划必有可行赋值；反向下界强制所有实际可导事实为1，因此可行赋值不可能隐藏真实恢复。故在固定正Horn/授权模型内是精确的存在性编码，不需要将未提及事实视为假。它不是新算法；可用成熟MILP/SAT/约束规划。

设m=|F|，L为规则/体文字规模，A为动作规模，联盟数K=Σ_{j=1}^3 C(n,j)=O(n³)。该编码用O(A+Km)变量和多项式规则/动作关联约束；求解仍可能指数级。正Horn以外、不可计算语义或不可靠抽取不能凭此编码声称解决。R35已实际用更简单的直接最小支持MILP并经独立穷举认证。

## 5. ExactK3究竟做了什么

冻结实现Compiled将已知事实映射bitset，建立正规则、≤3联盟、逐目标授权mask和每名接收者受影响联盟索引。Exact.trial复制状态，只更新包含本次接收者的联盟闭包，命中已有种子时用纯缓存。n人每次单接收者变化只涉及Σ_{j=0}² C(n−1,j)=O(n²)联盟，而非重算全部O(n³)联盟。

这是**给定表示/已交付历史下的精确风险门**，不是最优释放调度器、自然语言解析器或任意Agent攻击保证。闭包、bitset、索引和缓存均为已有机制，Exact名称不能升级为全系统语义精确。

本轮核查的源码为R35/snapshot/engines.py:10(Compiled)、:47(Exact)、:55(Exact.trial)，独立set定义在snapshot/reference.py:5(closure)、:23(reconstruct)、:32(unsafe)；精确行号另见SOURCE_LOCATORS.json。R32归档不分发原worker源码，本轮核查其原始trials/报告公式及同源Exact快照，不声称重跑或完整审计了未分发的原worker实现。

## 6. 固定菜单仍充分的条件

这里严格限于旧R34/R35的统一学生域：实际无权接收者集合U至多3人，U的每个非空子集对所有目标均无权；完整授权接收者不属于任何需要检查的未授权联盟。学生候选/效用只依题型而与U内身份无关，预算非绑定、风险单调。任取最优安全计划在U内的实际交付并集V（不包括完整授权者的交付）；U本身也无权，故Cl(V)对所有目标安全。每题型任选该计划给U成员用过的一个正确候选，回答该类全部学生请求，其知识仍是V子集、任务完成不减。因此存在最优固定菜单。完整授权者按既有权限类自由回答，不能故意用角色无关菜单削弱基线。

R34/R35恰好满足以上条件。这一证明可容纳任意已知正向重叠禁集，不限两类多数。它不是“每个目标各有某个覆盖联盟即可”的一般权限定理，也未证明任意角色相关候选下菜单充分。缺单联盟覆盖仅使此证明失效，不自动证明菜单有差距。

## 7. 贪心、次模性与未来信息

风险指示g(S)=1[目标可恢复]一般非次模：规则ab→目标，S=∅⊂T={a}，加入b的风险增量从0变为1，违反边际递减。安全集合虽向下封闭，却一般不是matroid：旧L2的ab/ac禁集使A={a}、B={b,c}都安全且|A|<|B|，B中任何元素都不能增广A。这只能排除通用matroid贪心保证，不排除其他近似保证或特殊图算法。

真实最优未来机会成本应是W*(V,未来)−W*(V∪D(a),未来)，不是独立单题可答性损失之和。计算W*本身已是标准组合优化；把它替代A1代理损失不构成自动创新。

若未来未知，状态为实际历史h，策略只能依h/可用预测包；同一可见历史的情景必须同决策。适当小问题参照是Bellman/情景树非预知优化。对最大化有sup_π E[U_π]≤E[OPT(完整未来)]；右侧多出的未来信息不能归功于算法。逐情景后续各自全知的B打分是信息松弛，不必等于其实际在线策略价值。
''')
    write('MINIMAL_JOINT_CASE.md', '''# 一个可手算的联合案例与三人边界

来源：**复用R35 L3，SYNTHETIC、作者机制设计、已见开发语言；不是新资产或真实课堂请求。** 未改任何身份/权限/数值/候选。完整契约与原始回复见MINIMAL_JOINT_SAVED_PLANS.json。

## 重叠二元/三元，4个知识单元

公开规则为a∧b→TARGET、b∧c∧d→TARGET；其余世界均允许。实际r0/r1/r2均未获TARGET权限，r3获权但不接请求。四题均允许回答对应单个观察或空答，每题正确1分。顺序与收件人为：

1. 向r0问b；规范回复报告b。
2. 向r1问a；规范回复报告a。
3. 向r2问c；规范回复报告c。
4. 向同一r0问d；规范回复报告d。

每条规范回复31 UTF8字节，共同预算124，非绑定。标准答案、权限与公开规则相同。

手算：4题全答必危险。若答b，不能答a，且c/d至多答一个，所以最多2分；若拒b，a/c/d全部安全，得3分。因此OPT=3，唯一最优交付mask=1110（按位t0为最低位，整数14），实际93字节。即时贪心交付b、c，拒a、d，2分/62字节。菜单“a答/b空/c答/d答”同样3分，不需要新规划算法。

这不是二元冲突图：b/c、b/d、c/d分别都安全，但b/c/d联合不安全；任何仅用原事实二元边的图若保留这些对，就无法禁止三元组。它是最小的“二元边和三元边重叠但不互相包含”例（至少4个顶点），不是所有教学联合结构的最小例。32个世界独立判别、16观察子集和256旧请求流的4096计划核验保留，未只取这个贪心失败案例作统计。

**实际线上记录不能冒充Oracle：** 旧uniform/error0的Simple、A2、B-SAA、MenuRecourse在这一已见流都答2题，与G相同。3分是完整未来的离线值/最优菜单存在性，不是这些在线方法实际达到3。NoGate/Counter答4但违规。

## 真正三人恢复前缀，并无新增规划机制

另一个旧流L3-1230按b、c、d、a请求，接收者仍为r0、r1、r2、r0。NoGate前三步分别交b、c、d：单人和任意双人的并集都不含ab或bcd，三人并集包含bcd，故k_min=3。删去任一必要动作即不能恢复。独立反世界可令缺失观察为假、TARGET为假。

PairExact若只看这同一状态的≤2联盟会漏判；ExactK3会阻止第三份。这里是在原实际字节上比较风险范围，不是新跑一个权限不同/预算不同的控制器。第四步r0又收到a后会单人收齐ab，因此“三人最小”只针对第三步前缀，不能写成最终始终需要三人。

三人让安全判据需要覆盖真正三元组合；但三名实际无权接收者本身构成一个允许观察的k=3联盟，故整体安全等价于其全局并集安全。相同约束也能交给一个观察者研究：并未出现双人模型不可表达的新优化问题或新的算法难度类别。真实多主体/Agent作用不能由这一个合成前缀推得。
''')
    write('RELATED_METHODS.md', '''# 成熟方法撞车与来源核查

本轮只查三个直接近邻，一手论文/官方文档，不进行泛泛综述；2026-10-29读取，未下载新教学数据/模型。

1. [Biskup & Weibert, Confidentiality Policies for Controlled Query Evaluation, DBSEC 2007](https://dl.ifip.org/db/conf/dbsec/dbsec2007/BiskupW07.pdf)，第1—2页：保留过去query/answer日志，在交付前检查新答案与既有知识是否推出受限信息，可拒绝/修改回答。故“共享内容历史、组合推断、按秘密策略阻断”本身不是C²新算法。该文不自动覆盖当前全部多Agent效用模型；需逐假设比较。
2. [Shapiro, Stochastic Programming Approach to Optimization under Uncertainty, 2006](https://optimization-online.org/wp-content/uploads/2006/01/1323.pdf)，§2情景近似，§5（PDF第14—15页）可实施策略/动态规划，§6情景树：未来不应在尚未观察时决定当前策略，B的逐场景最优续期与真正可实施策略价值应区分。SAA、情景树、Bellman本身均成熟，拼接进泄露门不自动是贡献。
3. [SciPy milp官方文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html)：标准线性目标、线性约束、整数变量与求解状态。R35用本地已装HiGHS接口，并已有1374个子问题的独立穷举证书；本轮没有重新求解它们。把重叠禁集写成Σz≤|e|−1只是标准整数建模。

图/弱超图独立集、背包及集合打包的具体约化由MATHEMATICAL_MODEL.md给出可检验编码，未依赖二手博客。不得将“弱超图禁止选齐边”误引为“强独立集每边至多一项”。复杂性不等于论文贡献；成熟算法是否够用需同信息、同约束、同成本评价，不能仅因存在NP难特例宣称CCF-B空间。

其他链接检查：Oxford CQE页面返回403，未据其不可读全文扩充结论；搜索结果的2026强超图独立集文献定义不同，没有拿来支撑当前弱超图模型。上述三项足以排除当前候选的直接独立贡献，不是穷尽查新或不可能性证明。
''')
    write('RESULT.md', '''# R37 联合释放约束与长期优化价值审查

**决策PIVOT：超出二类多数的联合风险确实存在，但当前证据仍被固定菜单、标准0-1优化及非预知动态规划解释；不支持继续实现一个新的前瞻释放算法。** 没有通过新性能实验的前置门槛，此轮只复核旧证据和有限数学证书。所有数值标REUSED，不能算新增独立实验。

## R32完整原始核查

固定research-sync接续3615483a9ac0dc0fc07853278371d5a83a0dc599。重读完整REPORT/PROTOCOL/REPRODUCE及失败记录，报告/协议/决定与固定远端一致；完整归档Git blob一致。本轮按实际公开文本重新核对510旧轨迹、3060步、每步接收者视图、效用、字节与≤3联盟；0分歧。102个旧OPT证书均满足多数闭式解；原13,872个日程是旧执行数，不冒充本轮新算法运行。

原计分仍为G340，A1-U136，A1-O357，A2-O=OPT442（各612请求）。kinetic-N8-S1首轮v，未来v4/m3；当前发v前后的联合未来最优都是4，真实机会成本0，而A1代理损失3、分数−2。它最后只答2，G/A2/OPT答5。完美预测也未修复代理目标误计。A2本批达到OPT不能作一般保证；R34其Oracle246已低于Simple-Oracle/OPT252。

## 合法来源与结构代表性

既有实源12题确有二元/三元重叠和两种正确功法，但请求拆分、收件人、隐藏原题与授权是作者模拟；T05—T08还是同一个包裹，不是4个独立来源资产。完整公开原题可见时目标可计算。R36已冻结审计194文件，未取得真实持续接收者与签发授权/候选可用性完整合同。本轮复用该负面审计，不从同一语料再捏角色。

R34六实例/36流Simple-Oracle=OPT252/288，已有全局并集→固定菜单证明；S03/S06同构、有限域捷径、最终三人见证不足等失败全部保留。R35五个命题契约、690流，B与逐情景菜单10093候选得分/动作一致，1374旧MILP子问题已有独立认证。这些是作者机制案例，不能代表真实教学需求分布。

## 最小案例与实际旧数据重计

固定复用L3的ab或bcd恢复目标；按b,a,c,d请求，G2，手算OPT3；最优固定菜单也3，见MINIMAL_JOINT_CASE.md。三元禁集确实不能仅用原事实二元冲突边表达，却是普通弱超图独立集/整数规划。没有证据证明一个新优化器优于这些强基线。

不只展示该流：独立重计L3/uniform/error0全部256旧流（一个资产，每方法1024请求）：

- NoGate、Counter4：正确1024，拒0，输出31744字节，146/256流完整恢复。
- G-Shared、Simple：正确836，拒188，25916字节，0/256流完整恢复。
- A2、B-SAA、MenuRecourse：正确832，拒192，25792字节，0/256流完整恢复。
- 完整未来Offline：872；与所有256旧Oracle逐流一致（4096计划复核）。最优菜单的872是由既有充分性证明推出，不是新运行一个Simple-Oracle。

因此G到Offline有36分空间，但同信息A2/B比简单方法少4；B与MenuRecourse完全相同。Counter4预算非绑定而等于NoGate，不代表所有预算方法必无效；减少预算必须对全部方法公平改变，而本轮未这样做。完整恢复只限结构化TARGET，UNKNOWN0不表示自然语言抽取无未知。

## 信息价值与算法贡献不能混淆

L3/uniform原正确分布下，非预知最优DP与G均为3.265625/4，Offline3.40625；即836与872的36分并非此iid观察信息下可实现算法增益。按具体流知道后缀选菜单3分的存在性也不表示在线能先知。

R35 L4/uniform原反例：B精确分布打分201/64，实际99/32，正确分布非预知最优199/64。差异来自情景后续全知的信息松弛/策略失误，并非预测器训练不足。其他9/10分布格该B实际达到DP也保留，不能只取反例。未来Oracle、正确分布、32条预测情景是不同信息条件。

## 三Agent是否带来独立算法问题

原L3-1230的NoGate前三步b/c/d分给r0/r1/r2，任意两人不能恢复、三人可以；本轮用Boolean反模型核验。第四步同一r0再获a会变单人ab，故仅称三人前缀。只查两人的门确会遗漏第三份，但在三名实际无权接收者都可联合且k=3时，全局并集已覆盖风险。它改变必须检查的知识阶数，不证明比单视图超图优化更难，更不能用身份/账本分片充当贡献。

## 研究取舍

不训练预测器，不实现新控制器，不改变Stage1-C、不重跑正式实验，也不扩SYNTHETIC样本。当前可支撑“风险模型/评测审查”的负面证据，尚不足支撑CCF-B算法贡献；不能保证论文档次或认定不存在未来贡献。

下一轮唯一研究问题：**能否取得一份来源可核验的既有教学任务，其实际授权与正确答案可用性产生互不覆盖的接收视图，并在相同信息下严格超出角色感知强固定菜单？** 先要任务/授权证据，不通过更换身份、强行删候选或刷种子造差距。缺此材料时保持停止，不自动开启下一轮。
''')
    write('FAILURES.md', '''# 全部负面证据与边界

- 未发现满足代表性及独立算法缺口的新增任务；新性能实验未启动，不填新算法增益0，记NOT_TESTED。
- 旧R32 A1完美信息仍失误；34条退步、17条进步、51条同分，未仅挑增益。R32报告曾把6设定误称6结构，实际5模式；原修正及失败清单保留于归档。
- R34存在工程attempt01失败，02仅修无效菜单前缀循环；未更改冻结数据。两离散域捷径和同构留出不作未见验证。
- 旧R35 L3：所有256流都重计，A2/B总分少于G/Simple；没有隐藏最小例中所有线上方法均2分的事实。最优3分是全未来参照/数学存在性。
- 三人风险前缀不是最终三人风险，更不是3个Agent提供独立规划贡献的证据。未改变身份分配，未运行真实Agent/LLM攻击。
- 风险表示、实际收件历史和授权均给定；没有验证自然语言解析、隐藏前提、噪声、拒答/长度侧信道或开放知识来源关联。未知语义不按安全处理。
- 关系与权限由同一研究助手编写/复核，没有两名独立人类标注。独立Boolean/集合计算不是独立人工真值。旧样本都已见，未冒称盲测。
- 协议有一处“CPU不发生”的文字错误，在audit入口先保存PROTOCOL_CLARIFICATION并保留原协议/hash；实际CPU核验约6秒，600秒上限未变，没有改数据/评分/门槛。无主核验异常。
- 首次文件检索范围过广导致输出截断，改为目录级定位；一次只读Get-Content误指不存在的common.py，未写文件。Oxford来源403及web find超时未用作依据。保留本记录，无隐匿研究失败或自动重试研究运行。

本轮没有新防御、模型、付费调用、GPU、预测训练或教育数据下载；只读取既有证据和查重论文。所有历史源在核验前后hash一致。
''')
    write('decision.json', {'round':'R37','decision':'PIVOT','EXPLORATORY':True,
                          'new_performance_experiment_gate_passed':False,
                          'reason':'joint constraints exist but old strong menu, hypergraph/IP and causal DP explain them; real task/authorization evidence missing',
                          'new_algorithm_candidate':None,'new_algorithm_runs':0,'new_assets':0,
                          'new_algorithm_gain':None,'new_algorithm_gain_status':'NOT_TESTED_GATE_NOT_PASSED',
                          'R32_saved_totals_reverified':{'G':340,'A1-U':136,'A1-O':357,'A2-O':442,'OPT':442},
                          'L3_reused_independent_assets':1,'L3_reused_streams':256,
                          'L3_old_G_and_Simple':836,'L3_old_A2_B_and_MenuRecourse':832,
                          'L3_complete_future_OPT':872,'L3_optimal_static_menu_by_proof':872,
                          'L3_true_distribution_nonanticipative_DP_old_value':836,
                          'genuine_three_recipient_prefix':True,'three_agents_independent_optimization_contribution':False,
                          'real_teaching_representativeness_established':False,
                          'model_calls':0,'paid_API_calls':0,'training':False,'Stage1_C_changed':False,
                          'CCF_B_algorithm_contribution_supported':False,
                          'next_unique_question':'one source-backed existing task whose actual role grants and correct-answer availability yield noncovering recipient views and a strict gap against role-aware strong menus under identical information',
                          'stop_after_delivery':True})
    # Reproducible source navigation without copying production/source snapshot code.
    from experiments.c2rag_r37_joint_constraint_audit_20261029_01.common import R35, PROJECT_ROOT
    locations = []
    for path, markers in [(R35/'snapshot/engines.py',['class Compiled:', 'class Exact:', 'def trial(self,add):']),
                          (R35/'snapshot/reference.py',['def closure(', 'def reconstruct(', 'def unsafe(']),
                          (PROJECT_ROOT/'experiments/c2rag_r34_20261028_02/planner.py',['def choose(', 'def best_static_menu(']),
                          (PROJECT_ROOT/'experiments/c2rag_r35_20261029_01/core.py',['def exact(', 'def dp('])]:
        lines = path.read_text(encoding='utf8').splitlines()
        for marker in markers:
            locations.append({'path':path.relative_to(PROJECT_ROOT).as_posix(),'marker':marker,
                              'lines':[i for i,line in enumerate(lines,1) if marker in line],
                              'sha256':sha(path.read_bytes())})
    write('SOURCE_LOCATORS.json',locations)
    write('REPRODUCE.md', '''# 执行和复核

本轮是回顾审查，不是新未见性能试验。输出写入exclusive-create，不能对旧目录重跑。

```powershell
.venv-langgraph/Scripts/python.exe -m experiments.c2rag_r37_joint_constraint_audit_20261029_01.prepare
.venv-langgraph/Scripts/python.exe -m experiments.c2rag_r37_joint_constraint_audit_20261029_01.audit
.venv-langgraph/Scripts/python.exe -m experiments.c2rag_r37_joint_constraint_audit_20261029_01.report
.venv-langgraph/Scripts/python.exe -m experiments.c2rag_r37_joint_constraint_audit_20261029_01.postcheck
```

已有audit独立检查510个原R32交付轨迹、102多数证书；L3的32个Boolean赋值、16观察子集、256流4096个计划，以及1792个旧方法回放。所有主算法运行数0；对旧计划的独立枚举是核验，不是追加算法数据。实际执行时间在VERIFICATION.json，预算600秒。

最终report源码已含行号和证明范围修正；初稿备份记录本次审稿历史，不要求最终脚本重新制造相同笔误。复现目标是评分/数学证书一致，不是重造过去措辞错误；需核对报告中的充分条件明确只针对R34/R35统一无权学生域，V不包括完整授权者交付。归档同时保留修正前文字和说明。

报告包含人工数学证明；无独立人类审稿/双标。代码使用标准库，无旧控制器/评分器导入，风险按实际字节和公开规则重建。复现需获准访问freeze.json中的旧文件；发布只含新审计定义、结果/少量原合成案例摘录及来源哈希，未上传生产代码或真实教师/学生原文。
''')
    write('CODE_VERSION.json', {'scripts':{p.name:sha(p.read_bytes()) for p in SOURCE.glob('*.py')},
                                'scripts_are_audit_only':True,'production_edits':False})
    frozen()
    print('Wrote mathematical model, minimal certificates, source collision review and PIVOT decision.')


if __name__ == '__main__':
    main()
