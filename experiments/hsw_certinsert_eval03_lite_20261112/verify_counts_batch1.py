"""Independent standard-library recomputation of all published count cells."""
import csv,json,sys
from pathlib import Path
def main():
 d=Path(sys.argv[1]);fc=json.loads((d/'figure_counts.json').read_text(encoding='utf8'));rows=list(csv.DictReader((d/'per_item.csv').open(encoding='utf-8-sig',newline='')));paired=set(json.loads((d/'PAIRED_IDS.json').read_text(encoding='utf8')));checks=[]
 def ck(path,actual,expected):
  checks.append(dict(path=path,actual=actual,expected=expected,PASS=actual==expected));assert actual==expected,(path,actual,expected)
 def cnt(rr,key):return dict(k=sum(r.get(key)=='True' for r in rr),n=len(rr)) if rr else None
 for m in ['CertInsert','RC']:ck('coverage.T4.'+m,fc['coverage']['T4'][m],cnt([r for r in rows if r['kind']=='coverage' and r['method']==m],'watermarkable'))
 for ds in ['T4','T4_paired100']:
  for m,attacks in fc['detection'][ds].items():
   for a,v in attacks.items():
    rr=[r for r in rows if r['kind']=='evaluation' and r['method']==m and r['attack']==a and r['conditional_eligible']=='True' and r['detected'] in ['True','False'] and (ds=='T4' or r['source_id'] in paired)];ck(f'detection.{ds}.{m}.{a}',v,cnt(rr,'detected'))
 for m in ['CertInsert','RC']:ck('false_positives.'+m,fc['false_positives']['in_domain_1000'][m],cnt([r for r in rows if r['kind']=='false_positive' and r['method']==m and r['detected'] in ['True','False']],'detected'))
 for alpha,v in fc['pvalue_calibration']['empirical_rate'].items():
  rr=[r for r in rows if r['kind']=='pvalue_calibration' and r['alpha']==alpha];ck('pvalue.'+alpha,v,sum(int(r['k']) for r in rr)/sum(int(r['n']) for r in rr))
 for label,key in [('restore_pass','certificate'),('anchor_invariant_pass','anchor_invariant')]:ck('certificate.'+label,fc['certificate']['T4'][label],cnt([r for r in rows if r['kind']=='evaluation' and r['method']=='CertInsert' and r['attack']=='none'],key))
 for m,v in fc['numbers_formulas_intact']['T4_paired100'].items():ck('numbers_formulas.'+m,v,cnt([r for r in rows if r['kind']=='evaluation' and r['method']==m and r['attack']=='none' and r['source_id'] in paired and r['numeric_formula_intact'] in ['True','False']],'numeric_formula_intact'))
 def band(n):return '<100' if n<100 else '100-200' if n<=200 else '200-400' if n<=400 else '>400'
 for b,v in fc['coverage_by_length']['T4'].items():ck('length.'+b,v,cnt([r for r in rows if r['kind']=='coverage' and r['method']=='CertInsert' and band(int(r['explanation_words']))==b],'watermarkable'))
 def walk(x):
  if isinstance(x,dict):
   if set(x)=={'k','n'}:assert 0<=x['k']<=x['n']
   for v in x.values():walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
 walk(fc);ck('coverage_equals_none_denominator',fc['coverage']['T4']['CertInsert']['k'],fc['detection']['T4']['CertInsert']['none']['n'])
 result=dict(PASS=True,rows=len(rows),checks=checks)
 with (d/'INDEPENDENT_COUNTS_VALIDATION.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
 print('PASS',len(checks),'checks',len(rows),'rows')
if __name__=='__main__':main()
