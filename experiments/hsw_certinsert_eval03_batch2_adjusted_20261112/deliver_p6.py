from common_adjusted import *
import shutil,csv

def main():
 d=O/'delivery_P6';d.mkdir(exist_ok=False);r=read(O/'P6/RESULT.json');s=read(O/'P6/key_stress/RESULT.json');rows=[read(p) for p in (O/'P6/scores').glob('*.json')];fc=read(O/'delivery_P1N10_P2/figure_counts.json')
 for m in ['CertInsert','RC']:
  rr=[x for x in rows if x['method']==m and isinstance(x['detected'],bool)];cnt=dict(k=sum(x['detected'] for x in rr),n=len(rr));assert cnt=={k:r['counts'][m][k] for k in ['k','n']};fc['false_positives']['in_domain_1000'][m]=cnt
 fc['meta'].update(run_id='EVAL03_ADJUSTED_P1_N10_P2_P6',actual_in_domain=500,in_domain_1000_is_legacy_label=True,independent_background_modules=s['independent_source_modules'],previous_background91_separate=True)
 fc['pvalue_calibration_adjusted']=s;put(d/'figure_counts.json',fc);put(d/'COUNTS.json',r);put(d/'KEY_CALIBRATION.json',s)
 with (d/'per_item.csv').open('x',encoding='utf-8-sig',newline='') as f:
  fields=sorted({k for x in rows for k in x});w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in x.items()} for x in rows)
 (d/'RESULT.md').write_text('''# P6：新增领域内背景与随机密钥检验

冻结实际密钥：CertInsert与RC均0/500误报。描述性Wilson95%区间为0–0.7624%；500段来自164个源模块、31个章节，不能把段落视为完全独立，更不能把0误报解释为总体零风险。

|检验|CertInsert|RC|
|---|---|---|
|实际密钥，p<.01|0/500|0/500|
|1000随机密钥，p<.001|86/500000|86/500000|
|1000随机密钥，p<.01|362/500000|362/500000|
|1000随机密钥，p<.05|1616/500000|1616/500000|

500000是依赖的“文本×密钥”试验数，不是500000个独立文本。自然背景上的检测统计表现保守；本结果不是p值连续均匀性的证明，也不能抵消P1主动伪造风险。未调整阈值、词频或词表。原91段结果保持原样。

所有背景从固定许可教材中独立抽取，不在例题内，排除了测试章节、T5预留章节及历史文本的精确/子串重复；语义近重复仍不可能由字符筛查完全排除。新增100学习背景、200伪造目标、500本背景相互分离。

本包已验证各计数与原始记录一致；其他阶段继续，P6不触发新算法或参数调整。
''',encoding='utf8')
 dst=O/'publication_P6';dst.mkdir(exist_ok=False)
 def copy(p,rel):q=dst/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
 for p in d.iterdir():copy(p,p.name)
 for p in (O/'P6').rglob('*'):
  if p.is_file():copy(p,'evidence/'+p.relative_to(O/'P6').as_posix())
 for n in ['score_cpu.py','stress_p6.py','P6_STRESS_FREEZE.json','DATA_FREEZE.json','FREEZE.json','PROTOCOL.md','common_adjusted.py']:copy(E/n,'code_and_protocol/'+n)
 copy(O/'data/P6_BACKGROUND.json','inputs/P6_BACKGROUND.json');copy(O/'data/SOURCE_MANIFEST.json','inputs/SOURCE_MANIFEST.json');copy(O/'publication_P1N10_P2/LICENSES.md','LICENSES.md')
 (dst/'.gitattributes').write_text('* -text\n',encoding='utf8');files=[]
 for p in sorted(dst.rglob('*')):
  if p.is_file():
   bb=p.read_bytes();files.append(dict(path=p.relative_to(dst).as_posix(),bytes=len(bb),sha256=hashlib.sha256(bb).hexdigest(),git_blob_sha1=hashlib.sha1(b'blob '+str(len(bb)).encode()+b'\0'+bb).hexdigest()))
 put(dst/'FILE_MANIFEST.json',dict(files=files,self_excluded=True));print('P6 PACKAGE',len(files))
if __name__=='__main__':main()
