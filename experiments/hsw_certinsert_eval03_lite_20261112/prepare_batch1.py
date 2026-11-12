"""Batch1 CPU plans; frozen method reused, explicit XML body-offset adapter."""
from initialize import *
import sys,ast,re,time
sys.path.insert(0,str(W/'experiments/hsw_certinsert_eval_20261111_01'))
import prepare_cpu as p
from e1_v4r8_capacity import capacity
from e1_v4r8_selector import selector
from e1_v4r3_core import pb_tail,exact
D=O/'materials02';Z=O/'prepared_batch1'
def main():
 Z.mkdir(exist_ok=True);voc=read(p.R/'VOCABULARY.json');freq=read(E2/'DOMAIN_FREQUENCIES.json')['probabilities']
 # Source XML solution offset replaces only printed-header discovery; text unchanged.
 src=__import__('inspect').getsource(p.build_plan)
 src=src.replace("start=heads[0].end() if heads else len(t)","start=x.get('body_start',heads[0].end() if heads else len(t))")
 ns=dict(p.__dict__);exec(compile(src,'xml_body_offset_adapter','exec'),ns);build=ns['build_plan']
 det,key=p.make_detector(voc);sel=selector(det,key,4,voc)
 class GlobalDetector:
  words=det.words
  table=det.table
  lexical=det.lexical
 # Same keyed fallback order + unconditional supplement, independent of text.
 rc=selector(det,key,4,voc);global_list=rc('')
 put(Z/'CONFIG.json',dict(source_freeze_sha256=sha(D/'BATCH1_DATA_FREEZE.json'),key_sha256=hashlib.sha256(key).hexdigest(),rc_selected=global_list,method_sha256=read(E/'EVAL_FREEZE.json')['frozen_files']['method']['sha256']))
 for x in read(D/'T4.json'):
  for method in ['CertInsert','RC']:
   ident='T4__'+x['id']+'__'+method;out=Z/(ident+'.json')
   if out.exists():continue
   try:
    plan=build(x,'T4','A4' if method=='RC' else method,(lambda t:global_list) if method=='RC' else sel)
    plan.update(id=ident,method=method);cap=capacity(plan,voc,freq);put(out,dict(plan=plan,capacity=cap))
   except Exception as e:put(out,dict(id=ident,error=type(e).__name__+': '+str(e),status='PREPARATION_FAILED'))
  print('planned',x['id'],flush=True)
 rows=[]
 for x in read(D/'IN_DOMAIN.json'):
  for method in ['CertInsert','RC']:
   try:
    ws=global_list if method=='RC' else sel(x['text']);hit=sum(exact(x['text'],w) for w in ws);pv=pb_tail([freq[w] for w in ws],hit)
    rows.append(dict(id=x['id'],example_id=x['example_id'],chapter=x['chapter'],method=method,selected=ws,hits=hit,p=pv,detected=pv<.01))
   except Exception as e:rows.append(dict(id=x['id'],method=method,error=str(e),p=None,detected=None))
 put(Z/'BACKGROUND_SCORES.json',rows);put(Z/'VOCABULARY.json',voc);put(Z/'FREQUENCIES.json',freq);put(Z/'SCALE.json',read(p.R/'FLUENCY_SCALE_LOCK.json'))
 print('CPU_PREPARED',len(rows),flush=True)
if __name__=='__main__':main()
