"""Create reports from preserved observations; never rerun either baseline."""
import collections
import copy
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path
from src.oracle import solve
from src.wire import digest

H=Path(__file__).resolve().parent; ROOT=H.parents[1]
def write(p,x):
    if p.exists(): raise FileExistsError(p)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n','utf8')
def text(p,s):
    if p.exists(): raise FileExistsError(p)
    p.write_text(s,'utf8')

def main():
    rows=[json.loads(s) for s in (H/'runs/initial/results.jsonl').read_text('utf8').splitlines()]
    metrics=json.loads((H/'metrics.json').read_text('utf8'))
    summary=json.loads((H/'runs/initial/summary.json').read_text('utf8'))
    inventory=json.loads((H/'history_inventory.json').read_text('utf8'))
    groups={}
    for r in rows:
        data=(H/r['path']).read_bytes(); h=hashlib.sha256(data).hexdigest()
        groups.setdefault(h,[]).append(r)
    cache=[]
    for h,alias in groups.items():
        for r in alias[1:]:
            cache.append({'sha256':h,'canonical_input':alias[0]['path'],'alias_input':r['path'],
                          'same_verdicts':all(r['methods'][m]['verdict']==alias[0]['methods'][m]['verdict'] for m in ['B1','B2']),
                          'same_duties':all(r['methods'][m]['breaches']==alias[0]['methods'][m]['breaches'] for m in ['B1','B2'])})
    write(H/'runs/dedup_mapping.json',{'planned_views':76,'unique_bytes':len(groups),'aliases':cache,
             'notes':'Initial implementation evaluated aliases; no new solver calls. Cache-equivalence check preserves raw results.'})
    chosen=next(r for r in rows if r['scenario']=='S10' and r['topology']=='centralized' and r['view']=='full' and not r['paired'])
    x=json.loads((H/chosen['path']).read_text('utf8'))
    x['events']=[e for e in x['events'] if e['event_type'] in ['effect_commit','revocation_published']]
    for e in x['events']:
        e['causal_parent_ids']=[]
        e['fixture_digest']=digest({k:v for k,v in e.items() if k!='fixture_digest'})
    proof=solve(x); deletions=[]
    for e in x['events']:
        y=copy.deepcopy(x);y['events']=[v for v in y['events'] if v['event_id']!=e['event_id']]
        deletions.append({'removed':e['event_type'],'verdict':solve(y)['verdict']})
    write(H/'counterexamples/minimal_two_event_input.json',x)
    write(H/'counterexamples/minimal_two_event_certificate.json',{'type':'IDENTIFIABILITY_LIMIT',
          'not_algorithm_failure':True,'reference':proof,'event_deletion_checks':deletions,
          'minimality_scope':'event deletion within this frozen rule fragment; policy/object facts remain',
          'extra_baseline_calls':0,'oracle_certificate_checks':3})
    text(H/'counterexamples/README.md',
         '# 最短不可识别性证书\n\n固定祖先受限对象，实际效果t=11。公开撤销界为[10,12]。\n'
         '历史一撤销t=10，动作违规；历史二撤销t=12，动作合规。两者公开字节完全相同。\n'
         'minimal_two_event_input.json只保留撤销/效果两事件。独立O得到一正一负见证；\n'
         '删去任一事件且保留完整性假设，均变为确定合规，因此在该删事件类中局部最小。\n'
         '不是最强算法失败，不是多Agent专属，也不能凭新增算法恢复缺失顺序。\n'
         '获取可信的撤销—效果顺序/接收端提交证据才改变可判定性。\n')
    fields=['input_id','trace_id','scenario','topology','paired','view','phase','oracle','B1','B2','passed','input_sha256','evidence_bytes','events','query_available','query_used','effect_commit_records']
    with (H/'RESULTS.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:
            data=(H/r['path']).read_bytes();x=json.loads(data)
            row={k:r[k] for k in fields if k in r}
            row.update(oracle=r['oracle']['verdict'],B1=r['methods']['B1']['verdict'],B2=r['methods']['B2']['verdict'],
                       input_sha256=hashlib.sha256(data).hexdigest(),evidence_bytes=len(data),events=len(x['events']),
                       query_available=x['check']['query_available'],query_used=x['check']['query_used'],
                       effect_commit_records=sum(e['event_type']=='effect_commit' for e in x['events']))
            w.writerow(row)
    # Actual primary-source reading locations, no downloaded articles or copied full text.
    literature=[
      ('R1','PeerReview: Practical Accountability for Distributed Systems','Andreas Haeberlen; Petr Kouznetsov; Peter Druschel',2007,'SOSP','published','https://www.sigops.org/s/conferences/sosp/2007/papers/sosp118-haeberlen.pdf','sections 3-5 and 7','signed deterministic logs -> observable deviation evidence','correct witnesses; deterministic reference; signatures','replay; secure records','authenticated network not reproduced'),
      ('R2','Using the ACE framework to enforce access and usage control with notifications of revoked access rights','Marco Rasori; Andrea Saracino; Paolo Mori; Marco Tiloca',2024,'IJIS','published','https://link.springer.com/article/10.1007/s10207-024-00877-1','4.1-4.2; evaluation','tokens / usage policy -> revocation notification','ACE/UCON; reliable token identity; network delay','usage checking; notification','not a full forensic auditor'),
      ('R3','Runtime Verification over Out-of-order Streams','David Basin; Felix Klaedtke; Eugen Zalinescu',2019,'TOCL','author final','https://people.inf.ethz.ch/basin/pubs/tocl19.pdf','3.1-3.4; 4-5; 6','partial timed observations -> three-valued monitoring','known timestamp observations; explicit gaps','MTL freeze; DAG refinement; no fabricated Boolean verdict','observational semantics not arbitrary supervaluation'),
      ('R4','Distributed Runtime Verification Under Partial Synchrony','Ritam Ganguly; Anik Momtaz; Borzoo Bonakdarpour',2020,'OPODIS; publication 2021-01-25','published','https://drops.dagstuhl.de/doi/10.4230/LIPIcs.OPODIS.2020.20','2; 3.2-3.5; 4','happened-before / bounded clock skew / LTL -> possible verdicts','known skew; HLC; model','SMT consistent cuts; segmentation','Z3 unavailable; exact finite reference only'),
      ('R5','MAP-Graph: Provenance-Aware Shared Memory for Multi-Agent Workflows','Yiqi Wang; Zihao Yan; Jiaqi Zhang; Zhangkai Wu; Mingkai Zheng; Zequn Sun; Yanming Zhu; Taotao Cai',2026,'arXiv','v1 preprint','https://arxiv.org/html/2608.10509v1','methods; B.1-B.2','memory provenance -> filtered retrieval / audit','fixed role order; explicit graph; simulated effects','ancestor revocation and audit','not arbitrary asynchronous production'),
      ('R6','AUDITA: certified auditing and causal attribution of adverse outcomes in autonomous multi-agent systems','Zhixu Du; Yiran Chen',2026,'arXiv','v2 preprint','https://arxiv.org/html/2608.22160v2','Methods A1-A3; gate/grade/certify; supplements 1/3/5/7','certified command graph -> breach / causal intervals','recorded channel; replayable stack; key custody','effect gate; admissible completions; replay','not legal responsibility; full system not reproduced'),
      ('R7','Failure-aware Runtime Verification of Distributed Systems','David Basin; Felix Klaedtke; Eugen Zalinescu',2015,'FSTTCS','published','https://drops.dagstuhl.de/doi/10.4230/LIPIcs.FSTTCS.2015.590','official metadata / scope','faulty event stream -> monitoring verdicts','fault-aware observation assumptions','handling delayed / missing evidence','full algorithm not run'),
      ('R8','Monitoring Compliance Policies over Incomplete and Disagreeing Logs','David Basin; Felix Klaedtke; Srdjan Marinovic; Eugen Zalinescu',2012,'RV','author version','https://people.inf.ethz.ch/basin/pubs/rv12.pdf','introduction; semantic definitions / monitor','incomplete or disagreeing logs -> three-valued policy','explicit uncertainty interpretation','incomplete evidence refusal','trusted contradictory assertions differ from uncertain disputes'),
      ('R9','Policy Auditing over Incomplete Logs: Theory, Implementation and Applications','Deepak Garg; Limin Jia; Anupam Datta',2011,'CCS','published','https://people.mpi-sws.org/~dg/papers/ccs11-policy.pdf','primary paper overview / reduce description','partial logs and quantified policies -> residual policy','restricted quantification; known / unknown predicates','residual obligations','full reduce implementation not run'),
      ('R10','Beyond Corrected Memory: Execution Consistency in Multi-Agent Systems','Zhe Yu; Zixuan Wang; Peidong Wang; Hehai Lin; Ruochen Zhao; Chengwei Qin',2026,'arXiv','v1 preprint','https://arxiv.org/html/2610.08101v1','3; 4; 5; appendix A','contract and retained records -> V / N / U','coverage and duty semantics; extraction','receipt vs use vs fulfillment; indistinguishability','CAVERT extraction / production recovery not reproduced'),
      ('R11','Time, Clocks, and the Ordering of Events in a Distributed System','Leslie Lamport',1978,'CACM','published','https://lamport.azurewebsites.net/pubs/time-clocks.pdf','partial ordering; logical clock definition','distributed events -> happened-before','process order and messaging','causal partial order','clock magnitude does not prove causality')]
    with (H/'related_work.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['id','title','authors','year','venue','version_status','primary_url','read_locations','input_output','assumptions','overlap','unverified_or_not_reproduced']);w.writerows(literature)
    # Read-only provenance extension: actual later evidence omitted by old directory names.
    latest=ROOT/'experiments/cgc_real_integration_20261105_01'
    follow=[p for p in latest.iterdir() if p.is_file() and p.suffix in ('.md','.csv','.py')]
    follow += [ROOT/p for p in ['docs/design/PROFILE_CONSENT.md','cogniguard/applications/education/profile_consent.py',
                               'cogniguard/governance/audit.py','cogniguard/runtime/README.md','cogniguard/governance/README.md']]
    write(H/'history_followup_inventory.json',{'files':[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in follow]})
    # Verify old inputs unchanged after this task, not only at startup.
    old_changed=[]
    for r in inventory['files']:
        p=ROOT/r['path']
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:old_changed.append(r['path'])
    write(H/'runs/historical_immutability.json',{'checked':len(inventory['files']),'changed':old_changed})
    decision={'task_id':'CG-C-AUDIT-GATE-01','decision':'STOP','decision_scope':'Stop the claim that a new core algorithm is necessary for this frozen explicit-evidence fragment; retain auditing engineering',
         'problem_status':'NO_IN_TESTED_SCOPE','baseline_completeness':'COMPLETE_FOR_FROZEN_FINITE_FRAGMENT; FULL_PAPER_SYSTEMS_NOT_REPRODUCED',
         'multi_agent_specificity':'NOT_OBSERVED; SAME_DISTRIBUTED_SYSTEM_PROBLEM','novelty_status':'NO_NEW_ALGORITHM_PRESENT',
         'remaining_gap_type':'IDENTIFIABILITY_LIMIT','secondary_gaps':['EVIDENCE_ACQUISITION_GAP','PRODUCTION_ENGINEERING_GAP'],
         'evidence_level':'READ_ONLY_HISTORY_PLUS_SINGLE_PROCESS_FINITE_MODEL','allow_production_changes':False,
         'allow_new_algorithm_implementation':False,'closest_prior_work':['PeerReview','Garg reduce','Basin out-of-order RV','OPODIS partial synchrony','AUDITA','CAVERT'],
         'minimal_counterexample_path':'counterexamples/minimal_two_event_input.json',
         'counts':{'execution_traces':38,'audit_inputs':76,'unique_public_inputs':70,'extra_interface_checks':6,
                   'paper_system_reproductions':0,'new_production_runs':0,'not_run':3},
         'confidence':None,'confidence_basis':'Deterministic constructed cases only, not a population confidence estimate',
         'next_question':'Can the real delivery boundary provide trustworthy effect/receipt ordering and explicit dependency evidence to an existing audit verifier?'}
    write(H/'DECISION.json',decision)
    md='# 结论：STOP 当前“必须新增核心算法”的假设，保留审计能力\n\n'
    md+='38条有限构造轨迹、76审计视图（70种唯一公开字节），B1常规回放和B2参考枚举各76/76符合冻结标签及独立O。\n'
    md+='38/38可判定视图被正确确定，30/30必要拒绝，8/8无效证据识别；错误定违规0、错误定合规0，不必要拒绝0。\n'
    md+='这是作者构造、显式JSON和虚拟时钟的结果，不是随机安全率、生产集成验收或所有成熟系统的完整复现。\n\n'
    md+='## 已实际执行\n\n六类准入24/24后执行52条扩展视图，总76。未重跑旧191条矩阵。\n'
    md+=f"原始正式轮耗时{summary['elapsed_seconds']:.6f}秒，含152个审计子进程启动；各方法单输入最大候选6。\n"
    md+='两个独立算法判定实现另由独立O与手工冻结期望核对，152份证书检查通过。\n'
    md+='6次额外接口复核通过，包含逆转事件到达序、重复事件、oracle文件读取拒绝和修复后内存计量。\n'
    md+='内存计量初版返回0是API声明缺陷，不是零内存；原记录保留。修复后的六次子进程峰值约17.8MiB，不能冒称152个原进程均已测RSS。\n'
    md+='相同公开输入的6个别名未在初轮跳过计算；事后完整字节去重70种、缓存等价6/6，不扩充独立样本分母。\n\n'
    md+='## 具体最短轨迹与剩余问题\n\n对象含已冻结的profile.f祖先限制；实际效果t=11，公开撤销界[10,12]。\n'
    md+='撤销t=10对应违规，撤销t=12对应合规，但审计输入完全相同。两种拓扑均验证了相反真相的相同字节。\n'
    md+='最小证书只留两个事件；这是IDENTIFIABILITY_LIMIT，现有方法正确INDETERMINATE，不是算法错误。\n'
    md+='S3补录的安装后违规可定位执行节点D_RECHECK；S6旧版本回退可定位D_VERSION_MONOTONE；没有指控所有上游。\n'
    md+='只有6/76视图具有非空明确义务违背，其余空集合也纳入精确匹配，不能拿76/76夸大正例定位规模。\n\n'
    md+='## 全部场景\n\n'
    for s in sorted({r['scenario'] for r in rows},key=lambda s:int(s[1:])):
        a=[r for r in rows if r['scenario']==s]
        md+=f"- {s}：{len(a)}视图，{dict(collections.Counter(r['expected'] for r in a))}；B1/B2均匹配。\n"
    md+='\n按严格/陈旧/收尾语义、集中/分散拓扑、完整/受限视图的真实分母见metrics.json；逐例见RESULTS.csv。\n\n'
    md+='## 强基线、公平性与多Agent增量\n\n两方法共享相同规则、对象依赖、查询能力与证据预算；不用静态ACL支撑结论。\n'
    md+='B2仅REFERENCE_ENUMERATOR，没有Z3/任意LTL/MTL↓在线实现，不宣称最强论文方法失败。\n'
    md+='集中和A→B→C的配对判定一致；多出的交接边来自普通通信，未发现Agent特有算法问题。\n'
    md+='无法由本轮无模型JSON实验回答自然语言隐含依赖、随机模型回放或真实多机证据完整性。\n'
    md+='没有稳定算法反例，按门控不再做最多3条项目接口复核；该分支NOT_RUN，不将旧组件回归算本轮框架验收。\n\n'
    md+='## 普通缺陷与执行边界\n\n旧集成脚本哈希变化已有v2修订说明；当前历史324文件结束回读未变。\n'
    md+='本轮仅修复计量接线并核算去重，未改政策/判定代码/阈值，未伪造新算法。\n'
    md+='生产已有匿名会话同意锁与revision，但完整账号许可、派生对象和外部提交证据仍不足，属于工程/采集问题。\n'
    md+='没有发现计算瓶颈；最大6候选不能证明大系统可扩展，也不能用慢枚举声称新复杂性问题。\n'
    md+='GPU、LLM、付费API、环境安装、模型下载均0；没有启动任何长期Worker。默认本地交付，没有新远端上传授权。\n\n'
    md+='唯一后续问题：真实交付边界能否提供可验证的效果顺序、回执和显式依赖，供现成验证器使用？本轮不实施生产接线。\n'
    text(H/'RESULTS.md',md)
    text(H/'REPRODUCE.md',
      '# 复现和只读核验\n\n解释器：D:/pycharm/CogniGuard/.venv-langgraph/Scripts/python.exe，Python3.12.10。无需安装。\n'
      '实际已执行（从项目根目录）：\n\n```powershell\n'
      '.\\.venv-langgraph\\Scripts\\python.exe experiments/cg_c_audit_gate_20261108_01/inspect_history.py\n'
      '.\\.venv-langgraph\\Scripts\\python.exe experiments/cg_c_audit_gate_20261108_01/prepare_cases.py\n'
      '.\\.venv-langgraph\\Scripts\\python.exe experiments/cg_c_audit_gate_20261108_01/run.py freeze\n'
      '.\\.venv-langgraph\\Scripts\\python.exe experiments/cg_c_audit_gate_20261108_01/run.py run --run-id initial\n'
      '.\\.venv-langgraph\\Scripts\\python.exe experiments/cg_c_audit_gate_20261108_01/check_results.py\n```\n'
      '\n以上首次写入入口故意拒绝覆盖，不能对本归档原地重跑。正式结果全部保留。\n'
      '下列只读核验命令可重复执行；它核对冻结文件/历史输入/证书，不追加正式审计或模型实验：\n\n'
      '```powershell\n.\\.venv-langgraph\\Scripts\\python.exe experiments/cg_c_audit_gate_20261108_01/verify_archive.py\n```\n'
      '\n公开输入与评分真值物理分目录；基线通过stdin接收JSON，导入后禁用文件读取。\n'
      '这是一项输入隔离测试，不是操作系统沙箱安全认证。原始与计量修复版分别记录。\n')
    print(json.dumps({'historical_changed':old_changed,'dedup_aliases':len(cache),'minimal_proof':proof,
                      'decision':decision['decision'],'rows':len(rows)},ensure_ascii=False))

if __name__=='__main__':main()
