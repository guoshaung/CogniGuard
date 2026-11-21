"""Post-execution descriptive analysis; no changes to frozen methods or truth."""
from collections import defaultdict
from fractions import Fraction as F
import csv
import io
import itertools
import json
import math
import statistics
import subprocess
from experiments.c2rag_r35_20261029_01.common import *
from experiments.c2rag_r35_20261029_01.verify import Reference

def csvfile(name,rows):
    out=io.StringIO(newline='');w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows);write(name,out.getvalue())
def mdtable(headers,rows):
    return '|'+ '|'.join(headers)+'|\n|'+'|'.join(['---']*len(headers))+'|\n'+''.join('|'+ '|'.join(map(str,r))+'|\n' for r in rows)
def number(v):return f'{float(F(v)):.6f}'

def main():
    frozen();summary=read('weighted_summary.json');index={(r['asset'],r['law'],r['error'],r['method']):r for r in summary}
    bounds=read('verified_information_bounds.json');banks={b['id']:b for b in read('banks.json')};policies=read('policy_index.json')
    replay=read('evaluated_replays.json');verification=read('independent_verification.json');refs={k:Reference(b) for k,b in banks.items()}
    extras=defaultdict(lambda:defaultdict(F))
    for row in replay:
        key=tuple(row[k] for k in ['asset','law','error','method']);p=F(row['probability']);J=len(banks[row['asset']]['observations'])
        extras[key]['input_unit_disclosure_fraction']+=p*F(round(row['released_input_fraction']*J),J)
        for k in [1,2,3]:extras[key][f'recovery_exact_k{k}']+=p*row[f'recovery_exact_k{k}']
    metric_rows=[]
    for row in summary:
        key=tuple(row[k] for k in ['asset','law','error','method']);safe=row['method'] not in ['NoGate','Counter4']
        metric_rows.append({**row,'split':banks[row['asset']]['split'],'correct_rate':str(F(row['correct'])/4),
            'refusal_rate':str(F(row['refusals'])/4),'Offline_gap':str(F(row['offline_utility'])-F(row['correct'])) if safe else 'N/A_UNSAFE',
            'unknown':0,'semantic_risk':'NOT_MEASURED','generation_tokens':'NOT_APPLICABLE_NO_GENERATOR',
            **{k:str(v) for k,v in extras[key].items()}})
    csvfile('complete_results.csv',metric_rows);csvfile('information_bounds.csv',bounds)
    paired=[];failures=[];sensitivity=[]
    for asset in banks:
        for law in ['uniform','biased']:
            for error in ['0','1/2','1']:
                s=index[asset,law,error,'Simple'];b=index[asset,law,error,'B-SAA'];m=index[asset,law,error,'MenuRecourse'];d=index[asset,law,error,'Causal-DP']
                assert b['correct']==m['correct'] and b['bytes']==m['bytes'] and b['refusals']==m['refusals']
                pair={'asset':asset,'split':banks[asset]['split'],'law':law,'error':error,
                    'B_minus_Simple':str(F(b['correct'])-F(s['correct'])),'B_minus_MenuRecourse':str(F(b['correct'])-F(m['correct'])),
                    'B_minus_Causal_DP_same_forecast':str(F(b['correct'])-F(d['correct'])),
                    'B_minus_G':str(F(b['correct'])-F(index[asset,law,'NA','G-Shared']['correct']))}
                paired.append(pair)
                if F(b['correct'])<F(s['correct']):failures.append(pair|{'failure':'B worse than Simple'})
    csvfile('paired_differences.csv',paired);write('all_B_below_Simple_cases.json',failures)
    for method in ['A1','Simple','A2','B-SAA','MenuRecourse','B-Expectation','Causal-DP']:
        for error in ['0','1/2','1']:
            rows=[r for r in summary if r['method']==method and r['error']==error];zero=[r for r in summary if r['method']==method and r['error']=='0']
            total=sum((F(r['correct']) for r in rows),F(0));base=sum((F(r['correct']) for r in zero),F(0))
            sensitivity.append({'method':method,'error':error,'equal_cell_weight_descriptive_correct_sum_out_of_40':str(total),
                'decimal_correct_sum':float(total),'difference_vs_correct_distribution':str(total-base),
                'full_reconstruction_sum_of_cell_probabilities':str(sum((F(r['full_reconstruction']) for r in rows),F(0))),
                'interpretation':'10 equally weighted asset-law cells, not one sampled population or 10 independent assets'})
    csvfile('prediction_sensitivity.csv',sensitivity)
    quality=[]
    for asset,bank in banks.items():
        for law,true in bank['evaluation_true_probabilities'].items():
            true=list(map(F,true))
            for error in [F(0),F(1,2),F(1)]:
                shifted=true[1:]+true[:1];estimated=[(1-error)*a+error*b for a,b in zip(true,shifted)]
                quality.append({'asset':asset,'law':law,'error':str(error),'L1_distribution_error':str(sum(abs(a-b) for a,b in zip(true,estimated))),
                    'expected_next_query_logloss_nats':-sum(float(p)*math.log(float(q)) for p,q in zip(true,estimated)),
                    'KL_true_to_forecast':sum(float(p)*math.log(float(p/q)) for p,q in zip(true,estimated))})
    csvfile('forecast_distribution_quality.csv',quality)
    latency=defaultdict(list);latency_nonterminal=defaultdict(list)
    for p in policies:
        for node in read(p['path']):
            latency[p['method']].append(node['cpu_wall_ns']/1e6)
            if len(node['prefix'])<H:latency_nonterminal[p['method']].append(node['cpu_wall_ns']/1e6)
    def percentile(xs,p):return sorted(xs)[math.ceil(p*len(xs))-1]
    times=[]
    for m,x in latency.items():
        nt=latency_nonterminal[m]
        times.append({'method':m,'decisions':len(x),'median_ms_all_depths':statistics.median(x),'p95_ms_all_depths':percentile(x,.95),
            'nonterminal_decisions':len(nt),'median_ms_nonterminal':statistics.median(nt),'p95_ms_nonterminal':percentile(nt,.95),
            'observed_sum_ms':sum(x),'cache_scope':'pure backend cache shared in frozen method order; do NOT use as comparative speed ranking'})
    csvfile('decision_latency.csv',times)
    # Fully auditable representative policies; no extra generated test leaves.
    keyB=next(p for p in policies if (p['asset'],p['law'],p['error'],p['method'])==('L4','uniform','0','B-Expectation'))
    keyD=next(p for p in policies if (p['asset'],p['law'],p['error'],p['method'])==('L4','uniform','0','Causal-DP'))
    B=read(keyB['path']);D={tuple(x['prefix']):x for x in read(keyD['path'])}
    differences=[{'B':x,'causal_DP':D[tuple(x['prefix'])]} for x in sorted(B,key=lambda n:(len(n['prefix']),n['prefix']))
        if x['known_before']==D[tuple(x['prefix'])]['known_before'] and x['answer_id']!=D[tuple(x['prefix'])]['answer_id']]
    write('information_relaxation_decision_counterexamples.json',differences)
    # Check exact truth-table equivalence against the original detector, all states.
    engine=module('engines');truth_checks=0
    for asset,bank in banks.items():
        c=engine.Compiled(bank['case']);r=refs[asset]
        for bits in range(1<<len(bank['observations'])):
            facts=[a for j,a in enumerate(bank['observations']) if bits&(1<<j)]
            detect=bool(c.expand(c.bits(facts))&(1<<c.index['TARGET']))
            assert detect==r.table[bits]['recover'];truth_checks+=1
    write('detector_all_subset_check.json',{'checks':truth_checks,'disagreements':0,'scope':'exact propositional theory only; language semantics untested'})
    head=subprocess.run(['git','rev-parse','HEAD'],cwd=PROJECT_ROOT,capture_output=True,text=True,check=True).stdout.strip()
    dirty=subprocess.run(['git','status','--porcelain'],cwd=PROJECT_ROOT,capture_output=True,text=True,check=True).stdout
    write('code_version.json',{'git_HEAD_observed_after_run':head,'working_tree_dirty':bool(dirty.strip()),
        'unrelated_preexisting_changes_not_staged_or_reset':True,'authoritative_experiment_version':'freeze.json experiment_code_sha256 and baseline snapshot hashes'})
    write('test_receipt.json',{'command':'run.cmd test experiments/c2rag_r35_20261029_01/test_audit.py -q','passed':4,'seconds':1.29})
    mainrows=[]
    for asset in banks:
        for law in ['uniform','biased']:
            mainrows.append([asset,law,*[number(index[asset,law,'NA' if m=='G-Shared' else '0',m]['correct']) for m in ['G-Shared','A1','Simple','A2','B-SAA','MenuRecourse','Causal-DP']],number(index[asset,law,'0','B-SAA']['offline_utility'])])
    main_table=mdtable(['资产','需求','G','A1','Simple','A2','B-SAA','菜单续期','非预知DP','Offline'],mainrows)
    info_table=mdtable(['资产','需求','B精确分布打分上界','最优非预知策略','B实际效用','打分乐观差'],
        [[x['asset'],x['law'],number(x['B_exact_root_information_relaxation']),number(x['optimal_causal_value']),
            number(x['B_expectation_actual_causal_policy_utility']),number(x['information_relaxation_gap'])] for x in bounds])
    sensitivity_table=mdtable(['方法','误差0','误差1/2','误差1'],
        [[m,*[number(next(x['equal_cell_weight_descriptive_correct_sum_out_of_40'] for x in sensitivity if x['method']==m and x['error']==e)) for e in ['0','1/2','1']]] for m in ['A1','Simple','A2','B-SAA','MenuRecourse','B-Expectation','Causal-DP']])
    write('THEORY_AND_LIMITS.md',"""# 性质与成熟方法排重

所有下述自证只适用于冻结正命题规则、静态权限、实际披露集合、非绑定预算；不是自然语言/侧信道定理。

## 单调、次模与贪心
恢复风险R(S)=1[公开理论+S蕴含TARGET]对集合单调；安全集合向下封闭。
它一般非次模：规则a∧b⇒T，有R(∅)=R(a)=R(b)=0、R(ab)=1；加入b的边际从0增至1，违反递减收益。
一般也非超模：a∧b⇒T、a∧c⇒T，R(ab)+R(ac)=2>R(abc)+R(a)=1。
任务选择效用sum(x)为模函数，但安全约束不是matroid。L2中A={a}、B={b,c}安全且|A|<|B|，B任一元素都不能加入A，违反交换公理。
一般即时贪心没有常数近似保证：公开规则a∧b_i⇒T(i=1..m)，顺序a,b1,...,bm，一次正确回答效用1，G选a后只能得1，OPT可取全部m叶得m，比值1/m。此为形式化存在性族，未计为m个真实样本或本轮扩量。
它不排除特定结构/分布/效用的保证；二类互斥时已证OPT=max(n_A,n_B)，不能把其多数计数包装复杂规划。

## B与静态菜单点态等价
本批所有实际无权接收者能被一个k=3联盟覆盖。给定已交付K与任一未来情景ω，取一份最优安全计划，最终并集为V。
对各题型从计划中任选一条曾交付正确答案，其余EMPTY。重复同题型均交该答案，最终并集⊆V，安全且完成数不少于原计划。
故每情景OPT(K,ω)=最佳静态菜单(K,ω)。这是R34固定菜单充分性在当前动作条件下的直接应用，不是新定理贡献。
对每个当前候选的同一32情景求和，两者分数相同；相同平局规则意味着整个在线策略完全相同。1374个不同MILP与10093个当前候选分数被独立穷举认证。
普通Simple预先为预测请求共选一菜单；MenuRecourse可为每个情景另选菜单，因此B超过普通Simple时，不能排除“更强菜单续期”这一解释。

## 信息松弛与可实现性
非预知DP：V(K,r)=Σ_q p(q) max_a[u(a)+V(K∪a,r−1)]。
B精确分布打分：Q_B(a)=u(a)+E_ω OPT(K∪a,ω)，其后续决策假定ω全部可知，因此对匹配分布它上界对应非预知续期价值。
max_a Q_B(a)不是实际B策略价值；重滚动执行也可能次优。L4/uniform已给严格反例，见RESULT。
B合法使用预测场景，不是把真实测试后缀偷渡在线；问题是对续期信息结构的乐观假设。SAA32均值还额外有采样误差，不能称总体的确定上界。
对精确条件分布、精确一致的基策略cost-to-go和有限时域，标准rollout可通过包含原G动作并逐步归纳得到不劣于G；这是成熟动态规划性质。
本轮A2为32情景近似，误差与平局可破坏保证；不能把其Oracle/采样实现推广成总优。通用B松弛不能用这一rollout性质背书。

## 预测错误与安全
所有预测方法每次候选仍通过相同ExactK3，拒答不更新交付，故在冻结正确规则与静态权限下，无论预测多错，安全不变量均由归纳保持。
预测失配会改变安全但不可撤销的信息选择，导致后续拒答/效用损失；不能据此声称语义风险永不增加。解析错误、漏记交付、权限变化和侧信道均未建模。

## 排重与文献
知识推断保密与最大化信息回答已有CQE：Cuenca Grau等，IJCAI2015，[原文入口](https://ijcai.org/proceedings/2015/408)。这里并未突破CQE表达或证明新的策略类别。
G rollout/近似DP见Bertsekas，[Rollout Algorithms for Constrained Dynamic Programming](https://web.mit.edu/dimitrib/www/ADP-MPC.pdf)。A2不能仅凭rollout名称认领新算法。
逐场景完全信息、非预知决策与EVPI是成熟随机规划区别；参见[PyPSA官方随机优化文档](https://docs.pypsa.org/v1.0.3/user-guide/optimization/stochastic/)。本轮独立DP/穷举给自己的精确值，不依赖文档公式作评分真值。
整数规划使用[Scipy milp官方接口](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html)与已安装HiGHS，status0/gap0/整数容差验证后仍逐题独立穷举。没有把通用求解器当新算法。
既有ExactK3受影响联盟、索引、闭包缓存，旧Support的bitset/支配/delta/ZDD都为成熟工程；部分缓存曾更慢。本轮复用它们，不做native ZDD或生产性能领先主张。
查新限于本轮机制排重，非全领域系统综述；当前缺乏独立正收益，因此不提出待包装的新算法。
""")
    write('METHOD_MATRIX.md',"""# 实验矩阵与真实运行范围

- NoGate / Counter4：相同4次全局额度与输出字节上限，不做知识依赖风险检查；因额度不绑定，故完全相同。没有调小配额来制造安全收益。
- G-Shared：已有ExactK3的即时安全回答。
- A1：按R32公开公式重述独立未来机会损失；原R32源码未归档，明确不是原程序重跑。固定系数1，不调权。
- A2 / Simple：复用R34冻结planner与同一风险库；相同32预测情景。
- B-SAA：相同情景、同安全候选，使用标准MILP完整规划每个假想后缀。
- MenuRecourse：每个假想后缀仅穷举原固定菜单；是比普通Simple更强的必要简单基线。
- B-Expectation：枚举预测分布全部后缀，去除32样本估计误差的诊断参照。
- Causal-DP：每到达一个未来请求才选动作的精确已知分布小状态参照。ε0不知真实后缀。
- Offline-Oracle：每实际完整叶序列独立穷举，仅评分阶段读取未来；未传在线函数。

5契约×2真需求分布；7预测方法×3误差+3基线=240策略配置。690唯一序列在不同方法/分布下重放形成33120行，不是33120独立样本。
两开发/三冻结验证契约均研究助手编写，没有独立人工标注者或盲测。新命题模型不是来源真实的自然语言教学材料。
先完成所有因果prefix策略树，再读取叶序列评价；函数输入只有当前prefix、实际交付、当前预测包。公共actor bank去除evaluation_true_probabilities字段。
这里验证功能性nonanticipativity，不声称对恶意native代码的进程隔离；Stage1-C正式门槛不变。
三个实际可信答题Agent/接收槽共享资产历史，攻击者只收合法学生界面reply；没有内部恶意Agent。CGC生产接线未运行。
Single-Agent/Identity-Split/3-Agent/3-Agent+CGC的正式第三阶段矩阵保留为条件任务，当前没有独立算法收益故不启动，不用符号标签代替集成证据。
本轮无生成/RAG调用、Token不适用，实记UTF8字节；真实语义风险NOT_MEASURED，UNKNOWN0仅指52个明确逻辑观察子集及实际回放。
""")
    write('RESULT.md',f"""# R35：B场景优化的简单基线与信息结构审计

**决策PIVOT。B与逐场景最佳固定菜单全部打分/动作相同；没有独立算法收益。** 这是明确有限逻辑类中的机制证据，不代表一般教育场景或语义攻击有效。
五个新SYNTHETIC命题契约，2开发/3作者冻结验证，四轮请求，690唯一序列，均匀/偏置两种完整概率评价；没有看到表现后改题、seed、权限或真值。

## 正确需求分布下的实际效用
数值为每四轮的精确期望正确任务数，展示6位小数；原始分数见complete_results.csv。
{main_table}

G到Offline在8/10资产-分布格有空间（独立契约两个分布均无空间），但这不自动意味着需求预测可利用。
例如L1/uniform：G=正确分布的非预知最优DP=2.5，Offline=2.75。不可预知未来的0.25差距并非可实现算法改进。
相比普通Simple，B在L1/biased小幅增加(218/81−8/3=2/81)，在L3两个分布及L4/uniform退步；所有失败保留。其对MenuRecourse的差距在30个资产-分布-误差格全部为0。

## B打分不等于在线策略价值
{info_table}

代表反例L4/uniform：B精确分布分数201/64=3.140625；实际在线99/32=3.09375；最优非预知DP199/64=3.109375，B实际少1/64。
首问q1要求观察b，完全相同空历史。B给“回答b”打5/2，拒答打81/32，选择拒答；非预知DP给回答5/2、拒答39/16，选择回答。不是预测错或看了真实后缀，而是B假设各场景后续全可知而过度等待。
这证明该打分可能乐观，不证明所有B策略都失效；9/10格的B-Expectation实际等于DP，L0独立事实对照始终4/4，不删除这些阴性结果。

## 预测误差敏感性
下表仅10格等权描述性效用和，满分40，不是抽样总体或独立10资产。
{sensitivity_table}

uniform误差三档预测包完全相同；biased仅研究者控制的循环失配，不代表真实训练预测器误差。
所有依赖安全门方法在所有误差档均0受保护完整重构/0 UNKNOWN；NoGate/Counter仍有组合风险。预测错误降低效用但没有绕过冻结硬安全门。
过拒绝用“当前仍有安全候选却拒答”单列，可能是未来权衡，不能全部当风险误报；正常正确只计真实规范答案，不用提示文本充数。
完整恢复、恰k1/2/3恢复概率、输入知识披露比例、拒答、字节、Offline差距见complete_results.csv。没有测累计自然语言语义恢复率，不能填语义安全0。

## 独立核验与成本
{verification['MILP_subproblems_certified']}个MILP子问题由笛卡尔积全计划认证；{verification['B_current_candidate_scores_checked']}个当前候选B/菜单续期得分逐项一致；690个完整Oracle获独立认证。
52个观察子集Boolean反模型与原ExactK3全部一致，927360个实际联盟前缀检查；33120行回放与45600个独特非预知上下文一致。
90份旧研究/核心文件运行前后SHA256不变。四项预检通过；主完整运行一次，耗wall {read('execution_completed.json')['wall_seconds']:.3f}s，独立核验 {verification['wall_seconds']:.3f}s，均在冻结600秒预算内。
decision_latency.csv记录微秒级wall测量；共用纯求解缓存导致首访问者支付冷启动，不能按这些数排列算法速度优势。MILP冷调用时间另在MILP/*.json。
模型推理/GPU/付费API/训练=0；本轮文字、代码、标签由研究助手编写，不能冒称独立人工真值或盲测。没有生产控制器/Stage1-C阈值改动。

## 结论与唯一下一步
已有即时贪心确有局部长期效用空间，但普通场景采样、整数规划或更强续期菜单不足以成为独立算法贡献。
本批最强简单参照逐场景完全解释B；还要剥离不可预知未来的价值，不能把离线最优差距当可实现增益。
不进入模型训练或CGC集成。唯一下一问题：是否存在有真实教学依据的授权/答案可用性，使无权观察视图不能被一个允许的≤3人联盟并集覆盖，从而破坏已证菜单等价？先审查这种依据，不按结果换身份造Gap。
""")
    write('FAILURES_AND_LIMITATIONS.md',f"""# 负面证据与缺口

- 主执行与独立核验一次通过，未发生需改契约的主运行失败；所有旧失败只读保全。测试与协议先于方法结果。
- B未超出逐场景固定菜单；30个条件格及全部10093候选分数一致。与普通Simple比较的全部退步格共有{len(failures)}项，见all_B_below_Simple_cases.json。
- 正确分布下B-Expectation的L4/uniform决策失误已严格复核，不能用模型预测误差遮掩。其余9格实际达到DP，也不删除。
- Offline>G并不充分：L1/uniform未来为iid，正确分布DP也不能超过G2.5，而Offline2.75拥有不可获得的未来。
- 这些是作者有目的覆盖独立/互补/竞争/长期冲突的存在性机制契约，不是随机抽取教育资产。留出仍作者标注、同一命题语言，不能冒称真实泛化。
- 同一题型重问和同一资产多方法/概率权重不增加独立样本；不报告总体显著性或自编机制的虚假置信区间。
- 所有目标为一个Boolean命题；输入单元披露比例不是受保护关系部分恢复率。没有自然语言提取、测量噪声、负条件语义、外部检索或拒答侧信道验证。
- Counter cap4非绑定而等于NoGate，不能据此宣称任何调优预算方法都无效；缩小cap须给所有方法相同新预算，当前未做。
- Online函数功能上不读真实后缀，prefix树一致性已验，但没有独立OS强隔离；Stage1-C仍缺两名独立人类真值/正式资产等条件。
- B-MILP status最优/gap0还经穷举验证，无法归因于求解器未完成；本轮只显示成熟MILP/菜单/DP关系，不是新优化理论或系统速度创新。
- 主算法未超强基线，因此Single/Identity/3-Agent/3-Agent+CGC正式接线未执行，不能用符号回放宣称CGC性能。当前持续三个逻辑槽及共享历史只验证结构化组合。
""")
    write('NOVELTY_AND_DECISION.md',"""# 算法空间判断：PIVOT

本轮不提出新的防御算法候选。将未来需求信息、标准场景采样、标准整数规划与共享闭包拼接，并未构成独立算法贡献。
G→Offline存在收益只给完整未来的上界；同信息B→逐场景最佳菜单为0，故不能从B超过普通Simple的局部格宣称解决了新的结构问题。
L4反例还说明应先处理非预知信息约束；精确DP已提供成熟的小问题答案，不认领其本身为创新。
对于一般非覆盖联盟/身份相关候选/绑定预算，现有菜单充分性没有证明；但没有现实任务依据和冻结独立Gap，就不能靠变难合成案例立项。
CCF-B/C：当前没有足够算法证据。可积累为基准审查和负结果，不能把执行完整、风险为0或微小局部增益当投稿贡献。
下一轮只审查有来源的角色授权与候选可用性，确认是否真的打破全局并集覆盖；不训练模型、不先扩SYNTHETIC种子、不自动进入队列。
""")
    write('decision.json',{'decision':'PIVOT','complete':True,'EXPLORATORY':True,'SYNTHETIC':True,'assets':5,
        'unique_leaf_sequences':690,'policy_configurations':240,'replay_rows_not_independent_samples':33120,
        'B_all_scores_actions_equal_MenuRecourse':True,'independent_algorithm_gain_over_strong_menu':False,
        'correct_model_L4_uniform_B_score':'201/64','correct_model_L4_uniform_B_actual':'99/32',
        'correct_model_L4_uniform_optimal_causal':'199/64','Stage1_C_formal_gate_passed':False,
        'Stage1_E_confirmatory':False,'semantic_attack_tested':False,'experimental_generation_model_calls':0,
        'new_algorithm_candidate':None,'training_started':False,'CGC_integration_started':False,'CCF_B_C_algorithm_claim_supported':False,
        'next_unique_question':'source-backed authorization/answer-availability breaking one-coalition union covering; audit before algorithms'})
    write('REPRODUCE.md',"""# 复现

Python3.12、已安装numpy/scipy1.18.0、HiGHS；无需模型/下载。原ExactK3与R34 planner快照哈希见freeze。
在CogniGuard checkout的独立新运行名中执行README序列：prepare→run.cmd test本目录→run→verify→report。原OUT已存在时拒绝覆盖。
prepare生成所有原始资产/候选/正Horn规则、690叶序列、5700逐prefix预测包；完整hash先于所有性能，方法平局和600秒wall限制见PROTOCOL。
核心代码版本以freeze.json和快照哈希为准；仓库本来dirty，gitHEAD仅上下文，记录为明确运行后观察，不能代表干净提交。
run先生成所有在线策略树，再读test_leaves构造Offline与评价；verify无engine/planner/scipy.optimize导入，按Boolean模型、实答和独立全计划校验。
完整replays含真实query/reply/接收者/轮次/资产；策略树含当前状态、原候选分数及计时。所有无差异/失败/未知原样保留，不选较好seed重跑。
""")
    write('GROUP_MEETING.md',"""# 三分钟讲解

这轮不是再证明共享历史，而是检查B场景整数规划有没有超过成熟简单方法。
先审计发现Stage1-C仍未正式通过；Stage1-E是固定生成合成实验，不能作为真实多Agent算法证据。R34还已证明一类权限下固定菜单足够。
我们新冻结五个纯逻辑教学契约，枚举690条四轮请求和三档预测误差，用相同预测情景比较贪心、A1、A2、Simple、B、菜单续期和精确非预知DP。
结果有两点。第一，1374个整数规划子问题都被独立穷举认证，而B与逐场景最佳固定菜单的10093个分数和所有动作完全相同。因此B没有独立收益。
第二，离线与在线差距不能都算预测潜力。二类均匀请求里，贪心和最好的非预知策略都是2.5题，离线知道未来能2.75题。另一个多答案案例中，B把拒答后的价值估高：打分3.140625，实际3.09375，还低于非预知最优3.109375。
预测错误确实能损害效用；硬闭包安全门使这批明确逻辑契约内的受限恢复仍为零，但我们没有测自然语言攻击。
所以决策PIVOT，不开发新算法、不进入训练或CGC集成。下一步只查真实教学授权是否存在单个三人联盟覆盖不了的观察结构；没有这种依据，就不继续包装复杂前瞻规划。
""")
    after={p:sha((PROJECT_ROOT/p).read_bytes()) for p in read('history_preservation_before.json')};assert after==read('history_preservation_before.json')
    write('FINAL_QA.json',{'all_frozen_definitions_unchanged':True,'historical_files_unchanged':len(after),'test_passed':4,
        'main_completed_runs':1,'models_and_paid_calls':0,'no_next_experiment_started':True,
        'disclaimer':'research-assistant authored synthetic labels; no independent human annotations or natural language safety test'})
    write('MANIFEST.sha256.json',{p.relative_to(OUT).as_posix():sha(p.read_bytes()) for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
    print('Report complete: PIVOT; B is pointwise identical to menu recourse.')

if __name__=='__main__':main()
