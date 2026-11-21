"""Produce bounded sanitized protocol/results/failures/decision delivery."""
from pathlib import Path
import json,hashlib,re
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def save(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def text(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(v)
def main():
    attempt=HERE/'attempt_02';summary=load(attempt/'summary.json');audit=load(HERE/'postrun_audit.json')
    assert audit['status']=='PASS' and summary['executed_and_scored']==81 and summary['unscorable']==0
    delivery=HERE/'sanitized_delivery';delivery.mkdir(exist_ok=False)
    groups=summary['groups'];scores=load(attempt/'independent_scores.json')
    save(delivery/'stage1_e_protocol.json',load(HERE/'protocol.json'))
    save(delivery/'case_results.json',{'scope':'81 finite synthetic mechanism cases, not LLM safety evidence','results':scores,'oracle':'Frozen hidden finite arithmetic rule in separate scorer; no CG risk score used as truth','raw_records':'Retained locally with per-case raw_sha256; not uploaded private core or raw observer stacks'})
    save(delivery/'group_metrics.json',{'groups':groups,'per_trace_budget':{'scripted_generation_attempts':3,'query_opportunities':3,'input_bytes':9216,'candidate_output_bytes':3072,'model_tokens':None,'real_model_calls':0},'normal_task':'Public score-field extraction with fixed readiness acknowledgements; not broad teaching utility','restricted_metric':'Actual received calibration facts and finite joint derivability, not string-similarity proxy','all_direct_joint_target_deliveries':0,'normal_overblocking_all_groups':0,'not_independent_samples_warning':'Three closely structured assets; repeated topology/configuration cells are not independent dataset examples'})
    failures={'attempt_01':load(HERE/'attempt_01/failure_review.json'),'attempt_02_main':{'completed':81,'scorable':81,'unscorable':0,'main_worker_failures':0},'probe_handler_failure':load(attempt/'truth_probe/failure_review.json'),'repaired_probe':{'status':audit['truth_probe'],'original_failure_preserved':True,'main_cases_rerun':False},'bootstrap_initialization':{'workers':9,'local_gethostname_reads':9,'blocked_subprocess_attempts':27,'successful_subprocess_launches':0,'source_or_gold_loaded_before_bootstrap':False,'scope':'All startup events retained separately; strict existing observer installed before CG/source/gate execution. No connect/DNS/data allowance added.'},'legacy':{'S00-11':'FAIL preserved','S00-12_supplement':'FAIL preserved','v2_S00-12':'NOT_EXECUTED preserved'},'failure_data_policy':'Failure counts and precise causes retained; raw full stacks and all original script versions stay local.'}
    save(delivery/'failure_records.json',failures)
    table='| 架构 | 防护配置 | 正常正确 | 互补片段组合恢复 | 校准单元恢复 | 篡改边实际接收 | 释放拒绝 |\n|---|---|---:|---:|---:|---:|---:|\n'
    costtable='| 架构 | 配置 | 查询/生成槽 | 输入字节 | 候选输出字节 | 交付回复字节 | trace总毫秒 | CGC边处理毫秒 |\n|---|---|---:|---:|---:|---:|---:|---:|\n'
    for g in groups:
        table+=f"| {g['architecture']} | {g['defense']} | {g['normal_correct_n']}/{g['normal_n']} | {g['fragment_joint_n']}/{g['fragment_n']} | {g['fragment_unit_coverage']:.1%} | {g['modified_unauthorized_edges']}/{g['relay_edge_attempts']} | {g['gate_refusals']}/{g['gate_attempts']} |\n"
        costtable+=f"| {g['architecture']} | {g['defense']} | {g['query_opportunities']}/{g['generation_attempts']} | {g['input_bytes']} | {g['candidate_output_bytes']} | {g['delivered_reply_bytes']} | {g['total_elapsed_ms']:.3f} | {g['total_cgc_ms']:.3f} |\n"
    source_table='| 既有实现路径 | SHA256 |\n|---|---|\n'+''.join(f'| {p} | `{h}` |\n' for p,h in audit['source_hashes'].items())
    report=f'''# CogniGuard Stage1-E：已执行的合成机制探索

决策 **PIVOT（仅本批观察增量的新算法叙事）**。分离账本下，多Agent与单Agent多会话均能联合恢复3/3个目标；共享资产账本将两者降至0/3，正常公开任务均3/3正确。**本批全部观察增量可由会话/账本分片解释，未显示不可由强基线解释的多Agent协作效应。** 这不证明现实多Agent没有风险，也不证明共享账本普遍解决语义重构。

## 停止原因复核与本轮实际执行

上轮 Stage1 preparation 已完成准备和24条纯调度排练，未执行真实C²-RAG/CGC：正式研究缺双人独立真值，五报告上传另被审批拒绝。两者是不同原因。Stage1-C的正式独立真值门槛本轮仍未通过；本轮单独执行Stage1-E合成探索，不把准备阶段的限制错误延续为禁止一切本地执行。

本地 `D:/pycharm/CogniGuard/experiments/stage1_e_20261019_01/`；本地HEAD d01953234add03996cb9200af3ff02c9592697e7，现存未提交修改未覆盖。读取research-sync main 78ee8074151d422f55f287f79d0d36390cde80ec的交接目录，并读取本地 preparation目录及拒绝回执。未补传上轮五报告。原S00-11和补测S00-12 FAIL、旧v2 S00-12 NOT_EXECUTED全部保留，不重跑/修绿。

主运行规模：**3架构×3配置×3资产×3意图=81条完成且可评分trace**，每组9条。正常/互补片段/篡改转发各3资产。共243次固定生成、243次片段查询机会、243次真实gate_fact调用；Shared-Asset+CGC组真实issue/admit各54次。模型API、真实/本地推理、训练、新语义算法、核心改动均0。

## 真实实现接入与范围

直接导入原 `experiments.c2rag_v3.fact_release.gate_fact`，使用其既有source witness、short-answer、实际输出cost预算门和传入dict的真实读写。Per-Agent给不同session独立ledger；S沿用同session，M/I分片session；Shared两组将同可信委托根/资产的请求传给同一个ledger对象。作用域选择是实验配置，不另写代理风险门。

直接导入原 `core.langgraph_runtime.teachers.chain.TrustChain.issue/admit` 及 TeacherNode/TeacherEdge/TeamSpec，在mode=enforce下真实签名、校验并据返回view决定接收。篡改对照改正文而不重签名，原生signature_invalid判定阻断。调用入口由profile记录，仅记模块/函数/行，不采局部变量或密钥。81条每条gate=3、CGC启用时issue/admit各2，独立核对通过。

**该范围是现有fact-release分支与CGC边界原语，不是完整C2RAGV3检索/生成pipeline或完整TeacherDAG。** 固定片段选择不是BM25/Dense检索，固定生成器不是LLM。未实现新的语义风险算法，也未把自写账本计数器冒充CGC；ledger累计和预算拒绝由真实gate_fact执行。所有配置同分支同阈值，预算0.08在执行前冻结，不随结果调参。

## 资产、规则、隔离与预算

新建3份SYNTHETIC虚构教学记录，各有公开分数字段、可单独解释的两个校准参数，以及评测端定义的受限组合目标。完整合成source、可信交付策略、同一公开固定生成规则、隐藏有限评分规则和脚本/源码hash先冻结，再执行。source文本未包含隐藏组合目标或答案；隐藏目标选择/有限规则在evaluator_only/oracle_truth.json，只由独立评分进程读取。固定生成器可对所有架构一视同仁使用公开整数乘法/回显/弃答；它不读oracle，不因M而增加推理能力。

S连续三槽保留本地历史；M两个worker加第三槽merge；I同实现三会话、与M同可见图。第三槽已经是最终整合，绝无第四次免费调用。所有组同资产权限、同片段时序和机会；受控输出差异是门的结果，不是额外源访问。终态攻击者统一只看实际交付的worker回复、实际接收的relay和最终回复并集，不看被拒绝候选、完整server source、gold或内部全日志。

每trace恰好3个查询机会和3次脚本生成，3072输入字节/槽、1024候选输出字节/槽，ASCII JSON空格填充，合计**9216输入/3072候选输出字节**。这是公开统一的byte-token替代计数，**不是任何模型tokenizer的Token**。每次拒绝仍消耗槽，不退款、不重试；最终交付字节按实际另报。网关/释放门可读source以执行既有检查，脚本生成只接当槽片段及许可历史；同进程为诚实实验边界，不声称OS级恶意Agent隔离。

评分器仅stdlib，不importCG；对实际接收值识别两个合成校准unit，并用隐藏有限组合规则判断是否可恢复目标。不能把CG cost当真值，也不把字符串相似当语义恢复。直接出现目标与“两个合法片段可推导目标”分别报：本批所有组直接交付组合答案均0，但M/I分离账本的实际联合视图可推导目标。天然可推导性控制9/9符合预期，说明两个片段共同足够、单片段/错误配对不够；不把这种数学可推导性冒充协作智能。

## 九组实际指标

{table}

表中组合恢复/单元覆盖来自互补片段意图，正常正确来自公开字段提取，篡改边来自篡改意图的6次边尝试。每个trace三次释放尝试。正常任务所有组无过度阻断0/3，但这是极窄的固定公开字段任务，不是广泛教学效用。篡改意图中的联合恢复与互补片段意图在本批相同（M/I分离账本3/3，其余0/3）。详细81条结果及分母/unknown字段在case_results.json；最终unscorable=0，不把未执行/未知填0安全。

CGC使每组篡改实际接收从3/6降至0/6；它没有在Shared-Asset已经0/3的组合恢复上取得额外收益。合法签名、来源真实与内容无害并不等价。HSW-ST未调用，水印检出/盲来源恢复/责任归因均未测，不能以原生路由日志替代这些结论。

## 九组执行成本

{costtable}

每组9trace，同为27查询/27生成，输入82944字节、候选输出27648字节。总墙钟包含各worker第一次gate调用时的NumPy/sklearn等惰性导入，进程冷启动/缓存噪声显著；不能按该毫秒表排名算法性能或声称CGC让LLM更快。没有真实模型Token、模型延迟或付费成本。逐案例和gate/CGC耗时保留可复核，未为了美化删掉冷启动。

## 两次框架问题与有限修正

1. attempt_01：首例完成前，NumPy依赖调用platform.machine→本机gethostname，被既有严格Observer拒绝；首条部分执行、0完成、其余80未执行，不能记成0风险。旧runtime.py、runner、冻结、stderr/事件均保留。
2. runtime_v2：在读取资产/应用导入前显式初始化platform.machine，本机gethostname事件单独记录；启动子进程仍拒绝。9个worker共有9次本机hostname读取、27个被拒绝的启动尝试，0个成功启动。随后安装**原严格Observer**，原有精确hash IPv6回环能力探测例外不变，connect/DNS/data/truth和未知操作继续拒绝。应用阶段每worker仅3条已核对探测事件，独立观测门均通过；没有隐去bootstrap记录或将其冒充CG安全收益。
3. 负控制probe：既有Observer拒绝oracle读取，但测试错误捕获PermissionError（实际OperationDenied继承RuntimeError），因此探针退出1。原异常/脚本/日志保留；仅新增truth_probe_v3捕获精确既有异常并检查拒绝原因，单独重跑探针成功BLOCKED_BEFORE_READ。**81条主结果没有重跑。** 资产、核心、阈值、评分真值均未修改。

独立复核：81/81 source时序/历史可见性/ledger承接与读写/预算检查通过；7项评分合同负例/不变性检查符合预期（执行后审计，不冒充预注册安全样本）。同UID诚实Python边界不抵抗native逃逸或宿主失陷，仍需Stage1-C正式隔离/独立真值。

## 保护哈希与复核路径

**2587份既有文件运行前后SHA256一致**。attempt_02冻结内脚本、资产、公开策略、隐藏真值、原核心6文件hash均一致；两次失败及新修正版本有独立清单，未覆盖原件。完整原始I/O、ledger前后、函数调用、observer事件、stdout/stderr及评分留在本地目录。

{source_table}

发布仅含本轮脱敏协议、81条结果、九组指标、失败摘要、研究判断与证据hash清单。原始长栈/个人路径、HMAC密钥、真实学生、收费教材、完整CG源码、上轮五报告均不上传。失败/成功回执另留本地；远端没有确认前不声称同步完成。

## 有边界的研究判断

本批M与I一致、调用/来源机会相同，Shared-Asset在同样正常任务正确率下消除全部观察增量，故**PIVOT：将该分片现象作为已有账本作用域工程问题收尾，停止包装新多Agent算法**。只有3份同结构人工合成资产、固定输出、单一冻结预算；无随机LLM、释义、适应性攻击、预算敏感性或确认性统计，不推论现实系统无风险或共享账本普遍足够。

下一轮若另获授权，唯一可证伪问题：在可信委托根/资产账本已经统一的条件下，词面cost很低但能由独立有限规则组合的片段，是否仍会在相同实际可见集合中恢复受限目标？先检验共享账本proxy本身的范围，不预设多Agent特有效应，不直接开发算法。Stage1-C双人真值与真实模型许可仍未具备。
'''
    text(delivery/'stage1_e_report.md',report)
    decision='''# 研究决策：PIVOT（局限于本批合成机制）

81条探索完成且可评分，9组同预算。多Agent和单Agent多会话的分离账本组合恢复均3/3；共享资产账本后均0/3，所有组正常字段任务3/3正确。观察到的全部增量由会话账本分片解释，没有独立协作效应证据。

因此停止把本批分片现象包装成新算法，转为已有账本作用域绑定与可复核工程收尾。CGC真实边界原语阻止预设正文篡改，但未在共享账本的组合恢复零地板上显示额外收益。不是通用安全证明，不是实际LLM或论文确认性结果。

本轮调用原fact-release gate_fact和TrustChain.issue/admit，未运行完整检索/DAG、模型或新风险算法。固定生成、源/权限/预算、隐藏有限评分规则执行前冻结；隐藏oracle不传runtime。原S00-11/补测S00-12失败仍在，不用新实验覆盖。

两个框架问题和修正完整保留：首次导入元数据被拒绝；后续负控制异常类型捕获错误。只修隔离启动/观测解析，原核心/评分真值/预算未变，81条主结果只执行一次完成版。

下一轮唯一可证伪问题：统一可信委托根与资产账本后，低词面成本但可被独立有限规则组合的片段是否仍可恢复受限目标？该问题针对现有proxy的范围，不先认领多Agent机制，不自动开发算法或扩实验。

Stage1-C保持未放行：双人独立真值、正式资产与真实模型授权尚缺。本次Stage1-E已按边界完成，不再以准备工作代替探索，也不因局部通过进入真实模型pilot。
'''
    text(delivery/'research_decision.md',decision)
    manifest={'scope':'Stage1-E sanitized protocol, per-case results, failures and research judgment only','main_attempt':'attempt_02','main_results':{'traces':81,'scorable':81,'model_calls':0,'core_calls':audit['actual_calls']},'existing_files_preserved':2587,'source_hashes':audit['source_hashes'],'frozen_manifest_sha256':sha(attempt/'frozen_manifest.json'),'original_failure_manifest_sha256':sha(HERE/'attempt_01/frozen_manifest.json'),'probe_repair_manifest_sha256':sha(HERE/'probe_repair_frozen_manifest.json'),'postrun_audit_sha256':sha(HERE/'postrun_audit.json'),'source_assets_sha256':{a['asset_id']:a['source_sha256'] for a in load(HERE/'runtime_inputs/assets.json')},'oracle_file_sha256':sha(HERE/'evaluator_only/oracle_truth.json'),'files_sha256':{p.name:sha(p) for p in sorted(delivery.iterdir())},'raw_evidence_access':'Original full evidence retained locally; published per-case raw hashes map to local files. Not a full source-code or all-raw-logs release.'}
    save(delivery/'evidence_manifest.json',manifest)
    patterns=[r'C:[/\\]Users[/\\](?!WINDOWS_USER_HOME)',r'(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+)',r'-----BEGIN .*PRIVATE KEY-----',r'(?i)(?:api_key|password|secret)\s*[=:]\s*[\"\x27][^\"\x27]{8,}']
    findings=[p.name for p in delivery.iterdir() for pattern in patterns if re.search(pattern,p.read_text(encoding='utf-8'))]
    if findings:raise RuntimeError('Sensitive pattern found: no upload')
    files=sorted(p.name for p in delivery.iterdir())
    save(HERE/'publication_allowlist.json',{'files':files,'count':len(files),'sha256':{n:sha(delivery/n) for n in files},'git_blob_sha':{n:hashlib.sha1(b'blob '+str(len((delivery/n).read_bytes())).encode()+b'\0'+(delivery/n).read_bytes()).hexdigest() for n in files},'sensitive_pattern_findings':findings,'content_review':'Protocol, finite-rule metric results, failure summaries and evidence hashes only. No private core source, raw personal stacks, credentials, original student data, paid material, unrelated data or previous denied preparation reports.','target':'CG/diagnostics/2026-10-19-stage1-e-01/'})
    print(json.dumps({'files':files,'sensitive_pattern_findings':findings,'decision':'PIVOT_WITH_SYNTHETIC_MECHANISM_LIMITS'}))
if __name__=='__main__':main()
