"""Publish only the sanitized R9 subtree; verify via separate authenticated clone."""
from pathlib import Path
import hashlib,json,re,subprocess,sys
sys.stdout.reconfigure(encoding='utf8')
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
REPO=ROOT/'.tmp/c2rag-review-sync-20261019'
READBACK=ROOT/'.tmp/c2rag-remote-readback-20261019-01'
DEST='CG/experiments/2026-10-19-c2rag-r9-real-text-01'
def git(repo,*args):return subprocess.run(['git',*args],cwd=repo,capture_output=True,check=True).stdout
def sha(b):return hashlib.sha256(b).hexdigest()
assert git(REPO,'remote','get-url','origin').decode().strip()=='https://github.com/guoshaung/research-sync.git'
assert not git(REPO,'status','--porcelain')
git(REPO,'pull','--ff-only','--quiet','origin','main')
parent=git(REPO,'rev-parse','HEAD').decode().strip()
target=REPO/DEST
assert not target.exists(),'new destination required'
for f,h in json.loads((P/'protocol.json').read_text(encoding='utf8'))['hashes'].items():
    assert sha((P/f).read_bytes())==h,'frozen method/input drift: '+f
for f,h in json.loads((P/'preservation_before.json').read_text(encoding='utf8')).items():
    assert sha((ROOT/f).read_bytes())==h,'old artifact drift: '+f
files=[]
for f in sorted(P.rglob('*')):
    if not f.is_file() or '__pycache__' in f.parts:continue
    if f.name in ['manifest.json','sync_receipt.json']:continue
    assert not f.name.endswith('_LOCAL.json')
    rel=f.relative_to(P).as_posix();data=f.read_bytes()
    if f.suffix in ['.py','.json','.md','.csv','.svg']:
        assert not re.search(r'gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',data.decode('utf-8-sig')),rel
    if f.suffix=='.py':compile(data,str(f),'exec')
    dst=target/rel;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
    files.append({'path':rel,'sha256':sha(data),'bytes':len(data)})
manifest={'status':'SANITIZED_EXPLORATORY_R9','parent_commit':parent,'files':files,
          'hash_basis':'exact file/Git blob bytes; subtree .gitattributes disables newline conversion',
          'source_pages':4,'knowledge_assets':4,'blind_test_assets':0,'model_calls':0,'paid_api_calls':0,
          'annotation':'single AI research-author development labels, no independent human raters',
          'remote_readback':'separate authenticated Git checkout; no anonymous-public-readability claim',
          'excluded':'raw full HTML, model files, caches, credentials, real individual records',
          'failure_records':['operational_failures.json','c2rag_r9_failure_cases.md','e1_raw_results.json','e2_raw_results.json']}
