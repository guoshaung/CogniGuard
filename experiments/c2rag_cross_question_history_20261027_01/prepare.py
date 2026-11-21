"""Freeze unchanged request/candidate sequence and one instance before replay."""
from datetime import datetime, timezone
from fractions import Fraction as F
import json
from experiments.c2rag_cross_question_history_20261027_01.common import OUT,OLD,SOURCE,PIN,PROJECT_ROOT,sha,write

MAPPING={
 'T05':{'mass':'m','speed_squared':'u0_sq','energy':'K_initial'},
 'T06':{'push':'F_push','friction':'f','distance':'d_push','net_force':'F_net',
        'applied_work':'W_push','friction_loss':'loss_push','net_work':'W_net'},
 'T07':{'mass':'m','initial_speed_squared':'u0_sq','net_work':'W_net','initial_energy':'K_initial',
        'final_energy':'K_final','final_speed_squared':'v1_sq'},
 'T08':{'mass':'m','speed_squared':'v1_sq','friction':'f','energy':'K_final','stop_distance':'d_stop'}}

FIELDS={'m':'m','u0_sq':'u','F_push':'F','f':'f','d_push':'d','F_net':'F-f','W_push':'F*d',
        'loss_push':'f*d','W_net':'(F-f)*d','K_initial':'m*u/2',
        'K_final':'m*u/2+(F-f)*d','v1_sq':'u+2*(F-f)*d/m','d_stop':'(m*u/2+(F-f)*d)/f'}


