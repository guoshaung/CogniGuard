from initialize import *
import csv,math,collections,numpy as np
D=O/'batch01_delivery';rows=list(csv.DictReader((D/'per_item.csv').open(encoding='utf-8-sig')));rng=np.random.default_rng(2026111204);out={}
def ci(rs,col,group):
 groups=collections.defaultdict(list)
 for r in rs:groups[r[group]].append(r[col]=='True')
 aa=np.array([[sum(v),len(v)] for v in groups.values()]);draw=rng.integers(0,len(aa),size=(2000,len(aa)));s=aa[draw].sum(axis=1);rates=s[:,0]/s[:,1];lo,hi=np.quantile(rates,[.025,.975]);return dict(lo=float(lo),hi=float(hi),clusters=len(aa),replicates=2000)
for m in ['CertInsert','RC','Fingerprint']:
 for a in ['none','ocr','crop_first100','crop_middle100']:
  rs=[r for r in rows if r['kind']=='evaluation' and r['method']==m and r['attack']==a and r['conditional_eligible']=='True' and r['detected'] in ['True','False']]
  if rs:out[m+'.'+a]=ci(rs,'detected','source_id')
for m in ['CertInsert','RC']:out[m+'.coverage']=ci([r for r in rows if r['kind']=='coverage' and r['method']==m],'watermarkable','source_id')
put(D/'BOOTSTRAP_INTERVALS.json',dict(seed=2026111204,unit='source example',intervals=out,limitations='Source-level conditional intervals; chapter dependence and limited subject diversity remain. All-zero background bootstrap would be degenerate and is not used to claim FPR certification.'))
errors=[{k:r.get(k) for k in ['id','method','attack','detection_error','quality_error','fingerprint_error']} for r in rows if r.get('detection_error') or r.get('quality_error') or r.get('fingerprint_error')]
put(D/'PUBLIC_PARSE_ERRORS.json',errors)
put(D/'RESOURCE_USAGE.json',dict(GPU_forward_scoring_seconds=read(O/'scoring_recovery01/INSERT_T4_all_RESULT.json')['seconds'],GPU_generation_calls=0,paid_API_calls=0,OCR=read(O/'ocr/FINISHED.json'),parallel_trial=read(O/'ocr/parallel01/SCALE8_TRIAL.json'),eight_workers_returned=read(O/'ocr/parallel01/SCALE8_FINISHED.json')['workers'],four_workers_returned=read(O/'ocr/parallel01/RESULT.json')['workers']))
upper=1.959963984540054**2/(91+1.959963984540054**2)
p=D/'RESULT.md';s=p.read_text();s=s.replace('unw atermarkable','unwatermarkable')
s+='\n\n## Important limitations and calibration\n\n'
s+=f'CertInsert and RC each have 0/91 in-domain false positives. Descriptive paragraph-level Wilson95% upper bound is {upper:.4%}; paragraphs derive from77 examples and are not fully independent. Requested1000 was not reached.1000 diagnostic keys×91 passages yield zero alarms at .001/.01/.05, indicating conservative behavior on this limited material, not proof of uniform p-values or a validated global FPR. No threshold was refitted.\n\n'
s+='All326 OCR tasks completed. The unchanged anchor parser cannot score two CertInsert OCR texts and five Fingerprint OCR texts (empty formula spans cause TypeError); these remain UNKNOWN, not negative or silently repaired. CertInsert OCR is29/37 scorable, with2/39 UNKNOWN; Fingerprint OCR is213/233 scorable, with5/238 UNKNOWN. RC scores use its global list and remain scorable; mechanical quality may still be unknown. PUBLIC_PARSE_ERRORS.json retains details.\n\n'
s+='Full-denominator CertInsert coverage/detection is39/238=16.4%; conditional original detection39/39 is not population effectiveness. RC is49/238=20.6%. This batch does not demonstrate an overall advantage over RC or fingerprint retrieval. Short excerpts lose substantial insertion signal. Fingerprint source identity and watermark detection are different tasks, and denominators differ. No recipient attribution claim is made.\n\n'
s+='No>400-word explanation example survived the frozen material screening/split, so that bin is unmeasured. Materials are177 mathematics,48 statistics,13 astronomy examples; these results cannot establish performance on the previously excluded physics/chemistry chapters.\n\n'
s+='## Decision\n\nANALYZE. Engineering batch completed with explicit material shortfalls; scientific evidence remains limited. Batch02/03 are NOT_RUN. No new parameters or vocabulary were adopted.\n'
p.write_text(s,encoding='utf8')
print('errors',len(errors),'intervals',len(out))
