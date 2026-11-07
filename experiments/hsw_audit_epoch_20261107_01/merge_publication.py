"""Merge only this study's new safe checkpoint into its existing evidence branch.

Does not commit or push. Original raw/quality/analysis bytes are immutable. Old
top-level checkpoint reports/receipt stay archived and in the earlier Git commit.
"""
import argparse,json,re,shutil
from pathlib import Path
from bootstrap import R,save,digest
from secrets_store import read

ap=argparse.ArgumentParser();ap.add_argument('--staging',required=True);ap.add_argument('--round',required=True);a=ap.parse_args()
S=Path('D:/pycharm/research-sync-worktrees/hsw-audit-epoch-20261107-01')
dest=S/'CG/experiments/2026-11-07-hsw-audit-epoch-01';src=Path(a.staging).resolve()
assert src.is_relative_to(S.resolve()) and src!=dest.resolve()
assert (src/'SHA256_MANIFEST.json').is_file() and (dest/'SHA256_MANIFEST.json').is_file()
old_manifest=json.loads((dest/'SHA256_MANIFEST.json').read_text(encoding='utf-8'))
archive=dest/'history'/'checkpoint_round01_root_reports'
if not archive.exists():
 archive.mkdir(parents=True)
 for p in dest.iterdir():
  if p.is_file() and p.name not in {'.gitattributes'}:shutil.copyfile(p,archive/p.name)
report=src/'FINAL_RESULT.md';assert report.is_file()
# This first-write staging report now becomes the latest public RESULT; retain
# the mechanically produced earlier report in its own visible history folder.
raw_reports=src/'history'/('delivery_'+a.round+'_initial_reports');raw_reports.mkdir(parents=True)
for name in ['RESULT.md','README.md','FINAL_DECISION.md']:
 if (src/name).exists():shutil.copyfile(src/name,raw_reports/name)
(src/'RESULT.md').write_text(report.read_text(encoding='utf-8')+'\n\n'+(src/'METHOD_RESULTS.md').read_text(encoding='utf-8'),encoding='utf-8')
res=json.loads((src/'RESOURCE_FINAL.json').read_text(encoding='utf-8'))
(src/'README.md').write_text(f'''# HSW-AUDIT-EPOCH-01

工程PARTIAL；研究INSUFFICIENT_EVIDENCE。此次有界执行已归档，不自动扩量或开发新算法。
最新公开结果：RESULT.md；逐例RESULTS.csv；对照PRIMARY_SUMMARY.csv位于data/analysis_{a.round}/。
实际主槽启动{res['main_started']}/{res['main_planned_slots']}；正文快照{res['main_public_snapshots']}，自然EOS {res['main_EOS']}。
此前round01、round02及失败保留；当前仅一本教材的章节级探索，非总体误报或独立人工金标。
公开可验证签名、正文SHA与MinHash；真实水印分数重算需受控历史检测材料，实际密钥和生成seed未上传。
''',encoding='utf-8')
(src/'FINAL_DECISION.md').write_text('''# 最终边界

工程：PARTIAL。研究：INSUFFICIENT_EVIDENCE。
现有登记、历史周期保留与显式拒识具有集成价值；不是已证明的新水印算法。
具体交付关联依赖受信候选登记和历史材料；相同文本的多个身份不能被无中生有区分。
主1%整体错误接受目标未认证，名义Bonferroni与有限CAL均单列诊断。拒识不能计为防御成功。
公开逐密钥Greenlist和真实MPAC多比特适配均运行；不能拿优化颜色高统计量替代完整发行码恢复。
普通改写也存在条件遗漏与歧义，不能据本轮作者PROVISIONAL判断宣称水印普遍导致知识损坏。
下一步唯一问题：在充分独立背景校准且交付完整保真的条件下，水印是否给完整版本指纹索引带来增量价值。
不自动恢复旧路线、不自动开发算法；详见RESULT.md、ERROR_CASES.md、ATTACK_STATUS.md及全部原始表。
''',encoding='utf-8')
if (src/'FINAL_DECISION_FINAL.md').exists():shutil.copyfile(src/'FINAL_DECISION_FINAL.md',src/'FINAL_DECISION.md')
if (src/'REPRODUCE_FINAL.md').exists():
 shutil.copyfile(src/'REPRODUCE.md',raw_reports/'REPRODUCE.md')
 shutil.copyfile(src/'REPRODUCE_FINAL.md',src/'REPRODUCE.md')
changes=[]
for p in src.rglob('*'):
 if not p.is_file() or p.name in {'SHA256_MANIFEST.json','SYNC_RECEIPT.json'}:continue
 rel=p.relative_to(src);out=dest/rel
 if out.exists() and digest(out)!=digest(p):
  assert rel.parts[0] not in {'data','sources_and_licenses','readonly_dependency_sources'},'Frozen public evidence changed: '+str(rel)
  changes.append(rel.as_posix())
 out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out)

def leaves(x):
 if isinstance(x,dict):return [v for y in x.values() for v in leaves(y)]
 if isinstance(x,list):return [v for y in x for v in leaves(y)]
 return [str(x)]

values=leaves(read(R/'private/RUN_SECRETS.dpapi'))+leaves(read(R/'private/ISSUER_SIGNING.dpapi'))+leaves(read(R/'private/NULL_DETECTOR_KEYS.dpapi'))
bad=[]
for p in dest.rglob('*'):
 if not p.is_file():continue
 assert p.suffix.lower() not in {'.dpapi','.dat','.dll','.gguf','.safetensors','.pdf','.env','.sqlite3'}
 text=p.read_text(encoding='utf-8-sig')
 if re.search(r'\bsk-[A-Za-z0-9_-]{20,}',text):bad.append(p.relative_to(dest).as_posix())
 if any(len(v)>=7 and re.search(r'(?<![A-Za-z0-9])'+re.escape(v)+r'(?![A-Za-z0-9])',text) for v in values):bad.append(p.relative_to(dest).as_posix())
assert not bad,'SECRET_SCAN_FAILED filenames only: '+json.dumps(sorted(set(bad)))
manifest={p.relative_to(dest).as_posix():digest(p) for p in dest.rglob('*') if p.is_file() and p.relative_to(dest).as_posix() not in {'SHA256_MANIFEST.json','SYNC_RECEIPT.json'}}
# Archived manifests are regular input files; exclude only the current root
# manifest, whose own digest would create a cycle.
(dest/'SHA256_MANIFEST.json').write_text(json.dumps({'self_excluded':True,'root_sync_receipt_excluded':True,'files':manifest},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save(R/('PUBLICATION_MERGE_'+a.round+'.json'),{'status':'PASS','payload_files':len(manifest),'changed_latest_reports_or_code':changes,
 'old_data_bytes_verified_unchanged':True,'secret_scan':'PASS','staging':str(src),'no_commit_or_push_by_this_helper':True})
print(json.dumps({'status':'SAFE_MERGE_PREPARED','files':len(manifest),'changed_latest_files':len(changes)}))