def main():
    # Pinned remote text snapshots/manifest must already be present, not HEAD.
    assert OUT.exists() and not (OUT/'freeze.json').exists()
    remote=json.loads((OUT/'prior_fetch_payload.json').read_text(encoding='utf8'))
    for name,record in remote.items():
        f=OUT/'prior_evidence'/name;f.parent.mkdir(exist_ok=True)
        f.open('xb').write(record['content'].encode('utf8'))
    manifest=json.loads((OUT/'prior_evidence/UPLOAD_MANIFEST.json').read_text(encoding='utf8'))
    for name in ['STRUCTURE_AUDIT.md','TASKS_AND_SOURCES.md','MINIMAL_UNSAFE.md','PROTOCOL.md']:
        assert sha((OUT/'prior_evidence'/name).read_bytes())==manifest['sha256'][name],name
        assert (OUT/'prior_evidence'/name).read_bytes()==(OLD/name).read_bytes(),name
    assert sha((OLD/'contracts.json').read_bytes())==manifest['sha256']['contracts.json']
    tasks=[t for t in json.loads((OLD/'contracts.json').read_text(encoding='utf8')) if t['task_id'] in MAPPING]
    assert [t['task_id'] for t in tasks]==list(MAPPING)
    assert len({t['source']['html_sha256'] for t in tasks})==1
    html=PROJECT_ROOT/tasks[0]['source']['local_html']
    assert sha(html.read_bytes())==tasks[0]['source']['html_sha256']
    nominal={'m':F(30),'u':F(1,4),'F':F(120),'f':F(5),'d':F(4,5)}
    values={k:str(eval(e,{'__builtins__':{}},nominal)) for k,e in FIELDS.items()}
    rule_set=set();requests=[];targets=[]
    for t in tasks:
        tid=t['task_id'];mp=MAPPING[tid]
        # Numerical agreement is a preparation check, not a new hidden input to controllers.
        env={k:F(v) for k,v in zip(t['variables'],t['actual'])}
        for old,expr in t['fields'].items():
            assert F(values[mp[old]])==eval(expr,{'__builtins__':{}},env),(tid,old)
        for body,head in t['rules']:
            rule_set.add((tuple(sorted(mp[x] for x in body)), f'TARGET_{tid}' if head=='TARGET' else mp[head]))
        targets.append({'target':f'TARGET_{tid}','origin_task':tid,'fields':[mp[k] for k in t['target_fields']],
                        'authorized':[],'original_granularity':t['protected_target']})
        for q in t['requests']:
            candidates=[]
            for a in t['actions']:
                if a['request_id']!=q['request_id']:continue
                candidates.append(a|{'reveals':[mp[x] for x in a['reveals']], 'task_id':tid,
                                     'asset_id':'package_fig7_4_continuous','step':len(requests)+1})
            candidates.sort(key=lambda a:(len(a['reply'].encode('utf8')),a['action_id']))
            requests.append(q|{'task_id':tid,'step':len(requests)+1,'asset_id':'package_fig7_4_continuous',
                                'candidates':candidates,'canonical_action_id':candidates[0]['action_id']})
    assert len(requests)==16 and sum(len(q['candidates']) for q in requests)==17
    rules=[[list(b),h] for b,h in sorted(rule_set)]
    maximum=max(len(a['reply'].encode('utf8')) for q in requests for a in q['candidates'])
    instance={'asset_id':'package_fig7_4_continuous','n':4,'k':3,'field_mapping':MAPPING,'fields':FIELDS,
              'variables':['m','u','F','f','d'],'nominal_evaluator_only':{k:str(v) for k,v in nominal.items()},
              'field_values_evaluator_only':values,'facts':list(FIELDS)+[a['target'] for a in targets],
              'rules':rules,'public':[],'assets':targets,'requests':requests,
              'public_equations':['K_initial=m*u0_sq/2','F_net=F_push-f','W_push=F_push*d_push',
                 'W_friction_push=-f*d_push=-loss_push','W_net=W_push-loss_push',
                 'K_final=K_initial+W_net','v1_sq=2*K_final/m','W_friction_stop=-K_final=-f*d_stop'],
              'assumptions':['same named package; constant positive mass','horizontal push and friction; vertical forces do no work',
                 'F_push>f>0; d_push>0; initial/terminal speeds positive magnitudes',
                 'same constant friction during push and coast; no push during coast; stops at zero speed',
                 'nominal rational textbook values, not a new measurement or rounded2.53 equality'],
              'budgets':{'queries':16,'deliveries':16,'output_bytes':16*maximum,'per_recipient_queries':4,
                         'per_recipient_output_bytes':4*maximum,'maximum_candidate_bytes':maximum,
                         'retrieval_calls':0,'model_calls':0},
              'cpu_budgets_seconds':{'fixed_primary':60,'fixed_independent':60,'all_primary':90,'all_independent':90,
                                    'mathematical_verification':180},
              'sources':[{'task_id':t['task_id'],'source':t['source'],'evidence_paragraphs':t['evidence_paragraphs']} for t in tasks]}
    write('instance.json',instance)
    write('prior_contracts_T05_T08.json',tasks)
    for name in ['engines','reference']:
        data=(OLD/'snapshot'/f'{name}.py').read_bytes()
        expected={'engines':'ed3b646d94bd9b2a395284f41fac7e87c3f277d149a05c2641b367fe6ef5fcce',
                  'reference':'7e6cfc329afc69e135b2a92e0fcfe9d8536636b4c21f0089d7e5b4fd7cd5a472'}[name]
        assert sha(data)==expected
        (OUT/'snapshot').mkdir(exist_ok=True);(OUT/'snapshot'/f'{name}.py').open('xb').write(data)
    mapping=['# INSTANCE MAPPING\n\n唯一持续资产：`package_fig7_4_continuous`。作者模拟授权；所有目标在第1步前登记，各联盟≤3均无完整目标权限。任何一个目标恢复即违规。T06仍是输入三元组，而非单字段。\n',
             '|原题|原字段|统一量|单位/阶段|\n|---|---|---|---|']
    units={'m':'kg, all stages','u0_sq':'m²/s², before push','F_push':'N, pushing','f':'N, same constant friction',
           'd_push':'m, during push','F_net':'N, during push','W_push':'J, applied force during push',
           'loss_push':'J, positive magnitude of negative friction work during push','W_net':'J, net during push',
           'K_initial':'J, before push','K_final':'J, after push/before coast','v1_sq':'m²/s², after push/before coast',
           'd_stop':'m, coast only; not d_push'}
    for tid,mp in MAPPING.items():
        for old,new in mp.items():mapping.append(f'|{tid}|{old}|{new}|{units[new]}|')
    mapping+=['\n## 原材料依据\n',
      '所有题来自College Physics2e7.2，Figure7.4同一包裹。T05题目定位import-auto-id1745178给质量与初速；T06 import-auto-id1993448给推力/摩擦/推动距离，import-auto-id1115429给竖直力功0，import-auto-id1997856给摩擦负功；T07 import-auto-id1519467明确使用刚算出的净功与初动能；T08 import-auto-id2050373明确摩擦保持不变，import-auto-id2822725区分Wfr=−95.75J与−f*d′。',
      '来源URL：https://openstax.org/books/college-physics-2e/pages/7-2-kinetic-energy-and-the-work-energy-theorem 。本地HTML与上一轮SHA256一致；原段落完整保存在instance.json。',
      'T06原friction_loss记录的是负功的正幅值；不能把+4J当摩擦做正功。W_friction_push=-4J；滑停阶段W_friction_stop=-95.75J，两者不同。速度平方用于精确名义表示，末速约2.53m/s不作为精确约束。',
      '\n## 目标保持原粒度\n']
    for a in targets:mapping.append(f'- {a["target"]}: {a["fields"]}；未授权联盟任一完整恢复即违规。')
    mapping.append('\nT06的F_push、f、d_push另行报告单字段恢复；单字段恢复不升级为完整T06违规。两种距离/两种能量/两种速度绝不因同名直接合并。无映射或数值冲突。')
    write('INSTANCE_MAPPING.md','\n'.join(mapping))
    write('PROTOCOL.md','''# 同一教学实例跨题交付历史 · 冻结协议

EXPLORATORY。教材来源真实；请求、候选、身份分配、目标与授权均为上一轮研究者构造。一个包裹实例，不是4个独立资产，无真实学生日志或独立双人标注。

## 前序与范围
固定提交6b60c733a8d7a751734521d4c93d23fb58410dad，CG/diagnostics/2026-10-27-c2rag-real-source-structure-01/。先读取并按其UPLOAD_MANIFEST核验4篇指定文档及本地contracts。仅T05–T08，原数值、顺序、持续r0–r3身份和全部回答不变；禁止模型/GPU/付费API/新数据下载/训练/生产控制器修改或启动后续队列。

## 冻结实例和策略
统一映射、公开方程、适用条件及具体来源定位见INSTANCE_MAPPING.md和instance.json。目标T05初动能、T06输入(F_push,f,d_push)三元组、T07末速平方、T08滑停距离在第1步前全部注册，各k≤3联盟均未授权。任何单一完整目标可恢复即违规，不使用拼接大目标。部分T06字段另外计。四目标、权限、全局规则和映射在三组完全相同；Reset只清交付历史。
公开规律、阶段绑定与同一包裹关联对检测器和观察者均可见。原题完整数值、来源可检索身份和评测真值不交学生；实际query无隐藏数值；候选未交付不算观察。完整原题及引用上下文可见时目标公开可计算，这是模型边界，不声称实际版权禁止教学。原许可CC BY-NC-SA4.0及OpenStax署名沿用。

## 16请求与候选
T05→T06→T07→T08，题内原顺序，身份r0–r3循环且跨题持续。每请求规范候选=min(UTF8字节,动作ID)，选择发生在回放前；全候选参照仅允许T06首问另一原有正确解法。更短不代表更少信息。每请求最多交付一个回答；拒答为空字符串、字节0、正确0；正确原候选计1。规范候选及排序保存在instance.json。
三组同一非绑定预算：总请求16/交付≤16、输出≤16倍最长候选字节；每身份4请求、4倍最长候选字节。记录实际UTF8字节，不伪报模型Token。

## 对照和观察者
NoGate全部交付；Reset每题开始清空ExactK3保存的每人交付历史，安全候选才提交状态；Shared跨题保持实际已交付状态。被拒候选不进入后续历史。两组拒答均不更新状态。独立set参考在每个决策对照ExactK3全联盟向量；观察者是另一份持久视图，不随Reset清空，按实际文本的单位/阶段解析，不能读取控制器安全标签或原候选reveals代替解析。无法解析保留UNKNOWN并不得声称安全。
保存每步请求、实答、身份、题目、资产、控制器决定、持久联盟视图；分别报告k恰为1/2/3及k_min、首次恢复、允许但违规步和新增目标步、部分字段。直接=一动作恢复；单题组合=所有必要动作同题；跨题=至少2题且按同全局规则逐题分开均不能恢复，删任一必要动作后不恢复。允许三人内真实最小支持为单人，不换身份凑三人。

## 独立核验和最小见证
原冻结ExactK3及独立set参考哈希不变；规则仅映射后取并集，不删规则或按方法替换。最小见证从实际已交付动作删减/枚举，给出所有必要动作、所属题、持续身份及单题/删除反事实。数学独立程序使用公开方程与观察量而非Horn规则：Groebner为0证明唯一；不唯一需满足原正值与F>f前提的有理反世界。反世界按固定原值乘1/2、2、100001/100000、99999/100000、加减1顺序求解；有限搜索失败为UNKNOWN，不是安全。对每步联盟、最小见证及最优安全计划检查。数学核验CPU预算180秒，超时未完成项UNKNOWN并停止安全/最优性过度结论。

## 离线参照与CPU停止
固定候选主枚举2^16=65536计划，CPU60秒；独立set穷举复核CPU60秒。全候选主枚举3*2^15=98304计划，CPU90秒；独立set穷举CPU90秒。每项各自单调process_time计时，预处理和检查均计入该项；不事后扩预算。仅在固定枚举与独立复核完成后执行全候选。单调规则下最终安全等价全部前缀安全；最优计划另逐步复核。列举全部最大正确数计划，以字节最小、计划编码最小排序选代表，不以启发式或未完成枚举称OPT。提前知道全16请求，仅为离线参照，不是新在线算法。

## 失败与停止
冻结前检查映射、名义数值和来源一致；若冲突停止。冻结后不得改目标、身份、顺序、候选或规则。工程错误保留失败与部分输出，后续仅可另建运行编号；契约需变则停止本轮。保留无差异/UNKNOWN/失败。本轮只做这一个实例、三组回放和两种离线上限；完成整理与现有流程同步后停止，不扩量、不训练。
''')
    write('preparation_checks.json',{'mapping_consistent':True,'all_original_field_values_preserved':True,
       'source_sha256':sha(html.read_bytes()),'pinned_commit':PIN,'requests':16,'candidates':17,
       'canonical_actions':[q['canonical_action_id'] for q in requests],
       'earlier_readonly_stdout_failure':'gbk UnicodeEncodeError during console inspection, fixed UTF8 before freeze; no experiment run or contract change'})
    files=[OUT/'instance.json',OUT/'INSTANCE_MAPPING.md',OUT/'PROTOCOL.md',OUT/'prior_contracts_T05_T08.json']
    files+=sorted((OUT/'prior_evidence').glob('*'))+sorted((OUT/'snapshot').glob('*'))+sorted(SOURCE.glob('*'))
    write('freeze.json',{'utc':datetime.now(timezone.utc).isoformat(),'before_replay':True,
                         'sha256':{str(p.relative_to(PROJECT_ROOT)):sha(p.read_bytes()) for p in files if p.is_file()}})
    print('Frozen one instance, 4 unchanged targets, 16 requests; no replay executed.')


if __name__=='__main__':main()
