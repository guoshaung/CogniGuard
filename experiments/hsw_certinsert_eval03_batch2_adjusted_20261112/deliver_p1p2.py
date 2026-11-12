from common_adjusted import *
import shutil,re,collections,csv

def main():
 d=O/'delivery_P1N10_P2';d.mkdir(exist_ok=False);r=read(O/'P1/RESULT.json');p2=read(O/'P2/COUNTS.json');scores=[read(p) for p in (O/'P1/scores').glob('*.json')];checks=[]
 for m,cells in r['counts'].items():
  for label,aa in cells.items():
   N,mm=[int(v[1:]) for v in label.split('_')]
   for a,v in aa.items():
    rr=[s for s in scores if s['method']==m and s['N']==N and s['m']==mm and s['attack']==a and isinstance(s['detected'],bool)];act=dict(k=sum(s['detected'] for s in rr),n=len(rr)) if rr else None;exp={k:v[k] for k in ['k','n']} if v else None;assert act==exp;checks.append(dict(method=m,label=label,attack=a,actual=act,PASS=True))
 preg=read(O/'P2/per_output.json')
 for m,v in p2.items():assert v==dict(k=sum(x['any_title_or_problem'] for x in preg if x['method']==m),n=sum(x['method']==m for x in preg))
 fc=read(BASE/'batch01_delivery/figure_counts.json');fc['meta'].update(run_id='EVAL03_ADJUSTED_P1_N10_P2',method_unchanged=True,previous_60_pair_queue='SUPERSEDED_26_ATTEMPTS_RETAINED',publication_commit='external SYNC_RECEIPT.json');fc.update(spoofing={},scrubbing={},protected_region_edits=p2,human_eval={m:dict(naturalness_mean=None,added_relation=None,knowledge_error=None) for m in ['CertInsert','RC','Original']});fc['human_eval']['kappa']=None
 for a in ['spoofing','scrubbing']:fc[a]={m:{label:({k:v[a][k] for k in ['k','n']} if v[a] else None) for label,v in cells.items()} for m,cells in r['counts'].items()}
 put(d/'figure_counts.json',fc);put(d/'INDEPENDENT_VALIDATION.json',dict(PASS=True,checks=checks,P2_verified=True));put(d/'INTERVALS.json',r['counts'])
 text='''# 调整版第2批：P1（N=10）与P2

知识锚点选词没有阻止本次频率攻击。观察10份同密钥公开文本后，CertInsert伪造成功56/200（28%），低于RC的85/200（42.5%），但仍是明显的误接受风险。擦除学得短语后，未参与学习的CertInsert 0/29、RC 0/39仍检出。m=4与m=8在本批得到相同检出计数；并不代表更多观察样本没有影响。

|方法|N10,m4伪造|N10,m8伪造|擦除后仍检出,m4|擦除后仍检出,m8|标题或题干插入|
|---|---|---|---|---|---|
|CertInsert|56/200|56/200|0/29|0/29|0/39|
|RC|85/200|85/200|0/39|0/39|41/49|

P2按同批完整成功嵌入输出计算。标题/题干命中是结构位置指标，不自动等于知识错误；同句公式/数值邻近另记，不冒充改动锚点。逐项原文逆变换均通过。

## 分母、限制和未完成项

- 观察样本与主擦除目标按源ID分离；现有水印输出仅CertInsert39、RC49。N50/N200未运行，保持null；不会复制到200。
- 伪造目标200篇未标记正文，学习背景100篇另行划分。检测器不参与攻击词排序或位置选择。攻击者只看公开文本，不读真密钥、插入标记、私有词表。
- 伪造使用词频排序与确定性随机合法句首位置，不用LM打分；它是可复核的低成本频率攻击，不是最强自适应攻击。攻击插入的语义正确性未由真人审核。
- 95%区间见INTERVALS.json，按原始来源模块或输出源聚类。0次事件的bootstrap区间退化，不表示总体风险为0；附描述性Wilson上界。材料来自固定教材，跨章节依赖仍限制外推。
- P3的200道题干、P6的500篇非例题背景已在评分前冻结并提交；本交付不冒称T5已生成。人工审核没有代填。
- 原60篇队列因用户替换协议停止：23个完成、1个连接失败、2个中断，共26个尝试；原始记录保留，没有补跑，未启动压缩攻击。GPU驻留591.451秒。

## 决策

ANALYZE。结构保护有明确工程作用；锚点选词不能作为抵抗观察攻击的充分保证。保留负面结果，继续既定P3及后续独立任务，不改方法。
'''
 (d/'RESULT.md').write_text(text,encoding='utf8');fields=sorted({k for s in scores for k in s})
 with (d/'per_item.csv').open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in s.items()} for s in scores)
 dst=O/'publication_P1N10_P2';dst.mkdir(exist_ok=False)
 def copy(p,r):q=dst/r;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
 for p in d.iterdir():copy(p,p.name)
 for p in E.iterdir():
  if p.is_file():copy(p,'code_and_protocol/'+p.name)
 for folder in ['data','P1','P2']:
  for p in (O/folder).rglob('*'):
   if p.is_file():copy(p,'evidence/'+p.relative_to(O).as_posix())
 for n in ['GENERATION_RESULT.json','GENERATION_FINISHED.json','GPU_USAGE.json','RUN_MANIFEST.jsonl','FAILURES.jsonl','PROTOCOL_REPLACEMENT_PROCESSES.json']:
  p=BASE/'batch02'/n
  if p.exists():copy(p,'superseded_queue/'+n)
 (dst/'LICENSES.md').write_text('OpenStax / Rice University. Original author attribution, pinned revision and official URL for each source are in evidence/data/SOURCE_MANIFEST.json. All selected pinned collections were checked CC BY4.0 in Batch01; reuse those collection receipts. Current editions are not assumed equivalent. Extracted passages and attack modifications are clearly identified; no author endorsement is implied. https://creativecommons.org/licenses/by/4.0/\n',encoding='utf8')
 (dst/'REPRODUCTION.md').write_text('Reported k/n can be independently recomputed from per_item.csv and evidence/P2/per_output.json. Public attack text, ranking and exact source manifests are included. Full private-key rescoring needs owner-controlled CertInsert key; key hashes are not substitutes for key access. No private keys, model weights or runtime environments are redistributed. N50/N200 and human labels remain unmeasured. Batch01 commit ad46db1b138e960a182ab681909ee19fbb12a642 contains original output evidence.\n',encoding='utf8')
 (dst/'.gitattributes').write_text('* -text\n',encoding='utf8')
 secrets=[(W/'var/results/hsw-st/english_replication_20261110_01/e1_guarded/development_round01/restricted/key.bin').read_bytes(),(W/'var/results/hsw-st/english_replication_20261110_01/e1_guarded/frozen_comparison09/restricted/kgw_key.txt').read_bytes()]
 files=[]
 for p in sorted(dst.rglob('*')):
  if not p.is_file():continue
  bb=p.read_bytes();assert not any(s in bb or s.hex().encode() in bb for s in secrets);assert not re.search(rb'sk-[A-Za-z0-9_-]{24,}',bb);assert not re.search(rb'(?m)^-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?$',bb)
  files.append(dict(path=p.relative_to(dst).as_posix(),bytes=len(bb),sha256=hashlib.sha256(bb).hexdigest(),git_blob_sha1=hashlib.sha1(b'blob '+str(len(bb)).encode()+b'\0'+bb).hexdigest()))
 put(dst/'FILE_MANIFEST.json',dict(files=files,bytes=sum(x['bytes'] for x in files),self_excluded=True,secret_scan_PASS=True));print('PACKAGE',len(files),sum(x['bytes'] for x in files))
if __name__=='__main__':main()
