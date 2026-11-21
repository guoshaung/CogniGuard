"""Final local audit and preservation of editorial corrections, not rerunning main."""
import itertools
import json
import shutil
from experiments.c2rag_r34_20261028_02.common import *
from experiments.c2rag_r34_20261028_02.verify import parse, tables, union, masks

def main():
    frozen()
    text=(OUT/'RESULT.md').read_text(encoding='utf8')
    assert '(r0 P、r1 V、r2 T)' in text
    write('RESULT.initial.md',text)
    corrected=text.replace('(r0 P、r1 V、r2 T)','(r0 V、r1 P、r2 T)')
    (OUT/'RESULT.md').write_text(corrected,encoding='utf8',newline='\n')
    write('REPORTING_CORRECTION.json',{'field':'RESULT.md representative three-person example ordering',
        'before':'r0 P, r1 V, r2 T','after':'r0 V, r1 P, r2 T',
        'evidence':'traces/S03-uniform-2__M0-NoGate.json steps0,1,2',
        'metrics_data_or_contracts_changed':False,'initial_preserved':'RESULT.initial.md'})
    write('MINIMAL_WITNESSES.md',"""# 两个可人工复核的代表案例

## 真三人前缀：S03-uniform-2
零基步骤0/r0收到V=4 V0；1/r1收到P=2 P0；2/r2收到T=2 T0。同一气样、同一实例，三题不同。
三人合并 nR=PV/T=4 P0V0/T0；任意两人不足。
去掉r0/V：同P2/T2，V2或V4给nR2或4。
去掉r1/P：同V4/T2，P1或P2给nR2或4。
去掉r2/T：同P2/V4，T1或T2给nR8或4。
全部反世界都在冻结正值域里。三人此前各只收到一条，单人无提前积累；单题分开都不恢复。
到后续第5步r1又收到V、r2已有T，因此后续可能两人恢复。不能把这一前缀结论写成完整流始终需要三人。
最小动作集、逐删除反世界索引和全部三人前缀见minimal_witnesses/structure_audit.json。

## 同效用、不同兼容性：S02-uniform-2
零基步骤1/r1的正常任务：用任一种功法算净功并报告两个中间量。两答均92J：
A各力功法：WA96J、损失4J、W92J；B净力法：N115N、d0.8m、W92J。
两答各自安全，可能世界集合彼此不包含。未来步骤2/r2请求N115N。
A+N：d=(WA-loss)/N=92/115=0.8m，F=WA/d=120N，f=loss/d=5N，恢复完整输入。
B+N：N只是重复，仍不能分开F与f；至少三个冻结可行输入对支持同N115/d0.8/W92。
这证明正确回答选择存在兼容性差异，但并不证明需要超出固定菜单的新算法。
这里推导A+N在连续正域也成立；另一个仅N+WA的捷径只在冻结有限域成立，二者不能混淆。
此分支对照是同实际前缀的可核验反事实，不作为第二条真实运行攻击样本。全部证据answer_compatibility_certificates.json。
""")
    banks={b['id']:b for b in read('public/banks.json')};truths={t['id']:t for t in read('private/truth.json')}
    # Check direct safety judgments of every candidate at every actual prefix,
    # and label voluntary safe refusals separately from mistaken risk detection.
    risk=[];totals={'candidate_checks':0,'risk_false_negative':0,'risk_false_positive':0,'voluntary_safe_refusals':0}
    engine=module('engines');reference=module('reference')
    for row in read('evaluated_rows.json'):
        bank=banks[row['asset']];truth=truths[row['asset']];table=tables(truth);trace=read(row['trace']);views=[0]*4
        comp=engine.Compiled(bank['case']);state=engine.METHODS['ExactK3'](comp)
        for event in trace['steps']:
            feasible=[]
            for candidate in bank['queries'][event['q']]['answers']:
                v=views.copy();v[event['recipient']]|=parse(candidate['reply'],bank,truth)
                bad=any(table[union(v,m)]['recover'] for m in masks() if m not in bank['case']['assets'][0]['authorized'])
                _,primary,_=state.trial({event['recipient']:candidate['facts']})
                totals['candidate_checks']+=1
                totals['risk_false_negative']+=int(bad and not primary);totals['risk_false_positive']+=int(primary and not bad)
                assert bad==primary
                if not bad:feasible.append(candidate['id'])
            voluntary=not event['reply'] and bool(feasible)
            totals['voluntary_safe_refusals']+=int(voluntary)
            risk.append({'stream':row['stream'],'method':row['method'],'step':event['step'],'safe_candidates':feasible,
                'refused':not bool(event['reply']),'voluntary_safe_refusal':voluntary})
            facts=[]
            b=parse(event['reply'],bank,truth)
            facts=[o for i,o in enumerate(bank['observations']) if b&(1<<i)]
            state,_,_=state.trial({event['recipient']:facts});views[event['recipient']]|=b
    write('risk_judgment_audit.json',{'totals':totals,'steps':risk})
    for independent in read('opt_independent.json'):
        assert independent['safe_plans']==read(f'opt/{independent["stream"]}.json')['opt']['safe_leaves']
    # Degenerate initial public-policy conflict is explicit, not counted as safety.
    pub=[]
    for bank in banks.values():
        case=json.loads(json.dumps(bank['case']));case['public']=['TARGET'];case['assets'][0]['authorized']=bank['case']['assets'][0]['authorized']
        assert reference.unsafe(case,[set() for _ in range(4)])
        pub.append({'asset':bank['id'],'if_public_target_still_marked_restricted':'POLICY_INFEASIBLE_FROM_INITIAL_STATE',
            'main_public_control_policy':'public instance treated authorized, not claimed secret'})
    write('PUBLIC_SOURCE_POLICY_BOUNDARY.json',pub)
    # Fingerprint all local source code, including post-run analysis, without
    # changing any pre-execution code-hash manifest.
    code={p.relative_to(PROJECT_ROOT).as_posix():sha(p.read_bytes()) for src in [SOURCE,PROJECT_ROOT/'experiments/c2rag_r34_20261028_01'] for p in src.glob('*.py')}
    write('source_code_sha256.json',code)
    write('FINAL_QA.json',{'complete':True,'frozen_files_unchanged':True,'full_main_runs':1,'failed_preceding_run_retained':True,
        'independent_legal_plans':sum(x['all_legal_plans'] for x in read('opt_independent.json')),'risk_judgment_checks':totals,
        'no_result_driven_contract_changes':True,'standalone_language_model_attack_tested':False,
        'stopped_no_next_experiment':True})
    write('LICENSE_SOURCES.md','OpenStax educational backgrounds, cached CC BY-NC-SA 4.0: https://creativecommons.org/licenses/by-nc-sa/4.0/ . Attribution and exact page locators/hashes in sources.json. Noncommercial research adaptation, same-license source excerpts/adaptations. All protected instance values/domains/permissions and demand streams are SYNTHETIC. Public laws and textbook expressions are not asserted confidential. No actual restricted teacher work/student records.\n')
    members={p.relative_to(OUT).as_posix():sha(p.read_bytes()) for p in OUT.rglob('*') if p.is_file()}
    write('MANIFEST.sha256.json',members)
    print(json.dumps({'files':len(members),'risk_checks':totals,'seal_complete':True}))

if __name__=='__main__':main()
