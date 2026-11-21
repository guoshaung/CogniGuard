from fractions import Fraction as F
import itertools
import random
import shutil
from experiments.c2rag_r35_20261029_01.common import *

DEFINITIONS=[
 ('L0','development','independent',list('abc'),[],[['a'],['b'],['c']]),
 ('L1','development','pair',list('ab'),[['a','b']],[['a'],['b']]),
 ('L2','frozen_validation','fork',list('abc'),[['a','b'],['a','c']],[['a'],['b'],['c']]),
 ('L3','frozen_validation','overlap_pair_triple',list('abcd'),[['a','b'],['b','c','d']],[['a'],['b'],['c'],['d']]),
 ('L4','frozen_validation','alternative_answers',list('abcd'),[['a','b'],['a','c'],['b','d']],[['a','d'],['b'],['c'],['d']]),
]

def main():
    OUT.mkdir(exist_ok=False);banks=[];leafs=[];packets=[]
    for ident,split,family,obs,supports,query_opts in DEFINITIONS:
        queries=[]
        for q,options in enumerate(query_opts):
            answers=[]
            for ai,atom in enumerate(options):
                reply=enc({'asset':ident,'positive':[atom]}).decode('utf8')
                answers.append({'id':f'{ident}-Q{q}-A{ai}','facts':[atom],'reply':reply,'correct':True})
            answers.sort(key=lambda a:(len(a['reply'].encode('utf8')),a['id']))
            queries.append({'id':q,'request':'任选报告虚构教学实验中下列一项观察的真假结果：'+','.join(options),'answers':answers})
        bank={'id':ident,'split':split,'family':family,'title':f'SYNTHETIC propositional teaching lab {ident}',
            'observations':obs,'queries':queries,'trusted_recipient':3,
            'case':{'n':4,'facts':obs+['TARGET'],'rules':[(s,'TARGET') for s in supports],'public':[],
                'assets':[{'target':'TARGET','authorized':[m for m in range(1,16) if m.bit_count()<=3 and m&8]}]},
            'H':H,'recipients':RECIPIENTS,'budget_bytes':H*max(len(a['reply'].encode('utf8')) for q in queries for a in q['answers']),
            'provenance':'Original researcher-assistant authored logical exercise, no real copyrighted or private teaching document',
            'public_background':'Boolean positive Horn implications in case.rules; all Boolean models satisfying them are possible; TARGET truth is the simulated protected target',
            'nominal':'all observation atoms true and TARGET true; nominal hidden except actual delivered observations',
            'authorization':'All actual recipients r0-r2 unauthorized; r3 never receives requests. Preserve global-union class deliberately; do not change roles to manufacture a gap.'}
        banks.append(bank);K=len(queries)
        laws={'uniform':[F(1,K)]*K,'biased':[F(K-i,K*(K+1)//2) for i in range(K)]}
        for seq in itertools.product(range(K),repeat=H):leafs.append({'id':ident+'-'+''.join(map(str,seq)),'asset':ident,'sequence':seq})
        for law,true_p in laws.items():
            for epsilon in [F(0),F(1,2),F(1)]:
                rotated=true_p[1:]+true_p[:1];p=[(1-epsilon)*a+epsilon*b for a,b in zip(true_p,rotated)]
                for length in range(1,H+1):
                    for prefix in itertools.product(range(K),repeat=length):
                        rng=random.Random(seed(ident,law,prefix,'scenarios'))
                        scenarios=[rng.choices(range(K),weights=list(map(float,p)),k=H-length) for _ in range(32)]
                        packets.append({'asset':ident,'law':law,'error':str(epsilon),'prefix':prefix,
                            'probability':list(map(str,p)),'scenarios':scenarios,'seed':seed(ident,law,prefix,'scenarios'),
                            'visible_information':'current prefix + estimated iid probabilities; never actual future leaf'})
        bank['evaluation_true_probabilities']={k:list(map(str,v)) for k,v in laws.items()}
    write('banks.json',banks);write('test_leaves.json',leafs);write('forecast_packets.json',packets)
    historical=[PROJECT_ROOT/'experiments/stage1_preparation_20261019_01/stage1_readiness_report.md',
        PROJECT_ROOT/'experiments/stage1_e_20261019_01/sanitized_delivery/research_decision.md',
        PROJECT_ROOT/'experiments/stage1_e_causal_review_20261019_01/sanitized_delivery/causal_review.md',
        PROJECT_ROOT/'experiments/c2rag_v3/fact_release.py',PROJECT_ROOT/'cogniguard/workflows/teachers/chain.py',
        RESULTS_DIR/'c2rag_r34_20261028_02/decision.json',RESULTS_DIR/'c2rag_r34_20261028_02/GLOBAL_UNION_REDUCTION.md',
        RESULTS_DIR/'c2rag_imperfect_forecast_20261027_01/RESULT.md',
        RESULTS_DIR/'c2rag_real_source_structure_20261027_01/r32_evidence/REPORT.md']
    historical+=list((PROJECT_ROOT/'experiments/stage1_e_20261019_01/attempt_02').glob('*/*.raw.json'))
    write('history_preservation_before.json',{p.relative_to(PROJECT_ROOT).as_posix():sha(p.read_bytes()) for p in historical})
    raw=[__import__('json').loads(p.read_text(encoding='utf8')) for p in historical if p.name.endswith('.raw.json')]
    write('stage1_raw_record_audit.json',{'records_read':len(raw),'classes':sorted(set(x['class'] for x in raw)),
        'statuses':sorted(set(x['status'] for x in raw)),'api_calls':sum(x['api_calls'] for x in raw),
        'local_model_calls':sum(x['local_model_calls'] for x in raw),'fixed_generation_slots':sum(x['generation_slots'] for x in raw),
        'unique_assets':len(set(x['case']['asset_id'] for x in raw)),'raw_text_not_republished':True})
    write('HISTORY_AUDIT.md',"""# 接续证据审查

最新research-sync main e06b2d5061f982cf02a1e81834d31fc9dd8afccc 已读，R34 decision回读仍PIVOT/Gap0。
Stage1-C：正式独立人工unit/span/关系/正常答案及裁决未完成；Stage1-E不是通过Stage1-C的替代。现有空表/AI草案不能升级为确认性真值，本轮不改门槛、不启动真实模型。
Stage1 preparation24调度占位排练，不是真实生成；Stage1-E attempt_02为81条固定生成脚本trace、3原资产、3场景、3×3架构配置，API/本地模型调用0。
本轮读取81份原始记录的class/status/calls/gate账本片段并hash保全，引用已完成的只读因果复核；不重新评分或执行旧实验。
Multi-Agent与Identity-Split的27配对走同构分支，不能证明额外多主体效应。Per-Agent变Shared使多份0.08联盟额度收紧为一份0.08，非等联盟总额度的纯拓扑因果效果。
gate_fact(fact_release.py:37)实际是源文本见证+词面测量cost，累加到传入document ledger；本轮不改。Stage1-E runtime_v2.py把ledger按session或trusted root/asset存储；共享历史不由签名自动产生。
当前TrustChain在cogniguard/workflows/teachers/chain.py:60，issue/admit提供来源/链完整性与边权限，不是语义重构判据。旧core入口为兼容层。不能把这部分与C²-RAG知识恢复混淆。
ExactK3是正规则、静态授权、k<=3的离线研究原型，非自然语言防护证明。原Support早已有bitset、缓存、索引；delta/ZDD优化为成熟机制，部分变体反而慢，非新算法。
R32的A1独立机会损失重复计互斥未来，A2Oracle=OPT442但可化二类多数；旧源码未在本地归档中分发，R35明确为公式重述，不谎称旧程序重跑。
不完美预测64流仅两结构，strong Simple371>A2365，A2Oracle384<OPT397。B场景MILP尚无本地可复用实现；Support优化名为B的delta缓存不是这个B。
R34五类超图/六实例，SimpleOracle=OPT252，任意同候选安全计划能转固定菜单。两有限域捷径和同构留出已保留，不能包装语义泛化。
本轮只审计场景信息结构，不改变身份/权限来制造新算法Gap，不重跑R34，不进入CGC集成。所有新任务是原创SYNTHETIC命题教学习题，非真实学生或教师私有材料。
""")
    write('PROTOCOL.md',"""# R35 预注册 · EXPLORATORY / SYNTHETIC

唯一问题：B逐场景精确组合优化是否超出逐场景最佳固定菜单；其预估值是否等于非预知未来的策略价值？
不是R34扩量/权限造反例；保留三名实际无权接收者、k<=3、全局累计历史的已解决类，先排除新B方案的简单解释。
五个全新纯命题教学逻辑契约，非真实课堂/语义泛化：独立、二元、叉形、二元三元重叠、多答案；L0/L1开发，L2–4结构验证。
作者为研究助手，无独立人类标签/盲测。资产、规则、候选、角色、目标、所有4轮题型序列和预测包在任何方法表现前整体冻结；不调题/seed/门槛。
所有Boolean模型满足公开Horn规则是独立真值域；名义所有观察为真。实际只能看到所交query/reply，不可看到全观察或TARGET值。
持续r0,r1,r2,r0跨题历史，同联盟规则/授权/候选，候选正确1/空答0，拒答0字节；总请求4、输出4*最长候选，均非绑定。
Counter统一累计输出次数cap4，与所有方法同上限，故不能靠缩小联盟预算产生优势；它可遗漏非加性风险，须如实报告。
不调用生成/检索模型，Token不适用，记录实际UTF8字节；实验模型/API/GPU/训练均0。

## 需求与预测
每资产枚举所有K^4序列，不抽取有利测试流。两种iid真需求分布：均匀，或p(q_i)=(K-i)/sum(1..K)。同一叶序列在不同分布下仅权重不同，不冒充独立样本。
错误ε=0,1/2,1；p_hat=(1-ε)*p+ε*左循环p。ε0是正确分布，不是已知未来Oracle。
每可见prefix SHA256([20261029,asset,law,prefix,scenarios])前16hex为种子，32个独立有序未来情景；各ε共用随机数。先冻结所有prefix包，在线函数只接当前包。
先递归构造所有前缀的非预知策略树，再评价全部实际叶序列；在线决策函数没有真实后缀参数。Oracle在另一评分阶段读叶序列。
相同prefix与实际历史必须同决策，独立检查nonanticipativity。预测p_hat只能作为假设，不承诺是现实可训练质量。

## 固定方法矩阵
NoGate、Counter4、G-Shared；以及每ε下A1、A2、强Simple、B-SAA-MILP、MenuRecourse-SAA、B-FullExpectation、Nonanticipative-DP。
G/Simple/A2复用R34冻结代码；风险复用原ExactK3，不改控制器。A1明确重述R32设计：32*即时效用−逐情景各未来请求因当前动作而丧失单独可答性的次数；非精确旧源码重跑。
Simple为全局兼容固定菜单、每步重选；A2当前安全候选后按样本顺序G rollout。均用32相同情景。
B对每当前安全候选、每情景用SciPy/HiGHS精确求未来可完成数，再加即时效用平均。二进制x_{t,a}单请求至多一答，z_f>=x对每透露单元，既有事实z=1；每最小危险集C约束sum(z_f)<=|C|-1；目标max sum(x)。
MenuRecourse只将每情景MILP替换为穷举最佳固定菜单；它是必须保留的成熟简单强基线，不削弱风险或候选。
B-FullExpectation在同p_hat下完整枚举情景概率，分离采样噪声；这是有界小问题参照，不是实际未来Oracle。
DP在同p_hat下按Bellman递推，未来每个q到达才可选动作；r=0值0，V(S,r)=sum_q p_hat(q)*max_a[u(a)+V(S∪facts(a),r-1)]。
Offline-Oracle每实际完整序列独立穷举；只作理想上界，严禁在线输入。未来场景是合法预测假设，非真实未来泄漏；但逐场景假设后续完全可知可能产生信息松弛乐观值。
SAA均值不是总体置信上界；精确场景OPT只给对应场景的上界。DP和B-Expectation在小状态空间精确计算，不宣称新算法。
score大、即时效用大、当前字节少、ID小；Simple再菜单ID元组小，所有平局固定。

## 核验、指标与停止
独立Boolean全模型枚举所有观察子集；按实际回复解析并独立恢复每名接收者视图、恰k1/2/3联盟；unknown停止，不算安全。
所有MILP子问题以独立全计划笛卡尔积认证；所有逐情景最佳菜单/OPT值必须相同或保留反例，不假定新B有优势。
报告逐资产/分布/ε/方法的精确加权完成数(满分4)、恢复率、拒答、仍可安全回答却被拒次数、字节、耗时、Offline差距、B−Simple和B−MenuRecourse。
另报告B-FullExpectation的首步分布上界与非预知DP最优值，二者差异才是信息松弛；实际策略效用另列，不能当成算法获得上界值。
无总体统计外推/置信区间；五机制才是资产单位，不把690叶或多方法当独立样本。独立/均匀/强Simple=OPT对照与所有Simple>B、B<DP、失配退步保留。
主与独立核验各600秒wall；MILP每题2秒、mip_gap0、整数误差1e-6。status非最优/超时/真值分歧保留INCOMPLETE，不加预算或换种子。
正Horn恢复单调、风险非次模、一般安全系统非matroid须给严格反例；安全硬门下预测错误不能增加所建模越权，但可能损害效用。对自然语言/侧信道不推广。
不进入第三阶段CGC集成：只有超过强简单基线且可复核的独立收益才能另议。完成本轮同步后停止，不自动训练/扩大。
""")
    (OUT/'snapshot').mkdir()
    for n in ['engines.py','reference.py']:shutil.copyfile(BASE/n,OUT/'snapshot'/n)
    shutil.copyfile(PROJECT_ROOT/'experiments/c2rag_r34_20261028_02/planner.py',OUT/'snapshot/old_planner.py')
    write('freeze.json',{'before_any_performance':True,'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'data_and_baseline_sha256':{p.relative_to(OUT).as_posix():sha(p.read_bytes()) for p in OUT.rglob('*') if p.is_file()},
        'experiment_code_sha256':{p.name:sha(p.read_bytes()) for p in SOURCE.glob('*.py')},
        'assets':len(banks),'unique_leaf_sequences':len(leafs),'forecast_packets':len(packets)})
    print('Frozen',len(banks),'assets;',len(leafs),'unique sequences;',len(packets),'causal packets')

if __name__=='__main__':main()
