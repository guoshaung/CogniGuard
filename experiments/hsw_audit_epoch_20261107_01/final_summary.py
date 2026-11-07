"""Read-only final accounting after scored snapshot; no generation or scoring.

The analysis round and all pre-score quality locks remain immutable. This is an
additional report, not a replacement for earlier partial checkpoint reports.
"""
import argparse,csv,datetime,json
from collections import Counter,defaultdict
from pathlib import Path
from bootstrap import E,R,save,digest

ap=argparse.ArgumentParser();ap.add_argument('--round',required=True);a=ap.parse_args()
D=R/('analysis_'+a.round);V=R/('delivery_'+a.round)
assert (D/'EVALUATION_RECEIPT.json').exists() and V.is_dir()
tasks=json.loads((R/'TASKS_FROZEN.json').read_text(encoding='utf-8'))
ledger=[json.loads(x) for x in (R/'RUN_MANIFEST.jsonl').read_text(encoding='utf-8').splitlines()]
starts=[x for x in ledger if x['event']=='STARTED'];assert len({x['task_id'] for x in starts})==len(starts)
locks={}
for p in (R/'reviews').glob('*QUALITY_LOCK*.json'):
 for row in json.loads(p.read_text(encoding='utf-8')).get('rows',[]):
  assert row['task_id'] not in locks,'Duplicate quality decision, not another independent reviewer'
  locks[row['task_id']]=row
frozen=json.loads((R/'GENERATION_CODE_FREEZE.json').read_text(encoding='utf-8'))
for rel,expected in frozen['code'].items():assert digest(E/rel)==expected
assert digest(R/'freeze.json')==frozen['input_freeze_sha256']
rows=[]
for task in tasks:
 tid=task['task_id'];p=R/'raw'/tid/'result.json'
 row={'task_id':tid,'stage':task['stage'],'arm':task['method'],'source_id':task['source_id'],
      'planned':True,'started':tid in {x['task_id'] for x in starts},'public_snapshot':p.exists()}
 if p.exists():
  raw=json.loads(p.read_text(encoding='utf-8'));q=locks[tid]
  assert digest(p.parent/'public.txt')==q['public_sha256']==raw['public_sha256']
  row.update(EOS=raw['natural_EOS'],finish_reason=raw['finish_reason'],quality=q['overall'],facts=q['facts'],coverage=q['coverage'],
    generated_tokens=raw['generated_tokens'],wall_seconds=raw['wall_seconds'],A=raw['A_bytes'],B=raw['B_ids_equal'])
 elif (p.parent/'FAILURE.json').exists():row.update(EOS=False,finish_reason='TECH_FAIL',quality='NOT_ASSESSED_TECH_FAIL')
 else:row.update(EOS=False,finish_reason='NOT_RUN' if not row['started'] else 'INCOMPLETE',quality='NOT_ASSESSED')
 rows.append(row)

def write_csv(path,items):
 fields=list(dict.fromkeys(k for item in items for k in item))
 with path.open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(items)

groups=defaultdict(list)
for r in rows:groups[(r['stage'],r['arm'])].append(r)
summary=[]
for key,rs in sorted(groups.items()):
 summary.append({'stage':key[0],'arm':key[1],'planned':len(rs),'started':sum(x['started'] for x in rs),
  'public_snapshots':sum(x['public_snapshot'] for x in rs),'natural_EOS':sum(x['EOS'] for x in rs),
  **{'quality_'+v:sum(x['quality']==v for x in rs) for v in ['PASS','FAIL','UNKNOWN']},
  'not_assessed':sum(x['quality'].startswith('NOT_ASSESSED') for x in rs),
  'B_history_mismatch':sum(x.get('B') is False for x in rs)})
write_csv(V/'MAIN_ATTEMPT_ACCOUNTING.csv',rows);write_csv(V/'QUALITY_BY_STAGE_ARM.csv',summary)
stages=[x for x in ledger if x['event']=='STAGE_EXIT']
actual=[x for x in rows if x['public_snapshot']];noncal=[x for x in actual if x['stage']!='CAL']
spent=sum(x['wall_seconds'] for x in stages)
resource={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'formal_answer_attempts':len(starts),
 'main_planned_slots':len(tasks),'main_started':sum(x['started'] for x in rows),'main_public_snapshots':len(actual),
 'main_EOS':sum(x['EOS'] for x in actual),'planned_issuance_slots_excluding_CAL':sum(t['issue_id'] is not None for t in tasks),
 'observed_issuance_snapshots':len(noncal),'CAL_rewrites':sum(x['stage']=='CAL' for x in actual),
 'quality':dict(Counter(x['quality'] for x in actual)),'model_stage_wall_seconds':spent,
 'generated_tokens_all_ledger':sum(x.get('tokens',0) for x in ledger if x['event'] in {'DELIVERED','TECH_FAIL'}),
 'GPU_calls':0,'paid_API_calls':0,'new_model_downloads':0,'original_hard_model_seconds':7200,
 'active_stage_processes_must_be_closed_before_final_sync':True,'final_generator_freeze_verified':True,
 'calibration_independent_chapters':2,'unknown_independent_TEST_sources':0,'FPR_1percent_certified':False}