blob=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf8')
(P/'manifest.json').write_bytes(blob);(target/'manifest.json').write_bytes(blob)
log=REPO/'CG/decision_log.md'
entry='''

<!-- c2rag-r9-real-text-20261019-01 -->
## 2026-10-19：C²-RAG R9真实来源文本实测 — PIVOT

实际完成E1→通过门槛的E2/E3：2本OpenStax教材、4来源页、4已准备资产、2来源关联族；不是新增盲测，也未把旧合成资产/重复查询算成新样本。核对6个原始HTML快照及许可；公开文本仅施加作者模拟授权，不声称真实禁止正常引用/教学使用。标注由单一AI研究作者编制，无独立人工真值或一致率。

E1共20文本单元（12原始句段+8来源子片段，来源有重叠），有界类型前端17PASS/2FAIL/1UNKNOWN，精确原子P=1、R=32/37、F1=64/69。只看原始12单元为9PASS/2FAIL/1UNKNOWN，F1=48/53。旧槽位和R8当前Conditional前端均20/20UNKNOWN；旧关系规则丢失冷态电阻单位/工况，2FAIL/18UNKNOWN。成熟指后端，不把本轮作者有限规则叫通用提取器。过程目标、瞬态共变、公式指代失败保留；无可靠因果重构结果。

E2仅在每资产2/2实际数值/单位候选通过后执行。20计划×8方法=160方法回合，资产分母仍4。跨Agent主比较原始/静态/加性/旧槽位恢复4/4、正常8/8；共享精确闭包恢复0/4、正常4/8；独立内容历史跨Agent恢复3/4、正常7/8。欧姆例query电流+单电压即确定R，不归于互补协同；只有其余3例是组合风险。重复事实强闭包正常8/8、恢复0/4。单位/前提变化中热冷公式指代计划8方法全部UNSUPPORTED、恢复空值，不当作8次攻击失败。

当前Conditional前端对主场景8/8候选UNKNOWN、全拒答、正常0/8；零恢复不是语义成功。同合同Conditional诊断共用强闭包后端，20/20输出/Token IDs相同，只是构造性接口核验，不是新算法竞赛。

E3四策略×四危险复合问题=16行：原完整答复答对4/4且恢复4/4；拒答、固定提醒、局部替代恢复均0/4，完整答对均0/4。局部保留54.2%题目事实，主要为公共/已见事实，新要求私有目标事实增量0；不能包装成教学效用完全保持。平均回复Token完整22.75、拒答0、固定10、局部20.25，实际长度未匹配。提醒确有相关检查步骤但不算答对；无意义指标仅作者规则代理。

168次独立SymPy求解后端核验与160回合资源检查通过，前端仍共用，非独立语义裁决；11个旧文件/源快照哈希未改。没有检索/生成运行，模型推理/付费调用/大模型下载均0。冻结后未改规则/问题找优势，UNKNOWN和操作失败保留。

决策PIVOT：当前数值契约收益由成熟闭包解释，新算法候选0。唯一下一步是独立人工核验单位、工况、否定与指代/过程契约，并在任何规则修补前冻结新的来源分组评估。

[完整报告](experiments/2026-10-19-c2rag-r9-real-text-01/c2rag_r9_real_text_report.md)、[组会稿](experiments/2026-10-19-c2rag-r9-real-text-01/group_meeting_c2rag_r9.md)、[失败记录](experiments/2026-10-19-c2rag-r9-real-text-01/c2rag_r9_failure_cases.md)、[提取CSV](experiments/2026-10-19-c2rag-r9-real-text-01/c2rag_r9_relation_extraction.csv)、[重构CSV](experiments/2026-10-19-c2rag-r9-real-text-01/c2rag_r9_multiagent_reconstruction.csv)、[效用CSV](experiments/2026-10-19-c2rag-r9-real-text-01/c2rag_r9_safety_utility.csv)、[哈希清单](experiments/2026-10-19-c2rag-r9-real-text-01/manifest.json)。
'''
assert b'c2rag-r9-real-text-20261019-01' not in log.read_bytes()
with log.open('ab') as f:f.write(entry.encode('utf8'))
git(REPO,'add','--',DEST,'CG/decision_log.md')
names=[n for n in git(REPO,'diff','--cached','--name-only','-z').decode().split('\0') if n]
assert all(n.startswith(DEST+'/') or n=='CG/decision_log.md' for n in names)
for f in files:assert sha(git(REPO,'show',':'+DEST+'/'+f['path']))==f['sha256'],f['path']
assert git(REPO,'show',':CG/decision_log.md').startswith(git(REPO,'show','HEAD:CG/decision_log.md'))
git(REPO,'-c','user.name=Codex','-c','user.email=codex@localhost','commit','-m',
    'Add C2-RAG R9 real-source extraction, multi-agent closure and safety-utility pilot')
commit=git(REPO,'rev-parse','HEAD').decode().strip()
git(REPO,'push','origin','HEAD:main')
assert not git(READBACK,'status','--porcelain')
git(READBACK,'pull','--ff-only','--quiet','origin','main')
git(READBACK,'merge-base','--is-ancestor',commit,'HEAD')
for f in files:assert sha((READBACK/DEST/f['path']).read_bytes())==f['sha256'],f['path']
assert sha((READBACK/DEST/'manifest.json').read_bytes())==sha(blob)
changed=[n for n in git(REPO,'diff','--name-only','-z',parent,commit).decode().split('\0') if n]
assert all(n.startswith(DEST+'/') or n=='CG/decision_log.md' for n in changed)
receipt={'status':'REMOTE_SEPARATE_AUTHENTICATED_CHECKOUT_ALL_HASHES_PASS','commit':commit,
         'payload_files_verified':len(files),'manifest_verified':True,'old_results_changed':False,
         'decision_log_append_only':True,'url':'https://github.com/guoshaung/research-sync/tree/'+commit+'/'+DEST}
(P/'sync_receipt.json').write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps(receipt,ensure_ascii=False))
