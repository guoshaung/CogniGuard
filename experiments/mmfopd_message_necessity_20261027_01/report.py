"""Derive requested reports from the one completed evaluation, without new fits."""
import os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from pathlib import Path
import json,csv,hashlib,sys,datetime
import numpy as np
P=Path(__file__).parent;ROOT=P.parents[1]
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def write(n,s):(P/n).write_text(s,encoding='utf8')
def fmt(x,n=3):return 'N/A' if x is None else f'{x:.{n}f}'
def table(h,rr):return '| '+' | '.join(h)+' |\n| '+' | '.join(['---']*len(h))+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rr)+'\n'
def main():
    done=load('completion.json');assert done['status']=='COMPLETED'
    ss=load('method_summary.json');aa=load('attribute_inference.json');cc=load('utility_contrasts.json');state=load('train_state.json');audit=load('audit.json');cfg=load('config.json');cases=load('five_cases_LOCAL.json')
    by={r['method']:r for r in ss}
    def attack(m,a,k,scope='public_plus_message'):return next(r for r in aa if (r['method'],r['attribute'],r['attacker'],r['scope'])==(m,a,k,scope))
    utility=table(['消息','MAE [学生95%]','相对M4 MAE差 [95%]','满足+1/区间上限≤1','本地逻辑读/上传项','Token均值/最大','消息NA比例'],
      [[r['method'],fmt(r['MAE'])+' ['+fmt(r['MAE95_low'])+','+fmt(r['MAE95_high'])+']',fmt(r['delta_MAE_vs_M4'])+' ['+fmt(r['delta95_low'])+','+fmt(r['delta95_high'])+']',str(r['point_within_M4_plus1'])+'/'+str(r['upper_CI_within_M4_plus1']),str(r['local_logical_fields_read'])+'/'+fmt(r['uploaded_items_mean'],1),fmt(r['tokens_mean'],1)+'/'+str(r['tokens_max']),fmt(r['message_NA_fraction'])] for r in ss])
    contrast=table(['左−右MAE，负值有利左侧','差值','学生簇配对95%'],[[r['left']+'−'+r['right'],fmt(r['delta_MAE']),str([round(x,3) for x in r['student95']])] for r in cc])
    privacy=''
    for scope in ['public_plus_message','authorized_result_plus_message']:
        privacy+='\n### '+scope+'\n\n'
        rows=[]
        for r in aa:
            if r['scope']!=scope:continue
            if r['status']!='COMPLETED':rows.append([r['method'],r['attribute'],r['attacker'],r['status'],'N/A','N/A']);continue
            rows.append([r['method'],r['attribute'],r['attacker'],fmt(r['AUC'])+' ['+fmt(r['AUC95_low'])+','+fmt(r['AUC95_high'])+']',fmt(r['BA']),fmt(r['delta_AUC_vs_scope_baseline'])+' ['+fmt(r['delta95_low'])+','+fmt(r['delta95_high'])+']'])
        privacy+=table(['消息','属性','攻击器','AUC [95%]','BA','相对本scope基线AUC差 [配对95%]'],rows)
    data=audit['cohort'];counts=table(['划分','学生/快照','性别正/负学生','残疾正/负学生'],[[sp,str(z['students'])+'/'+str(z['snapshots']),str(z['attributes']['gender_F']['positive_students'])+'/'+str(z['attributes']['gender_F']['negative_students']),str(z['attributes']['disability_Y']['positive_students'])+'/'+str(z['attributes']['disability_Y']['negative_students'])] for sp,z in data.items()])
    simple=[m for m in ['M1','M2','M3'] if by[m]['upper_CI_within_M4_plus1']]
    result_only=by['M3']['upper_CI_within_M4_plus1'];c40=next(r for r in cc if (r['left'],r['right'])==('M4','M0'));c21=next(r for r in cc if (r['left'],r['right'])==('M2','M1'))
    messages=''
    for case in cases:
        messages+='\n## '+case['case']+' / '+case['student_pseudonym']+'\n\n任务：'+case['task']+'。独立参考分数仅本地：'+str(case['target_score_LOCAL'])+'；是否及时有成绩：'+str(case['target_observed'])+'。\n\n'
        for m,z in case['methods'].items():
            messages+='### '+m+'\n\n本地读取：'+(', '.join(z['local_read_fields']) or '无画像字段')+'。上传'+str(z['tokens'])+' Token；预测='+fmt(z['prediction'])+'，绝对误差='+fmt(z['absolute_error'])+'。\n\n```text\n'+(z['uploaded'] or '(empty message)')+'\n```\n\n省略来源字段：'+(', '.join(z['omitted_source_fields']) or '无')+'；变换：'+z['transformation']+'。\n\n'
    write('MESSAGE_EXAMPLES_LOCAL.md','# 五个真实消息案例（仅本地，假名化不等于匿名保证）\n\n按预先冻结的示例类别选择，不影响全开发集评估。未输出真实学生ID或受保护标签；包含真实学习字段、成绩和预测，不上传外部。M3没有原字段名，但预测本身仍可能携带个人信号。\n'+messages)
    case_table=table(['样本假名/案例','M0误差','M1误差','M2误差','M3误差','M4误差'],[[c['student_pseudonym']+'/'+c['case']]+[fmt(c['methods'][m]['absolute_error']) for m in ['M0','M1','M2','M3','M4']] for c in cases])
    decision='STOP_COMPLEX_SEARCH_FOR_THIS_PROXY_TASK_USE_RESULT_ONLY' if result_only else 'EVIDENCE_INSUFFICIENT_NO_NEW_ALGORITHM'
    verdict='在本轮授权任务下优先结果-only接口，停止在该任务上寻找复杂画像披露算法。' if result_only else '证据不足以推荐复杂算法，保留失败并停止本轮。'
    private_risks=[]
    for attr in ['gender_F','disability_Y']:
        r=attack('M3',attr,'RF');private_risks.append(attr+' RF AUC='+fmt(r['AUC'])+'，相对Public差='+fmt(r['delta_AUC_vs_scope_baseline'])+'，95%='+str([round(r['delta95_low'],3),round(r['delta95_high'],3)]))
    text=f'''# 真实学习日志上的消息最小化代理验证

**{verdict}** 本轮COMPLETED，全部结论限定于现有2013J训练/已用开发学生、下一次TMA成绩代理、固定Ridge/LR/RF和单次消息。不是真实云端LLM教学、学习计划质量或学生学习收益证据。

## 先回答四个问题

1. 新增个人信息是否有任务效用：M4−M0 MAE={c40['delta_MAE']:.3f}，学生配对95%={c40['student95']}，负值表示改善。这里只能判断在本轮Public边界下个人字段与课程/时间背景合计的作用，不能归因给某一个字段。
2. 哪些简单接口足够：区间上限也满足M4+1的消息为{', '.join(simple) or '无'}。M3直接按解析预测值计分，接收端不再拟合还原器。其模型和M4采用完全相同输入/训练协议，只差本地或接收端执行及0.1分舍入；效用接近是可核验的接口性质，不是新算法提升。
3. 是否存在隐私效用矛盾：详见两套攻击表和M2−M1 MAE={c21['delta_MAE']:.3f}，95%={c21['student95']}。M3仍有自身属性信号：{'; '.join(private_risks)}。减少原字段不代表无隐私风险；预测输出本身也属于披露。有限攻击器加入信息后AUC下降不能抹除已有知识。
4. 是否值得新算法：{verdict} 这不宣布整个MM-FOPD无价值；需要解释型、多用途或交互式教学消息的实际业务尚未验证。

## 冻结边界、来源和样本分母

{counts}

Public仅固定任务标识next_TMA_score，没有课程、阶段、截止日或其他个人背景。这是无法从部署系统确认时显式采用的实验假设；不代表线上接收端确实一无所知。课程module、cutoff、days_to_due本轮计入上传字段。旧V2/V3把这三项当Public，不能直接横比它们的AUC。

本地允许13个学习字段加上述3项上下文，共16项；敏感标签/ID/真实未来成绩不是输入。M1训练MI选择：{', '.join(state['selected'])}。M2同来源字段训练集三分位摘要，阈值：{json.dumps(state['thresholds'],ensure_ascii=False)}；NA明确传递，不用混合坐标假装原事实。

实际唯一缓存：{cfg['cache']}；2013J固定484/166学生，1337/473快照，学生无交叉，不读2014J。原OULAD作者公开数据，缓存构建和许可元数据沿用原证据。原标签为下一计划TMA的及时提交成绩，晚/未提交记0，非纯已观测成绩；各方法observed_MAE和分母另在CSV。

## 效用与上传成本

{utility}

{contrast}

M1/M2同64 Token上限，完整项逐个预算检查，超出则整项省略，不截断字符串、不填充。M3自然长度；M4完整16项仅本地影子参考，超64例数={by['M4']['over_64_count']}，不是数学上界或等预算竞争者。共享缓存IO包含全画像；表中本地逻辑读取数只指各机制的逐例处理，M1/M2的训练选择和排序读16候选，不能称只接触3项。上传项数与本地读取数、实际Token分开。

消息生成/序列化/解析和预测时间在timings.json；总耗时{done['runtime_seconds']:.2f}秒，拟合{done['fits_started']}/50次，最高2 CPU工作线程，不用GPU。M3计时还须包含本地完整输入编码和本地预测，不能仅拿结果字符串的生成耗时代表总成本。任务预测器统一Ridge alpha10；攻击器统一固定LR和RF64/深度6参数；M3训练消息来自学生分组3折交叉拟合，所有折内缺失处理/缩放只由该折训练估计。

## 真实可见信息的属性推断

两套输入均从实际wire解析，仅额外包含各自允许的背景。第一套Public+消息与M0比较。第二套共同授权结果Y_auth在协议中预定为M3预测：训练用OOF，开发用全train拟合预测，绝不使用真实未来成绩。预测结果授权是本实验合同，不是已核实的部署RBAC。第二套只衡量已知该预测后消息增添的推断信号；M3加同一预测不产生新视图，四项是明确别名，非独立重复证据。未测的其他授权信息、攻击器、跨轮泄露没有保证。

{privacy}

200次学生聚类bootstrap，同一学生所有快照共同抽样，配对使用同一权重。只对固定已拟合模型和本开发样本条件化，没有重复拟合或多重比较调整，不是泄露下限或信息论隐私保证。残疾阳性仅20名开发学生，区间与统计功效限制必须保留。

## 五个真实失败/差异案例

{case_table}

各例原始任务、逻辑来源字段、五种实际消息、预测/误差与省略信息见MESSAGE_EXAMPLES_LOCAL.md和five_cases_LOCAL.json。假名化逐例CSV为per_sample_LOCAL.csv；不含真实学生ID或敏感标签，但仍含学习结果，应仅留本地。方法总体判断来自全473例，案例不是筛选后的评估集。

## 对旧结论的影响及限制

没有恢复旧正交/Attention/信息瓶颈，没有将本次结果追溯给旧算法。旧R31未找到，状态BLOCKED_MISSING_SOURCE：本地目录/缓存Git树及GitHub两次代码搜索无结果，不臆造内容。旧V2/V3报告显示表示/缺失接口、公共背景和实际外发评估的重要性，本轮直接比较信息形式。

已知时间限制：无真实成绩公开时间戳，原审计发现9训练/7开发下一计划TMA已在快照前提交；保留原样本，不将此称严格未观测未来盲测。开发集反复被研究使用；本轮仅冻结后评估一次，仍是探索性。只有一项成绩/提交代理，没有教师评分或真实LLM接收任务；结果-only可行不能外推到需要理由、源证据或多轮交互的任务。

## 版本、核验及停止

当前仓库commit {audit['git_commit']}，预存tracked脏状态{audit['git_tracked_dirty_lines']}行，未混入/修改。协议先于首次拟合冻结；模型全部保存后开启唯一dev评估。execution_lock、TRAIN_COMPLETE、DEV_EVAL_LOCK和run_log记录顺序；原输入和读取源码哈希均未变。主程序本轮拟合日志含MI估计1次、Ridge8次和攻击36次，总45；另有4个显式授权视图别名。完整原始数据、模型及逐人信息不上传外部。

下一轮唯一问题（仅记录，不执行）：如果接收端必须给出可审计的预测理由，除授权预测分数外，最少哪一种低粒度证据能够满足这一额外任务要求？

本轮到此停止，无自动科研队列。复现命令见REPRODUCE.md，校验和见manifest.json。
'''
    write('RESULT.md',text)
    meeting=f'''# 组会一页：本地画像应上传什么？

**任务：真实学习日志上的消息最小化代理验证。** OULAD2013J，484训练/166开发学生，1337/473快照。目标是下一计划TMA成绩/提交代理；不是教学效果或云端LLM。开发已被研究使用，本轮探索性。

Public只有任务标识，课程/阶段/截止日均计入披露；这是实验假设，未确认部署背景。M1为TrainMI3原字段，M2同字段训练三分位类别，M3本地完成预测只传0.1分精度结果，M4全16输入仅本地影子参考。

{table(['消息','MAE','相对M4差','平均Token','+1分区间准入'],[[r['method'],fmt(r['MAE']),fmt(r['delta_MAE_vs_M4']),fmt(r['tokens_mean'],1),str(r['upper_CI_within_M4_plus1'])] for r in ss])}

新增个人信息效用：M4−M0={c40['delta_MAE']:.3f}分，配对95%={str([round(v,3) for v in c40['student95']])}。M3−M4={by['M3']['delta_MAE_vs_M4']:.3f}分，最大逐例差{done['M3_vs_M4_max_score_difference']:.3f}。M3按预测值直接评分，无接收端还原拟合。

属性推断：{'; '.join(private_risks)}。另评估已知共同授权预测Y_auth后的增量；不把AUC下降说成擦除已有知识。200次学生簇配对bootstrap，残疾阳性仅20学生，隐私结论限固定LR/RF。

**决策：{verdict}** 旧正交/Attention核心收益结论没有改变，本轮也不挽救旧算法。不能据一个代理宣布全部MM-FOPD无价值。真实解释型/交互教学接口未验证。

资源：{done['fits_started']}/50拟合，CPU≤2线程，0 GPU/下载/付费/外部学生数据上传，唯一一次dev评估。R31来源缺失已标BLOCKED；原文件哈希未变。

唯一后续问题：接收端如必须提供可审计预测理由，除授权分数外还最少需要什么低粒度证据？本轮不执行。
'''
    write('MEETING_ONE_PAGE.md',meeting)
    write('REPRODUCE.md','''# Reproduction / no overwrite

Use the existing system Python recorded in audit.json. The project virtualenv is used only for interface tests; it lacks tokenizers. No installation or downloads.

Original commands from the repository root:

```powershell
$env:PYTHONHASHSEED='20261027'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
$env:RAYON_NUM_THREADS='1'
$env:CUDA_VISIBLE_DEVICES='-1'
$env:PYTHONDONTWRITEBYTECODE='1'
python -B experiments/mmfopd_message_necessity_20261027_01/audit.py
./run.cmd test experiments/mmfopd_message_necessity_20261027_01/test_contract.py -q -p no:cacheprovider
python -B experiments/mmfopd_message_necessity_20261027_01/run.py
python -B experiments/mmfopd_message_necessity_20261027_01/report.py
```

These sources refuse overwriting completed locks. Do not rerun here or automatically rerun formal experiments. For an explicitly authorized replay, copy only the5 source/test files, README, PROTOCOL and config to a NEW immediate experiments child folder; select fresh wall-clock deadlines before any fit and record that protocol as a replay. Use the SAME hashed2013J cache and existing tokenizer, never test_data. Existing reports can be reproduced from stored method_summary/attribute_inference/contrasts without fitting; any report rebuild is postprocessing, not another evaluation.

All *_LOCAL, models_LOCAL and actual messages remain on this computer. No external synchronization is authorized in this round. The forecast Y_auth is an out-of-fold or train-only predicted value, never a hidden future label. The first selection estimation and44 predictive classifier/regressor calls are separately visible in run_log.jsonl.
''')
    save={'decision':decision,'result_only_recommended_for_this_proxy':result_only,'simple_methods_supported_within1':simple,'R31':'BLOCKED_MISSING_SOURCE','new_algorithm_started':False,'new_test_started':False,'fits':done['fits_started'],'run_stopped':True,'next_question':'Minimum low-granularity evidence beyond the authorized prediction for a separately required auditable explanation?'}
    (P/'decision.json').write_text(json.dumps(save,ensure_ascii=False,indent=2),encoding='utf8')
    # Small scientific plot from real final metrics only.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained');colors=['#777777','#3d688c','#547a63','#aa5e40','#685b7f']
    for ai,attr in enumerate(['gender_F','disability_Y']):
        for j,m in enumerate(['M0','M1','M2','M3','M4']):
            r=by[m];a=attack(m,attr,'RF');axes[ai].plot(r['MAE'],a['AUC'],'o',color=colors[j]);axes[ai].annotate(m,(r['MAE'],a['AUC']),xytext=(5,5),textcoords='offset points')
        axes[ai].set(xlabel='Next-TMA proxy MAE (score points; lower better)',ylabel='Actual-view RF ROC AUC',title=attr+' / Public + message');axes[ai].grid(alpha=.15)
    fig.suptitle('OULAD2013J /473 dev snapshots /166 students; fixed models, no search');fig.savefig(P/'privacy_utility.png',dpi=150);plt.close(fig)
    manifest={'classification':'LOCAL_ONLY_REAL_STUDENT_LOGS','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':{p.relative_to(P).as_posix():{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in P.rglob('*') if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts},'external_uploads':0}
    (P/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('REPORTS_COMPLETED',decision)
if __name__=='__main__':main()