save(V/'RESOURCE_FINAL.json',resource)
table='\n'.join('|'+ '|'.join(str(s[k]) for k in ['stage','arm','planned','started','natural_EOS','quality_PASS','quality_FAIL','quality_UNKNOWN','not_assessed'])+'|' for s in summary)
save(V/'FINAL_RESULT.md',f'''# HSW-AUDIT-EPOCH-01：执行与证据边界

工程：PARTIAL。研究：INSUFFICIENT_EVIDENCE。这是有结果的现有方法适配实验，不是只完成文献审计，也没有证明新算法必要性。

## 原计划全分母

{len(tasks)}个原计划槽中已启动{resource['main_started']}，公开快照{len(actual)}，自然EOS {resource['main_EOS']}。预登记发行槽87，另有2个未登记CAL改写；接收方、周期、片段都不是独立来源。真实作者正文来自一本书的8个章节，DEV2/CAL2/TEST4；质量为当前助手作者PROVISIONAL，非独立真人金标。

|阶段|生成臂|计划|启动|自然EOS|知识PASS|FAIL|UNKNOWN|未审核/未运行|
|---|---|---:|---:|---:|---:|---:|---:|---:|
{table}

## 可以成立的工程能力

1. 新交付由可信原文一次性产生，保留来源、发行方、接收方代号、交付号、内容版本、密钥周期与parent关系的分离登记。它不是在M1上重水印。
2. 同一受信版本库同时提供给精确哈希、MinHash、英文MiniLM语义指纹及混合检索；水印扫描全部保留的密钥和周期，不偷看查询真值。精确字节相同且登记身份不同，必须歧义；登记与签名无法创造文本中不存在的身份信息。
3. 换钥停止旧钥新发行，不删除旧检测材料；许可撤销不改变旧版本身份。签名验证只证明定义协议下的记录/正文关联，不证明实际法律权属、真实发行时间或最终泄露人。

## 效果解释

完整、裁剪与格式变换的逐例表见analysis目录ATTRIBUTION_RESULTS.csv及PRIMARY_SUMMARY.csv。主1%工作点未认证：仅2个独立CAL章节，预冻结秩3超过样本2，故主阈值∞并拒识。拒识不是防御成功。另列有限CAL和名义Bonferroni诊断，不能将其包装成匹配1%FPR的方法胜负。

B2是TextSeal工具包Greenlist，不是TextSeal双密钥；B3是真实MPAC 32bit公开多比特解码适配。不能把B3优化颜色后的高统计量当成正确发行码。当前结果不排除更短消息、其他编码、PRMB或失真优化方法的能力。

本轮语义指纹实际使用已有的英文all-MiniLM-L6-v2，并未运行更强的英文BGE；不把中文BGE硬用于英文，也不据此宣称最强内容指纹已经获胜。具体实现在METHOD_AUDIT.md固定。主生成是7B Q4 CPU、temperature=.8/top-p=.95，而非旧HSW的云FP32 greedy/SHA256-PCG64 delta4配置，不能跨轮归因。

生命周期保留与唯一检测必须分开：即使旧记录与检测材料都还在，同字节多身份、短片段或解码拒识仍会使旧版本不能唯一关联。签名正确不等于一个修改后的查询正文也获得签名完整性认证。

同字节身份冲突的附加保守解释字段是在观察到S05输出碰撞之后、最终TEST公开评分分析之前实现。它贯彻相同副本不能强选身份的原始约束，但不是独立事前注册的新机制收益；原始分数/归因与派生safe状态并列保留，不因此提高方法成功数。

## 保真与失败

全部知识FAIL/UNKNOWN保留原文引句，见ERROR_CASES.md与质量锁。独立测量/相同条件、变量R_E定义、刚性腔体等覆盖遗漏与明确事实错误分开；倒数加“times smaller”保留UNKNOWN而不猜作者意图。普通改写也可能有这些问题，不能凭单次成对差异归因水印。技术中断/截断不重跑，也不伪装成已观察知识错误。

## 成本与下一步边界

账本累计模型阶段{spent:.3f}秒；实际Token、EOS、CPU速度、RSS及独立语义编码/公开检测成本分别保留，不能拿原始生成Token/s当合格交付吞吐。API/GPU调用均0，未新增模型和付费资源。保持7B；3B如仅准备而未生成，不算有效跨模型攻击证据。没有有效强改写时不声称强攻击鲁棒性。

当前可集成登记、历史密钥保留和明确拒识的审计能力；是否有可重复的归因—保真—成本缺口仍证据不足。不能据此开发新算法。下一项唯一研究问题是：在充分独立背景校准并保证真实交付完整保真的条件下，水印对完整版本指纹索引是否有增量价值。
''')
print(json.dumps({'status':'FINAL_ACCOUNTING_WRITTEN','actual':len(actual),'main_started':resource['main_started'],'main_EOS':resource['main_EOS']}))
