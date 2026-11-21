"""Publish only this new sanitized experiment; fail before committing bad hashes."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,urllib.parse,urllib.request,urllib.error

P=Path(__file__).resolve().parent
ROOT=P.parents[1]
REPO=ROOT/'.tmp/c2rag-review-sync-20261019'
DEST='CG/experiments/2026-10-19-c2rag-relation-closure-01'
def git(*args):
    r=subprocess.run(['git',*args],cwd=REPO,capture_output=True,check=True)
    return r.stdout
def sha(b):return hashlib.sha256(b).hexdigest()

assert git('remote','get-url','origin').decode().strip()=='https://github.com/guoshaung/research-sync.git'
pending=(git('diff','--name-only','-z')+git('diff','--cached','--name-only','-z')).decode().split('\0')
assert all(not n or n.startswith(DEST+'/') or n=='CG/decision_log.md' for n in pending)
assert not git('ls-tree','HEAD',DEST), 'destination already committed; refuse replacement'
git('pull','--ff-only','--quiet','origin','main')
parent=git('rev-parse','HEAD').decode().strip()
target=REPO/DEST
target.mkdir(parents=True,exist_ok=True)  # resume only own unpublished staged subtree
files=[]
for f in sorted(P.rglob('*')):
    if not f.is_file() or '__pycache__' in f.parts or 'local_source_snapshots' in f.parts:continue
    if f.name in ['manifest.json','sync_receipt.json','sync_attempts.jsonl']:continue
    rel=f.relative_to(P).as_posix();data=f.read_bytes()
    if f.suffix.lower() in ['.py','.json','.md','.csv','.svg']:
        text=data.decode('utf-8-sig')
        assert not re.search(r'gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',text),rel
    assert not f.name.endswith('_LOCAL.json')
    dst=target/rel;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
    files.append({'path':rel,'sha256':sha(data),'bytes':len(data)})
manifest={'status':'SANITIZED_EXPLORATORY_PUBLISH','date_beijing':'2026-10-19',
    'source_parent_commit':parent,'main_attempt':'02','retained_attempt':'01',
    'independent_performance_assets':1,'model_calls':0,'paid_api_cost_cny':0,
    'files':files,'hash_basis':'exact Git blob bytes; experiment subtree .gitattributes disables newline conversion',
    'excluded':'model files, raw HTML snapshots, caches, credentials, real individual records',
    'old_results':'no old experimental directory modified; only new subtree and append-only decision log'}
blob=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf8')
(P/'manifest.json').write_bytes(blob);(target/'manifest.json').write_bytes(blob)
log=REPO/'CG/decision_log.md'
entry='''

<!-- c2rag-relation-closure-20261019-01 -->
## 2026-10-19：C²-RAG最小关系重构实测 — PIVOT

已完成P0和极小P1：同一旧开发仿射资产，6序列10检查点×7方法=70行离线判别；2问题序列×2身份计划×11方法=44在线方法回合、88次交付。独立资产仍n=1，不把枚举或重复计划扩成样本。相同公开参数域、候选、权限、联盟Token72及等局部配额、加性成本1。所有风险门只获公开契约和query/reply，不读取隐藏实际系数。

不同点x0→7、x1→10使可能函数21→1；重复x0仍21。原样槽位/Conditional解析器漏掉点方程；成熟Fraction算术闭包识别第二轮增量。用共同方程前端适配的Conditional与算术闭包在4条件逐条交付及Token IDs完全相同，无独立算法收益。域边界单轮危险、矛盾UNKNOWN、未支持改写单列；算术/适配离线0漏警0误警、2/10 UNKNOWN，不冒称全语义正确。

跨身份不同点：Raw/静态/5gram/加性/旧槽位/旧条件均答对2/2、完整恢复1/1、9Token；算术/适配均答对1/2、恢复0/1、14Token，第二题被已有提醒替代，不能算答对。固定3Token把10截成1，答对1/2、恢复0/1、6Token，不能将错误教学当防御优势。策略感知攻击枚举公开机制的完整可见输出；算术阻断后仍21函数。去内容历史/跨身份独立内容历史消融在相同资源下放行互补点；支持内容历史作用，不支持新算法创新。

首版Ngram接收了不必要的含实际系数源字符串，违反严格输入边界的意图，原样保留；新目录重新冻结后使用短输出无5gram的源无关精确判据，不给风险门源系数。未改预算/候选/阈值，输出完全一致，不合并两次为更多样本。2646项有限域消元/枚举核验、882项短输出核验、44回合资源检查通过，8个旧源码/结果文件哈希未改。

P2选OpenStax当前CC BY-NC-SA4.0网页，准备4来源关联资产、8正常问题、8抽取回合和书籍/列明作者/来源知识族分组协议；原始HTML仅本地，发布URL/哈希/精简标注及署名。物理预备留出已为标注阅读，不冒称未见盲测；真实性能评估0。QASC缓存4文件哈希通过但缺文档/作者ID，不承担严格文档留出。公开教材只施加模拟应用授权，不声称真实受限版权。

决策PIVOT：成熟算术闭包足够解释当前正式契约内收益，停止简单内容闭包新算法路线。唯一下一步是两名独立标注者核验真实文档语言—单位—前提—关系契约。新LLM/付费调用0、模型下载0；未改CGC/MM-FOPD/HSW-ST/生产核心。

[组会稿](experiments/2026-10-19-c2rag-relation-closure-01/group_meeting_c2rag.md)、[闭包结果](experiments/2026-10-19-c2rag-relation-closure-01/c2rag_relation_closure_results.md)、[安全效用](experiments/2026-10-19-c2rag-relation-closure-01/c2rag_safety_utility.md)、[CSV](experiments/2026-10-19-c2rag-relation-closure-01/safety_utility.csv)、[P2材料](experiments/2026-10-19-c2rag-relation-closure-01/real_document_preparation.md)、[哈希清单](experiments/2026-10-19-c2rag-relation-closure-01/manifest.json)。
'''
if b'c2rag-relation-closure-20261019-01' not in log.read_bytes():
    with log.open('ab') as f:f.write(entry.encode('utf8'))
git('add','--',DEST,'CG/decision_log.md')
changed=[n for n in git('diff','--cached','--name-only','-z').decode().split('\0') if n]
assert all(n.startswith(DEST+'/') or n=='CG/decision_log.md' for n in changed)
for f in files:assert sha(git('show',':'+DEST+'/'+f['path']))==f['sha256'],f['path']
assert git('show',':CG/decision_log.md').startswith(git('show','HEAD:CG/decision_log.md'))
# No commit or push occurs if any assertion/command above fails.
git('-c','user.name=Codex','-c','user.email=codex@localhost','commit','-m',
    'Add falsifiable C2-RAG arithmetic closure and safety-utility pilot with retained failure')
commit=git('rev-parse','HEAD').decode().strip()
git('push','origin','HEAD:main')
git('fetch','--quiet','origin','main')
git('merge-base','--is-ancestor',commit,'origin/main')
for f in files:assert sha(git('show','origin/main:'+DEST+'/'+f['path']))==f['sha256']
assert sha(git('show','origin/main:'+DEST+'/manifest.json'))==sha(blob)
diff=[n for n in git('diff','--name-only','-z',parent,commit).decode().split('\0') if n]
assert all(n.startswith(DEST+'/') or n=='CG/decision_log.md' for n in diff)
readable=[]
for name in ['README.md','protocol.json','c2rag_relation_closure_results.md','c2rag_safety_utility.md',
             'group_meeting_c2rag.md','safety_utility.csv','manifest.json',
             'figures/组合重构风险.png','figures/正常效用—安全权衡.png']:
    url='https://raw.githubusercontent.com/guoshaung/research-sync/'+commit+'/'+urllib.parse.quote(DEST+'/'+name,safe='/')
    expected=git('show',commit+':'+DEST+'/'+name)
    try:
        with urllib.request.urlopen(url,timeout=25) as response:data=response.read()
        assert sha(data)==sha(expected),name
        readable.append({'path':name,'https_readable':True,'sha256':sha(data)})
    except urllib.error.HTTPError as error:
        if error.code!=404:raise
        readable.append({'path':name,'https_readable':False,'http_status':404,
                         'git_blob_readable':True,'sha256':sha(expected)})
receipt={'status':'SYNCED_REMOTE_GIT_VERIFIED','anonymous_https_all_readable':all(x['https_readable'] for x in readable),'parent_commit':parent,'commit':commit,
         'files_git_blob_verified':len(files)+1,'https_read_checks':readable,
         'old_directories_unchanged_by_this_commit':True,'decision_log_append_only':True,
         'url':'https://github.com/guoshaung/research-sync/tree/'+commit+'/'+DEST}
(P/'sync_receipt.json').write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps({k:v for k,v in receipt.items() if k!='https_read_checks'},ensure_ascii=False))
