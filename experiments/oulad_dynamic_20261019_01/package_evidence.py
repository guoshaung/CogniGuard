"""Generate sanitized manifest, provenance and scoped research-sync helper."""
from pathlib import Path
import json,hashlib,platform,importlib.metadata as metadata,re
P=Path(__file__).parent;ROOT=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,s):(P/n).write_text(s,encoding='utf8')
validation=json.loads((P/'validation.json').read_text(encoding='utf8'));assert validation['core_unchanged'] and validation['source_versions_unchanged_since_freeze']
write('environment.json',json.dumps({'python':platform.python_version(),'platform':platform.platform(),'libraries':{k:metadata.version(k) for k in ['numpy','pandas','scikit-learn','torch','transformers','matplotlib']},'LLM_calls':0,'paid_API_calls':0,'large_model_downloads':0,'data_download_bytes':46750706,'primary_hash_seed':'20261013','scope':'same Windows host; CPU sklearn/tokenizer, no generative inference'},indent=2))
code=json.loads((P/'code_paths.json').read_text(encoding='utf8'));lines=['# 函数、真实行号与源版本\n','完整机制与公平性说明在mechanism_and_code.md；这里只列实际路径和函数，不能凭开关名声称有效。生产源未修改。\n']
for row in code:lines.append('\n## '+row['file']+'\n\nSHA256: `'+row['sha256']+'`\n\n'+'\n'.join('- `'+x['name']+'`: L'+str(x['line']) for x in row['functions']))
write('code_paths.md','\n'.join(lines))
write('RESULT_PRECEDENCE.md','''# 有效证据优先级与分母

主比较comparison.csv /comparison_derived.json；主60格/期来自*_results/summary，严格配对在strict_ablation。10方法保持同候选/接口/预算/训练/攻击规格。独立保留协议在independent_protocol。

RelevanceCostRule为开发后、保留结果完成前冻结的解释性普通贪心对照；rule_dev/test核验其无约束最优字段与Full相同、所有训练评估样本满足真实Token限额，并逐条匹配全部真实评估payload。rule_equivalent_metrics只是复用已证同视图的同一确定性拟合指标，不声称增加模型运行。

stage_privacy重建同240个保留攻击拟合，主BA/AUC逐项精确一致，再拆分阶段/简单学生概率平均；不是240个新独立样本。public_context_attack是事后背景校准，0私密字段，不作为K3方法竞争。

audit_target_timing在主试验后核查，保留3/462目标已提前提交；仅列既有模型的全部条件子集敏感性，不更换测试/模型/主数值。成绩公布时间仍缺，7天lag非严格可用性证明。

必要信息Recall仅作者公开任务契约/已可用契约，不是独立教师因果真值；真正必要性和实际教学干预收益未确认。学生组数train484/dev166/test167，snapshot分别1337/473/462，六表述重复相同学生/时点，禁止按请求数夸大独立人数。

所有*_LOCAL.json含本地真实学生ID/值/预测/payload或分组，不同步。公共文件只有聚合结果、无学生值的元数据trace模板、代码、协议、图表、哈希。原始OULAD archive留在.cache，不打包。
''')
write('.gitattributes','* -text\n')
template=(ROOT/'experiments/final_key_evidence_20261019_01/sync_public.py').read_text(encoding='utf8').replace('2026-10-19-final-key-evidence-01','2026-10-19-oulad-dynamic-01').replace('Add C2 relation reconstruction dev diagnostics and MM causal trace audit','Add OULAD forward-heldout MM-FOPD verification and component simplification evidence');write('sync_public.py',template)
files=[]
for path in sorted(P.rglob('*')):
 if not path.is_file() or '__pycache__' in path.parts or path.name in ['evidence_manifest.json','sync_receipt.json']:continue
 rel=path.relative_to(P).as_posix();local=path.name.endswith('_LOCAL.json')
 if not local and path.suffix in ['.json','.md','.py','.csv','.txt']:
  text=path.read_text(encoding='utf-8-sig')
  if re.search(r'gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',text):raise RuntimeError('credential literal '+rel)
 files.append({'path':rel,'bytes':path.stat().st_size,'sha256':sha(path),'local_only':local})
manifest={'status':'FROZEN_AFTER_VALIDATION_AND_REPORT_QA','classification':'EXPLORATORY_OULAD_REAL_RECORDS','decision':'PIVOT','source_data_attribution':'Kuzilek, Hlosta & Zdrahal2017; doi10.1038/sdata.2017.171; author dataset doi10.6084/m9.figshare.5081998.v1; CC BY4.0; modified temporal features/labels/groups/aggregates; raw archive not distributed','privacy_policy':'student-level data and original identifiers/payloads excluded; no raw OULAD export','validation':{'prior_files_unchanged':validation['previous_evidence_files_unchanged'],'actual_eval_payloads_token_checked':validation['actual_eval_payloads_token_checked']},'public_files':sum(not x['local_only'] for x in files),'local_only_files':sum(x['local_only'] for x in files),'files':files}
write('evidence_manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2));print(json.dumps({'public_files':manifest['public_files'],'local_only_files':manifest['local_only_files'],'public_bytes':sum(x['bytes'] for x in files if not x['local_only'])},indent=2))
