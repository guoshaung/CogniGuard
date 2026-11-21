"""Package immutable sanitized evidence; no student records in public bundle."""
from pathlib import Path
import json,hashlib,platform,importlib.metadata as metadata,ast,re
P=Path(__file__).parent;ROOT=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,x):(P/n).write_text(x,encoding='utf8')
env={'python':platform.python_version(),'platform':platform.platform(),'versions':{k:metadata.version(k) for k in ['numpy','scikit-learn','torch','transformers','matplotlib']},'main_hash_seed':'20261013','hardware_scope':'single Windows host; CPU sklearn/selector/tokenizer, no model generation','LLM_calls':0,'paid_calls':0,'downloaded_models':0}
write('environment.json',json.dumps(env,indent=2))
code=json.loads((P/'code_paths.json').read_text(encoding='utf8'));parts=['# 代码改动与行号\n','仅增加本目录。生产三文件哈希与旧实验181文件哈希不变（validation.json）。原StrictSelector在前批证据中冻结，本轮继续作为旧逻辑适配对照。不是给旧源码开关改名：新编码、得分尺度、预算优化和Slot奖励均在独立新选择器实现。\n','## 实际函数起始行\n']
for row in code:
 parts.append(f"\n### {row['path']}\n\nSHA256: `{row['sha256']}`\n\n"+'\n'.join(f"- `{x['name']}`: L{x['line']}" for x in row['functions']))
parts.append('''

## 与旧实现的结构变化

- 旧OrthogonalDecoder以字段位置作向量坐标，任务词哈希作另一套坐标；替换为公共角色one-hot与同角色掩码。不是仅补齐维数。
- 旧softmax概率直接减隐私成本，压缩候选近空；修复采用max归一化相对权重，成本有界，仍保留共同硬敏感门。
- 旧TaskSlot可覆盖上游字段集合；实验版仅有界加分，全部最终选择受同一硬约束；删除它本批并无变化。
- 旧“bottleneck”名称含互信息暗示；新明确为带角色重复惩罚的预算子集优化，不作信息论声明。
- 旧基线完整画像先进入Attention再过滤，与其他方法入口不同；纠正两个基线后重算实际预测与属性攻击，修复方法未重调。
- C²原型只实现有限世界可识别性，没有生产集成。实际提醒泄露指数的反例保留，未修改提醒追求更优分数。

## 结果选择规则与工程错误

主表旧基线来自corrected_baselines，另外七方法来自mm_v2/new_families。C²主表来自visibility_audit，content原始结果仅保留语法内证据。首次开发缓存冲突、第一次入口审查种子未固定均保留。一次PowerShell内联脚本转义失败未执行实验，随后使用独立脚本。验证脚本初次在入口任务完成前读文件失败，完成后按实际纠正结果通过。未删除任何已冻结实验结果，未将无效运行当有效分母。

再运行必须新建目录，实验驱动会拒绝覆盖冻结输出。PYTHONHASHSEED须在启动Python前设为20261013。新任务旧基线的入口纠正属于已看过数据上的工程复核，不再称新盲测。
''')
write('code_change_summary.md','\n'.join(parts))
# Ensure generated prose does not silently point readers to obsolete main values.
write('RESULT_PRECEDENCE.md','''# 有效结果与保留原始结果的优先级

1. MM主表/消融使用mm_comparison.csv、mm_new_families.csv、mm_ablation.csv；Original与TaskSlot用corrected_baselines入口纠正版，其他7方法使用先前冻结结果。源JSON保留。
2. C²主比较使用visibility_audit/aggregate_main.json与content_comparison.csv。完整关系恢复Shared=1/3；content/aggregate_main.json的0/3是原受限解析器假阴性，不能作为语义安全结果。防御回复从未改动。
3. fairpool第一次入口审查缺少原Python哈希种子，run_validity标INVALID；fairpool_v2及corrected_baselines固定种子；主表采用真实重新拟合结果。
4. 主运行的混合缓存耗时不可比较，采用latency.csv开发选择器测量；其旧适配入口早于纠正，精确同池性能只对Full/Safe及修复消融成立。不是端到端LLM延迟。
5. 两模块全部EXPLORATORY。两科UCI为旧开发复核，新合成任务是作者设计的heldout组合，C²只有3个旧开发资产；不称独立人类盲测。
''')
write('.gitattributes','* -text\n')
oldsync=(ROOT/'experiments/final_key_evidence_20261019_01/sync_public.py').read_text(encoding='utf8');new=oldsync.replace('2026-10-19-final-key-evidence-01','2026-10-19-aligned-content-01').replace('Add C2 relation reconstruction dev diagnostics and MM causal trace audit','Add aligned MM repair ablations and visible-content risk failure audit')
write('sync_public.py',new)
files=[]
for path in sorted(P.rglob('*')):
 if not path.is_file() or '__pycache__' in path.parts or path.name in ['evidence_manifest.json','sync_receipt.json']:continue
 rel=path.relative_to(P).as_posix();local=path.name.endswith('_LOCAL.json')
 if not local and path.suffix in ['.json','.md','.py','.csv','.txt']:
  text=path.read_text(encoding='utf-8-sig')
  if re.search(r'gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',text):raise RuntimeError('credential literal '+rel)
 files.append({'path':rel,'bytes':path.stat().st_size,'sha256':sha(path),'local_only':local})
manifest={'status':'FROZEN_PACKAGE_AFTER_VALIDATION','classification':'EXPLORATORY','MM_decision':'PIVOT','C2_decision':'ANALYZE','public_policy':'only aggregate real-student results, all fictional authored data/visible content safe to share; no actual UCI row or per-student trace exported','primary_results':{'MM':'mm_comparison.csv + corrected_baselines + seven frozen methods','C2':'visibility_audit/aggregate_main.json; fallback-aware Shared1/3, NOT original grammar0/3'},'files':files,'local_only_files':sum(x['local_only'] for x in files),'public_files':sum(not x['local_only'] for x in files)}
write('evidence_manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2));print(json.dumps({'files':len(files),'public':manifest['public_files'],'local_only':manifest['local_only_files']},indent=2))
