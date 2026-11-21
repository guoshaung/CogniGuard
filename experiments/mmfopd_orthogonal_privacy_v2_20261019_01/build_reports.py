"""Build requested reports and scientific plots from completed measurements only."""
from pathlib import Path
import json,hashlib,inspect,platform,statistics
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).parent;ROOT=P.parents[1]
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def save(n,s):(P/n).write_text(s,encoding='utf8')
def table(headers,rows):return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(str(x) for x in row)+' |' for row in rows)+'\n'
def mean(xs):return float(np.mean(list(xs)))
def fmt(x):return f'{x:.3f}'

def main():
    s=load('all_method_results.json');a=load('attack_results.json')+load('field_anchor_attacks.json');internal=load('internal_attacks.json');paired=load('paired_changes.json');math=load('projection_checks.json');cohort=load('cohort.json');gate=load('phaseC_gate.json')
    assert not gate['any_passed']
    summaries=[x for x in s if x['interface']=='three_numeric_summary']
    methods=list(dict.fromkeys(x['method'] for x in s));summary_methods=list(dict.fromkeys(x['method'] for x in summaries))
    contexts=[(i,w) for i in ['trajectory','engagement','readiness'] for w in ['explicit','ambiguous']]
    def sm(m,i,w):return next(x for x in s if (x['method'],x['intent'],x['wording'])==(m,i,w))
    def attack(m,attr,k):return mean(x['AUC'] for x in a if x['method']==m and x['attribute']==attr and x['attacker']==k)
    def metric(m,key):return mean(x[key] for x in s if x['method']==m)
    def im(m,scope,attr,k):return next(x for x in internal if (x['method'],x['scope'],x['attribute'],x['attacker'])==(m,scope,attr,k))
    all_table=table(['接口','方法','MAE↓','真实Token','来源槽契约Recall*','来源槽缺失率*','性别RF AUC','残疾RF AUC'],
       [[('原字段' if '+' not in m else '数值摘要'),m,fmt(metric(m,'MAE')),fmt(metric(m,'actual_tokens_mean')),fmt(metric(m,'source_slot_contract_recall')),fmt(metric(m,'source_slot_missing_fraction')),fmt(attack(m,'gender_F','RF')),fmt(attack(m,'disability_Y','RF'))] for m in methods])
    privacy_table=table(['方法','性别LR AUC/BA','性别RF AUC/BA','残疾LR AUC/BA','残疾RF AUC/BA'],
       [[m]+[fmt(attack(m,attr,k))+'/'+fmt(mean(x['BA'] for x in a if x['method']==m and x['attribute']==attr and x['attacker']==k)) for attr in ['gender_F','disability_Y'] for k in ['LR','RF']] for m in ['Public']+summary_methods])
    factorial=table(['任务/表述','均无：固定MI3','仅Attention','仅OPP','Attention+OPP','投影ΔMAE','投影实际回复变更'],
       [[i+'/'+w]+[fmt(sm(m,i,w)['MAE']) for m in ['NoAtt+Identity','Att+Identity','NoAtt+OPP','Att+OPP']]+[fmt(sm('Att+OPP',i,w)['MAE']-sm('Att+Identity',i,w)['MAE']),'473/473'] for i,w in contexts])
    internal_table=table(['内部表示','性别LR AUC/BA','性别RF AUC/BA','残疾LR AUC/BA','残疾RF AUC/BA'],
       [[m]+[fmt(im(m,'z_only',attr,k)['AUC'])+'/'+fmt(im(m,'z_only',attr,k)['BA']) for attr in ['gender_F','disability_Y'] for k in ['LR','RF']] for m in ['Identity','OPP','INLP3','LEACE']])
    geometry=table(['算子','秩/26','对称误差','幂等误差','训练cross-cov范数','开发平方失真'],
       [[m,math[m]['rank'],f'{math[m]["symmetry_frobenius"]:.2e}',f'{math[m]["idempotence_frobenius"]:.2e}',f'{math[m]["train_crosscov_frobenius"]:.2e}',f'{100*math[m]["dev_relative_squared_distortion"]:.2f}%'] for m in ['Identity','OPP','INLP3','LEACE']])
    # Function index from actual saved files, not estimated line numbers.
    names={'privacy_core.py':['class ProfileEncoding','def fit','def transform','def crosscov','def fit_projections','def apply_transform','def verify'],
           'run_dev.py':['def fit_attack','def wire','def parsed_view','def attention_slots','def run'],
           'vendor/concept_erasure/leace.py':['class LeaceEraser','def __call__','class LeaceFitter','def eraser']}
    indices=[]
    for path,patterns in names.items():
        lines=(P/path).read_text(encoding='utf8').splitlines()
        for pattern in patterns:
            ix=next((i for i,l in enumerate(lines,1) if l.strip().startswith(pattern)),None)
            if ix:indices.append({'path':path,'symbol':pattern,'line':ix,'sha256':hashlib.sha256((P/path).read_bytes()).hexdigest()})
    save('code_paths.json',json.dumps(indices,indent=2))
    code='\n'.join(f'- `{x["path"]}:{x["line"]}`：`{x["symbol"]}`。' for x in indices)
    dims=load('representation.json')['dimensions']
    dimension_table=table(['原始字段','标准化数值坐标','标准化缺失指示坐标'],[[x['meaning'].split(':',1)[1],x['index'],x['index']+13] for x in dims[:13]])
    ln_source=load('reference_sources.json')
    narration='本轮把任务相关性与隐私抑制分开：Attention只选教学相关坐标，敏感子空间仅用训练学生估计，再将投影摘要真实外发。开发集结果表明，正交数学性质成立，线性内部攻击接近随机，但非线性与公开背景泄露仍在；六个任务的教学误差全部上升，未通过预设门槛。建议停止扩量，保留简单安全Top-K与可解释任务选择，撤回旧投影的隐私解耦表述。'
    failure=f'''# MM-FOPD v2：失败、残留泄露与接口限制

结论：**PIVOT**。完成一次冻结开发验证后停止，没有为AUC下降更换数据、攻击器、参数或测试集。

## 成功执行，不等于获得安全效用收益

- OPP严格作用于连续画像：26维，训练cross-cov范数0.18037→{math['OPP']['train_crosscov_frobenius']:.3e}；对称、幂等及敏感方向残留约1e-15。开发内部向量473/473变化；六个任务的实际三坐标回复也各473/473变化，Token都为26，证明不是内部空算。
- 仅内部z、不含背景时，性别LR AUC {im('Identity','z_only','gender_F','LR')['AUC']:.3f}→{im('OPP','z_only','gender_F','LR')['AUC']:.3f}，BA {im('Identity','z_only','gender_F','LR')['BA']:.3f}→{im('OPP','z_only','gender_F','LR')['BA']:.3f}。这是指定训练协议下的线性攻击结果，不能替代真实接收者安全性。

## 失败案例一：被擦掉线性均值方向，非线性信号仍在

内部z的性别RF AUC仍为{im('OPP','z_only','gender_F','RF')['AUC']:.3f}、BA {im('OPP','z_only','gender_F','RF')['BA']:.3f}；加上共同公开背景后RF AUC={im('OPP','z_plus_public','gender_F','RF')['AUC']:.3f}。性别公开背景LR/RF AUC本身为{attack('Public','gender_F','LR'):.3f}/{attack('Public','gender_F','RF'):.3f}，投影无权擦除接收者原本已知的课程/日程信息。不能把某个增强攻击器AUC低于背景单独攻击器说成“删除了攻击者知识”。CSV同时报告带符号差及截断为非负的观察增量。

## 失败案例二：明确trajectory的实际攻击反而增强

相同摘要接口、相同26Token：Att+Identity→Att+OPP，MAE27.952→28.185，性别RF AUC0.826→0.846。学生聚类500次bootstrap的配对AUC差95%区间[0.00457,0.03805]（仅固定拟合模型下条件区间，未作多重比较校正）。不能因内部LR下降宣布该真实输出安全。

## 失败案例三：出现小幅泄露下降，但效用代价大且不确定

readiness/ambiguous残疾RF AUC差−0.03367，配对95%区间[−0.09434,0.02801]跨零；同时MAE21.527→28.514，增加6.987。dev只有20名残疾阳性学生、57个阳性快照，不能把重复快照视为57名独立学生。没有挑这个有利子项替代预设门槛。

## 失败案例四：摘要并非原始字段的等价接口

仅Identity、同一源字段集合时，明确trajectory的原始SafeTaskTopK MAE20.598，数值摘要MAE27.952。二者所有473例来源字段集合相同，但原字段回复携带NA/可用性；摘要只交付训练中位数填补后的三数值并舍入，缺失状态不再单独保留。此差异足以否定直接跨接口归因；尚未单独实验分离填补、缺失标识和舍入各自的贡献，不能将全部差值断言为某一个原因。投影的额外损害由摘要内Identity配对判断。

## 失败案例五：投影和任务坐标读出不匹配

Q_q仍读取原字段坐标，但P会把其他13字段及缺失维混合进来。OPP整体平方失真39.32%，三数值不再有“原字段事实”的含义；source-slot Recall只是读取位置的公共契约代理，真实事实Recall为NA。三摘要坐标不能假装等于三原字段的信息预算。INLP3移除12方向、秩14；OPP和LEACE移除2方向、秩24，参考方法不构成等擦除秩的公平优越性证明。

## 失败案例六：Attention不是新发现的强优势

无投影时，Attention在六个固定任务中仅2个MAE低于固定TrainMI3，其余4个更差；六情境均值21.279 vs19.368。投影后也未显示稳定互补。任务cosine/readout均来自现有公共元数据，可由普通TF-IDF Top-K复现。没有神经注意力或原创隐私投影的证据。

没有新模型训练/接口调参来补救上述失败。没有运行阶段C、旧2014J复测、跨任务/跨轮拼接攻击、成员推断、其他受保护属性或更强攻击器；不能对此声称安全。逐学生真实向量/回复/标签/预测只保留在本地`*_LOCAL.json`，公开材料只含聚合指标、公共槽位和算法参数。
'''
    save('mmfopd_v2_failure_cases.md',failure)
    report=f'''# MM-FOPD v2：任务Attention与敏感子空间投影分离

**决策：PIVOT。研究性开发实验已实际完成；不进入独立验证阶段。** 新投影符合数学定义并改变真实输出，但内部线性抑制没有转化为有可接受教学代价的实际泄露改善。不能将新结果归功于旧版角色投影，也不能称零空间擦除为原创。

## 真实执行与冻结边界

只使用现有OULAD2013J训练484名学生/1337快照，开发166名/473快照，学生不相交；三任务×明确/模糊共六个任务化情境反复使用同一473快照，不是2838个独立学生。训练/开发性别阳性学生231/77，残疾阳性45/20（开发阳性快照225/57）。已有2014J已被研究使用，本轮不读取其原始快照或新增模型评测，不叫盲测。数据来自Kuzilek、Hlosta、Zdrahal的[OULAD作者数据版本](https://doi.org/10.6084/m9.figshare.5081998.v1)，CC BY4.0；[数据论文](https://doi.org/10.1038/sdata.2017.171)。本地归档MD5沿用已核验7412686fd77cf0e0ee1e8c3e9b354308，未重新获取。

阶段A核查真实源码、旧攻击器、原字段输出，并以SHA256回读research-sync两份既有报告，见`prior_remote_readback.json`。确认原字段接口无法直接表达向量擦除后，阶段B采用用户允许的A路径，冻结`protocol.json`后才拟合。真实新增36个摘要方法情境、144个实际输出属性攻击、32个内部攻击、4个背景攻击及36个Ridge任务模型；INLP仅固定3轮，运行{load('completion.json')['seconds']:.1f}秒。另复用30个既有字段对照拟合，来源哈希完整保留；没有重跑旧模型。无失败、付费API或数据/模型下载；仅引入{ln_source['download_bytes_small_source_only']}字节MIT官方参考源码并保留许可证。

`execution_lock.json`锁定方案/运行代码/画像代码哈希；`validation.json`核验12个既有源/证据文件未变、官方参考源码未变、288次实际wire精确复算、12例翻转开发属性/成绩/ID后推理不变。没有生产代码、历史结果或冻结测试集修改。

## 新旧算法区别与成熟方法来源

旧Repaired-Full的z是8维公共任务角色one-hot，`||P_task z||`只是0/1奖励，再统一加0.25；它不拟合敏感方向，最终还释放原字段值。本轮B1只作历史基线，B2-FIELD仅删除这个角色奖励，仍保留旧成本/Slot/子集策略；不能说它已换成了新的隐私投影。

本轮新增的**敏感协方差正交投影OPP**是成熟概念擦除的应用，数值上等同官方LEACE库`method="orth"`，没有算法原创差异。[INLP](https://arxiv.org/abs/2004.07667)通过迭代线性预测与零空间求交；本轮忠实实现其自回归求交核心，固定三轮、联合四类标签，不称完整论文基准复现。[LEACE](https://arxiv.org/abs/2306.03819)提供闭式概念擦除；本轮采用[官方MIT实现](https://github.com/EleutherAI/concept-erasure)，所有源码SHA与许可证随证据保留。LEACE一般为斜投影，不能要求它也满足欧氏对称性。上述工作均已有，不将“正交”“零空间”当本研究创新。

## 连续画像、数学定义与职责

13个输入都是旧共同硬安全门允许的教育行为/成绩历史字段；禁止直接输入画像z的有ID、性别、残疾、未来成绩、公开课程和日程。数值缺失用训练中位数填补，另拼13个缺失指示，26维各自用训练均值与标准差标准化；零方差维的尺度设1。没有大型模型或在测试上学习表示。

{dimension_table}

每个数值维的单位来自原字段定义：成绩/成绩差为分，completion_rate及forum/content_share为比例，clicks为次数，active/inactive为天数，previous_attempts为次数、studied_credits为学分。数值标准化后无量纲；缺失维原值为0/1，再训练标准化。`representation.json`包含每维精确训练中位数/均值/尺度，8个训练恒定缺失指示维仍保留，不伪装为26个独立信息维。

令S为训练行的两个二值属性列，C=Cov_train(z,S)。对C做SVD，保留奇异值>1e−10的左奇异向量为U_s，验证U_sᵀU_s=I。P_priv=I−U_sU_sᵀ，z_priv=P_priv(z−μ_z)+μ_z（代码采用行向量等价转置）。OPP移除两个训练敏感均值相关方向；仅这有限样本线性约束成立，不是统计独立、互信息为零或跨域隐私保证。

Attention只使用现有公共任务/字段元数据TF-IDF cosine，得到u_i(q)，读出Top3数值坐标Q_q；没有敏感成本、角色奖励或敏感预测器参与效用打分。NoAtt使用旧训练集MI排名前三latest_score/inactive_days/clicks_recent，保持强固定选择而非随机弱基线。输出r=round₃(Q_q z_priv)，实际wire为c0/c1/c2三行数值；下游预测器、攻击器只读取**解析后的真实wire及共同公开背景**。训练标签和攻击器预测不进入wire。

Bottleneck只限制3个摘要标量及Qwen真实Token≤64，不再计算效用/隐私惩罚或覆盖选择；Hard Gate限制共同13安全源字段、敏感门限0.7、禁止直接输出受保护属性及标识。TaskSlot保留为原字段强基线；未在摘要中强行补“原字段事实”，四格摘要消融共享同一门与预算。

机制B未实现：没有经验证的“投影距离→某原字段释放风险”映射，不能用内部向量改变给原样字段输出背书，也没有把向量伪装成自然语言。

## 数学与接线检查：通过，但不足以证明保护

{geometry}

OPP的U正交归一误差{math['OPP']['U_orthonormality_frobenius']:.3e}，||PU||={math['OPP']['sensitive_direction_residual_frobenius']:.3e}，与官方orth矩阵最大差{load('projection_fit.json')['official_orth_max_abs_difference']:.3e}。所有473开发向量改变，六情境的473条摘要均实际改变；读出槽位保持不变是职责分离的设计：OPP改变内容值，Attention决定Q，后续没有Slot/Bottleneck吞掉差异。预测变更率见`paired_changes.json`，实际Token始终26。LEACE非对称误差为正常斜投影性质；INLP3有三轮共12个独立行空间方向，不是三维擦除。

## 方法对照与预算公平性

B0=SafeTaskTopK；B1=旧Repaired-Full；B2-FIELD=旧no-role-projection（与B1仅角色奖励不同）；B2-SUMMARY=Att+Identity；B3=NoAtt+OPP；B4=Att+OPP；B5=Att+INLP3及Att+LEACE；B6=NoAtt+Identity。额外保留TaskSlot、TrainMI原字段强基线。只有摘要四格在相同接口内可解释为Attention/OPP单因素变化。新OPP与官方orth相同，无需重复一条伪独立基线。

{all_table}

以上是六个固定情境等权均值，分母每情境473快照/166学生，均值不是新增样本。*来源槽契约Recall只是公共所需字段集合与读出槽位置重合的代理；摘要的真实事实Recall=NA，投影后的坐标已经混合，不能声称释放了对应事实。摘要来源槽缺失率仍报告，实际输出始终有限数值而物理缺失为0，不能把中位数填补称为恢复知识。

所有方法输入同一安全候选池/公开背景、同一64Token上限及3个输出位置。但摘要可能混合全部13源字段及缺失维，原字段最多释放3事实，因此**不是相同信息量或实际长度的字段选择公平试验**。摘要实际均26Token，原字段约15–18Token；不填无意义文本凑长。旧原字段还提供NA/availability特征，Identity摘要没有独立缺失标识。不能跨这两组宣称投影因果收益或获胜。新摘要只能由数值预测器消费，未验证LLM教学解释、事实可读性或自然语言接口。

同一学生划分、下一TMA目标、Ridge(alpha10, lsqr)、训练DictVectorizer/StandardScaler(with_mean=False)、预测裁剪[0,100]。LR为C1 balanced/liblinear，RF为64树/depth6/minleaf5/balanced_subsample，种子20261020，不为投影选弱攻击器。公开背景是课程、cutoff、距已公布下一deadline天数；不含学生ID或受保护属性。内部z与z+背景分开训练攻击；实际释放攻击只见wire+背景。INLP3用联合四类、OPP/LEACE用两个二值列，虽标签来源相同，保护函数和擦除秩不同，不作等复杂度优势结论。

## 严格四格消融：六情境均没有可接受投影收益

{factorial}

相同摘要接口下，OPP使Attention条件的MAE六情境均上升，范围0.233–9.833分，均值+{metric('Att+OPP','MAE')-metric('Att+Identity','MAE'):.3f}；固定MI3下也增加{metric('NoAtt+OPP','MAE')-metric('NoAtt+Identity','MAE'):.3f}。仅Attention比固定MI3在2/6情境改善，不能称稳定互补或优于简单规则。分阶段42/98/154天的真实MAE见`stage_results.json`，复用同一拟合，没有另做阶段调参。

## 属性推断：内部与实际输出分开

先看**仅内部z**，未给公共背景：

{internal_table}

再看**真实三数值wire+公共背景**；AUC/BA为六情境均值，Public只拟合一次：

{privacy_table}

OPP实际性别RF均值{attack('Att+Identity','gender_F','RF'):.3f}→{attack('Att+OPP','gender_F','RF'):.3f}，未降低；残疾RF均值{attack('Att+Identity','disability_Y','RF'):.3f}→{attack('Att+OPP','disability_Y','RF'):.3f}，小幅下降且不是稳定隐私保证。内部z+背景的性别RF AUC={im('OPP','z_plus_public','gender_F','RF')['AUC']:.3f}。线性擦除不消除非线性或接收者公开知识。每属性/攻击器BA、AUC、Accuracy、相对背景增量、方法效用和Token详见300行CSV；旧字段拟合未保存Accuracy，标NA并说明，未编造准确率。

`paired_changes.json`对同一学生组做500次配对bootstrap，仅固定模型条件下的队列区间；不是完整训练不确定性、不是独立复现实验、未校正多重比较。残疾阳性仅20名学生，不能把小数点差异当确定改善。实际攻击器在增强视图上可表现更差，但理性接收者能忽略摘要，故不把负增量当作删掉背景信息；额外报告max(0,增强AUC−背景AUC)作为观察性非负增量。

## 指标与分母

- 任务MAE：473个快照的下一预定TMA成绩误差；未及时提交构造0分，非真实干预效果。observed_grade_MAE只在339个有及时实际分数的开发快照计算。三任务共用同一成绩目标，未验证各教学任务的独立行为效度。
- BA=(TPR+TNR)/2；AUC为二值属性ROC AUC；Accuracy=正确预测/473。开发性别阳性225/473、残疾57/473，对应独立学生77/166、20/166。字段基线Accuracy未记录则NA。
- 来源槽契约Recall=|Q与预定义3个所需字段交集|/3，按快照平均；不是教师双人标注真值。缺失率=来源槽中原始None数量/(473×3)。投影混合摘要的事实Recall不可定义，置NA。
- Token用本地现有Qwen tokenizer对wire逐条计数，无padding；3摘要标量与3字段位置分开。内部26维攻击从未当作释放内容，Token/MAE为NA。
- 输出/预测变更与内部变更均对同一473快照逐例配对；六情境没有增加独立学生。失败数为运行或约束失败数，本轮0；没有拒答/丢弃样本获得优势。
- CSV中的延迟是已缓存投影结果后的批量序列化/分词/解析摊销wall-clock，未含画像编码、投影矩阵乘法、模型推理和首次Attention模板构建；完整在线单条推理延迟未测，旧缓存selector延迟不可横比。投影拟合{load('projection_fit.json')['projection_fit_seconds']:.3f}秒，仅作本机资源记录，不声称在线加速。

## 证据支持什么、不能支持什么

支持：旧角色奖励与敏感擦除职责不同；新OPP是实际非空投影且真实改变接收内容；指定线性内部攻击下降；非线性/背景残留与教学损失可测；现接口下没有获得预设安全效用收益。失败案例文件保留有利和不利子项，不只展示AUC下降。

不支持：旧MM-FOPD已实现敏感解耦；新OPP原创；投影比INLP/LEACE更好；三个摘要等价三个字段；统计独立/零互信息/差分隐私；跨域、跨轮、跨任务联合输出安全；自然语言教学有效；已达到论文最终独立主证据。成绩可见时间使用既有lag代理、没有真实发布时间，开发7/473下一TMA已被提前提交；本轮不改协议掩盖这一限制。自编任务契约未经独立教师确认。

预先门槛要求实际payload改变、至少一属性LR AUC下降≥.02、同属性RF AUC恶化≤.02、MAE增幅≤2，至少一个情境同时满足；结果**0/12属性情境通过**。因此阶段C停止：不申请独立验证、不动已看2014J、不调参凑改善。

建议保留透明SafeTaskTopK/TrainMI及任务相关选择作为强基线，删除旧冗余角色奖励的敏感解耦表述；本次协方差投影+三坐标摘要只保留为负结果研究分支，LEACE/INLP为参考对照。尚无证据将新投影放回正式核心。

唯一值得继续的问题：**在相同真实输出接口及教学误差上限内，能否降低相对于公开背景的非线性增量属性泄露？** 本轮不继续实现或搜索。

## 真实函数与行号

以下路径均相对本独立实验目录，完整SHA见`code_paths.json`；原版真实路径保留在上一轮诊断报告。

{code}

## 图与复核入口

![四格消融](figures/v2_factorial.png)

![内部与真实输出攻击](figures/internal_vs_release.png)

![不同输出接口的效用与属性攻击](figures/privacy_utility.png)

图全部读取已完成指标；相同学生反复情境无误差条伪精度。`validate_derive.py`只复算wire与派生统计，不新增训练。真正重跑须把实验分支复制到新目录，先在`setup.py`/`protocol.json`相同冻结条件下使用本地原缓存，禁止覆盖本目录的execution_lock与结果。公开包不含逐学生数据，需已有授权OULAD缓存和原项目才能复现模型。
'''
    save('mmfopd_orthogonal_privacy_v2.md',report)
    meeting=f'''# 2026-10-20组会：MM-FOPD职责分离开发实测

**PIVOT：停止当前三坐标正交摘要扩量，保留负结果。阶段C未启动。**

本轮实际运行：484训练学生/1337快照，166开发学生/473快照；三任务×明确/模糊六情境。新增36方法情境、144实际输出攻击、32内部攻击、4背景攻击；另复用30个既有字段对照。无付费调用、无数据/模型下载；正式核心、历史与2014J保留集未改/未读。EXPLORATORY，不能称论文确认性独立测试。

## 旧方法与新分支

旧角色one-hot投影仅给任务匹配加0.25，不能归功为敏感擦除。新分支用训练安全字段数值+缺失共26维，估计性别/残疾协方差方向并正交删除；Attention只做公共元数据TF-IDF相关性读出。投影后真实外发三个数值，攻击者从解析后的wire+公共背景学习。采用成熟INLP/LEACE作参考，不宣称零空间新算法。

## 方法均值：必须区分两种接口

{all_table}

六情境等权均值；不是新增2838名学生。来源槽Recall为公共契约代理；混合摘要的真实知识事实Recall=NA。摘要可能混合13源字段，不等价3原字段信息预算。原字段回复15–18Token，摘要均26Token，全部<=64；不作跨接口投影因果结论。

## 摘要内部严格四格：MAE越低越好

{factorial}

投影六情境全部使MAE变差，平均+{metric('Att+OPP','MAE')-metric('Att+Identity','MAE'):.3f}分；单独Attention仅2/6优于固定TrainMI3，互补性未证明。不同阶段数据在stage_results.json，不据结果更改任务或划分。

## 关键证据

- 数学：OPP对称误差0，幂等误差1.07e−15，训练敏感cross-cov范数0.18037→2.35e−16；官方orth矩阵最大差4.58e−16。平方失真39.32%。
- 接线：每情境473/473实际回复改变，Token仍26；已排除只算内部不影响输出。
- 内部z性别LR AUC0.711→0.500，但RF仍0.737；加公共背景后RF0.848。实际摘要性别RF六情境均值0.836→0.844，不能称改善。
- readiness模糊任务残疾RF AUC下降0.034，95%配对区间跨零且MAE恶化6.987；开发仅20名残疾阳性学生。负结果和有利子项全部保留。
- 同源字段的Identity摘要已丢失独立NA/availability信息，明确trajectory MAE20.598→27.952；因此不能将跨接口差异都归给投影。真实投影效应在摘要内单因素对照。
- 预冻结门槛0/12属性情境通过，无新独立验证、无参数搜索。不是最终论文主证据，可作为撤回旧隐私解耦表述及简化模型的依据。

## 建议与唯一研究问题

保留透明SafeTaskTopK/TrainMI与可解释任务相关选择；旧角色奖励撤回敏感解耦命名，新投影只保留研究分支。唯一后续问题：在相同真实输出接口及教学误差上限内，能否降低相对公开背景的非线性增量属性泄露？

## 约150字讲解词

{narration}

![四格消融](figures/v2_factorial.png)

完整定义/分母/公平性/参考来源见mmfopd_orthogonal_privacy_v2.md；66行消融与300行隐私效用CSV均来自真实结果。公开材料只同步聚合指标、公共元数据、代码/哈希及许可证；逐学生回复、属性、目标和预测留本地。
'''
    save('group_meeting_mmfopd_v2.md',meeting)
    save('decision.json',json.dumps({'decision':'PIVOT','phaseA':'COMPLETED','phaseB':'COMPLETED_EXPLORATORY','phaseC':'STOPPED_FROZEN_GATE_FAILED',
        'new_algorithm_credit_to_old':False,'claim_novel_nullspace_algorithm':False,'eligible_attribute_contexts':12,'passed':0,
        'only_next_question':'在相同真实输出接口及教学误差上限内，能否降低相对于公开背景的非线性增量属性泄露？'},ensure_ascii=False,indent=2))
    save('README.md','''# MM-FOPD orthogonal privacy v2 / exploratory development

Start with group_meeting_mmfopd_v2.md. Decision: PIVOT; frozen development gate failed, no phaseC test.

Order: setup.py (already run once) -> run_dev.py (refuses overwrite) -> validate_derive.py -> build_reports.py -> package_sync.py.
Existing train/dev cache and offline Qwen tokenizer required; no new data/model downloads. Small official MIT LEACE source vendored with license. No production changes. Copy branch to a fresh experiment directory to reproduce; do not rerun setup over this frozen evidence or automatically acquire datasets.

The frozen protocol, source hashes and official-reference hashes precede new fitting. Public CSVs have 66 method-context rows and 300 visibility/attribute/attacker rows; internal and release attacks have separate scopes. Raw-field anchors reuse existing frozen fits, explicitly tagged. Summary and raw-field interfaces are not equal information/length budgets. Individual outputs and labels are local-only and excluded from synchronization.
''')
    (P/'figures').mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':140})
    colors={'Att+Identity':'#395b89','Att+OPP':'#b04c3d','NoAtt+OPP':'#8a6547','NoAtt+Identity':'#545454','Att+INLP3':'#7e6a96','Att+LEACE':'#447e70'}
    fig,axs=plt.subplots(2,2,figsize=(13,8),layout='constrained')
    labels=[i[:4]+'\n'+('explicit' if w=='explicit' else 'ambiguous') for i,w in contexts];x=np.arange(6)
    for m in ['NoAtt+Identity','Att+Identity','NoAtt+OPP','Att+OPP']:
        axs[0,0].plot(x,[sm(m,i,w)['MAE'] for i,w in contexts],marker='o',label=m,color=colors[m])
        for ax,attr in [(axs[0,1],'gender_F'),(axs[1,0],'disability_Y')]:
            ax.plot(x,[next(z['AUC'] for z in a if z['method']==m and z['intent']==i and z['wording']==w and z['attribute']==attr and z['attacker']=='RF') for i,w in contexts],marker='o',label=m,color=colors[m])
        axs[1,1].plot(x,[sm(m,i,w)['actual_tokens_mean'] for i,w in contexts],marker='o',label=m,color=colors[m])
    titles=['Teaching target MAE','Actual-release + public: gender RF AUC','Actual-release + public: disability RF AUC','Actual reply tokens: equal26, no padding']
    for ax,title,ylabel in zip(axs.flat,titles,['MAE (score points)','ROC AUC (unitless)','ROC AUC (unitless)','Tokens per reply (Qwen)']):
        ax.set(title=title,ylabel=ylabel,xlabel='Frozen task context');ax.set_xticks(x,labels);ax.grid(axis='y',alpha=.18)
    axs[1,1].set_ylim(24,28);axs[0,0].legend(fontsize=8)
    fig.suptitle('OULAD2013J development: strict2x2 summary ablation\n473 repeated snapshots /166 students per context; fixed fits, no independent test')
    fig.savefig(P/'figures/v2_factorial.png');plt.close(fig)
    fig,axs=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    for row,attr in enumerate(['gender_F','disability_Y']):
        for col,kind in enumerate(['LR','RF']):
            ax=axs[row,col]
            for name,m in [('Identity','Att+Identity'),('OPP','Att+OPP'),('INLP3','Att+INLP3'),('LEACE','Att+LEACE')]:
                ax.plot(range(3),[im(name,'z_only',attr,kind)['AUC'],im(name,'z_plus_public',attr,kind)['AUC'],attack(m,attr,kind)],marker='o',label=name,color=colors[m])
            ax.axhline(attack('Public',attr,kind),color='gray',ls='--',label='public-only')
            ax.set_xticks(range(3),['Internal26D','Internal26D\n+public','Actual3D reply\n+public (6-context mean)'])
            ax.set(title=attr+' / '+kind,ylabel='ROC AUC (unitless)',xlabel='Attacker-visible input');ax.set_ylim(.43,.92);ax.grid(axis='y',alpha=.18)
    axs[0,0].legend(fontsize=8)
    fig.suptitle('Internal linear erasure does not establish release privacy\nSame166 development students; actual summaries rounded to3 decimals /26 tokens')
    fig.savefig(P/'figures/internal_vs_release.png');plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    for ax,group,title in [(axs[0],[m for m in methods if '+' not in m],'Raw3-field anchors (cached fits)'),(axs[1],summary_methods,'Three numeric summaries (new fits)')]:
        for m in group:
            xs=[z['MAE'] for z in s if z['method']==m];ys=[next(z['AUC'] for z in a if z['method']==m and z['intent']==i and z['wording']==w and z['attribute']=='gender_F' and z['attacker']=='RF') for i,w in contexts]
            ax.scatter(xs,ys,s=22,label=m,alpha=.8)
        ax.axhline(attack('Public','gender_F','RF'),ls='--',color='gray',lw=1)
        ax.set(title=title,xlabel='Task MAE (score points; lower is better)',ylabel='Actual-release + public gender RF AUC');ax.legend(fontsize=7);ax.grid(alpha=.16)
    fig.suptitle('Privacy / utility: separate interfaces, not equal information budgets\n6 contexts on the same473 snapshots; common3-slot /64-token caps')
    fig.savefig(P/'figures/privacy_utility.png');plt.close(fig)
    import sklearn,torch,transformers
    save('environment.json',json.dumps({'python':platform.python_version(),'platform':platform.platform(),'numpy':np.__version__,'sklearn':sklearn.__version__,'torch':torch.__version__,'transformers':transformers.__version__,'neural_inference':False,'paid_calls':0},indent=2))
    print(json.dumps({'status':'REPORTS_BUILT_FROM_REAL_METRICS','decision':'PIVOT','requested_files':5,'plots':3,'source_index_count':len(indices),'narration_chars':len(narration)},indent=2))

if __name__=='__main__':main()
