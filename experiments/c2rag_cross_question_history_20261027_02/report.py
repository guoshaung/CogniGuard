"""Read-only independent certificate kernel and postprocessing; no replay rerun."""
from collections import Counter
from fractions import Fraction as F
import csv
import itertools
import json
from experiments.c2rag_cross_question_history_20261027_02.common import OUT,SOURCE,PROJECT_ROOT,OLD,read,write,module,verify_freeze,sha
from experiments.c2rag_cross_question_history_20261027_02.run import case_of,coalitions
from experiments.c2rag_cross_question_history_20261027_02.observer import decode
from experiments.c2rag_real_source_structure_20261027_01.report import rational


def main():
    verify_freeze();data=read('instance.json');traces=read('replay.json');summary=read('method_summary.json')
    witnesses=read('minimal_witnesses.json');math=read('mathematical_certificates.json');certs=math['queries']
    case=case_of(data);ref=module('reference');disagreements=[];counterexamples=0
    def target_status(known,target):
        cert=certs['|'.join(sorted(known))]
        targetfields=next(a['fields'] for a in data['assets'] if a['target']==target)
        vals=[cert['fields'][f]['status'] for f in targetfields]
        if all(s=='UNIQUE' for s in vals):return 'UNIQUE'
        if 'NONUNIQUE' in vals:return 'NONUNIQUE'
        return 'UNKNOWN'
    # Independent Fraction kernel checks all saved worlds against the delivered values.
    for key,cert in certs.items():
        cl=ref.closure(cert['known'],case['rules'])
        for field,proof in cert['fields'].items():
            status=proof['status']
            if (status=='UNIQUE')!=(field in cl) and status!='UNKNOWN':
                disagreements.append({'known':key,'field':field,'horn':field in cl,'math':status})
            if status!='NONUNIQUE':continue
            a=cert['actual_world'];b=proof['alternate_world']
            assert all(F(v)>0 for v in b.values()) and F(b['F'])>F(b['f'])
            assert all(rational(data['fields'][k],a)==rational(data['fields'][k],b) for k in cert['known'])
            assert rational(data['fields'][field],a)!=rational(data['fields'][field],b)
            counterexamples+=1
    verified_witnesses=[]
    for w in witnesses:
        union=set(w['known_values']);assert target_status(union,w['target'])=='UNIQUE'
        acts=w['actual_deliveries'];deletion=[];separate=[]
        for a in acts:
            known={k for x in acts if x!=a for k in decode(x['reply'],x['task_id'])}
            state=target_status(known,w['target'])
            deletion.append({'removed':a['action_id'],'math_status':state,'math_key':'|'.join(sorted(known))})
        for task in w['tasks']:
            known={k for x in acts if x['task_id']==task for k in decode(x['reply'],x['task_id'])}
            separate.append({'task':task,'math_status':target_status(known,w['target']),'math_key':'|'.join(sorted(known))})
        assert all(x['math_status']=='NONUNIQUE' for x in deletion)
        if w['kind']=='cross_question_accumulation':assert all(x['math_status']=='NONUNIQUE' for x in separate)
        full=next(s for s in traces if s['method']==w['method'] and s['step']==w['last_step'])
        verified_witnesses.append(w|{'independent_equations':'UNIQUE','math_key':'|'.join(sorted(union)),
           'math_deletion_checks':deletion,'math_separate_checks':separate,
           'actual_full_history_k_min_at_completion':full['observer']['targets'][w['target']]['k_min']})
    # Every coalition in all 48 actual observer prefixes is checked algebraically.
    prefix_checks=0;unknown_prefix=[]
    for s in traces:
        for g in s['observer']['coalitions']:
            for a in data['assets']:
                status=target_status(g['known'],a['target']);prefix_checks+=1
                if status=='UNKNOWN':unknown_prefix.append({'method':s['method'],'step':s['step'],'mask':g['mask'],'target':a['target']})
                elif (status=='UNIQUE')!=(a['target'] in g['targets']):
                    disagreements.append({'method':s['method'],'step':s['step'],'mask':g['mask'],'target':a['target'],'math':status})
    opt_checks=[];byid={a['action_id']:a for q in data['requests'] for a in q['candidates']}
    for mode in ['fixed','all']:
        r=read(f'opt_{mode}_primary.json')
        if not r['completed']:continue
        for plan in r['optimal_plans']:
            views=[set() for _ in range(4)]
            for aid in plan['actions']:
                a=byid[aid];views[a['recipient']].update(decode(a['reply'],a['task_id']))
            for mask,members in coalitions():
                known=set().union(*(views[i] for i in members))
                for target in data['assets']:
                    status=target_status(known,target['target'])
                    opt_checks.append({'mode':mode,'plan_code':plan['code'],'mask':mask,'target':target['target'],'math_status':status})
    all_verified=not disagreements and not unknown_prefix and all(c['math_status']=='NONUNIQUE' for c in opt_checks)
    write('witness_verification.json',verified_witnesses)
    write('independent_verification.json',{'frozen_inputs_unchanged':True,'math_horn_disagreements':disagreements,
        'math_unknown_fields':math['unknown_field_count'],'unknown_prefix_targets':unknown_prefix,
        'prefix_target_checks':prefix_checks,'fraction_countermodels_verified':counterexamples,
        'witnesses_verified':len(verified_witnesses),'optimal_plan_target_checks':opt_checks,
        'all_claims_verified':all_verified,'source_and_prior_contracts_unchanged':True})
    assert all_verified,'STOP: unresolved independent evidence; do not report defended success'

    # Explicit exact-k and partial-field tables, including the globally easier attack.
    with (OUT/'recovery_by_step.csv').open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['method','step','target','k_min','exact_k1','exact_k2','exact_k3'])
        writer.writeheader()
        for s in traces:
            for target,p in s['observer']['targets'].items():
                writer.writerow({'method':s['method'],'step':s['step'],'target':target,'k_min':p['k_min'],
                    **{'exact_k'+str(k):p['counts_exact_k'][str(k)] for k in [1,2,3]}})
    partial=[]
    for method in ['NoGate','Reset','Shared']:
        for field in ['F_push','f','d_push']:
            ss=[s for s in traces if s['method']==method]
            first=next((s['step'] for s in ss if any(field in g['partial_T06_fields'] for g in s['observer']['coalitions'])),None)
            final=ss[-1]
            partial.append({'method':method,'field':field,'first_step':first,
                'final_k_min':min((g['size'] for g in final['observer']['coalitions'] if field in g['partial_T06_fields']),default=None),
                'counts_exact_k':{str(k):sum(g['size']==k and field in g['partial_T06_fields'] for g in final['observer']['coalitions']) for k in [1,2,3]}})
    write('partial_T06_recovery.json',partial)
    count=Counter((w['method'],w['kind'],w['k_min_for_support']) for w in witnesses)
    write('witness_counts.json',[{'method':m,'kind':kind,'support_people':k,'count':n} for (m,kind,k),n in sorted(count.items())])
    record=['# 最小跨题见证与独立反世界\n',
      '所有340项动作最小支持（含直接、单题和跨题）保存在minimal_witnesses.json；witness_verification.json逐一记录方程、删动作及逐题分开核验。以下重点列Reset的全部漏判支持。\n',
      '**人数口径**：support人数是删减支持使用的不同接收者数；实际完整历史的k_min另列。不能因删掉已交付信息得到一个三人支持，就声称实际需要三人。Reset第13步已有单人恢复路径。\n']
    for w in verified_witnesses:
        if w['method']!='Reset':continue
        record+=[f'## {w["target"]} · 支持{w["actions"]}\n',
           f'来源类型{w["kind"]}；题目{w["tasks"]}；支持接收者{w["members"]}，人数{w["k_min_for_support"]}；实际完整历史在完成步{w["last_step"]}的最小人数为{w["actual_full_history_k_min_at_completion"]}。',
           f'实际交付：{json.dumps(w["actual_deliveries"],ensure_ascii=False)}',
           f'联合观察：{w["known_values"]}。公开方程唯一性证书：{certs[w["math_key"]]["fields"]}。']
        for x in w['math_deletion_checks']+w['math_separate_checks']:
            c=certs[x['math_key']];targetfields=next(a['fields'] for a in data['assets'] if a['target']==w['target'])
            nonunique=next((c['fields'][t] for t in targetfields if c['fields'][t]['status']=='NONUNIQUE'),None)
            record.append(f'- 反事实{x}；符合所有可见量、但目标不同的世界：{nonunique}。')
    record+=['''
## 最简可手算说明

T07目标：r0在第1步（T05）拿质量30kg，第13步（T08）拿末动能95.75J，独自计算v1²=2×95.75/30=383/60。只有质量不能确定末动能；只有末动能不能确定质量，因此删任一动作均不恢复。两条数据分属不同题，按同全局方程分别检查均不足。

T05目标：r0在第5步（T06净力法）拿净功92J，第13步（T08）拿末动能95.75J，独自计算K_initial=95.75−92=3.75J。第5步回答还包含N=115N,d_push=.8m，不能忽略这些额外信息；独立反世界已对整条回答约束核验。即使保留N,d,W，缺少末动能时初速仍可变化；只有末动能时初动能与净功仍可变化。

这两条都是跨题累计见证，不是第13步单条回答直接泄露；四个目标、公开规则及权限在Reset/Shared相同，差异来自Reset忘记已经交付的约束。第13步Reset局部只有K_final，可安全通过；观察者仍持有第1/5步，故判违规。
''']
    write('CROSS_QUESTION_WITNESSES.md','\n'.join(record))
    opt=read('offline_references.json');shared=next(s for s in summary if s['method']=='Shared');reset=next(s for s in summary if s['method']=='Reset')
    lines=['# RESULT · 同一包裹实例跨题交付历史\n',
      '**结论：存在经独立方程核验的跨题漏判，单人即可；Shared消除本次漏判，总正常回答数不减，且达到固定候选和全候选离线上限。** 决定STOP：本批请求不支持继续开发复杂交付调度。\n',
      'EXPLORATORY。一个实例、4个关联教材题、16个研究者构造请求；不是4份独立样本或真实学生需求。保护是模拟实例授权，不保护公开公式。模型/GPU/付费API/新数据下载/训练均0。\n',
      '|组别|正确回答/16|拒答|实际UTF8字节|被完整恢复目标/4|控制器误放步|\n|---|---:|---:|---:|---:|---|']
    for s in summary:lines.append(f'|{s["method"]}|{s["correct"]}/16|{s["refusals"]}|{s["output_bytes"]}|{s["final_targets_recovered"]}/4|{s["false_safe_allow_steps"] if s["method"]!="NoGate" else "无拦截；不定义误放"}|')
    lines+=['\n## 各目标首次恢复与人数\n',
      '|组别|T05初动能|T06完整输入三元组|T07末速平方|T08滑停距离|\n|---|---|---|---|---|']
    for s in summary:
        cells=[]
        for target,step in s['first_recovery_steps'].items():
            if step is None:cells.append('未恢复');continue
            r=next(x for x in traces if x['method']==s['method'] and x['step']==step)
            final=next(x for x in traces if x['method']==s['method'] and x['step']==16)
            cells.append(f'第{step}步，初次k_min={r["observer"]["targets"][target]["k_min"]}；最终k_min={final["observer"]["targets"][target]["k_min"]}')
        lines.append('|'+s['method']+'|'+'|'.join(cells)+'|')
    lines+=['\n|组别|恰1人最终可恢复目标|恰2人|恰3人|\n|---|---|---|---|']
    for s in summary:lines.append('|'+s['method']+'|'+'|'.join(', '.join(s['final_recovery_by_exact_k'][str(k)]) or '无' for k in [1,2,3])+'|')
    lines+=['\n## 真实差异，不能以字节减少代替解释\n',
      'Reset允许但观察者判违规：仅第13步；此次新增恢复T05、T07。NoGate第2–16步交付后都已存在违规，新增完整目标出现在第2/5/7步；这些后续步数不是独立成功次数。Shared无误放。',
      '第13步r0请求T08停止前动能，Reset答95.75J，Shared拒答。第16步r3请求质量，Reset因本题残留95.75J而拒答；Shared允许30kg。两组各8次正确、8次拒答，仅对换一条回答；Shared比Reset少11字节。Shared比NoGate少8次正确回答，不能把50%效用下降藏起来；比Reset的净效用损失为0，但具体被满足的请求不同。',
      '关键单人推导：r0第1步m30kg＋第13步K_final95.75J→v1²=383/60；r0第5步W_net92J＋第13步K_final95.75J→K_initial3.75J。每个最小支持逐题分开和删任一必要动作均有显式反世界。见CROSS_QUESTION_WITNESSES.md。',
      '\n## 每步实际决定\n',
      '|步|题/身份|规范候选|NoGate|Reset|Shared|Reset新增目标|\n|---:|---|---|---|---|---|---|']
    for q in data['requests']:
        ss={m:next(s for s in traces if s['method']==m and s['step']==q['step']) for m in ['NoGate','Reset','Shared']}
        lines.append(f'|{q["step"]}|{q["task_id"]}/r{q["recipient"]}|{q["canonical_action_id"]}|'+'|'.join(ss[m]['controller_decision'] for m in ['NoGate','Reset','Shared'])+'|'+', '.join(ss['Reset']['new_targets'])+'|')
    lines+=['\n## T06完整目标与部分字段\n',
      '|组别|字段|首次恢复步|最终最小人数|\n|---|---|---|---|']
    for p in partial:lines.append(f'|{p["method"]}|{p["field"]}|{p["first_step"]}|{p["final_k_min"]}|')
    lines+=['T06仍按F_push、f、d_push三元组全部恢复判完整；Reset/Shared可能公开了d_push而不完整恢复T06。不能把部分字段写成全无披露。\n',
      '## 离线效用上限\n',
      '|候选空间|主枚举/独立枚举计划数|安全计划数|最优正确数|Shared差距|CPU秒（主/独立）|\n|---|---:|---:|---:|---:|---:|']
    for mode in ['fixed','all']:
        p=read(f'opt_{mode}_primary.json');r=read(f'opt_{mode}_independent.json')
        lines.append(f'|{mode}|{p["checked"]}/{r["checked"]}|{len(p["safe_codes"])}|{p.get("opt_correct")}/16|{p.get("opt_correct",0)-shared["correct"]}|{p["cpu_seconds"]:.3f}/{r["cpu_seconds"]:.3f}|')
    lines+=['''
两空间穷举完成且逐计划安全编码、最优计划完全一致，全部CPU时间在预登记预算内。唯一最优计划与Shared实际8条动作完全相同，166字节；可选T06另一功法未增加效用。全局知识单调，最终安全蕴含所有前缀安全；代表计划又经过原ExactK3逐步、独立set以及方程反世界检查。两个上限都提前看到全部请求，不是可部署在线算法。

独立方程额外核验最优计划可行与全部实际历史；已知每条Horn规则都为正值公共方程的有效推论，因此规则枚举不会排除真实安全计划。Shared已达到这一安全松弛的上界并获数学安全证据，本批请求不存在更高正确数的交付/选答空间。没有训练需求预测器，也没有以穷举编造在线算法优势。

## 来源、判据与失败

变量映射见INSTANCE_MAPPING.md：两种速度/能量/距离分开；T06摩擦损失4J是负功的幅值，滑停摩擦功另为−95.75J；T08明确摩擦保持不变。全部目标与授权第一步前注册，三组同一全局规则哈希，Reset仅清交付历史。观察者按回答文本和单位/阶段解析，不使用控制器安全标签。所有输出/拒答完整保存，拒答为空且正确0。

准备编号01因上一轮可读文本镜像LF、清单记录归档CRLF字节而失败；随后误调用回放入口也因缺freeze在前置检查停止，未执行任何回放。原目录及失败保留，编号02在固定提交归档原始字节核验后冻结并运行一次；不更改任何映射语义/目标/候选/身份/顺序。该旧发布换行差异在本轮同步中明确区分归档原始字节和可读镜像哈希，不改旧结果。

所有实际48个前缀×14个联盟×4目标=2688项恢复判定，经315组不同观察的独立方程核验；数学UNKNOWN=0（仅本冻结名义契约），具体数值反世界经另一份Fraction内核验证。全部340个最小支持（335 NoGate、5 Reset、0 Shared）保留；它们高度重叠、包含重复回答，不是340个独立风险样本。删减支持有1/2/3人，并不改变实际Reset已可由1人恢复的事实。

这些结果只证明同一实例持久交付历史对于本序列的一致约束必要性；未证明真实课堂收益、实际版权保密、自动自然语言解析能力、超出闭包的新算法或泛化效果。完整原题/网页及引用上下文若公开给接收者，目标可直接计算；当前是闭合可见性模拟。公开教材规律始终公开。

## 决定与下一步唯一建议

**STOP：停止在本批请求上开发复杂调度。** 唯一后续建议是把这次已核验的单人跨题见证固化为实例ID/历史作用域的离线回归验收，先核对系统集成是否错误地按题清历史；这只是建议，本轮没有修改生产控制器、启动集成队列或执行下一轮。若将来讨论实际教学价值，需要另行授权、合规真实请求与独立标注，而不是重复本实例刷数。
''']
    write('RESULT.md','\n'.join(lines))
    write('decision.json',{'decision':'STOP','completion':'COMPLETE_STOP_NO_NEXT_QUEUE',
       'cross_question_false_negative_verified':True,'reset_false_safe_steps':reset['false_safe_allow_steps'],
       'minimum_people_actual_history':1,'shared_correct':shared['correct'],'reset_correct':reset['correct'],
       'shared_minus_reset_correct':shared['correct']-reset['correct'],'fixed_candidate_opt':opt['fixed']['opt_correct'],
       'all_candidate_opt':opt['all']['opt_correct'],'shared_gap_fixed':opt['fixed']['opt_correct']-shared['correct'],
       'shared_gap_all':opt['all']['opt_correct']-shared['correct'],'algorithm_novelty_claim':False,
       'scope':'one source-grounded instance; researcher requests and simulated permissions',
       'next_unique_recommendation':'retain witnessed cross-question accumulation as instance-history-scope regression; no implementation started'})
    write('README.md','# 同一教学实例跨题信息累积\n\n先读RESULT.md；协议PROTOCOL.md；变量INSTANCE_MAPPING.md；全部回放replay.json与method_summary.csv；最小见证CROSS_QUESTION_WITNESSES.md和witness_verification.json；固定/全候选离线上限opt_*；独立核验independent_verification.json。EXPLORATORY，一个实例，真实教材＋研究者请求与模拟授权。已停止。\n')
    previous_failure=PROJECT_ROOT/'var/results/c2rag_cross_question_history_20261027_01/FAILURE.json'
    write('FAILURES_AND_LIMITATIONS.json',{'preparation_run01':json.loads(previous_failure.read_text(encoding='utf8')),
         'run02_execution_failures':[],'unknown_fields':math['unknown_field_count'],'math_issues':math['issues'],
         'independent_annotation':False,'real_student_logs':0,'source_instances':1,'models':0,'paid_api':0,'gpu':0})
    write('code_manifest.json',{str(f.relative_to(PROJECT_ROOT)):sha(f.read_bytes()) for f in sorted(SOURCE.glob('*')) if f.is_file()})
    write('MANIFEST.sha256.json',{p.relative_to(OUT).as_posix():sha(p.read_bytes()) for p in sorted(OUT.rglob('*')) if p.is_file()})
    print(json.dumps({'verified':all_verified,'countermodels':counterexamples,'prefix_target_checks':prefix_checks,
                      'supports':len(witnesses),'decision':'STOP'},ensure_ascii=False))


if __name__=='__main__':main()
