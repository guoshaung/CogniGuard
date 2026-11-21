"""Publish only this sanitized experiment and append-only decision entry."""
from pathlib import Path
import json,hashlib,subprocess,re,sys
sys.stdout.reconfigure(encoding='utf8')
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
REPO=ROOT/'.tmp/c2rag-review-sync-20261019';BACK=ROOT/'.tmp/c2rag-remote-readback-20261019-01'
DEST='CG/experiments/2026-10-20-c2rag-r10-multiasset-01'
def git(where,*args):return subprocess.run(['git',*args],cwd=where,capture_output=True,check=True).stdout
def sha(b):return hashlib.sha256(b).hexdigest()
assert git(REPO,'remote','get-url','origin').decode().strip()=='https://github.com/guoshaung/research-sync.git'
assert not git(REPO,'status','--porcelain')
git(REPO,'pull','--ff-only','--quiet','origin','main');parent=git(REPO,'rev-parse','HEAD').decode().strip()
target=REPO/DEST;assert not target.exists()
for n,h in json.loads((P/'protocol.json').read_text(encoding='utf8'))['hashes'].items():assert sha((P/n).read_bytes())==h,n
for n,h in json.loads((P/'preservation_before.json').read_text(encoding='utf8')).items():assert sha((ROOT/n).read_bytes())==h,n
files=[]
for f in sorted(P.rglob('*')):
 if not f.is_file() or '__pycache__' in f.parts or 'local_sources' in f.parts:continue
 if f.name.endswith('_private.json') or f.name in ['manifest.json','sync_receipt.json']:continue
 rel=f.relative_to(P).as_posix();blob=f.read_bytes()
 if f.suffix in ['.py','.json','.md','.csv','.svg','.html']:
  assert not re.search(r'gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',blob.decode('utf-8-sig')),rel
 if f.suffix=='.py':compile(blob,str(f),'exec')
 dst=target/rel;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(blob)
 files.append({'path':rel,'bytes':len(blob),'sha256':sha(blob)})
manifest={'label':'EXPLORATORY_R10_PARTIAL_DATA_QUALITY_GATE','parent_commit':parent,'files':files,
 'candidate_assets':24,'source_verified':23,'controlled_contract_assets':17,'raw_text_end_to_end_scored_assets':0,
 'independent_human_annotators':0,'model_inference_calls':0,'paid_calls':0,'decision':'PIVOT',
 'excluded':'full source HTML, private paragraph capture, caches/models/credentials; private means local-only capture not restricted educational data',
 'hash_basis':'exact file/Git blob bytes; * -text attributes; separate authenticated checkout readback'}
blob=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf8')
(P/'manifest.json').write_bytes(blob);(target/'manifest.json').write_bytes(blob)
log=REPO/'CG/decision_log.md';old=log.read_bytes();assert b'c2rag-r10-multiasset-20261020-01' not in old
entry='''

<!-- c2rag-r10-multiasset-20261020-01 -->
## 2026-10-20：C²-RAG R10扩样门槛与强基线验证 — PIVOT

实际预建24候选（公式/单位/条件/过程各6），23来源核验；来源失败1、过程6缺可靠因果/时序标注，停止扩至40，不凑数。有效17为真实OpenStax规律支持的作者数值任务，不是教材原例题数字，更不是24份独立原文盲测。有效来源3本书、5个主要数学结构族，全部单一AI作者开发标注。

先冻结资产、背景、问题、候选、公开域、配额、攻击和代码，再运行A/B/C/D。34条作者规范化答案通用赋值前端34/34 PASS，四个旧前端均34/34 UNKNOWN；原文关系真值不可靠故不报原文F1，原文端到端有效分母0。5条件题均True分支，不能声称完整条件分支泛化。预算方法为本轮等机会成本适配器，未调用旧LCS/5gram代理门；非生产RAG运行。

17资产跨Agent互补：Raw/静态/共享加性/旧槽位恢复17/17、正常34/34，实际279回复Token；共享成熟闭包、同表示有限世界Conditional、简单共享带类型事实集合恢复0/17、正常17/34，135 Token。三者127/127计划回复Token IDs一致，类型集合已足够，未发现独立新算法收益。旧Conditional全UNKNOWN全拒答，0/17恢复伴随0/34效用，不能算风险识别成功。无内容/独立内容历史跨Agent恢复17/17；独立历史同身份阻断，说明共享范围作用。

重复与公共前提阴性计划三种内容方法均0完整恢复、34/34正常答对；单轮完整候选17份本来危险，均拒绝。单位转换有效8份；前提冲突17份全部UNKNOWN排除保护分母。离线220相关前缀为59危险、144不完整安全、17未知；共享闭包有值漏放0/59、误拦0/144，不把前缀数当资产数。220符号/有限世界及220作者标签检查、17独立Fraction/Boolean计算、1270预算检查通过；53旧JSON工件哈希不变。模型推理/检索/付费调用0。

结论PIVOT：共享内容历史有收益，成熟闭包在受控契约足够，且简单类型集合完全匹配；真实语言关系表示仍未验证，暂无支撑新C²算法的独立贡献。不扩40、不继续包装闭包创新；唯一下一步为独立标注、按来源族留出的原文到类型约束验证。

[报告](experiments/2026-10-20-c2rag-r10-multiasset-01/c2rag_r10_report.md)、[组会稿](experiments/2026-10-20-c2rag-r10-multiasset-01/group_meeting_c2rag_r10.md)、[失败](experiments/2026-10-20-c2rag-r10-multiasset-01/c2rag_r10_failure_cases.md)、[逐资产汇总](experiments/2026-10-20-c2rag-r10-multiasset-01/asset_method_summary.csv)、[哈希清单](experiments/2026-10-20-c2rag-r10-multiasset-01/manifest.json)。
'''
with log.open('ab') as f:f.write(entry.encode('utf8'))
git(REPO,'add','--',DEST,'CG/decision_log.md')
names=[n for n in git(REPO,'diff','--cached','--name-only','-z').decode().split('\0') if n]
assert all(n.startswith(DEST+'/') or n=='CG/decision_log.md' for n in names)
for f in files:assert sha(git(REPO,'show',':'+DEST+'/'+f['path']))==f['sha256'],f['path']
assert git(REPO,'show',':CG/decision_log.md').startswith(old)
git(REPO,'-c','user.name=Codex','-c','user.email=codex@localhost','commit','-m','Add exploratory C2-RAG R10 multiasset constraint baseline evidence and exclusions')
commit=git(REPO,'rev-parse','HEAD').decode().strip();git(REPO,'push','origin','HEAD:main')
assert not git(BACK,'status','--porcelain');git(BACK,'pull','--ff-only','--quiet','origin','main');git(BACK,'merge-base','--is-ancestor',commit,'HEAD')
for f in files:assert sha((BACK/DEST/f['path']).read_bytes())==f['sha256'],f['path']
assert sha((BACK/DEST/'manifest.json').read_bytes())==sha(blob)
remote=git(REPO,'ls-remote','origin','refs/heads/main').decode().split()[0]
receipt={'status':'REMOTE_AUTHENTICATED_SEPARATE_CHECKOUT_ALL_HASHES_PASS','commit':commit,'remote_head_at_check':remote,
 'payload_files_verified':len(files),'manifest_sha256':sha(blob),'only_new_subtree_and_append_only_log':True,
 'anonymous_public_readability':'not asserted','url':'https://github.com/guoshaung/research-sync/tree/'+commit+'/'+DEST}
(P/'sync_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
