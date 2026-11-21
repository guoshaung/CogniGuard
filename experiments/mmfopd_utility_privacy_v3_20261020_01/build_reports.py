"""Requested repository deliverables, only measured results and algebraic checks."""
import core as c
import numpy as np
import json,platform
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=c.P
def text(name,value):(P/name).write_text(value,encoding='utf8')
def table(head,rows):return '| '+' | '.join(head)+' |\n| '+' | '.join(['---']*len(head))+' |\n'+'\n'.join('| '+' | '.join(map(str,row))+' |' for row in rows)+'\n'
def f(x):return f'{x:.3f}'

def main():
    s=c.load(P/'validated_summary.json');a=c.load(P/'validated_attacks.json');bg=c.load(P/'background_with_intervals.json');inner=c.load(P/'selection_inner.json');geom=c.load(P/'geometry.json');completion=c.load(P/'phaseC_completion.json');gate=c.load(P/'phaseD_gate.json');eq=c.load(P/'teacher_readout_equivalence.json');b=c.load(P/'bootstrap.json');validation=c.load(P/'validation.json')
    assert gate['decision']=='PIVOT' and all(x['rank']==0 for x in gate['cells'])
    tr,dv=c.dataset();cohort={'train_students':len({r['student'] for r in tr}),'dev_students':len({r['student'] for r in dv}),'train_snapshots':len(tr),'dev_snapshots':len(dv),'attributes':{x:{'train_positive_students':len({r['student'] for r in tr if r[x]}),'dev_positive_students':len({r['student'] for r in dv if r[x]}),'dev_positive_snapshots':sum(r[x] for r in dv)} for x in c.ATTRS}}
    c.save('cohort.json',cohort)
    contexts=c.CONTEXTS
    def row(m,i,w):return next(x for x in s if (x['method'],x['intent'],x['wording'])==(m,i,w))
    def avg(m,key):return float(np.mean([x[key] for x in s if x['method']==m]))
    def avga(m,attr,kind,key='AUC'):return float(np.mean([x[key] for x in a if x['method']==m and x['attribute']==attr and x['attacker']==kind]))
    selected=['Identity','RoleReward-history','OPP-v2-style','INLP3','LEACE','V3','V3-rank1','V3-rank2','NoAtt-Identity']
    methods_table=table(['同接口方法','MAE↓','几何失真','性别LR/RF AUC','残疾LR/RF AUC','Token','角色'],
        [[m,f(avg(m,'MAE')),f(avg(m,'relative_squared_distortion')),f(avga(m,'gender_F','LR'))+'/'+f(avga(m,'gender_F','RF')),f(avga(m,'disability_Y','LR'))+'/'+f(avga(m,'disability_Y','RF')),f(avg(m,'actual_tokens_mean')),('开发秩诊断，未选中' if m.startswith('V3-rank') else '正式冻结对照/候选')] for m in selected])
    rank_table=table(['任务/措辞','内验证r1失真','内验证r2失真','选中r','外开发Identity MAE','外开发r1/r2 MAE'],
        [[i+'/'+w,f(inner[i+'|'+w]['candidates'][1]['distortion']),f(inner[i+'|'+w]['candidates'][2]['distortion']),inner[i+'|'+w]['selected_rank'],f(row('Identity',i,w)['MAE']),f(row('V3-rank1',i,w)['MAE'])+'/'+f(row('V3-rank2',i,w)['MAE'])] for i,w in contexts])
    phaseb=c.load(P/'phaseB_gate.json')
    interface_table=table(['任务/措辞','旧字段Safe MAE','统一Identity MAE','差值','实际Token'],
        [[g['intent']+'/'+g['wording'],f(g['same_source_cached_raw_MAE']),f(g['Identity_MAE']),f(g['delta_MAE']),49] for g in phaseb['cells']])
    privacy_table=table(['方法','性别LR AUC/BA','性别RF AUC/BA','残疾LR AUC/BA','残疾RF AUC/BA'],
        [[m]+[f(avga(m,attr,k))+'/'+f(avga(m,attr,k,'BA')) for attr in c.ATTRS for k in ['LR','RF']] for m in ['Identity','V3','V3-rank1','V3-rank2','OPP-v2-style','INLP3','LEACE','NoAtt-Identity']])
    bgtable=table(['属性/攻击器','AUC [学生bootstrap95%]','BA [95%]'],
        [[x['attribute']+'/'+x['attacker'],f(x['AUC'])+' ['+f(x['AUC95_low'])+','+f(x['AUC95_high'])+']',f(x['BA'])+' ['+f(x['BA95_low'])+','+f(x['BA95_high'])+']'] for x in bg])
    fractions=[v['task_shared_sensitive_crosscov_frobenius']/v['total_sensitive_crosscov_frobenius'] for k,v in geom.items() if not k.startswith(('NoAtt','INLP'))]
    r1dist=[inner[i+'|'+w]['candidates'][1]['distortion'] for i,w in contexts];r2dist=[inner[i+'|'+w]['candidates'][2]['distortion'] for i,w in contexts]
    maxteacher=max(x.get('teacher_linear_score_change_max_on_actual_wire',0) for x in s)
    maxsym=max(x['P_symmetry_error'] for x in s if x['method'].startswith('V3-rank'));maxidem=max(x['P_idempotence_error'] for x in s if x['method'].startswith('V3-rank'))
    emax=max(x['P_rank2_minus_teacher_outer_frobenius'] for x in eq)
    # Real line numbers from the exact executed sources.
    paths=[]
    for name,patterns in {'core.py':['class Encoder','def fit','def transform','def wire','def parse','def emit','def covariance_projection','def evaluate'],
                          'candidate.py':['def teacher_weight','def family','def select_rank','def references'],
                          'phase_c.py':['def final_eval','for intent,wording in c.CONTEXTS:'],
                          'derive_validate.py':['def aucboots','def babooots']}.items():
        lines=(P/name).read_text(encoding='utf8').splitlines()
        for pattern in patterns:
            line=next(i for i,l in enumerate(lines,1) if l.strip().startswith(pattern))
            paths.append({'path':name,'symbol':pattern,'line':line,'sha256':c.sha(P/name)})
    c.save('code_paths.json',paths)
    code='\n'.join('- `'+x['path']+':'+str(x['line'])+'` — `'+x['symbol']+'`。' for x in paths)
    audit=f'''# MM-FOPD v3：表示和实际外发接口审查

**Phase A完成，Phase B接口门槛6/6通过。** 数值来源、字段身份和缺失状态可核算；统一接口可以公平比较投影方法。不能把修复后的接口效果追溯给v2。

## v2真实路径复核

`experiments/mmfopd_orthogonal_privacy_v2_20261019_01/privacy_core.py`中ProfileEncoding.fit/transform以训练中位数填补13值并拼13缺失指示，训练标准化。`run_dev.py`的wire只输出三个h/c式数值；readout按原字段索引从变换后的26维取三维，原有缺失指示没有独立发布。投影后这些坐标已是混合码，不再保持原字段单位和事实语义。

**未发现“用原字段预测器权重直接预测新坐标”的接线错误**：v2在每个方法对应的实际解析摘要上重新拟合Ridge，攻击器也在真实wire+公共背景上重新拟合。编码器、投影、下游和攻击器都只用原训练学生；开发标签仅做评估。v2的问题是有损readout/缺失接口及敏感抑制与任务损失，而不是可以假定的未重训错误。v2结果和三份远端报告均只读、哈希匹配，见prior_remote_readback.json及preservation.json。

## v3统一接口：三字段来源、六个分量

源池沿用13个安全字段和门限0.7。Task Attention按公共TF-IDF元数据选3字段，字段位置按公共schema索引排序；明确/模糊任务均为旧冻结定义，阶段42/98/154的选择先核验字段身份稳定。NoAtt用旧训练MI前三，历史角色奖励用原冻结选择字段，皆相同3来源预算。

对选中字段仅在相应训练分组估计median、mean、scale，产生三个标准化数值v；缺失用训练中位数填补并额外发布m0..m2。数值码h0..h2是P变换后的v，缺失标记完全不投影。实际格式为`f=三个公共字段索引`及h0/h1/h2/m0/m1/m2七行；没有学生ID、性别/残疾真值或攻击预测。f确实在wire中，不是攻击者被隐藏的侧信息。所有方法同样格式、同样三位小数、K_source=3及64Token上限，本轮训练和开发回复均49Token，没有凑长文本。

字段原单位：older/latest_score及score_delta为分；completion_rate、forum_share、content_share为比例；clicks为次数；active/inactive为天；previous_attempts为次数；studied_credits为学分。训练标准化后h无量纲。Identity可依据f和公开训练统计恢复原单位到舍入精度，并用m明确标记None。P非Identity时h只是混合码，不允许按f把它陈述成原始学生成绩或行为事实；f说明输入基底，不授予输出事实语义。

## 门槛先于算法优化

冻结Identity相对同来源原始SafeTaskTopK的MAE增幅≤1分，全部六情境都必须通过。结果如下（每行473快照/166学生）：

{interface_table}

最大增幅0.02043分，缺失标记逐条精确保留。因此才执行Phase C。这里比较旧接口只用于回归准入；正式投影对照全部重新在本轮统一接口上训练、评估。旧v2的Identity明确trajectory为27.952，本轮为20.619；不能将差值归功于v3隐私投影，其他编码及特征处理也有变化。

## 训练、开发和攻击可见性

外训练484学生/1337快照，外开发166/473；内拟合376/1041，内验证108/296，完全按学生hash划分。内验证只来自外训练，不接触外开发学生。内拟合单独拟合编码统计、教师、投影与RF，内验证选r；随后仅用全部外训练重拟合一次。外开发不改r或约束。

每个方法的任务Ridge和LR/RF攻击在其**实际解析wire+共同公开背景**上拟合；没有额外原始字段、内部向量或隐私标签输入到攻击视图。公开背景为课程、cutoff和距下一已公布deadline天数。单独背景攻击另训；f、m、h均可被接收者和攻击者利用。缺失状态是故意保留的侧信道，不把它当作已擦除。

验证36894条开发wire（78原始方法情境×473）精确重放，所有缺失标记相同；24次翻转本地属性/成绩/ID后，输出和解析视图不变。18个既有源/证据文件及当前锁定代码哈希未变；未读取2014J原始数据。该检查证明实现边界，不是统计安全证明。

成本CSV包括真实Token、UTF-8字节、6维输出大小及编码/投影/序列化/解析的批量摊销延迟，未含tokenizer初始化和下游模型推理；完整在线单请求延迟未测。所有表示的三个缺失标记仍可解释，但只有Identity的三数值能还原原字段；混合表示的事实Recall设为不适用，另报来源契约代理和任务方向保留，不能偷换必要知识真值。

## 真实函数与行号（本实验目录内）

{code}
'''
    text('mmfopd_v3_interface_audit.md',audit)
    algorithm=f'''# MM-FOPD v3：任务效用约束下的隐私正交表示

**PIVOT。** 接口修复成功，任务保护方向可以避免v2式效用损失；但在预冻结ε=1分、δ=0.20、64Token约束下，训练内部选择的可行解全部为Identity。没有实际非线性增量泄露收益，不能保留为已验证的核心创新。Phase D未运行独立测试。

## 来源、版本与实际执行

只读复核research-sync的OULAD dynamic、projection diagnosis和orthogonal privacy v2三份报告，与本地哈希一致。本分支独立于现有`experiments/mmfopd_v3`和生产核心，不覆盖v2。只用现有2013J训练/开发缓存，未下载数据/模型、未付费调用。2014J已用保留集不读取和复测。数据源为Kuzilek等的[OULAD作者版本](https://doi.org/10.6084/m9.figshare.5081998.v1)，CC BY4.0，[数据论文](https://doi.org/10.1038/sdata.2017.171)。

依次冻结protocol→Phase A/B→通过接口门槛→锁定候选代码→Phase C一次有限比较→配对统计/审查。78个原始方法×情境单元、312条属性/攻击器结果，实际仅38套不同外发输入的任务模型及相应攻击器拟合；重复输入复用相同拟合并显式记录aliases，不拿重复方法增加证据量。B5和no-projection另外12行纯Identity别名使最终消融CSV为90行；隐私效用CSV360实际输出条目+4背景=364行。内验证仅RF评价固定r0/1/2；没有参数、数据划分、epsilon/delta或攻击器搜索。Phase C耗时{completion['actual_seconds']:.1f}秒，失败0。

外训练484名/1337快照，外开发166/473；内拟合376名/1041、内验证108/296来自外训练，学生不交叉。开发性别阳性77名/225快照，残疾阳性20名/57快照。六任务化情境重复同一批学生，不是2838名学生，也不是独立确认性数据。任务均预测下一预定TMA成绩，未及时提交构造0；及时真实成绩339快照。未衡量自然语言教学、干预因果效应或教师标注必要知识。

## 一个候选，统一外发接口

先按公共任务q选择3安全来源字段；数值以训练统计填补/标准化为v∈R³，缺失位m∈{{0,1}}³。实际发布h=P(v−μ)+μ及不变m，同时发布公共字段身份f；三位小数，6个数值分量，实际49Token，源字段K=3、Token上限64。h为混合码，不是原始学生事实。Identity带完整缺失状态，六情境接口回归全通过，详见接口审计。

## 区分四类信息，不假设天然正交

训练Ridge教师预测y，输入v、m和公共背景c；抽出在v上的系数w，t=w/||w||，T=ttᵀ。

1. 任务相关信息：t方向是该线性教师使用的值信息；m、c另保留。它不是所有教育任务信息的完整充分统计量。
2. 敏感相关信息：C=Cov_train(v,[gender,disability])的列空间只是训练类别均值相关代理；非线性可预测性必须用实际外发RF另测。
3. 任务—敏感重叠：TC为敏感协方差沿任务方向的分量；训练||TC||/||C||范围{min(fractions):.3f}–{max(fractions):.3f}，并非0。此量不是子空间集合交、互信息分解或独立性证明；删除这部分可能伤任务，主候选明确保留它。
4. 冗余代理：span(t,C)的欧氏正交补只是上述线性代理未使用的方向，不能因此称统计上真正无关；非线性信号仍可能存在。三值低维接口不保证有便宜的隐私方向可删。

## 数学定义与真正执行的约束

只研究以下一个有限家族：C_res=(I−T)C；SVD(C_res)取正交左基U，r∈{{0,1,2}}，P_r=I−U_rU_rᵀ。P_r对称、幂等且P_rw=w，因此**在未舍入表示上保持该固定线性教师预测**。完整六分量变换为diag(P_r,I₃)，缺失位和公共背景不变；δ仅在三值块上计算，不把不变缺失位加入分母来稀释失真。它并不保证重新拟合预测器的真实MAE或非线性任务效用，故仍检查真实损失。

内拟合学生估计编码、教师、C和P；内验证对每个r真实序列化、解析、重训同协议下游和属性RF：

`Risk_r = max_s max(0, AUC_RF(actual_wire_r,c;s) − AUC_RF(c;s))`。

在以下硬准入集合内最小化Risk，风险数值并列取更低失真/更低r，Identity允许被选：

- 内验证MAE_r ≤ 内验证MAE_Identity + **ε=1.0分**；这是明确的筛除条件，没有用软惩罚偷放宽。
- 内验证D_r=Σ||P_rv−v||²/Σ||v||² ≤ **δ=0.20**。
- 每条真实wire Token≤**64**，相同三字段源预算和缺失/身份接口。

内验证秩只从外训练学生中选定，然后用全外训练重拟合同r一次，外开发只验证，不重选。ε、δ、秩集及RF预算在Phase B前已经冻结。几何D在序列化前计算；另独立报告解析真实wire后的精确失真，未把二者伪称完全相等。主候选r0在两者下均通过；未靠舍入越过阈值。教师保护不是“精确真实标签效用保证”，本次显式ε门全部非绑定，删除ε门仍选r0，不能宣称这个门本身已有独立实验收益。

## 基线和单因素边界

B0=Identity；B1=RoleReward-history，历史角色奖励选字段后走相同接口；B2=OPP-v2-style，在相同3值源上重拟合C的无约束正交擦除，掩码共同保留。它是v2公式的新接口实例，**不是重写v2的26维/三读出旧结果**。B3=INLP3（固定最多3轮joint4类LinearSVC、行空间零空间求交，代数秩耗尽停止）；B4=官方LEACE（float64、affine、无shrinkage/trace约束）；B5=仅任务选择，与B0完全同一输入和输出；B6=受约束家族选择后的V3。

单因素消融：NoAtt-Identity/V3把公共TF-IDF源选择换固定训练MI3；V3-no-loss-gate只取消ε准入，仍保留教师保护及δ；V3-no-teacher-protection只令T=0，仍保留ε/δ；no-projection就是Identity，真实相同不额外拟合；r1/r2为开发诊断，外开发结果不能倒用作新r选择。B2同时取消教师保护及约束筛除，属于复合无约束参照，不能冒充单因素。所有都相同源池、输出schema、K和Token上限。

预设非正交参考为I−.5UUᵀ，使用被选方向。由于选中r全0，它也退化Identity，**不是有信息的正交必要性对照**，不能由此说正交优于非正交。

{methods_table}

表为六情境等权均值，非扩大分母；失真为未舍入几何值。V3秩诊断不是最终选中方法。完整BA/AUC/Accuracy、Token/字节/延迟、95%学生区间和逐情境约束均在CSV。

## 有限秩诊断：教学保护有效，但当前硬界不可行

{rank_table}

内验证r1失真{min(r1dist):.4f}–{max(r1dist):.4f}，r2为{min(r2dist):.4f}–{max(r2dist):.4f}，都超过0.20；NoAtt固定MI3也没有非零可行解。**只是这个冻结家族在内验证下无非零可行解，并非所有正交变换数学上不可行**。三维标准化值每维有单位方差，秩1删去的能量常接近1/3，20%欧氏失真上限可能比任务MAE更严格；本轮不事后改用任务加权距离或放宽δ。

同接口下，r1/r2外开发MAE均接近Identity（均值{avg('V3-rank1','MAE'):.3f}/{avg('V3-rank2','MAE'):.3f} vs{avg('Identity','MAE'):.3f}），而无约束OPP为{avg('OPP-v2-style','MAE'):.3f}。这支持教师方向保护能避免该线性预测任务的重大损失，不能被写成“隐私与效用已兼得”。外开发engagement/explicit的r1失真0.17724碰巧低于界，但其内验证为0.2935，预先选择r仍是0；未据外开发反选它。

## 数学和简单替代审查

非零r1/r2的P对称最大误差{maxsym:.2e}，幂等最大误差{maxidem:.2e}；P_rw−w近机器精度，真实舍入后教师线性评分最大变化{maxteacher:.5f}分。LEACE一般是斜投影，不能用其非对称性判实现失败。INLP在3值小空间首轮即耗尽值方向，后续没有可再删的秩，仍发布共同缺失位；不能声称复现了原论文所有设置或得到全6维擦除。

**额外只读代数审查**：在本次三维值、一个教师方向的六情境，r2的P与普通教师一维读出ttᵀ最大Frobenius差{emax:.3e}；每情境473/473真实wire完全相同。因为C_res张成教师正交补，删完该二维补空间后只剩任务教师方向。这个r2表示可由不使用敏感标签来拟合方向的普通教师分数压缩复现；敏感标签仍参与秩选择，但r2变换本身没有独立新颖性。该审查未增加模型拟合、未改变原选择，也不假装是预注册独立基线。

## 实际外发隐私与公开背景

{bgtable}

{privacy_table}

最终V3=Identity：六情境每条wire和预测均相同，LR/RF各属性的配对AUC/BA差及500次学生bootstrap区间均为0。不能将这叫新安全收益。r1/r2诊断出现有利与反向子项，但未满足内验证δ，且多数性别RF本来低于背景单独攻击的AUC，不能称擦除了接收者已知信息。指标是观察性攻击差，不是条件互信息；接收者始终可以忽略表示。

反向例：trajectory/explicit，r2使性别RF AUC0.81672→0.81635几乎不变，残疾RF AUC0.54521→0.57585、BA0.53013→0.61233。配对BA差95%区间[0.03267,0.13412]，AUC差区间[−0.03480,0.10115]。全部报告，不能用一个属性下降掩盖另一个上升。相同快照同学生聚类，未作多重比较校正，不作确认性显著性声明。

## A—E明确回答

**A：实现了经验任务效用硬约束。** 内验证eligibility执行ε/δ/B并允许Identity回退；教师保持仅为训练线性代理，未承诺任意y或任意新学生误差界。ε本次不绑定，没有证明它单独带来收益。

**B：最终候选没有降低真实外发的非线性增量属性泄露。** 它选r0，与Identity完全相同；不合格秩诊断不能替代主方法结论。

**C：选中输出满足预设教学误差约束，但靠Identity回退。** 非零探针也保持MAE，却在内验证失真界下被拒，不能称联合约束成功。

**D：没有独立优势。** 最终与Identity/B5/no-projection持平，NoAtt训练MI3平均MAE更低；r2还与普通教师压缩完全等价。没有优于简单方法、INLP/LEACE的合格安全效用证据。

**E：当前证据不足以保留为MM-FOPD核心机制。** 可保留这次可复核边界与负结果，撤回旧角色奖励的敏感解耦命名；不把正交从实验分支并入生产。判断针对本次候选/接口/ε/δ，不宣称正交永远无用。

决策PIVOT；独立验证门槛0/6通过，没有Phase D、新独立数据申请或2014J复测。停止搜索，不为了组会放宽δ。

## 与已有工作的关系与局限

[INLP](https://arxiv.org/abs/2004.07667)已使用迭代线性分类及零空间擦除；[LEACE](https://arxiv.org/abs/2306.03819)已有闭式概念擦除，本轮复用既有官方MIT源码且保留许可证。[Privacy Funnel](https://arxiv.org/abs/1402.1774)研究隐私—效用披露权衡。这里是受限RF攻击代理下的有限正交家族筛选，不是在估计或求解其互信息目标；普通SVD、教师零空间和硬约束筛选都不称原创优化器。

C为边缘协方差，未残差化公开背景；隐私目标虽在wire+c上评估，也不等于条件信息量。保留m会保留缺失相关泄露；RF/LR预算不是最强攻击。目标成绩可见性仍用原lag代理，没有真实发布时间，开发7/473目标曾提前提交；不称严格前瞻教学无泄漏。未做跨轮拼接、自然语言教学、跨域或新独立确认。

## 复核入口

代码与真实行号见code_paths.json；protocol.json早于新拟合，phaseB/C_lock锁执行源码。validation通过18旧文件哈希、36894条wire、24例禁用列翻转。90行消融、364行隐私效用、JSON、源码及哈希公开；逐学生数据/标签/预测/回复仅LOCAL，不上传。原始数据或模型未下载。

![接口修复](figures/interface_regression.png)

![约束与任务效用](figures/rank_feasibility.png)

![实际外发RF](figures/release_privacy.png)
'''
    text('mmfopd_v3_algorithm.md',algorithm)
    failures=f'''# MM-FOPD v3失败与可行边界

**PIVOT，保留全部不利结果。** 不是v2改写或确认性盲测。

1. **修复成功仅属于接口。** 新Identity最大MAE增幅0.02043分、缺失标记精确保留；旧v2明确trajectory摘要MAE27.952，本轮20.619。不把这算作投影收益。v2每方法都正确重训过预测器，不能杜撰旧接线失败。

2. **当前正交家族在δ下只有平凡解。** 六情境内验证r1失真{min(r1dist):.4f}–{max(r1dist):.4f}，r2为{min(r2dist):.4f}–{max(r2dist):.4f}，均>.20。移除MAE筛选仍r0，约束瓶颈为几何失真；不能说是正交无法保持MAE。三维标准化接口的20%界本身可能过于限制秩1删去能量，但事后不得改界制造成功。

3. **教师保护提供了局部效用证据，未提供隐私成功。** 同接口无约束OPP平均MAE{avg('OPP-v2-style','MAE'):.3f}，教师保护r1/r2分别{avg('V3-rank1','MAE'):.3f}/{avg('V3-rank2','MAE'):.3f}，接近Identity{avg('Identity','MAE'):.3f}。这能说明本有限线性任务保护方向有效；不能说明满足全部约束或超越简单压缩。

4. **零秩使主方法输出完全相同。** 最终V3所有六情境473/473回复与Identity相同；AUC、BA、MAE配对差及区间均0，不能用内部投影算子名称声称收益。NoAtt也选r0。Nonorth-half采用选中方向，所以也退化Identity，没有独立的正交必要性证据。

5. **正交还可能增强另一属性推断。** trajectory/explicit的r2，性别RF AUC0.81672→0.81635，但残疾0.54521→0.57585，BA0.53013→0.61233。BA差95%[0.03267,0.13412]；AUC差95%[−0.03480,0.10115]。这是开发秩诊断，不是主候选；没有隐藏。阳性只有20独立学生，不能按57阳性快照当独立学生。

6. **公开背景使“增量泄露”存在地板。** 课程/日程自身性别RF AUC0.84287，多数Identity情境小于它；负的增强攻击差不能当成删去已知背景。报告带符号差、max(0,差)及学生区间；不是条件互信息、最优攻击或信息论保证。

7. **r2能被普通教师读出复现。** 六情境P2≈ttᵀ最大矩阵差{emax:.3e}，普通教师一维得分再映回三值码可逐字复现473/473回复。该只读审查不新增拟合、没有重选r。成熟线性代数不能改名包装成独立新算法。

8. **外开发偶然可行不能反选。** engagement/explicit的r1外开发失真0.17724，但内验证0.2935，原选择r0。外开发RF性别AUC0.84356→0.84541反而升高，残疾0.51969→0.50782下降。没有因外开发的局部好值改用该秩。

9. **共享任务敏感分量被保留。** ||TC||/||C||为{min(fractions):.3f}–{max(fractions):.3f}，任务与敏感相关并不天然分离。m也公开；残留学习阶段、行为和成绩信号可被非线性利用。保护教师预测不保证对真实新标签或其他教学目标保持效用。

10. **限制不可隐去。** ε本次非绑定，不能证明显式损失门单独有贡献；只研究r0/1/2，不能否定所有正交家族。没有新学生确认、跨轮联合攻击、真实教师必要知识标注或LLM教学评测。延迟是编码/投影/序列化/解析摊销值，不是完整在线模型时延。所有数值真实，失败日志和负结果保留，不再搜索。
'''
    text('mmfopd_v3_failure_cases.md',failures)
    narration='本轮先修复表示接口，补回字段身份和缺失标记，Identity六项回归均通过。随后只检验教师方向保护的正交家族：非零投影能保持预测误差，却全部超出训练内验证预设失真上限，最终六情境均回退Identity，实际属性推断没有改善。秩二探针还可由普通教师分数压缩逐字复现。因此结论为PIVOT：保留边界证据，不把正交包装成已验证的核心隐私机制。'
    meeting=f'''# 2026-10-20组会：MM-FOPD v3阶段结果

**PIVOT：接口修好，教学方向保护有局部效用证据，联合安全—效用收益仍未成立。**

外训练484学生/1337快照，外开发166/473；内拟合376/1041、内验证108/296完全来自外训练学生。六情境重用同一学生，全部EXPLORATORY。78原始方法情境、38套不同实际输入的模型，90行含显式别名消融、364行隐私效用。无付费、下载、生产/历史修改或2014J原始数据读取。

## 接口先行：真实回归

三值码＋三缺失标记＋公共字段身份，所有方法相同接口、三来源字段、49实际Token<=64，混合码不伪装成学生事实。v2预测器本来已经每方法重训；本次修复的是缺失/readout接口，不能杜撰旧接线故障。

{interface_table}

## 真正冻结并执行的约束

ε=Identity MAE+1分；δ=标准化值相对平方失真0.20；Token64。仅在训练内部学生验证选r0/1/2，包含Identity，随后外训练重拟合一次，外开发不选秩。

保护教师值系数w，在其正交补内估计敏感协方差方向U，P=I−UUᵀ；数学对称/幂等和Pw=w通过。它保留任务—敏感共享信号，不声称统计独立。隐私目标用真正wire+公共背景的RF超背景AUC，条件不是内部LR。

{rank_table}

所有内验证非零秩超过δ，主候选六情境都选r0；移除ε门仍同样结果。非零秩外开发MAE虽保持，不能据外开发反选或放宽界。不能把它写成“正交与效用绝不兼容”，本轮瓶颈是预设失真界和未证实的实际隐私收益。

## 同接口真实结果（六情境均值）

{methods_table}

来源契约Recall仅为代理；缺失标记100%保留；混合码不报告原字段事实恢复率。逐情境LR/RF的AUC/BA/Accuracy、学生bootstrap95%、Token/字节/延迟均在CSV。公开背景性别RF AUC0.84287，不能用低于背景的某次攻击值宣布删除攻击者知识。

## Algorithm Reviewer结论

- 任务方向保护使r1/r2 MAE接近Identity，避免无约束OPP严重损失；这个局部机制有证据。
- 联合约束下最终V3=Identity，所有实际回复及属性攻击完全相同；无独立安全收益。
- r2在三维空间等于普通ttᵀ教师读出，六情境每个473/473实际wire完全可复现；不是不可替代的新机制。
- 一个属性改善可能伴随另一个恶化：trajectory明确任务r2的残疾RF AUC0.545→0.576、BA0.530→0.612。完整披露，未筛掉不利项。
- 相同数据上固定TrainMI3无Attention平均MAE18.414，Identity任务选择20.042；不能包装Attention普遍优越。

## 必答A—E

A：实现经验硬约束，但ε在本次非绑定，不能证明该门独立有效。

B：最终未降低实际非线性增量泄露，选中输出与Identity相同。

C：选中输出满足MAE界，靠Identity回退；非零探针保持MAE但未通过训练内δ。

D：没有超越简单方法、INLP/LEACE的合格独立收益；r2等价普通教师压缩。

E：不宜作为已验证MM-FOPD核心机制；保留本分支负结果与可行边界，不并入生产。

Phase D门槛0/6通过；不申请新独立测试、不改δ、不继续参数搜索。成熟INLP/LEACE/Privacy Funnel的关系和局限详见算法报告。

## 约150字讲解词

{narration}

![接口修复](figures/interface_regression.png)

![有限秩可行边界](figures/rank_feasibility.png)

![真实外发RF](figures/release_privacy.png)
'''
    text('group_meeting_mmfopd_v3.md',meeting)
    text('REPRODUCE.md','''# Reproduce without overwriting evidence

Requires the same CogniGuard project, installed NumPy/scikit-learn/PyTorch/transformers/matplotlib, existing offline Qwen tokenizer, and the existing authorized OULAD2013J cache with its recorded SHA256. No dataset/model download command is part of this run. The earlier frozen source/metadata under the referenced experiment directories is required. Vendor MIT code is copied locally fromv2.

Do not run over this evidence directory. Copy only the Python source files into a NEW immediate child directory of experiments, with a new name. Do not copy generated protocol/locks/results/vendor; freeze.py creates those dependencies. In PowerShell, with the new directory as $v3ReplayDir, run:

```powershell
$env:PYTHONHASHSEED = '20261020'
python "$v3ReplayDir/freeze.py"
python "$v3ReplayDir/phase_b.py"
# Stop if phaseB_gate.json says false.
python "$v3ReplayDir/phase_c.py"
python "$v3ReplayDir/derive_validate.py"
python "$v3ReplayDir/build_reports.py"
```

package_sync.py is the one-time publication script for the original new subtree; do not run it for a reproduction, as it refuses existing remote evidence destinations. A reproduction should keep a separate receipt and source hashes, never overwrite the original files or prior test sets. Individual outputs/targets/attribute truth/probabilities stay local in *_LOCAL.json and are not in the public package. Public results alone are not a substitute for the original authorized cache for refitting.

Frozen protocol precedes new fits; phaseB/C locks hash executed code. Internal validation is a student-disjoint subset of outer training, and all source projection/attack models are refitted there for rank selection. Outer development never tunes rank. 2014J is neither loaded nor reused for search. All stages stop on violated preconditions rather than adapting thresholds.
''')
    text('README.md','''# MM-FOPD v3 /2026-10-20

Decision: PIVOT. Start with group_meeting_mmfopd_v3.md and mmfopd_v3_interface_audit.md. Interface regression passed; all chosen privacy projectors have rank0 under frozen inner-validation constraints. No independent test.

The source family preserves a train-only linear teacher direction; nonzero rank probes retain task MAE but violate the inner distortion budget. In3D, rank2 is exactly ordinary teacher-score compression, verified against actual wires. This is a negative result, not a new proven privacy algorithm.

90 ablation rows include12 explicitly declared duplicate aliases;364 privacy-utility rows include4 public-only attacks. Raw total78 method/context cells reuse38 distinct actual-input fits. Repeated contexts/snapshots are not independent students. *_LOCAL.json and student records are excluded; mathematical transforms, aggregate results, frozen source hashes and vendor MIT license are public. See REPRODUCE.md; do not overwrite execution locks.
''')
    c.save('decision.json',{'decision':'PIVOT','phaseA':'COMPLETED_READ_ONLY','phaseB':'INTERFACE_GATE_PASSED6_OF6','phaseC':'COMPLETED_SINGLE_FROZEN_FAMILY','phaseD':'STOPPED_NO_ELIGIBLE_NONTRIVIAL_SUCCESS',
        'A':'implemented empirical TaskLoss eligibility; not a population guarantee, epsilon nonbinding here',
        'B':'no selected actual release privacy gain; rank0 equals Identity',
        'C':'selected Identity satisfies utility; nonzero diagnostics keep MAE but violate inner distortion',
        'D':'no independent advantage; rank2 exactly teacher-score compression, nonorth reference degenerates Identity',
        'E':'not supported as a validated core MM-FOPD mechanism','new_test_run':False,'search_after_results':False})
    (P/'figures').mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':140})
    labels=[i[:4]+'\n'+('explicit' if w=='explicit' else 'ambig.') for i,w in contexts];x=np.arange(6)
    oldv2=c.load(c.V2/'summary_results.json')
    fig,ax=plt.subplots(figsize=(11,5),layout='constrained')
    ax.plot(x,[g['same_source_cached_raw_MAE'] for g in phaseb['cells']],marker='o',label='Historical raw SafeTaskTopK',color='#555555')
    ax.plot(x,[next(z['MAE'] for z in oldv2 if z['method']=='Att+Identity' and z['intent']==i and z['wording']==w) for i,w in contexts],marker='s',label='Historical v2 three-number Identity (no separate flags)',color='#a25b43')
    ax.plot(x,[row('Identity',i,w)['MAE'] for i,w in contexts],marker='^',label='v3 unified Identity with explicit missing flags',color='#3b648e')
    ax.set_xticks(x,labels);ax.set(xlabel='Frozen task context',ylabel='MAE (score points)',title='Interface regression:6 components,49 tokens; same3 source fields\n473 snapshots /166 students; historical interfaces are not privacy causal controls');ax.legend(fontsize=8);ax.grid(axis='y',alpha=.18)
    fig.savefig(P/'figures/interface_regression.png');plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    axs[0].plot(x,r1dist,marker='o',label='Rank1 (inner validation)',color='#3b648e');axs[0].plot(x,r2dist,marker='s',label='Rank2 (inner validation)',color='#a25b43');axs[0].axhline(.2,ls='--',color='black',label='Frozen delta0.20')
    axs[0].set(title='Nonzero ranks rejected before outer development',ylabel='Relative squared value distortion (unitless)',xlabel='Frozen task context');axs[0].set_xticks(x,labels);axs[0].set_ylim(0,.7);axs[0].legend(fontsize=8)
    for m,color in [('Identity','#555555'),('OPP-v2-style','#a25b43'),('V3-rank1','#3b648e'),('V3-rank2','#477c6a')]:axs[1].plot(x,[row(m,i,w)['MAE'] for i,w in contexts],marker='o',label=m,color=color)
    axs[1].set(title='Teacher protection retains development task MAE',ylabel='MAE (score points)',xlabel='Frozen task context');axs[1].set_xticks(x,labels);axs[1].legend(fontsize=8)
    for ax in axs:ax.grid(axis='y',alpha=.18)
    fig.suptitle('One frozen rank family; r0 selected for every context\nInner validation108 students; outer development166 students; no rank tuning on outer data')
    fig.savefig(P/'figures/rank_feasibility.png');plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for ax,attr in zip(axs,c.ATTRS):
        for m,color in [('Identity','#555555'),('V3-rank1','#3b648e'),('V3-rank2','#a25b43')]:
            ys=[next(z['AUC'] for z in a if (z['method'],z['intent'],z['wording'],z['attribute'],z['attacker'])==(m,i,w,attr,'RF')) for i,w in contexts]
            ax.plot(x,ys,marker='o',label=m,color=color)
        ax.axhline(next(z['AUC'] for z in bg if z['attribute']==attr and z['attacker']=='RF'),color='black',ls='--',label='Public-only RF')
        ax.set_xticks(x,labels);ax.set(title=attr+' : actual wire + public',xlabel='Frozen task context',ylabel='RF ROC AUC (unitless)');ax.grid(axis='y',alpha=.18);ax.legend(fontsize=8)
    fig.suptitle('No privacy benefit for selected V3 (exactly Identity); nonzero ranks are diagnostics\nSame49-token interface; AUC below a fitted public-only attack is not deletion of public knowledge')
    fig.savefig(P/'figures/release_privacy.png');plt.close(fig)
    import sklearn,torch,transformers
    c.save('environment.json',{'python':platform.python_version(),'platform':platform.platform(),'numpy':np.__version__,'sklearn':sklearn.__version__,'torch':torch.__version__,'transformers':transformers.__version__,'random_seed':20261020,'paid_calls':0,'personal_paths_included':False})
    print(json.dumps({'status':'REPORTS_BUILT','decision':'PIVOT','requested_deliverables':6,'figures':3,'narration_chars':len(narration),'rank2_teacher_equivalence_max_error':emax},indent=2))

if __name__=='__main__':main()
