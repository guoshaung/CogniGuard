from initialize import *
import csv,collections,subprocess

def main():
 z=O/'evaluation_batch1';assert (z/'FINISHED.json').exists(),'EVALUATION_NOT_COMPLETE'
 out=O/'batch01_delivery';out.mkdir(exist_ok=True)
 rows=[read(p) for p in (z/'records').glob('*.json')];lookup={r['id']:r for r in rows};records={r['id']:r for r in read(O/'INSERT_T4_all_RESULT.json')['rows']};records.update({r['id']:r for r in read(O/'scoring_recovery01/INSERT_T4_all_RESULT.json')['rows']})
 cov=[];success=set()
 for r in records.values():
  q=lookup.get(r['id'],{});ok=r['status']=='PREDICTED_TARGET_REACHED' and q.get('certificate') is True and q.get('anchor_invariant') is True and q.get('selection_invariant') is True
  if ok:success.add(r['id'])
  cov.append(dict(kind='coverage',id=r['id'],source_id=r['source_id'],dataset='T4',method=r['method'],status=r['status'],watermarkable=ok,explanation_words=next(x['explanation_words'] for x in read(O/'materials02/T4.json') if x['id']==r['source_id']),inserted_entries=r['inserted_entries'],seconds=r['seconds']))
 for r in rows:r['conditional_eligible']=r['method']=='Fingerprint' or 'T4__'+r['source_id']+'__'+r['method'] in success
 bg=[dict(r,kind='false_positive',dataset='in_domain_1000') for r in read(O/'prepared_batch1/BACKGROUND_SCORES.json')]
 stress=read(O/'key_stress/RESULT.json');pr=[]
 for ident,counts in stress['per_text'].items():
  for alpha,k in counts.items():pr.append(dict(kind='pvalue_calibration',id=ident,alpha=alpha,k=k,n=stress['keys']))
 allrows=cov+rows+bg+pr;fields=sorted({k for r in allrows for k in r})
 with (out/'per_item.csv').open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in allrows)
 def count(rr,field):return dict(k=sum(r.get(field) is True for r in rr),n=len(rr)) if rr else None
 methods=['CertInsert','RC','KGW','Unigram','Fingerprint'];attacks=['none','ocr','crop_first100','crop_middle100','compress70'];datasets=['T4','T5','T4_paired100'];paired=set(read(O/'materials02/PAIRED_IDS.json'))
 fc=dict(meta=dict(run_id='EVAL-03-LITE-BATCH01',commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),commit_role='code parent; final publication commit in external sync receipt',freeze_sha256=sha(E/'EVAL_FREEZE.json'),batch_freeze_sha256=sha(E/'BATCH1_FINAL_INPUT_FREEZE.json'),calibration='unchanged EVAL02 domain null',actual_T4=238,actual_in_domain=91,independent_background_examples=77,paired_actual=60,T4_paired100_is_legacy_label=True),coverage={d:{m:None for m in ['CertInsert','RC']} for d in ['T4','T5']},coverage_by_length={d:{b:None for b in ['<100','100-200','200-400','>400']} for d in ['T4','T5']},detection={d:{m:{a:None for a in attacks} for m in methods} for d in datasets},false_positives={d:{m:None for m in methods[:-1]} for d in ['in_domain_1000','general_300']},certificate={d:{k:None for k in ['restore_pass','anchor_invariant_pass']} for d in ['T4','T5']},numbers_formulas_intact={'T4_paired100':{m:None for m in methods[:-1]}},compression_detail={'T4_paired100':{m:None for m in methods}},detection_note='Conditional successful-embedding denominator; NOT_APPLICABLE short crops and failed OCR excluded and separately recorded. Fingerprint is unique positive Top1, not watermark detection.')
 for m in ['CertInsert','RC']:
  fc['coverage']['T4'][m]=count([r for r in cov if r['method']==m],'watermarkable');fc['false_positives']['in_domain_1000'][m]=count([r for r in bg if r['method']==m and r['detected'] is not None],'detected')
 def band(n):return '<100' if n<100 else '100-200' if n<=200 else '200-400' if n<=400 else '>400'
 for b in fc['coverage_by_length']['T4']:fc['coverage_by_length']['T4'][b]=count([r for r in cov if r['method']=='CertInsert' and band(r['explanation_words'])==b],'watermarkable')
 for d in ['T4','T4_paired100']:
  for m in methods:
   for a in attacks:fc['detection'][d][m][a]=count([r for r in rows if r['method']==m and r['attack']==a and r['conditional_eligible'] and r.get('detected') is not None and (d=='T4' or r['source_id'] in paired)],'detected')
 cc=[r for r in rows if r['method']=='CertInsert' and r['attack']=='none']
 fc['certificate']['T4']=dict(restore_pass=count(cc,'certificate'),anchor_invariant_pass=count(cc,'anchor_invariant'))
 for m in methods[:-1]:fc['numbers_formulas_intact']['T4_paired100'][m]=count([r for r in rows if r['method']==m and r['attack']=='none' and r['source_id'] in paired and r.get('numeric_formula_intact') is not None],'numeric_formula_intact')
 fc['pvalue_calibration']=dict(keys=stress['keys'],passages=stress['actual_texts'],independent_source_examples=stress['independent_examples'],empirical_rate={a:sum(r['k'] for r in pr if r['alpha']==a)/sum(r['n'] for r in pr if r['alpha']==a) for a in ['0.001','0.01','0.05']},warning='Dependent key-text trials; 91 passages do not meet requested1000. No global error guarantee.')
 put(out/'figure_counts.json',fc)
 put(out/'SUMMARY_RECOMPUTATION.json',dict(source='per_item.csv',coverage='kind=coverage, sum watermarkable / actual assessed rows',detection='kind=evaluation, conditional_eligible=true, non-null detected; group dataset/method/attack; paired requires PAIRED_IDS membership',coverage_length='CertInsert coverage grouped by explanation_words: <100,100..200,200<w<=400,>400',false_positive='kind=false_positive, non-null detected; sum detected / scorable',pvalue='kind=pvalue_calibration, grouped alpha, sum(k)/sum(n); n is diagnostic keys, not independent sources',certificate='CertInsert none evaluation rows, sum certificate / rows; same for anchor_invariant',numbers_formulas='none evaluation rows in paired IDs, sum numeric_formula_intact / non-null rows'))
 assert fc['coverage']['T4']['CertInsert']['k']==(fc['detection']['T4']['CertInsert']['none'] or {'n':0})['n']
 text=['# Batch01 result','', 'This is an exploratory material extension, not a final method superiority conclusion.','',f"Actual T4:238; background:91 paragraphs/77 examples (requested1000 unmet); paired IDs:60.",'', '|Method|Coverage|None|OCR|First100|Middle100|','|---|---|---|---|---|---|']
 for m in ['CertInsert','RC','Fingerprint']:
  vals=[fc['coverage']['T4'].get(m)]+[fc['detection']['T4'][m][a] for a in attacks[:4]];text.append('|'+m+'|'+'|'.join('NOT_RUN/N/A' if v is None else f"{v['k']}/{v['n']}" for v in vals)+'|')
 text+=['','Knowledge checks are mechanical and provisional; no human knowledge/naturalness gold labels.','Source composition is mathematics/statistics/astronomy. Historical physics/chemistry chapters excluded.','Original pre-model path failures retained; recovery resumes only zero-call scoring slots. RC completed outputs were not repeated.','Conditional detection does not include unw atermarkable sources; coverage is reported separately.','GPU is forward scoring only. No7B generation in Batch01.']
 (out/'RESULT.md').write_text('\n'.join(text),encoding='utf8');print(json.dumps(fc['coverage']))
if __name__=='__main__':main()
