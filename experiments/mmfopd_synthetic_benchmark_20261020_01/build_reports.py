from pathlib import Path
import json,csv,hashlib,collections,platform
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).parent;ROOT=P.parents[1]
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def write(n,s):(P/n).write_text(s,encoding='utf8')
def table(h,rows):return '| '+' | '.join(h)+' |\n| '+' | '.join(['---']*len(h))+' |\n'+'\n'.join('| '+' | '.join(map(str,row))+' |' for row in rows)+'\n'
def f(x):return f'{float(x):.3f}'
def main():
    s=load('summary.json');a=load('attribute_inference.json');validation=load('analysis_validation.json');trace=load('component_trace_audit.json');old=load('historical_144_reaggregation.json')
    with (P/'strict_ablation.csv').open(encoding='utf-8-sig',newline='') as file:paired=list(csv.DictReader(file))
    primary=[x['method'] for x in old]+['SafeTaskTopK','RelevanceCostRule']
    def sr(m,k=3):return next(x for x in s if x['method']==m and x['K']==k)
    def ar(m,attr,kind='RF',scope='actual_release',k=3):return next(x for x in a if (x['method'],x['K'],x['attribute'],x['attacker'],x['scope'])==(m,k,attr,kind,scope))
    full=sr('MM-FOPD');safe=sr('SafeTaskTopK');rule=sr('RelevanceCostRule')
    main_table=table(['方法(K≤3)','必要Recall','Precision','F1','可执行完成率 [双向95%]','字段/Token','加权暴露','高敏选择占比'],
        [[('FullProfile-budgeted' if m=='FullProfile' else m),f(sr(m)['Recall']),f(sr(m)['Precision']),f(sr(m)['F1']),f(sr(m)['completion'])+' ['+f(sr(m)['completion_two_way95_low'])+','+f(sr(m)['completion_two_way95_high'])+']',f(sr(m)['fields'])+'/'+f(sr(m)['tokens']),f(sr(m)['weighted_privacy_exposure']),f(sr(m)['high_sensitive_selection_ratio'])] for m in primary])
    inference=table(['方法(K≤3)','性别LR AUC/BA','性别RF AUC/BA','残疾LR AUC/BA','残疾RF AUC/BA'],
        [[m]+[f(ar(m,attr,k)['AUC'])+'/'+f(ar(m,attr,k)['BA']) for attr in ['gender_F','disability_Y'] for k in ['LR','RF']] for m in primary])
    abl_rows=[]
    for m in ['MM-no-projection','MM-no-attention-strict-uniform','MM-no-bottleneck','MM-no-taskslot','SafeTaskTopK','MM-no-attention']:
        p=next(x for x in paired if x['method']==m and x['K']=='3');z=sr(m)
        abl_rows.append([m,f(z['completion']),f(z['F1']),f(z['fields']),f(p['wire_change_rate']),f(p['delta_completion'])+' ['+f(p['delta_completion_two_way95_low'])+','+f(p['delta_completion_two_way95_high'])+']',('复合旧回退，不能归因' if m=='MM-no-attention' else ('补充严格复算' if m.endswith('uniform') else '相同外部预算'))])
    ablation=table(['对照','完成率','F1','字段数','回复变化率','相对Full完成差 [双向95%]','解释'],abl_rows)
    stats={split:load('data/'+split+'/statistics.json') for split in ['train','dev','test']}
    stats_table=table(['划分','合成学生','任务实例','每人任务','用途'],[['train',2500,5000,2,'属性攻击拟合'],['dev',500,1000,2,'仅开发/调试；内部350/150学生验证攻击流程'],['test',2000,10000,5,'冻结后一次评估；不调参'],['合计',5000,16000,'—','主评估实例为10000，另有6000训练/开发']])
    schema=[]
    import truth
    for ti,name in enumerate(truth.TYPES):
        for variant in range(4):schema.append({'family':name+':v'+str(variant),'static_inputs':truth.INPUTS[ti][variant],'active_public_parameters':list(truth.PARAMS[ti][variant]),'truth':'executable conditional teaching decision, instrumented dynamic read trace; no selector scores'})
    (P/'task_family_catalog.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2),encoding='utf8')
    groups=[]
    with (P/'group_results.csv').open(encoding='utf-8-sig',newline='') as file:groups=list(csv.DictReader(file))
    grouped=table(['分组','实例数','MM完成率','Safe完成率','规则完成率'],
        [[g['group'],g['n_tasks'],f(g['completion']),f(next(x['completion'] for x in groups if x['category']==g['category'] and x['group']==g['group'] and x['method']=='SafeTaskTopK' and x['K']=='3')),f(next(x['completion'] for x in groups if x['category']==g['category'] and x['group']==g['group'] and x['method']=='RelevanceCostRule' and x['K']=='3'))] for g in groups if g['K']=='3' and g['method']=='MM-FOPD' and g['category'] in ['type','difficulty']])
    codepaths=[]
    for n,patterns in {'truth.py':['def execute'],'generator.py':['def profile','def generate'],'engine.py':['def config','def release','def choose','def view'],'evaluate.py':['def run'],'frozen/profile_selector.py':['def select_enhanced'],'strict_attention_audit.py':['def uniform_attention'],'attacks.py':['def run']}.items():
        lines=(P/n).read_text(encoding='utf8').splitlines()
        for pat in patterns:
            line=next(i for i,l in enumerate(lines,1) if l.strip().startswith(pat));codepaths.append({'path':n,'symbol':pat,'line':line,'sha256':hashlib.sha256((P/n).read_bytes()).hexdigest()})
    (P/'code_paths.json').write_text(json.dumps(codepaths,indent=2),encoding='utf8')
    audit='''# 历史实验审计与本轮复现边界

原数据位于experiments/datasets/mmfopd_v3_suite/mixed_math_suite/student_profile/data_expanded：270个合成画像，原任务文件720条（432训练/144开发/144测试），历史144测试来自54名学生而非144名独立学生。profiles均50字段，expand_profiles.py只是追加循环类型随机历史记录并原样复制问题文件，没有扩充学生或独立任务结构。上游build_math_datasets.py::_build_profiles按问题知识点为学生创建mastery/error_pattern/preference三类核心记录，再加状态、行为等；原问题来自公开数学题，不能把全部720文本称为自编合成教学类型。本轮不复制这些题文。

八方法真实入口experiments/mmfopd_v3/baselines.py；runner.py::_metrics将mastery/error_pattern/preference对应的三单元固定设为必要真值，与原MM后处理的allowed单元结构一致。unit_precision主要看选中的单元是否在同知识点画像中，不能等同本次任务真正必要Precision。CardLen为字符/长度代理，旧报告没有逐条真实Token。本轮用32个独立教学程序的真实输入读迹定义必要信息，用实际解析回复执行程序验证输出，未读MM打分生成答案。

旧FullProfile释放50字段、其他多为3，LLM proxy为2，因此旧八方法表并非相同字段预算。旧DP函数是种子化指数式抽样并原样释放所选值，缺少整个输出机制的DP证明；Privacy Funnel仅线性相关度减敏感成本，并非求解互信息目标；GPG/PAPILLON/LLM名称均为适配器/代理。本轮保留原函数及限制，不称官方复现，也没有实际LLM或外部API调用。名为mmfopd_attribute_attack_20261008的目录仍是上述字段proxy表，未发现LR/RF AUC列。

原组件实现的耦合：去orthogonal还会取消部分安全门；去bottleneck同时跳过语义TaskSlot补齐；去Attention会把归一化权重替换为未归一化baseline score，并从Top8变成全部候选。即使旧表平均字段数都为3，也不能排除这些混杂。此前其他UCI实验出现6vs3，不能直接说本144条也存在该数值差异。

本轮仅复制源码到frozen：固定MM所有消融的敏感门.7；让TaskSlot独立于bottleneck启用；no-taskslot仅关闭整个语义补齐/最少两条回填阶段；统一外部K和实际Token限制。开发1000条×3预算的Full输出与原快照同预算结果3000/3000相同。生产及历史文件未改。

对于旧no-attention，原行保留但标复合回退。源码后续审查锁定了补充均匀权重1/N、保留Top8的单函数干预；其他开关全部保持Full。训练15000次、测试30000次实际wire复算均与Full一致，攻击器和置信区间按完全相同输入合法复用；它是补充机制审查，不能冒称最初预注册的独立确认性结果。相关锁、代码及时间边界完整保留。

开发问题均保留：第一版生成器的查询带未使用参数，正式前已删除；配置加载器不必要导入旧整条流水线，改为只读FOPD配置，参数不变；元组经JSON变数组导致开发执行器一致性检查失败，已统一规范化，保留失败尝试。最终测试生成前还移除“有效输入必须唯一”的致命断言，保留有限域独立抽样碰撞；没有去重、替换或拒绝采样。final_freeze_v1_pretest、pretest_amendment及最终freeze同时保留；该改动发生在任何train/test生成前。

当前测试已经一次生成/运行，未因MM落后改样本、难度、规则、种子或参数。本轮算法是历史MM字段选择器的严格实验副本，并非此前v2/v3数值隐私投影；不能把本轮结果归功或追溯到那些新分支。所有观察只属于受控合成基准。
'''
    write('historical_audit.md',audit)
    datareport=f'''# 大规模合成教育隐私基准数据报告

{stats_table}

原270名、144条测试的历史文件未覆盖。本轮5000名均为独立种子生成的虚构学生，不含真实学生、真实姓名、联系方式、图像或生物特征；每位有5–40期学习事件、8知识主题掌握、学习行为与两个模拟受保护标签。源候选每实例31–37字段，历史长短和有效输入随学生/情境变化。性别与残疾标签及代理相关系数为人为压力参数，不代表现实人群事实，不能解释为人口属性因果规律。

8教学类型：成绩诊断、薄弱点、学习路径、资源推荐、行为干预、备考、动态进度、双Agent证据协作；每类型4个不同结构程序，共32结构族。每类覆盖explicit/ambiguous/missing/dependency/sensitive_proxy五难度；测试各类型1250、各难度2000，每类型×难度250。并非10000种独立任务类型，训练/测试共享结构族，未测试全新族迁移。协作类型是两独立噪声证据的可执行共识/交接模拟，不是实际多Agent通信系统。

测试10000次独立随机情景生成，按实际程序输入与有效参数指纹有9994种有效输入组合；6次有限域偶然重复原样保留。问题字符串8443种，重复指令下学生证据/情景重新生成，未靠换姓名、ID或同义改写扩量。每位测试学生5条，因此这些任务既非10000独立学生，也非统计iid。学生和结构族相关通过分组区间处理。

真值是truth.py的32个可执行动作/资源/路径/诊断程序，参数与测量在实例生成时抽样，所有输入已三位小数规范化；跟踪实际访问字段作为“程序必要信息”参考。条件分支可能只需1字段，其他程序需2–4字段，不是固定三数模式。源全信息执行10000/10000复现参考输出；K不足时预算Oracle可行率另报，不把不可达上限归罪某算法。缺失程序返回具体need_more，正确澄清与正常回答完成率分别报告。

selector只看到同一公开任务和候选记录，不读取oracle；攻击器只看到query公开结构/参数/知识标签及真实wire编码，学生ID及未释放字段/标签不进预测特征。训练标签仅用于训练攻击器，测试标签仅计分。所有数据都在结果后公开，所以未来不得把这份公开集重新称盲测。

固定种子：画像2026102011，开发2026102012，训练2026102013，测试2026102014。按学生区间固定2500/500/2000且不交叉。先执行1000开发（内部350/150学生分组验证攻击流程），再冻结源码、JSON参数、预算、规则、测试种子及指标；最后生成训练和测试。测试不重筛。每个划分数据/源码/原始结果均有SHA256，公开压缩副本另记未压缩哈希。

公开文件为纯合成profiles/tasks/oracle及原始释放结果。tasks.jsonl中的候选记录是后端私有输入，不是攻击器获准读取的整表；公开基准的模拟威胁边界由attacks.py强制。features_LOCAL缓存可由真实wire重建，非必要重复缓存不上传；旧公开数学题文及任何真实学生缓存不上传。
'''
    write('dataset_report.md',datareport)
    oldmm=next(x for x in old if x['method']=='MM-FOPD')
    report=f'''# MM-FOPD合成基准扩充与复现结果 /2026-10-20

**数据扩充完成；算法证据判断PIVOT。** 十方法、四历史式消融、三个预算均已实际运行；真实程序执行和LR/RF攻击齐全。此为32结构族上的可复核合成实验，不是真实学生或实际LLM教学确认性证据。

## 数据与运行分母

{stats_table}

主测试10000随机情景/2000学生/32结构族，其中9994种有效输入组合、6次自然碰撞保留；8443种问题字符串。每类型1250、每难度2000，任务类型及难度表见下。训练/开发学生不进入测试攻击。测试420000方法×预算结果（14方法×3预算×10000），并不是420000独立样本。补充严格Attention复算45000次完全相同，不增加独立证据量。所有源全信息程序执行10000/10000一致。

## 十方法完整主表

{main_table}

所有同一候选池、学生/任务、评价器、K≤3和Token≤96；另外K2/K5已运行，ten_method_comparison.csv包含30方法预算行。FullProfile原为不删减50字段，与共同预算相冲突，主表明确使用原顺序预算截断版本，不冒称完整画像上界；完整候选Oracle只用于可行性验证，不进入公平排名。LLM proxy固定最多2条，实际长度不同，不能从少释放自动推出算法隐私优势。统一上限不等于等实际信息量，表中字段/Token和风险原值均保留。

必要Recall/Precision/F1来自真实程序执行读迹，非TaskSlot/Attention评分。完成率为从**实际wire**运行既定教学决策程序后，与独立参考动作/资源/路径/诊断结果精确一致的比例；不是简单关键词或字段命中。然而它仍是可执行合成教学代理，不等于真实教学质量、学生学习提升或LLM答复质量。完整成功包括正确澄清，answer_completion_rate只在可回答实例计算，clarification_success_rate另列，避免把拒答冒充教学成功。

## 严格消融与混杂审查

Full完成率{f(full['completion'])}，F1={f(full['F1'])}；对照如下，主预算相同：

{ablation}

去projection与补充严格去Attention的实际回复均与Full相同；后者不是复合旧回退行，旧回退提升{float(sr('MM-no-attention')['completion']-full['completion']):.4f}不能归因于Attention删除。无TaskSlot全部不释放，虽隐私指标为0但完成率也是0，不构成隐私效用优势。去bottleneck仍保留TaskSlot和外部K/Token，差值是在这一流水线条件下的机制交互，不是互信息压缩理论证明。

机制开发复核：1000开发例的bottleneck全部返回0，最大Attention权重{trace['max_attention_weight_observed']:.5f}小于最小隐私成本{trace['min_privacy_cost_observed']:.2f}；投影998/1000非零但没有决定最终输出。有效内容来自后续baseline相关度最少两条回填及语义槽补齐，所以“正交+Attention+信息瓶颈共同发挥作用”缺乏支持。原投影是按位置任务词加权/归一化，并未证明敏感方向正交擦除；信息瓶颈的-log(weight)也不是经估计的互信息。

## 直接暴露与间接属性推断必须分开

{inference}

MM主预算直接敏感字段选择为0，但真实外发RF性别AUC={f(ar('MM-FOPD','gender_F')['AUC'])}，残疾AUC={f(ar('MM-FOPD','disability_Y')['AUC'])}；公开背景RF约0.501/0.491。没有直接释放不等于无法推断。SafeTaskTopK完成率更高，但两个RF点估计也更高；这说明存在安全—效用权衡，不能只按完成率宣布全面优胜，也不能把MM称为联合Pareto优势。

attribute_inference.csv同时给出LR/RF AUC、BA、Accuracy、公开背景差值及学生/任务族/双向95%区间。actual_release攻击看到全部真实合法wire；proxy_only攻击主动忽略两直接属性的值、缺失位和出现位，在相同训练/测试分母、模型预算下重新拟合，用于检验其他释放信息的推断信号，**并非修复了实际输出**。两类结果完整公开，包括不利属性、所有预算。

加权暴露=sum(所释放敏感权重)/sum(全候选权重)，另报未归一化暴露质量；权重是合成注释，不是互信息或真实伤害量。高敏选择比例阈值≥.7；直接属性为gender_F/disability_Y字段本身。PII/敏感词零命中不能替代属性推断。DP式方法没有整个机制的DP证明，Privacy-Funnel只是接口适配器，其他style/proxy不冒称官方系统复现。

## 类型与难度结果（K≤3）

{grouped}

group_results.csv共1890条类型/难度/32族×方法×预算结果；各组报告任务数、学生数和族数，完成/F1含学生分组区间。单族不能产生跨族置信区间；总体及预算曲线给出32族和双向区间。测试族也用于训练，不能从族bootstrap宣称跨全新任务族泛化。

## 与原144条对照

旧MM固定三单元Recall={oldmm['required_unit_recall']:.4f}、F1={oldmm['unit_reconstruction_f1']:.4f}，来自54学生/144任务；新程序必要Recall={full['Recall']:.4f}、F1={full['F1']:.4f}、完成率={full['completion']:.4f}。这些不是同一效用定义或同一任务分布，不作提升/下降幅度的因果检验。新数据按旧三类型规则计算的Recall={full['legacy_three_unit_recall']:.4f}，与独立程序输入真值不同，说明评分口径影响结论。旧FullProfile50字段、新主表最多3字段，不能直接对比其绝对数值。

已直接从旧rows.csv重聚合八方法历史指标，见historical_144_reaggregation.json；没有覆盖旧文件，也没有把已多次分析的旧测试叫新盲测。历史问题原文和真实数据均未用于本轮任务生成。

## 不确定性、失败与结论边界

500次学生簇bootstrap、500次32结构族簇bootstrap、500次独立学生×族乘积权重的双向bootstrap；均对固定已拟合模型/固定基准条件化，没有把重复任务当iid。类型/难度组内结果另给学生区间，小结构族数导致族区间较宽。No-projection与严格Attention实际完全相同，配对差区间为0只说明本固定数据输出等价，不证明所有可能任务都等价。属性分数缓存float32导致AUC点复算最大差{validation['max_AUC_drift_from_float32_prediction_cache']:.3e}，主点值采用原拟合双精度概率；区间使用保留的缓存，数值差单列而不隐去。

保留Full失败而Safe成功、反向成功以及双方失败的逐例wire、实际程序结果和参考结果，见failure_success_examples.json。程序真值可自动验证但未经独立教师双标；32有限结构、少量任务族、合成人口相关和代理基线限制外推。缺少实际教学干预、自然语言生成及官方LLM系统复现；不得将本结果包装成论文最终真实教育主证据。

建议：公开本基准和固定复现协议；将SafeTaskTopK/透明成本规则保留为强对照；MM原正交及Attention应删除核心隐私收益措辞或降级，TaskSlot是主要后处理但不能证明上游创新。后续优先检验简单规则在独立设计教学族和真实许可数据上的安全—效用边界，本轮不实现新算法或生产改动。

## 交付索引与图

历史审计historical_audit.md；数据dataset_report.md；十方法ten_method_comparison.csv；严格消融strict_ablation.csv；分组group_results.csv；预算与区间all_budget_results.csv；属性攻击attribute_inference.csv。原始释放raw_rows.jsonl.gz、合成profiles/tasks/oracle、源码、配置、锁与SHA均保留，缓存features_LOCAL不公开但可重建。

![安全效用](figures/privacy_utility.png)

![预算曲线](figures/budget_curves.png)

![严格消融](figures/strict_ablation.png)
'''
    write('benchmark_report.md',report)
    examples=load('failure_success_examples.json');failtext='# 失败案例与局限\n\n以下按固定case顺序保留各模式前5例，不据此选择或改动测试数据。全部ID为合成标识，无真实学生。\n\n'
    for label,bucket in examples.items():
        failtext+='## '+label+'\n\n'
        for rr in bucket[:3]:
            mm=rr['MM-FOPD'];st=rr['SafeTaskTopK'];failtext+=f'- `{mm["case"]}` / `{mm["family"]}` / {mm["difficulty"]}：参考`{mm["reference_output"]}`；MM选{mm["selected"]}，输出`{mm["actual_output"]}`；Safe选{st["selected"]}，输出`{st["actual_output"]}`。\n'
    failtext+='\nMM无直接属性释放仍存在代理推断；无TaskSlot零输出只获得零效用隐私地板；旧no-Attention分数尺度混杂，严格均匀干预输出不变。原bottleneck在1000开发例从未接受字段，最终由回填/TaskSlot恢复。32规则族有限，参考程序读迹不是教师必要知识标注，完整程序成功不等于人类教学有效。代理相关人为设置，不能推广到真实群体。6次离散域独立碰撞、训练测试共用规则族、float32分数缓存数值差、后置严格Attention审查均已披露；所有负结果保留。\n'
    write('failure_cases.md',failtext)
    write('REPRODUCE.md','''# Reproduction

Use the same CogniGuard checkout, Python NumPy/scikit-learn/transformers/PyTorch/PyYAML/matplotlib and existing offline Qwen tokenizer. No downloads or paid calls. Copy source only to a fresh immediate experiments child directory; do not copy generated locks/results/data and never overwrite this evidence. setup.py snapshots the old source. Also copy the frozen FOPD JSON config, whose parameters equal those used in development.

For the published package without the original CogniGuard checkout, run `python verify_public.py` first. Then `python public_replay.py --workspace <new-absolute-directory>` copies frozen sources, dependency snapshots, the tokenizer (no model weights), and published synthetic inputs to a new workspace. It re-executes train/test selection, LR/RF attacks and strict attention equivalence, then compares uncompressed raw-result hashes and attack metrics. `--prepare-only` prepares the workspace without the full rerun. This is a replay of published inputs, not a new independent test. The historical comparison/bootstrap analysis additionally requires the original hashed historical files; historical question texts are deliberately not redistributed.

```powershell
$env:PYTHONHASHSEED='20261020'
python "$benchmarkReplayDir/setup.py"
python "$benchmarkReplayDir/generator.py" dev
python "$benchmarkReplayDir/evaluate.py" dev
python "$benchmarkReplayDir/attacks.py" dev
python "$benchmarkReplayDir/freeze_test.py"
python "$benchmarkReplayDir/generator.py" train
python "$benchmarkReplayDir/evaluate.py" train
python "$benchmarkReplayDir/generator.py" test
python "$benchmarkReplayDir/evaluate.py" test
python "$benchmarkReplayDir/attacks.py" test
python "$benchmarkReplayDir/strict_attention_audit.py" train
python "$benchmarkReplayDir/strict_attention_audit.py" test
python "$benchmarkReplayDir/component_trace_audit.py"
python "$benchmarkReplayDir/analyze.py"
python "$benchmarkReplayDir/build_reports.py"
```

The original development attempts and pre-test uniqueness-assertion amendment are retained; the released generator already keeps finite-domain collisions without resampling, so a clean replay needs no amendment. The strict normalized attention intervention is a declared supplementary mechanism audit and not an initially preregistered method. package_sync.py is only for the original fresh publication destination and refuses overwrite; do not use it for replay publication. Program truth, final primary-source lock, raw synthetic tasks and releases are available; original historical questions and computed feature caches are excluded.
''')
    write('README.md',f'''# Synthetic MM-FOPD benchmark /2026-10-20

Start with benchmark_report.md and dataset_report.md. Dataset expansion completed:5000 wholly synthetic students,10000 held-out evaluation episodes plus5000 attacker-training and1000 development episodes. Test has9994 distinct active-input fingerprints across32 structural program families, not10000 independent families or learners.

Metric denominators and units: metrics_and_schema.md. Standard-library artifact verification: verify_public.py. Standalone frozen-input replay: public_replay.py (see REPRODUCE.md). Dependency snapshots include only small Python modules and the existing Apache-licensed tokenizer, never neural model weights. Group meeting text: group_meeting_synthetic.md.

Ten primary methods and four historical-style ablations were run atK2/3/5 under common96-token caps. One supplementary normalized uniform-attention intervention was actually replayed and exactly matched Full. Data/algorithm choices were not changed to make MM-FOPD lead. Main K3 MM completion={full['completion']:.4f}; SafeTaskTopK={safe['completion']:.4f}. Their attribute risks differ; no overall Pareto win claimed.

All results are synthetic/exploratory, not real-student teaching or a new privacy guarantee. Eight named systems retain original adapter/proxy limitations. See historical_audit.md, REPRODUCE.md, final_freeze.json, source hashes, raw releases and grouped intervals. Production/core/history untouched; no paid APIs or data/model downloads. Only wholly synthetic data from this new branch is published.
''')
    (P/'figures').mkdir(exist_ok=True);plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':140})
    colors={'MM-FOPD':'#a04f3d','SafeTaskTopK':'#3c648b','RelevanceCostRule':'#467866','Privacy-Funnel-adapter':'#756789'}
    fig,ax=plt.subplots(figsize=(9,5),layout='constrained')
    for m,color in colors.items():
        x=sr(m);ax.errorbar(x['weighted_privacy_exposure'],x['completion'],xerr=[[x['weighted_privacy_exposure']-x['weighted_privacy_exposure_two_way95_low']],[x['weighted_privacy_exposure_two_way95_high']-x['weighted_privacy_exposure']]],yerr=[[x['completion']-x['completion_two_way95_low']],[x['completion_two_way95_high']-x['completion']]],fmt='o',label=m,color=color,capsize=3)
    ax.set(xlabel='Weighted released sensitivity / total candidate sensitivity',ylabel='Executable task completion rate',title='CommonK3 /96-token cap: utility and annotated exposure\n10000 synthetic episodes /2000 students /32 families;500 two-way cluster draws');ax.legend();ax.grid(alpha=.15);fig.savefig(P/'figures/privacy_utility.png');plt.close(fig)
    fig,axs=plt.subplots(1,3,figsize=(15,5),layout='constrained')
    for m,color in colors.items():
        for ax,metric,title in [(axs[0],'completion','Executable completion'),(axs[1],'weighted_privacy_exposure','Annotated privacy exposure')]:
            xs=[sr(m,k) for k in [2,3,5]];ys=[x[metric] for x in xs];low=[x[metric]-x[metric+'_two_way95_low'] for x in xs];high=[x[metric+'_two_way95_high']-x[metric] for x in xs]
            ax.errorbar([2,3,5],ys,yerr=[low,high],marker='o',label=m,color=color,capsize=3);ax.set(title=title,xlabel='Maximum released fields K',ylabel=metric+' (ratio)');ax.set_xticks([2,3,5]);ax.grid(alpha=.15)
        ys=[ar(m,'disability_Y',k=k)['AUC'] for k in [2,3,5]];lo=[ys[i]-ar(m,'disability_Y',k=k)['AUC_two_way95_low'] for i,k in enumerate([2,3,5])];hi=[ar(m,'disability_Y',k=k)['AUC_two_way95_high']-ys[i] for i,k in enumerate([2,3,5])]
        axs[2].errorbar([2,3,5],ys,yerr=[lo,hi],marker='o',label=m,color=color,capsize=3)
    axs[0].legend(fontsize=7);axs[2].set(title='Actual release disability RF AUC',xlabel='Maximum released fields K',ylabel='ROC AUC');axs[2].set_xticks([2,3,5]);axs[2].grid(alpha=.15);fig.suptitle('Fixed synthetic test;500 student xfamily bootstrap draws, no iid-task intervals');fig.savefig(P/'figures/budget_curves.png');plt.close(fig)
    ms=['MM-FOPD','MM-no-projection','MM-no-attention-strict-uniform','MM-no-bottleneck','MM-no-taskslot','SafeTaskTopK'];labels=['Full','No projection','No attention\nstrict uniform','No bottleneck','No TaskSlot','SafeTaskTopK'];fig,ax=plt.subplots(figsize=(10,5),layout='constrained');ys=[sr(m)['completion'] for m in ms]
    ax.bar(range(len(ms)),ys,color=['#a04f3d']+['#647b8c']*5);ax.errorbar(range(len(ms)),ys,yerr=[[ys[i]-sr(m)['completion_two_way95_low'] for i,m in enumerate(ms)],[sr(m)['completion_two_way95_high']-ys[i] for i,m in enumerate(ms)]],fmt='none',ecolor='black',capsize=4)
    ax.set_xticks(range(len(ms)),labels);ax.set(ylabel='Executable completion rate',xlabel='SameK3 /96-token budget',title='Component contributions: strict uniform attention is supplementary\n10000 episodes /2000 students;95% two-way cluster intervals');ax.grid(axis='y',alpha=.15);fig.savefig(P/'figures/strict_ablation.png');plt.close(fig)
    import sklearn,transformers
    (P/'environment.json').write_text(json.dumps({'python':platform.python_version(),'numpy':np.__version__,'sklearn':sklearn.__version__,'transformers':transformers.__version__,'seed':20261020,'LLM_calls':0,'paid_calls':0},indent=2),encoding='utf8')
    (P/'decision.json').write_text(json.dumps({'dataset':'COMPLETED_REPRODUCIBLE_EXPLORATORY','MM_component_claim':'PIVOT','projection_independent_effect':'not observed; actual outputs identical','attention_independent_effect':'not observed in strict normalized supplementary intervention','TaskSlot_role':'restores content after bottleneck accepts none; zero without it','official_LLM_reproduction':False,'dataset_resampled_to_favor_MM':False,'main_case_count':10000,'unique_semantic_inputs':9994,'real_student_data_used':False},indent=2),encoding='utf8')
    print('REPORTS_AND_REAL_FIGURES_BUILT',flush=True)
if __name__=='__main__':main()
